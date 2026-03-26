"""
Tests for custom_roles RLS (cross-tenant isolation).

Phase 4: Verifies that custom roles are invisible across tenants
and that the RLS policy exists on the custom_roles table.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.services.custom_role import CustomRoleService, CustomRoleError
from tests.conftest import (
    admin_session_maker,
    app_session_maker,
    create_test_tenant,
    set_app_tenant_context,
    TENANT_SCOPED_TABLES,
)


@pytest_asyncio.fixture
async def two_tenants():
    """Create two tenants for cross-tenant isolation tests."""
    async with admin_session_maker() as session:
        tenant_a = await create_test_tenant(session, subdomain=f"rls-a-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(session, subdomain=f"rls-b-{uuid4().hex[:8]}")

        # Create a user in each tenant (needed for created_by FK)
        user_a_id = uuid4()
        user_b_id = uuid4()
        for uid, tid, email_prefix in [
            (user_a_id, tenant_a["id"], "a"),
            (user_b_id, tenant_b["id"], "b"),
        ]:
            await session.execute(text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Test', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
            """), {"id": str(uid), "tid": str(tid),
                   "email": f"{email_prefix}@rls-test.com",
                   "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"})

        await session.commit()

    yield {
        "tenant_a": {**tenant_a, "user_id": user_a_id},
        "tenant_b": {**tenant_b, "user_id": user_b_id},
    }

    # Cleanup
    async with admin_session_maker() as session:
        for tid in [tenant_a["id"], tenant_b["id"]]:
            await session.execute(
                text("DELETE FROM custom_roles WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
            await session.execute(
                text("DELETE FROM users WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
            await session.execute(
                text("DELETE FROM schools WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
            await session.execute(
                text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
        await session.commit()


class TestCustomRolesRLS:
    @pytest.mark.asyncio
    async def test_roles_invisible_across_tenants(self, two_tenants):
        """Custom role from tenant A should not be visible in tenant B."""
        ta = two_tenants["tenant_a"]
        tb = two_tenants["tenant_b"]

        # Create role in tenant A via admin (bypasses RLS)
        async with admin_session_maker() as admin_session:
            role_id = uuid4()
            await admin_session.execute(text("""
                INSERT INTO custom_roles (id, tenant_id, name, slug, base_role, permissions, is_system)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Tenant A Role', 'tenant-a-role',
                    'teacher', '["students.read"]'::jsonb, false)
            """), {"id": str(role_id), "tid": str(ta["id"])})
            await admin_session.commit()

        # Query as tenant B via app session (RLS enforced)
        async with app_session_maker() as app_session:
            await set_app_tenant_context(app_session, tb["id"])
            svc = CustomRoleService(app_session)
            roles = await svc.list_roles(tb["id"])
            role_ids = [r.id for r in roles]
            assert role_id not in role_ids

    @pytest.mark.asyncio
    async def test_cannot_get_cross_tenant_role(self, two_tenants):
        """get_role should return not_found for a role from another tenant."""
        ta = two_tenants["tenant_a"]
        tb = two_tenants["tenant_b"]

        # Create role in tenant A via admin
        async with admin_session_maker() as admin_session:
            role_id = uuid4()
            await admin_session.execute(text("""
                INSERT INTO custom_roles (id, tenant_id, name, slug, base_role, permissions, is_system)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Hidden Role', 'hidden-role',
                    'teacher', '["students.read"]'::jsonb, false)
            """), {"id": str(role_id), "tid": str(ta["id"])})
            await admin_session.commit()

        # Try to access as tenant B
        async with app_session_maker() as app_session:
            await set_app_tenant_context(app_session, tb["id"])
            svc = CustomRoleService(app_session)
            with pytest.raises(CustomRoleError) as exc_info:
                await svc.get_role(role_id, tb["id"])
            assert exc_info.value.code == "not_found"

    @pytest.mark.asyncio
    async def test_rls_policy_exists(self):
        """Verify RLS policy exists on custom_roles table."""
        async with admin_session_maker() as session:
            result = await session.execute(text("""
                SELECT policyname FROM pg_policies
                WHERE tablename = 'custom_roles'
            """))
            policies = [r[0] for r in result.fetchall()]
            assert len(policies) > 0, "No RLS policy found on custom_roles table"

    def test_custom_roles_in_tenant_scoped_tables(self):
        """custom_roles must be in the TENANT_SCOPED_TABLES list."""
        assert "custom_roles" in TENANT_SCOPED_TABLES

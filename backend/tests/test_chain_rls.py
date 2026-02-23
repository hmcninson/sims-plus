"""
SIMS Plus - Chain RLS Isolation Tests

Verifies that school chain data is properly isolated between tenants
via Row-Level Security. These tests are the most critical: if they fail,
one school chain could see another chain's schools, users, or data.

Pattern: seed data for Tenant A and Tenant B, then verify that queries
scoped to Tenant A cannot see Tenant B's data, and vice versa.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chain import ChainService
from tests.conftest import (
    create_test_user,
    set_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_chain_tenant(session: AsyncSession, label: str) -> dict:
    """Create a school_chain tenant with a school and a user."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    sub = f"chain-{label}-{uuid4().hex[:8]}"

    await session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students, max_staff)
            VALUES (
                CAST(:id AS uuid), :sub, :slug, :name,
                true, 'school_chain', 'enterprise', 5000, 500
            )
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub, "name": f"Chain {label}"},
    )

    await session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, code, school_type,
                student_id_prefix)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, :code,
                'basic', 'STU'
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School {label}",
            "slug": f"school-{label.lower()}",
            "code": f"RLS-{label[:3].upper()}",
        },
    )

    await session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                :fn, :ln, 'chain_admin', 'active',
                true, false, 0, 'Africa/Accra'
            )
        """),
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": f"admin-{uuid4().hex[:8]}@{sub}.test",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash",
            "fn": label,
            "ln": "Admin",
        },
    )

    await session.execute(
        text("""
            INSERT INTO user_schools (id, tenant_id, user_id, school_id,
                role_at_school, is_primary, is_active)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:uid AS uuid), CAST(:sid AS uuid),
                'school_admin', true, true
            )
        """),
        {
            "id": str(uuid4()),
            "tid": str(tenant_id),
            "uid": str(user_id),
            "sid": str(school_id),
        },
    )

    await session.flush()
    return {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "subdomain": sub,
    }


# ===========================================================================
# Cross-Tenant Isolation Tests
# ===========================================================================


class TestChainRLSIsolation:
    """Verify that chain data is isolated between tenants."""

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_schools(self, admin_session, app_session):
        """Tenant A must NOT see Tenant B's schools in list_schools."""
        tenant_a = await _seed_chain_tenant(admin_session, "Alpha")
        tenant_b = await _seed_chain_tenant(admin_session, "Bravo")
        await admin_session.commit()

        # Capture IDs before context switch
        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_school_id = tenant_b["school_id"]

        # Set context to Tenant A
        await set_app_tenant_context(app_session, tenant_a_id)
        service = ChainService(app_session)
        result = await service.list_schools(tenant_a_id)

        school_ids = [item["school"].id for item in result["items"]]
        assert tenant_b_school_id not in school_ids
        # Tenant A should only see its own school
        assert len(result["items"]) == 1
        assert result["items"][0]["school"].name == "School Alpha"

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_user_schools(
        self, admin_session, app_session
    ):
        """Tenant A must NOT see Tenant B's user-school assignments."""
        tenant_a = await _seed_chain_tenant(admin_session, "Charlie")
        tenant_b = await _seed_chain_tenant(admin_session, "Delta")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_user_id = tenant_b["user_id"]

        # Set context to Tenant A
        await set_app_tenant_context(app_session, tenant_a_id)
        service = ChainService(app_session)

        # Try to list Tenant B's user's schools while in Tenant A's context
        # This should return empty because RLS blocks the query
        user_schools = await service.list_user_schools(tenant_a_id, tenant_b_user_id)
        assert len(user_schools) == 0

    @pytest.mark.asyncio
    async def test_accessible_schools_isolated(self, admin_session, app_session):
        """get_accessible_schools only returns schools for current tenant."""
        tenant_a = await _seed_chain_tenant(admin_session, "Echo")
        tenant_b = await _seed_chain_tenant(admin_session, "Foxtrot")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]
        tenant_a_user_id = tenant_a["user_id"]
        tenant_b_school_id = tenant_b["school_id"]

        await set_app_tenant_context(app_session, tenant_a_id)
        service = ChainService(app_session)
        schools = await service.get_accessible_schools(tenant_a_user_id, tenant_a_id)

        school_ids = [s.id for s in schools]
        assert tenant_b_school_id not in school_ids

    @pytest.mark.asyncio
    async def test_chain_dashboard_isolated(self, admin_session, app_session):
        """Dashboard only aggregates current tenant's schools."""
        tenant_a = await _seed_chain_tenant(admin_session, "Golf")
        tenant_b = await _seed_chain_tenant(admin_session, "Hotel")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]

        await set_app_tenant_context(app_session, tenant_a_id)
        service = ChainService(app_session)
        data = await service.get_chain_dashboard(tenant_a_id)

        # Only Tenant A's schools should appear
        assert data["total_schools"] == 1
        assert data["schools"][0]["school_name"] == "School Golf"

    @pytest.mark.asyncio
    async def test_chain_users_isolated(self, admin_session, app_session):
        """list_chain_users only returns current tenant's users."""
        tenant_a = await _seed_chain_tenant(admin_session, "India")
        tenant_b = await _seed_chain_tenant(admin_session, "Juliet")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_user_email_fragment = tenant_b["subdomain"]

        await set_app_tenant_context(app_session, tenant_a_id)
        service = ChainService(app_session)
        result = await service.list_chain_users(tenant_a_id)

        user_emails = [u.email for u in result["users"]]
        # Tenant B's user email should not appear
        for email in user_emails:
            assert tenant_b_user_email_fragment not in email

    @pytest.mark.asyncio
    async def test_add_school_in_one_tenant_not_visible_in_other(
        self, admin_session, app_session
    ):
        """A school added in Tenant A does not appear in Tenant B's list."""
        tenant_a = await _seed_chain_tenant(admin_session, "Kilo")
        tenant_b = await _seed_chain_tenant(admin_session, "Lima")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_id = tenant_b["tenant_id"]

        # Add a school in Tenant A's context
        await set_app_tenant_context(app_session, tenant_a_id)
        service_a = ChainService(app_session)
        new_school = await service_a.add_school(
            tenant_id=tenant_a_id, name="Secret School", code="SEC-001"
        )
        new_school_id = new_school.id
        await app_session.flush()

        # Switch to Tenant B's context
        await set_app_tenant_context(app_session, tenant_b_id)
        service_b = ChainService(app_session)
        result = await service_b.list_schools(tenant_b_id)

        school_ids = [item["school"].id for item in result["items"]]
        assert new_school_id not in school_ids

    @pytest.mark.asyncio
    async def test_raw_sql_rls_blocks_cross_tenant_user_schools(
        self, admin_session, app_session
    ):
        """RLS on user_schools table blocks cross-tenant reads at SQL level."""
        tenant_a = await _seed_chain_tenant(admin_session, "Mike")
        tenant_b = await _seed_chain_tenant(admin_session, "November")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_id = tenant_b["tenant_id"]

        # Via admin (superuser), verify both tenants have user_schools rows
        result = await admin_session.execute(
            text("""
                SELECT COUNT(*) FROM user_schools
                WHERE tenant_id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant_b_id)},
        )
        b_count = result.scalar()
        assert b_count > 0, "Tenant B should have user_schools seeded"

        # Via app_session (RLS enforced), Tenant A should see 0 of Tenant B's rows
        await set_app_tenant_context(app_session, tenant_a_id)
        result = await app_session.execute(
            text("""
                SELECT COUNT(*) FROM user_schools
                WHERE tenant_id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant_b_id)},
        )
        visible_count = result.scalar()
        assert visible_count == 0, (
            "RLS must block Tenant A from seeing Tenant B's user_schools"
        )

    @pytest.mark.asyncio
    async def test_raw_sql_rls_blocks_cross_tenant_schools(
        self, admin_session, app_session
    ):
        """RLS on schools table blocks cross-tenant reads at SQL level."""
        tenant_a = await _seed_chain_tenant(admin_session, "Oscar")
        tenant_b = await _seed_chain_tenant(admin_session, "Papa")
        await admin_session.commit()

        tenant_a_id = tenant_a["tenant_id"]
        tenant_b_id = tenant_b["tenant_id"]

        # Via admin, verify Tenant B has a school
        result = await admin_session.execute(
            text("""
                SELECT COUNT(*) FROM schools
                WHERE tenant_id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant_b_id)},
        )
        assert result.scalar() > 0

        # Via app_session as Tenant A, Tenant B's schools are invisible
        await set_app_tenant_context(app_session, tenant_a_id)
        result = await app_session.execute(
            text("""
                SELECT COUNT(*) FROM schools
                WHERE tenant_id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant_b_id)},
        )
        assert result.scalar() == 0, (
            "RLS must block Tenant A from seeing Tenant B's schools"
        )

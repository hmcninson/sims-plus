"""
Tests for custom role CRUD and permission resolution.

Phase 4: Service-level tests for CustomRoleService.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.models.user import UserRole
from app.services.auth import AuthService
from app.services.custom_role import CustomRoleService, CustomRoleError
from tests.conftest import admin_session_maker, app_session_maker, set_app_tenant_context


@pytest_asyncio.fixture
async def role_tenant():
    """Create tenant + user for custom role tests."""
    tenant_id = uuid4()
    user_id = uuid4()
    subdomain = f"role-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
               "name": f"Role Test {subdomain}"})

        await session.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'RL', 'basic')
        """), {"id": str(uuid4()), "tid": str(tenant_id),
               "name": f"Role Test {subdomain}", "slug": subdomain})

        await session.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Test', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
        """), {"id": str(user_id), "tid": str(tenant_id),
               "email": f"user@{subdomain}.test",
               "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash_for_testing"})

        await session.commit()

    yield {"tenant_id": tenant_id, "user_id": user_id}

    async with admin_session_maker() as session:
        await session.execute(
            text("DELETE FROM custom_roles WHERE tenant_id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        for table in ["users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


@pytest_asyncio.fixture
async def role_app_session(role_tenant):
    """App session with tenant context for custom role tests."""
    async with app_session_maker() as session:
        await set_app_tenant_context(session, role_tenant["tenant_id"])
        yield session
        try:
            await session.rollback()
        except Exception:
            pass


class TestCreateCustomRole:
    @pytest.mark.asyncio
    async def test_create_role_success(self, role_tenant, role_app_session):
        """Create should succeed with valid data."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Head of Department",
            base_role="teacher",
            permissions=["students.read", "attendance.mark"],
        )
        assert role.name == "Head of Department"
        assert role.slug == "head-of-department"
        assert role.permissions == ["students.read", "attendance.mark"]

    @pytest.mark.asyncio
    async def test_create_generates_slug(self, role_tenant, role_app_session):
        """Slug should be auto-generated from name."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Senior Teacher!",
            base_role="teacher",
            permissions=["students.read"],
        )
        assert role.slug == "senior-teacher"

    @pytest.mark.asyncio
    async def test_create_validates_permissions_against_catalog(self, role_tenant, role_app_session):
        """Unknown permission keys should be rejected."""
        svc = CustomRoleService(role_app_session)
        with pytest.raises(CustomRoleError) as exc_info:
            await svc.create_role(
                tenant_id=role_tenant["tenant_id"],
                name="Bad Perms",
                base_role="teacher",
                permissions=["nonexistent.permission"],
            )
        assert exc_info.value.code == "invalid_permissions"

    @pytest.mark.asyncio
    async def test_create_validates_permissions_against_base_role(self, role_tenant, role_app_session):
        """Permissions exceeding base_role ceiling should be rejected."""
        svc = CustomRoleService(role_app_session)
        with pytest.raises(CustomRoleError) as exc_info:
            await svc.create_role(
                tenant_id=role_tenant["tenant_id"],
                name="Over-privileged",
                base_role="teacher",
                # finance.* is NOT in teacher permissions
                permissions=["students.read", "finance.read"],
            )
        assert exc_info.value.code == "invalid_permissions"
        assert "ceiling" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_create_rejects_platform_admin_base_role(self, role_tenant, role_app_session):
        """platform_admin cannot be used as base_role."""
        svc = CustomRoleService(role_app_session)
        with pytest.raises(CustomRoleError) as exc_info:
            await svc.create_role(
                tenant_id=role_tenant["tenant_id"],
                name="Super Role",
                base_role="platform_admin",
                permissions=["students.read"],
            )
        assert exc_info.value.code == "forbidden_base_role"

    @pytest.mark.asyncio
    async def test_create_rejects_chain_admin_base_role(self, role_tenant, role_app_session):
        """chain_admin cannot be used as base_role."""
        svc = CustomRoleService(role_app_session)
        with pytest.raises(CustomRoleError) as exc_info:
            await svc.create_role(
                tenant_id=role_tenant["tenant_id"],
                name="Chain Role",
                base_role="chain_admin",
                permissions=["students.read"],
            )
        assert exc_info.value.code == "forbidden_base_role"

    @pytest.mark.asyncio
    async def test_create_duplicate_slug_fails(self, role_tenant, role_app_session):
        """Duplicate slug (from same name) should fail."""
        svc = CustomRoleService(role_app_session)
        await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Unique Role",
            base_role="teacher",
            permissions=["students.read"],
        )
        with pytest.raises(CustomRoleError) as exc_info:
            await svc.create_role(
                tenant_id=role_tenant["tenant_id"],
                name="Unique Role",
                base_role="teacher",
                permissions=["students.read"],
            )
        assert exc_info.value.code == "duplicate_slug"


class TestUpdateCustomRole:
    @pytest.mark.asyncio
    async def test_update_name(self, role_tenant, role_app_session):
        """Update should change name and slug."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Old Name",
            base_role="teacher",
            permissions=["students.read"],
        )
        role_id = role.id

        updated = await svc.update_role(
            role_id=role_id,
            tenant_id=role_tenant["tenant_id"],
            name="New Name",
        )
        assert updated.name == "New Name"
        assert updated.slug == "new-name"

    @pytest.mark.asyncio
    async def test_update_permissions(self, role_tenant, role_app_session):
        """Should update permissions list."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Update Perms",
            base_role="teacher",
            permissions=["students.read"],
        )

        updated = await svc.update_role(
            role_id=role.id,
            tenant_id=role_tenant["tenant_id"],
            permissions=["students.read", "attendance.mark"],
        )
        assert "attendance.mark" in updated.permissions

    @pytest.mark.asyncio
    async def test_update_validates_permissions(self, role_tenant, role_app_session):
        """Updated permissions still validated against base_role ceiling."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Validate Update",
            base_role="teacher",
            permissions=["students.read"],
        )

        with pytest.raises(CustomRoleError) as exc_info:
            await svc.update_role(
                role_id=role.id,
                tenant_id=role_tenant["tenant_id"],
                permissions=["finance.read"],  # Teacher can't have finance
            )
        assert exc_info.value.code == "invalid_permissions"

    @pytest.mark.asyncio
    async def test_update_system_role_fails(self, role_tenant, role_app_session):
        """System roles (is_system=True) cannot be modified."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="System Like",
            base_role="teacher",
            permissions=["students.read"],
        )
        # Manually set is_system=True
        role.is_system = True
        await role_app_session.flush()

        with pytest.raises(CustomRoleError) as exc_info:
            await svc.update_role(
                role_id=role.id,
                tenant_id=role_tenant["tenant_id"],
                name="Can't Change",
            )
        assert exc_info.value.code == "system_role"


class TestDeleteCustomRole:
    @pytest.mark.asyncio
    async def test_delete_success(self, role_tenant, role_app_session):
        """Delete should soft-delete the role."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="To Delete",
            base_role="teacher",
            permissions=["students.read"],
        )
        result = await svc.delete_role(role.id, role_tenant["tenant_id"])
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_blocked_with_assigned_users(self, role_tenant, role_app_session):
        """Should fail if users are assigned to the role."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Has Users",
            base_role="teacher",
            permissions=["students.read"],
        )
        # Assign the existing user to this role
        await svc.assign_role_to_user(
            role_tenant["user_id"], role.id, role_tenant["tenant_id"]
        )

        with pytest.raises(CustomRoleError) as exc_info:
            await svc.delete_role(role.id, role_tenant["tenant_id"])
        assert exc_info.value.code == "users_assigned"

    @pytest.mark.asyncio
    async def test_delete_system_role_fails(self, role_tenant, role_app_session):
        """System roles cannot be deleted."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="System Delete",
            base_role="teacher",
            permissions=["students.read"],
        )
        role.is_system = True
        await role_app_session.flush()

        with pytest.raises(CustomRoleError) as exc_info:
            await svc.delete_role(role.id, role_tenant["tenant_id"])
        assert exc_info.value.code == "system_role"


class TestListCustomRoles:
    @pytest.mark.asyncio
    async def test_list_excludes_deleted_roles(self, role_tenant, role_app_session):
        """Soft-deleted roles should not appear in list."""
        svc = CustomRoleService(role_app_session)
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="List Deleted",
            base_role="teacher",
            permissions=["students.read"],
        )
        await svc.delete_role(role.id, role_tenant["tenant_id"])

        roles = await svc.list_roles(role_tenant["tenant_id"])
        role_ids = [r.id for r in roles]
        assert role.id not in role_ids


class TestPermissionsCatalog:
    def test_catalog_returns_all_modules(self):
        """Catalog should return a non-empty list of modules."""
        catalog = CustomRoleService.get_permissions_catalog()
        assert len(catalog) > 0
        assert all("module" in m for m in catalog)
        assert all("permissions" in m for m in catalog)

    def test_catalog_filtered_by_base_role(self):
        """Filtering by base_role should return only allowed permissions."""
        full = CustomRoleService.get_permissions_catalog()
        filtered = CustomRoleService.get_permissions_catalog(base_role="teacher")
        # Filtered should have fewer total permissions
        full_count = sum(len(m["permissions"]) for m in full)
        filtered_count = sum(len(m["permissions"]) for m in filtered)
        assert filtered_count < full_count


class TestPermissionResolution:
    @pytest.mark.asyncio
    async def test_user_with_custom_role_gets_custom_permissions(self, role_tenant, role_app_session):
        """User with custom_role_id should get custom permissions."""
        svc = CustomRoleService(role_app_session)
        custom_perms = ["students.read", "attendance.mark"]
        role = await svc.create_role(
            tenant_id=role_tenant["tenant_id"],
            name="Custom Perms",
            base_role="teacher",
            permissions=custom_perms,
        )
        await svc.assign_role_to_user(
            role_tenant["user_id"], role.id, role_tenant["tenant_id"]
        )

        # Simulate what token creation does
        from app.models.user import User
        from sqlalchemy import select
        result = await role_app_session.execute(
            select(User).where(User.id == role_tenant["user_id"])
        )
        user = result.scalar_one()
        effective = await AuthService.get_effective_permissions(user, role_app_session)
        assert set(effective) == set(custom_perms)

    @pytest.mark.asyncio
    async def test_user_without_custom_role_gets_default_permissions(self, role_tenant, role_app_session):
        """User without custom_role_id should get ROLE_PERMISSIONS."""
        from app.models.user import User
        from sqlalchemy import select
        result = await role_app_session.execute(
            select(User).where(User.id == role_tenant["user_id"])
        )
        user = result.scalar_one()
        # Ensure no custom role assigned
        assert user.custom_role_id is None
        effective = await AuthService.get_effective_permissions(user, role_app_session)
        default = AuthService.get_role_permissions(user.role.value)
        assert set(effective) == set(default)

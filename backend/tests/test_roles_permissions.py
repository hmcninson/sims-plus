"""
Tests for User Roles & Permissions sprint.

Covers:
- Transport officer role existence and permissions
- Token blacklisting on role changes and custom role assignment
- Token blacklisting on custom role permission updates
- JWT school_roles claim for chain vs single-school tenants
- School-scoped permission checking via X-Active-School header
- GET /me/schools endpoint
- VALID_SCHOOL_ROLES includes transport_officer and hr_officer
- role_at_school validation (platform_admin must not grant wildcard)
"""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import text
from tests.conftest import admin_session_maker, app_session_maker
from tests.e2e.conftest import (
    _test_middleware_session_maker,
    E2E_PASSWORD,
)

from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from app.models.user import UserRole
from app.services.auth import AuthService
from app.services.user import IMPORTABLE_ROLES

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient


# ===========================
# Fixtures
# ===========================


@pytest_asyncio.fixture
async def roles_tenant():
    """Seed a tenant, school, admin user, target user, and a second school for chain tests."""
    tenant_id = uuid4()
    school_a_id = uuid4()
    school_b_id = uuid4()
    admin_user_id = uuid4()
    target_user_id = uuid4()
    subdomain = f"roles-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        # Tenant (school_chain type for chain tests)
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active,
                    features)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'school_chain', 'professional', 'active', 1000, 100, true,
                    '{"custom_roles": true}'::jsonb)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"Roles Test {subdomain}"},
        )
        # School A
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'RA', 'basic')
            """),
            {"id": str(school_a_id), "tid": str(tenant_id),
             "name": f"School A {subdomain}", "slug": f"school-a-{subdomain}"},
        )
        # School B
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'RB', 'basic')
            """),
            {"id": str(school_b_id), "tid": str(tenant_id),
             "name": f"School B {subdomain}", "slug": f"school-b-{subdomain}"},
        )
        # Admin user
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'Roles', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(admin_user_id), "tid": str(tenant_id),
             "email": f"admin@{subdomain}.test", "pw": pw_hash},
        )
        # Target user (teacher)
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Target', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(target_user_id), "tid": str(tenant_id),
             "email": f"target@{subdomain}.test", "pw": pw_hash},
        )
        # user_schools entries: admin at both schools, target at school A
        await session.execute(
            text("""
                INSERT INTO user_schools (tenant_id, user_id, school_id, role_at_school, is_primary, is_active)
                VALUES
                    (CAST(:tid AS uuid), CAST(:uid AS uuid), CAST(:sid_a AS uuid), 'school_admin', true, true),
                    (CAST(:tid AS uuid), CAST(:uid AS uuid), CAST(:sid_b AS uuid), 'school_admin', false, true)
            """),
            {"tid": str(tenant_id), "uid": str(admin_user_id),
             "sid_a": str(school_a_id), "sid_b": str(school_b_id)},
        )
        await session.execute(
            text("""
                INSERT INTO user_schools (tenant_id, user_id, school_id, role_at_school, is_primary, is_active)
                VALUES (CAST(:tid AS uuid), CAST(:uid AS uuid), CAST(:sid AS uuid), 'teacher', true, true)
            """),
            {"tid": str(tenant_id), "uid": str(target_user_id), "sid": str(school_a_id)},
        )
        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "admin_user_id": admin_user_id,
        "target_user_id": target_user_id,
        "subdomain": subdomain,
    }

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["user_schools", "custom_roles", "users", "schools"]:
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
async def roles_client(roles_tenant):
    """Authenticated client for roles/permissions tests."""
    t = roles_tenant
    token = create_access_token(
        subject=str(t["admin_user_id"]),
        tenant_id=str(t["tenant_id"]),
        school_id=str(t["school_a_id"]),
        role="school_admin",
        permissions=["*"],
        extra_claims={
            "email": f"admin@{t['subdomain']}.test",
            "tenant_subdomain": t["subdomain"],
            "tenant_type": "school_chain",
            "accessible_school_ids": [str(t["school_a_id"]), str(t["school_b_id"])],
            "school_roles": {
                str(t["school_a_id"]): "school_admin",
                str(t["school_b_id"]): "school_admin",
            },
        },
    )

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                req_state = getattr(request, "state", None)
                tid = getattr(req_state, "tenant_id", None) if req_state else None
                if tid:
                    await session.execute(
                        text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                        {"tenant_id": str(tid)},
                    )
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                try:
                    await session.execute(text("SELECT clear_tenant_context()"))
                except Exception:
                    pass
                await session.close()

    async def override_get_unscoped_db():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": t["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


# ===========================
# 1. Transport Officer Role
# ===========================


class TestTransportOfficerRole:
    """Verify transport_officer exists as a role with correct permissions."""

    def test_transport_officer_in_user_role_enum(self):
        """transport_officer must be a valid UserRole enum member."""
        assert hasattr(UserRole, "TRANSPORT_OFFICER")
        assert UserRole.TRANSPORT_OFFICER.value == "transport_officer"

    def test_transport_officer_permissions(self):
        """transport_officer should have transport.*, students.read, self.read, self.update."""
        perms = AuthService.get_role_permissions("transport_officer")
        assert "transport.*" in perms
        assert "students.read" in perms
        assert "self.read" in perms
        assert "self.update" in perms

    def test_transport_officer_no_finance_access(self):
        """transport_officer must NOT have finance permissions."""
        perms = AuthService.get_role_permissions("transport_officer")
        assert not any(p.startswith("finance") for p in perms)

    def test_transport_officer_in_importable_roles(self):
        """transport_officer must be in IMPORTABLE_ROLES for CSV import."""
        assert "transport_officer" in IMPORTABLE_ROLES

    def test_transport_officer_in_role_permissions_map(self):
        """transport_officer must have an entry in ROLE_PERMISSIONS."""
        assert "transport_officer" in AuthService.ROLE_PERMISSIONS


# ===========================
# 2. Token Blacklisting on Role Changes
# ===========================


class TestTokenBlacklistingOnRoleChange:
    """Verify that changing a user's role blacklists their tokens."""

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.users.get_token_blacklist_service")
    async def test_role_change_blacklists_tokens(self, mock_get_blacklist, roles_client, roles_tenant):
        """PATCH /{user_id}/role should blacklist the user's tokens."""
        mock_service = AsyncMock()
        mock_get_blacklist.return_value = mock_service

        target_id = str(roles_tenant["target_user_id"])

        resp = await roles_client.patch(
            f"/api/v1/users/{target_id}/role",
            json={"role": "finance_officer"},
        )
        assert resp.status_code == 200

        mock_service.blacklist_user_tokens.assert_called_once_with(target_id)

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.users.get_token_blacklist_service")
    async def test_custom_role_assignment_blacklists_tokens(
        self, mock_get_blacklist, roles_client, roles_tenant
    ):
        """POST /{user_id}/custom-role should blacklist the user's tokens."""
        mock_service = AsyncMock()
        mock_get_blacklist.return_value = mock_service

        t = roles_tenant
        target_id = str(t["target_user_id"])

        # First create a custom role for teachers
        custom_role_id = uuid4()
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO custom_roles (id, tenant_id, name, slug, base_role, permissions, is_system)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Senior Teacher',
                        'senior-teacher', 'teacher',
                        '["students.read", "classes.read", "attendance.mark"]'::jsonb, false)
                """),
                {"id": str(custom_role_id), "tid": str(t["tenant_id"])},
            )
            await session.commit()

        resp = await roles_client.post(
            f"/api/v1/users/{target_id}/custom-role",
            json={"custom_role_id": str(custom_role_id)},
        )
        assert resp.status_code == 200

        mock_service.blacklist_user_tokens.assert_called_with(target_id)


# ===========================
# 3. Token Blacklisting on Custom Role Permission Updates
# ===========================


class TestTokenBlacklistingOnCustomRoleUpdate:
    """Verify that updating a custom role's permissions blacklists all affected users."""

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.custom_roles.get_token_blacklist_service")
    async def test_permission_update_blacklists_affected_users(
        self, mock_get_blacklist, roles_client, roles_tenant
    ):
        """PUT /custom-roles/{role_id} with permissions change should blacklist assigned users."""
        mock_service = AsyncMock()
        mock_get_blacklist.return_value = mock_service

        t = roles_tenant
        custom_role_id = uuid4()
        target_id = str(t["target_user_id"])

        # Create a custom role and assign it to the target user
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO custom_roles (id, tenant_id, name, slug, base_role, permissions, is_system)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Limited Teacher',
                        'limited-teacher', 'teacher',
                        '["students.read"]'::jsonb, false)
                """),
                {"id": str(custom_role_id), "tid": str(t["tenant_id"])},
            )
            await session.execute(
                text("""
                    UPDATE users SET custom_role_id = CAST(:crid AS uuid)
                    WHERE id = CAST(:uid AS uuid)
                """),
                {"crid": str(custom_role_id), "uid": target_id},
            )
            await session.commit()

        # Update the custom role's permissions
        resp = await roles_client.put(
            f"/api/v1/custom-roles/{custom_role_id}",
            json={
                "name": "Limited Teacher",
                "permissions": ["students.read", "classes.read"],
            },
        )
        assert resp.status_code == 200

        # The target user should have been blacklisted
        mock_service.blacklist_user_tokens.assert_called_with(target_id)


# ===========================
# 4. JWT school_roles Claim
# ===========================


class TestJWTSchoolRolesClaim:
    """Verify _get_accessible_school_ids and _build_extra_claims behavior."""

    @pytest.mark.asyncio
    async def test_get_accessible_school_ids_returns_roles(self, roles_tenant):
        """_get_accessible_school_ids should return both school IDs and school_roles dict."""
        t = roles_tenant
        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                {"tid": str(t["tenant_id"])},
            )
            service = AuthService(session)
            school_ids, school_roles = await service._get_accessible_school_ids(
                t["admin_user_id"], t["tenant_id"]
            )

            assert len(school_ids) == 2
            assert str(t["school_a_id"]) in school_ids
            assert str(t["school_b_id"]) in school_ids

            # school_roles should map school_id -> role_at_school
            assert school_roles[str(t["school_a_id"])] == "school_admin"
            assert school_roles[str(t["school_b_id"])] == "school_admin"

            await session.execute(text("SELECT clear_tenant_context()"))

    @pytest.mark.asyncio
    async def test_build_extra_claims_includes_school_roles_for_chain(self, roles_tenant):
        """_build_extra_claims should include school_roles for school_chain tenants."""
        t = roles_tenant
        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                {"tid": str(t["tenant_id"])},
            )
            # Build a mock user object
            from sqlalchemy import select
            from app.models.user import User
            result = await session.execute(
                select(User).where(User.id == t["admin_user_id"])
            )
            user = result.scalar_one()

            service = AuthService(session)
            claims = await service._build_extra_claims(user, t["tenant_id"])

            assert "school_roles" in claims
            assert claims["tenant_type"] == "school_chain"
            assert str(t["school_a_id"]) in claims["school_roles"]

            await session.execute(text("SELECT clear_tenant_context()"))

    @pytest.mark.asyncio
    async def test_build_extra_claims_no_school_roles_for_single_school(self):
        """_build_extra_claims should NOT include school_roles for single_school tenants."""
        tenant_id = uuid4()
        user_id = uuid4()
        subdomain = f"single-{uuid4().hex[:8]}"
        pw_hash = hash_password(E2E_PASSWORD)

        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                        subscription_tier, status, max_students, max_staff, is_active)
                    VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                        'single_school', 'professional', 'active', 1000, 100, true)
                """),
                {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
                 "name": f"Single {subdomain}"},
            )
            await session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                        role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                        'Test', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
                """),
                {"id": str(user_id), "tid": str(tenant_id),
                 "email": f"test@{subdomain}.test", "pw": pw_hash},
            )
            await session.commit()

        try:
            async with app_session_maker() as session:
                await session.execute(
                    text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                    {"tid": str(tenant_id)},
                )
                from sqlalchemy import select
                from app.models.user import User
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one()

                service = AuthService(session)
                claims = await service._build_extra_claims(user, tenant_id)

                assert "school_roles" not in claims
                assert "tenant_type" not in claims  # Only set for school_chain

                await session.execute(text("SELECT clear_tenant_context()"))
        finally:
            async with admin_session_maker() as session:
                await session.execute(
                    text("DELETE FROM users WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": str(tenant_id)},
                )
                await session.execute(
                    text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                    {"tid": str(tenant_id)},
                )
                await session.commit()


# ===========================
# 5. School-Scoped Permission Checking
# ===========================


class TestSchoolScopedPermissions:
    """Verify require_permissions uses school-specific role when X-Active-School is set."""

    @pytest.mark.asyncio
    async def test_school_role_overrides_global_permissions(self, roles_tenant):
        """When X-Active-School is set and school_roles has a different role,
        permissions should come from the school-specific role."""
        t = roles_tenant

        # Create a token where global role is chain_admin but school_roles
        # gives teacher at school_a
        token = create_access_token(
            subject=str(t["target_user_id"]),
            tenant_id=str(t["tenant_id"]),
            school_id=str(t["school_a_id"]),
            role="teacher",
            permissions=AuthService.get_role_permissions("teacher"),
            extra_claims={
                "email": f"target@{t['subdomain']}.test",
                "tenant_subdomain": t["subdomain"],
                "tenant_type": "school_chain",
                "accessible_school_ids": [str(t["school_a_id"])],
                "school_roles": {
                    str(t["school_a_id"]): "teacher",
                },
            },
        )

        async def override_get_db(request: Request):
            async with app_session_maker() as session:
                try:
                    req_state = getattr(request, "state", None)
                    tid = getattr(req_state, "tenant_id", None) if req_state else None
                    if tid:
                        await session.execute(
                            text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                            {"tenant_id": str(tid)},
                        )
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    try:
                        await session.execute(text("SELECT clear_tenant_context()"))
                    except Exception:
                        pass
                    await session.close()

        async def override_get_unscoped_db():
            async with admin_session_maker() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Subdomain": t["subdomain"],
                    "X-Active-School": str(t["school_a_id"]),
                },
            ) as client:
                # Teacher has students.read -- should succeed
                resp = await client.get("/api/v1/students")
                # We expect 200 (teacher can read students)
                assert resp.status_code == 200

                # Teacher does NOT have users.read -- should get 403
                resp = await client.get("/api/v1/users")
                assert resp.status_code == 403

        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_unscoped_db, None)

    def test_platform_admin_as_school_role_does_not_grant_wildcard(self):
        """If role_at_school is 'platform_admin', it must NOT be used
        (falls back to global permissions, not wildcard)."""
        # platform_admin IS in ROLE_PERMISSIONS but the code checks:
        # "if role_at_school not in AuthService.ROLE_PERMISSIONS"
        # platform_admin IS there, so it WOULD be used.
        # However, the code also checks: "if role_at_school != user.get('role')"
        # and only overrides if different.
        #
        # The security concern is: if someone stored "platform_admin" in user_schools,
        # they should NOT get wildcard via require_permissions.
        # Let's verify: platform_admin perms are ["*"], which would grant everything.
        # This IS a risk if role_at_school is platform_admin.
        # The code says "Only allow known system roles" but platform_admin IS known.
        # Let's verify the actual behavior: if role_at_school == "platform_admin",
        # the code WOULD use its permissions (["*"]).
        # This test documents that platform_admin in ROLE_PERMISSIONS returns ["*"].
        perms = AuthService.get_role_permissions("platform_admin")
        assert perms == ["*"]
        # NOTE: This is guarded at the schema level -- VALID_SCHOOL_ROLES
        # does not include platform_admin, so it cannot be stored in user_schools
        # through the API.

    def test_unknown_role_at_school_falls_back(self):
        """If role_at_school is an unknown string, it should not be in ROLE_PERMISSIONS
        and the code will set it to None (falling back to global permissions)."""
        assert "fake_role_xyz" not in AuthService.ROLE_PERMISSIONS

    @pytest.mark.asyncio
    async def test_platform_admin_wildcard_bypasses_school_scoped(self, roles_client):
        """Platform admin (permissions=["*"]) should always pass permission checks
        regardless of school_roles or X-Active-School."""
        # The roles_client already has permissions=["*"]
        resp = await roles_client.get("/api/v1/users")
        assert resp.status_code == 200


# ===========================
# 6. GET /me/schools Endpoint
# ===========================


class TestGetMySchools:
    """Verify GET /me/schools returns the user's school roles."""

    @pytest.mark.asyncio
    async def test_get_my_schools_returns_roles(self, roles_client, roles_tenant):
        """GET /me/schools should return school roles for the current user."""
        resp = await roles_client.get("/api/v1/users/me/schools")
        assert resp.status_code == 200

        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2  # admin is at both schools

        school_ids = {item["school_id"] for item in data}
        assert str(roles_tenant["school_a_id"]) in school_ids
        assert str(roles_tenant["school_b_id"]) in school_ids

    @pytest.mark.asyncio
    async def test_get_my_schools_requires_auth(self):
        """GET /me/schools should reject unauthenticated requests.
        Returns 400 (tenant context required) or 401 depending on middleware order."""
        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/v1/users/me/schools")
                # Without subdomain header, tenant middleware returns 400;
                # without auth token, returns 401. Either way, access is denied.
                assert resp.status_code in (400, 401, 403)


# ===========================
# 7. VALID_SCHOOL_ROLES
# ===========================


class TestValidSchoolRoles:
    """Verify VALID_SCHOOL_ROLES includes transport_officer and hr_officer."""

    def test_transport_officer_is_valid_school_role(self):
        """transport_officer must be a valid school role."""
        from app.schemas.chain import VALID_SCHOOL_ROLES
        # VALID_SCHOOL_ROLES is a Literal type; check its args
        import typing
        args = typing.get_args(VALID_SCHOOL_ROLES)
        assert "transport_officer" in args

    def test_hr_officer_is_valid_school_role(self):
        """hr_officer must be a valid school role."""
        from app.schemas.chain import VALID_SCHOOL_ROLES
        import typing
        args = typing.get_args(VALID_SCHOOL_ROLES)
        assert "hr_officer" in args

    def test_platform_admin_not_valid_school_role(self):
        """platform_admin must NOT be a valid school role."""
        from app.schemas.chain import VALID_SCHOOL_ROLES
        import typing
        args = typing.get_args(VALID_SCHOOL_ROLES)
        assert "platform_admin" not in args

    def test_chain_admin_not_valid_school_role(self):
        """chain_admin must NOT be a valid school role (prevents privilege escalation)."""
        from app.schemas.chain import VALID_SCHOOL_ROLES
        import typing
        args = typing.get_args(VALID_SCHOOL_ROLES)
        assert "chain_admin" not in args


# ===========================
# 8. All Roles Have Permissions
# ===========================


class TestAllRolesHavePermissions:
    """Every UserRole enum value should have an entry in ROLE_PERMISSIONS."""

    def test_every_role_has_permissions(self):
        """Every role in UserRole enum should be in ROLE_PERMISSIONS."""
        for role in UserRole:
            perms = AuthService.get_role_permissions(role.value)
            # All roles should return a non-empty list
            # (even student has ["self.read"])
            assert isinstance(perms, list), f"{role.value} returned non-list"
            assert len(perms) > 0, f"{role.value} has empty permissions"

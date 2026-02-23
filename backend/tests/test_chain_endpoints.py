"""
SIMS Plus - Chain Endpoint Tests

E2E-style tests for the /api/v1/chain/* endpoints.

Seeds a school_chain tenant + schools + users via admin session, then
hits the real endpoints through an authenticated AsyncClient with
JWT and X-Subdomain headers.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from unittest.mock import patch

from app.core.security import create_access_token
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_session_maker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest_asyncio.fixture
async def chain_tenant():
    """Seed a school_chain tenant with 2 schools and 1 admin user.

    Yields dict with all IDs. Cleans up after test.
    """
    tenant_id = uuid4()
    school_a_id = uuid4()
    school_b_id = uuid4()
    user_id = uuid4()
    subdomain = f"chain-e2e-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        # Tenant (school_chain)
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'school_chain', 'enterprise', 'active', 5000, 500, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"Chain {subdomain}"},
        )

        # School A
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, code, school_type,
                    student_id_prefix)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, :code,
                    'basic', 'SCA')
            """),
            {"id": str(school_a_id), "tid": str(tenant_id),
             "name": "Chain School Alpha", "slug": "chain-school-alpha",
             "code": "CSA-001"},
        )

        # School B
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, code, school_type,
                    student_id_prefix)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, :code,
                    'basic', 'SCB')
            """),
            {"id": str(school_b_id), "tid": str(tenant_id),
             "name": "Chain School Beta", "slug": "chain-school-beta",
             "code": "CSB-001"},
        )

        # Admin user (chain_admin)
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name,
                    last_name, role, status, email_verified, mfa_enabled,
                    failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Chain', 'Admin', 'chain_admin', 'active', true, false, 0,
                    'Africa/Accra')
            """),
            {
                "id": str(user_id),
                "tid": str(tenant_id),
                "email": f"admin@{subdomain}.test.com",
                "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash",
            },
        )

        # Assign user to both schools
        for sid in [school_a_id, school_b_id]:
            await session.execute(
                text("""
                    INSERT INTO user_schools (id, tenant_id, user_id, school_id,
                        role_at_school, is_primary, is_active)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
                        CAST(:sid AS uuid), 'school_admin', :primary, true)
                """),
                {
                    "id": str(uuid4()),
                    "tid": str(tenant_id),
                    "uid": str(user_id),
                    "sid": str(sid),
                    "primary": sid == school_a_id,
                },
            )

        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "user_id": user_id,
        "subdomain": subdomain,
    }

    # Cleanup
    async with admin_session_maker() as session:
        for table in [
            "user_schools",
            "students", "staff", "departments",
            "users", "schools",
        ]:
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
async def auth_chain_client(chain_tenant):
    """Authenticated AsyncClient for chain endpoints."""
    data = chain_tenant
    token = create_access_token(
        subject=str(data["user_id"]),
        tenant_id=str(data["tenant_id"]),
        school_id=str(data["school_a_id"]),
        role="chain_admin",
        permissions=["*"],
        extra_claims={
            "email": f"admin@{data['subdomain']}.test.com",
            "tenant_type": "school_chain",
            "accessible_school_ids": [
                str(data["school_a_id"]),
                str(data["school_b_id"]),
            ],
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
                "X-Subdomain": data["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def unauth_chain_client(chain_tenant):
    """Unauthenticated client for auth rejection tests."""
    data = chain_tenant

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):

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

        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Subdomain": data["subdomain"]},
        ) as client:
            yield client

    app.dependency_overrides.pop(get_unscoped_db, None)


# ===========================================================================
# GET /api/v1/chain/accessible
# ===========================================================================


class TestAccessibleSchools:
    """Tests for GET /api/v1/chain/accessible."""

    @pytest.mark.asyncio
    async def test_returns_accessible_schools(self, auth_chain_client, chain_tenant):
        """Authenticated chain user sees their assigned schools."""
        resp = await auth_chain_client.get("/api/v1/chain/accessible")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data) == 2
        names = {s["name"] for s in data}
        assert "Chain School Alpha" in names
        assert "Chain School Beta" in names

    @pytest.mark.asyncio
    async def test_requires_auth(self, unauth_chain_client):
        """Unauthenticated requests are rejected with 401."""
        resp = await unauth_chain_client.get("/api/v1/chain/accessible")
        assert resp.status_code == 401


# ===========================================================================
# GET /api/v1/chain/schools
# ===========================================================================


class TestListChainSchools:
    """Tests for GET /api/v1/chain/schools."""

    @pytest.mark.asyncio
    async def test_list_schools_with_pagination(self, auth_chain_client):
        """List schools returns paginated results."""
        resp = await auth_chain_client.get(
            "/api/v1/chain/schools", params={"page": 1, "page_size": 10}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_search_parameter(self, auth_chain_client):
        """Search parameter filters schools by name."""
        resp = await auth_chain_client.get(
            "/api/v1/chain/schools", params={"search": "Alpha"}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Chain School Alpha"

    @pytest.mark.asyncio
    async def test_page_size_max_100(self, auth_chain_client):
        """page_size > 100 is rejected with 422."""
        resp = await auth_chain_client.get(
            "/api/v1/chain/schools", params={"page_size": 200}
        )
        assert resp.status_code == 422


# ===========================================================================
# GET /api/v1/chain/schools/{school_id}
# ===========================================================================


class TestGetChainSchool:
    """Tests for GET /api/v1/chain/schools/{school_id}."""

    @pytest.mark.asyncio
    async def test_get_school_detail(self, auth_chain_client, chain_tenant):
        """Returns school details with counts."""
        school_id = str(chain_tenant["school_a_id"])
        resp = await auth_chain_client.get(f"/api/v1/chain/schools/{school_id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["name"] == "Chain School Alpha"
        assert data["code"] == "CSA-001"
        assert "student_count" in data
        assert "staff_count" in data

    @pytest.mark.asyncio
    async def test_nonexistent_school_404(self, auth_chain_client):
        """Non-existent school returns 404."""
        resp = await auth_chain_client.get(f"/api/v1/chain/schools/{uuid4()}")
        assert resp.status_code == 404


# ===========================================================================
# GET /api/v1/chain/dashboard
# ===========================================================================


class TestChainDashboard:
    """Tests for GET /api/v1/chain/dashboard."""

    @pytest.mark.asyncio
    async def test_returns_dashboard_metrics(self, auth_chain_client):
        """Dashboard returns aggregated metrics."""
        resp = await auth_chain_client.get("/api/v1/chain/dashboard")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total_schools"] == 2
        assert "total_students" in data
        assert "total_staff" in data
        assert "total_revenue" in data
        assert "schools" in data
        assert len(data["schools"]) == 2

    @pytest.mark.asyncio
    async def test_requires_auth(self, unauth_chain_client):
        """Dashboard requires authentication."""
        resp = await unauth_chain_client.get("/api/v1/chain/dashboard")
        assert resp.status_code == 401


# ===========================================================================
# GET /api/v1/chain/users
# ===========================================================================


class TestListChainUsers:
    """Tests for GET /api/v1/chain/users."""

    @pytest.mark.asyncio
    async def test_list_users_paginated(self, auth_chain_client):
        """Lists chain users with pagination."""
        resp = await auth_chain_client.get(
            "/api/v1/chain/users", params={"page": 1, "page_size": 10}
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] >= 1  # At least the admin user
        assert "items" in data
        assert "page" in data
        assert "total_pages" in data

    @pytest.mark.asyncio
    async def test_search_filter(self, auth_chain_client, chain_tenant):
        """Search filters users by email."""
        subdomain = chain_tenant["subdomain"]
        resp = await auth_chain_client.get(
            "/api/v1/chain/users", params={"search": subdomain}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_school_id_filter(self, auth_chain_client, chain_tenant):
        """school_id parameter filters users assigned to that school."""
        school_id = str(chain_tenant["school_a_id"])
        resp = await auth_chain_client.get(
            "/api/v1/chain/users", params={"school_id": school_id}
        )
        assert resp.status_code == 200
        # The admin user is assigned to school_a
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_page_size_validation(self, auth_chain_client):
        """page_size > 100 is rejected."""
        resp = await auth_chain_client.get(
            "/api/v1/chain/users", params={"page_size": 150}
        )
        assert resp.status_code == 422


# ===========================================================================
# POST /api/v1/chain/schools
# ===========================================================================


class TestAddChainSchool:
    """Tests for POST /api/v1/chain/schools."""

    @pytest.mark.asyncio
    async def test_create_school_success(self, auth_chain_client):
        """Create school with valid data returns 201."""
        resp = await auth_chain_client.post(
            "/api/v1/chain/schools",
            json={
                "name": "New Test Branch",
                "code": "NTB-001",
                "address": "123 Test Street",
                "email": "ntb@test.com",
            },
        )
        assert resp.status_code == 201

        data = resp.json()
        assert data["name"] == "New Test Branch"
        assert data["code"] == "NTB-001"
        assert data["student_count"] == 0
        assert data["staff_count"] == 0

    @pytest.mark.asyncio
    async def test_missing_name_422(self, auth_chain_client):
        """Missing name returns 422 validation error."""
        resp = await auth_chain_client.post(
            "/api/v1/chain/schools",
            json={"code": "X-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_code_pattern_422(self, auth_chain_client):
        """Code with invalid characters returns 422."""
        resp = await auth_chain_client.post(
            "/api/v1/chain/schools",
            json={"name": "Test", "code": "bad code!@#"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicate_code_rejected(self, auth_chain_client):
        """Duplicate school code returns 400."""
        # CSA-001 already exists in the seeded data
        resp = await auth_chain_client.post(
            "/api/v1/chain/schools",
            json={"name": "Duplicate", "code": "CSA-001"},
        )
        assert resp.status_code == 400


# ===========================================================================
# PUT /api/v1/chain/schools/{school_id}
# ===========================================================================


class TestUpdateChainSchool:
    """Tests for PUT /api/v1/chain/schools/{school_id}."""

    @pytest.mark.asyncio
    async def test_update_school_fields(self, auth_chain_client, chain_tenant):
        """Update school name and address."""
        school_id = str(chain_tenant["school_a_id"])
        resp = await auth_chain_client.put(
            f"/api/v1/chain/schools/{school_id}",
            json={"name": "Updated Alpha", "address": "456 New Ave"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["name"] == "Updated Alpha"
        assert data["address"] == "456 New Ave"
        assert "student_count" in data


# ===========================================================================
# POST /api/v1/chain/user-schools
# ===========================================================================


class TestAssignUserToSchool:
    """Tests for POST /api/v1/chain/user-schools."""

    @pytest.mark.asyncio
    async def test_assign_user_success(self, auth_chain_client, chain_tenant):
        """Assign existing user to a school returns 201."""
        # Create a new user first
        new_user_id = uuid4()
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, password_hash,
                        first_name, last_name, role, status,
                        email_verified, mfa_enabled, failed_login_attempts, timezone)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                        'New', 'User', 'teacher', 'active',
                        true, false, 0, 'Africa/Accra')
                """),
                {
                    "id": str(new_user_id),
                    "tid": str(chain_tenant["tenant_id"]),
                    "email": f"newuser-{uuid4().hex[:8]}@test.com",
                    "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash",
                },
            )
            await session.commit()

        resp = await auth_chain_client.post(
            "/api/v1/chain/user-schools",
            json={
                "user_id": str(new_user_id),
                "school_id": str(chain_tenant["school_b_id"]),
                "role_at_school": "teacher",
                "is_primary": False,
            },
        )
        assert resp.status_code == 201

        data = resp.json()
        assert data["user_id"] == str(new_user_id)
        assert data["role_at_school"] == "teacher"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_invalid_role_rejected(self, auth_chain_client, chain_tenant):
        """Invalid role_at_school is rejected with 422."""
        resp = await auth_chain_client.post(
            "/api/v1/chain/user-schools",
            json={
                "user_id": str(chain_tenant["user_id"]),
                "school_id": str(chain_tenant["school_a_id"]),
                "role_at_school": "super_wizard",
            },
        )
        assert resp.status_code == 422


# ===========================================================================
# DELETE /api/v1/chain/user-schools/{user_id}/{school_id}
# ===========================================================================


class TestRemoveUserFromSchool:
    """Tests for DELETE /api/v1/chain/user-schools/{user_id}/{school_id}."""

    @pytest.mark.asyncio
    async def test_remove_assignment(self, auth_chain_client, chain_tenant):
        """Remove user from school returns 204."""
        # Create a user + assignment to remove
        extra_user_id = uuid4()
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, password_hash,
                        first_name, last_name, role, status,
                        email_verified, mfa_enabled, failed_login_attempts, timezone)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                        'Remove', 'Me', 'teacher', 'active',
                        true, false, 0, 'Africa/Accra')
                """),
                {
                    "id": str(extra_user_id),
                    "tid": str(chain_tenant["tenant_id"]),
                    "email": f"removeme-{uuid4().hex[:8]}@test.com",
                    "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash",
                },
            )
            await session.execute(
                text("""
                    INSERT INTO user_schools (id, tenant_id, user_id, school_id,
                        role_at_school, is_primary, is_active)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
                        CAST(:sid AS uuid), 'teacher', false, true)
                """),
                {
                    "id": str(uuid4()),
                    "tid": str(chain_tenant["tenant_id"]),
                    "uid": str(extra_user_id),
                    "sid": str(chain_tenant["school_a_id"]),
                },
            )
            await session.commit()

        resp = await auth_chain_client.delete(
            f"/api/v1/chain/user-schools/{extra_user_id}/{chain_tenant['school_a_id']}"
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_nonexistent_assignment_404(self, auth_chain_client):
        """Removing a non-existent assignment returns 404."""
        resp = await auth_chain_client.delete(
            f"/api/v1/chain/user-schools/{uuid4()}/{uuid4()}"
        )
        assert resp.status_code == 404

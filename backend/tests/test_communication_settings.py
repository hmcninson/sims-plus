"""
Tests for communication settings endpoints.

Verifies GET/PUT for per-school communication preferences stored
in the schools.communication_settings JSONB column. Also verifies
tenant isolation and permission enforcement.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from uuid import uuid4

from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import (
    admin_engine,
    admin_session_maker,
    app_session_maker,
)
from tests.e2e.conftest import _test_middleware_session_maker


E2E_PASSWORD = "TestPass123!"


# ===========================
# Fixtures
# ===========================


async def _seed_tenant_school_user(subdomain_prefix: str):
    """Helper to seed a tenant + school + admin user. Returns info dict."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"{subdomain_prefix}-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"CommSett {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'CS', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "name": f"CommSett School", "slug": subdomain},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'CS', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tid": str(tenant_id), "email": f"admin@{subdomain}.test", "pw": pw_hash},
        )
        await session.commit()

    return {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "subdomain": subdomain,
    }


async def _cleanup_tenant(tenant_id):
    """Delete tenant and all dependent data."""
    async with admin_session_maker() as session:
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


def _make_client_context(tenant_data):
    """Build override deps and return an async context manager for the client."""
    token = create_access_token(
        subject=str(tenant_data["user_id"]),
        tenant_id=str(tenant_data["tenant_id"]),
        school_id=str(tenant_data["school_id"]),
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": f"admin@{tenant_data['subdomain']}.test"},
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

    return token, override_get_db, override_get_unscoped_db


@pytest_asyncio.fixture
async def comm_tenant():
    """Seed tenant A for communication settings tests."""
    data = await _seed_tenant_school_user("commsett-a")
    yield data
    await _cleanup_tenant(data["tenant_id"])


@pytest_asyncio.fixture
async def comm_tenant_b():
    """Seed tenant B for isolation tests."""
    data = await _seed_tenant_school_user("commsett-b")
    yield data
    await _cleanup_tenant(data["tenant_id"])


@pytest_asyncio.fixture
async def comm_client(comm_tenant):
    """Authenticated client for tenant A."""
    token, override_db, override_unscoped = _make_client_context(comm_tenant)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": comm_tenant["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def comm_client_b(comm_tenant_b):
    """Authenticated client for tenant B."""
    token, override_db, override_unscoped = _make_client_context(comm_tenant_b)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": comm_tenant_b["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


# ===========================
# Tests
# ===========================


@pytest.mark.asyncio
async def test_get_communication_settings_returns_defaults(comm_client):
    """GET /communication-settings should return defaults when no settings have been saved."""
    resp = await comm_client.get("/api/v1/communication-settings")
    assert resp.status_code == 200

    data = resp.json()
    assert data["sms"]["sender_id"] == "SIMSPLUS"
    assert data["email"]["from_email"] is None
    assert data["notifications"]["report_card_notifications"] is True


@pytest.mark.asyncio
async def test_put_sms_settings(comm_client):
    """PUT /communication-settings should save SMS settings."""
    resp = await comm_client.put(
        "/api/v1/communication-settings",
        json={
            "sms": {
                "sender_id": "MYSCHOOL",
                "attendance_alerts_enabled": False,
                "fee_reminders_enabled": True,
            },
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["sms"]["sender_id"] == "MYSCHOOL"
    assert data["sms"]["attendance_alerts_enabled"] is False


@pytest.mark.asyncio
async def test_put_email_settings(comm_client):
    """PUT /communication-settings should save email settings."""
    resp = await comm_client.put(
        "/api/v1/communication-settings",
        json={
            "email": {
                "from_email": "info@myschool.edu",
                "from_name": "My School",
                "reply_to": "admin@myschool.edu",
            },
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["email"]["from_email"] == "info@myschool.edu"
    assert data["email"]["from_name"] == "My School"


@pytest.mark.asyncio
async def test_partial_update_merges_correctly(comm_client):
    """PUT with only one section should not overwrite other sections."""
    # First, save SMS settings
    await comm_client.put(
        "/api/v1/communication-settings",
        json={"sms": {"sender_id": "FIRST"}},
    )

    # Then update only email settings
    resp = await comm_client.put(
        "/api/v1/communication-settings",
        json={"email": {"from_name": "Updated School"}},
    )
    assert resp.status_code == 200

    data = resp.json()
    # SMS should still have the previous value
    assert data["sms"]["sender_id"] == "FIRST"
    # Email should have the new value
    assert data["email"]["from_name"] == "Updated School"


@pytest.mark.asyncio
async def test_get_returns_saved_settings(comm_client):
    """After PUT, GET should return the saved settings."""
    await comm_client.put(
        "/api/v1/communication-settings",
        json={"sms": {"sender_id": "PERSIST"}},
    )

    resp = await comm_client.get("/api/v1/communication-settings")
    assert resp.status_code == 200
    assert resp.json()["sms"]["sender_id"] == "PERSIST"


@pytest.mark.asyncio
async def test_settings_tenant_isolation(comm_client, comm_client_b):
    """Tenant A's settings must not leak to Tenant B."""
    # Save unique settings for Tenant A
    await comm_client.put(
        "/api/v1/communication-settings",
        json={"sms": {"sender_id": "TENANT_A"}},
    )

    # Tenant B should see default settings, not Tenant A's
    resp = await comm_client_b.get("/api/v1/communication-settings")
    assert resp.status_code == 200
    assert resp.json()["sms"]["sender_id"] == "SIMSPLUS"  # default, not TENANT_A


@pytest.mark.asyncio
async def test_get_requires_school_read_permission(comm_tenant):
    """GET /communication-settings should reject users without school.read permission."""
    # Create token with no permissions
    token = create_access_token(
        subject=str(comm_tenant["user_id"]),
        tenant_id=str(comm_tenant["tenant_id"]),
        school_id=str(comm_tenant["school_id"]),
        role="teacher",
        permissions=[],
        extra_claims={"email": "noperm@test.com"},
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

    async def override_unscoped():
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
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": comm_tenant["subdomain"],
            },
        ) as client:
            resp = await client.get("/api/v1/communication-settings")
            assert resp.status_code == 403

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
async def test_put_requires_school_update_permission(comm_tenant):
    """PUT /communication-settings should reject users without school.update permission."""
    # Token with only school.read but not school.update
    token = create_access_token(
        subject=str(comm_tenant["user_id"]),
        tenant_id=str(comm_tenant["tenant_id"]),
        school_id=str(comm_tenant["school_id"]),
        role="teacher",
        permissions=["school.read"],
        extra_claims={"email": "readonly@test.com"},
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

    async def override_unscoped():
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
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": comm_tenant["subdomain"],
            },
        ) as client:
            resp = await client.put(
                "/api/v1/communication-settings",
                json={"sms": {"sender_id": "HACKER"}},
            )
            assert resp.status_code == 403

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)

"""
Tests for SMS messaging endpoints.

Verifies send, bulk send, history, stats, phone validation, tenant isolation,
and permission enforcement. Arkesel HTTP calls are always mocked.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
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


@pytest_asyncio.fixture
async def sms_tenant():
    """Seed a tenant + school + admin user for SMS tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"sms-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"SMS {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'SM', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "name": "SMS Test School", "slug": subdomain},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'SMS', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tid": str(tenant_id), "email": f"admin@{subdomain}.test", "pw": pw_hash},
        )
        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "subdomain": subdomain,
    }

    # Cleanup
    async with admin_session_maker() as session:
        for table in ["sms_log", "student_guardians", "guardians", "students",
                       "class_sections", "classes", "users", "schools"]:
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
async def sms_tenant_b():
    """Seed a second tenant for isolation tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"smsb-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"SMSB {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'SB', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "name": "SMS B School", "slug": subdomain},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'SMSB', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tid": str(tenant_id), "email": f"admin@{subdomain}.test", "pw": pw_hash},
        )
        await session.commit()

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "subdomain": subdomain,
    }

    async with admin_session_maker() as session:
        for table in ["sms_log", "users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


def _build_client_overrides():
    """Return get_db and get_unscoped_db overrides."""

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

    return override_get_db, override_get_unscoped_db


@pytest_asyncio.fixture
async def sms_client(sms_tenant):
    """Authenticated client for SMS tests."""
    t = sms_tenant
    token = create_access_token(
        subject=str(t["user_id"]),
        tenant_id=str(t["tenant_id"]),
        school_id=str(t["school_id"]),
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": f"admin@{t['subdomain']}.test"},
    )
    override_db, override_unscoped = _build_client_overrides()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

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


@pytest_asyncio.fixture
async def sms_client_b(sms_tenant_b):
    """Authenticated client for tenant B."""
    t = sms_tenant_b
    token = create_access_token(
        subject=str(t["user_id"]),
        tenant_id=str(t["tenant_id"]),
        school_id=str(t["school_id"]),
        role="school_admin",
        permissions=["*"],
        extra_claims={"email": f"admin@{t['subdomain']}.test"},
    )
    override_db, override_unscoped = _build_client_overrides()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

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
# Send Tests
# ===========================


@pytest.mark.asyncio
async def test_send_sms_to_specific_phones(sms_client):
    """POST /messaging/sms/send should accept phone numbers and create log entries."""
    resp = await sms_client.post(
        "/api/v1/messaging/sms/send",
        json={
            "recipient_phones": ["+233241234567", "0201234567"],
            "message": "Test SMS message",
        },
    )
    assert resp.status_code == 201

    data = resp.json()
    assert len(data) == 2
    assert data[0]["recipient_phone"] == "+233241234567"
    assert data[1]["recipient_phone"] == "0201234567"
    # Status should be pending (Arkesel not configured in tests)
    assert data[0]["status"] in ("pending", "sent")


@pytest.mark.asyncio
async def test_send_sms_validates_phone_format(sms_client):
    """POST /messaging/sms/send should reject invalid phone formats."""
    resp = await sms_client.post(
        "/api/v1/messaging/sms/send",
        json={
            "recipient_phones": ["not-a-phone!"],
            "message": "Test message",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_sms_creates_log_entries(sms_client):
    """Sent SMS should appear in history."""
    # Send a message
    await sms_client.post(
        "/api/v1/messaging/sms/send",
        json={"recipient_phones": ["+233241111111"], "message": "Log check"},
    )

    # Check history
    resp = await sms_client.get("/api/v1/messaging/sms/history")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] >= 1
    messages = [item["message"] for item in data["items"]]
    assert "Log check" in messages


@pytest.mark.asyncio
async def test_bulk_sms_resolves_all_parents(sms_client, sms_tenant):
    """POST /messaging/sms/bulk with all_parents should attempt resolution."""
    # Since there are no students/guardians seeded, we expect a 422 for no recipients
    resp = await sms_client.post(
        "/api/v1/messaging/sms/bulk",
        json={
            "audience": "all_parents",
            "message": "Bulk test to all parents",
        },
    )
    # No guardians with phones => 422 "No recipients with phone numbers found"
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_sms_class_parents_requires_class_id(sms_client):
    """POST /messaging/sms/bulk with class_parents but no class_id should fail."""
    resp = await sms_client.post(
        "/api/v1/messaging/sms/bulk",
        json={
            "audience": "class_parents",
            "message": "Test class parents message",
        },
    )
    assert resp.status_code == 422
    assert "class_id" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_bulk_sms_rejects_specific_audience(sms_client):
    """POST /messaging/sms/bulk should reject the 'specific' audience type."""
    resp = await sms_client.post(
        "/api/v1/messaging/sms/bulk",
        json={
            "audience": "specific",
            "message": "Test specific message",
        },
    )
    assert resp.status_code == 422
    assert "send" in resp.json()["detail"].lower()


# ===========================
# History + Stats Tests
# ===========================


@pytest.mark.asyncio
async def test_sms_history_returns_paginated(sms_client):
    """GET /messaging/sms/history should return paginated results."""
    resp = await sms_client.get("/api/v1/messaging/sms/history?page=1&page_size=5")
    assert resp.status_code == 200

    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "total_pages" in data


@pytest.mark.asyncio
async def test_sms_history_filters_by_status(sms_client):
    """GET /messaging/sms/history?status=sent should filter correctly."""
    # First send a message so there is data
    await sms_client.post(
        "/api/v1/messaging/sms/send",
        json={"recipient_phones": ["+233249999999"], "message": "Filter test"},
    )

    # Filter by a status that shouldn't match (delivered)
    resp = await sms_client.get("/api/v1/messaging/sms/history?status=delivered")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_sms_stats_returns_counts(sms_client):
    """GET /messaging/sms/stats should return aggregate counts."""
    resp = await sms_client.get("/api/v1/messaging/sms/stats")
    assert resp.status_code == 200

    data = resp.json()
    assert "total_sent" in data
    assert "total_failed" in data
    assert "total_pending" in data
    assert "credits_used" in data


# ===========================
# Tenant Isolation Tests
# ===========================


@pytest.mark.asyncio
async def test_sms_log_tenant_isolation(sms_client, sms_client_b):
    """Tenant A's SMS logs must not be visible to Tenant B."""
    # Send SMS as Tenant A
    await sms_client.post(
        "/api/v1/messaging/sms/send",
        json={"recipient_phones": ["+233241000001"], "message": "Tenant A secret"},
    )

    # Check Tenant B's history -- should NOT contain Tenant A's message
    resp = await sms_client_b.get("/api/v1/messaging/sms/history")
    assert resp.status_code == 200

    messages = [item["message"] for item in resp.json()["items"]]
    assert "Tenant A secret" not in messages


# ===========================
# Permission Tests
# ===========================


@pytest.mark.asyncio
async def test_send_sms_requires_communications_send_permission(sms_tenant):
    """POST /messaging/sms/send should reject users without communications.send."""
    t = sms_tenant
    token = create_access_token(
        subject=str(t["user_id"]),
        tenant_id=str(t["tenant_id"]),
        school_id=str(t["school_id"]),
        role="teacher",
        permissions=["communications.read"],  # has read but not send
        extra_claims={"email": f"admin@{t['subdomain']}.test"},
    )
    override_db, override_unscoped = _build_client_overrides()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

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
            resp = await client.post(
                "/api/v1/messaging/sms/send",
                json={"recipient_phones": ["+233240000000"], "message": "No perm"},
            )
            assert resp.status_code == 403

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
async def test_arkesel_not_called_when_not_configured(sms_client):
    """When Arkesel API key is not set, send_sms should still log but not call Arkesel."""
    with patch("app.services.sms._sms_client") as mock_arkesel:
        mock_arkesel.is_configured = False

        resp = await sms_client.post(
            "/api/v1/messaging/sms/send",
            json={"recipient_phones": ["+233241000099"], "message": "No Arkesel"},
        )
        assert resp.status_code == 201

        # send_sms should NOT have been called on the mock
        mock_arkesel.send_sms.assert_not_called()

"""
Tests for email messaging endpoints.

Verifies send, bulk send, history, stats, tenant isolation,
and permission enforcement. SMTP delivery is always mocked.
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


@pytest_asyncio.fixture
async def email_tenant():
    """Seed a tenant + school + admin user for email messaging tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"eml-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"Email {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'EM', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "name": "Email Test School", "slug": subdomain},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'Email', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
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
        for table in ["email_log", "users", "schools"]:
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
async def email_tenant_b():
    """Second tenant for isolation tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"emlb-{uuid4().hex[:8]}"
    pw_hash = hash_password(E2E_PASSWORD)

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"EmailB {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'EB', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "name": "Email B School", "slug": subdomain},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'EmailB', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
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
        for table in ["email_log", "users", "schools"]:
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
    """Shared dep overrides for get_db and get_unscoped_db."""

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


def _make_auth_client(tenant_data, permissions=None):
    """Create token + headers for a tenant."""
    t = tenant_data
    perms = permissions if permissions is not None else ["*"]
    token = create_access_token(
        subject=str(t["user_id"]),
        tenant_id=str(t["tenant_id"]),
        school_id=str(t["school_id"]),
        role="school_admin",
        permissions=perms,
        extra_claims={"email": f"admin@{t['subdomain']}.test"},
    )
    return token, t["subdomain"]


@pytest_asyncio.fixture
async def email_client(email_tenant):
    """Authenticated client for Tenant A email tests."""
    token, subdomain = _make_auth_client(email_tenant)
    override_db, override_unscoped = _build_client_overrides()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker), \
         patch("app.services.messaging.email_compose.email_service") as mock_email_svc:
        mock_email_svc.send_email = AsyncMock(return_value=True)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def email_client_b(email_tenant_b):
    """Authenticated client for Tenant B."""
    token, subdomain = _make_auth_client(email_tenant_b)
    override_db, override_unscoped = _build_client_overrides()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker), \
         patch("app.services.messaging.email_compose.email_service") as mock_email_svc:
        mock_email_svc.send_email = AsyncMock(return_value=True)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


# ===========================
# Send Tests
# ===========================


@pytest.mark.asyncio
async def test_send_email_creates_log_entries(email_client):
    """POST /messaging/email/send should create EmailLog entries for each recipient."""
    resp = await email_client.post(
        "/api/v1/messaging/email/send",
        json={
            "recipient_emails": ["parent1@test.com", "parent2@test.com"],
            "subject": "Term Report Available",
            "body": "<p>Your child's term report is ready.</p>",
        },
    )
    assert resp.status_code == 201

    data = resp.json()
    assert len(data) == 2
    assert data[0]["recipient_email"] == "parent1@test.com"
    assert data[1]["recipient_email"] == "parent2@test.com"
    assert data[0]["subject"] == "Term Report Available"


@pytest.mark.asyncio
async def test_send_email_calls_email_service(email_tenant):
    """POST /messaging/email/send should call email_service.send_email for delivery."""
    token, subdomain = _make_auth_client(email_tenant)
    override_db, override_unscoped = _build_client_overrides()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker), \
         patch("app.services.messaging.email_compose.email_service") as mock_svc:
        mock_svc.send_email = AsyncMock(return_value=True)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        ) as client:
            resp = await client.post(
                "/api/v1/messaging/email/send",
                json={
                    "recipient_emails": ["test@test.com"],
                    "subject": "Hello",
                    "body": "Body text",
                },
            )
            assert resp.status_code == 201

            # email_service.send_email should have been called once
            mock_svc.send_email.assert_called_once()

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
async def test_bulk_email_resolves_all_staff(email_client):
    """POST /messaging/email/bulk with all_staff should attempt resolution."""
    # No staff seeded => expect 422 "No recipients with email addresses"
    resp = await email_client.post(
        "/api/v1/messaging/email/bulk",
        json={
            "audience": "all_staff",
            "subject": "Staff meeting",
            "body": "Please attend the meeting at 3pm.",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_email_resolves_all_parents(email_client):
    """POST /messaging/email/bulk with all_parents should attempt resolution."""
    # No guardians seeded => expect 422
    resp = await email_client.post(
        "/api/v1/messaging/email/bulk",
        json={
            "audience": "all_parents",
            "subject": "PTA meeting",
            "body": "You are invited to the PTA meeting.",
        },
    )
    assert resp.status_code == 422


# ===========================
# History + Stats Tests
# ===========================


@pytest.mark.asyncio
async def test_email_history_returns_paginated(email_client):
    """GET /messaging/email/history should return paginated results."""
    resp = await email_client.get("/api/v1/messaging/email/history?page=1&page_size=10")
    assert resp.status_code == 200

    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "total_pages" in data


@pytest.mark.asyncio
async def test_email_history_filters_by_status(email_client):
    """GET /messaging/email/history?status=bounced should filter correctly."""
    # First send an email so there is data
    await email_client.post(
        "/api/v1/messaging/email/send",
        json={
            "recipient_emails": ["histfilter@test.com"],
            "subject": "Filter",
            "body": "Body",
        },
    )

    # Filter by bounced (which shouldn't match)
    resp = await email_client.get("/api/v1/messaging/email/history?status=bounced")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_email_stats_returns_counts(email_client):
    """GET /messaging/email/stats should return aggregate counts."""
    resp = await email_client.get("/api/v1/messaging/email/stats")
    assert resp.status_code == 200

    data = resp.json()
    assert "total_sent" in data
    assert "total_failed" in data
    assert "total_pending" in data
    assert "total_delivered" in data
    assert "total_bounced" in data


# ===========================
# Tenant Isolation
# ===========================


@pytest.mark.asyncio
async def test_email_log_tenant_isolation(email_client, email_client_b):
    """Tenant A's email logs must not be visible to Tenant B."""
    await email_client.post(
        "/api/v1/messaging/email/send",
        json={
            "recipient_emails": ["isolated@test.com"],
            "subject": "Tenant A confidential",
            "body": "Secret body",
        },
    )

    resp = await email_client_b.get("/api/v1/messaging/email/history")
    assert resp.status_code == 200

    subjects = [item["subject"] for item in resp.json()["items"]]
    assert "Tenant A confidential" not in subjects


# ===========================
# Permission Tests
# ===========================


@pytest.mark.asyncio
async def test_send_requires_communications_send(email_tenant):
    """POST /messaging/email/send should reject users without communications.send."""
    token, subdomain = _make_auth_client(email_tenant, permissions=["communications.read"])
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
                "X-Subdomain": subdomain,
            },
        ) as client:
            resp = await client.post(
                "/api/v1/messaging/email/send",
                json={
                    "recipient_emails": ["noperm@test.com"],
                    "subject": "No permission",
                    "body": "Should fail",
                },
            )
            assert resp.status_code == 403

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
async def test_history_requires_communications_read(email_tenant):
    """GET /messaging/email/history should reject users without communications.read."""
    token, subdomain = _make_auth_client(email_tenant, permissions=[])
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
                "X-Subdomain": subdomain,
            },
        ) as client:
            resp = await client.get("/api/v1/messaging/email/history")
            assert resp.status_code == 403

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)

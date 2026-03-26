"""
Tests for phone verification endpoints.

Phase 1B: Tests the /auth/send-phone-otp and /auth/verify-phone endpoints.
Uses E2E-style authenticated client to test the full HTTP flow.
"""

from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import Request

from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_engine, app_session_maker


_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

PASSWORD = "TestPass123!"


@pytest_asyncio.fixture
async def phone_tenant():
    """Create tenant + school + user WITH phone number."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"phone-{uuid4().hex[:8]}"
    pw_hash = hash_password(PASSWORD)
    phone = "+233241234567"

    async with admin_session_maker() as session:
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
               "name": f"Phone Test {subdomain}"})

        await session.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'PT', 'basic')
        """), {"id": str(school_id), "tid": str(tenant_id),
               "name": f"Phone Test {subdomain}", "slug": subdomain})

        await session.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                phone, role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Test', 'User', :phone, 'teacher', 'active', true, false, 0, 'Africa/Accra')
        """), {"id": str(user_id), "tid": str(tenant_id),
               "email": f"user@{subdomain}.test", "pw": pw_hash, "phone": phone})

        await session.commit()

    yield {
        "tenant_id": tenant_id, "school_id": school_id, "user_id": user_id,
        "subdomain": subdomain, "email": f"user@{subdomain}.test", "phone": phone,
    }

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


@pytest_asyncio.fixture
async def phone_auth_client(phone_tenant):
    """Authenticated client with real Redis mocked to fakeredis."""
    td = phone_tenant
    token = create_access_token(
        subject=str(td["user_id"]), tenant_id=str(td["tenant_id"]),
        school_id=str(td["school_id"]), role="teacher",
        permissions=["*"],
    )

    fake_redis = FakeRedis(decode_responses=True)

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                tid = getattr(getattr(request, "state", None), "tenant_id", None)
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
         patch("app.main.async_session_maker", _test_middleware_session_maker), \
         patch("app.services.otp._sms_client.send_sms", new_callable=AsyncMock,
               return_value={"success": True, "message_id": "test"}):
        # Inject fakeredis into app.state
        app.state.redis = fake_redis
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": td["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.clear()
    await fake_redis.aclose()


@pytest_asyncio.fixture
async def phone_unauth_client():
    """Unauthenticated client."""
    with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
        ) as client:
            yield client


class TestSendPhoneOTP:
    @pytest.mark.asyncio
    async def test_send_otp_success(self, phone_auth_client):
        """POST /auth/send-phone-otp should succeed."""
        resp = await phone_auth_client.post("/api/v1/auth/send-phone-otp")
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.asyncio
    async def test_send_otp_requires_auth(self, phone_unauth_client):
        """Should return 401/403 without JWT."""
        resp = await phone_unauth_client.post("/api/v1/auth/send-phone-otp")
        # Without auth, we get 401 or 400 (no tenant context)
        assert resp.status_code in (400, 401, 403)

    @pytest.mark.asyncio
    async def test_send_otp_rate_limited(self, phone_auth_client):
        """Second request within 60 seconds should return 429."""
        resp1 = await phone_auth_client.post("/api/v1/auth/send-phone-otp")
        assert resp1.status_code == 200

        resp2 = await phone_auth_client.post("/api/v1/auth/send-phone-otp")
        assert resp2.status_code == 429


class TestVerifyPhone:
    @pytest.mark.asyncio
    async def test_verify_invalid_code(self, phone_auth_client):
        """Invalid code should return 400."""
        # Send OTP first
        await phone_auth_client.post("/api/v1/auth/send-phone-otp")
        # Try with wrong code
        resp = await phone_auth_client.post(
            "/api/v1/auth/verify-phone", json={"code": "000000"}
        )
        assert resp.status_code == 400

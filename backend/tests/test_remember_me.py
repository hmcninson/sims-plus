"""
Tests for Remember Me authentication feature.

Verifies that login with remember_me=true extends refresh token lifetime
to 30 days, and that token rotation preserves the remember_me state.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import Request

from app.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_session_maker


_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

PASSWORD = "TestPass123!"


@pytest_asyncio.fixture
async def remember_tenant():
    """Create tenant + school + user for remember_me tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"rem-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
               "name": f"Remember Test {subdomain}"})

        await session.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'RM', 'basic')
        """), {"id": str(school_id), "tid": str(tenant_id),
               "name": f"Remember Test {subdomain}", "slug": subdomain})

        await session.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Test', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra')
        """), {"id": str(user_id), "tid": str(tenant_id),
               "email": f"user@{subdomain}.example.com", "pw": hash_password(PASSWORD)})

        await session.commit()

    yield {
        "tenant_id": tenant_id, "school_id": school_id, "user_id": user_id,
        "subdomain": subdomain, "email": f"user@{subdomain}.example.com",
    }

    async with admin_session_maker() as session:
        for table in ["user_sessions", "users", "schools"]:
            try:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": str(tenant_id)},
                )
            except Exception:
                await session.rollback()
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


def _make_login_client_overrides():
    """Return dependency overrides for login tests."""
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

    return override_get_db, override_get_unscoped_db


class TestRememberMe:
    @pytest.mark.asyncio
    async def test_login_remember_me_true_extends_refresh(self, remember_tenant):
        """Login with remember_me=true should return 30-day refresh token."""
        td = remember_tenant
        override_get_db, override_get_unscoped_db = _make_login_client_overrides()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD, "remember_me": True,
                })
                assert resp.status_code == 200, f"Login failed: {resp.text}"
                data = resp.json()

                # 30 days in seconds
                expected_seconds = settings.REMEMBER_ME_REFRESH_TOKEN_DAYS * 86400
                assert data["refresh_token_expires_in"] == expected_seconds

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_remember_me_false_uses_default(self, remember_tenant):
        """Login with remember_me=false should return 7-day refresh token."""
        td = remember_tenant
        override_get_db, override_get_unscoped_db = _make_login_client_overrides()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD, "remember_me": False,
                })
                assert resp.status_code == 200, f"Login failed: {resp.text}"
                data = resp.json()

                expected_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
                assert data["refresh_token_expires_in"] == expected_seconds

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_without_remember_me_defaults_to_short(self, remember_tenant):
        """Login without remember_me field should default to 7-day refresh token."""
        td = remember_tenant
        override_get_db, override_get_unscoped_db = _make_login_client_overrides()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD,
                })
                assert resp.status_code == 200, f"Login failed: {resp.text}"
                data = resp.json()

                expected_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
                assert data["refresh_token_expires_in"] == expected_seconds

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_access_token_expiry_unchanged(self, remember_tenant):
        """Access token expiry should be the same regardless of remember_me."""
        td = remember_tenant
        override_get_db, override_get_unscoped_db = _make_login_client_overrides()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD, "remember_me": True,
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_refresh_preserves_remember_me_state(self, remember_tenant):
        """Token refresh should preserve remember_me=true claim in the new refresh token."""
        td = remember_tenant
        override_get_db, override_get_unscoped_db = _make_login_client_overrides()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                # Login with remember_me=True
                login_resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD, "remember_me": True,
                })
                assert login_resp.status_code == 200
                login_data = login_resp.json()
                original_refresh = login_data["refresh_token"]

                # Refresh the token
                refresh_resp = await client.post("/api/v1/auth/refresh", json={
                    "refresh_token": original_refresh,
                })
                assert refresh_resp.status_code == 200
                refresh_data = refresh_resp.json()

                # The new refresh token should also have 30-day expiry
                expected_seconds = settings.REMEMBER_ME_REFRESH_TOKEN_DAYS * 86400
                assert refresh_data["refresh_token_expires_in"] == expected_seconds

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_response_includes_refresh_expires_in(self, remember_tenant):
        """Login response must include the refresh_token_expires_in field."""
        td = remember_tenant
        override_get_db, override_get_unscoped_db = _make_login_client_overrides()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD,
                })
                assert resp.status_code == 200
                data = resp.json()
                assert "refresh_token_expires_in" in data
                assert isinstance(data["refresh_token_expires_in"], int)
                assert data["refresh_token_expires_in"] > 0

        app.dependency_overrides.clear()

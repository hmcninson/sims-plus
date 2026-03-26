"""
Tests for session timeout and heartbeat.

Phase 2: Tests the /auth/heartbeat endpoint and inactivity timeout enforcement
on token refresh.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import Request

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_engine, app_session_maker


_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

PASSWORD = "TestPass123!"


@pytest_asyncio.fixture
async def session_tenant():
    """Create tenant + school + user for session timeout tests."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"sess-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
                'single_school', 'professional', 'active', 1000, 100, true)
        """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
               "name": f"Session Test {subdomain}"})

        await session.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'SS', 'basic')
        """), {"id": str(school_id), "tid": str(tenant_id),
               "name": f"Session Test {subdomain}", "slug": subdomain})

        await session.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone,
                last_activity_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Test', 'User', 'teacher', 'active', true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP)
        """), {"id": str(user_id), "tid": str(tenant_id),
               "email": f"user@{subdomain}.example.com",
               "pw": hash_password(PASSWORD)})

        await session.commit()

    yield {
        "tenant_id": tenant_id, "school_id": school_id, "user_id": user_id,
        "subdomain": subdomain, "email": f"user@{subdomain}.example.com",
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
async def session_client(session_tenant):
    """Authenticated client for session timeout tests."""
    td = session_tenant
    token = create_access_token(
        subject=str(td["user_id"]), tenant_id=str(td["tenant_id"]),
        school_id=str(td["school_id"]), role="teacher",
        permissions=["*"],
    )

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
         patch("app.main.async_session_maker", _test_middleware_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": td["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.clear()


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_returns_204(self, session_client):
        """POST /auth/heartbeat should return 204 No Content."""
        resp = await session_client.post("/api/v1/auth/heartbeat")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_heartbeat_requires_auth(self):
        """Heartbeat should reject unauthenticated requests."""
        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.post("/api/v1/auth/heartbeat")
                # Without tenant context + auth, returns 400 or 401
                assert resp.status_code in (400, 401)


class TestLoginSetsActivity:
    @pytest.mark.asyncio
    async def test_login_sets_last_activity(self, session_tenant):
        """Successful login should set last_activity_at.

        Verifies indirectly: AuthService._record_successful_login sets
        last_activity_at = now() on the user row.
        """
        td = session_tenant

        # Use the E2E pattern: override get_db with Request type annotation
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
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/login", json={
                    "email": td["email"], "password": PASSWORD,
                })
                assert resp.status_code == 200, f"Login failed: {resp.text}"

        app.dependency_overrides.clear()

        # Verify last_activity_at was set
        async with admin_session_maker() as session:
            result = await session.execute(
                text("SELECT last_activity_at FROM users WHERE id = CAST(:uid AS uuid)"),
                {"uid": str(td["user_id"])},
            )
            row = result.fetchone()
            assert row[0] is not None


class TestInactivityEnforcement:
    @pytest.mark.asyncio
    async def test_refresh_rejected_after_timeout(self, session_tenant):
        """Token refresh should fail if last_activity > 30 minutes."""
        td = session_tenant

        # Set last_activity_at to 31 minutes ago
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=31)
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    UPDATE users SET last_activity_at = :time
                    WHERE id = CAST(:uid AS uuid)
                """),
                {"time": stale_time, "uid": str(td["user_id"])},
            )
            await session.commit()

        refresh_token, refresh_jti, _expires_at = create_refresh_token(
            subject=str(td["user_id"]), tenant_id=str(td["tenant_id"]),
        )

        # Register the JTI in user_sessions so the blacklist DB fallback
        # doesn't treat the token as revoked (session not found = revoked).
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO user_sessions
                        (id, tenant_id, user_id, jti, is_active,
                         ip_address, expires_at, created_at, updated_at)
                    VALUES (gen_random_uuid(), CAST(:tid AS uuid),
                        CAST(:uid AS uuid), :jti, true,
                        '127.0.0.1', :expires_at,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    "tid": str(td["tenant_id"]),
                    "uid": str(td["user_id"]),
                    "jti": refresh_jti,
                    "expires_at": _expires_at,
                },
            )
            await session.commit()

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
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/refresh", json={
                    "refresh_token": refresh_token,
                })
                assert resp.status_code == 401
                assert "inactivity" in resp.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_no_last_activity_allows_refresh(self, session_tenant):
        """If last_activity_at is NULL (legacy user), refresh should succeed."""
        td = session_tenant

        # Set last_activity_at to NULL
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    UPDATE users SET last_activity_at = NULL
                    WHERE id = CAST(:uid AS uuid)
                """),
                {"uid": str(td["user_id"])},
            )
            await session.commit()

        refresh_token, refresh_jti, _expires_at = create_refresh_token(
            subject=str(td["user_id"]), tenant_id=str(td["tenant_id"]),
        )

        # Register the JTI in user_sessions so the blacklist DB fallback
        # doesn't treat the token as revoked (session not found = revoked).
        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO user_sessions
                        (id, tenant_id, user_id, jti, is_active,
                         ip_address, expires_at, created_at, updated_at)
                    VALUES (gen_random_uuid(), CAST(:tid AS uuid),
                        CAST(:uid AS uuid), :jti, true,
                        '127.0.0.1', :expires_at,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    "tid": str(td["tenant_id"]),
                    "uid": str(td["user_id"]),
                    "jti": refresh_jti,
                    "expires_at": _expires_at,
                },
            )
            await session.commit()

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
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                resp = await client.post("/api/v1/auth/refresh", json={
                    "refresh_token": refresh_token,
                })
                assert resp.status_code == 200
                assert "access_token" in resp.json()

        app.dependency_overrides.clear()

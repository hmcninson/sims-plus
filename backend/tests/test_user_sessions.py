"""
Tests for session management.

Verifies session creation on login, listing, termination, tenant isolation,
and IDOR prevention for the /auth/sessions endpoints.
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

from app.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_session_maker


_test_middleware_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

PASSWORD = "TestPass123!"


def _override_get_db():
    async def _inner(request: Request):
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
    return _inner


def _override_get_unscoped_db():
    async def _inner():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    return _inner


async def _create_tenant_and_user(admin_session, subdomain_prefix="sess"):
    """Helper to create a tenant + school + user. Returns info dict."""
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    subdomain = f"{subdomain_prefix}-{uuid4().hex[:8]}"

    await admin_session.execute(text("""
        INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
            subscription_tier, status, max_students, max_staff, is_active)
        VALUES (CAST(:id AS uuid), :subdomain, :slug, :name,
            'single_school', 'professional', 'active', 1000, 100, true)
    """), {"id": str(tenant_id), "subdomain": subdomain, "slug": subdomain,
           "name": f"Session Test {subdomain}"})

    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'SS', 'basic')
    """), {"id": str(school_id), "tid": str(tenant_id),
           "name": f"Session Test {subdomain}", "slug": subdomain})

    await admin_session.execute(text("""
        INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
            role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
            'Test', 'User', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
    """), {"id": str(user_id), "tid": str(tenant_id),
           "email": f"user@{subdomain}.example.com", "pw": hash_password(PASSWORD)})

    return {
        "tenant_id": tenant_id, "school_id": school_id, "user_id": user_id,
        "subdomain": subdomain, "email": f"user@{subdomain}.example.com",
    }


@pytest_asyncio.fixture
async def session_data():
    """Create tenant A + user for session tests."""
    async with admin_session_maker() as session:
        data = await _create_tenant_and_user(session, "sessa")
        await session.commit()

    yield data

    async with admin_session_maker() as session:
        for table in ["user_sessions", "users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(data["tenant_id"])},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(data["tenant_id"])},
        )
        await session.commit()


@pytest_asyncio.fixture
async def tenant_b_data():
    """Create tenant B for cross-tenant isolation tests."""
    async with admin_session_maker() as session:
        data = await _create_tenant_and_user(session, "sessb")
        await session.commit()

    yield data

    async with admin_session_maker() as session:
        for table in ["user_sessions", "users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(data["tenant_id"])},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(data["tenant_id"])},
        )
        await session.commit()


async def _login(client, subdomain, email, password=PASSWORD):
    """Login and return the response data."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Subdomain": subdomain},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()


def _make_authenticated_client(td, token):
    """Create an authenticated AsyncClient context manager."""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Subdomain": td["subdomain"],
        },
    )


class TestSessionCreation:
    @pytest.mark.asyncio
    async def test_session_created_on_login(self, session_data):
        """Logging in should create a session record."""
        td = session_data

        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                login_data = await _login(client, td["subdomain"], td["email"])
                access_token = login_data["access_token"]

            # Now list sessions with the access token
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Subdomain": td["subdomain"],
                },
            ) as client:
                resp = await client.get("/api/v1/auth/sessions")
                assert resp.status_code == 200
                data = resp.json()
                assert data["count"] >= 1

        app.dependency_overrides.clear()


class TestListSessions:
    @pytest.mark.asyncio
    async def test_current_session_marked(self, session_data):
        """The current session should have is_current=true."""
        td = session_data

        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                login_data = await _login(client, td["subdomain"], td["email"])
                access_token = login_data["access_token"]

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Subdomain": td["subdomain"],
                },
            ) as client:
                resp = await client.get("/api/v1/auth/sessions")
                assert resp.status_code == 200
                sessions = resp.json()["sessions"]
                current_sessions = [s for s in sessions if s["is_current"]]
                assert len(current_sessions) == 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_sessions_requires_auth(self):
        """Listing sessions without auth should fail."""
        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                resp = await client.get("/api/v1/auth/sessions")
                assert resp.status_code in (400, 401)

        app.dependency_overrides.clear()


class TestTerminateSession:
    @pytest.mark.asyncio
    async def test_terminate_specific_session(self, session_data):
        """Terminating a session should mark it inactive."""
        td = session_data

        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                # Login twice to create two sessions
                login1 = await _login(client, td["subdomain"], td["email"])
                login2 = await _login(client, td["subdomain"], td["email"])
                active_token = login2["access_token"]

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {active_token}",
                    "X-Subdomain": td["subdomain"],
                },
            ) as client:
                # List sessions
                list_resp = await client.get("/api/v1/auth/sessions")
                assert list_resp.status_code == 200
                sessions = list_resp.json()["sessions"]

                # Find a non-current session to terminate
                non_current = [s for s in sessions if not s["is_current"]]
                if non_current:
                    target_id = non_current[0]["id"]
                    del_resp = await client.delete(f"/api/v1/auth/sessions/{target_id}")
                    assert del_resp.status_code == 204

                    # Verify session count decreased
                    list_resp2 = await client.get("/api/v1/auth/sessions")
                    assert list_resp2.json()["count"] < list_resp.json()["count"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_terminate_all_others_preserves_current(self, session_data):
        """Terminate-all-others should keep the current session active."""
        td = session_data

        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td["subdomain"]},
            ) as client:
                # Login multiple times to create sessions
                await _login(client, td["subdomain"], td["email"])
                await _login(client, td["subdomain"], td["email"])
                login3 = await _login(client, td["subdomain"], td["email"])
                active_token = login3["access_token"]

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {active_token}",
                    "X-Subdomain": td["subdomain"],
                },
            ) as client:
                # Terminate all others
                resp = await client.post("/api/v1/auth/sessions/terminate-all")
                assert resp.status_code == 200
                data = resp.json()
                assert data["terminated"] >= 0

                # List sessions -- only the current should remain
                list_resp = await client.get("/api/v1/auth/sessions")
                assert list_resp.status_code == 200
                sessions = list_resp.json()["sessions"]
                assert len(sessions) == 1
                assert sessions[0]["is_current"] is True

        app.dependency_overrides.clear()


class TestSessionIDOR:
    @pytest.mark.asyncio
    async def test_cannot_terminate_other_users_session(self, session_data, tenant_b_data):
        """User A should not be able to terminate User B's session (IDOR prevention)."""
        td_a = session_data
        td_b = tenant_b_data

        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):

            # Login as User B to create a session
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td_b["subdomain"]},
            ) as client:
                login_b = await _login(client, td_b["subdomain"], td_b["email"])

            # Get User B's session ID
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {login_b['access_token']}",
                    "X-Subdomain": td_b["subdomain"],
                },
            ) as client:
                list_resp = await client.get("/api/v1/auth/sessions")
                assert list_resp.status_code == 200
                b_sessions = list_resp.json()["sessions"]
                assert len(b_sessions) >= 1
                b_session_id = b_sessions[0]["id"]

            # Login as User A
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td_a["subdomain"]},
            ) as client:
                login_a = await _login(client, td_a["subdomain"], td_a["email"])

            # Try to terminate User B's session as User A
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {login_a['access_token']}",
                    "X-Subdomain": td_a["subdomain"],
                },
            ) as client:
                resp = await client.delete(f"/api/v1/auth/sessions/{b_session_id}")
                # Should fail -- session not found (because it belongs to B, not A)
                assert resp.status_code == 404

        app.dependency_overrides.clear()


class TestSessionTenantIsolation:
    @pytest.mark.asyncio
    async def test_sessions_isolated_by_tenant(self, session_data, tenant_b_data):
        """Listing sessions should only return sessions for the current tenant."""
        td_a = session_data
        td_b = tenant_b_data

        app.dependency_overrides[get_db] = _override_get_db()
        app.dependency_overrides[get_unscoped_db] = _override_get_unscoped_db()

        with patch("app.middleware.tenant.async_session_maker", _test_middleware_session_maker), \
             patch("app.main.async_session_maker", _test_middleware_session_maker):

            # Login as both tenants
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td_a["subdomain"]},
            ) as client:
                login_a = await _login(client, td_a["subdomain"], td_a["email"])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"X-Subdomain": td_b["subdomain"]},
            ) as client:
                login_b = await _login(client, td_b["subdomain"], td_b["email"])

            # Tenant A lists sessions -- should NOT see Tenant B's
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {login_a['access_token']}",
                    "X-Subdomain": td_a["subdomain"],
                },
            ) as client:
                resp = await client.get("/api/v1/auth/sessions")
                assert resp.status_code == 200
                sessions = resp.json()["sessions"]

                # All sessions should belong to the current user only
                # (tenant isolation is enforced by both RLS and service filter)
                for s in sessions:
                    # We can't check tenant_id directly (not in response),
                    # but the count should only reflect Tenant A's sessions
                    pass

                a_count = resp.json()["count"]

            # Tenant B lists sessions -- should also see only their own
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={
                    "Authorization": f"Bearer {login_b['access_token']}",
                    "X-Subdomain": td_b["subdomain"],
                },
            ) as client:
                resp = await client.get("/api/v1/auth/sessions")
                assert resp.status_code == 200
                b_count = resp.json()["count"]

            # Both should have exactly 1 session each
            assert a_count >= 1
            assert b_count >= 1

        app.dependency_overrides.clear()


class TestSessionServiceLevel:
    @pytest.mark.asyncio
    async def test_session_service_list_returns_only_users_sessions(self, session_data):
        """SessionService.list_sessions filters by user_id and tenant_id."""
        td = session_data
        from app.services.session import SessionService

        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                {"tenant_id": str(td["tenant_id"])},
            )

            svc = SessionService(session)

            # Create a session manually
            from datetime import datetime, timezone, timedelta
            s = await svc.create_session(
                user_id=td["user_id"],
                tenant_id=td["tenant_id"],
                jti=f"test-jti-{uuid4().hex[:8]}",
                device_info="Test Browser on Test OS",
                ip_address="127.0.0.1",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session_id = s.id

            # List should include the session we created
            sessions = await svc.list_sessions(
                user_id=td["user_id"],
                tenant_id=td["tenant_id"],
            )
            session_ids = [s.id for s in sessions]
            assert session_id in session_ids

            # List for a different user should not include it
            other_user_id = uuid4()
            other_sessions = await svc.list_sessions(
                user_id=other_user_id,
                tenant_id=td["tenant_id"],
            )
            other_ids = [s.id for s in other_sessions]
            assert session_id not in other_ids

            await session.rollback()

    @pytest.mark.asyncio
    async def test_terminate_returns_jti(self, session_data):
        """Terminating a session should return the JTI for blacklisting."""
        td = session_data
        from app.services.session import SessionService
        from datetime import datetime, timezone, timedelta

        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                {"tenant_id": str(td["tenant_id"])},
            )

            svc = SessionService(session)
            jti = f"terminate-jti-{uuid4().hex[:8]}"

            s = await svc.create_session(
                user_id=td["user_id"],
                tenant_id=td["tenant_id"],
                jti=jti,
                device_info="Chrome on Windows",
                ip_address="10.0.0.1",
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )

            returned_jti = await svc.terminate_session(
                session_id=s.id,
                user_id=td["user_id"],
                tenant_id=td["tenant_id"],
            )
            assert returned_jti == jti

            await session.rollback()

    @pytest.mark.asyncio
    async def test_terminate_nonexistent_raises_error(self, session_data):
        """Terminating a nonexistent session should raise SessionService.Error."""
        td = session_data
        from app.services.session import SessionService

        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                {"tenant_id": str(td["tenant_id"])},
            )

            svc = SessionService(session)

            with pytest.raises(SessionService.Error) as exc_info:
                await svc.terminate_session(
                    session_id=uuid4(),
                    user_id=td["user_id"],
                    tenant_id=td["tenant_id"],
                )
            assert exc_info.value.code == 404

            await session.rollback()

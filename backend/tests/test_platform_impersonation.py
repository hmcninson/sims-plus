"""
Platform admin impersonation tests.

Tests the /platform/impersonate/{tenant_id} endpoint and validates that
impersonation tokens have correct claims, work at school endpoints,
and cannot be used for escalation.
"""

from datetime import datetime, UTC
from uuid import uuid4

import pyotp
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from unittest.mock import patch

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import admin_engine, admin_session_maker, app_session_maker

PLATFORM_TENANT_ID = settings.PLATFORM_TENANT_ID
TEST_PASSWORD = "PlatformAdmin123!"

_test_mw_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


async def _ensure_infra(session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT 1 FROM tenants WHERE id = CAST(:id AS uuid)"),
        {"id": PLATFORM_TENANT_ID},
    )
    if result.fetchone() is None:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), '_platform', '_platform', 'Platform Admin',
                    'single_school', 'enterprise', 'active', 999999, 999999, true)
            """),
            {"id": PLATFORM_TENANT_ID},
        )

    result = await session.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name = 'platform_audit_log'")
    )
    if result.fetchone() is None:
        await session.execute(text("""
            CREATE TABLE platform_audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                actor_user_id UUID NOT NULL,
                action VARCHAR(100) NOT NULL,
                target_tenant_id UUID,
                target_entity_type VARCHAR(50),
                target_entity_id UUID,
                details JSONB,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Revoke default-privilege-granted permissions, then grant INSERT only
        await session.execute(text("REVOKE ALL ON platform_audit_log FROM sims_app_user"))
        await session.execute(text("GRANT INSERT ON platform_audit_log TO sims_app_user"))

    await session.commit()


async def _create_admin_user(session: AsyncSession) -> dict:
    user_id = uuid4()
    email = f"padmin-{uuid4().hex[:8]}@simsplus.io"
    secret = pyotp.random_base32()
    await session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, mfa_secret,
                failed_login_attempts, timezone)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Platform', 'Admin', 'platform_admin', 'active',
                true, true, :secret, 0, 'UTC')
        """),
        {
            "id": str(user_id), "tid": PLATFORM_TENANT_ID,
            "email": email, "pw": hash_password(TEST_PASSWORD), "secret": secret,
        },
    )
    await session.commit()
    return {"id": user_id, "email": email}


async def _create_target_tenant(session: AsyncSession) -> dict:
    tid = uuid4()
    sub = f"imp-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :sub, :sub, :name, 'single_school',
                'professional', 'active', 1000, 100, true)
        """),
        {"id": str(tid), "sub": sub, "name": f"Target School {sub}"},
    )
    await session.commit()
    return {"id": tid, "subdomain": sub}


async def _cleanup(session: AsyncSession, user_id=None, tenant_ids=None) -> None:
    if user_id:
        await session.execute(
            text("DELETE FROM platform_audit_log WHERE actor_user_id = CAST(:id AS uuid)"),
            {"id": str(user_id)},
        )
        await session.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": str(user_id)},
        )
    for tid in (tenant_ids or []):
        await session.execute(
            text("DELETE FROM platform_audit_log WHERE target_tenant_id = CAST(:id AS uuid)"),
            {"id": str(tid)},
        )
        for table in ["students", "staff", "users", "schools"]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:id AS uuid)"),
                {"id": str(tid)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:id AS uuid)"),
            {"id": str(tid)},
        )
    await session.commit()


def _make_token(user_id: str, email: str) -> str:
    return create_access_token(
        subject=user_id,
        tenant_id=PLATFORM_TENANT_ID,
        role="platform_admin",
        permissions=["*"],
        extra_claims={"is_platform": True, "email": email, "tenant_subdomain": "_platform"},
    )


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _setup():
    async with admin_session_maker() as session:
        await _ensure_infra(session)


from contextlib import contextmanager

@contextmanager
def _apply_patches():
    async def override_unscoped():
        from fastapi import HTTPException
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except HTTPException:
                await session.commit()
                raise
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_unscoped_db] = override_unscoped

    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker), \
         patch("app.api.deps.async_session_maker", _test_mw_session_maker), \
         patch("app.services.platform.get_platform_admin_session_maker", lambda: admin_session_maker):
        yield

    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
class TestImpersonation:

    async def test_impersonation_returns_token_with_target_tenant_id(self):
        """POST /impersonate/{id} returns a token with the target tenant_id."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            target = await _create_target_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.post(f"/api/v1/platform/impersonate/{target['id']}")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "access_token" in data
                    assert data["tenant_id"] == str(target["id"])
                    assert data["tenant_subdomain"] == target["subdomain"]

                    # Decode the impersonation token to verify claims
                    payload = jose_jwt.decode(
                        data["access_token"],
                        settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM],
                    )
                    assert payload["tenant_id"] == str(target["id"])
                    assert payload["is_impersonation"] is True
                    assert payload["original_tenant_id"] == PLATFORM_TENANT_ID
                    assert payload["permissions"] == ["*"]
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"], tenant_ids=[target["id"]])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_impersonation_token_has_is_impersonation_true(self):
        """Impersonation JWT has is_impersonation=True."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            target = await _create_target_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.post(f"/api/v1/platform/impersonate/{target['id']}")
                    payload = jose_jwt.decode(
                        resp.json()["access_token"],
                        settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM],
                    )
                    assert payload["is_impersonation"] is True
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"], tenant_ids=[target["id"]])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_impersonation_token_expires_in_30_min(self):
        """Token expiry is approximately 30 minutes from creation."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            target = await _create_target_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.post(f"/api/v1/platform/impersonate/{target['id']}")
                    data = resp.json()
                    assert data["expires_in"] == settings.PLATFORM_IMPERSONATION_EXPIRY_MINUTES * 60

                    payload = jose_jwt.decode(
                        data["access_token"],
                        settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM],
                    )
                    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
                    iat = datetime.fromtimestamp(payload["iat"], tz=UTC)
                    diff_minutes = (exp - iat).total_seconds() / 60
                    # Should be close to 30 minutes (allow 1 minute tolerance)
                    assert abs(diff_minutes - settings.PLATFORM_IMPERSONATION_EXPIRY_MINUTES) < 1
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"], tenant_ids=[target["id"]])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_impersonation_audited(self):
        """Impersonation creates audit log entry with action='impersonate_start'."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            target = await _create_target_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    await client.post(f"/api/v1/platform/impersonate/{target['id']}")

            async with admin_session_maker() as session:
                result = await session.execute(
                    text("""
                        SELECT action FROM platform_audit_log
                        WHERE actor_user_id = CAST(:uid AS uuid)
                        AND action = 'impersonate_start'
                        AND target_tenant_id = CAST(:tid AS uuid)
                    """),
                    {"uid": str(user["id"]), "tid": str(target["id"])},
                )
                assert result.fetchone() is not None
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"], tenant_ids=[target["id"]])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_nonexistent_tenant_returns_404(self):
        """Cannot impersonate a nonexistent tenant."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    fake_id = uuid4()
                    resp = await client.post(f"/api/v1/platform/impersonate/{fake_id}")
                    assert resp.status_code == 404
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
class TestImpersonationRefreshBlocked:

    async def test_impersonation_token_cannot_access_platform_endpoints(self):
        """Impersonation token rejected at /platform/me."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            target = await _create_target_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    # Get impersonation token
                    resp = await client.post(f"/api/v1/platform/impersonate/{target['id']}")
                    imp_token = resp.json()["access_token"]

                # Try to use impersonation token at /platform/me
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {imp_token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/me")
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"], tenant_ids=[target["id"]])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_impersonation_token_cannot_create_new_impersonation(self):
        """Impersonation token cannot be used to create another impersonation token."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            target1 = await _create_target_tenant(session)
            target2 = await _create_target_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.post(f"/api/v1/platform/impersonate/{target1['id']}")
                    imp_token = resp.json()["access_token"]

                # Try to impersonate again with the impersonation token
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {imp_token}"},
                ) as client:
                    resp = await client.post(f"/api/v1/platform/impersonate/{target2['id']}")
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup(session, user_id=user["id"], tenant_ids=[target1["id"], target2["id"]])
            app.dependency_overrides.pop(get_unscoped_db, None)

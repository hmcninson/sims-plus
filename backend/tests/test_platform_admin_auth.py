"""
Platform admin auth dependency tests.

Tests the PlatformAdmin (get_platform_admin_user) dependency that guards
all /platform/* protected endpoints. Verifies token validation, role checks,
and that special token types (impersonation, mfa_pending, mfa_setup) are rejected.
"""

from datetime import datetime, timedelta, UTC
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


async def _ensure_platform_tenant(session: AsyncSession) -> None:
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
        await session.commit()


async def _ensure_platform_audit_table(session: AsyncSession) -> None:
    result = await session.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'platform_audit_log' AND table_schema = 'public'
        """)
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
        await session.execute(text(
            "REVOKE ALL ON platform_audit_log FROM sims_app_user"
        ))
        await session.execute(text(
            "GRANT INSERT ON platform_audit_log TO sims_app_user"
        ))
        await session.commit()


async def _create_platform_user(session: AsyncSession, *, status: str = "active") -> dict:
    user_id = uuid4()
    email = f"padmin-{uuid4().hex[:8]}@simsplus.io"
    secret = pyotp.random_base32()
    pw_hash = hash_password(TEST_PASSWORD)

    await session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, mfa_secret,
                failed_login_attempts, timezone, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Platform', 'Admin', 'platform_admin', :status,
                true, true, :secret, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(user_id), "tid": PLATFORM_TENANT_ID,
            "email": email, "pw": pw_hash, "status": status, "secret": secret,
        },
    )
    await session.commit()
    return {"id": user_id, "email": email, "mfa_secret": secret}


async def _cleanup_platform_user(session: AsyncSession, user_id) -> None:
    await session.execute(
        text("DELETE FROM platform_audit_log WHERE actor_user_id = CAST(:id AS uuid)"),
        {"id": str(user_id)},
    )
    await session.execute(
        text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": str(user_id)},
    )
    await session.commit()


def _make_platform_token(user_id: str, email: str, **extra_claims) -> str:
    """Create a platform admin access token with standard claims."""
    claims = {
        "is_platform": True,
        "email": email,
        "tenant_subdomain": "_platform",
    }
    claims.update(extra_claims)
    return create_access_token(
        subject=user_id,
        tenant_id=PLATFORM_TENANT_ID,
        role="platform_admin",
        permissions=["*"],
        extra_claims=claims,
    )


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _setup_platform_infra():
    async with admin_session_maker() as session:
        await _ensure_platform_audit_table(session)
        await _ensure_platform_tenant(session)


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
class TestPlatformAdminDependency:

    async def test_valid_platform_token_accepted(self):
        """GET /platform/me works with a valid platform token."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session)

        try:
            token = _make_platform_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/me")
                    assert resp.status_code == 200
                    assert resp.json()["email"] == user["email"]
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_expired_token_rejected(self):
        """Expired platform JWT returns 401."""
        expired = jose_jwt.encode(
            {
                "sub": str(uuid4()),
                "tenant_id": PLATFORM_TENANT_ID,
                "type": "access",
                "role": "platform_admin",
                "is_platform": True,
                "permissions": ["*"],
                "exp": datetime.now(UTC) - timedelta(minutes=1),
                "iat": datetime.now(UTC) - timedelta(minutes=20),
                "jti": str(uuid4()),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {expired}"},
            ) as client:
                resp = await client.get("/api/v1/platform/me")
                assert resp.status_code == 401
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_school_admin_token_rejected(self):
        """JWT with role=school_admin is rejected at /platform/* endpoints."""
        token = create_access_token(
            subject=str(uuid4()),
            tenant_id=str(uuid4()),
            role="school_admin",
            permissions=["*"],
            extra_claims={"email": "school@test.com"},
        )
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                resp = await client.get("/api/v1/platform/me")
                assert resp.status_code == 401
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_impersonation_token_rejected_at_platform_endpoints(self):
        """Impersonation token (is_impersonation=True) rejected at /platform/*."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session)

        try:
            # Create impersonation token with a different tenant_id
            target_tenant_id = str(uuid4())
            token = create_access_token(
                subject=str(user["id"]),
                tenant_id=target_tenant_id,
                role="platform_admin",
                permissions=["*"],
                extra_claims={
                    "is_platform": True,
                    "is_impersonation": True,
                    "original_tenant_id": PLATFORM_TENANT_ID,
                },
            )
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/me")
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_pending_token_rejected(self):
        """mfa_pending token rejected at /platform/* endpoints."""
        mfa_pending = jose_jwt.encode(
            {
                "sub": str(uuid4()),
                "tenant_id": PLATFORM_TENANT_ID,
                "type": "mfa_pending",
                "is_platform": True,
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "iat": datetime.now(UTC),
                "jti": str(uuid4()),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {mfa_pending}"},
            ) as client:
                resp = await client.get("/api/v1/platform/me")
                assert resp.status_code == 401
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_setup_token_rejected(self):
        """MFA setup token (mfa_setup_required=True) rejected at /platform/* endpoints."""
        setup_token = create_access_token(
            subject=str(uuid4()),
            tenant_id=PLATFORM_TENANT_ID,
            role="platform_admin",
            extra_claims={
                "is_platform": True,
                "mfa_setup_required": True,
            },
        )
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {setup_token}"},
            ) as client:
                resp = await client.get("/api/v1/platform/me")
                assert resp.status_code == 401
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_suspended_user_token_rejected(self):
        """JWT for a suspended platform admin user is rejected (DB lookup check)."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, status="suspended")

        try:
            token = _make_platform_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/me")
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
class TestPlatformEndpointAccess:

    async def test_platform_endpoints_skip_tenant_middleware(self):
        """Platform login works without X-Subdomain header (no subdomain needed)."""
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
            ) as client:
                # Even without subdomain header, /platform/login responds (not 400 tenant required)
                resp = await client.post("/api/v1/platform/login", json={
                    "email": "test@test.com",
                    "password": "Password123!",
                })
                # Should be 401 (invalid creds), NOT 400 (tenant required)
                assert resp.status_code == 401
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_platform_endpoints_skip_subscription_check(self):
        """Platform endpoints bypass subscription enforcement."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session)

        try:
            token = _make_platform_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    # This should succeed without any subscription checks
                    resp = await client.get("/api/v1/platform/me")
                    assert resp.status_code == 200
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

"""
Platform admin login and MFA tests.

Tests the /platform/login, /platform/mfa/verify, /platform/mfa/setup,
and /platform/mfa/generate endpoints.

Uses admin_session_maker to seed the platform tenant + user directly
(bypasses RLS). Tests run against the real FastAPI app via httpx.
"""

from datetime import datetime, timedelta, UTC
from uuid import uuid4

import pyotp
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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

# Middleware session maker for tenant lookups in test DB
_test_mw_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


async def _ensure_platform_tenant(session: AsyncSession) -> None:
    """Create the platform tenant if it doesn't exist."""
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
    """Create platform_audit_log table if it doesn't exist."""
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
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_platform_audit_actor ON platform_audit_log (actor_user_id)"
        ))
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON platform_audit_log (created_at)"
        ))
        # Revoke default-privilege-granted permissions, then grant INSERT only
        await session.execute(text(
            "REVOKE ALL ON platform_audit_log FROM sims_app_user"
        ))
        await session.execute(text(
            "GRANT INSERT ON platform_audit_log TO sims_app_user"
        ))
        await session.commit()


async def _create_platform_user(
    session: AsyncSession,
    *,
    mfa_enabled: bool = False,
    mfa_secret: str | None = None,
    status: str = "active",
    email: str | None = None,
) -> dict:
    """Create a platform admin user. Returns dict with id, email, password_hash."""
    user_id = uuid4()
    user_email = email or f"padmin-{uuid4().hex[:8]}@simsplus.io"
    pw_hash = hash_password(TEST_PASSWORD)

    await session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, mfa_secret,
                failed_login_attempts, timezone, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Platform', 'Admin', 'platform_admin', :status,
                true, :mfa_enabled, :mfa_secret, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(user_id),
            "tid": PLATFORM_TENANT_ID,
            "email": user_email,
            "pw": pw_hash,
            "status": status,
            "mfa_enabled": mfa_enabled,
            "mfa_secret": mfa_secret,
        },
    )
    await session.commit()

    return {"id": user_id, "email": user_email, "password_hash": pw_hash}


async def _cleanup_platform_user(session: AsyncSession, user_id) -> None:
    """Delete a platform admin user and related audit entries."""
    await session.execute(
        text("DELETE FROM platform_audit_log WHERE actor_user_id = CAST(:id AS uuid)"),
        {"id": str(user_id)},
    )
    await session.execute(
        text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": str(user_id)},
    )
    await session.commit()


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _setup_platform_infra():
    """Ensure platform tenant and audit table exist."""
    async with admin_session_maker() as session:
        await _ensure_platform_audit_table(session)
        await _ensure_platform_tenant(session)


from contextlib import contextmanager

@contextmanager
def _apply_patches():
    """Apply all necessary patches for platform admin testing."""
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
class TestPlatformLogin:

    async def test_valid_credentials_returns_mfa_setup_required(self):
        """First login (mfa_enabled=False) returns mfa_setup_required."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["mfa_setup_required"] is True
                    assert "access_token" in data
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_valid_credentials_with_mfa_enabled_returns_mfa_required(self):
        """User with MFA enabled gets mfa_required with pending token."""
        secret = pyotp.random_base32()
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=True, mfa_secret=secret)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["mfa_required"] is True
                    assert "mfa_pending_token" in data
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_invalid_password_returns_401(self):
        """Wrong password returns 401 with generic message."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": "WrongPassword123!",
                    })
                    assert resp.status_code == 401
                    assert resp.json()["detail"] == "Invalid email or password"
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_nonexistent_email_returns_401(self):
        """Email not found returns same 401 (no account enumeration)."""
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/api/v1/platform/login", json={
                    "email": f"nonexistent-{uuid4().hex[:8]}@simsplus.io",
                    "password": TEST_PASSWORD,
                })
                assert resp.status_code == 401
                assert resp.json()["detail"] == "Invalid email or password"
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_school_admin_cannot_platform_login(self):
        """A school_admin user cannot log in at /platform/login."""
        # Create a school tenant + school_admin user
        tenant_id = uuid4()
        user_id = uuid4()
        pw_hash = hash_password(TEST_PASSWORD)
        school_email = f"school-{uuid4().hex[:8]}@test.com"

        async with admin_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                        subscription_tier, status, max_students, max_staff, is_active)
                    VALUES (CAST(:id AS uuid), :sub, :sub, 'School', 'single_school',
                        'professional', 'active', 1000, 100, true)
                """),
                {"id": str(tenant_id), "sub": f"school-{uuid4().hex[:8]}"},
            )
            await session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                        role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                        'School', 'Admin', 'school_admin', 'active', true, false, 0, 'UTC')
                """),
                {"id": str(user_id), "tid": str(tenant_id), "email": school_email, "pw": pw_hash},
            )
            await session.commit()

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": school_email,
                        "password": TEST_PASSWORD,
                    })
                    # Should fail because user is not in platform tenant
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await session.execute(
                    text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
                    {"id": str(user_id)},
                )
                await session.execute(
                    text("DELETE FROM tenants WHERE id = CAST(:id AS uuid)"),
                    {"id": str(tenant_id)},
                )
                await session.commit()
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_lockout_after_5_failed_attempts(self):
        """After 5 failed attempts, account returns 429."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # 5 failed attempts
                    for _ in range(5):
                        await client.post("/api/v1/platform/login", json={
                            "email": user["email"],
                            "password": "WrongPassword123!",
                        })

                    # 6th attempt should be locked out
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": "WrongPassword123!",
                    })
                    assert resp.status_code == 429
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_suspended_account_rejected(self):
        """Suspended platform admin cannot log in."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False, status="suspended")

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_login_sets_last_activity_at(self):
        """Successful login sets user.last_activity_at."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })

            # Verify last_activity_at was set
            async with admin_session_maker() as session:
                result = await session.execute(
                    text("SELECT last_activity_at FROM users WHERE id = CAST(:id AS uuid)"),
                    {"id": str(user["id"])},
                )
                row = result.fetchone()
                assert row is not None
                assert row[0] is not None
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
class TestPlatformMFA:

    async def test_mfa_generate_returns_secret_and_uri(self):
        """GET /platform/mfa/generate returns TOTP secret + provisioning URI."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False)

        try:
            # Get a setup token via login
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    login_resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    setup_token = login_resp.json()["access_token"]

                    # Now call /mfa/generate with the setup token
                    resp = await client.get(
                        "/api/v1/platform/mfa/generate",
                        headers={"Authorization": f"Bearer {setup_token}"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "secret" in data
                    assert "provisioning_uri" in data
                    assert len(data["secret"]) >= 16
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_generate_requires_setup_token(self):
        """No token or regular token returns 401."""
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # No token at all
                resp = await client.get("/api/v1/platform/mfa/generate")
                assert resp.status_code in (401, 403)
        app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_setup_enables_mfa_and_returns_tokens(self):
        """MFA setup with valid code enables MFA and returns full tokens."""
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=False)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # Login to get setup token
                    login_resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    setup_token = login_resp.json()["access_token"]

                    # Generate secret
                    gen_resp = await client.get(
                        "/api/v1/platform/mfa/generate",
                        headers={"Authorization": f"Bearer {setup_token}"},
                    )
                    secret = gen_resp.json()["secret"]

                    # Complete setup with valid TOTP code
                    totp = pyotp.TOTP(secret)
                    resp = await client.post("/api/v1/platform/mfa/setup", json={
                        "setup_token": setup_token,
                        "totp_code": totp.now(),
                        "mfa_secret": secret,
                    })
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "access_token" in data
                    assert "refresh_token" in data
                    assert data["user"]["mfa_enabled"] is True
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_setup_when_already_enabled_returns_error(self):
        """Cannot call /mfa/setup if MFA is already enabled."""
        secret = pyotp.random_base32()
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=True, mfa_secret=secret)

        try:
            # Create a fake setup token (even though MFA is already enabled)
            setup_token = create_access_token(
                subject=str(user["id"]),
                tenant_id=PLATFORM_TENANT_ID,
                role="platform_admin",
                extra_claims={"is_platform": True, "mfa_setup_required": True},
            )
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    new_secret = pyotp.random_base32()
                    totp = pyotp.TOTP(new_secret)
                    resp = await client.post("/api/v1/platform/mfa/setup", json={
                        "setup_token": setup_token,
                        "totp_code": totp.now(),
                        "mfa_secret": new_secret,
                    })
                    assert resp.status_code == 401
                    assert "already" in resp.json()["detail"].lower()
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_verify_with_valid_code_returns_tokens(self):
        """Valid MFA code returns full access + refresh tokens."""
        secret = pyotp.random_base32()
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=True, mfa_secret=secret)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # Login to get mfa_pending_token
                    login_resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    pending_token = login_resp.json()["mfa_pending_token"]

                    # Verify MFA
                    totp = pyotp.TOTP(secret)
                    resp = await client.post("/api/v1/platform/mfa/verify", json={
                        "mfa_pending_token": pending_token,
                        "totp_code": totp.now(),
                    })
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "access_token" in data
                    assert "refresh_token" in data
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_verify_with_invalid_code_returns_401(self):
        """Invalid TOTP code returns 401."""
        secret = pyotp.random_base32()
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=True, mfa_secret=secret)

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    login_resp = await client.post("/api/v1/platform/login", json={
                        "email": user["email"],
                        "password": TEST_PASSWORD,
                    })
                    pending_token = login_resp.json()["mfa_pending_token"]

                    resp = await client.post("/api/v1/platform/mfa/verify", json={
                        "mfa_pending_token": pending_token,
                        "totp_code": "000000",
                    })
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_mfa_verify_with_expired_token_returns_401(self):
        """Expired mfa_pending_token returns 401."""
        from jose import jwt as jose_jwt

        secret = pyotp.random_base32()
        async with admin_session_maker() as session:
            user = await _create_platform_user(session, mfa_enabled=True, mfa_secret=secret)

        try:
            # Create an expired mfa_pending_token manually
            expired_token = jose_jwt.encode(
                {
                    "sub": str(user["id"]),
                    "tenant_id": PLATFORM_TENANT_ID,
                    "type": "mfa_pending",
                    "is_platform": True,
                    "exp": datetime.now(UTC) - timedelta(minutes=1),
                    "iat": datetime.now(UTC) - timedelta(minutes=10),
                    "jti": str(uuid4()),
                },
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )

            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    totp = pyotp.TOTP(secret)
                    resp = await client.post("/api/v1/platform/mfa/verify", json={
                        "mfa_pending_token": expired_token,
                        "totp_code": totp.now(),
                    })
                    assert resp.status_code == 401
        finally:
            async with admin_session_maker() as session:
                await _cleanup_platform_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

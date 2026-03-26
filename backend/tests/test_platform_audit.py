"""
Platform audit log tests.

Tests audit log creation, querying, filtering, and access control.
The platform_audit_log table has NO RLS and NO tenant_id.
sims_app_user has INSERT only (no SELECT) -- reads go via superuser engine.
"""

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
        # REVOKE default-privilege-granted permissions, then grant INSERT only.
        # ALTER DEFAULT PRIVILEGES in init-db.sql auto-grants SELECT/UPDATE/DELETE
        # on new tables, so we must explicitly revoke and re-grant INSERT only.
        await session.execute(text("REVOKE ALL ON platform_audit_log FROM sims_app_user"))
        await session.execute(text("GRANT INSERT ON platform_audit_log TO sims_app_user"))

    # Always enforce INSERT-only even if table existed from a prior run,
    # since ALTER DEFAULT PRIVILEGES may have re-granted SELECT.
    else:
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


async def _cleanup_user(session: AsyncSession, user_id) -> None:
    await session.execute(
        text("DELETE FROM platform_audit_log WHERE actor_user_id = CAST(:id AS uuid)"),
        {"id": str(user_id)},
    )
    await session.execute(
        text("DELETE FROM users WHERE id = CAST(:id AS uuid)"), {"id": str(user_id)},
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
class TestPlatformAuditLog:

    async def test_login_creates_audit_entry(self):
        """Platform login creates an audit entry."""
        secret = pyotp.random_base32()
        user_id = uuid4()
        email = f"padmin-{uuid4().hex[:8]}@simsplus.io"

        async with admin_session_maker() as session:
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

        try:
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    # Login (will return mfa_required)
                    resp = await client.post("/api/v1/platform/login", json={
                        "email": email,
                        "password": TEST_PASSWORD,
                    })
                    assert resp.status_code == 200

                    # Complete MFA to trigger full audit entry
                    pending_token = resp.json()["mfa_pending_token"]
                    totp = pyotp.TOTP(secret)
                    resp = await client.post("/api/v1/platform/mfa/verify", json={
                        "mfa_pending_token": pending_token,
                        "totp_code": totp.now(),
                    })
                    assert resp.status_code == 200

            # Check audit log
            async with admin_session_maker() as session:
                result = await session.execute(
                    text("""
                        SELECT action FROM platform_audit_log
                        WHERE actor_user_id = CAST(:uid AS uuid)
                        ORDER BY created_at
                    """),
                    {"uid": str(user_id)},
                )
                actions = [r[0] for r in result.fetchall()]
                assert "platform_login" in actions
        finally:
            async with admin_session_maker() as session:
                await _cleanup_user(session, user_id)
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_get_audit_log_returns_entries(self):
        """GET /platform/audit-log returns paginated entries."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            # Insert a test audit entry directly
            await session.execute(
                text("""
                    INSERT INTO platform_audit_log (actor_user_id, action, ip_address)
                    VALUES (CAST(:uid AS uuid), 'test_action', '127.0.0.1')
                """),
                {"uid": str(user["id"])},
            )
            await session.commit()

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/audit-log")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "items" in data
                    assert "total" in data
                    assert data["total"] >= 1
        finally:
            async with admin_session_maker() as session:
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_filter_by_action(self):
        """?action=test_filter filters audit entries."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            await session.execute(
                text("""
                    INSERT INTO platform_audit_log (actor_user_id, action)
                    VALUES (CAST(:uid AS uuid), 'test_filter')
                """),
                {"uid": str(user["id"])},
            )
            await session.execute(
                text("""
                    INSERT INTO platform_audit_log (actor_user_id, action)
                    VALUES (CAST(:uid AS uuid), 'other_action')
                """),
                {"uid": str(user["id"])},
            )
            await session.commit()

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/audit-log?action=test_filter")
                    assert resp.status_code == 200
                    data = resp.json()
                    for entry in data["items"]:
                        assert entry["action"] == "test_filter"
        finally:
            async with admin_session_maker() as session:
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_entries_ordered_by_created_at_desc(self):
        """Most recent entries appear first."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            # Insert entries with explicit timestamps
            await session.execute(
                text("""
                    INSERT INTO platform_audit_log (actor_user_id, action, created_at)
                    VALUES
                        (CAST(:uid AS uuid), 'older', '2026-01-01 00:00:00+00'),
                        (CAST(:uid AS uuid), 'newer', '2026-03-01 00:00:00+00')
                """),
                {"uid": str(user["id"])},
            )
            await session.commit()

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/audit-log")
                    data = resp.json()
                    if len(data["items"]) >= 2:
                        timestamps = [e["created_at"] for e in data["items"]]
                        # Verify descending order
                        assert timestamps == sorted(timestamps, reverse=True)
        finally:
            async with admin_session_maker() as session:
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_audit_log_not_visible_to_school_users(self):
        """School admin cannot access /platform/audit-log."""
        school_token = create_access_token(
            subject=str(uuid4()),
            tenant_id=str(uuid4()),
            role="school_admin",
            permissions=["*"],
            extra_claims={"email": "school@test.com"},
        )
        with _apply_patches():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {school_token}"},
            ) as client:
                resp = await client.get("/api/v1/platform/audit-log")
                assert resp.status_code == 401

    async def test_sims_app_user_cannot_select_audit_log(self):
        """Raw SQL check: sims_app_user has INSERT only, no SELECT on platform_audit_log."""
        async with admin_session_maker() as session:
            # Insert a test entry via admin (superuser)
            await session.execute(
                text("""
                    INSERT INTO platform_audit_log (actor_user_id, action)
                    VALUES (CAST(:uid AS uuid), 'select_test')
                """),
                {"uid": str(uuid4())},
            )
            await session.commit()

        # Try SELECT via app engine (sims_app_user) — should be denied
        async with app_session_maker() as session:
            with pytest.raises(Exception, match="(?i)permission denied"):
                await session.execute(
                    text("SELECT COUNT(*) FROM platform_audit_log")
                )

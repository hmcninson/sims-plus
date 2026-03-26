"""
Platform admin tenant CRUD tests.

Tests list, search, filter, paginate, update, suspend, and activate
operations on tenants via /platform/tenants endpoints.
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
from tests.conftest import admin_engine, admin_session_maker

PLATFORM_TENANT_ID = settings.PLATFORM_TENANT_ID
TEST_PASSWORD = "PlatformAdmin123!"

_test_mw_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


async def _ensure_infra(session: AsyncSession) -> None:
    """Ensure platform tenant and audit table exist."""
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

    # Audit table
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


async def _cleanup_user(session: AsyncSession, user_id) -> None:
    await session.execute(
        text("DELETE FROM platform_audit_log WHERE actor_user_id = CAST(:id AS uuid)"),
        {"id": str(user_id)},
    )
    await session.execute(
        text("DELETE FROM users WHERE id = CAST(:id AS uuid)"), {"id": str(user_id)},
    )
    await session.commit()


async def _create_test_tenant(session: AsyncSession, *, name: str = "Test", status: str = "active", tier: str = "professional") -> dict:
    tid = uuid4()
    sub = f"crud-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                subscription_tier, status, max_students, max_staff, is_active)
            VALUES (CAST(:id AS uuid), :sub, :sub, :name, 'single_school',
                :tier, :status, 1000, 100, true)
        """),
        {"id": str(tid), "sub": sub, "name": name, "tier": tier, "status": status},
    )
    await session.commit()
    return {"id": tid, "subdomain": sub, "name": name}


async def _delete_test_tenant(session: AsyncSession, tid) -> None:
    # Remove associated audit entries that may reference this tenant
    await session.execute(
        text("DELETE FROM platform_audit_log WHERE target_tenant_id = CAST(:id AS uuid)"),
        {"id": str(tid)},
    )
    # Remove any students/staff/schools/users that may have been created
    for table in ["students", "staff", "users", "schools"]:
        await session.execute(
            text(f"DELETE FROM {table} WHERE tenant_id = CAST(:id AS uuid)"),
            {"id": str(tid)},
        )
    await session.execute(
        text("DELETE FROM tenants WHERE id = CAST(:id AS uuid)"), {"id": str(tid)},
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
class TestListTenants:

    async def test_returns_all_tenants(self):
        """GET /platform/tenants returns non-platform tenants."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, name="ListTest One")

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/tenants")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "items" in data
                    assert "total" in data
                    # Platform tenant should NOT be in results
                    subdomains = [t["subdomain"] for t in data["items"]]
                    assert "_platform" not in subdomains
                    # Our test tenant should be present
                    ids = [t["id"] for t in data["items"]]
                    assert str(t1["id"]) in ids
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_search_by_name(self):
        """?search=XYZ filters by tenant name."""
        unique_name = f"UniqueSearch-{uuid4().hex[:6]}"
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, name=unique_name)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get(f"/api/v1/platform/tenants?search={unique_name}")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["total"] >= 1
                    names = [t["name"] for t in data["items"]]
                    assert unique_name in names
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_filter_by_status(self):
        """?status=suspended returns only suspended tenants."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, name="SuspendedOne", status="suspended")

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/tenants?status=suspended")
                    assert resp.status_code == 200
                    data = resp.json()
                    for item in data["items"]:
                        assert item["status"] == "suspended"
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_pagination(self):
        """page=1&page_size=1 returns only 1 item."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, name="Page1")
            t2 = await _create_test_tenant(session, name="Page2")

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/tenants?page=1&page_size=1")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert len(data["items"]) == 1
                    assert data["page"] == 1
                    assert data["page_size"] == 1
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _delete_test_tenant(session, t2["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
class TestUpdateTenant:

    async def test_update_subscription_tier(self):
        """PATCH /platform/tenants/{id} can change subscription_tier."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, tier="starter")

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.patch(
                        f"/api/v1/platform/tenants/{t1['id']}",
                        json={"subscription_tier": "professional"},
                    )
                    assert resp.status_code == 200

            # Verify change persisted
            async with admin_session_maker() as session:
                result = await session.execute(
                    text("SELECT subscription_tier FROM tenants WHERE id = CAST(:id AS uuid)"),
                    {"id": str(t1["id"])},
                )
                row = result.fetchone()
                assert row[0] == "professional"
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_update_audited(self):
        """Tenant update creates audit log entry."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    await client.patch(
                        f"/api/v1/platform/tenants/{t1['id']}",
                        json={"max_students": 500},
                    )

            # Check audit log
            async with admin_session_maker() as session:
                result = await session.execute(
                    text("""
                        SELECT action FROM platform_audit_log
                        WHERE actor_user_id = CAST(:uid AS uuid)
                        AND action = 'tenant_update'
                    """),
                    {"uid": str(user["id"])},
                )
                assert result.fetchone() is not None
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)


@pytest.mark.asyncio
class TestSuspendActivate:

    async def test_suspend_sets_status(self):
        """POST /suspend sets status=suspended."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, status="active")

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.post(
                        f"/api/v1/platform/tenants/{t1['id']}/suspend",
                        json={"reason": "Testing suspension"},
                    )
                    assert resp.status_code == 200

            # Verify
            async with admin_session_maker() as session:
                result = await session.execute(
                    text("SELECT status, is_active FROM tenants WHERE id = CAST(:id AS uuid)"),
                    {"id": str(t1["id"])},
                )
                row = result.fetchone()
                assert row[0] == "suspended"
                assert row[1] is False
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_activate_sets_status(self):
        """POST /activate sets status=active."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)
            t1 = await _create_test_tenant(session, status="suspended")

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.post(
                        f"/api/v1/platform/tenants/{t1['id']}/activate",
                    )
                    assert resp.status_code == 200

            # Verify
            async with admin_session_maker() as session:
                result = await session.execute(
                    text("SELECT status, is_active FROM tenants WHERE id = CAST(:id AS uuid)"),
                    {"id": str(t1["id"])},
                )
                row = result.fetchone()
                assert row[0] == "active"
                assert row[1] is True
        finally:
            async with admin_session_maker() as session:
                await _delete_test_tenant(session, t1["id"])
                await _cleanup_user(session, user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

"""
Platform analytics tests.

Tests the /platform/analytics endpoint which returns cross-tenant aggregates.
Uses admin engine to seed test tenants with students/staff for count verification.
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


async def _cleanup_all(session: AsyncSession, user_id=None, tenant_ids=None) -> None:
    if user_id:
        await session.execute(
            text("DELETE FROM platform_audit_log WHERE actor_user_id = CAST(:id AS uuid)"),
            {"id": str(user_id)},
        )
        await session.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"), {"id": str(user_id)},
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
class TestPlatformAnalytics:

    async def test_returns_tenant_counts(self):
        """GET /platform/analytics returns correct tenant counts by status."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/analytics")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert "total_tenants" in data
                    assert "active_tenants" in data
                    assert "trial_tenants" in data
                    assert "suspended_tenants" in data
                    assert isinstance(data["total_tenants"], int)
        finally:
            async with admin_session_maker() as session:
                await _cleanup_all(session, user_id=user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_returns_student_staff_counts(self):
        """Analytics includes total_students and total_staff."""
        # Create a tenant with some students and staff
        tenant_id = uuid4()
        school_id = uuid4()
        sub = f"analytics-{uuid4().hex[:8]}"

        async with admin_session_maker() as session:
            user = await _create_admin_user(session)

            # Tenant
            await session.execute(
                text("""
                    INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                        subscription_tier, status, max_students, max_staff, is_active)
                    VALUES (CAST(:id AS uuid), :sub, :sub, 'Analytics School', 'single_school',
                        'professional', 'active', 1000, 100, true)
                """),
                {"id": str(tenant_id), "sub": sub},
            )
            # School
            await session.execute(
                text("""
                    INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Analytics School', :slug, 'AN', 'basic')
                """),
                {"id": str(school_id), "tid": str(tenant_id), "slug": sub},
            )
            # Students
            for i in range(3):
                sid = uuid4()
                await session.execute(
                    text("""
                        INSERT INTO students (id, tenant_id, school_id, student_id,
                            first_name, last_name, gender, date_of_birth, status)
                        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                            :student_id, :fn, 'Test', 'male', '2010-01-01', 'active')
                    """),
                    {
                        "id": str(sid), "tid": str(tenant_id), "sid": str(school_id),
                        "student_id": f"AN-{i:04d}", "fn": f"Student{i}",
                    },
                )
            # Staff
            for i in range(2):
                staff_id_val = uuid4()
                await session.execute(
                    text("""
                        INSERT INTO staff (id, tenant_id, school_id, staff_id,
                            first_name, last_name, email, phone, gender,
                            job_title, staff_type, status, employment_date)
                        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                            :staff_id, :fn, 'Staff', :email, '+233200000000', 'male',
                            'Teacher', 'teaching', 'active', '2025-01-01')
                    """),
                    {
                        "id": str(staff_id_val), "tid": str(tenant_id), "sid": str(school_id),
                        "staff_id": f"ST-{i:04d}", "fn": f"Staff{i}",
                        "email": f"staff{i}-{uuid4().hex[:6]}@test.com",
                    },
                )
            await session.commit()

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    resp = await client.get("/api/v1/platform/analytics")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["total_students"] >= 3
                    assert data["total_staff"] >= 2
                    assert data["total_schools"] >= 1
        finally:
            async with admin_session_maker() as session:
                await _cleanup_all(session, user_id=user["id"], tenant_ids=[tenant_id])
            app.dependency_overrides.pop(get_unscoped_db, None)

    async def test_school_user_cannot_access_analytics(self):
        """School admin gets 401 at /platform/analytics."""
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
                resp = await client.get("/api/v1/platform/analytics")
                assert resp.status_code == 401

    async def test_analytics_audited(self):
        """Analytics access creates audit entry with action='analytics_view'."""
        async with admin_session_maker() as session:
            user = await _create_admin_user(session)

        try:
            token = _make_token(str(user["id"]), user["email"])
            with _apply_patches():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    await client.get("/api/v1/platform/analytics")

            async with admin_session_maker() as session:
                result = await session.execute(
                    text("""
                        SELECT action FROM platform_audit_log
                        WHERE actor_user_id = CAST(:uid AS uuid)
                        AND action = 'analytics_view'
                    """),
                    {"uid": str(user["id"])},
                )
                assert result.fetchone() is not None
        finally:
            async with admin_session_maker() as session:
                await _cleanup_all(session, user_id=user["id"])
            app.dependency_overrides.pop(get_unscoped_db, None)

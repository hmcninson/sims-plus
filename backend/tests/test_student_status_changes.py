"""
Tests for StudentStatusChange — enrollment status tracking.

Covers: record creation, nullable performed_by, history retrieval,
JSONB metadata, and the status-history and enrollment-analytics endpoints.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_status_prereqs(admin_session, tenant_id, *, with_user=True):
    """Seed school, academic year, student, and optionally a user.

    Returns dict with all IDs.
    """
    school_id = uuid4()
    academic_year_id = uuid4()
    class_id = uuid4()
    student_id = uuid4()
    user_id = uuid4() if with_user else None

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(academic_year_id), "tid": str(tenant_id),
         "name": f"AY-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id),
         "name": f"Class-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                class_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :student_id, 'Kofi', 'Adjei', '2011-06-20', 'male', 'active',
                CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
            "student_id": f"STU-{uuid4().hex[:8]}", "cid": str(class_id),
        },
    )

    if user_id:
        await admin_session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status,
                    email_verified, mfa_enabled, failed_login_attempts, timezone,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'User', 'school_admin', 'active',
                    true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(user_id), "tid": str(tenant_id),
             "email": f"admin-{uuid4().hex[:6]}@status.example.com",
             "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
        )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "academic_year_id": academic_year_id,
        "class_id": class_id,
        "student_id": student_id,
        "user_id": user_id,
    }


# --- Tests ---


async def test_record_status_change(app_session, admin_session):
    """Create a status change record and verify all fields."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_status_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    record = await svc.record_status_change(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        from_status=None,
        to_status="active",
        reason="New enrollment",
        effective_date=date(2025, 9, 1),
        performed_by=prereqs["user_id"],
        change_metadata={"source": "admission"},
    )

    assert record.id is not None
    assert record.student_id == prereqs["student_id"]
    assert record.from_status is None
    assert record.to_status == "active"
    assert record.reason == "New enrollment"
    assert record.effective_date == date(2025, 9, 1)
    assert record.performed_by == prereqs["user_id"]
    assert record.change_metadata == {"source": "admission"}


async def test_status_change_performed_by_nullable(app_session, admin_session):
    """performed_by can be NULL (e.g., system-triggered status change)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_status_prereqs(admin_session, tenant["id"], with_user=False)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    record = await svc.record_status_change(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        from_status="active",
        to_status="suspended",
        reason="System triggered",
        effective_date=date(2026, 1, 15),
        performed_by=None,
    )

    assert record.performed_by is None


async def test_get_status_history_ordered_desc(app_session, admin_session):
    """Multiple status changes are returned ordered by created_at DESC."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_status_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Insert two changes — first enrollment, then suspension
    await svc.record_status_change(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        from_status=None,
        to_status="active",
        reason="New enrollment",
        effective_date=date(2025, 9, 1),
        performed_by=prereqs["user_id"],
    )
    await svc.record_status_change(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        from_status="active",
        to_status="suspended",
        reason="Disciplinary",
        effective_date=date(2026, 1, 10),
        performed_by=prereqs["user_id"],
    )

    history = await svc.get_status_history(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
    )

    assert len(history) == 2
    # Most recent first (suspended is newer)
    assert history[0]["to_status"] == "suspended"
    assert history[1]["to_status"] == "active"
    # performed_by_name should be populated
    assert history[0]["performed_by_name"] is not None


async def test_status_change_with_metadata(app_session, admin_session):
    """Verify JSONB metadata is stored and returned correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_status_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    metadata = {
        "transfer_type": "outbound",
        "destination_school": "Achimota School",
        "transfer_date": "2026-03-01",
    }

    await svc.record_status_change(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        from_status="active",
        to_status="transferred",
        reason="Parent relocation",
        effective_date=date(2026, 3, 1),
        performed_by=prereqs["user_id"],
        change_metadata=metadata,
    )

    history = await svc.get_status_history(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
    )

    assert len(history) == 1
    assert history[0]["metadata"]["transfer_type"] == "outbound"
    assert history[0]["metadata"]["destination_school"] == "Achimota School"


async def test_status_history_endpoint(admin_session):
    """GET /students/{id}/status-history returns correct data."""
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import patch
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from fastapi import Request

    from app.main import app
    from app.api.deps import get_db, get_unscoped_db
    from app.core.security import create_access_token
    from tests.conftest import admin_engine, admin_session_maker, app_session_maker

    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    student_id = uuid4()
    class_id = uuid4()
    subdomain = f"stat-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, max_students, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 1000, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"Status Test {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, student_id_prefix)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic', 'STU')
            """),
            {"id": str(school_id), "tid": str(tenant_id),
             "name": "Status School", "slug": f"stat-{uuid4().hex[:8]}"},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'User', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tid": str(tenant_id),
             "email": f"admin-{uuid4().hex[:6]}@stat.example.com",
             "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
        )
        await session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, name, level, sequence, is_active)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'JHS 1', 'jhs', 1, true)
            """),
            {"id": str(class_id), "tid": str(tenant_id)},
        )
        await session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status, class_id)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :stuid, 'Abena', 'Osei', '2012-08-01', 'female', 'active',
                    CAST(:cid AS uuid))
            """),
            {"id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
             "stuid": f"STU-{uuid4().hex[:8]}", "cid": str(class_id)},
        )
        # Insert a status change record
        await session.execute(
            text("""
                INSERT INTO student_status_changes (id, tenant_id, student_id, school_id,
                    from_status, to_status, reason, effective_date, performed_by)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), NULL, 'active', 'Initial enrollment',
                    '2025-09-01', CAST(:uid AS uuid))
            """),
            {"id": str(uuid4()), "tid": str(tenant_id), "stuid": str(student_id),
             "sid": str(school_id), "uid": str(user_id)},
        )
        await session.commit()

    token = create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(school_id),
        role="school_admin",
        permissions=["*"],
    )

    _test_mw_session_maker = async_sessionmaker(
        admin_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                req_state = getattr(request, "state", None)
                tid = getattr(req_state, "tenant_id", None) if req_state else None
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

    async def override_unscoped():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    try:
        with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
             patch("app.main.async_session_maker", _test_mw_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Subdomain": subdomain,
                },
            ) as client:
                resp = await client.get(f"/api/v1/students/{student_id}/status-history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert body["records"][0]["to_status"] == "active"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_unscoped_db, None)


async def test_enrollment_analytics_endpoint(admin_session):
    """GET /students/enrollment-analytics returns status counts and by_class data."""
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import patch
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from fastapi import Request

    from app.main import app
    from app.api.deps import get_db, get_unscoped_db
    from app.core.security import create_access_token
    from tests.conftest import admin_engine, admin_session_maker, app_session_maker

    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    class_id = uuid4()
    subdomain = f"ana-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, max_students, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 1000, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"Analytics Test {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, student_id_prefix)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic', 'STU')
            """),
            {"id": str(school_id), "tid": str(tenant_id),
             "name": "Analytics School", "slug": f"ana-{uuid4().hex[:8]}"},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'User', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tid": str(tenant_id),
             "email": f"admin-{uuid4().hex[:6]}@ana.example.com",
             "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
        )
        await session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, name, level, sequence, is_active)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Primary 1', 'primary', 1, true)
            """),
            {"id": str(class_id), "tid": str(tenant_id)},
        )
        # Insert 2 active students in the class
        for i in range(2):
            await session.execute(
                text("""
                    INSERT INTO students (id, tenant_id, school_id, student_id,
                        first_name, last_name, date_of_birth, gender, status, class_id)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                        :stuid, :fn, :ln, '2013-01-01', 'male', 'active',
                        CAST(:cid AS uuid))
                """),
                {"id": str(uuid4()), "tid": str(tenant_id), "sid": str(school_id),
                 "stuid": f"STU-{uuid4().hex[:8]}",
                 "fn": f"Student{i}", "ln": "Test", "cid": str(class_id)},
            )
        await session.commit()

    token = create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(school_id),
        role="school_admin",
        permissions=["*"],
    )

    _test_mw_session_maker = async_sessionmaker(
        admin_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                req_state = getattr(request, "state", None)
                tid = getattr(req_state, "tenant_id", None) if req_state else None
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

    async def override_unscoped():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_unscoped

    try:
        with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
             patch("app.main.async_session_maker", _test_mw_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Subdomain": subdomain,
                },
            ) as client:
                resp = await client.get(
                    f"/api/v1/students/enrollment-analytics?school_id={school_id}"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_active"] == 2
        assert body["total_withdrawn"] == 0
        assert isinstance(body["by_class"], list)
        assert isinstance(body["trends"], list)
        assert isinstance(body["attrition_rate"], (int, float))
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_unscoped_db, None)

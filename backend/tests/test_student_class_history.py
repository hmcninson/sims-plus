"""
Tests for StudentClassHistory — class assignment tracking.

Covers: record creation, closing assignments, history retrieval,
joined names, unique index, and the class-history endpoint.
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


async def _seed_class_history_prereqs(admin_session, tenant_id):
    """Seed school, academic year, class, section, and student.

    Returns dict with all IDs.
    """
    school_id = uuid4()
    academic_year_id = uuid4()
    class_id = uuid4()
    section_id = uuid4()
    student_id = uuid4()

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
            INSERT INTO class_sections (id, tenant_id, class_id, name,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), 'A', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                class_id, section_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :student_id, 'Kwame', 'Asante', '2012-03-15', 'male', 'active',
                CAST(:cid AS uuid), CAST(:secid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
            "student_id": f"STU-{uuid4().hex[:8]}",
            "cid": str(class_id), "secid": str(section_id),
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "academic_year_id": academic_year_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_id": student_id,
    }


# --- Tests ---


async def test_record_class_assignment(app_session, admin_session):
    """Create a class assignment record and verify all fields are set."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_class_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    record = await svc.record_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        class_id=prereqs["class_id"],
        section_id=prereqs["section_id"],
        academic_year_id=prereqs["academic_year_id"],
        enrolled_date=date(2025, 9, 1),
    )

    assert record.id is not None
    assert record.student_id == prereqs["student_id"]
    assert record.class_id == prereqs["class_id"]
    assert record.section_id == prereqs["section_id"]
    assert record.academic_year_id == prereqs["academic_year_id"]
    assert record.enrolled_date == date(2025, 9, 1)
    assert record.left_date is None
    assert record.reason is None


async def test_close_class_assignment(app_session, admin_session):
    """Close an active assignment by setting left_date and reason."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_class_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Create an assignment first
    await svc.record_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        class_id=prereqs["class_id"],
        section_id=prereqs["section_id"],
        academic_year_id=prereqs["academic_year_id"],
        enrolled_date=date(2025, 9, 1),
    )

    # Close it
    await svc.close_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        academic_year_id=prereqs["academic_year_id"],
        left_date=date(2026, 7, 31),
        reason="year_end",
    )

    # Verify via get_class_history
    history = await svc.get_class_history(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
    )
    assert len(history) == 1
    assert history[0]["left_date"] == date(2026, 7, 31)
    assert history[0]["reason"] == "year_end"


async def test_close_nonexistent_assignment_raises(app_session, admin_session):
    """Closing a non-existent assignment raises StudentServiceError."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_class_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.close_class_assignment(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            academic_year_id=prereqs["academic_year_id"],
            left_date=date(2026, 7, 31),
            reason="year_end",
        )

    assert exc_info.value.code == "no_active_assignment"


async def test_get_class_history_ordered_desc(app_session, admin_session):
    """Multiple assignments are returned ordered by enrolled_date DESC."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_class_history_prereqs(admin_session, tenant["id"])

    # Create a second academic year and class
    ay2_id = uuid4()
    class2_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2026-09-01', '2027-07-31', 'planning', false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ay2_id), "tid": str(tenant["id"]), "name": f"AY2-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 2, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class2_id), "tid": str(tenant["id"]), "name": f"Class2-{uuid4().hex[:6]}"},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Create two assignments with different enrolled dates
    await svc.record_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        class_id=prereqs["class_id"],
        section_id=None,
        academic_year_id=prereqs["academic_year_id"],
        enrolled_date=date(2025, 9, 1),
    )
    await svc.record_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        class_id=class2_id,
        section_id=None,
        academic_year_id=ay2_id,
        enrolled_date=date(2026, 9, 1),
    )

    history = await svc.get_class_history(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
    )

    assert len(history) == 2
    # Most recent first
    assert history[0]["enrolled_date"] == date(2026, 9, 1)
    assert history[1]["enrolled_date"] == date(2025, 9, 1)


async def test_class_history_with_names(app_session, admin_session):
    """Verify class_name, section_name, academic_year_name are populated."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_class_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    await svc.record_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        class_id=prereqs["class_id"],
        section_id=prereqs["section_id"],
        academic_year_id=prereqs["academic_year_id"],
        enrolled_date=date(2025, 9, 1),
    )

    history = await svc.get_class_history(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
    )

    assert len(history) == 1
    record = history[0]
    # Names should be non-None because we seeded the related objects
    assert record["class_name"] is not None
    assert record["section_name"] == "A"
    assert record["academic_year_name"] is not None


async def test_duplicate_active_assignment_rejected(app_session, admin_session):
    """Same student+class+year with left_date=NULL should fail (unique index)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_class_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from sqlalchemy.exc import IntegrityError

    svc = StudentService(app_session)

    await svc.record_class_assignment(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        class_id=prereqs["class_id"],
        section_id=prereqs["section_id"],
        academic_year_id=prereqs["academic_year_id"],
        enrolled_date=date(2025, 9, 1),
    )

    # Try creating a duplicate active assignment for same student+class+year
    with pytest.raises(IntegrityError):
        await svc.record_class_assignment(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            class_id=prereqs["class_id"],
            section_id=prereqs["section_id"],
            academic_year_id=prereqs["academic_year_id"],
            enrolled_date=date(2025, 10, 1),
        )


async def test_class_history_endpoint(admin_session):
    """GET /students/{id}/class-history returns correct data via E2E client."""
    # This test uses raw SQL to insert history, then queries the endpoint.
    # We seed data via admin, then insert a class_history row directly.
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
    ay_id = uuid4()
    subdomain = f"hist-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, max_students, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 1000, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"Hist Test {subdomain}"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, student_id_prefix)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic', 'STU')
            """),
            {"id": str(school_id), "tid": str(tenant_id),
             "name": "Hist School", "slug": f"hist-{uuid4().hex[:8]}"},
        )
        await session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                    role, status, email_verified, mfa_enabled, failed_login_attempts, timezone)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Admin', 'User', 'school_admin', 'active', true, false, 0, 'Africa/Accra')
            """),
            {"id": str(user_id), "tid": str(tenant_id),
             "email": f"admin-{uuid4().hex[:6]}@hist.example.com",
             "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
        )
        await session.execute(
            text("""
                INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                    status, is_current)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                    '2025-09-01', '2026-07-31', 'active', true)
            """),
            {"id": str(ay_id), "tid": str(tenant_id)},
        )
        await session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, name, level, sequence, is_active)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Primary 1', 'primary', 1, true)
            """),
            {"id": str(class_id), "tid": str(tenant_id)},
        )
        await session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status, class_id)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :stuid, 'Ama', 'Mensah', '2013-05-01', 'female', 'active',
                    CAST(:cid AS uuid))
            """),
            {"id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
             "stuid": f"STU-{uuid4().hex[:8]}", "cid": str(class_id)},
        )
        # Insert a class history row
        await session.execute(
            text("""
                INSERT INTO student_class_history (id, tenant_id, student_id, school_id,
                    class_id, academic_year_id, enrolled_date)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), CAST(:cid AS uuid), CAST(:ayid AS uuid), '2025-09-01')
            """),
            {"id": str(uuid4()), "tid": str(tenant_id), "stuid": str(student_id),
             "sid": str(school_id), "cid": str(class_id), "ayid": str(ay_id)},
        )
        await session.commit()

    # Create JWT
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
                resp = await client.get(f"/api/v1/students/{student_id}/class-history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert any(r["class_name"] == "Primary 1" for r in body["records"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_unscoped_db, None)


async def test_class_history_endpoint_requires_auth():
    """GET /students/{id}/class-history rejects unauthenticated requests.

    Without a valid subdomain/token, the middleware rejects the request before
    reaching the auth layer. We verify the request is NOT allowed (not 200).
    With a valid subdomain but no token, we get 401.
    """
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import patch
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from app.main import app
    from app.api.deps import get_db, get_unscoped_db
    from tests.conftest import admin_engine, admin_session_maker, app_session_maker

    # We need a real tenant for the middleware to find
    tenant_id = uuid4()
    subdomain = f"noauth-{uuid4().hex[:8]}"

    _test_mw_session_maker = async_sessionmaker(
        admin_engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, max_students, is_active)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    'single_school', 'professional', 1000, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"NoAuth Test {subdomain}"},
        )
        await session.commit()

    async def override_unscoped():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_unscoped_db] = override_unscoped

    try:
        with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
             patch("app.main.async_session_maker", _test_mw_session_maker):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-Subdomain": subdomain},  # Valid subdomain, no auth token
            ) as client:
                resp = await client.get(f"/api/v1/students/{uuid4()}/class-history")

        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_unscoped_db, None)

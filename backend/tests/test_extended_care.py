"""
SIMS Plus - Extended Care Tests (Phase 2)

Tests exercise PreschoolExtendedCareService against a real PostgreSQL database.
Covers check-in, check-out, double-checkout error, list sessions (by student,
active-only), billing summary (hourly and flat-rate), and RLS tenant isolation.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import json
import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolExtendedCareService, PreschoolServiceError
from app.schemas.preschool import ExtendedCareCheckInRequest

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)


# ============================================================
# SQL templates for test data seeding
# ============================================================

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'preschool', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_ACADEMIC_YEAR_INSERT = text("""
    INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
        status, is_current, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
        :start_date, :end_date, 'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_TERM_INSERT = text("""
    INSERT INTO terms (id, tenant_id, academic_year_id, name, short_name,
        sequence, start_date, end_date, status, is_current,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay_id AS uuid),
        :name, :short_name, :seq, :start_date, :end_date,
        'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_CLASS_INSERT = text("""
    INSERT INTO classes (id, tenant_id, name, level, sequence,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :level, :seq,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
        date_of_birth, gender, status, class_id, school_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_care_env(session: AsyncSession) -> dict:
    """Seed a complete environment for extended care tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    student1_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Sunshine Preschool", "slug": f"sp-{uuid4().hex[:8]}",
    })
    await session.execute(_ACADEMIC_YEAR_INSERT, {
        "id": str(ay_id), "tid": str(tid), "name": "2025/2026",
        "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
    })
    await session.execute(_TERM_INSERT, {
        "id": str(term_id), "tid": str(tid), "ay_id": str(ay_id),
        "name": "First Term", "short_name": "T1", "seq": 1,
        "start_date": date(2025, 9, 1), "end_date": date(2025, 12, 20),
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_id), "tid": str(tid),
        "name": "KG 2", "level": "kg_2", "seq": 2,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "EC-001",
        "fn": "Abena", "ln": "Tetteh", "cid": str(class_id),
        "school_id": str(school_id),
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "student1_id": student1_id,
        "user_id": user["id"],
    }


@pytest.mark.asyncio
class TestExtendedCare:
    """Test extended care session lifecycle and billing."""

    async def test_check_in(self, admin_session, app_session):
        """Check in creates a session with check_in_time, no check_out_time."""
        env = await _seed_care_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolExtendedCareService(app_session)
        data = ExtendedCareCheckInRequest(
            student_id=env["student1_id"],
            session_type="after_care",
        )
        session = await service.check_in_extended_care(
            tenant_id=env["tenant_id"],
            data=data,
            checked_in_by=env["user_id"],
        )

        assert session.student_id == env["student1_id"]
        assert session.session_type == "after_care"
        assert session.session_date == date.today()
        assert session.check_in_time is not None
        assert session.check_out_time is None
        assert session.duration_minutes is None

    async def test_check_out(self, admin_session, app_session):
        """Check out sets check_out_time and calculates duration_minutes."""
        env = await _seed_care_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolExtendedCareService(app_session)
        data = ExtendedCareCheckInRequest(
            student_id=env["student1_id"],
            session_type="before_care",
        )
        session = await service.check_in_extended_care(
            tenant_id=env["tenant_id"],
            data=data,
            checked_in_by=env["user_id"],
        )

        checked_out = await service.check_out_extended_care(
            tenant_id=env["tenant_id"],
            session_id=session.id,
            checked_out_by=env["user_id"],
        )

        assert checked_out.check_out_time is not None
        assert checked_out.checked_out_by == env["user_id"]
        # Duration should be >= 0 (check-in and check-out happen almost instantly in tests)
        assert checked_out.duration_minutes is not None
        assert checked_out.duration_minutes >= 0

    async def test_check_out_already_checked_out(self, admin_session, app_session):
        """Double check-out raises an error."""
        env = await _seed_care_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolExtendedCareService(app_session)
        data = ExtendedCareCheckInRequest(
            student_id=env["student1_id"],
            session_type="after_care",
        )
        session = await service.check_in_extended_care(
            tenant_id=env["tenant_id"],
            data=data,
            checked_in_by=env["user_id"],
        )
        await service.check_out_extended_care(
            tenant_id=env["tenant_id"],
            session_id=session.id,
            checked_out_by=env["user_id"],
        )

        # Second check-out should fail
        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.check_out_extended_care(
                tenant_id=env["tenant_id"],
                session_id=session.id,
                checked_out_by=env["user_id"],
            )
        assert exc_info.value.code == "already_checked_out"

    async def test_list_sessions_by_student(self, admin_session, app_session):
        """List sessions filtered by student_id."""
        env = await _seed_care_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolExtendedCareService(app_session)

        # Create 3 sessions for the student
        for _ in range(3):
            data = ExtendedCareCheckInRequest(
                student_id=env["student1_id"],
                session_type="after_care",
            )
            await service.check_in_extended_care(
                tenant_id=env["tenant_id"],
                data=data,
                checked_in_by=env["user_id"],
            )

        sessions = await service.list_extended_care_sessions(
            env["tenant_id"],
            student_id=env["student1_id"],
        )
        assert len(sessions) == 3

    async def test_list_sessions_active_only(self, admin_session, app_session):
        """Active-only filter returns only sessions without check_out_time."""
        env = await _seed_care_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolExtendedCareService(app_session)

        # Check in 2 sessions
        sessions = []
        for _ in range(2):
            data = ExtendedCareCheckInRequest(
                student_id=env["student1_id"],
                session_type="after_care",
            )
            s = await service.check_in_extended_care(
                tenant_id=env["tenant_id"],
                data=data,
                checked_in_by=env["user_id"],
            )
            sessions.append(s)

        # Check out the first one
        await service.check_out_extended_care(
            tenant_id=env["tenant_id"],
            session_id=sessions[0].id,
            checked_out_by=env["user_id"],
        )

        # Only 1 should be active (not checked out)
        active = await service.list_extended_care_sessions(
            env["tenant_id"],
            student_id=env["student1_id"],
            checked_out=False,
        )
        assert len(active) == 1
        assert active[0].id == sessions[1].id

    async def test_billing_summary_hourly(self, admin_session, app_session):
        """Billing summary calculates total charge using hourly rate."""
        env = await _seed_care_env(admin_session)

        # Configure hourly rate on the school's preschool_settings
        await admin_session.execute(text("""
            UPDATE schools SET preschool_settings = CAST(:settings AS jsonb)
            WHERE id = CAST(:id AS uuid)
        """), {
            "settings": json.dumps({"extended_care_rate_per_hour": 5.0}),
            "id": str(env["school_id"]),
        })
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolExtendedCareService(app_session)

        today = date.today()

        # Insert 3 completed sessions with known durations via admin (to control times precisely)
        for i in range(3):
            session_id = uuid4()
            # Each session is 120 minutes (2 hours)
            check_in = time(7, 0, 0)
            check_out = time(9, 0, 0)
            await admin_session.execute(text("""
                INSERT INTO extended_care_sessions
                    (id, tenant_id, student_id, session_date, session_type,
                     check_in_time, check_out_time, duration_minutes,
                     checked_in_by, checked_out_by,
                     created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :sdate, 'before_care',
                    :cin, :cout, :dur,
                    CAST(:uid AS uuid), CAST(:uid AS uuid),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                "id": str(session_id),
                "tid": str(env["tenant_id"]),
                "sid": str(env["student1_id"]),
                "sdate": today,
                "cin": check_in,
                "cout": check_out,
                "dur": 120,
                "uid": str(env["user_id"]),
            })
        await admin_session.commit()

        # Billing summary: 3 sessions x 120 min = 360 min = 6 hours x $5/hr = $30
        summaries = await service.get_extended_care_billing_summary(
            env["tenant_id"],
            student_id=env["student1_id"],
            date_from=today,
            date_to=today,
        )

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary["total_sessions"] == 3
        assert summary["total_minutes"] == 360
        assert summary["estimated_charge"] == Decimal("30.00")

    async def test_billing_summary_flat_rate(self, admin_session, app_session):
        """Billing summary calculates total charge using flat rate per session."""
        env = await _seed_care_env(admin_session)

        # Configure flat rate on the school's preschool_settings
        await admin_session.execute(text("""
            UPDATE schools SET preschool_settings = CAST(:settings AS jsonb)
            WHERE id = CAST(:id AS uuid)
        """), {
            "settings": json.dumps({"extended_care_flat_rate": 10.0}),
            "id": str(env["school_id"]),
        })
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolExtendedCareService(app_session)

        today = date.today()

        # Insert 3 completed sessions via admin
        for i in range(3):
            session_id = uuid4()
            await admin_session.execute(text("""
                INSERT INTO extended_care_sessions
                    (id, tenant_id, student_id, session_date, session_type,
                     check_in_time, check_out_time, duration_minutes,
                     checked_in_by, checked_out_by,
                     created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :sdate, 'after_care',
                    :cin, :cout, :dur,
                    CAST(:uid AS uuid), CAST(:uid AS uuid),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                "id": str(session_id),
                "tid": str(env["tenant_id"]),
                "sid": str(env["student1_id"]),
                "sdate": today,
                "cin": time(14, 0, 0),
                "cout": time(16, 0, 0),
                "dur": 120,
                "uid": str(env["user_id"]),
            })
        await admin_session.commit()

        # Billing: 3 sessions x $10 flat = $30
        summaries = await service.get_extended_care_billing_summary(
            env["tenant_id"],
            student_id=env["student1_id"],
            date_from=today,
            date_to=today,
        )

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary["total_sessions"] == 3
        assert summary["estimated_charge"] == Decimal("30.00")

    async def test_extended_care_rls(self, admin_session, app_session):
        """Extended care sessions from tenant A are invisible to tenant B."""
        env_a = await _seed_care_env(admin_session)

        # Insert a session for tenant A via admin
        session_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO extended_care_sessions
                (id, tenant_id, student_id, session_date, session_type,
                 check_in_time, checked_in_by,
                 created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CURRENT_DATE, 'after_care',
                '15:00:00', CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(session_id),
            "tid": str(env_a["tenant_id"]),
            "sid": str(env_a["student1_id"]),
            "uid": str(env_a["user_id"]),
        })
        await admin_session.commit()

        # Seed tenant B
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Query as tenant B — should see 0 sessions
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM extended_care_sessions")
        )
        count = result.scalar()
        assert count == 0, (
            f"Tenant B should see 0 extended care sessions but saw {count}"
        )

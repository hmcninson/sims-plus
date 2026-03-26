"""
SIMS Plus - Daily Report Sending Tests (Phase 2)

Tests exercise PreschoolObservationService.send_daily_log_to_parents() and
bulk_send_daily_logs() against a real PostgreSQL database.

The send methods depend on NotificationDispatcher which requires guardian/email
infrastructure. These tests verify the service-layer logic (log lookup, student
resolution, error handling) rather than actual SMS/email delivery — the dispatcher
is expected to either succeed silently or be caught by the service's try/except.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import pytest
from datetime import date, time
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolObservationService, PreschoolServiceError
from app.schemas.preschool import DailyActivityLogCreate

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


async def _seed_report_env(session: AsyncSession) -> dict:
    """Seed environment for daily report sending tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    student1_id = uuid4()
    student2_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Daily Report Preschool", "slug": f"dr-{uuid4().hex[:8]}",
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
        "name": "KG 1", "level": "kg_1", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "DR-001",
        "fn": "Efua", "ln": "Appiah", "cid": str(class_id),
        "school_id": str(school_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student2_id), "tid": str(tid), "sid": "DR-002",
        "fn": "Kofi", "ln": "Asare", "cid": str(class_id),
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
        "student2_id": student2_id,
        "user_id": user["id"],
    }


async def _create_daily_log(service, env, student_id, log_date):
    """Create a daily activity log via the service."""
    data = DailyActivityLogCreate(
        student_id=student_id,
        log_date=log_date,
        arrival_time=time(8, 0),
        arrival_mood="happy",
        departure_time=time(14, 0),
        departure_mood="tired",
        nap_quality="good",
        notes="Good day overall",
        highlights="Enjoyed painting and group reading",
    )
    return await service.create_or_update_daily_log(
        tenant_id=env["tenant_id"],
        data=data,
        user_id=env["user_id"],
    )


@pytest.mark.asyncio
class TestDailyReportSend:
    """Test daily log sending to parents."""

    async def test_send_daily_log_to_parents(self, admin_session, app_session):
        """Send a daily log notification — should return sent/failed counts without error.

        The NotificationDispatcher may not have a real email/SMS backend in tests,
        but the service catches exceptions gracefully. We verify the service
        locates the log, resolves the student, and returns a result dict.
        """
        env = await _seed_report_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolObservationService(app_session)
        log = await _create_daily_log(service, env, env["student1_id"], date.today())

        result = await service.send_daily_log_to_parents(
            tenant_id=env["tenant_id"],
            log_id=log.id,
            sent_by=env["user_id"],
        )

        # Result should be a dict with sent_count and failed_count
        assert isinstance(result, dict)
        assert "sent_count" in result
        assert "failed_count" in result
        # Total should be 1 (one dispatch attempt for one student)
        assert result["sent_count"] + result["failed_count"] == 1

    async def test_send_daily_log_not_found(self, admin_session, app_session):
        """Sending a non-existent log raises not_found error."""
        env = await _seed_report_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolObservationService(app_session)

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.send_daily_log_to_parents(
                tenant_id=env["tenant_id"],
                log_id=uuid4(),  # random non-existent ID
                sent_by=env["user_id"],
            )
        assert exc_info.value.code == "not_found"

    async def test_bulk_send_daily_logs(self, admin_session, app_session):
        """Bulk send daily logs for a class on a given date."""
        env = await _seed_report_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolObservationService(app_session)
        today = date.today()

        # Create logs for 2 students in the same class
        await _create_daily_log(service, env, env["student1_id"], today)
        await _create_daily_log(service, env, env["student2_id"], today)

        result = await service.bulk_send_daily_logs(
            tenant_id=env["tenant_id"],
            class_id=env["class_id"],
            log_date=today,
            sent_by=env["user_id"],
        )

        assert isinstance(result, dict)
        assert result["total_students"] == 2
        # Each student's log triggers one dispatch attempt
        assert result["sent_count"] + result["failed_count"] == 2

    async def test_bulk_send_no_logs(self, admin_session, app_session):
        """Bulk send for a class with no logs on the given date returns total=0."""
        env = await _seed_report_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolObservationService(app_session)

        # No daily logs created for this date
        result = await service.bulk_send_daily_logs(
            tenant_id=env["tenant_id"],
            class_id=env["class_id"],
            log_date=date(2020, 1, 1),  # date with no logs
            sent_by=env["user_id"],
        )

        assert result["total_students"] == 0
        assert result["sent_count"] == 0
        assert result["failed_count"] == 0

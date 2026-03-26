"""
Tests for staff attendance backend contract (Phase 2).

These verify the existing staff attendance endpoints produce the correct
response shapes for the frontend to consume. All endpoints already exist;
these tests confirm the contract is stable.

Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date, time
from uuid import uuid4

from sqlalchemy import text

from app.services.attendance import AttendanceService

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("staff_attendance_serial"),
]


# --- Helpers ---


async def _seed_staff_attendance_prereqs(admin_session, tenant_id, num_staff=1):
    """Seed school and N staff members. Returns dict with IDs."""
    school_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    staff_ids = []
    for i in range(num_staff):
        sid = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title,
                    employment_date,
                    created_at, updated_at)
                VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, :fn, :ln,
                    'male', :email, '0241234567',
                    'teaching', 'active', 'Teacher',
                    '2020-09-01',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(sid), "tid": str(tenant_id), "sid": str(school_id),
                "staff_num": f"STF-{uuid4().hex[:8]}",
                "fn": f"Staff{i}",
                "ln": "Test",
                "email": f"staff-{uuid4().hex[:8]}@test.com",
            },
        )
        staff_ids.append(sid)

    await admin_session.commit()
    return {"school_id": school_id, "staff_ids": staff_ids}


# --- Tests ---


async def test_mark_single_staff_attendance_returns_correct_response(
    app_session, admin_session,
):
    """Marking single staff attendance returns a record with status, date, and check_in_time."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"])
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    record = await service.mark_staff_attendance(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        attendance_date=date(2026, 3, 10),
        status="present",
        check_in_time=time(7, 45),
    )

    assert record.id is not None
    assert record.status.value == "present"
    assert record.date == date(2026, 3, 10)
    assert record.check_in_time == time(7, 45)
    assert record.tenant_id == tenant["id"]


async def test_bulk_mark_staff_attendance_all_present(
    app_session, admin_session,
):
    """Bulk marking 3 staff as present creates 3 records."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"], num_staff=3)
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    result = await service.bulk_mark_staff_attendance(
        tenant_id=tenant["id"],
        attendance_date=date(2026, 3, 10),
        attendance_records=[
            {"staff_id": str(sid), "status": "present"}
            for sid in prereqs["staff_ids"]
        ],
    )

    assert result["created"] == 3
    assert result["updated"] == 0
    assert result["failed"] == 0


async def test_bulk_mark_staff_attendance_mixed_statuses(
    app_session, admin_session,
):
    """Bulk marking with mixed statuses (present, absent, late) works correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"], num_staff=3)
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    statuses = ["present", "absent", "late"]
    result = await service.bulk_mark_staff_attendance(
        tenant_id=tenant["id"],
        attendance_date=date(2026, 3, 10),
        attendance_records=[
            {"staff_id": str(sid), "status": status}
            for sid, status in zip(prereqs["staff_ids"], statuses)
        ],
    )

    assert result["created"] == 3
    assert result["failed"] == 0

    # Verify each record has the correct status
    for sid, expected_status in zip(prereqs["staff_ids"], statuses):
        records, total = await service.list_staff_attendance(
            tenant["id"],
            staff_id=sid,
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 10),
        )
        assert total == 1
        assert records[0].status.value == expected_status


async def test_list_staff_attendance_with_date_filter(
    app_session, admin_session,
):
    """List with date range filter returns only matching records."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"])
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    # Mark 3 consecutive days
    for day in [date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)]:
        await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_ids"][0],
            attendance_date=day,
            status="present",
        )

    # Filter to only the last 2 days
    records, total = await service.list_staff_attendance(
        tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        start_date=date(2026, 3, 11),
        end_date=date(2026, 3, 12),
    )

    assert total == 2
    assert len(records) == 2


async def test_list_staff_attendance_with_status_filter(
    app_session, admin_session,
):
    """List with status filter returns only matching records."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"])
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    await service.mark_staff_attendance(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        attendance_date=date(2026, 3, 10),
        status="present",
    )
    await service.mark_staff_attendance(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        attendance_date=date(2026, 3, 11),
        status="absent",
    )

    records, total = await service.list_staff_attendance(
        tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        status="absent",
    )

    assert total == 1
    assert records[0].status.value == "absent"


async def test_get_staff_attendance_summary_returns_correct_counts(
    app_session, admin_session,
):
    """Summary returns correct counts for present, absent, late, and attendance_rate."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"])
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    # Mark 5 days with mixed statuses
    marks = [
        (date(2026, 3, 10), "present"),
        (date(2026, 3, 11), "present"),
        (date(2026, 3, 12), "absent"),
        (date(2026, 3, 13), "late"),
        (date(2026, 3, 14), "excused"),
    ]
    for day, status in marks:
        await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_ids"][0],
            attendance_date=day,
            status=status,
        )

    summary = await service.get_staff_attendance_summary(
        tenant["id"], prereqs["staff_ids"][0],
    )

    assert summary["total_days"] == 5
    assert summary["present"] == 2
    assert summary["absent"] == 1
    assert summary["late"] == 1
    assert summary["excused"] == 1
    # attendance_rate = (present + late) / total = 3/5 = 60%
    assert summary["attendance_rate"] == 60.0


async def test_staff_attendance_report_daily_breakdown(
    app_session, admin_session,
):
    """List returns records ordered by date descending for daily breakdown."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"])
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    days = [date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)]
    for day in days:
        await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_ids"][0],
            attendance_date=day,
            status="present",
        )

    records, total = await service.list_staff_attendance(
        tenant["id"],
        staff_id=prereqs["staff_ids"][0],
    )

    assert total == 3
    # Records should be in descending date order
    assert records[0].date >= records[1].date >= records[2].date


async def test_delete_staff_attendance_record(
    app_session, admin_session,
):
    """Deleting a staff attendance record removes it from subsequent queries."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_attendance_prereqs(admin_session, tenant["id"])
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    service = AttendanceService(app_session)

    record = await service.mark_staff_attendance(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        attendance_date=date(2026, 3, 10),
        status="present",
    )
    record_id = record.id

    deleted = await service.delete_staff_attendance(tenant["id"], record_id)
    assert deleted is True

    # Verify it's gone from list
    records, total = await service.list_staff_attendance(
        tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 10),
    )
    assert total == 0

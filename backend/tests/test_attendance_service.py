"""
Attendance Service Tests

Tests for student and staff attendance CRUD and reporting operations.
Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

Attendance requires prerequisite data (tenant, school, class, section,
student/staff) seeded via admin_session before testing under RLS.

IMPORTANT: These tests require a running sims_plus_test database with
RLS policies applied (alembic upgrade head).
"""

from datetime import date, time
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.services.attendance import AttendanceService

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("attendance_serial"),
]


# =========================
# Helper: seed attendance prerequisites via admin
# =========================


async def seed_school(admin_session, tenant_id):
    """Seed a school for a tenant. Returns school_id."""
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
    )
    return school_id


async def seed_class_and_section(admin_session, tenant_id):
    """Seed a class and section. Returns (class_id, section_id)."""
    class_id = uuid4()
    section_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, sequence, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(class_id),
            "tid": str(tenant_id),
            "name": f"Class-{uuid4().hex[:6]}",
        },
    )
    await admin_session.execute(
        text("""
            INSERT INTO class_sections (
                id, tenant_id, class_id, name, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                'A', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(section_id),
            "tid": str(tenant_id),
            "cid": str(class_id),
        },
    )
    return class_id, section_id


async def seed_student(admin_session, tenant_id, school_id, section_id):
    """Seed a student. Returns student_id."""
    student_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, section_id,
                student_id, first_name, last_name,
                date_of_birth, gender, status,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:sid AS uuid), CAST(:sec_id AS uuid),
                :student_num, :fn, :ln,
                '2012-05-15', 'male', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "sec_id": str(section_id),
            "student_num": f"STU-{uuid4().hex[:6]}",
            "fn": "Kwame",
            "ln": "Asante",
        },
    )
    return student_id


async def seed_staff(admin_session, tenant_id, school_id):
    """Seed a staff member. Returns staff record id."""
    staff_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title,
                employment_date,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, :fn, :ln,
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher',
                '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(staff_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:6]}",
            "fn": "Kofi",
            "ln": "Mensah",
            "email": f"staff-{uuid4().hex[:6]}@test.com",
        },
    )
    return staff_id


async def seed_attendance_fixtures(admin_session, tenant_id):
    """Seed all prerequisites for attendance tests.
    Returns dict with school_id, class_id, section_id, student_id, staff_id.
    """
    school_id = await seed_school(admin_session, tenant_id)
    class_id, section_id = await seed_class_and_section(admin_session, tenant_id)
    student_id = await seed_student(admin_session, tenant_id, school_id, section_id)
    staff_id = await seed_staff(admin_session, tenant_id, school_id)
    return {
        "school_id": school_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_id": student_id,
        "staff_id": staff_id,
    }


# =========================
# Student Attendance Tests
# =========================


class TestMarkStudentAttendance:
    """Tests for marking individual student attendance."""

    async def test_mark_student_present(self, app_session, admin_session):
        """Marking a student present creates a record with status=present."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )

        assert record is not None
        assert record.status.value == "present"
        assert record.date == date(2026, 1, 15)
        assert record.student_id == fixtures["student_id"]
        assert record.section_id == fixtures["section_id"]

    async def test_mark_student_absent(self, app_session, admin_session):
        """Marking a student absent creates a record with status=absent."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="absent",
            excuse_reason="Family emergency",
        )

        assert record.status.value == "absent"
        assert record.excuse_reason == "Family emergency"

    async def test_mark_student_late_with_check_in_time(
        self, app_session, admin_session
    ):
        """Marking a student late stores the check_in_time."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        check_in = time(8, 45)
        record = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="late",
            check_in_time=check_in,
        )

        assert record.status.value == "late"
        assert record.check_in_time == check_in

    async def test_mark_already_marked_date_updates_existing(
        self, app_session, admin_session
    ):
        """Marking attendance for an already-marked date updates the record."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        # First mark: present
        record_1 = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )
        record_1_id = record_1.id

        # Second mark same date: absent (upsert)
        record_2 = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="absent",
        )

        # Should update the same record, not create a new one
        assert record_2.id == record_1_id
        assert record_2.status.value == "absent"


class TestBulkMarkStudentAttendance:
    """Tests for bulk student attendance marking."""

    async def test_bulk_mark_creates_multiple_records(
        self, app_session, admin_session
    ):
        """Bulk mark creates attendance for multiple students."""
        tenant = await create_test_tenant(admin_session)
        school_id = await seed_school(admin_session, tenant["id"])
        class_id, section_id = await seed_class_and_section(admin_session, tenant["id"])
        student_1 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        student_2 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        result = await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=section_id,
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"student_id": str(student_1), "status": "present"},
                {"student_id": str(student_2), "status": "absent"},
            ],
        )

        assert result["created"] == 2
        assert result["updated"] == 0
        assert result["failed"] == 0

    async def test_bulk_mark_updates_existing_records(
        self, app_session, admin_session
    ):
        """Bulk mark updates already-marked students instead of creating dupes."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        # First bulk mark
        await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"student_id": str(fixtures["student_id"]), "status": "present"},
            ],
        )

        # Second bulk mark on same date (should update)
        result = await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"student_id": str(fixtures["student_id"]), "status": "absent"},
            ],
        )

        assert result["created"] == 0
        assert result["updated"] == 1

    async def test_bulk_mark_skips_missing_student_id(
        self, app_session, admin_session
    ):
        """Bulk mark counts failure for records missing student_id."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        result = await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"status": "present"},  # Missing student_id
            ],
        )

        assert result["failed"] == 1
        assert result["created"] == 0


class TestGetStudentAttendance:
    """Tests for retrieving student attendance."""

    async def test_get_student_attendance_for_date(
        self, app_session, admin_session
    ):
        """Get returns the attendance record for a specific student and date."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )

        record = await service.get_student_attendance(
            tenant["id"], fixtures["student_id"], date(2026, 1, 15)
        )

        assert record is not None
        assert record.status.value == "present"

    async def test_get_student_attendance_returns_none_for_unmarked_date(
        self, app_session, admin_session
    ):
        """Get returns None when no attendance exists for the date."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.get_student_attendance(
            tenant["id"], fixtures["student_id"], date(2026, 1, 15)
        )

        assert record is None

    async def test_get_section_attendance_returns_all_for_date(
        self, app_session, admin_session
    ):
        """Get section attendance returns all records for a section on a date."""
        tenant = await create_test_tenant(admin_session)
        school_id = await seed_school(admin_session, tenant["id"])
        class_id, section_id = await seed_class_and_section(admin_session, tenant["id"])
        student_1 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        student_2 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=section_id,
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"student_id": str(student_1), "status": "present"},
                {"student_id": str(student_2), "status": "late"},
            ],
        )

        records = await service.get_section_attendance(
            tenant["id"], section_id, date(2026, 1, 15)
        )

        assert len(records) == 2


class TestDeleteStudentAttendance:
    """Tests for soft-deleting student attendance."""

    async def test_soft_delete_attendance(self, app_session, admin_session):
        """Deleted attendance record is no longer returned by queries."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )

        deleted = await service.delete_student_attendance(
            tenant["id"], record.id
        )
        assert deleted is True

        # Should no longer be found
        result = await service.get_student_attendance(
            tenant["id"], fixtures["student_id"], date(2026, 1, 15)
        )
        assert result is None

    async def test_delete_nonexistent_attendance_returns_false(
        self, app_session, admin_session
    ):
        """Deleting a nonexistent attendance record returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        result = await service.delete_student_attendance(
            tenant["id"], uuid4()
        )
        assert result is False

    async def test_deleted_attendance_excluded_from_list(
        self, app_session, admin_session
    ):
        """Soft-deleted attendance records are excluded from list queries."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.mark_student_attendance(
            tenant_id=tenant["id"],
            student_id=fixtures["student_id"],
            section_id=fixtures["section_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )

        await service.delete_student_attendance(tenant["id"], record.id)

        records, total = await service.list_student_attendance(
            tenant["id"],
            student_id=fixtures["student_id"],
        )
        assert total == 0
        assert len(records) == 0


# =========================
# Student Attendance Statistics
# =========================


class TestStudentAttendanceSummary:
    """Tests for student attendance summary statistics."""

    async def test_student_attendance_summary_counts(
        self, app_session, admin_session
    ):
        """Summary returns correct counts for each status."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        # Mark 3 days: present, absent, late
        for day, status in [
            (date(2026, 1, 13), "present"),
            (date(2026, 1, 14), "absent"),
            (date(2026, 1, 15), "late"),
        ]:
            await service.mark_student_attendance(
                tenant_id=tenant["id"],
                student_id=fixtures["student_id"],
                section_id=fixtures["section_id"],
                attendance_date=day,
                status=status,
            )

        summary = await service.get_student_attendance_summary(
            tenant["id"], fixtures["student_id"]
        )

        assert summary["total_days"] == 3
        assert summary["present"] == 1
        assert summary["absent"] == 1
        assert summary["late"] == 1
        # Attendance rate: (present + late) / total = 2/3 = 66.67%
        assert summary["attendance_rate"] == pytest.approx(66.67, abs=0.01)

    async def test_student_attendance_summary_empty(
        self, app_session, admin_session
    ):
        """Summary returns zeros when no attendance records exist."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        summary = await service.get_student_attendance_summary(
            tenant["id"], fixtures["student_id"]
        )

        assert summary["total_days"] == 0
        assert summary["attendance_rate"] == 0


class TestSectionAttendanceSummary:
    """Tests for section-level attendance summary."""

    async def test_section_attendance_summary(
        self, app_session, admin_session
    ):
        """Section summary returns correct present/absent/late counts."""
        tenant = await create_test_tenant(admin_session)
        school_id = await seed_school(admin_session, tenant["id"])
        class_id, section_id = await seed_class_and_section(admin_session, tenant["id"])
        student_1 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        student_2 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        student_3 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=section_id,
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"student_id": str(student_1), "status": "present"},
                {"student_id": str(student_2), "status": "present"},
                {"student_id": str(student_3), "status": "absent"},
            ],
        )

        summary = await service.get_section_attendance_summary(
            tenant["id"], section_id, date(2026, 1, 15)
        )

        assert summary["total_students"] == 3
        assert summary["marked"] == 3
        assert summary["unmarked"] == 0
        assert summary["present"] == 2
        assert summary["absent"] == 1


# =========================
# Daily Report Tests
# =========================


class TestDailyAttendanceReport:
    """Tests for school-wide daily attendance report."""

    async def test_daily_report_returns_school_wide_summary(
        self, app_session, admin_session
    ):
        """Daily report aggregates attendance across all sections."""
        tenant = await create_test_tenant(admin_session)
        school_id = await seed_school(admin_session, tenant["id"])
        class_id, section_id = await seed_class_and_section(admin_session, tenant["id"])
        student_1 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        student_2 = await seed_student(admin_session, tenant["id"], school_id, section_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        await service.bulk_mark_student_attendance(
            tenant_id=tenant["id"],
            section_id=section_id,
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"student_id": str(student_1), "status": "present"},
                {"student_id": str(student_2), "status": "late"},
            ],
        )

        report = await service.get_daily_attendance_report(
            tenant["id"], date(2026, 1, 15)
        )

        assert report["date"] == "2026-01-15"
        assert report["total_students"] == 2
        assert report["marked"] == 2
        assert report["present"] == 1
        assert report["late"] == 1
        # attendance_rate = (present + late) / marked = 2/2 = 100%
        assert report["attendance_rate"] == 100.0

    async def test_daily_report_empty_when_no_attendance(
        self, app_session, admin_session
    ):
        """Daily report handles days with no attendance marked."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        report = await service.get_daily_attendance_report(
            tenant["id"], date(2026, 1, 15)
        )

        assert report["marked"] == 0
        assert report["attendance_rate"] == 0


# =========================
# Staff Attendance Tests
# =========================


class TestMarkStaffAttendance:
    """Tests for marking staff attendance."""

    async def test_mark_staff_present(self, app_session, admin_session):
        """Marking staff present creates a record with status=present."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=fixtures["staff_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
            check_in_time=time(7, 30),
        )

        assert record is not None
        assert record.status.value == "present"
        assert record.check_in_time == time(7, 30)
        assert record.date == date(2026, 1, 15)

    async def test_mark_staff_attendance_upsert(
        self, app_session, admin_session
    ):
        """Marking attendance again for the same date updates the record."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        # First mark: present
        record_1 = await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=fixtures["staff_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )
        record_1_id = record_1.id

        # Second mark same date: late
        record_2 = await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=fixtures["staff_id"],
            attendance_date=date(2026, 1, 15),
            status="late",
        )

        assert record_2.id == record_1_id
        assert record_2.status.value == "late"


class TestListStaffAttendance:
    """Tests for listing staff attendance."""

    async def test_list_staff_attendance_filtered_by_date_range(
        self, app_session, admin_session
    ):
        """List filters by date range correctly."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        # Mark 3 days
        for day in [date(2026, 1, 13), date(2026, 1, 14), date(2026, 1, 15)]:
            await service.mark_staff_attendance(
                tenant_id=tenant["id"],
                staff_id=fixtures["staff_id"],
                attendance_date=day,
                status="present",
            )

        # Filter to only 2 days
        records, total = await service.list_staff_attendance(
            tenant["id"],
            staff_id=fixtures["staff_id"],
            start_date=date(2026, 1, 14),
            end_date=date(2026, 1, 15),
        )

        assert total == 2
        assert len(records) == 2

    async def test_list_staff_attendance_filtered_by_status(
        self, app_session, admin_session
    ):
        """List filters by status correctly."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=fixtures["staff_id"],
            attendance_date=date(2026, 1, 13),
            status="present",
        )
        await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=fixtures["staff_id"],
            attendance_date=date(2026, 1, 14),
            status="absent",
        )

        records, total = await service.list_staff_attendance(
            tenant["id"],
            staff_id=fixtures["staff_id"],
            status="present",
        )

        assert total == 1
        assert records[0].status.value == "present"


class TestDeleteStaffAttendance:
    """Tests for soft-deleting staff attendance."""

    async def test_soft_delete_staff_attendance(
        self, app_session, admin_session
    ):
        """Deleted staff attendance is no longer returned."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        record = await service.mark_staff_attendance(
            tenant_id=tenant["id"],
            staff_id=fixtures["staff_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )

        deleted = await service.delete_staff_attendance(
            tenant["id"], record.id
        )
        assert deleted is True

        result = await service.get_staff_attendance(
            tenant["id"], fixtures["staff_id"], date(2026, 1, 15)
        )
        assert result is None


class TestStaffAttendanceSummary:
    """Tests for staff attendance summary statistics."""

    async def test_staff_attendance_summary_counts(
        self, app_session, admin_session
    ):
        """Summary returns correct counts and attendance rate."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_attendance_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        for day, status in [
            (date(2026, 1, 13), "present"),
            (date(2026, 1, 14), "present"),
            (date(2026, 1, 15), "absent"),
            (date(2026, 1, 16), "late"),
        ]:
            await service.mark_staff_attendance(
                tenant_id=tenant["id"],
                staff_id=fixtures["staff_id"],
                attendance_date=day,
                status=status,
            )

        summary = await service.get_staff_attendance_summary(
            tenant["id"], fixtures["staff_id"]
        )

        assert summary["total_days"] == 4
        assert summary["present"] == 2
        assert summary["absent"] == 1
        assert summary["late"] == 1
        # Attendance rate: (present + late) / total = 3/4 = 75%
        assert summary["attendance_rate"] == 75.0


class TestBulkMarkStaffAttendance:
    """Tests for bulk staff attendance marking."""

    async def test_bulk_mark_staff_attendance(
        self, app_session, admin_session
    ):
        """Bulk mark creates attendance for multiple staff members."""
        tenant = await create_test_tenant(admin_session)
        school_id = await seed_school(admin_session, tenant["id"])
        staff_1 = await seed_staff(admin_session, tenant["id"], school_id)
        staff_2 = await seed_staff(admin_session, tenant["id"], school_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AttendanceService(app_session)

        result = await service.bulk_mark_staff_attendance(
            tenant_id=tenant["id"],
            attendance_date=date(2026, 1, 15),
            attendance_records=[
                {"staff_id": str(staff_1), "status": "present"},
                {"staff_id": str(staff_2), "status": "absent"},
            ],
        )

        assert result["created"] == 2
        assert result["updated"] == 0
        assert result["failed"] == 0


# =========================
# Tenant Isolation
# =========================


class TestAttendanceTenantIsolation:
    """Attendance records must be isolated between tenants."""

    async def test_student_attendance_isolated(
        self, app_session, admin_session
    ):
        """Tenant A's student attendance is invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        fixtures_a = await seed_attendance_fixtures(admin_session, tenant_a["id"])
        await admin_session.commit()

        # Mark attendance as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AttendanceService(app_session)

        await service.mark_student_attendance(
            tenant_id=tenant_a["id"],
            student_id=fixtures_a["student_id"],
            section_id=fixtures_a["section_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )
        await app_session.flush()

        # Switch to Tenant B -- should see nothing
        await set_app_tenant_context(app_session, tenant_b["id"])

        records, total = await service.list_student_attendance(tenant_b["id"])
        assert total == 0, "Tenant B must not see Tenant A's student attendance"

    async def test_staff_attendance_isolated(
        self, app_session, admin_session
    ):
        """Tenant A's staff attendance is invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        fixtures_a = await seed_attendance_fixtures(admin_session, tenant_a["id"])
        await admin_session.commit()

        # Mark attendance as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AttendanceService(app_session)

        await service.mark_staff_attendance(
            tenant_id=tenant_a["id"],
            staff_id=fixtures_a["staff_id"],
            attendance_date=date(2026, 1, 15),
            status="present",
        )
        await app_session.flush()

        # Switch to Tenant B -- should see nothing
        await set_app_tenant_context(app_session, tenant_b["id"])

        records, total = await service.list_staff_attendance(tenant_b["id"])
        assert total == 0, "Tenant B must not see Tenant A's staff attendance"

    async def test_attendance_rls_raw_sql_isolation(
        self, app_session, admin_session
    ):
        """Raw SQL verification: RLS blocks cross-tenant attendance visibility."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        fixtures_a = await seed_attendance_fixtures(admin_session, tenant_a["id"])
        await admin_session.commit()

        # Seed attendance via admin (bypasses RLS)
        await admin_session.execute(
            text("""
                INSERT INTO student_attendance (
                    id, tenant_id, student_id, section_id,
                    date, status,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid), CAST(:sec_id AS uuid),
                    :date, 'present',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "sid": str(fixtures_a["student_id"]),
                "sec_id": str(fixtures_a["section_id"]),
                "date": date(2026, 1, 20),
            },
        )
        await admin_session.commit()

        # Tenant B queries raw SQL -- should see 0 rows
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM student_attendance")
        )
        count = result.scalar()
        assert count == 0, (
            f"Tenant B saw {count} student_attendance rows from Tenant A -- RLS BREACH"
        )

    async def test_staff_attendance_rls_raw_sql_isolation(
        self, app_session, admin_session
    ):
        """Raw SQL verification: RLS blocks cross-tenant staff attendance."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        fixtures_a = await seed_attendance_fixtures(admin_session, tenant_a["id"])
        await admin_session.commit()

        # Seed staff attendance via admin
        await admin_session.execute(
            text("""
                INSERT INTO staff_attendance (
                    id, tenant_id, staff_id,
                    date, status,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid),
                    :date, 'present',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "sid": str(fixtures_a["staff_id"]),
                "date": date(2026, 1, 20),
            },
        )
        await admin_session.commit()

        # Tenant B queries raw SQL -- should see 0 rows
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM staff_attendance")
        )
        count = result.scalar()
        assert count == 0, (
            f"Tenant B saw {count} staff_attendance rows from Tenant A -- RLS BREACH"
        )

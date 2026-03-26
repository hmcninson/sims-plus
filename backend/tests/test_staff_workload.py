"""
Tests for staff workload calculation (Phase 3 — Part A).

Covers: single staff workload, empty timetable, all-staff summary,
class teacher info, and subjects taught list.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_workload_prereqs(admin_session, tenant_id):
    """
    Seed school, class, section, two subjects, staff,
    staff_class_assignments (one as class teacher), and timetable entries.
    Returns dict with IDs.
    """
    school_id = uuid4()
    class_id = uuid4()
    section_id = uuid4()
    subj1_id = uuid4()
    subj2_id = uuid4()
    staff_id = uuid4()
    acad_year_id = uuid4()

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

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(acad_year_id), "tid": str(tenant_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Class 1', 'primary_1', 1,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), 'A',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)},
    )

    # Two subjects
    for sid, name, code in [(subj1_id, "Mathematics", "MATH"), (subj2_id, "English", "ENG")]:
        await admin_session.execute(
            text("""
                INSERT INTO subjects (id, tenant_id, name, code, category,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code, 'core',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(sid), "tid": str(tenant_id), "name": name, "code": code},
        )

    # Teaching staff
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
                :staff_num, 'Kwame', 'Asante',
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher',
                '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(staff_id), "tid": str(tenant_id), "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"staff-{uuid4().hex[:8]}@test.com",
        },
    )

    # Staff class assignment — class teacher for section A, teaches Math
    await admin_session.execute(
        text("""
            INSERT INTO staff_class_assignments (id, tenant_id, staff_id, section_id,
                is_class_teacher, subject_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:sec_id AS uuid),
                true, CAST(:subj_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant_id),
            "staff_id": str(staff_id), "sec_id": str(section_id),
            "subj_id": str(subj1_id),
        },
    )

    # Timetable entries: 3 Math periods + 2 English periods (Mon-Fri)
    for i, (day, period, subj_id) in enumerate([
        (0, 1, subj1_id), (0, 2, subj1_id), (1, 1, subj1_id),
        (2, 1, subj2_id), (3, 1, subj2_id),
    ]):
        await admin_session.execute(
            text("""
                INSERT INTO class_timetables (id, tenant_id, class_id, section_id,
                    academic_year_id, subject_id, teacher_id,
                    day_of_week, period_number, start_time, end_time,
                    is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:cid AS uuid), CAST(:sec_id AS uuid),
                    CAST(:year_id AS uuid), CAST(:subj_id AS uuid),
                    CAST(:teacher_id AS uuid),
                    :day, :period, '08:00', '08:45',
                    true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(uuid4()), "tid": str(tenant_id),
                "cid": str(class_id), "sec_id": str(section_id),
                "year_id": str(acad_year_id),
                "subj_id": str(subj_id), "teacher_id": str(staff_id),
                "day": day, "period": period,
            },
        )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "staff_id": staff_id,
        "class_id": class_id,
        "section_id": section_id,
        "subject1_id": subj1_id,
        "subject2_id": subj2_id,
        "academic_year_id": acad_year_id,
    }


# --- Tests ---


async def test_get_staff_workload_from_timetable(app_session, admin_session):
    """Staff with timetable entries returns correct periods/week count."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_workload_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff.workload_service import StaffWorkloadService

    svc = StaffWorkloadService(app_session)
    result = await svc.get_staff_workload(tenant["id"], prereqs["staff_id"])

    assert result["staff_id"] == prereqs["staff_id"]
    assert result["staff_name"] == "Kwame Asante"
    # Only 1 assignment (Math) with 3 timetable periods for that subject
    assert result["total_periods_per_week"] == 3
    assert result["total_sections"] >= 1


async def test_get_staff_workload_empty_timetable(app_session, admin_session):
    """Staff with no timetable entries returns 0 periods."""
    tenant = await create_test_tenant(admin_session)
    school_id = uuid4()
    staff_id = uuid4()

    # Seed minimal staff with no timetable
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant["id"]),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Ama', 'Solo',
                'female', :email, '0241234567',
                'teaching', 'active', 'Teacher', '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(staff_id), "tid": str(tenant["id"]), "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"staff-{uuid4().hex[:8]}@test.com",
        },
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff.workload_service import StaffWorkloadService

    svc = StaffWorkloadService(app_session)
    result = await svc.get_staff_workload(tenant["id"], staff_id)

    assert result["total_periods_per_week"] == 0
    assert result["total_sections"] == 0
    assert result["class_teacher_of"] is None
    assert result["subjects_taught"] == []


async def test_get_all_staff_workload_summary(app_session, admin_session):
    """Multiple teaching staff appear in workload summary with correct aggregation."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_workload_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff.workload_service import StaffWorkloadService

    svc = StaffWorkloadService(app_session)
    results = await svc.get_all_staff_workload(tenant["id"])

    # At least the staff we seeded should appear
    staff_ids = [r["staff_id"] for r in results]
    assert prereqs["staff_id"] in staff_ids

    # Find our staff in the summary
    our_staff = [r for r in results if r["staff_id"] == prereqs["staff_id"]][0]
    assert our_staff["total_periods_per_week"] == 5
    assert our_staff["total_sections"] >= 1


async def test_workload_includes_class_teacher_info(app_session, admin_session):
    """Staff marked as class teacher has class_teacher_of populated."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_workload_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff.workload_service import StaffWorkloadService

    svc = StaffWorkloadService(app_session)
    result = await svc.get_staff_workload(tenant["id"], prereqs["staff_id"])

    # Staff is class teacher for "Class 1 A"
    assert result["class_teacher_of"] is not None
    assert "Class 1" in result["class_teacher_of"]


async def test_workload_subjects_taught_list(app_session, admin_session):
    """Staff with multiple subject assignments shows correct subjects_taught list."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_workload_prereqs(admin_session, tenant["id"])

    # Create a second section so we can add a second assignment (unique is staff+section+tenant)
    section2_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), 'B',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section2_id), "tid": str(tenant["id"]),
         "cid": str(prereqs["class_id"])},
    )

    # Add second assignment for English subject on section B
    await admin_session.execute(
        text("""
            INSERT INTO staff_class_assignments (id, tenant_id, staff_id, section_id,
                is_class_teacher, subject_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:sec_id AS uuid),
                false, CAST(:subj_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "staff_id": str(prereqs["staff_id"]),
            "sec_id": str(section2_id),
            "subj_id": str(prereqs["subject2_id"]),
        },
    )

    # Add timetable entries for English in section B
    await admin_session.execute(
        text("""
            INSERT INTO class_timetables (id, tenant_id, class_id, section_id,
                academic_year_id, subject_id, teacher_id,
                day_of_week, period_number, start_time, end_time,
                is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), CAST(:sec_id AS uuid),
                CAST(:year_id AS uuid), CAST(:subj_id AS uuid),
                CAST(:teacher_id AS uuid),
                4, 1, '08:00', '08:45',
                true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "cid": str(prereqs["class_id"]), "sec_id": str(section2_id),
            "year_id": str(prereqs["academic_year_id"]),
            "subj_id": str(prereqs["subject2_id"]),
            "teacher_id": str(prereqs["staff_id"]),
        },
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff.workload_service import StaffWorkloadService

    svc = StaffWorkloadService(app_session)
    result = await svc.get_staff_workload(tenant["id"], prereqs["staff_id"])

    # Should include both Mathematics and English
    assert "English" in result["subjects_taught"]
    assert "Mathematics" in result["subjects_taught"]
    # 3 Math (section A) + 1 English (section B) = 4 total
    assert result["total_periods_per_week"] == 4
    assert result["total_sections"] == 2

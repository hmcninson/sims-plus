"""
Tests for Sprint 17-18 Teacher Context School Filtering.

Covers:
1. get_teacher_class_ids with school_id filter returns only that school's assignments
2. get_teacher_class_ids without school_id returns ALL assignments (backward compat)
3. get_teacher_subject_ids with school_id filter
4. get_teacher_subject_ids without school_id returns all subjects
"""

import pytest
from uuid import uuid4, UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.teacher.teacher_context import TeacherContextService

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)


async def _seed_teacher_across_schools(admin_session: AsyncSession) -> dict:
    """Seed a chain tenant with two schools and a teacher assigned to
    sections+subjects in both schools.

    Returns dict with all IDs needed for assertions.
    """
    tenant = await create_test_tenant(admin_session, subdomain=f"tctx-{uuid4().hex[:8]}")
    tid = str(tenant["id"])

    # Two schools
    school_a_id = str(uuid4())
    school_b_id = str(uuid4())
    for sid, name in [(school_a_id, "Campus Alpha"), (school_b_id, "Campus Beta")]:
        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, status, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic', 'active', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": sid, "tid": tid, "name": name, "slug": name.lower().replace(" ", "-")},
        )

    # One staff member (teacher)
    staff_id = str(uuid4())
    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id, staff_id, first_name, last_name,
                email, phone, gender, job_title, staff_type, status, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:school_id AS uuid),
                :staff_id, 'Teacher', 'One', :email, '0241234567', 'male',
                'Teacher', 'teaching', 'active', '2025-01-15',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": staff_id, "tid": tid, "school_id": school_a_id,
            "staff_id": f"STF-{uuid4().hex[:6]}", "email": f"teacher-{uuid4().hex[:8]}@test.com",
        },
    )

    # Classes (one per school)
    class_a_id = str(uuid4())
    class_b_id = str(uuid4())
    for cid, sid, name in [(class_a_id, school_a_id, "JHS 1 Alpha"), (class_b_id, school_b_id, "JHS 1 Beta")]:
        await admin_session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, school_id, name, sequence, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :name, 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": cid, "tid": tid, "sid": sid, "name": name},
        )

    # Sections (one per class)
    section_a_id = str(uuid4())
    section_b_id = str(uuid4())
    for sec_id, cls_id, sid in [(section_a_id, class_a_id, school_a_id), (section_b_id, class_b_id, school_b_id)]:
        await admin_session.execute(
            text("""
                INSERT INTO class_sections (id, tenant_id, school_id, class_id, name, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:cls AS uuid), 'A', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": sec_id, "tid": tid, "sid": sid, "cls": cls_id},
        )

    # StaffClassAssignment: teacher assigned to both sections, different schools
    for sec_id, sid in [(section_a_id, school_a_id), (section_b_id, school_b_id)]:
        await admin_session.execute(
            text("""
                INSERT INTO staff_class_assignments (id, tenant_id, school_id, staff_id, section_id,
                    is_class_teacher, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:staff AS uuid), CAST(:sec AS uuid), false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(uuid4()), "tid": tid, "sid": sid, "staff": staff_id, "sec": sec_id},
        )

    # Subjects (two distinct subjects)
    subject_a_id = str(uuid4())
    subject_b_id = str(uuid4())
    for sub_id, name, code in [(subject_a_id, "Mathematics", "MATH"), (subject_b_id, "English", "ENG")]:
        await admin_session.execute(
            text("""
                INSERT INTO subjects (id, tenant_id, name, code, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code, true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": sub_id, "tid": tid, "name": name, "code": code},
        )

    # ClassSubject: Math assigned to School A's class, English to School B's class
    # Both taught by our teacher
    for cs_cls, cs_sub, cs_school in [(class_a_id, subject_a_id, school_a_id), (class_b_id, subject_b_id, school_b_id)]:
        await admin_session.execute(
            text("""
                INSERT INTO class_subjects (id, tenant_id, school_id, class_id, subject_id,
                    teacher_id, is_compulsory, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:cls AS uuid), CAST(:sub AS uuid), CAST(:teacher AS uuid),
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(uuid4()), "tid": tid, "sid": cs_school,
                "cls": cs_cls, "sub": cs_sub, "teacher": staff_id,
            },
        )

    await admin_session.commit()

    return {
        "tenant_id": tenant["id"],
        "staff_id": UUID(staff_id),
        "school_a_id": UUID(school_a_id),
        "school_b_id": UUID(school_b_id),
        "section_a_id": UUID(section_a_id),
        "section_b_id": UUID(section_b_id),
        "subject_a_id": UUID(subject_a_id),
        "subject_b_id": UUID(subject_b_id),
    }


@pytest.fixture
async def teacher_data(admin_session: AsyncSession):
    return await _seed_teacher_across_schools(admin_session)


# ==========================
# get_teacher_class_ids tests
# ==========================

@pytest.mark.asyncio
async def test_get_teacher_class_ids_all_schools(
    app_session: AsyncSession,
    teacher_data: dict,
):
    """Without school_id filter, returns sections from ALL schools."""
    data = teacher_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = TeacherContextService(app_session)
    section_ids = await service.get_teacher_class_ids(
        staff_id=data["staff_id"],
        tenant_id=data["tenant_id"],
    )

    assert len(section_ids) == 2
    assert data["section_a_id"] in section_ids
    assert data["section_b_id"] in section_ids


@pytest.mark.asyncio
async def test_get_teacher_class_ids_filtered_to_school_a(
    app_session: AsyncSession,
    teacher_data: dict,
):
    """With school_id=school_a, returns only School A sections."""
    data = teacher_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = TeacherContextService(app_session)
    section_ids = await service.get_teacher_class_ids(
        staff_id=data["staff_id"],
        tenant_id=data["tenant_id"],
        school_id=data["school_a_id"],
    )

    assert len(section_ids) == 1
    assert data["section_a_id"] in section_ids
    assert data["section_b_id"] not in section_ids


@pytest.mark.asyncio
async def test_get_teacher_class_ids_filtered_to_school_b(
    app_session: AsyncSession,
    teacher_data: dict,
):
    """With school_id=school_b, returns only School B sections."""
    data = teacher_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = TeacherContextService(app_session)
    section_ids = await service.get_teacher_class_ids(
        staff_id=data["staff_id"],
        tenant_id=data["tenant_id"],
        school_id=data["school_b_id"],
    )

    assert len(section_ids) == 1
    assert data["section_b_id"] in section_ids


# ==========================
# get_teacher_subject_ids tests
# ==========================

@pytest.mark.asyncio
async def test_get_teacher_subject_ids_all_schools(
    app_session: AsyncSession,
    teacher_data: dict,
):
    """Without school_id filter, returns subjects from ALL schools."""
    data = teacher_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = TeacherContextService(app_session)
    subject_ids = await service.get_teacher_subject_ids(
        staff_id=data["staff_id"],
        tenant_id=data["tenant_id"],
    )

    assert len(subject_ids) == 2
    assert data["subject_a_id"] in subject_ids
    assert data["subject_b_id"] in subject_ids


@pytest.mark.asyncio
async def test_get_teacher_subject_ids_filtered_to_school_a(
    app_session: AsyncSession,
    teacher_data: dict,
):
    """With school_id=school_a, returns only School A subjects (Math)."""
    data = teacher_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = TeacherContextService(app_session)
    subject_ids = await service.get_teacher_subject_ids(
        staff_id=data["staff_id"],
        tenant_id=data["tenant_id"],
        school_id=data["school_a_id"],
    )

    assert len(subject_ids) == 1
    assert data["subject_a_id"] in subject_ids
    assert data["subject_b_id"] not in subject_ids


@pytest.mark.asyncio
async def test_get_teacher_subject_ids_filtered_to_school_b(
    app_session: AsyncSession,
    teacher_data: dict,
):
    """With school_id=school_b, returns only School B subjects (English)."""
    data = teacher_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = TeacherContextService(app_session)
    subject_ids = await service.get_teacher_subject_ids(
        staff_id=data["staff_id"],
        tenant_id=data["tenant_id"],
        school_id=data["school_b_id"],
    )

    assert len(subject_ids) == 1
    assert data["subject_b_id"] in subject_ids

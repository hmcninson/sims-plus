"""
SIMS Plus - Teacher Lesson Plan Service Tests

Tests for TeacherLessonService:
- Create lesson plan with all fields
- Authorization checks (unassigned class, unassigned subject)
- List filtered by teacher (only own plans returned)
- Update own plan (success) and other teacher's plan (blocked)
- Soft delete (sets deleted_at, does not hard delete)
- Status workflow (planned -> taught, planned -> cancelled)
- Cross-tenant isolation at the service level

Uses the two-engine test pattern:
- admin_session: superuser for seeding (bypasses RLS)
- app_session: sims_app_user for service calls (RLS enforced)
"""

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.teacher import TeacherLessonService, TeacherServiceError
from app.services.teacher.teacher_context import TeacherContextService
from tests.conftest import (
    admin_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# =====================================================================
# Helpers
# =====================================================================


async def seed_school(admin_session, tenant_id, suffix):
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, uses_boarding, uses_transport,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'LP', 'STF',
                true, false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"Lesson School {suffix}", "slug": f"lp-{suffix}"},
    )
    return school_id


async def seed_staff(admin_session, tenant_id, school_id, user_id=None, suffix=None):
    staff_id = uuid4()
    sfx = suffix or uuid4().hex[:6]
    await admin_session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title,
                employment_date, user_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, :fn, :ln,
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher',
                '2020-09-01', CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(staff_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "staff_num": f"STF-{sfx}",
            "fn": "Lesson",
            "ln": f"Teacher-{sfx}",
            "email": f"staff-{sfx}@test.com",
            "uid": str(user_id) if user_id else None,
        },
    )
    return staff_id


async def seed_class(admin_session, tenant_id, school_id, suffix=None):
    sfx = suffix or uuid4().hex[:6]
    class_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, sequence, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                :name, 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"Class-{sfx}"},
    )
    return class_id


async def seed_subject(admin_session, tenant_id, name="Mathematics"):
    subj_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO subjects (id, tenant_id, name, code,
                category, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                :name, :code, 'core', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(subj_id), "tid": str(tenant_id),
            "name": name, "code": name[:4].upper(),
        },
    )
    return subj_id


async def seed_class_subject(admin_session, tenant_id, class_id, subject_id, teacher_id=None):
    cs_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO class_subjects (id, tenant_id, class_id, subject_id, teacher_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                CAST(:sid AS uuid), CAST(:teacher AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(cs_id), "tid": str(tenant_id), "cid": str(class_id),
            "sid": str(subject_id), "teacher": str(teacher_id) if teacher_id else None,
        },
    )
    return cs_id


async def seed_section(admin_session, tenant_id, class_id, suffix=None):
    sfx = suffix or uuid4().hex[:6]
    section_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                :name, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id),
         "name": f"Sec-{sfx}"},
    )
    return section_id


async def seed_staff_class_assignment(admin_session, tenant_id, staff_id, section_id):
    assign_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO staff_class_assignments (id, tenant_id, staff_id, section_id,
                is_class_teacher, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stid AS uuid),
                CAST(:secid AS uuid), false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(assign_id), "tid": str(tenant_id),
            "stid": str(staff_id), "secid": str(section_id),
        },
    )
    return assign_id


# =====================================================================
# Fixture: lesson plan test environment
# =====================================================================


@pytest_asyncio.fixture
async def lesson_env(admin_session: AsyncSession, app_session: AsyncSession):
    """Seed a full environment for lesson plan tests.

    Creates:
    - Tenant with school
    - Teacher A assigned to Class + Subject (via class_subjects + staff_class_assignments)
    - Teacher B (different teacher, NOT assigned)
    - An unassigned class and unassigned subject for negative tests
    """
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"lp-{suffix}")
    tid = tenant["id"]

    school_id = await seed_school(admin_session, tid, suffix)

    # Teacher A (assigned)
    user_a = await create_test_user(admin_session, tid, email=f"lp-teacher-a-{suffix}@test.com")
    staff_a_id = await seed_staff(admin_session, tid, school_id, user_id=user_a["id"], suffix=f"lp-a-{suffix}")

    # Teacher B (not assigned to any class/subject)
    user_b = await create_test_user(admin_session, tid, email=f"lp-teacher-b-{suffix}@test.com")
    staff_b_id = await seed_staff(admin_session, tid, school_id, user_id=user_b["id"], suffix=f"lp-b-{suffix}")

    # Assigned class + subject (Teacher A teaches Math in Class-A)
    class_id = await seed_class(admin_session, tid, school_id, suffix=f"lpa-{suffix}")
    subject_id = await seed_subject(admin_session, tid, name="Mathematics")
    await seed_class_subject(admin_session, tid, class_id, subject_id, teacher_id=staff_a_id)
    section_id = await seed_section(admin_session, tid, class_id, suffix=f"lpa-{suffix}")
    await seed_staff_class_assignment(admin_session, tid, staff_a_id, section_id)

    # Unassigned class and subject (Teacher A is NOT assigned)
    unassigned_class_id = await seed_class(admin_session, tid, school_id, suffix=f"lpx-{suffix}")
    unassigned_subject_id = await seed_subject(admin_session, tid, name="Art")

    await admin_session.commit()
    await set_app_tenant_context(app_session, tid)

    yield {
        "tenant_id": tid,
        "school_id": school_id,
        "staff_a_id": staff_a_id,
        "staff_b_id": staff_b_id,
        "user_a_id": user_a["id"],
        "user_b_id": user_b["id"],
        "class_id": class_id,
        "subject_id": subject_id,
        "unassigned_class_id": unassigned_class_id,
        "unassigned_subject_id": unassigned_subject_id,
        "app_session": app_session,
    }

    # Cleanup
    await app_session.rollback()
    try:
        async with admin_session_maker() as cleanup:
            for tbl in [
                "lesson_plans", "report_comments",
                "class_subjects", "staff_class_assignments",
                "class_sections", "classes", "subjects",
                "staff", "users", "schools",
            ]:
                await cleanup.execute(
                    text(f"DELETE FROM {tbl} WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": str(tid)},
                )
            await cleanup.execute(
                text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
            await cleanup.commit()
    except Exception:
        pass


# =====================================================================
# Tests: create_lesson_plan
# =====================================================================


@pytest.mark.asyncio
async def test_create_lesson_plan_success(lesson_env):
    """Creating a lesson plan with all fields should succeed."""
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    data = {
        "class_id": env["class_id"],
        "subject_id": env["subject_id"],
        "date": date(2026, 2, 24),
        "period": 1,
        "topic": "Introduction to Algebra",
        "objectives": "Students will understand basic equations",
        "resources": "Whiteboard, textbook chapter 3",
        "activities": "Group exercises, pair work",
        "notes": "Focus on practical examples",
    }

    result = await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data=data,
    )

    assert result["id"] is not None
    assert result["topic"] == "Introduction to Algebra"
    assert result["objectives"] == "Students will understand basic equations"
    assert result["resources"] == "Whiteboard, textbook chapter 3"
    assert result["activities"] == "Group exercises, pair work"
    assert result["notes"] == "Focus on practical examples"
    assert result["status"] == "planned"
    assert result["date"] == date(2026, 2, 24)
    assert result["period"] == 1
    assert result["teacher_id"] == env["staff_a_id"]
    assert result["class_id"] == env["class_id"]
    assert result["subject_id"] == env["subject_id"]


@pytest.mark.asyncio
async def test_create_lesson_plan_unauthorized_class(lesson_env):
    """Creating a plan for an unassigned class should fail at the context layer.

    The TeacherContextService.verify_class_access check prevents teachers
    from creating plans for classes they are not assigned to.
    """
    env = lesson_env
    ctx_svc = TeacherContextService(env["app_session"])

    # Verify that class access check fails for unassigned class
    with pytest.raises(TeacherServiceError) as exc_info:
        await ctx_svc.verify_class_access(
            env["staff_a_id"], env["tenant_id"], env["unassigned_class_id"],
        )

    assert exc_info.value.code == "access_denied"


@pytest.mark.asyncio
async def test_create_lesson_plan_unauthorized_subject(lesson_env):
    """Creating a plan for an unassigned subject should fail at the context layer.

    The TeacherContextService.verify_subject_access check prevents teachers
    from creating plans for subjects they do not teach.
    """
    env = lesson_env
    ctx_svc = TeacherContextService(env["app_session"])

    with pytest.raises(TeacherServiceError) as exc_info:
        await ctx_svc.verify_subject_access(
            env["staff_a_id"], env["tenant_id"], env["unassigned_subject_id"],
        )

    assert exc_info.value.code == "access_denied"


# =====================================================================
# Tests: list_lesson_plans
# =====================================================================


@pytest.mark.asyncio
async def test_get_lesson_plans_filtered_by_teacher(lesson_env):
    """Listing lesson plans should only return the requesting teacher's plans."""
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    # Create plan for Teacher A
    await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data={
            "class_id": env["class_id"],
            "subject_id": env["subject_id"],
            "date": date(2026, 2, 25),
            "topic": "Teacher A's Plan",
        },
    )

    # Create plan for Teacher B via raw SQL (bypassing class assignment check)
    # because Teacher B is not assigned to this class, but the service only
    # filters on teacher_id for listing
    await env["app_session"].execute(
        text("""
            INSERT INTO lesson_plans (
                id, tenant_id, teacher_id, class_id, subject_id,
                date, topic, status, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:teacher AS uuid),
                CAST(:cid AS uuid), CAST(:sid AS uuid),
                '2026-02-25', 'Teacher B Plan', 'planned',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(uuid4()),
            "tid": str(env["tenant_id"]),
            "teacher": str(env["staff_b_id"]),
            "cid": str(env["class_id"]),
            "sid": str(env["subject_id"]),
        },
    )

    # Teacher A lists plans: should only see their own
    plans, total = await svc.list_lesson_plans(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
    )

    assert total >= 1
    # All returned plans should belong to Teacher A
    for plan in plans:
        assert plan["teacher_id"] == env["staff_a_id"]


# =====================================================================
# Tests: update_lesson_plan
# =====================================================================


@pytest.mark.asyncio
async def test_update_lesson_plan_own(lesson_env):
    """Teacher can update their own lesson plan."""
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    created = await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data={
            "class_id": env["class_id"],
            "subject_id": env["subject_id"],
            "date": date(2026, 2, 26),
            "topic": "Original Topic",
            "objectives": "Original objectives",
        },
    )

    updated = await svc.update_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        plan_id=created["id"],
        data={"topic": "Updated Topic", "objectives": "New objectives"},
    )

    assert updated["topic"] == "Updated Topic"
    assert updated["objectives"] == "New objectives"
    assert updated["id"] == created["id"]


@pytest.mark.asyncio
async def test_update_lesson_plan_other_teacher_blocked(lesson_env):
    """Teacher B cannot update Teacher A's lesson plan.

    The update query filters by teacher_id == staff_id, so a mismatch
    causes the plan to not be found (returns not_found, not forbidden).
    """
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    # Create a plan owned by Teacher A
    created = await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data={
            "class_id": env["class_id"],
            "subject_id": env["subject_id"],
            "date": date(2026, 2, 27),
            "topic": "Teacher A's Protected Plan",
        },
    )

    # Teacher B tries to update it
    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.update_lesson_plan(
            staff_id=env["staff_b_id"],
            tenant_id=env["tenant_id"],
            plan_id=created["id"],
            data={"topic": "Hijacked by Teacher B"},
        )

    assert exc_info.value.code == "not_found"


# =====================================================================
# Tests: delete_lesson_plan
# =====================================================================


@pytest.mark.asyncio
async def test_delete_lesson_plan_soft_deletes(lesson_env):
    """Deleting a lesson plan should set deleted_at, not hard delete."""
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    created = await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data={
            "class_id": env["class_id"],
            "subject_id": env["subject_id"],
            "date": date(2026, 2, 28),
            "topic": "To Be Soft-Deleted",
        },
    )
    plan_id = created["id"]

    # Delete it
    await svc.delete_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        plan_id=plan_id,
    )

    # The plan should NOT be findable via the service (filters out deleted_at)
    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.get_lesson_plan(
            staff_id=env["staff_a_id"],
            tenant_id=env["tenant_id"],
            plan_id=plan_id,
        )
    assert exc_info.value.code == "not_found"

    # But the row should still exist in the database (soft delete, not hard)
    result = await env["app_session"].execute(
        text("""
            SELECT deleted_at FROM lesson_plans
            WHERE id = CAST(:id AS uuid)
            AND tenant_id = CAST(:tid AS uuid)
        """),
        {"id": str(plan_id), "tid": str(env["tenant_id"])},
    )
    row = result.fetchone()
    assert row is not None, "Row should still exist in the database (soft delete)"
    assert row[0] is not None, "deleted_at should be set"


# =====================================================================
# Tests: status workflow
# =====================================================================


@pytest.mark.asyncio
async def test_status_workflow_planned_to_taught(lesson_env):
    """Status should change from 'planned' to 'taught'."""
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    created = await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data={
            "class_id": env["class_id"],
            "subject_id": env["subject_id"],
            "date": date(2026, 3, 1),
            "topic": "Lesson to Teach",
        },
    )
    assert created["status"] == "planned"

    updated = await svc.update_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        plan_id=created["id"],
        data={"status": "taught"},
    )

    assert updated["status"] == "taught"


@pytest.mark.asyncio
async def test_status_workflow_planned_to_cancelled(lesson_env):
    """Status should change from 'planned' to 'cancelled'."""
    env = lesson_env
    svc = TeacherLessonService(env["app_session"])

    created = await svc.create_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        data={
            "class_id": env["class_id"],
            "subject_id": env["subject_id"],
            "date": date(2026, 3, 2),
            "topic": "Lesson to Cancel",
        },
    )
    assert created["status"] == "planned"

    updated = await svc.update_lesson_plan(
        staff_id=env["staff_a_id"],
        tenant_id=env["tenant_id"],
        plan_id=created["id"],
        data={"status": "cancelled"},
    )

    assert updated["status"] == "cancelled"


# =====================================================================
# Tests: cross-tenant isolation
# =====================================================================


@pytest.mark.asyncio
async def test_cross_tenant_lesson_plan_blocked(
    admin_session: AsyncSession, app_session: AsyncSession,
):
    """Lesson plans from Tenant A should NOT be accessible from Tenant B.

    RLS and defense-in-depth teacher_id + tenant_id filtering prevent
    cross-tenant reads.
    """
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"lpta-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"lptb-{suffix}")

    # Seed data in Tenant A
    school_a = await seed_school(admin_session, tenant_a["id"], f"lxa-{suffix}")
    user_a = await create_test_user(admin_session, tenant_a["id"])
    staff_a = await seed_staff(admin_session, tenant_a["id"], school_a,
                                user_id=user_a["id"], suffix=f"lxa-{suffix}")
    class_a = await seed_class(admin_session, tenant_a["id"], school_a, suffix=f"lxa-{suffix}")
    subject_a = await seed_subject(admin_session, tenant_a["id"], name="Science")
    await seed_class_subject(admin_session, tenant_a["id"], class_a, subject_a, teacher_id=staff_a)

    await admin_session.commit()

    try:
        # Create plan in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc_a = TeacherLessonService(app_session)
        created = await svc_a.create_lesson_plan(
            staff_id=staff_a,
            tenant_id=tenant_a["id"],
            data={
                "class_id": class_a,
                "subject_id": subject_a,
                "date": date(2026, 3, 3),
                "topic": "Tenant A Lesson",
            },
        )
        plan_id = created["id"]

        # Switch to Tenant B and try to access the plan
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = TeacherLessonService(app_session)

        with pytest.raises(TeacherServiceError) as exc_info:
            await svc_b.get_lesson_plan(
                staff_id=staff_a,
                tenant_id=tenant_b["id"],
                plan_id=plan_id,
            )

        assert exc_info.value.code == "not_found"
    finally:
        await app_session.rollback()
        try:
            async with admin_session_maker() as cleanup:
                for tid in [str(tenant_a["id"]), str(tenant_b["id"])]:
                    for tbl in [
                        "lesson_plans", "class_subjects", "class_sections",
                        "classes", "subjects", "staff", "users", "schools",
                    ]:
                        await cleanup.execute(
                            text(f"DELETE FROM {tbl} WHERE tenant_id = CAST(:tid AS uuid)"),
                            {"tid": tid},
                        )
                    await cleanup.execute(
                        text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                        {"tid": tid},
                    )
                await cleanup.commit()
        except Exception:
            pass

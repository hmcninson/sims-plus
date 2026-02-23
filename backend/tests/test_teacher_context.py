"""
SIMS Plus - Teacher Context Service Tests

Tests for TeacherContextService:
- User-to-staff resolution
- Class and subject access verification
- Academic year/term retrieval
- Cross-tenant isolation at the context layer
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.teacher import TeacherContextService, TeacherServiceError
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
                'basic', 'active', 'TC', 'STF',
                true, false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id), "name": f"Context School {suffix}", "slug": f"ctx-{suffix}"},
    )
    return school_id


async def seed_staff(admin_session, tenant_id, school_id, user_id=None, suffix=None):
    """Create a staff record linked to user_id (if provided)."""
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
            "fn": "Kofi",
            "ln": "Mensah",
            "email": f"staff-{sfx}@test.com",
            "uid": str(user_id) if user_id else None,
        },
    )
    return staff_id


async def seed_academic_year(admin_session, tenant_id, is_current=True):
    ay_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                '2025-09-01', '2026-07-31', 'active', :cur, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ay_id), "tid": str(tenant_id), "cur": is_current},
    )
    return ay_id


async def seed_term(admin_session, tenant_id, ay_id, is_current=True):
    term_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO terms (id, tenant_id, academic_year_id, name,
                start_date, end_date, status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid), 'Term 1',
                '2025-09-01', '2025-12-15', 'active', :cur, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(term_id), "tid": str(tenant_id), "ayid": str(ay_id), "cur": is_current},
    )
    return term_id


async def seed_class_and_section(admin_session, tenant_id, school_id):
    class_id = uuid4()
    section_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, sequence, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                'Primary 6', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id)},
    )
    await admin_session.execute(
        text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                'Section A', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)},
    )
    return class_id, section_id


async def seed_staff_class_assignment(admin_session, tenant_id, staff_id, section_id, is_class_teacher=False):
    assign_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO staff_class_assignments (id, tenant_id, staff_id, section_id,
                is_class_teacher, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stid AS uuid),
                CAST(:secid AS uuid), :ict, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(assign_id), "tid": str(tenant_id),
            "stid": str(staff_id), "secid": str(section_id), "ict": is_class_teacher,
        },
    )
    return assign_id


async def seed_subject(admin_session, tenant_id, school_id, name="Mathematics"):
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
                CAST(:sid AS uuid), CAST(:teacher AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(cs_id), "tid": str(tenant_id), "cid": str(class_id),
            "sid": str(subject_id), "teacher": str(teacher_id) if teacher_id else None,
        },
    )
    return cs_id


async def seed_timetable_entry(admin_session, tenant_id, class_id, section_id, ay_id,
                                teacher_id, subject_id=None, day=0, period=1):
    tt_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO class_timetables (id, tenant_id, class_id, section_id,
                academic_year_id, teacher_id, subject_id,
                day_of_week, period_number, start_time, end_time, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                CAST(:secid AS uuid), CAST(:ayid AS uuid), CAST(:teacher AS uuid),
                CAST(:subj AS uuid), :day, :period, '08:00', '08:45', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(tt_id), "tid": str(tenant_id), "cid": str(class_id),
            "secid": str(section_id), "ayid": str(ay_id),
            "teacher": str(teacher_id), "subj": str(subject_id) if subject_id else None,
            "day": day, "period": period,
        },
    )
    return tt_id


# =====================================================================
# Fixture: full teacher context environment
# =====================================================================


@pytest_asyncio.fixture
async def ctx_env(admin_session: AsyncSession, app_session: AsyncSession):
    """Seed a complete teacher context: tenant, school, user, staff, class, section, subject."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"ctx-{suffix}")
    tid = tenant["id"]

    school_id = await seed_school(admin_session, tid, suffix)
    user = await create_test_user(admin_session, tid, email=f"ctx-teacher-{suffix}@test.com")
    staff_id = await seed_staff(admin_session, tid, school_id, user_id=user["id"], suffix=f"ctx-{suffix}")

    class_id, section_id = await seed_class_and_section(admin_session, tid, school_id)
    await seed_staff_class_assignment(admin_session, tid, staff_id, section_id, is_class_teacher=True)

    subject_id = await seed_subject(admin_session, tid, school_id)
    await seed_class_subject(admin_session, tid, class_id, subject_id, teacher_id=staff_id)

    ay_id = await seed_academic_year(admin_session, tid)
    term_id = await seed_term(admin_session, tid, ay_id)

    await admin_session.commit()
    await set_app_tenant_context(app_session, tid)

    yield {
        "tenant_id": tid,
        "school_id": school_id,
        "user_id": user["id"],
        "staff_id": staff_id,
        "class_id": class_id,
        "section_id": section_id,
        "subject_id": subject_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "app_session": app_session,
    }

    await app_session.rollback()
    try:
        async with admin_session_maker() as cleanup:
            for tbl in [
                "lesson_plans", "report_comments",
                "class_timetables", "staff_class_assignments",
                "class_subjects", "class_sections", "classes",
                "subjects", "terms", "academic_years",
                "staff", "students", "users", "schools",
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
# Tests: get_staff_for_user
# =====================================================================


@pytest.mark.asyncio
async def test_get_staff_for_user_success(ctx_env):
    """Valid teacher user should return staff record."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    staff = await svc.get_staff_for_user(env["user_id"], env["tenant_id"])
    assert staff.id == env["staff_id"]


@pytest.mark.asyncio
async def test_get_staff_for_user_not_found(ctx_env):
    """Non-teacher user (no staff record) should raise not_a_teacher."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.get_staff_for_user(uuid4(), env["tenant_id"])
    assert exc_info.value.code == "not_a_teacher"


@pytest.mark.asyncio
async def test_get_staff_for_user_wrong_tenant(
    admin_session: AsyncSession, app_session: AsyncSession
):
    """Cross-tenant staff lookup should fail (RLS blocks access)."""
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"ctxa-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"ctxb-{suffix}")
    school_a = await seed_school(admin_session, tenant_a["id"], f"a-{suffix}")
    user_a = await create_test_user(admin_session, tenant_a["id"])
    await seed_staff(admin_session, tenant_a["id"], school_a, user_id=user_a["id"], suffix=f"xa-{suffix}")
    await admin_session.commit()

    try:
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc = TeacherContextService(app_session)
        with pytest.raises(TeacherServiceError) as exc_info:
            await svc.get_staff_for_user(user_a["id"], tenant_b["id"])
        assert exc_info.value.code == "not_a_teacher"
    finally:
        await app_session.rollback()
        try:
            async with admin_session_maker() as cleanup:
                for tid in [str(tenant_a["id"]), str(tenant_b["id"])]:
                    for tbl in ["staff", "users", "schools"]:
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


# =====================================================================
# Tests: verify_class_access
# =====================================================================


@pytest.mark.asyncio
async def test_verify_class_access_assigned(ctx_env):
    """Teacher assigned to class via StaffClassAssignment should pass."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    # Should NOT raise
    await svc.verify_class_access(env["staff_id"], env["tenant_id"], env["class_id"])


@pytest.mark.asyncio
async def test_verify_class_access_not_assigned(ctx_env):
    """Teacher NOT assigned to a different class should raise access_denied."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.verify_class_access(env["staff_id"], env["tenant_id"], uuid4())
    assert exc_info.value.code == "access_denied"


@pytest.mark.asyncio
async def test_verify_class_access_via_timetable(
    admin_session: AsyncSession, app_session: AsyncSession
):
    """Teacher on timetable (but no StaffClassAssignment) should pass class access check."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"ttchk-{suffix}")
    tid = tenant["id"]
    school_id = await seed_school(admin_session, tid, suffix)
    user = await create_test_user(admin_session, tid)
    staff_id = await seed_staff(admin_session, tid, school_id, user_id=user["id"], suffix=f"tt-{suffix}")
    class_id, section_id = await seed_class_and_section(admin_session, tid, school_id)
    ay_id = await seed_academic_year(admin_session, tid)
    # No StaffClassAssignment -- only timetable entry
    await seed_timetable_entry(admin_session, tid, class_id, section_id, ay_id, staff_id)
    await admin_session.commit()

    try:
        await set_app_tenant_context(app_session, tid)
        svc = TeacherContextService(app_session)
        await svc.verify_class_access(staff_id, tid, class_id)  # Should NOT raise
    finally:
        await app_session.rollback()
        try:
            async with admin_session_maker() as cleanup:
                for tbl in [
                    "class_timetables", "class_sections", "classes",
                    "academic_years", "staff", "users", "schools",
                ]:
                    await cleanup.execute(
                        text(f"DELETE FROM {tbl} WHERE tenant_id = CAST(:tid AS uuid)"),
                        {"tid": str(tid)},
                    )
                await cleanup.execute(text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"), {"tid": str(tid)})
                await cleanup.commit()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_verify_class_access_with_section_id(ctx_env):
    """Section-level access verification should pass for assigned section."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    await svc.verify_class_access(
        env["staff_id"], env["tenant_id"], env["class_id"], section_id=env["section_id"]
    )


# =====================================================================
# Tests: verify_subject_access
# =====================================================================


@pytest.mark.asyncio
async def test_verify_subject_access_assigned(ctx_env):
    """Teacher assigned to subject via ClassSubject should pass."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    await svc.verify_subject_access(env["staff_id"], env["tenant_id"], env["subject_id"])


@pytest.mark.asyncio
async def test_verify_subject_access_not_assigned(ctx_env):
    """Teacher NOT assigned to subject should raise access_denied."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.verify_subject_access(env["staff_id"], env["tenant_id"], uuid4())
    assert exc_info.value.code == "access_denied"


# =====================================================================
# Tests: academic year / term
# =====================================================================


@pytest.mark.asyncio
async def test_get_current_academic_year(ctx_env):
    """Should return the active academic year with is_current=True."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    ay = await svc.get_current_academic_year(env["tenant_id"])
    assert ay.id == env["ay_id"]
    assert ay.is_current is True


@pytest.mark.asyncio
async def test_get_current_academic_year_none(
    admin_session: AsyncSession, app_session: AsyncSession
):
    """Should raise no_academic_year when none is set as current."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"noay-{suffix}")
    tid = tenant["id"]
    await admin_session.commit()

    try:
        await set_app_tenant_context(app_session, tid)
        svc = TeacherContextService(app_session)
        with pytest.raises(TeacherServiceError) as exc_info:
            await svc.get_current_academic_year(tid)
        assert exc_info.value.code == "no_academic_year"
    finally:
        await app_session.rollback()
        try:
            async with admin_session_maker() as cleanup:
                await cleanup.execute(text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"), {"tid": str(tid)})
                await cleanup.commit()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_current_term(ctx_env):
    """Should return the active term with is_current=True."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    term = await svc.get_current_term(env["tenant_id"], env["ay_id"])
    assert term.id == env["term_id"]


@pytest.mark.asyncio
async def test_get_current_term_none(ctx_env):
    """Should raise no_current_term when no term is set as current for a bogus AY."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.get_current_term(env["tenant_id"], uuid4())
    assert exc_info.value.code == "no_current_term"


# =====================================================================
# Tests: is_class_teacher_for_section
# =====================================================================


@pytest.mark.asyncio
async def test_is_class_teacher_true(ctx_env):
    """Should return True for a section where the staff is class teacher."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    result = await svc.is_class_teacher_for_section(
        env["staff_id"], env["tenant_id"], env["section_id"]
    )
    assert result is True


@pytest.mark.asyncio
async def test_is_class_teacher_false(ctx_env):
    """Should return False for a section the staff is NOT class teacher of."""
    env = ctx_env
    svc = TeacherContextService(env["app_session"])
    result = await svc.is_class_teacher_for_section(
        env["staff_id"], env["tenant_id"], uuid4()
    )
    assert result is False

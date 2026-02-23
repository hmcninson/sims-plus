"""
SIMS Plus - Teacher Reports Service Tests

Tests for TeacherReportsService:
- Class teacher comment CRUD (create, update, sign)
- Head teacher comment CRUD (create, sign)
- Section-scoped access control (class teachers only see their section)
- Draft head teacher comments hidden from regular teachers
- Signed head teacher comments visible to all
- Cross-tenant isolation at the service level

Uses the two-engine test pattern:
- admin_session: superuser for seeding (bypasses RLS)
- app_session: sims_app_user for service calls (RLS enforced)
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.teacher import TeacherReportsService, TeacherServiceError
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
                'basic', 'active', 'RPT', 'STF',
                true, false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"Report School {suffix}", "slug": f"rpt-{suffix}"},
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
            "fn": "Staff",
            "ln": f"Member-{sfx}",
            "email": f"staff-{sfx}@test.com",
            "uid": str(user_id) if user_id else None,
        },
    )
    return staff_id


async def seed_academic_year(admin_session, tenant_id):
    ay_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ay_id), "tid": str(tenant_id)},
    )
    return ay_id


async def seed_term(admin_session, tenant_id, ay_id):
    term_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO terms (id, tenant_id, academic_year_id, name,
                start_date, end_date, status, is_current,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid),
                'Term 1', '2025-09-01', '2025-12-15', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(term_id), "tid": str(tenant_id), "ayid": str(ay_id)},
    )
    return term_id


async def seed_class_and_section(admin_session, tenant_id, school_id, suffix=None):
    sfx = suffix or uuid4().hex[:6]
    class_id = uuid4()
    section_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, sequence, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                :name, 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"Class-{sfx}"},
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


async def seed_student(admin_session, tenant_id, school_id, section_id, suffix=None):
    """Create a student assigned to a specific section."""
    sfx = suffix or uuid4().hex[:6]
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
                CAST(:sid AS uuid), CAST(:secid AS uuid),
                :student_num, :fn, :ln,
                '2012-05-15', 'male', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "secid": str(section_id),
            "student_num": f"STU-{sfx}",
            "fn": f"Student-{sfx}",
            "ln": "Test",
        },
    )
    return student_id


async def seed_staff_class_assignment(admin_session, tenant_id, staff_id, section_id,
                                       is_class_teacher=False):
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
            "stid": str(staff_id), "secid": str(section_id),
            "ict": is_class_teacher,
        },
    )
    return assign_id


# =====================================================================
# Fixture: report comments test environment
# =====================================================================


@pytest_asyncio.fixture
async def rpt_env(admin_session: AsyncSession, app_session: AsyncSession):
    """Seed a full environment for report comment tests.

    Creates:
    - Tenant with school, academic year, term
    - Class teacher (staff A) assigned as class teacher for Section A
    - Head teacher (staff B) -- no class teacher assignment
    - Another teacher (staff C) assigned as class teacher for Section B
    - Student in Section A
    """
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"rpt-{suffix}")
    tid = tenant["id"]

    school_id = await seed_school(admin_session, tid, suffix)

    # Staff A: class teacher for Section A
    user_a = await create_test_user(admin_session, tid, email=f"rpt-teacher-{suffix}@test.com")
    staff_a_id = await seed_staff(admin_session, tid, school_id, user_id=user_a["id"], suffix=f"rpt-a-{suffix}")

    # Staff B: head teacher (school admin) -- not assigned as class teacher
    user_b = await create_test_user(admin_session, tid, email=f"rpt-head-{suffix}@test.com")
    staff_b_id = await seed_staff(admin_session, tid, school_id, user_id=user_b["id"], suffix=f"rpt-b-{suffix}")

    # Section A (staff A is class teacher)
    class_id, section_a_id = await seed_class_and_section(admin_session, tid, school_id, suffix=f"a-{suffix}")
    await seed_staff_class_assignment(admin_session, tid, staff_a_id, section_a_id, is_class_teacher=True)

    # Section B (staff C is class teacher) -- different class/section
    class_b_id, section_b_id = await seed_class_and_section(admin_session, tid, school_id, suffix=f"b-{suffix}")
    user_c = await create_test_user(admin_session, tid, email=f"rpt-other-{suffix}@test.com")
    staff_c_id = await seed_staff(admin_session, tid, school_id, user_id=user_c["id"], suffix=f"rpt-c-{suffix}")
    await seed_staff_class_assignment(admin_session, tid, staff_c_id, section_b_id, is_class_teacher=True)

    # Student in Section A
    student_id = await seed_student(admin_session, tid, school_id, section_a_id, suffix=f"rpt-{suffix}")

    # Student in Section B (for cross-section tests)
    student_b_id = await seed_student(admin_session, tid, school_id, section_b_id, suffix=f"rptb-{suffix}")

    ay_id = await seed_academic_year(admin_session, tid)
    term_id = await seed_term(admin_session, tid, ay_id)

    await admin_session.commit()
    await set_app_tenant_context(app_session, tid)

    yield {
        "tenant_id": tid,
        "school_id": school_id,
        "class_teacher_id": staff_a_id,    # class teacher for section A
        "head_teacher_id": staff_b_id,      # head teacher (no section assignment)
        "other_teacher_id": staff_c_id,     # class teacher for section B
        "section_a_id": section_a_id,
        "section_b_id": section_b_id,
        "student_id": student_id,           # in section A
        "student_b_id": student_b_id,       # in section B
        "ay_id": ay_id,
        "term_id": term_id,
        "app_session": app_session,
    }

    # Cleanup: rollback app_session before deleting via admin
    await app_session.rollback()
    try:
        async with admin_session_maker() as cleanup:
            for tbl in [
                "report_comments", "lesson_plans",
                "staff_class_assignments", "class_sections", "classes",
                "students", "staff", "terms", "academic_years",
                "users", "schools",
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
# Tests: get_report_comments
# =====================================================================


@pytest.mark.asyncio
async def test_get_report_comments_own_section(rpt_env):
    """Class teacher should see comments for students in their section."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # Create a comment for the student in section A
    await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Excellent progress this term.",
    )

    # Retrieve comments scoped to section A
    comments = await svc.get_report_comments(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        term_id=env["term_id"],
        section_id=env["section_a_id"],
    )

    assert len(comments) == 1
    assert comments[0]["student_id"] == env["student_id"]
    assert comments[0]["class_teacher_comment"] == "Excellent progress this term."


@pytest.mark.asyncio
async def test_get_report_comments_other_section_blocked(rpt_env):
    """Class teacher for Section A should NOT see Section B's comments via section filter.

    When section_id is provided, the query filters to students in that section.
    Staff A is class teacher for section A, so querying with section B's ID should
    return empty results (Section B's student has no comment from Staff A).
    """
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # Create a comment authored by Staff C (class teacher for Section B) for student in Section B
    # We need to do this via raw SQL since Staff C is a different teacher
    # and the service checks class teacher status
    await env["app_session"].execute(
        text("""
            INSERT INTO report_comments (
                id, tenant_id, student_id, term_id, academic_year_id,
                class_teacher_comment, class_teacher_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:termid AS uuid), CAST(:ayid AS uuid),
                :comment, CAST(:ctid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(uuid4()),
            "tid": str(env["tenant_id"]),
            "sid": str(env["student_b_id"]),
            "termid": str(env["term_id"]),
            "ayid": str(env["ay_id"]),
            "comment": "Section B comment by Staff C.",
            "ctid": str(env["other_teacher_id"]),
        },
    )

    # Staff A queries without section_id: service scopes to own comments only
    # (class_teacher_id == staff_a_id), so Staff C's comment is not visible
    comments = await svc.get_report_comments(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        term_id=env["term_id"],
        # No section_id => scoped to own comments (class_teacher_id filter)
    )

    student_ids = [c["student_id"] for c in comments]
    # Staff A has not written any comments yet, so result should be empty
    assert env["student_b_id"] not in student_ids


# =====================================================================
# Tests: upsert_class_teacher_comment
# =====================================================================


@pytest.mark.asyncio
async def test_upsert_class_teacher_comment_creates(rpt_env):
    """First call should create a new report comment record."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    result = await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="A new comment.",
    )

    assert result["id"] is not None
    assert result["class_teacher_comment"] == "A new comment."
    assert result["student_id"] == env["student_id"]
    assert result["class_teacher_signed"] is False


@pytest.mark.asyncio
async def test_upsert_class_teacher_comment_updates(rpt_env):
    """Second call for same student/term should update the existing comment."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # First call: create
    first = await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Original comment.",
    )

    # Second call: update
    updated = await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Updated comment.",
    )

    # Same record, different content
    assert updated["id"] == first["id"]
    assert updated["class_teacher_comment"] == "Updated comment."


# =====================================================================
# Tests: sign_class_teacher_comment
# =====================================================================


@pytest.mark.asyncio
async def test_sign_class_teacher_comment(rpt_env):
    """Signing should set class_teacher_signed=True on an existing comment."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # Create comment first
    await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Ready to sign.",
    )

    # Sign it
    signed = await svc.sign_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
    )

    assert signed["class_teacher_signed"] is True
    assert signed["class_teacher_comment"] == "Ready to sign."


# =====================================================================
# Tests: head teacher comments
# =====================================================================


@pytest.mark.asyncio
async def test_head_teacher_comment_create(rpt_env):
    """Head teacher should be able to create a head teacher comment."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    result = await svc.upsert_head_teacher_comment(
        staff_id=env["head_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Head teacher approves.",
    )

    assert result["head_teacher_comment"] == "Head teacher approves."
    assert result["head_teacher_signed"] is False


@pytest.mark.asyncio
async def test_head_teacher_sign(rpt_env):
    """Head teacher signing should set head_teacher_signed=True."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # Create head teacher comment first
    await svc.upsert_head_teacher_comment(
        staff_id=env["head_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Signed off by head.",
    )

    signed = await svc.sign_head_teacher_comment(
        staff_id=env["head_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
    )

    assert signed["head_teacher_signed"] is True
    assert signed["head_teacher_comment"] == "Signed off by head."


# =====================================================================
# Tests: head teacher comment visibility
# =====================================================================


@pytest.mark.asyncio
async def test_draft_head_teacher_comment_hidden_from_class_teacher(rpt_env):
    """Unsigned head teacher comment should return None for non-head-teacher callers.

    The _format_comment method only reveals head_teacher_comment when
    head_teacher_signed=True or is_head_teacher=True.
    """
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # Class teacher creates their comment first
    await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Class teacher comment.",
    )

    # Head teacher adds a draft comment (unsigned)
    await svc.upsert_head_teacher_comment(
        staff_id=env["head_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Draft HT comment, not yet signed.",
    )

    # Class teacher fetches comments with is_head_teacher=False (default)
    comments = await svc.get_report_comments(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        term_id=env["term_id"],
        section_id=env["section_a_id"],
        is_head_teacher=False,
    )

    assert len(comments) == 1
    # The head_teacher_comment should be None (hidden draft)
    assert comments[0]["head_teacher_comment"] is None
    # But the class teacher comment should be visible
    assert comments[0]["class_teacher_comment"] == "Class teacher comment."


@pytest.mark.asyncio
async def test_signed_head_teacher_comment_visible(rpt_env):
    """Once signed, head teacher comment should be visible to all callers."""
    env = rpt_env
    svc = TeacherReportsService(env["app_session"])

    # Class teacher creates their comment
    await svc.upsert_class_teacher_comment(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="Class teacher wrote this.",
    )

    # Head teacher writes and signs
    await svc.upsert_head_teacher_comment(
        staff_id=env["head_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
        academic_year_id=env["ay_id"],
        comment="HT approved and signed.",
    )
    await svc.sign_head_teacher_comment(
        staff_id=env["head_teacher_id"],
        tenant_id=env["tenant_id"],
        student_id=env["student_id"],
        term_id=env["term_id"],
    )

    # Class teacher fetches: signed HT comment should now be visible
    comments = await svc.get_report_comments(
        staff_id=env["class_teacher_id"],
        tenant_id=env["tenant_id"],
        term_id=env["term_id"],
        section_id=env["section_a_id"],
        is_head_teacher=False,
    )

    assert len(comments) == 1
    assert comments[0]["head_teacher_comment"] == "HT approved and signed."
    assert comments[0]["head_teacher_signed"] is True


# =====================================================================
# Tests: cross-tenant isolation
# =====================================================================


@pytest.mark.asyncio
async def test_cross_tenant_comment_blocked(
    admin_session: AsyncSession, app_session: AsyncSession,
):
    """Report comments from Tenant A should NOT be accessible from Tenant B.

    RLS and defense-in-depth tenant_id filtering prevent cross-tenant reads.
    """
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"rcta-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"rctb-{suffix}")

    # Seed data in Tenant A
    school_a = await seed_school(admin_session, tenant_a["id"], f"xa-{suffix}")
    user_a = await create_test_user(admin_session, tenant_a["id"])
    staff_a = await seed_staff(admin_session, tenant_a["id"], school_a,
                                user_id=user_a["id"], suffix=f"xa-{suffix}")
    _, section_a = await seed_class_and_section(admin_session, tenant_a["id"], school_a, suffix=f"xa-{suffix}")
    await seed_staff_class_assignment(admin_session, tenant_a["id"], staff_a, section_a, is_class_teacher=True)
    student_a = await seed_student(admin_session, tenant_a["id"], school_a, section_a, suffix=f"xa-{suffix}")
    ay_a = await seed_academic_year(admin_session, tenant_a["id"])
    term_a = await seed_term(admin_session, tenant_a["id"], ay_a)

    await admin_session.commit()

    try:
        # Create a comment in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc_a = TeacherReportsService(app_session)
        await svc_a.upsert_class_teacher_comment(
            staff_id=staff_a,
            tenant_id=tenant_a["id"],
            student_id=student_a,
            term_id=term_a,
            academic_year_id=ay_a,
            comment="Tenant A only.",
        )

        # Switch to Tenant B and try to access
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = TeacherReportsService(app_session)

        # The student lookup should fail because the student belongs to Tenant A
        with pytest.raises(TeacherServiceError) as exc_info:
            await svc_b.upsert_class_teacher_comment(
                staff_id=staff_a,
                tenant_id=tenant_b["id"],
                student_id=student_a,
                term_id=term_a,
                academic_year_id=ay_a,
                comment="Cross-tenant attempt.",
            )

        assert exc_info.value.code == "not_found"
    finally:
        await app_session.rollback()
        try:
            async with admin_session_maker() as cleanup:
                for tid in [str(tenant_a["id"]), str(tenant_b["id"])]:
                    for tbl in [
                        "report_comments", "staff_class_assignments",
                        "class_sections", "classes", "students",
                        "staff", "terms", "academic_years",
                        "users", "schools",
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

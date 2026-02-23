"""
SIMS Plus - Teacher Portal RLS Isolation Tests

Verifies that PostgreSQL Row-Level Security correctly isolates
report_comments and lesson_plans tables at the database level.

Pattern:
1. Seed data via admin session (superuser, bypasses RLS)
2. Query via app session (sims_app_user, RLS enforced)
3. Verify isolation: no context = 0 rows, wrong tenant = 0 rows,
   correct tenant = expected rows, cross-tenant INSERT rejected

Uses the two-engine test pattern:
- admin_session: superuser for seeding (bypasses RLS)
- app_session: sims_app_user for isolation assertions (RLS enforced)

IMPORTANT: These tests share database state and MUST NOT run in parallel.
The xdist_group marker ensures serial execution under pytest-xdist.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)

# Ensure serial execution and RLS marker for test selection
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.rls,
    pytest.mark.xdist_group("rls_teacher_serial"),
]


# =====================================================================
# Helpers: seed prerequisite data via admin engine
# =====================================================================


async def seed_prerequisites(admin_session, tenant_id, suffix):
    """Seed school + staff + class + subject + academic_year + term + student.

    Returns dict with all IDs needed for report_comments and lesson_plans.
    """
    school_id = uuid4()
    staff_id = uuid4()
    class_id = uuid4()
    subject_id = uuid4()
    section_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    student_id = uuid4()

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, uses_boarding, uses_transport,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'RLS', 'STF',
                true, false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"RLS School {suffix}", "slug": f"rls-{suffix}"},
    )

    # User + Staff
    user = await create_test_user(admin_session, tenant_id, email=f"rls-{suffix}@test.com")
    await admin_session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, school_id, staff_id, first_name, last_name,
                gender, email, phone, staff_type, status, job_title,
                employment_date, user_id, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'RLS', 'Teacher', 'male', :email, '0241234567',
                'teaching', 'active', 'Teacher', '2020-09-01',
                CAST(:uid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(staff_id), "tid": str(tenant_id), "sid": str(school_id),
            "staff_num": f"STF-{suffix}", "email": f"staff-rls-{suffix}@test.com",
            "uid": str(user["id"]),
        },
    )

    # Class + Section
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, sequence, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                :name, 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"Class-{suffix}"},
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

    # Subject
    await admin_session.execute(
        text("""
            INSERT INTO subjects (id, tenant_id, name, code,
                category, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                'Math', 'MATH', 'core', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(subject_id), "tid": str(tenant_id)},
    )

    # Academic Year + Term
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

    # Student (assigned to section)
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
                :student_num, 'RLS', 'Student', '2012-05-15', 'male', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id), "tid": str(tenant_id),
            "sid": str(school_id), "secid": str(section_id),
            "student_num": f"STU-{suffix}",
        },
    )

    return {
        "school_id": school_id,
        "staff_id": staff_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "section_id": section_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "student_id": student_id,
    }


async def seed_report_comment(admin_session, tenant_id, student_id, term_id,
                                ay_id, staff_id):
    """Insert a report comment via admin (bypasses RLS). Returns comment ID."""
    comment_id = uuid4()
    await admin_session.execute(
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
            "id": str(comment_id), "tid": str(tenant_id),
            "sid": str(student_id), "termid": str(term_id),
            "ayid": str(ay_id), "comment": "Test comment.",
            "ctid": str(staff_id),
        },
    )
    return comment_id


async def seed_lesson_plan(admin_session, tenant_id, staff_id, class_id,
                            subject_id, topic="RLS Test Lesson"):
    """Insert a lesson plan via admin (bypasses RLS). Returns plan ID."""
    plan_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO lesson_plans (
                id, tenant_id, teacher_id, class_id, subject_id,
                date, topic, status, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:teacher AS uuid),
                CAST(:cid AS uuid), CAST(:sid AS uuid),
                '2026-03-01', :topic, 'planned',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(plan_id), "tid": str(tenant_id),
            "teacher": str(staff_id), "cid": str(class_id),
            "sid": str(subject_id), "topic": topic,
        },
    )
    return plan_id


# =====================================================================
# Tests: report_comments RLS
# =====================================================================


async def test_report_comments_rls_no_context(admin_session, app_session):
    """SELECT on report_comments with no tenant context should return 0 rows."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"rc-no-{suffix}")
    prereqs = await seed_prerequisites(admin_session, tenant["id"], suffix)
    await seed_report_comment(
        admin_session, tenant["id"], prereqs["student_id"],
        prereqs["term_id"], prereqs["ay_id"], prereqs["staff_id"],
    )
    await admin_session.commit()

    # Query as app_user with NO context
    await clear_app_tenant_context(app_session)
    result = await app_session.execute(text("SELECT count(*) FROM report_comments"))
    count = result.scalar()
    assert count == 0, f"Expected 0 rows without context, got {count}"


async def test_report_comments_rls_wrong_tenant(admin_session, app_session):
    """SELECT on report_comments with wrong tenant context should return 0 rows."""
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"rc-a-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"rc-b-{suffix}")
    prereqs = await seed_prerequisites(admin_session, tenant_a["id"], f"rca-{suffix}")
    await seed_report_comment(
        admin_session, tenant_a["id"], prereqs["student_id"],
        prereqs["term_id"], prereqs["ay_id"], prereqs["staff_id"],
    )
    await admin_session.commit()

    # Set context to Tenant B -- should see nothing from Tenant A
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM report_comments"))
    count = result.scalar()
    assert count == 0, f"Expected 0 rows for wrong tenant, got {count}"


async def test_report_comments_rls_correct_tenant(admin_session, app_session):
    """SELECT on report_comments with correct tenant context should return rows."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"rc-ok-{suffix}")
    prereqs = await seed_prerequisites(admin_session, tenant["id"], f"rcok-{suffix}")
    await seed_report_comment(
        admin_session, tenant["id"], prereqs["student_id"],
        prereqs["term_id"], prereqs["ay_id"], prereqs["staff_id"],
    )
    await admin_session.commit()

    # Correct tenant context -- should see the row
    await set_app_tenant_context(app_session, tenant["id"])
    result = await app_session.execute(text("SELECT count(*) FROM report_comments"))
    count = result.scalar()
    assert count >= 1, f"Expected at least 1 row for correct tenant, got {count}"


# =====================================================================
# Tests: lesson_plans RLS
# =====================================================================


async def test_lesson_plans_rls_no_context(admin_session, app_session):
    """SELECT on lesson_plans with no tenant context should return 0 rows."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"lp-no-{suffix}")
    prereqs = await seed_prerequisites(admin_session, tenant["id"], f"lpno-{suffix}")
    await seed_lesson_plan(
        admin_session, tenant["id"], prereqs["staff_id"],
        prereqs["class_id"], prereqs["subject_id"],
    )
    await admin_session.commit()

    await clear_app_tenant_context(app_session)
    result = await app_session.execute(text("SELECT count(*) FROM lesson_plans"))
    count = result.scalar()
    assert count == 0, f"Expected 0 rows without context, got {count}"


async def test_lesson_plans_rls_wrong_tenant(admin_session, app_session):
    """SELECT on lesson_plans with wrong tenant context should return 0 rows."""
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"lp-a-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"lp-b-{suffix}")
    prereqs = await seed_prerequisites(admin_session, tenant_a["id"], f"lpa-{suffix}")
    await seed_lesson_plan(
        admin_session, tenant_a["id"], prereqs["staff_id"],
        prereqs["class_id"], prereqs["subject_id"],
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM lesson_plans"))
    count = result.scalar()
    assert count == 0, f"Expected 0 rows for wrong tenant, got {count}"


async def test_lesson_plans_rls_correct_tenant(admin_session, app_session):
    """SELECT on lesson_plans with correct tenant context should return rows."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"lp-ok-{suffix}")
    prereqs = await seed_prerequisites(admin_session, tenant["id"], f"lpok-{suffix}")
    await seed_lesson_plan(
        admin_session, tenant["id"], prereqs["staff_id"],
        prereqs["class_id"], prereqs["subject_id"],
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])
    result = await app_session.execute(text("SELECT count(*) FROM lesson_plans"))
    count = result.scalar()
    assert count >= 1, f"Expected at least 1 row for correct tenant, got {count}"


# =====================================================================
# Tests: INSERT with wrong tenant context (WITH CHECK violation)
# =====================================================================


async def test_report_comments_insert_wrong_tenant(admin_session, app_session):
    """INSERT into report_comments with wrong tenant context should be rejected.

    The RLS WITH CHECK clause ensures that the tenant_id in the inserted row
    must match the current tenant context. Inserting with a different tenant_id
    should raise a policy violation error.
    """
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"rci-a-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"rci-b-{suffix}")

    # Seed prerequisites in Tenant A (the data we'll reference in the INSERT)
    prereqs_a = await seed_prerequisites(admin_session, tenant_a["id"], f"rcia-{suffix}")
    await admin_session.commit()

    # Set context to Tenant A, but try to INSERT with Tenant B's tenant_id
    await set_app_tenant_context(app_session, tenant_a["id"])
    with pytest.raises((ProgrammingError, IntegrityError)) as exc_info:
        await app_session.execute(
            text("""
                INSERT INTO report_comments (
                    id, tenant_id, student_id, term_id, academic_year_id,
                    class_teacher_comment, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:termid AS uuid), CAST(:ayid AS uuid),
                    'Cross-tenant insert attempt',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_b["id"]),  # WRONG tenant_id
                "sid": str(prereqs_a["student_id"]),
                "termid": str(prereqs_a["term_id"]),
                "ayid": str(prereqs_a["ay_id"]),
            },
        )

    error_msg = str(exc_info.value).lower()
    assert "policy" in error_msg or "permission" in error_msg or "violates" in error_msg


async def test_lesson_plans_insert_wrong_tenant(admin_session, app_session):
    """INSERT into lesson_plans with wrong tenant context should be rejected.

    Same pattern as report_comments: the WITH CHECK clause prevents inserting
    rows where tenant_id does not match the session's current tenant.
    """
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"lpi-a-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"lpi-b-{suffix}")

    prereqs_a = await seed_prerequisites(admin_session, tenant_a["id"], f"lpia-{suffix}")
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant_a["id"])
    with pytest.raises((ProgrammingError, IntegrityError)) as exc_info:
        await app_session.execute(
            text("""
                INSERT INTO lesson_plans (
                    id, tenant_id, teacher_id, class_id, subject_id,
                    date, topic, status, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:teacher AS uuid),
                    CAST(:cid AS uuid), CAST(:sid AS uuid),
                    '2026-03-15', 'Cross-tenant plan', 'planned',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_b["id"]),  # WRONG tenant_id
                "teacher": str(prereqs_a["staff_id"]),
                "cid": str(prereqs_a["class_id"]),
                "sid": str(prereqs_a["subject_id"]),
            },
        )

    error_msg = str(exc_info.value).lower()
    assert "policy" in error_msg or "permission" in error_msg or "violates" in error_msg


# =====================================================================
# Tests: FORCE ROW LEVEL SECURITY (structural checks)
# =====================================================================


async def test_force_rls_on_report_comments(app_session):
    """pg_class should confirm relforcerowsecurity=true for report_comments.

    Without FORCE, the table owner bypasses RLS. This is dangerous if the
    application accidentally connects as the table owner.
    """
    result = await app_session.execute(
        text("""
            SELECT relforcerowsecurity FROM pg_class
            WHERE relname = 'report_comments'
        """)
    )
    row = result.fetchone()
    assert row is not None, "report_comments table not found in pg_class"
    assert row[0] is True, (
        "FORCE ROW LEVEL SECURITY not set on report_comments. "
        "Run: ALTER TABLE report_comments FORCE ROW LEVEL SECURITY;"
    )


async def test_force_rls_on_lesson_plans(app_session):
    """pg_class should confirm relforcerowsecurity=true for lesson_plans.

    Without FORCE, the table owner bypasses RLS.
    """
    result = await app_session.execute(
        text("""
            SELECT relforcerowsecurity FROM pg_class
            WHERE relname = 'lesson_plans'
        """)
    )
    row = result.fetchone()
    assert row is not None, "lesson_plans table not found in pg_class"
    assert row[0] is True, (
        "FORCE ROW LEVEL SECURITY not set on lesson_plans. "
        "Run: ALTER TABLE lesson_plans FORCE ROW LEVEL SECURITY;"
    )

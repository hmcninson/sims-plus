"""
SIMS Plus - Teacher Grading Service Tests

Tests for TeacherGradingService:
- Pending score retrieval scoped to teacher's class-subject assignments
- Score entry with validation (max_score, negative, absent, invalid student)
- Auto-grade calculation from grading scale (including normalization)
- Score upsert (update existing, no duplicate)
- Exam subject status locking (submitted/published cannot be modified)
- Cross-tenant isolation via RLS
- Empty input handling
- Batch count accuracy

Key patterns:
- admin_session seeds data as postgres superuser (bypasses RLS)
- app_session runs as sims_app_user (RLS enforced)
- UUID params in raw SQL require CAST(:param AS uuid)
- Enum values are lowercase in the database
- Use flush()/refresh() never commit() in service calls
"""

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.teacher import TeacherGradingService, TeacherServiceError
from tests.conftest import (
    admin_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# =====================================================================
# Seed helpers
# =====================================================================


async def _seed_school(session, tenant_id, suffix):
    school_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, uses_boarding, uses_transport,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'GRD', 'STF',
                true, false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id), "name": f"Grading School {suffix}", "slug": f"grd-{suffix}"},
    )
    return school_id


async def _seed_staff(session, tenant_id, school_id, user_id=None, suffix=None):
    staff_id = uuid4()
    sfx = suffix or uuid4().hex[:6]
    await session.execute(
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


async def _seed_academic_year(session, tenant_id, is_current=True):
    ay_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                '2025-09-01', '2026-07-31', 'active', :cur, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ay_id), "tid": str(tenant_id), "cur": is_current},
    )
    return ay_id


async def _seed_term(session, tenant_id, ay_id, is_current=True):
    term_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO terms (id, tenant_id, academic_year_id, name,
                start_date, end_date, status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid), 'Term 1',
                '2025-09-01', '2025-12-15', 'active', :cur, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(term_id), "tid": str(tenant_id), "ayid": str(ay_id), "cur": is_current},
    )
    return term_id


async def _seed_class_and_section(session, tenant_id, school_id, class_name="Primary 6"):
    class_id = uuid4()
    section_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, sequence, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                :name, 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": class_name},
    )
    await session.execute(
        text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                'Section A', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)},
    )
    return class_id, section_id


async def _seed_subject(session, tenant_id, school_id, name="Mathematics"):
    subj_id = uuid4()
    await session.execute(
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


async def _seed_class_subject(session, tenant_id, class_id, subject_id, teacher_id=None):
    cs_id = uuid4()
    await session.execute(
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


async def _seed_student(session, tenant_id, school_id, section_id, suffix=None):
    student_id = uuid4()
    sfx = suffix or uuid4().hex[:6]
    await session.execute(
        text("""
            INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
                date_of_birth, gender, status, school_id, section_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
                '2015-01-15', 'male', 'active', CAST(:school_id AS uuid), CAST(:sec_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id),
            "sid": f"GRD-{sfx}", "fn": f"Student{sfx}", "ln": "Test",
            "school_id": str(school_id), "sec_id": str(section_id),
        },
    )
    return student_id


async def _seed_exam(session, tenant_id, ay_id, term_id, name="Mid-Term Exam", status="scheduled"):
    exam_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO exams (id, tenant_id, academic_year_id, term_id, name,
                exam_type, status, start_date, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid),
                CAST(:termid AS uuid), :name, 'midterm', :status, '2025-10-15',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(exam_id), "tid": str(tenant_id),
            "ayid": str(ay_id), "termid": str(term_id),
            "name": name, "status": status,
        },
    )
    return exam_id


async def _seed_exam_subject(
    session, tenant_id, exam_id, subject_id, class_id,
    section_id=None, max_score=100, status="pending", grading_scale_id=None,
):
    es_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO exam_subjects (id, tenant_id, exam_id, subject_id, class_id,
                section_id, max_score, pass_mark, status, grading_scale_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:eid AS uuid),
                CAST(:sid AS uuid), CAST(:cid AS uuid),
                CAST(:secid AS uuid), :max_score, 50, :status,
                CAST(:gsid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(es_id), "tid": str(tenant_id),
            "eid": str(exam_id), "sid": str(subject_id), "cid": str(class_id),
            "secid": str(section_id) if section_id else None,
            "max_score": max_score, "status": status,
            "gsid": str(grading_scale_id) if grading_scale_id else None,
        },
    )
    return es_id


async def _seed_grading_scale_with_grades(session, tenant_id):
    """Seed a simple grading scale: A(80-100), B(60-79), C(40-59), F(0-39)."""
    gs_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Default Scale',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(gs_id), "tid": str(tenant_id)},
    )
    # (grade_letter, min_score, max_score, grade_point, remark)
    grades = [
        ("A", 80, 100, "4.00", "Excellent"),
        ("B", 60, 79, "3.00", "Good"),
        ("C", 40, 59, "2.00", "Satisfactory"),
        ("F", 0, 39, "0.00", "Fail"),
    ]
    for grade_letter, min_score, max_score, grade_point, remark in grades:
        g_id = uuid4()
        await session.execute(
            text("""
                INSERT INTO grades (id, tenant_id, grading_scale_id, grade,
                    min_score, max_score, grade_point, remark,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:gsid AS uuid),
                    :grade, :min_score, :max_score, :grade_point, :remark,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(g_id), "tid": str(tenant_id), "gsid": str(gs_id),
                "grade": grade_letter, "min_score": min_score,
                "max_score": max_score, "grade_point": grade_point,
                "remark": remark,
            },
        )
    return gs_id


# =====================================================================
# Fixture: full grading environment
# =====================================================================


@pytest_asyncio.fixture
async def grading_env(admin_session: AsyncSession, app_session: AsyncSession):
    """
    Seed a complete grading environment:
    - tenant, school, 2 users/staff (teacher A + teacher B)
    - academic year, term, class, section, 2 subjects
    - teacher A assigned to subject 1, teacher B assigned to subject 2
    - 2 students enrolled in the section
    - 1 exam with 2 exam subjects (one for each teacher's subject)
    - grading scale with A/B/C/F grades
    """
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"grd-{suffix}")
    tid = tenant["id"]

    school_id = await _seed_school(admin_session, tid, suffix)

    user_a = await create_test_user(admin_session, tid, email=f"grading-a-{suffix}@test.com")
    user_b = await create_test_user(admin_session, tid, email=f"grading-b-{suffix}@test.com")
    staff_a = await _seed_staff(admin_session, tid, school_id, user_id=user_a["id"], suffix=f"ga-{suffix}")
    staff_b = await _seed_staff(admin_session, tid, school_id, user_id=user_b["id"], suffix=f"gb-{suffix}")

    ay_id = await _seed_academic_year(admin_session, tid)
    term_id = await _seed_term(admin_session, tid, ay_id)

    class_id, section_id = await _seed_class_and_section(admin_session, tid, school_id)

    subj_1 = await _seed_subject(admin_session, tid, school_id, "Mathematics")
    subj_2 = await _seed_subject(admin_session, tid, school_id, "English")

    # Assign teacher A to Mathematics, teacher B to English
    await _seed_class_subject(admin_session, tid, class_id, subj_1, teacher_id=staff_a)
    await _seed_class_subject(admin_session, tid, class_id, subj_2, teacher_id=staff_b)

    # Two students enrolled in this section
    student_1 = await _seed_student(admin_session, tid, school_id, section_id, suffix=f"s1-{suffix}")
    student_2 = await _seed_student(admin_session, tid, school_id, section_id, suffix=f"s2-{suffix}")

    # Grading scale
    gs_id = await _seed_grading_scale_with_grades(admin_session, tid)

    # Exam with two exam subjects
    exam_id = await _seed_exam(admin_session, tid, ay_id, term_id)
    es_math = await _seed_exam_subject(
        admin_session, tid, exam_id, subj_1, class_id,
        section_id=section_id, grading_scale_id=gs_id,
    )
    es_english = await _seed_exam_subject(
        admin_session, tid, exam_id, subj_2, class_id,
        section_id=section_id, grading_scale_id=gs_id,
    )

    await admin_session.commit()
    await set_app_tenant_context(app_session, tid)

    yield {
        "tenant_id": tid,
        "school_id": school_id,
        "user_a_id": user_a["id"],
        "user_b_id": user_b["id"],
        "staff_a": staff_a,
        "staff_b": staff_b,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "section_id": section_id,
        "subj_1": subj_1,
        "subj_2": subj_2,
        "student_1": student_1,
        "student_2": student_2,
        "gs_id": gs_id,
        "exam_id": exam_id,
        "es_math": es_math,
        "es_english": es_english,
        "app_session": app_session,
    }

    await app_session.rollback()
    try:
        async with admin_session_maker() as cleanup:
            for tbl in [
                "exam_scores", "exam_subjects", "exams",
                "grades", "grading_scales",
                "class_subjects", "class_sections", "classes",
                "subjects", "terms", "academic_years",
                "students", "staff", "users", "schools",
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
# Tests: get_pending_scores
# =====================================================================


@pytest.mark.asyncio
async def test_get_pending_scores_returns_own_subjects(grading_env):
    """Teacher A should see only their assigned Math exam subject as pending."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    pending = await svc.get_pending_scores(
        staff_id=env["staff_a"],
        tenant_id=env["tenant_id"],
        academic_year_id=env["ay_id"],
        term_id=env["term_id"],
    )

    # Teacher A is assigned to Mathematics, so should see exactly one pending entry
    assert len(pending) == 1
    assert pending[0]["subject_id"] == env["subj_1"]
    assert pending[0]["exam_subject_id"] == env["es_math"]


@pytest.mark.asyncio
async def test_get_pending_scores_excludes_other_teachers(grading_env):
    """Teacher A should NOT see Teacher B's English exam subject."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    pending = await svc.get_pending_scores(
        staff_id=env["staff_a"],
        tenant_id=env["tenant_id"],
        academic_year_id=env["ay_id"],
        term_id=env["term_id"],
    )

    # Verify English (Teacher B's subject) is not in Teacher A's pending list
    subject_ids = [p["subject_id"] for p in pending]
    assert env["subj_2"] not in subject_ids


@pytest.mark.asyncio
async def test_pending_scores_batch_counts_correct(grading_env):
    """The total_students and scores_entered counts must be accurate."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    pending = await svc.get_pending_scores(
        staff_id=env["staff_a"],
        tenant_id=env["tenant_id"],
        academic_year_id=env["ay_id"],
        term_id=env["term_id"],
    )

    assert len(pending) == 1
    entry = pending[0]
    # 2 students enrolled in the section, no scores entered yet
    assert entry["total_students"] == 2
    assert entry["scores_entered"] == 0
    assert entry["status"] == "pending"


# =====================================================================
# Tests: enter_scores
# =====================================================================


@pytest.mark.asyncio
async def test_enter_scores_success(grading_env):
    """Valid score entry should create ExamScore records and report success."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    scores = [
        {"student_id": env["student_1"], "score": 85, "is_absent": False},
        {"student_id": env["student_2"], "score": 72, "is_absent": False},
    ]

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    assert result["total"] == 2
    assert result["successful"] == 2
    assert result["failed"] == 0
    assert len(result["results"]) == 2
    # Both entries should be successful
    for r in result["results"]:
        assert r["success"] is True


@pytest.mark.asyncio
async def test_enter_scores_auto_grades(grading_env):
    """Scores should trigger grade lookup from the grading scale.
    85/100 should map to A (min_score=80), 55/100 to C (min_score=40)."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    scores = [
        {"student_id": env["student_1"], "score": 85, "is_absent": False},
        {"student_id": env["student_2"], "score": 55, "is_absent": False},
    ]

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    # Student 1: 85 -> A (Excellent)
    s1_result = next(r for r in result["results"] if r["student_id"] == env["student_1"])
    assert s1_result["grade"] == "A"
    assert s1_result["grade_remark"] == "Excellent"

    # Student 2: 55 -> C (Satisfactory)
    s2_result = next(r for r in result["results"] if r["student_id"] == env["student_2"])
    assert s2_result["grade"] == "C"
    assert s2_result["grade_remark"] == "Satisfactory"


@pytest.mark.asyncio
async def test_enter_scores_validates_max_score(grading_env):
    """Score exceeding max_score should be rejected."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    scores = [
        {"student_id": env["student_1"], "score": 150, "is_absent": False},
    ]

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    assert result["failed"] == 1
    assert result["successful"] == 0
    assert "exceeds maximum" in result["results"][0]["error"]


@pytest.mark.asyncio
async def test_enter_scores_rejects_invalid_student(grading_env):
    """Student not enrolled in the exam subject's class should be rejected."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    # Use a random UUID that doesn't belong to any enrolled student
    fake_student_id = uuid4()
    scores = [
        {"student_id": fake_student_id, "score": 70, "is_absent": False},
    ]

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    assert result["failed"] == 1
    assert "not enrolled" in result["results"][0]["error"]


@pytest.mark.asyncio
async def test_enter_scores_absent_student(grading_env):
    """Absent flag should create score with is_absent=True and score=None."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    scores = [
        {"student_id": env["student_1"], "score": None, "is_absent": True},
    ]

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    assert result["successful"] == 1
    assert result["results"][0]["success"] is True
    # Absent students should not get a grade
    assert result["results"][0]["grade"] is None


@pytest.mark.asyncio
async def test_enter_scores_submitted_exam_locked(grading_env):
    """Scores cannot be entered for exam subjects in submitted status."""
    env = grading_env

    # Seed a separate exam with a submitted exam subject via admin session
    # (admin bypasses RLS, and both inserts need to be on the same connection
    # so the FK from exam_subjects -> exams resolves)
    async with admin_session_maker() as admin:
        exam_id = await _seed_exam(
            admin, env["tenant_id"], env["ay_id"], env["term_id"],
            name="Locked Exam", status="scheduled",
        )
        es_id = await _seed_exam_subject(
            admin, env["tenant_id"], exam_id, env["subj_1"], env["class_id"],
            section_id=env["section_id"], status="submitted",
        )
        await admin.commit()

    # Refresh the app_session to see the newly committed data
    env["app_session"].expire_all()

    svc = TeacherGradingService(env["app_session"])

    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.enter_scores(
            staff_id=env["staff_a"],
            user_id=env["user_a_id"],
            tenant_id=env["tenant_id"],
            exam_subject_id=es_id,
            scores=[{"student_id": env["student_1"], "score": 70, "is_absent": False}],
        )

    assert exc_info.value.code == "scores_locked"


@pytest.mark.asyncio
async def test_score_upsert_updates_existing(grading_env):
    """Re-entering score for the same student should update, not duplicate."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    # First entry
    scores_v1 = [{"student_id": env["student_1"], "score": 60, "is_absent": False}]
    result_v1 = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores_v1,
    )
    assert result_v1["successful"] == 1
    # Grade for 60 -> B
    assert result_v1["results"][0]["grade"] == "B"

    # Second entry (update score)
    scores_v2 = [{"student_id": env["student_1"], "score": 90, "is_absent": False}]
    result_v2 = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores_v2,
    )
    assert result_v2["successful"] == 1
    # Grade should now be A (90 -> A)
    assert result_v2["results"][0]["grade"] == "A"

    # Verify no duplicate by checking pending scores count
    pending = await svc.get_pending_scores(
        staff_id=env["staff_a"],
        tenant_id=env["tenant_id"],
        academic_year_id=env["ay_id"],
        term_id=env["term_id"],
    )
    math_pending = [p for p in pending if p["exam_subject_id"] == env["es_math"]]
    # scores_entered should be 1, not 2 (no duplicate)
    assert math_pending[0]["scores_entered"] == 1


@pytest.mark.asyncio
async def test_score_negative_value_rejected(grading_env):
    """Negative scores should be rejected by the service validation."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    scores = [{"student_id": env["student_1"], "score": -5, "is_absent": False}]

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    assert result["failed"] == 1
    assert "negative" in result["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_enter_scores_empty_list(grading_env):
    """Empty scores list should return zero results without error."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=[],
    )

    assert result["total"] == 0
    assert result["successful"] == 0
    assert result["failed"] == 0
    assert result["results"] == []


# =====================================================================
# Tests: get_class_grade_summary
# =====================================================================


@pytest.mark.asyncio
async def test_get_class_grade_summary(grading_env):
    """Grade summary should return averages and student details."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    # Enter scores first so the summary has data
    scores = [
        {"student_id": env["student_1"], "score": 80, "is_absent": False},
        {"student_id": env["student_2"], "score": 60, "is_absent": False},
    ]
    await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=env["es_math"],
        scores=scores,
    )

    summary = await svc.get_class_grade_summary(
        staff_id=env["staff_a"],
        tenant_id=env["tenant_id"],
        class_id=env["class_id"],
        subject_id=env["subj_1"],
        term_id=env["term_id"],
    )

    assert summary["class_id"] == env["class_id"]
    assert summary["subject_name"] == "Mathematics"
    assert summary["total_students"] == 2
    assert len(summary["students"]) == 2

    # Class average should be (80 + 60) / 2 = 70
    assert summary["class_average"] == Decimal("70.00")
    assert summary["highest_score"] == Decimal("80.00")
    assert summary["lowest_score"] == Decimal("60.00")


@pytest.mark.asyncio
async def test_grade_calculation_normalization(grading_env):
    """Non-100-point exams should normalize scores for grade lookup.
    A score of 40/50 = 80% should get grade A (min_score=80)."""
    env = grading_env

    # Create a new exam subject with max_score=50
    async with admin_session_maker() as admin:
        exam_id_50 = await _seed_exam(
            admin, env["tenant_id"], env["ay_id"], env["term_id"],
            name="50-Point Exam",
        )
        es_50 = await _seed_exam_subject(
            admin, env["tenant_id"], exam_id_50, env["subj_1"], env["class_id"],
            section_id=env["section_id"], max_score=50, grading_scale_id=env["gs_id"],
        )
        await admin.commit()

    env["app_session"].expire_all()
    svc = TeacherGradingService(env["app_session"])

    # 40/50 = 80% → should get A
    scores = [{"student_id": env["student_1"], "score": 40, "is_absent": False}]
    result = await svc.enter_scores(
        staff_id=env["staff_a"],
        user_id=env["user_a_id"],
        tenant_id=env["tenant_id"],
        exam_subject_id=es_50,
        scores=scores,
    )

    assert result["successful"] == 1
    assert result["results"][0]["grade"] == "A"
    assert result["results"][0]["grade_remark"] == "Excellent"


# =====================================================================
# Tests: Cross-tenant isolation
# =====================================================================


@pytest.mark.asyncio
async def test_enter_scores_cross_tenant_blocked(
    admin_session: AsyncSession, app_session: AsyncSession
):
    """RLS should prevent score entry against exam subjects from another tenant."""
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"grda-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"grdb-{suffix}")

    # Seed data in tenant A
    school_a = await _seed_school(admin_session, tenant_a["id"], f"a-{suffix}")
    user_a = await create_test_user(admin_session, tenant_a["id"])
    staff_a = await _seed_staff(admin_session, tenant_a["id"], school_a, user_id=user_a["id"], suffix=f"xa-{suffix}")
    ay_a = await _seed_academic_year(admin_session, tenant_a["id"])
    term_a = await _seed_term(admin_session, tenant_a["id"], ay_a)
    class_a, section_a = await _seed_class_and_section(admin_session, tenant_a["id"], school_a)
    subj_a = await _seed_subject(admin_session, tenant_a["id"], school_a)
    await _seed_class_subject(admin_session, tenant_a["id"], class_a, subj_a, teacher_id=staff_a)
    student_a = await _seed_student(admin_session, tenant_a["id"], school_a, section_a)
    exam_a = await _seed_exam(admin_session, tenant_a["id"], ay_a, term_a)
    es_a = await _seed_exam_subject(
        admin_session, tenant_a["id"], exam_a, subj_a, class_a, section_id=section_a,
    )
    await admin_session.commit()

    try:
        # Set tenant context to tenant B -- the exam subject from tenant A
        # should be invisible due to RLS
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc = TeacherGradingService(app_session)

        with pytest.raises(TeacherServiceError) as exc_info:
            await svc.enter_scores(
                staff_id=staff_a,
                user_id=user_a["id"],
                tenant_id=tenant_b["id"],
                exam_subject_id=es_a,
                scores=[{"student_id": student_a, "score": 70, "is_absent": False}],
            )

        assert exc_info.value.code == "not_found"
    finally:
        await app_session.rollback()
        try:
            async with admin_session_maker() as cleanup:
                for tid in [str(tenant_a["id"]), str(tenant_b["id"])]:
                    for tbl in [
                        "exam_scores", "exam_subjects", "exams",
                        "class_subjects", "class_sections", "classes",
                        "subjects", "terms", "academic_years",
                        "students", "staff", "users", "schools",
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


@pytest.mark.asyncio
async def test_enter_scores_exam_subject_not_found(grading_env):
    """Entering scores for a nonexistent exam subject should raise not_found."""
    env = grading_env
    svc = TeacherGradingService(env["app_session"])

    with pytest.raises(TeacherServiceError) as exc_info:
        await svc.enter_scores(
            staff_id=env["staff_a"],
            user_id=env["user_a_id"],
            tenant_id=env["tenant_id"],
            exam_subject_id=uuid4(),
            scores=[{"student_id": env["student_1"], "score": 70, "is_absent": False}],
        )

    assert exc_info.value.code == "not_found"

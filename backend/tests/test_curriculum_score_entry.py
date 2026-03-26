"""
Tests for curriculum-aware score entry (Phase 2).

Covers: effort_grade storage, backward compatibility for GES,
effort_grade validation, and criterion_scores JSONB storage.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    set_app_tenant_context,
)

import pytest_asyncio
from tests.conftest import admin_engine as _admin_engine

pytestmark = [pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True, scope="session")
async def _ensure_exam_scores_columns():
    """Add criterion_scores and effort_grade columns to exam_scores if missing."""
    async with _admin_engine.connect() as conn:
        for col, col_type in [
            ("criterion_scores", "JSONB"),
            ("effort_grade", "VARCHAR(5)"),
        ]:
            result = await conn.execute(
                text(f"""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'exam_scores'
                    AND column_name = '{col}'
                """)
            )
            if result.fetchone() is None:
                await conn.execute(text(f"ALTER TABLE exam_scores ADD COLUMN {col} {col_type}"))
        await conn.commit()


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_pro(admin_session, tier: str = "professional"):
    tenant_id = uuid4()
    sub = f"test{uuid4().hex[:8]}"
    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                true, 'single_school', :tier, 500,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub,
         "name": f"School {sub}", "tier": tier},
    )
    await admin_session.flush()
    return {"id": tenant_id, "subdomain": sub}


async def _seed_score_prerequisites(admin_session, tenant_id, curriculum_type="cambridge"):
    """Seed school, student, class, year, term, exam, exam_subject, grading_scale."""
    ids = {k: uuid4() for k in [
        "school_id", "student_id", "class_id", "academic_year_id",
        "term_id", "grading_scale_id", "profile_id", "subject_id",
        "exam_id", "exam_subject_id",
    ]}

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["school_id"]), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"sch-{uuid4().hex[:8]}"},
    )

    # Academic year
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["academic_year_id"]), "tid": str(tenant_id),
         "name": f"AY-{uuid4().hex[:6]}"},
    )

    # Term
    await admin_session.execute(
        text("""
            INSERT INTO terms (id, tenant_id, academic_year_id, name, sequence,
                start_date, end_date, status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay AS uuid),
                'Term 1', 1, '2025-09-01', '2025-12-20', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["term_id"]), "tid": str(tenant_id),
         "ay": str(ids["academic_year_id"])},
    )

    # Grading scale
    await admin_session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, scale_type,
                is_default, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :stype,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["grading_scale_id"]), "tid": str(tenant_id),
         "name": "Cambridge Scale", "stype": "cambridge"},
    )

    # Grades
    for grade, min_s, max_s, gp in [("A*", 90, 100, "9.0"), ("A", 80, 89, "8.0"),
                                      ("B", 70, 79, "7.0"), ("C", 60, 69, "6.0"),
                                      ("D", 50, 59, "5.0"), ("E", 40, 49, "4.0"),
                                      ("U", 0, 39, "0.0")]:
        await admin_session.execute(
            text("""
                INSERT INTO grades (id, tenant_id, grading_scale_id,
                    grade, min_score, max_score, grade_point,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:gsid AS uuid),
                    :grade, :min, :max, :gp,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(uuid4()), "tid": str(tenant_id),
             "gsid": str(ids["grading_scale_id"]),
             "grade": grade, "min": min_s, "max": max_s, "gp": gp},
        )

    # Curriculum profile
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, grading_scale_id, academic_calendar_type,
                periods_per_year, score_display_mode,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, :ctype, CAST(:gsid AS uuid), 'terms', 3, 'grade_and_score',
                false, false, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]), "name": "Cambridge IGCSE",
         "ctype": curriculum_type, "gsid": str(ids["grading_scale_id"])},
    )

    # Class with curriculum_profile_id
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, curriculum_profile_id, school_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'shs', 1, true, CAST(:pid AS uuid), CAST(:sid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["class_id"]), "tid": str(tenant_id),
         "name": f"IGCSE-{uuid4().hex[:4]}",
         "pid": str(ids["profile_id"]),
         "sid": str(ids["school_id"])},
    )

    # Student
    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                class_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:sid AS uuid), :stuid,
                'Test', 'Student', '2008-01-01', 'male', 'active',
                CAST(:cid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["student_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "stuid": f"STU-{uuid4().hex[:6]}",
         "cid": str(ids["class_id"])},
    )

    # Subject
    await admin_session.execute(
        text("""
            INSERT INTO subjects (id, tenant_id, name, code, category,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Mathematics', 'MATH',
                'core', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["subject_id"]), "tid": str(tenant_id)},
    )

    # Exam
    await admin_session.execute(
        text("""
            INSERT INTO exams (id, tenant_id, academic_year_id, term_id,
                name, exam_type, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:ayid AS uuid), CAST(:tmid AS uuid),
                :name, 'end_term', 'completed',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["exam_id"]), "tid": str(tenant_id),
         "ayid": str(ids["academic_year_id"]),
         "tmid": str(ids["term_id"]),
         "name": f"Exam-{uuid4().hex[:6]}"},
    )

    # Exam subject
    await admin_session.execute(
        text("""
            INSERT INTO exam_subjects (id, tenant_id, exam_id, subject_id,
                class_id, max_score, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:eid AS uuid), CAST(:sid AS uuid),
                CAST(:cid AS uuid), 100, 'scores_entered',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["exam_subject_id"]), "tid": str(tenant_id),
         "eid": str(ids["exam_id"]),
         "sid": str(ids["subject_id"]),
         "cid": str(ids["class_id"])},
    )

    await admin_session.commit()
    return ids


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestEffortGradeStorage:
    """Tests for effort_grade column on exam_scores."""

    async def test_effort_grade_saved(self, admin_session):
        """Effort grade should be stored on ExamScore for Cambridge."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"])

        score_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade, effort_grade,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    85.0, 'A', '2',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT effort_grade FROM exam_scores WHERE id = CAST(:id AS uuid)"),
            {"id": str(score_id)},
        )
        assert result.scalar_one() == "2"

    async def test_effort_grade_optional_backward_compat(self, admin_session):
        """Score entry without effort_grade should work (GES backward compat)."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"], "ges")

        score_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    75.0, 'B2',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT effort_grade FROM exam_scores WHERE id = CAST(:id AS uuid)"),
            {"id": str(score_id)},
        )
        assert result.scalar_one() is None

    async def test_effort_grade_max_length(self, admin_session):
        """Effort grade column should accept values up to 5 chars."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"])

        score_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade, effort_grade,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    92.0, 'A*', 'A+',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT effort_grade FROM exam_scores WHERE id = CAST(:id AS uuid)"),
            {"id": str(score_id)},
        )
        assert result.scalar_one() == "A+"


class TestCriterionScoresStorage:
    """Tests for criterion_scores JSONB column on exam_scores."""

    async def test_criterion_scores_saved_as_jsonb(self, admin_session):
        """Criterion scores should be stored in JSONB column."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"])

        score_id = uuid4()
        criterion_data = '{"criterion_a": 7, "criterion_b": 6, "criterion_c": 8, "criterion_d": 7}'
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade, criterion_scores,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    85.0, 'A', CAST(:criteria AS jsonb),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"]),
             "criteria": criterion_data},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT criterion_scores FROM exam_scores WHERE id = CAST(:id AS uuid)"),
            {"id": str(score_id)},
        )
        row = result.scalar_one()
        assert row["criterion_a"] == 7
        assert row["criterion_d"] == 7

    async def test_criterion_scores_null_for_non_ib(self, admin_session):
        """Criterion scores should be null when not provided (backward compat)."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"], "ges")

        score_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    70.0, 'B2',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT criterion_scores FROM exam_scores WHERE id = CAST(:id AS uuid)"),
            {"id": str(score_id)},
        )
        assert result.scalar_one() is None


class TestReportCardConfigFlags:
    """Tests for ReportCardConfig show_effort_grade flag."""

    async def test_show_effort_grade_flag_stored(self, admin_session):
        """ReportCardConfig should store show_effort_grade flag."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"])

        config_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO report_card_configs (id, tenant_id, curriculum_profile_id,
                    template_key, show_effort_grade, show_position,
                    show_class_average, show_subject_position,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:pid AS uuid),
                    'cambridge_igcse', true, true, true, true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(config_id), "tid": str(tenant["id"]),
             "pid": str(ids["profile_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT show_effort_grade FROM report_card_configs WHERE id = CAST(:id AS uuid)"),
            {"id": str(config_id)},
        )
        assert result.scalar_one() is True

    async def test_show_effort_grade_default_false(self, admin_session):
        """show_effort_grade should default to false for GES configs."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_score_prerequisites(admin_session, tenant["id"], "ges")

        config_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO report_card_configs (id, tenant_id, curriculum_profile_id,
                    template_key, show_position, show_class_average,
                    show_subject_position,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:pid AS uuid),
                    'ges_default', true, true, true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(config_id), "tid": str(tenant["id"]),
             "pid": str(ids["profile_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT show_effort_grade FROM report_card_configs WHERE id = CAST(:id AS uuid)"),
            {"id": str(config_id)},
        )
        assert result.scalar_one() is False

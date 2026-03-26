"""
Tests for criterion-referenced grading (Phase 7).

Covers: criterion scores saved in JSONB, auto-computed grade from totals,
backward compat without criterion_scores, and proportional scaling.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

import pytest_asyncio
from tests.conftest import admin_engine as _admin_engine


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


async def _seed_criterion_data(admin_session, tenant_id):
    """Seed school, class, student, grading_scale with IB MYP 1-8 grades."""
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

    # Academic year + term
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

    # IB MYP grading scale (1-8)
    await admin_session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, scale_type,
                is_default, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'IB MYP Scale', 'ib',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["grading_scale_id"]), "tid": str(tenant_id)},
    )

    # IB MYP grades: criterion totals map to levels 1-7
    # Standard MYP: max 32 points across 4 criteria (each 0-8)
    ib_grades = [
        ("7", 28, 32, "7.0"), ("6", 24, 27, "6.0"),
        ("5", 19, 23, "5.0"), ("4", 15, 18, "4.0"),
        ("3", 10, 14, "3.0"), ("2", 6, 9, "2.0"),
        ("1", 1, 5, "1.0"),
    ]
    for grade, min_s, max_s, gp in ib_grades:
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
             "grade": grade,
             "min": min_s, "max": max_s, "gp": gp},
        )

    # IB MYP profile with criterion grading enabled
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, grading_scale_id, academic_calendar_type,
                periods_per_year, score_display_mode,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'IB MYP', 'ib', CAST(:gsid AS uuid), 'terms', 3,
                'level', true, false, true,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "gsid": str(ids["grading_scale_id"])},
    )

    # Class
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, curriculum_profile_id, school_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'jhs', 1, true, CAST(:pid AS uuid), CAST(:sid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["class_id"]), "tid": str(tenant_id),
         "name": f"MYP-{uuid4().hex[:4]}",
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
                'Kofi', 'Owusu', '2011-05-15', 'male', 'active',
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
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Sciences', 'SCI',
                'core', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["subject_id"]), "tid": str(tenant_id)},
    )

    # Exam + exam_subject
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
    await admin_session.execute(
        text("""
            INSERT INTO exam_subjects (id, tenant_id, exam_id, subject_id,
                class_id, max_score, pass_mark, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:eid AS uuid), CAST(:sid AS uuid),
                CAST(:cid AS uuid), 32, 15, 'scores_entered',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["exam_subject_id"]), "tid": str(tenant_id),
         "eid": str(ids["exam_id"]),
         "sid": str(ids["subject_id"]),
         "cid": str(ids["class_id"])},
    )

    await admin_session.commit()
    return ids


def _compute_ib_grade(criterion_total: int, grades_data: list[tuple]) -> str | None:
    """Simulate IB MYP grade determination from criterion total.

    grades_data: list of (grade_label, min_score, max_score)
    """
    for grade, min_s, max_s in sorted(grades_data, key=lambda g: g[1], reverse=True):
        if criterion_total >= min_s:
            return grade
    return None


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

IB_GRADES = [
    ("7", 28, 32), ("6", 24, 27), ("5", 19, 23),
    ("4", 15, 18), ("3", 10, 14), ("2", 6, 9), ("1", 1, 5),
]


class TestCriterionScoring:
    """Tests for IB MYP criterion-referenced grading."""

    async def test_criterion_scores_stored_in_jsonb(self, admin_session):
        """Criterion scores should be stored in exam_scores.criterion_scores JSONB."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_criterion_data(admin_session, tenant["id"])

        score_id = uuid4()
        criteria = '{"A": 7, "B": 6, "C": 8, "D": 7}'
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, criterion_scores,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    28, CAST(:criteria AS jsonb),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"]),
             "criteria": criteria},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT criterion_scores FROM exam_scores WHERE id = CAST(:id AS uuid)"),
            {"id": str(score_id)},
        )
        data = result.scalar_one()
        assert data["A"] == 7
        assert data["B"] == 6
        assert data["C"] == 8
        assert data["D"] == 7
        assert sum(data.values()) == 28

    def test_auto_computed_grade_28_to_32_equals_7(self):
        """Criterion total 28-32 should map to IB grade 7."""
        assert _compute_ib_grade(28, IB_GRADES) == "7"
        assert _compute_ib_grade(30, IB_GRADES) == "7"
        assert _compute_ib_grade(32, IB_GRADES) == "7"

    def test_auto_computed_grade_15_to_18_equals_4(self):
        """Criterion total 15-18 should map to IB grade 4."""
        assert _compute_ib_grade(15, IB_GRADES) == "4"
        assert _compute_ib_grade(17, IB_GRADES) == "4"
        assert _compute_ib_grade(18, IB_GRADES) == "4"

    def test_auto_computed_grade_boundaries(self):
        """Verify all grade boundaries are correct."""
        assert _compute_ib_grade(1, IB_GRADES) == "1"
        assert _compute_ib_grade(5, IB_GRADES) == "1"
        assert _compute_ib_grade(6, IB_GRADES) == "2"
        assert _compute_ib_grade(9, IB_GRADES) == "2"
        assert _compute_ib_grade(10, IB_GRADES) == "3"
        assert _compute_ib_grade(14, IB_GRADES) == "3"
        assert _compute_ib_grade(19, IB_GRADES) == "5"
        assert _compute_ib_grade(24, IB_GRADES) == "6"

    async def test_backward_compat_without_criterion_scores(self, admin_session):
        """Score entry without criterion_scores should work (non-criterion classes)."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_criterion_data(admin_session, tenant["id"])

        score_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    24, '6',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("""
                SELECT score, grade, criterion_scores
                FROM exam_scores WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(score_id)},
        )
        row = result.one()
        assert float(row[0]) == 24.0
        assert row[1] == "6"
        assert row[2] is None  # criterion_scores is NULL

    async def test_criterion_profile_has_use_criterion_grading_flag(self, admin_session):
        """IB MYP profile should have use_criterion_grading=True."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_criterion_data(admin_session, tenant["id"])

        result = await admin_session.execute(
            text("""
                SELECT use_criterion_grading FROM curriculum_profiles
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["profile_id"])},
        )
        assert result.scalar_one() is True

    def test_proportional_scaling_non_standard_max(self):
        """Non-standard max criterion should scale proportionally.

        Example: if max is 24 instead of 32, scale boundaries:
        7 = 21-24, 6 = 18-20, etc.
        """
        # Scale factor: 24/32 = 0.75
        scale = Decimal("24") / Decimal("32")

        # Scaled boundaries for grade 7: 28*0.75=21, 32*0.75=24
        scaled_min_7 = int(28 * float(scale))  # 21
        scaled_max_7 = int(32 * float(scale))  # 24

        # A student with 22 out of 24 should get grade 7
        # (22/24) * 32 = 29.33 => grade 7
        normalized = int((22 / 24) * 32)
        assert _compute_ib_grade(normalized, IB_GRADES) == "7"

        # A student with 14 out of 24 should get grade 4
        # (14/24) * 32 = 18.67 => int(18.67) = 18 => grade 4
        normalized_low = int((14 / 24) * 32)
        assert _compute_ib_grade(normalized_low, IB_GRADES) == "4"

    async def test_criterion_scores_with_both_score_and_criteria(self, admin_session):
        """Score and criterion_scores can coexist on the same record."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_criterion_data(admin_session, tenant["id"])

        score_id = uuid4()
        criteria = '{"A": 6, "B": 5, "C": 7, "D": 6}'
        total = 6 + 5 + 7 + 6  # 24
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, grade, criterion_scores,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    :total, '6', CAST(:criteria AS jsonb),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(score_id), "tid": str(tenant["id"]),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids["student_id"]),
             "total": total, "criteria": criteria},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("""
                SELECT score, grade, criterion_scores
                FROM exam_scores WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(score_id)},
        )
        row = result.one()
        assert float(row[0]) == 24.0
        assert row[1] == "6"
        assert sum(row[2].values()) == 24

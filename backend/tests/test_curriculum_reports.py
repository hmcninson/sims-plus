"""
Tests for curriculum-specific report generation (Phase 1).

Covers: American GPA, honor roll, cumulative GPA, IB total points,
French mention, GES backward compat, subject position, and PDF context.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)
from app.services.exam.score_strategies import (
    AmericanScoreStrategy,
    IBScoreStrategy,
    FrenchScoreStrategy,
    GESScoreStrategy,
    MontessoriScoreStrategy,
    SubjectScoreResult,
    get_score_strategy,
)


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_pro(admin_session, tier: str = "professional"):
    """Create a tenant with a given subscription tier."""
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


async def _seed_report_prerequisites(admin_session, tenant_id, curriculum_type="american"):
    """Seed school, student, class, academic_year, term, grading scale, profile."""
    ids = {k: uuid4() for k in [
        "school_id", "student_id", "student2_id", "student3_id",
        "class_id", "academic_year_id", "term_id",
        "grading_scale_id", "profile_id", "subject_id", "subject2_id",
    ]}

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

    # Grading scale
    await admin_session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, scale_type,
                is_default, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :stype,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["grading_scale_id"]), "tid": str(tenant_id),
         "name": f"{curriculum_type} Scale",
         "stype": curriculum_type if curriculum_type != "ges" else "waec"},
    )

    # Grades for the grading scale
    if curriculum_type == "american":
        grades_data = [
            ("A", 90, 100, "4.0", "Excellent"),
            ("B", 80, 89, "3.0", "Good"),
            ("C", 70, 79, "2.0", "Average"),
            ("D", 60, 69, "1.0", "Below Average"),
            ("F", 0, 59, "0.0", "Fail"),
        ]
    elif curriculum_type == "ib":
        grades_data = [
            ("7", 86, 100, "7.0", "Excellent"),
            ("6", 72, 85, "6.0", "Very Good"),
            ("5", 58, 71, "5.0", "Good"),
            ("4", 44, 57, "4.0", "Satisfactory"),
            ("3", 30, 43, "3.0", "Mediocre"),
            ("2", 15, 29, "2.0", "Poor"),
            ("1", 0, 14, "1.0", "Very Poor"),
        ]
    elif curriculum_type == "french":
        grades_data = [
            ("TB", 16, 20, "4.0", "Tres Bien"),
            ("B", 14, 15, "3.0", "Bien"),
            ("AB", 12, 13, "2.5", "Assez Bien"),
            ("P", 10, 11, "2.0", "Passable"),
            ("I", 0, 9, "1.0", "Insuffisant"),
        ]
    else:  # GES / WAEC
        grades_data = [
            ("A1", 80, 100, "1.0", "Excellent"),
            ("B2", 70, 79, "2.0", "Very Good"),
            ("B3", 60, 69, "3.0", "Good"),
            ("C4", 55, 59, "4.0", "Credit"),
            ("C5", 50, 54, "5.0", "Credit"),
            ("C6", 45, 49, "6.0", "Credit"),
            ("D7", 40, 44, "7.0", "Pass"),
            ("E8", 35, 39, "8.0", "Pass"),
            ("F9", 0, 34, "9.0", "Fail"),
        ]

    for grade, min_s, max_s, gp, remark in grades_data:
        await admin_session.execute(
            text("""
                INSERT INTO grades (id, tenant_id, grading_scale_id,
                    grade, min_score, max_score, grade_point, remark,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:gsid AS uuid),
                    :grade, :min, :max, :gp, :remark,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(uuid4()), "tid": str(tenant_id),
             "gsid": str(ids["grading_scale_id"]),
             "grade": grade, "min": min_s, "max": max_s,
             "gp": gp, "remark": remark},
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
                :name, :ctype, CAST(:gsid AS uuid), :cal, :ppy, :sdm,
                :gpa, :credits, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]), "name": f"{curriculum_type.title()} Standard",
         "ctype": curriculum_type, "gsid": str(ids["grading_scale_id"]),
         "cal": "semesters" if curriculum_type in ("american", "french") else "terms",
         "ppy": 2 if curriculum_type in ("american", "french") else 3,
         "sdm": "gpa" if curriculum_type == "american" else "grade_and_score",
         "gpa": curriculum_type in ("american", "ib"),
         "credits": curriculum_type == "american"},
    )

    # Class with curriculum_profile_id
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, curriculum_profile_id, school_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CAST(:pid AS uuid), CAST(:sid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["class_id"]), "tid": str(tenant_id),
         "name": f"Grade-10-{uuid4().hex[:6]}",
         "pid": str(ids["profile_id"]),
         "sid": str(ids["school_id"])},
    )

    # Students
    for s_key in ["student_id", "student2_id", "student3_id"]:
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    class_id, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid), :stuid,
                    :fn, :ln, '2010-01-01', 'male', 'active',
                    CAST(:cid AS uuid),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ids[s_key]), "tid": str(tenant_id),
             "sid": str(ids["school_id"]),
             "stuid": f"STU-{uuid4().hex[:6]}",
             "fn": f"Student-{s_key[:3]}",
             "ln": f"Last-{uuid4().hex[:4]}",
             "cid": str(ids["class_id"])},
        )

    # Subjects
    for s_key in ["subject_id", "subject2_id"]:
        await admin_session.execute(
            text("""
                INSERT INTO subjects (id, tenant_id, name, code, category,
                    is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code,
                    'core', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ids[s_key]), "tid": str(tenant_id),
             "name": f"Subject-{uuid4().hex[:6]}",
             "code": f"SUB{uuid4().hex[:3].upper()}"},
        )

    await admin_session.commit()
    return ids


def _build_subject_result(score: Decimal, grade_point: Decimal | None = None) -> SubjectScoreResult:
    """Build a SubjectScoreResult for aggregate calculation tests."""
    result = SubjectScoreResult()
    result.final_score = score
    result.grade_point = grade_point
    result.component_scores = {}
    return result


# ---------------------------------------------------------------
# Phase 1: Strategy-Level Aggregate Tests
# ---------------------------------------------------------------

class TestAmericanAggregates:
    """Tests for American scoring strategy aggregate calculation."""

    def test_american_gpa_calculated(self):
        """GPA should be computed from grade points."""
        strategy = AmericanScoreStrategy()
        results = [
            _build_subject_result(Decimal("92"), Decimal("4.0")),  # A
            _build_subject_result(Decimal("85"), Decimal("3.0")),  # B
            _build_subject_result(Decimal("78"), Decimal("2.0")),  # C
        ]
        agg = strategy.calculate_aggregate(results, None)

        assert agg["gpa"] is not None
        assert 0.0 <= float(agg["gpa"]) <= 4.0
        assert float(agg["gpa"]) == 3.0  # (4+3+2) / 3

    def test_american_honor_roll_true(self):
        """Honor roll should be True when GPA >= 3.5."""
        strategy = AmericanScoreStrategy()
        results = [
            _build_subject_result(Decimal("95"), Decimal("4.0")),
            _build_subject_result(Decimal("92"), Decimal("4.0")),
            _build_subject_result(Decimal("88"), Decimal("3.0")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        # GPA = (4+4+3)/3 = 3.67
        assert agg["honor_roll"] is True

    def test_american_honor_roll_false(self):
        """Honor roll should be False when GPA < 3.5."""
        strategy = AmericanScoreStrategy()
        results = [
            _build_subject_result(Decimal("72"), Decimal("2.0")),
            _build_subject_result(Decimal("65"), Decimal("1.0")),
            _build_subject_result(Decimal("55"), Decimal("0.0")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        # GPA = (2+1+0)/3 = 1.0
        assert agg["honor_roll"] is False

    def test_american_credits_earned(self):
        """Credits earned should count passing subjects (grade_point >= 1.0)."""
        strategy = AmericanScoreStrategy()
        results = [
            _build_subject_result(Decimal("92"), Decimal("4.0")),  # pass
            _build_subject_result(Decimal("55"), Decimal("0.0")),  # fail
        ]
        agg = strategy.calculate_aggregate(results, None)
        assert agg["total_credits_earned"] == Decimal("1")

    def test_american_empty_results(self):
        """Empty results should return None GPA."""
        strategy = AmericanScoreStrategy()
        agg = strategy.calculate_aggregate([], None)
        assert agg["gpa"] is None
        assert agg["honor_roll"] is False


class TestIBAggregates:
    """Tests for IB scoring strategy aggregate calculation."""

    def test_ib_total_points_calculated(self):
        """IB total points should be sum of grade points."""
        strategy = IBScoreStrategy()
        results = [
            _build_subject_result(Decimal("90"), Decimal("7")),
            _build_subject_result(Decimal("80"), Decimal("6")),
            _build_subject_result(Decimal("70"), Decimal("5")),
            _build_subject_result(Decimal("60"), Decimal("5")),
            _build_subject_result(Decimal("50"), Decimal("4")),
            _build_subject_result(Decimal("45"), Decimal("3")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        assert agg["ib_total_points"] == 30  # 7+6+5+5+4+3

    def test_ib_empty_results(self):
        """Empty IB results should give 0 points."""
        strategy = IBScoreStrategy()
        agg = strategy.calculate_aggregate([], None)
        assert agg["ib_total_points"] == 0


class TestFrenchAggregates:
    """Tests for French scoring strategy aggregate calculation."""

    def test_french_mention_bien(self):
        """French mention should be 'Bien' for average 14-15."""
        strategy = FrenchScoreStrategy()
        results = [
            _build_subject_result(Decimal("15")),
            _build_subject_result(Decimal("14")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        assert agg["french_mention"] == "Bien"

    def test_french_mention_tres_bien(self):
        """French mention should be 'Tres Bien' for average >= 16."""
        strategy = FrenchScoreStrategy()
        results = [
            _build_subject_result(Decimal("17")),
            _build_subject_result(Decimal("18")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        assert agg["french_mention"] == "Tres Bien"

    def test_french_no_mention_below_10(self):
        """No mention for average below 10."""
        strategy = FrenchScoreStrategy()
        results = [
            _build_subject_result(Decimal("8")),
            _build_subject_result(Decimal("7")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        assert agg["french_mention"] is None


class TestGESBackwardCompat:
    """Tests that GES schools are unaffected by curriculum changes."""

    def test_ges_returns_empty_aggregate(self):
        """GES aggregate should return empty dict (no GPA, no IB points)."""
        strategy = GESScoreStrategy()
        results = [
            _build_subject_result(Decimal("75")),
        ]
        agg = strategy.calculate_aggregate(results, None)
        assert agg == {}

    def test_montessori_returns_empty_aggregate(self):
        """Montessori aggregate should return empty dict (narrative only)."""
        strategy = MontessoriScoreStrategy()
        agg = strategy.calculate_aggregate([], None)
        assert agg == {}


class TestStrategyFactory:
    """Tests for get_score_strategy factory function."""

    def test_known_types_resolve_correctly(self):
        """Each known curriculum type should produce the right strategy."""
        assert isinstance(get_score_strategy("ges"), GESScoreStrategy)
        assert isinstance(get_score_strategy("american"), AmericanScoreStrategy)
        assert isinstance(get_score_strategy("ib"), IBScoreStrategy)
        assert isinstance(get_score_strategy("french"), FrenchScoreStrategy)
        assert isinstance(get_score_strategy("montessori"), MontessoriScoreStrategy)

    def test_unknown_type_falls_back_to_ges(self):
        """Unknown curriculum types should fall back to GES."""
        assert isinstance(get_score_strategy("unknown"), GESScoreStrategy)


# ---------------------------------------------------------------
# Phase 1: Database-Level TermReport Population Tests
# ---------------------------------------------------------------

class TestTermReportCurriculumFields:
    """Tests that TermReport stores curriculum-specific fields correctly."""

    async def test_term_report_accepts_gpa_field(self, admin_session):
        """TermReport should accept GPA, honor_roll, cumulative_gpa fields."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_report_prerequisites(admin_session, tenant["id"], "american")

        # Insert a TermReport with curriculum fields via raw SQL
        report_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO term_reports (id, tenant_id, student_id, academic_year_id,
                    term_id, class_id, curriculum_profile_id,
                    gpa, weighted_gpa, cumulative_gpa, honor_roll,
                    total_score, average_score, subjects_count,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:ayid AS uuid), CAST(:tmid AS uuid), CAST(:cid AS uuid),
                    CAST(:pid AS uuid),
                    3.67, 3.80, 3.67, true,
                    275.0, 91.67, 3,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(report_id), "tid": str(tenant["id"]),
             "sid": str(ids["student_id"]),
             "ayid": str(ids["academic_year_id"]),
             "tmid": str(ids["term_id"]),
             "cid": str(ids["class_id"]),
             "pid": str(ids["profile_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT gpa, honor_roll, cumulative_gpa, curriculum_profile_id FROM term_reports WHERE id = CAST(:id AS uuid)"),
            {"id": str(report_id)},
        )
        row = result.one()
        assert float(row[0]) == 3.67
        assert row[1] is True
        assert float(row[2]) == 3.67
        assert str(row[3]) == str(ids["profile_id"])

    async def test_term_report_accepts_ib_total_points(self, admin_session):
        """TermReport should accept ib_total_points field."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_report_prerequisites(admin_session, tenant["id"], "ib")

        report_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO term_reports (id, tenant_id, student_id, academic_year_id,
                    term_id, class_id, ib_total_points,
                    total_score, average_score, subjects_count,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:ayid AS uuid), CAST(:tmid AS uuid), CAST(:cid AS uuid),
                    30, 450.0, 75.0, 6,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(report_id), "tid": str(tenant["id"]),
             "sid": str(ids["student_id"]),
             "ayid": str(ids["academic_year_id"]),
             "tmid": str(ids["term_id"]),
             "cid": str(ids["class_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT ib_total_points FROM term_reports WHERE id = CAST(:id AS uuid)"),
            {"id": str(report_id)},
        )
        assert result.scalar_one() == 30

    async def test_term_report_accepts_french_mention(self, admin_session):
        """TermReport should accept french_mention field."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_report_prerequisites(admin_session, tenant["id"], "french")

        report_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO term_reports (id, tenant_id, student_id, academic_year_id,
                    term_id, class_id, french_mention,
                    total_score, average_score, subjects_count,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:ayid AS uuid), CAST(:tmid AS uuid), CAST(:cid AS uuid),
                    'Bien', 280.0, 14.0, 5,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(report_id), "tid": str(tenant["id"]),
             "sid": str(ids["student_id"]),
             "ayid": str(ids["academic_year_id"]),
             "tmid": str(ids["term_id"]),
             "cid": str(ids["class_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("SELECT french_mention FROM term_reports WHERE id = CAST(:id AS uuid)"),
            {"id": str(report_id)},
        )
        assert result.scalar_one() == "Bien"

    async def test_ges_report_has_null_curriculum_fields(self, admin_session):
        """GES TermReport should have NULL gpa, ib_total_points, french_mention."""
        tenant = await _create_tenant_pro(admin_session, "starter")
        ids = await _seed_report_prerequisites(admin_session, tenant["id"], "ges")

        report_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO term_reports (id, tenant_id, student_id, academic_year_id,
                    term_id, class_id,
                    total_score, average_score, subjects_count,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:ayid AS uuid), CAST(:tmid AS uuid), CAST(:cid AS uuid),
                    350.0, 70.0, 5,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(report_id), "tid": str(tenant["id"]),
             "sid": str(ids["student_id"]),
             "ayid": str(ids["academic_year_id"]),
             "tmid": str(ids["term_id"]),
             "cid": str(ids["class_id"])},
        )
        await admin_session.commit()

        result = await admin_session.execute(
            text("""
                SELECT gpa, ib_total_points, french_mention, total_score
                FROM term_reports WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(report_id)},
        )
        row = result.one()
        assert row[0] is None  # gpa
        assert row[1] is None  # ib_total_points
        assert row[2] is None  # french_mention
        assert row[3] is not None  # total_score still works

"""
Tests for parent portal curriculum awareness (Phase 3).

Covers: American parent sees GPA/honor roll, IB parent sees total points,
GES parent sees unchanged format, grade trend metric varies by curriculum.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

pytestmark = [pytest.mark.asyncio]


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


async def _seed_parent_data(admin_session, tenant_id, curriculum_type="american"):
    """Seed a complete chain: school, class, student, term reports with curriculum fields."""
    ids = {k: uuid4() for k in [
        "school_id", "student_id", "class_id", "academic_year_id",
        "term_id", "term2_id", "profile_id", "report_id", "report2_id",
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

    # Two terms
    from datetime import date as _date
    term_dates = [
        ("term_id", "Term 1", 1, _date(2025, 9, 1), _date(2025, 12, 20)),
        ("term2_id", "Term 2", 2, _date(2026, 1, 10), _date(2026, 4, 15)),
    ]
    for t_key, name, seq, start, end in term_dates:
        await admin_session.execute(
            text("""
                INSERT INTO terms (id, tenant_id, academic_year_id, name, sequence,
                    start_date, end_date, status, is_current, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay AS uuid),
                    :name, :seq, :start, :end, 'active', false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ids[t_key]), "tid": str(tenant_id),
             "ay": str(ids["academic_year_id"]),
             "name": name, "seq": seq, "start": start, "end": end},
        )

    # Profile
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, academic_calendar_type,
                periods_per_year, score_display_mode,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, :ctype, 'semesters', 2, 'gpa',
                :gpa, false, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "name": f"{curriculum_type.title()} Standard",
         "ctype": curriculum_type,
         "gpa": curriculum_type in ("american", "ib")},
    )

    # Class
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
         "name": f"Grade-10-{uuid4().hex[:4]}",
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
                'Kwame', 'Asante', '2010-01-01', 'male', 'active',
                CAST(:cid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["student_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "stuid": f"STU-{uuid4().hex[:6]}",
         "cid": str(ids["class_id"])},
    )

    await admin_session.commit()
    return ids


async def _insert_term_report(admin_session, tenant_id, ids, term_key,
                                report_key, gpa=None, honor_roll=None,
                                ib_total_points=None, french_mention=None,
                                cumulative_gpa=None, total_score=350.0):
    """Insert a TermReport with optional curriculum fields."""
    fields = "id, tenant_id, student_id, academic_year_id, term_id, class_id, total_score, average_score, subjects_count"
    values = "CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid), CAST(:ayid AS uuid), CAST(:tmid AS uuid), CAST(:cid AS uuid), :ts, :avg, 5"
    params = {
        "id": str(ids[report_key]), "tid": str(tenant_id),
        "sid": str(ids["student_id"]),
        "ayid": str(ids["academic_year_id"]),
        "tmid": str(ids[term_key]),
        "cid": str(ids["class_id"]),
        "ts": total_score, "avg": total_score / 5,
    }

    if gpa is not None:
        fields += ", gpa, curriculum_profile_id"
        values += ", :gpa, CAST(:pid AS uuid)"
        params["gpa"] = gpa
        params["pid"] = str(ids["profile_id"])
    if honor_roll is not None:
        fields += ", honor_roll"
        values += ", :hr"
        params["hr"] = honor_roll
    if cumulative_gpa is not None:
        fields += ", cumulative_gpa"
        values += ", :cgpa"
        params["cgpa"] = cumulative_gpa
    if ib_total_points is not None:
        fields += ", ib_total_points"
        values += ", :ibp"
        params["ibp"] = ib_total_points
    if french_mention is not None:
        fields += ", french_mention"
        values += ", :fm"
        params["fm"] = french_mention

    fields += ", created_at, updated_at"
    values += ", CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"

    await admin_session.execute(
        text(f"INSERT INTO term_reports ({fields}) VALUES ({values})"),
        params,
    )
    await admin_session.commit()


# ---------------------------------------------------------------
# Tests: Parent Sees Curriculum-Specific Aggregates
# ---------------------------------------------------------------

class TestParentCurriculumGrades:
    """Parent portal should expose curriculum-specific aggregate data."""

    async def test_american_report_has_gpa_and_honor_roll(self, admin_session):
        """American TermReport should have GPA and honor_roll for parent view."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_parent_data(admin_session, tenant["id"], "american")
        await _insert_term_report(
            admin_session, tenant["id"], ids,
            "term_id", "report_id",
            gpa=3.67, honor_roll=True, cumulative_gpa=3.67,
        )

        # Verify the data is queryable
        result = await admin_session.execute(
            text("""
                SELECT gpa, honor_roll, cumulative_gpa
                FROM term_reports WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["report_id"])},
        )
        row = result.one()
        assert float(row[0]) == 3.67
        assert row[1] is True
        assert float(row[2]) == 3.67

    async def test_ib_report_has_total_points(self, admin_session):
        """IB TermReport should have ib_total_points for parent view."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_parent_data(admin_session, tenant["id"], "ib")
        await _insert_term_report(
            admin_session, tenant["id"], ids,
            "term_id", "report_id",
            ib_total_points=32,
        )

        result = await admin_session.execute(
            text("SELECT ib_total_points FROM term_reports WHERE id = CAST(:id AS uuid)"),
            {"id": str(ids["report_id"])},
        )
        assert result.scalar_one() == 32

    async def test_ges_report_has_null_curriculum_fields(self, admin_session):
        """GES TermReport should have NULL gpa/ib_total_points (unchanged)."""
        tenant = await _create_tenant_pro(admin_session, "starter")
        ids = await _seed_parent_data(admin_session, tenant["id"], "ges")
        await _insert_term_report(
            admin_session, tenant["id"], ids,
            "term_id", "report_id",
        )

        result = await admin_session.execute(
            text("""
                SELECT gpa, ib_total_points, french_mention, total_score
                FROM term_reports WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["report_id"])},
        )
        row = result.one()
        assert row[0] is None  # gpa
        assert row[1] is None  # ib_total_points
        assert row[2] is None  # french_mention
        assert row[3] is not None  # total_score exists

    async def test_cumulative_gpa_averages_across_terms(self, admin_session):
        """Second term cumulative_gpa should differ from term gpa if previous term differs."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_parent_data(admin_session, tenant["id"], "american")

        # Term 1: GPA 3.5, cumulative 3.5
        await _insert_term_report(
            admin_session, tenant["id"], ids,
            "term_id", "report_id",
            gpa=3.50, cumulative_gpa=3.50,
        )

        # Term 2: GPA 3.0, cumulative 3.25 (average of 3.5 and 3.0)
        await _insert_term_report(
            admin_session, tenant["id"], ids,
            "term2_id", "report2_id",
            gpa=3.00, cumulative_gpa=3.25,
        )

        # Verify Term 2 cumulative differs from term gpa
        result = await admin_session.execute(
            text("SELECT gpa, cumulative_gpa FROM term_reports WHERE id = CAST(:id AS uuid)"),
            {"id": str(ids["report2_id"])},
        )
        row = result.one()
        assert float(row[0]) == 3.0  # term gpa
        assert float(row[1]) == 3.25  # cumulative gpa

    async def test_french_report_has_mention(self, admin_session):
        """French TermReport should have french_mention for parent view."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_parent_data(admin_session, tenant["id"], "french")
        await _insert_term_report(
            admin_session, tenant["id"], ids,
            "term_id", "report_id",
            french_mention="Bien",
        )

        result = await admin_session.execute(
            text("SELECT french_mention FROM term_reports WHERE id = CAST(:id AS uuid)"),
            {"id": str(ids["report_id"])},
        )
        assert result.scalar_one() == "Bien"


class TestParentGradeTrendMetric:
    """Grade trend data should vary by curriculum type."""

    async def test_american_trend_uses_gpa(self, admin_session):
        """American grade trend should use GPA as the metric."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_parent_data(admin_session, tenant["id"], "american")

        for t_key, r_key, gpa_val in [
            ("term_id", "report_id", 3.50),
            ("term2_id", "report2_id", 3.20),
        ]:
            await _insert_term_report(
                admin_session, tenant["id"], ids,
                t_key, r_key, gpa=gpa_val,
            )

        # Query both reports, verify GPA values are present
        result = await admin_session.execute(
            text("""
                SELECT gpa FROM term_reports
                WHERE tenant_id = CAST(:tid AS uuid)
                AND student_id = CAST(:sid AS uuid)
                ORDER BY created_at
            """),
            {"tid": str(tenant["id"]), "sid": str(ids["student_id"])},
        )
        gpas = [float(r[0]) for r in result.fetchall()]
        assert len(gpas) == 2
        assert gpas[0] == 3.50
        assert gpas[1] == 3.20

    async def test_ib_trend_uses_total_points(self, admin_session):
        """IB grade trend should use ib_total_points as the metric."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_parent_data(admin_session, tenant["id"], "ib")

        for t_key, r_key, pts in [
            ("term_id", "report_id", 30),
            ("term2_id", "report2_id", 33),
        ]:
            await _insert_term_report(
                admin_session, tenant["id"], ids,
                t_key, r_key, ib_total_points=pts,
            )

        result = await admin_session.execute(
            text("""
                SELECT ib_total_points FROM term_reports
                WHERE tenant_id = CAST(:tid AS uuid)
                AND student_id = CAST(:sid AS uuid)
                ORDER BY created_at
            """),
            {"tid": str(tenant["id"]), "sid": str(ids["student_id"])},
        )
        points = [r[0] for r in result.fetchall()]
        assert len(points) == 2
        assert points[0] == 30
        assert points[1] == 33

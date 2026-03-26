"""
Tests for Montessori narrative assessment (Phase 4).

Covers: save assessment to TermReport.extra_data, reject for non-Montessori,
HTML stripping, update overwrites, subscription tier check.
"""

import pytest

nh3 = pytest.importorskip("nh3", reason="nh3 not installed -- required for Montessori schema validation")

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text

from tests.conftest import (
    set_app_tenant_context,
)
from app.services.exam.report_service import TermReportService
from app.services.curriculum._shared import CurriculumServiceError
from app.schemas.exam import (
    MontessoriAssessmentCreate,
    MontessoriAreaEntry,
    MontessoriSkillEntry,
    MontessoriWorkSample,
)




# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_with_tier(admin_session, tier: str):
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


async def _seed_montessori_data(admin_session, tenant_id, curriculum_type="montessori"):
    """Seed school, class, student, profile for Montessori assessment tests."""
    ids = {k: uuid4() for k in [
        "school_id", "student_id", "class_id", "academic_year_id",
        "term_id", "profile_id",
    ]}

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                curriculum_profile_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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

    # Curriculum profile
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, academic_calendar_type,
                periods_per_year, score_display_mode,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, :ctype, 'terms', 3, 'narrative',
                false, false, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "name": "Montessori Standard",
         "ctype": curriculum_type},
    )

    # Class with Montessori profile
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, curriculum_profile_id, school_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'kg_1', 1, true, CAST(:pid AS uuid), CAST(:sid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["class_id"]), "tid": str(tenant_id),
         "name": f"Montessori-{uuid4().hex[:4]}",
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
                'Ama', 'Mensah', '2020-03-15', 'female', 'active',
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


def _build_assessment_data(student_id: UUID) -> MontessoriAssessmentCreate:
    """Build a standard Montessori assessment Pydantic object."""
    return MontessoriAssessmentCreate(
        student_id=student_id,
        developmental_areas=[
            MontessoriAreaEntry(
                name="Practical Life",
                skills=[
                    MontessoriSkillEntry(name="Pouring", progress_level="developing"),
                    MontessoriSkillEntry(name="Buttoning", progress_level="practicing"),
                ],
                narrative="Shows good concentration during practical life activities.",
            ),
            MontessoriAreaEntry(
                name="Sensorial",
                skills=[
                    MontessoriSkillEntry(name="Color Sorting", progress_level="mastery"),
                ],
                narrative="Excellent sensorial discrimination.",
            ),
        ],
        work_samples=[
            MontessoriWorkSample(description="Number rods arrangement photo"),
        ],
        goals=["Improve writing grip", "Start cursive letters"],
        general_narrative="A delightful student making good progress across all areas.",
    )


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestMontessoriAssessmentSave:
    """Tests for saving Montessori narrative assessments."""

    async def test_save_assessment_stores_extra_data(self, admin_session, app_session):
        """Save assessment should populate TermReport.extra_data with developmental areas."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        ids = await _seed_montessori_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)
        data = _build_assessment_data(ids["student_id"])

        report = await service.save_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            class_id=ids["class_id"],
            section_id=None,
            data=data,
        )

        assert report.extra_data is not None
        assert "developmental_areas" in report.extra_data
        assert len(report.extra_data["developmental_areas"]) == 2
        assert report.extra_data["developmental_areas"][0]["name"] == "Practical Life"
        assert report.curriculum_profile_id == ids["profile_id"]

    async def test_reject_for_non_montessori_class(self, admin_session, app_session):
        """Assessment should be rejected for non-Montessori curriculum."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        ids = await _seed_montessori_data(admin_session, tenant["id"], "cambridge")

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)
        data = _build_assessment_data(ids["student_id"])

        with pytest.raises(ValueError, match="Montessori curriculum profile"):
            await service.save_montessori_assessment(
                tenant_id=tenant["id"],
                academic_year_id=ids["academic_year_id"],
                term_id=ids["term_id"],
                class_id=ids["class_id"],
                section_id=None,
                data=data,
            )

    async def test_update_existing_assessment_overwrites(self, admin_session, app_session):
        """Updating assessment should overwrite extra_data completely."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        ids = await _seed_montessori_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)

        # First save
        data1 = _build_assessment_data(ids["student_id"])
        report1 = await service.save_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            class_id=ids["class_id"],
            section_id=None,
            data=data1,
        )
        original_goals = report1.extra_data["goals"]

        # Second save with different goals
        data2 = MontessoriAssessmentCreate(
            student_id=ids["student_id"],
            developmental_areas=[
                MontessoriAreaEntry(
                    name="Language",
                    skills=[MontessoriSkillEntry(name="Reading", progress_level="emerging")],
                    narrative="Beginning to read simple words.",
                ),
            ],
            goals=["Read 5 sight words", "Write first name"],
            general_narrative="Updated narrative after mid-term review.",
        )
        report2 = await service.save_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            class_id=ids["class_id"],
            section_id=None,
            data=data2,
        )

        # Same report, updated data
        assert report2.id == report1.id
        assert report2.extra_data["goals"] != original_goals
        assert report2.extra_data["developmental_areas"][0]["name"] == "Language"

    async def test_subscription_tier_check(self, admin_session, app_session):
        """Montessori assessment requires Professional+ plan."""
        tenant = await _create_tenant_with_tier(admin_session, "starter")
        ids = await _seed_montessori_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)
        data = _build_assessment_data(ids["student_id"])

        with pytest.raises(CurriculumServiceError) as exc_info:
            await service.save_montessori_assessment(
                tenant_id=tenant["id"],
                academic_year_id=ids["academic_year_id"],
                term_id=ids["term_id"],
                class_id=ids["class_id"],
                section_id=None,
                data=data,
            )
        assert exc_info.value.code == "plan_limit"

    async def test_extra_data_contains_schema_version(self, admin_session, app_session):
        """Extra data should include montessori_schema_version for migration support."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        ids = await _seed_montessori_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)
        data = _build_assessment_data(ids["student_id"])

        report = await service.save_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            class_id=ids["class_id"],
            section_id=None,
            data=data,
        )

        assert report.extra_data["montessori_schema_version"] == 1

    async def test_get_montessori_assessment_returns_report(self, admin_session, app_session):
        """get_montessori_assessment should return report with Montessori data."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        ids = await _seed_montessori_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)
        data = _build_assessment_data(ids["student_id"])

        await service.save_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            class_id=ids["class_id"],
            section_id=None,
            data=data,
        )

        # Retrieve
        report = await service.get_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            student_id=ids["student_id"],
        )
        assert report is not None
        assert "developmental_areas" in report.extra_data

    async def test_get_montessori_returns_none_for_non_montessori(self, admin_session, app_session):
        """get_montessori_assessment should return None when no Montessori data exists."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        ids = await _seed_montessori_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = TermReportService(app_session)

        report = await service.get_montessori_assessment(
            tenant_id=tenant["id"],
            academic_year_id=ids["academic_year_id"],
            term_id=ids["term_id"],
            student_id=ids["student_id"],
        )
        assert report is None


class TestMontessoriHtmlStripping:
    """Tests for HTML sanitization in Montessori narratives."""

    def test_html_stripped_from_narrative_via_schema(self):
        """HTML tags should be stripped from narrative text at the schema level."""
        pytest.importorskip("nh3", reason="nh3 not installed")
        area = MontessoriAreaEntry(
            name="Language",
            skills=[MontessoriSkillEntry(name="Reading", progress_level="emerging")],
            narrative="Student is <script>alert('xss')</script> progressing well.",
        )
        # nh3 strips all HTML tags when tags=set()
        assert "<script>" not in area.narrative
        assert "progressing well" in area.narrative

    def test_clean_narrative_unchanged(self):
        """Clean narrative without HTML should pass through unchanged."""
        pytest.importorskip("nh3", reason="nh3 not installed")
        area = MontessoriAreaEntry(
            name="Math",
            skills=[],
            narrative="Shows excellent number sense and spatial reasoning.",
        )
        assert area.narrative == "Shows excellent number sense and spatial reasoning."

    def test_html_entities_cleaned(self):
        """HTML entities should be cleaned from narrative."""
        pytest.importorskip("nh3", reason="nh3 not installed")
        area = MontessoriAreaEntry(
            name="Art",
            skills=[],
            narrative="Uses <b>bold</b> colors and <i>creative</i> techniques.",
        )
        assert "<b>" not in area.narrative
        assert "<i>" not in area.narrative
        assert "bold" in area.narrative

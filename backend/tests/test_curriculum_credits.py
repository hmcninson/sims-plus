"""
Tests for CreditService.

Covers: record_credit (create/upsert), GPA calculation (credit-weighted),
AP/Honors bonuses, honor roll, _score_to_grade_points, transcript generation,
and CSS injection prevention.
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

from app.services.curriculum.credit_service import CreditService
from app.services.curriculum._shared import CurriculumServiceError
from app.schemas.curriculum import StudentCreditRecordCreate


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


async def _seed_credit_prerequisites(admin_session, tenant_id):
    """Seed school, student, academic_year, subject, curriculum_profile."""
    school_id = uuid4()
    student_id = uuid4()
    academic_year_id = uuid4()
    subject_id = uuid4()
    subject2_id = uuid4()
    profile_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
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
        {"id": str(academic_year_id), "tid": str(tenant_id),
         "name": f"AY-{uuid4().hex[:6]}"},
    )

    class_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id),
         "name": f"Class-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status, class_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :student_id, 'Alice', 'Smith', '2008-03-15', 'female', 'active',
                CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
         "student_id": f"STU-{uuid4().hex[:6]}", "cid": str(class_id)},
    )

    for sid, name, code in [
        (subject_id, "Mathematics", f"MTH{uuid4().hex[:4]}".upper()),
        (subject2_id, "English", f"ENG{uuid4().hex[:4]}".upper()),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO subjects (id, tenant_id, name, code, category,
                    is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code,
                    'core', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(sid), "tid": str(tenant_id), "name": name, "code": code},
        )

    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (
                id, tenant_id, school_id, name, curriculum_type,
                academic_calendar_type, periods_per_year,
                score_display_mode, show_position, show_class_average,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, config,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'American Standard', 'american', 'semesters', 2, 'gpa',
                false, true, true, true, false, false, true,
                '{"graduation_credits_required": 24, "honor_roll_threshold": 3.5}'::jsonb,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(profile_id), "tid": str(tenant_id), "sid": str(school_id)},
    )

    return {
        "school_id": school_id,
        "student_id": student_id,
        "academic_year_id": academic_year_id,
        "subject_id": subject_id,
        "subject2_id": subject2_id,
        "profile_id": profile_id,
    }


class TestRecordCredit:
    """Test credit record creation and upsert."""

    async def test_create_new_credit_record(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        data = StudentCreditRecordCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            curriculum_profile_id=prereqs["profile_id"],
            academic_year_id=prereqs["academic_year_id"],
            credits_attempted=Decimal("4.0"),
            credits_earned=Decimal("4.0"),
            grade_points=Decimal("4.0"),
            is_ap=False,
            is_honors=False,
        )
        record = await svc.record_credit(tenant["id"], prereqs["school_id"], data)

        assert record.credits_attempted == Decimal("4.0")
        assert record.credits_earned == Decimal("4.0")
        assert record.grade_points == Decimal("4.0")

    async def test_upsert_existing_credit_record(self, app_session, admin_session):
        """Second call with same student/subject/year/term updates in place."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        data = StudentCreditRecordCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            curriculum_profile_id=prereqs["profile_id"],
            academic_year_id=prereqs["academic_year_id"],
            credits_attempted=Decimal("4.0"),
            credits_earned=Decimal("4.0"),
            grade_points=Decimal("3.0"),
        )
        first = await svc.record_credit(tenant["id"], prereqs["school_id"], data)
        first_id = first.id

        # Update grade_points
        data2 = StudentCreditRecordCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            curriculum_profile_id=prereqs["profile_id"],
            academic_year_id=prereqs["academic_year_id"],
            credits_attempted=Decimal("4.0"),
            credits_earned=Decimal("4.0"),
            grade_points=Decimal("4.0"),
        )
        second = await svc.record_credit(tenant["id"], prereqs["school_id"], data2)

        assert second.id == first_id  # Same record, updated
        assert second.grade_points == Decimal("4.0")


class TestGPACalculation:
    """Test credit-weighted GPA calculation."""

    async def test_gpa_is_credit_weighted_not_simple_average(self, app_session, admin_session):
        """4-credit A (4.0) + 1-credit C (2.0) = 3.6 GPA, NOT 3.0."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        # 4-credit subject with A (4.0 GP)
        await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("4.0"),
                credits_earned=Decimal("4.0"),
                grade_points=Decimal("4.0"),
            ),
        )

        # 1-credit subject with C (2.0 GP)
        await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject2_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("1.0"),
                credits_earned=Decimal("1.0"),
                grade_points=Decimal("2.0"),
            ),
        )

        gpa_data = await svc.get_student_gpa(
            tenant["id"], prereqs["student_id"], prereqs["profile_id"],
        )

        # Weighted: (4.0*4 + 2.0*1) / (4+1) = 18/5 = 3.60
        assert gpa_data["cumulative_gpa"] == Decimal("3.60")

    async def test_ap_bonus_capped_at_5(self, app_session, admin_session):
        """AP courses get +1.0 bonus, capped at 5.0."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        record = await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("4.0"),
                credits_earned=Decimal("4.0"),
                grade_points=Decimal("4.0"),
                is_ap=True,
            ),
        )

        # 4.0 + 1.0 = 5.0 (at cap)
        assert record.weighted_grade_points == Decimal("5.0")

    async def test_honors_bonus_capped_at_4_5(self, app_session, admin_session):
        """Honors courses get +0.5 bonus, capped at 4.5."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        record = await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("4.0"),
                credits_earned=Decimal("4.0"),
                grade_points=Decimal("4.0"),
                is_honors=True,
            ),
        )

        # 4.0 + 0.5 = 4.5 (at cap)
        assert record.weighted_grade_points == Decimal("4.5")

    async def test_honor_roll_threshold(self, app_session, admin_session):
        """Weighted GPA >= 3.5 qualifies for honor roll."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("4.0"),
                credits_earned=Decimal("4.0"),
                grade_points=Decimal("3.5"),
                weighted_grade_points=Decimal("3.5"),
            ),
        )

        gpa_data = await svc.get_student_gpa(
            tenant["id"], prereqs["student_id"], prereqs["profile_id"],
        )
        assert gpa_data["honor_roll"] is True


class TestScoreToGradePoints:
    """Test the static _score_to_grade_points method."""

    @pytest.mark.parametrize("score,expected", [
        (Decimal("95"), Decimal("4.0")),   # A range
        (Decimal("90"), Decimal("4.0")),   # A boundary
        (Decimal("87"), Decimal("3.5")),   # B+ range
        (Decimal("82"), Decimal("3.0")),   # B range
        (Decimal("76"), Decimal("2.5")),   # C+ range
        (Decimal("71"), Decimal("2.0")),   # C range
        (Decimal("67"), Decimal("1.5")),   # D+ range
        (Decimal("62"), Decimal("1.0")),   # D range
        (Decimal("55"), Decimal("0.0")),   # F range
        (Decimal("0"), Decimal("0.0")),    # Zero
    ])
    def test_score_to_grade_points(self, score, expected):
        assert CreditService._score_to_grade_points(score) == expected


class TestTranscript:
    """Test transcript data generation."""

    async def test_transcript_basic_structure(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("4.0"),
                credits_earned=Decimal("4.0"),
                grade_points=Decimal("3.5"),
            ),
        )

        transcript = await svc.generate_transcript_data(
            tenant["id"], prereqs["student_id"], prereqs["profile_id"],
            school_id=prereqs["school_id"],
        )

        assert transcript["student_id"] == prereqs["student_id"]
        assert transcript["student_name"] == "Alice Smith"
        assert transcript["curriculum_profile"] == "American Standard"
        assert transcript["total_credits_earned"] == Decimal("4.0")
        assert len(transcript["academic_records"]) == 1
        assert transcript["graduation_credits_required"] == Decimal("24")
        assert transcript["credits_remaining"] == Decimal("20")

    async def test_transcript_css_injection_prevention(self, app_session, admin_session):
        """primary_color that isn't valid hex is sanitized to None."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_credit_prerequisites(admin_session, tenant["id"])

        # Set an invalid (non-hex) primary_color on the school
        # VARCHAR(7) so we use a 7-char string that fails the #RRGGBB regex
        await admin_session.execute(
            text("""
                UPDATE schools SET primary_color = '#GGG000'
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(prereqs["school_id"])},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditService(app_session)

        await svc.record_credit(
            tenant["id"], prereqs["school_id"],
            StudentCreditRecordCreate(
                student_id=prereqs["student_id"],
                subject_id=prereqs["subject_id"],
                curriculum_profile_id=prereqs["profile_id"],
                academic_year_id=prereqs["academic_year_id"],
                credits_attempted=Decimal("1.0"),
                credits_earned=Decimal("1.0"),
                grade_points=Decimal("3.0"),
            ),
        )

        transcript = await svc.generate_transcript_data(
            tenant["id"], prereqs["student_id"], prereqs["profile_id"],
            school_id=prereqs["school_id"],
        )

        # Malicious color should be sanitized to None
        assert transcript["school"]["primary_color"] is None

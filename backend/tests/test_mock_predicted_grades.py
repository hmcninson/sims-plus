"""
Tests for mock exam to predicted grade generation (Phase 5).

Covers: published mock generates predictions, reject non-mock,
reject unpublished, update existing auto-generated, skip manual predictions,
skip absent students.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import selectinload

from tests.conftest import (
    set_app_tenant_context,
)
from app.services.exam.exam_service import ExamService, ExamServiceError

pytestmark = [pytest.mark.asyncio]


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


async def _seed_mock_exam_data(admin_session, tenant_id, exam_type="mock",
                                 exam_status="results_published"):
    """Seed school, class, students, grading scale, profile, exam, scores."""
    ids = {k: uuid4() for k in [
        "school_id", "student_id", "student2_id", "absent_student_id",
        "class_id", "academic_year_id", "term_id",
        "grading_scale_id", "profile_id", "subject_id",
        "exam_id", "exam_subject_id",
        "user_id",
    ]}

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'shs', 'active', 'STU', 'STF', true,
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

    # Grading scale + grades
    await admin_session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, scale_type,
                is_default, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Cambridge Scale', 'cambridge',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["grading_scale_id"]), "tid": str(tenant_id)},
    )
    for grade, min_s, max_s, gp in [("A*", 90, 100, "9.0"), ("A", 80, 89, "8.0"),
                                      ("B", 70, 79, "7.0"), ("C", 60, 69, "6.0"),
                                      ("D", 50, 59, "5.0"), ("U", 0, 49, "0.0")]:
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

    # Profile
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, grading_scale_id, academic_calendar_type,
                periods_per_year, score_display_mode,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Cambridge IGCSE', 'cambridge', CAST(:gsid AS uuid), 'terms', 3,
                'grade_and_score', false, false, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "gsid": str(ids["grading_scale_id"])},
    )

    # Class with curriculum profile
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

    # Students
    for s_key, fn in [("student_id", "Alice"), ("student2_id", "Bob"),
                       ("absent_student_id", "Charlie")]:
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    class_id, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid), :stuid,
                    :fn, 'Test', '2008-01-01', 'male', 'active',
                    CAST(:cid AS uuid),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ids[s_key]), "tid": str(tenant_id),
             "sid": str(ids["school_id"]),
             "stuid": f"STU-{uuid4().hex[:6]}",
             "fn": fn,
             "cid": str(ids["class_id"])},
        )

    # User (exam creator)
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Teacher', 'One', 'teacher', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["user_id"]), "tid": str(tenant_id),
         "email": f"teacher-{uuid4().hex[:8]}@example.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash"},
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
                :name, :etype, :estatus,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["exam_id"]), "tid": str(tenant_id),
         "ayid": str(ids["academic_year_id"]),
         "tmid": str(ids["term_id"]),
         "name": f"Mock-{uuid4().hex[:6]}",
         "etype": exam_type, "estatus": exam_status},
    )

    # Exam subject
    await admin_session.execute(
        text("""
            INSERT INTO exam_subjects (id, tenant_id, exam_id, subject_id,
                class_id, max_score, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:eid AS uuid), CAST(:sid AS uuid),
                CAST(:cid AS uuid), 100, 'published',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["exam_subject_id"]), "tid": str(tenant_id),
         "eid": str(ids["exam_id"]),
         "sid": str(ids["subject_id"]),
         "cid": str(ids["class_id"])},
    )

    # Scores: student_id=85, student2_id=72, absent_student=absent
    for s_key, score, is_absent in [
        ("student_id", 85.0, False),
        ("student2_id", 72.0, False),
        ("absent_student_id", None, True),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO exam_scores (id, tenant_id, exam_subject_id, student_id,
                    score, is_absent, grade,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:esid AS uuid), CAST(:sid AS uuid),
                    :score, :absent, :grade,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(uuid4()), "tid": str(tenant_id),
             "esid": str(ids["exam_subject_id"]),
             "sid": str(ids[s_key]),
             "score": score, "absent": is_absent,
             "grade": "A" if score and score >= 80 else ("B" if score and score >= 70 else None)},
        )

    await admin_session.commit()
    return ids


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestMockToPredictedGrades:
    """Tests for generate_predicted_grades_from_mock."""

    async def test_published_mock_generates_predictions(self, admin_session, app_session):
        """Published mock exam should generate predicted grades."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_mock_exam_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = ExamService(app_session)

        result = await service.generate_predicted_grades_from_mock(
            tenant_id=tenant["id"],
            exam_id=ids["exam_id"],
            predicted_by=ids["user_id"],
        )

        assert result["created"] > 0

    async def test_reject_non_mock_exam(self, admin_session, app_session):
        """Non-mock exams should be rejected."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_mock_exam_data(
            admin_session, tenant["id"],
            exam_type="end_term", exam_status="results_published",
        )

        await set_app_tenant_context(app_session, tenant["id"])
        service = ExamService(app_session)

        with pytest.raises(ExamServiceError) as exc_info:
            await service.generate_predicted_grades_from_mock(
                tenant_id=tenant["id"],
                exam_id=ids["exam_id"],
                predicted_by=ids["user_id"],
            )
        assert exc_info.value.code == "invalid_type"

    async def test_reject_unpublished_mock(self, admin_session, app_session):
        """Unpublished mock results should be rejected."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_mock_exam_data(
            admin_session, tenant["id"],
            exam_type="mock", exam_status="completed",
        )

        await set_app_tenant_context(app_session, tenant["id"])
        service = ExamService(app_session)

        with pytest.raises(ExamServiceError) as exc_info:
            await service.generate_predicted_grades_from_mock(
                tenant_id=tenant["id"],
                exam_id=ids["exam_id"],
                predicted_by=ids["user_id"],
            )
        assert exc_info.value.code == "invalid_status"

    async def test_absent_students_skipped(self, admin_session, app_session):
        """Absent students should be skipped in prediction generation."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_mock_exam_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = ExamService(app_session)

        result = await service.generate_predicted_grades_from_mock(
            tenant_id=tenant["id"],
            exam_id=ids["exam_id"],
            predicted_by=ids["user_id"],
        )

        # 3 students: 2 with scores, 1 absent
        assert result["skipped"] >= 1
        assert result["created"] == 2

    async def test_existing_auto_generated_predictions_updated(self, admin_session, app_session):
        """Running twice should update existing auto-generated predictions."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_mock_exam_data(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        service = ExamService(app_session)

        # First run
        result1 = await service.generate_predicted_grades_from_mock(
            tenant_id=tenant["id"],
            exam_id=ids["exam_id"],
            predicted_by=ids["user_id"],
        )
        assert result1["created"] == 2

        # Second run should update, not create duplicates
        result2 = await service.generate_predicted_grades_from_mock(
            tenant_id=tenant["id"],
            exam_id=ids["exam_id"],
            predicted_by=ids["user_id"],
        )
        assert result2["updated"] == 2
        assert result2["created"] == 0

    async def test_manual_predictions_not_overwritten(self, admin_session, app_session):
        """Manually-set predictions should NOT be overwritten (H2 fix)."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_mock_exam_data(admin_session, tenant["id"])

        # Insert a manual prediction for student_id
        manual_pg_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO predicted_grades (id, tenant_id, student_id, subject_id,
                    academic_year_id, term_id,
                    predicted_grade, predicted_score, notes,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid), CAST(:subid AS uuid),
                    CAST(:ayid AS uuid), CAST(:tmid AS uuid),
                    'A*', 95.0, 'Manually set by teacher',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(manual_pg_id), "tid": str(tenant["id"]),
             "sid": str(ids["student_id"]),
             "subid": str(ids["subject_id"]),
             "ayid": str(ids["academic_year_id"]),
             "tmid": str(ids["term_id"])},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = ExamService(app_session)

        result = await service.generate_predicted_grades_from_mock(
            tenant_id=tenant["id"],
            exam_id=ids["exam_id"],
            predicted_by=ids["user_id"],
        )

        # Manual prediction should be skipped, only student2_id should be created
        assert result["skipped"] >= 2  # absent + manual
        assert result["created"] == 1  # only student2_id

        # Verify manual prediction is unchanged
        check = await admin_session.execute(
            text("""
                SELECT predicted_grade, notes FROM predicted_grades
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(manual_pg_id)},
        )
        row = check.one()
        assert row[0] == "A*"
        assert row[1] == "Manually set by teacher"

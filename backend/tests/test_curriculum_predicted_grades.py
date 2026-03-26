"""
Tests for PredictedGradeService.

Covers: create prediction, plan limits, update with immutable fields skipped,
bulk create (incl. limit), soft delete, and auto-set of predicted_by/predicted_at.
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

from app.services.curriculum.predicted_grade_service import PredictedGradeService
from app.services.curriculum._shared import CurriculumServiceError
from app.schemas.curriculum import (
    PredictedGradeCreate,
    PredictedGradeUpdate,
    BulkPredictedGradeCreate,
)

pytestmark = [pytest.mark.asyncio]


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


async def _seed_prerequisites(admin_session, tenant_id):
    """Seed school, student, user, academic_year, subject."""
    school_id = uuid4()
    student_id = uuid4()
    user_id = uuid4()
    academic_year_id = uuid4()
    subject_id = uuid4()
    class_id = uuid4()

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
                :student_id, 'Test', 'Student', '2008-03-15', 'male', 'active',
                CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
         "student_id": f"STU-{uuid4().hex[:6]}", "cid": str(class_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email,
                '$argon2id$v=19$m=65536,t=2,p=1$fake_hash',
                'Teacher', 'One', 'teacher', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"teacher-{uuid4().hex[:6]}@test.com"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO subjects (id, tenant_id, name, code, category,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code,
                'core', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(subject_id), "tid": str(tenant_id),
         "name": f"Maths-{uuid4().hex[:6]}", "code": f"MTH{uuid4().hex[:4]}".upper()},
    )

    return {
        "school_id": school_id,
        "student_id": student_id,
        "user_id": user_id,
        "academic_year_id": academic_year_id,
        "subject_id": subject_id,
    }


class TestCreatePrediction:
    """Test predicted grade creation."""

    async def test_create_prediction_happy_path(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        data = PredictedGradeCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            academic_year_id=prereqs["academic_year_id"],
            predicted_grade="A*",
            target_grade="A",
            predicted_score=Decimal("92.5"),
            notes="Strong performance",
        )
        prediction = await svc.create_prediction(
            tenant["id"], prereqs["school_id"], prereqs["user_id"], data,
        )

        assert prediction.predicted_grade == "A*"
        assert prediction.target_grade == "A"
        assert prediction.predicted_by == prereqs["user_id"]
        assert prediction.predicted_at is not None
        assert prediction.school_id == prereqs["school_id"]

    async def test_trial_tenant_blocked(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)  # trial
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        data = PredictedGradeCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            academic_year_id=prereqs["academic_year_id"],
            predicted_grade="A",
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_prediction(
                tenant["id"], prereqs["school_id"], prereqs["user_id"], data,
            )
        assert exc.value.code == "plan_limit"

    async def test_starter_tenant_blocked(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "starter")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        data = PredictedGradeCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            academic_year_id=prereqs["academic_year_id"],
            predicted_grade="A",
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_prediction(
                tenant["id"], prereqs["school_id"], prereqs["user_id"], data,
            )
        assert exc.value.code == "plan_limit"


class TestUpdatePrediction:
    """Test prediction updates."""

    async def test_update_mutable_fields(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        data = PredictedGradeCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            academic_year_id=prereqs["academic_year_id"],
            predicted_grade="B",
        )
        prediction = await svc.create_prediction(
            tenant["id"], prereqs["school_id"], prereqs["user_id"], data,
        )
        prediction_id = prediction.id
        original_predicted_at = prediction.predicted_at

        updated = await svc.update_prediction(
            tenant["id"], prediction_id, prereqs["user_id"],
            PredictedGradeUpdate(predicted_grade="A*", notes="Improved"),
        )

        assert updated.predicted_grade == "A*"
        assert updated.notes == "Improved"
        # predicted_at should be refreshed
        assert updated.predicted_at >= original_predicted_at
        assert updated.predicted_by == prereqs["user_id"]

    async def test_immutable_fields_skipped_on_update(self, app_session, admin_session):
        """student_id, subject_id, academic_year_id cannot change via update."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        data = PredictedGradeCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            academic_year_id=prereqs["academic_year_id"],
            predicted_grade="B",
        )
        prediction = await svc.create_prediction(
            tenant["id"], prereqs["school_id"], prereqs["user_id"], data,
        )
        prediction_id = prediction.id
        original_student_id = prediction.student_id

        # PredictedGradeUpdate schema only has mutable fields,
        # so immutable fields can't even be passed. Verify the service
        # pattern by checking the prediction is unchanged after update.
        updated = await svc.update_prediction(
            tenant["id"], prediction_id, prereqs["user_id"],
            PredictedGradeUpdate(predicted_grade="A"),
        )
        assert updated.student_id == original_student_id


class TestDeletePrediction:
    """Test prediction soft deletion."""

    async def test_soft_delete(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        data = PredictedGradeCreate(
            student_id=prereqs["student_id"],
            subject_id=prereqs["subject_id"],
            academic_year_id=prereqs["academic_year_id"],
            predicted_grade="A",
        )
        prediction = await svc.create_prediction(
            tenant["id"], prereqs["school_id"], prereqs["user_id"], data,
        )
        prediction_id = prediction.id

        await svc.delete_prediction(tenant["id"], prediction_id)

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.get_prediction(tenant["id"], prediction_id)
        assert exc.value.code == "not_found"


class TestBulkCreatePredictions:
    """Test bulk prediction creation."""

    async def test_bulk_create_happy_path(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        predictions_data = BulkPredictedGradeCreate(
            predictions=[
                PredictedGradeCreate(
                    student_id=prereqs["student_id"],
                    subject_id=prereqs["subject_id"],
                    academic_year_id=prereqs["academic_year_id"],
                    predicted_grade="A",
                ),
            ],
        )
        results = await svc.bulk_create_predictions(
            tenant["id"], prereqs["school_id"], prereqs["user_id"],
            predictions_data,
        )
        assert len(results) == 1
        assert results[0].predicted_by == prereqs["user_id"]
        assert results[0].predicted_at is not None

    async def test_bulk_create_over_200_fails(self, app_session, admin_session):
        """Bulk create with >200 predictions should fail."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_prerequisites(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = PredictedGradeService(app_session)

        # The schema itself has max_length=200, so we test the service-level check
        # by passing a list that somehow bypasses schema validation (e.g., direct call)
        class FakeBulk:
            predictions = [
                PredictedGradeCreate(
                    student_id=prereqs["student_id"],
                    subject_id=prereqs["subject_id"],
                    academic_year_id=prereqs["academic_year_id"],
                    predicted_grade="A",
                )
                for _ in range(201)
            ]

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.bulk_create_predictions(
                tenant["id"], prereqs["school_id"], prereqs["user_id"],
                FakeBulk(),
            )
        assert exc.value.code == "validation_error"

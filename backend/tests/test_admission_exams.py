"""
Tests for EntranceExamService.

Covers: create, register applicants, record results (upsert), capacity,
status transitions, tenant isolation. Uses two-engine pattern.
"""

import pytest
import secrets
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_exam_prereqs(admin_session, tenant_id):
    """Seed school, year, class, period, and 3 shortlisted applications.
    Returns dict with all IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), :name, '2025-01-01', '2027-12-31', 'open',
                0, false, true, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Scorer', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"scorer-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    # 3 shortlisted applications
    app_ids = []
    for i in range(3):
        app_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                    tracking_code, applicant_first_name, applicant_last_name,
                    date_of_birth, gender, target_class_id, status,
                    custom_fields, fee_waived, exam_waived, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid), :tc, :fn, 'Exam',
                    '2012-01-01', 'male', CAST(:cid AS uuid), 'shortlisted',
                    '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(app_id), "tid": str(tenant_id),
                "sid": str(school_id), "pid": str(period_id),
                "tc": secrets.token_urlsafe(48), "cid": str(class_id),
                "fn": f"Applicant-{i}",
            },
        )
        app_ids.append(app_id)

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "class_id": class_id, "app_ids": app_ids, "user_id": user_id,
    }


# --- Tests ---


async def test_create_exam_session(app_session, admin_session):
    """Create exam with valid data. Defaults: status=scheduled."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Entrance Exam Batch 1", exam_date=date(2026, 7, 15),
        venue="Main Hall", capacity=50,
    )
    assert exam.status == "scheduled"
    assert exam.name == "Entrance Exam Batch 1"
    assert exam.capacity == 50


async def test_register_applicants(app_session, admin_session):
    """Register 3 shortlisted applicants -> status becomes EXAM_SCHEDULED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Reg Test", exam_date=date(2026, 7, 15),
        venue="Hall A", capacity=10,
    )

    result = await svc.register_applicants(
        tenant["id"], exam.id, prereqs["app_ids"],
    )
    assert result["registered_count"] == 3
    assert len(result["errors"]) == 0

    # Verify application statuses changed
    for app_id in prereqs["app_ids"]:
        r = await app_session.execute(
            text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
            {"id": str(app_id)},
        )
        assert r.scalar() == "exam_scheduled"


async def test_register_exceeds_capacity(app_session, admin_session):
    """Capacity=2, register 3 -> only 2 succeed, 1 error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Cap Test", exam_date=date(2026, 7, 15),
        venue="Small Room", capacity=2,
    )

    result = await svc.register_applicants(
        tenant["id"], exam.id, prereqs["app_ids"],
    )
    assert result["registered_count"] == 2
    assert len(result["errors"]) == 1
    assert "capacity" in result["errors"][0]["error"].lower()


async def test_register_duplicate_prevented(app_session, admin_session):
    """Register same applicant twice -> second is already_registered."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Dup Test", exam_date=date(2026, 7, 15),
        venue="Hall B", capacity=10,
    )

    # First registration
    await svc.register_applicants(tenant["id"], exam.id, [prereqs["app_ids"][0]])

    # Second registration of same applicant
    result = await svc.register_applicants(tenant["id"], exam.id, [prereqs["app_ids"][0]])
    assert result["registered_count"] == 0
    assert result["already_registered_count"] == 1


async def test_submit_exam_results(app_session, admin_session):
    """Submit results for registered applicants. Transition to EXAM_COMPLETED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Result Test", exam_date=date(2026, 7, 15),
        venue="Hall C", capacity=10,
    )

    # Register applicants
    await svc.register_applicants(tenant["id"], exam.id, prereqs["app_ids"])

    # Move exam to in_progress (required for recording results)
    await svc.update_status(tenant["id"], exam.id, "in_progress")

    # Record results
    results = [
        {"application_id": str(prereqs["app_ids"][0]), "score": 85, "max_score": 100, "passed": True},
        {"application_id": str(prereqs["app_ids"][1]), "score": 60, "max_score": 100, "passed": True},
        {"application_id": str(prereqs["app_ids"][2]), "score": 30, "max_score": 100, "passed": False},
    ]
    count = await svc.record_results(
        tenant["id"], exam.id, results, scored_by=prereqs["user_id"],
    )
    assert count == 3

    # Verify applications transitioned to exam_completed
    for app_id in prereqs["app_ids"]:
        r = await app_session.execute(
            text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
            {"id": str(app_id)},
        )
        assert r.scalar() == "exam_completed"


async def test_submit_results_upsert(app_session, admin_session):
    """Submit results twice for same applicant -> updates (no duplicate)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Upsert Test", exam_date=date(2026, 7, 15),
        venue="Hall D", capacity=10,
    )
    await svc.register_applicants(tenant["id"], exam.id, [prereqs["app_ids"][0]])
    await svc.update_status(tenant["id"], exam.id, "in_progress")

    # First submission
    await svc.record_results(
        tenant["id"], exam.id,
        [{"application_id": str(prereqs["app_ids"][0]), "score": 70, "max_score": 100, "passed": True}],
        scored_by=prereqs["user_id"],
    )

    # Second submission with updated score
    await svc.record_results(
        tenant["id"], exam.id,
        [{"application_id": str(prereqs["app_ids"][0]), "score": 85, "max_score": 100, "passed": True}],
        scored_by=prereqs["user_id"],
    )

    # Only 1 result record (not 2)
    result = await app_session.execute(
        text("""
            SELECT count(*) FROM entrance_exam_results
            WHERE entrance_exam_id = CAST(:eid AS uuid)
            AND application_id = CAST(:aid AS uuid)
        """),
        {"eid": str(exam.id), "aid": str(prereqs["app_ids"][0])},
    )
    assert result.scalar() == 1

    # Score is updated
    result = await app_session.execute(
        text("""
            SELECT score FROM entrance_exam_results
            WHERE entrance_exam_id = CAST(:eid AS uuid)
            AND application_id = CAST(:aid AS uuid)
        """),
        {"eid": str(exam.id), "aid": str(prereqs["app_ids"][0])},
    )
    assert float(result.scalar()) == 85.0


async def test_exam_status_transitions(app_session, admin_session):
    """scheduled -> in_progress -> completed: valid. completed -> scheduled: invalid."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EntranceExamService, EntranceExamServiceError

    svc = EntranceExamService(app_session)
    exam = await svc.create_exam(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Status Test", exam_date=date(2026, 7, 15),
        venue="Hall E", capacity=10,
    )

    exam = await svc.update_status(tenant["id"], exam.id, "in_progress")
    assert exam.status == "in_progress"

    exam = await svc.update_status(tenant["id"], exam.id, "completed")
    assert exam.status == "completed"

    # completed -> scheduled: invalid
    with pytest.raises(EntranceExamServiceError) as exc_info:
        await svc.update_status(tenant["id"], exam.id, "scheduled")
    assert exc_info.value.code == "INVALID_TRANSITION"


async def test_exam_tenant_isolation(app_session, admin_session):
    """Exam from Tenant A is invisible to Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_exam_prereqs(admin_session, tenant_a["id"])
    await set_app_tenant_context(app_session, tenant_a["id"])

    from app.services.admissions import EntranceExamService

    svc = EntranceExamService(app_session)
    await svc.create_exam(
        tenant_id=tenant_a["id"], school_id=prereqs["school_id"],
        admission_period_id=prereqs["period_id"],
        name="Isolated Exam", exam_date=date(2026, 7, 15),
        venue="Hall F", capacity=10,
    )

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM entrance_exams"))
    assert result.scalar() == 0, "Tenant B must NOT see Tenant A's exams"

"""
Tests for DecisionService.

Covers: single decide, bulk decide, acceptance requires offered_class_id,
duplicate decision prevention, invalid transition, tenant isolation.
Uses two-engine pattern.
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

async def _seed_decision_prereqs(admin_session, tenant_id, *, app_status="shortlisted"):
    """Seed school, year, class, period, user, and an application.
    Returns dict with all IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
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
                0, false, false, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                'Decision', 'Maker', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"decider-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Kofi', 'Mensah',
                '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
            "status": app_status,
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "class_id": class_id, "app_id": app_id, "user_id": user_id,
    }


async def _seed_multiple_apps(admin_session, tenant_id, school_id, period_id, class_id, count=3, status="shortlisted"):
    """Seed multiple applications. Returns list of app IDs."""
    app_ids = []
    for i in range(count):
        app_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                    tracking_code, applicant_first_name, applicant_last_name,
                    date_of_birth, gender, target_class_id, status,
                    custom_fields, fee_waived, exam_waived, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid), :tc, :fn, 'Bulk',
                    '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                    '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(app_id), "tid": str(tenant_id),
                "sid": str(school_id), "pid": str(period_id),
                "tc": secrets.token_urlsafe(48), "cid": str(class_id),
                "fn": f"Applicant-{i}", "status": status,
            },
        )
        app_ids.append(app_id)
    await admin_session.commit()
    return app_ids


# --- Tests ---


async def test_accept_application(app_session, admin_session):
    """Accept a shortlisted application -> status becomes OFFERED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    decision = await svc.decide(
        tenant["id"],
        application_id=prereqs["app_id"],
        decision_type="accepted",
        decided_by=prereqs["user_id"],
        offered_class_id=prereqs["class_id"],
        response_deadline=date(2026, 8, 15),
    )
    assert decision.decision_type == "accepted"
    assert decision.offered_class_id == prereqs["class_id"]

    # Verify application status
    result = await app_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    assert result.scalar() == "offered"


async def test_reject_application(app_session, admin_session):
    """Reject a shortlisted application -> status becomes REJECTED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    decision = await svc.decide(
        tenant["id"],
        application_id=prereqs["app_id"],
        decision_type="rejected",
        decided_by=prereqs["user_id"],
        conditions="Academic requirements not met",
    )
    assert decision.decision_type == "rejected"

    result = await app_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    assert result.scalar() == "rejected"


async def test_waitlist_application(app_session, admin_session):
    """Waitlist an under_review application -> status becomes WAITLISTED."""
    tenant = await create_test_tenant(admin_session)
    # under_review allows: shortlisted, rejected, waitlisted, deferred, withdrawn
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"], app_status="under_review")
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    decision = await svc.decide(
        tenant["id"],
        application_id=prereqs["app_id"],
        decision_type="waitlisted",
        decided_by=prereqs["user_id"],
    )
    assert decision.decision_type == "waitlisted"

    result = await app_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    assert result.scalar() == "waitlisted"


async def test_acceptance_requires_offered_class(app_session, admin_session):
    """Acceptance without offered_class_id -> MISSING_CLASS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.decide(
            tenant["id"],
            application_id=prereqs["app_id"],
            decision_type="accepted",
            decided_by=prereqs["user_id"],
            # No offered_class_id
        )
    assert exc_info.value.code == "MISSING_CLASS"


async def test_duplicate_decision_prevented(app_session, admin_session):
    """Second decision on same application -> DECISION_EXISTS error."""
    tenant = await create_test_tenant(admin_session)
    # under_review allows waitlisted (first decision)
    # after waitlisted, allows rejected (second attempt -- should hit DECISION_EXISTS)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"], app_status="under_review")
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)

    # First decision: waitlist (under_review -> waitlisted)
    await svc.decide(
        tenant["id"],
        application_id=prereqs["app_id"],
        decision_type="waitlisted",
        decided_by=prereqs["user_id"],
    )

    # Second decision on same app: rejected (valid from waitlisted, but decision exists)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.decide(
            tenant["id"],
            application_id=prereqs["app_id"],
            decision_type="rejected",
            decided_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "DECISION_EXISTS"


async def test_invalid_status_for_decision(app_session, admin_session):
    """Application in draft status cannot receive a decision."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"], app_status="draft")
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.decide(
            tenant["id"],
            application_id=prereqs["app_id"],
            decision_type="rejected",
            decided_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "INVALID_TRANSITION"


async def test_invalid_decision_type(app_session, admin_session):
    """Invalid decision type -> INVALID_DECISION_TYPE error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.decide(
            tenant["id"],
            application_id=prereqs["app_id"],
            decision_type="promoted",
            decided_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "INVALID_DECISION_TYPE"


async def test_bulk_decide_partial_success(app_session, admin_session):
    """Bulk decide: 2 eligible + 1 ineligible -> 2 succeed, 1 fail."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant["id"])
    # 2 more shortlisted apps
    extra_apps = await _seed_multiple_apps(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"], count=2, status="shortlisted",
    )
    # 1 draft app (ineligible for decision)
    draft_apps = await _seed_multiple_apps(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"], count=1, status="draft",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    result = await svc.bulk_decide(
        tenant["id"],
        application_ids=[prereqs["app_id"]] + extra_apps + draft_apps,
        decision_type="rejected",
        decided_by=prereqs["user_id"],
    )
    assert len(result["succeeded"]) == 3  # 1 original + 2 extra (all shortlisted)
    assert len(result["failed"]) == 1  # 1 draft


async def test_decision_tenant_isolation(app_session, admin_session):
    """Decision from Tenant A is invisible to Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_decision_prereqs(admin_session, tenant_a["id"])
    await set_app_tenant_context(app_session, tenant_a["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    await svc.decide(
        tenant_a["id"],
        application_id=prereqs["app_id"],
        decision_type="rejected",
        decided_by=prereqs["user_id"],
    )

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM admission_decisions"))
    assert result.scalar() == 0, "Tenant B must NOT see Tenant A's decisions"

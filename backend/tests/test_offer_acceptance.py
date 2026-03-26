"""
Tests for offer acceptance/decline by registered applicants.

Covers: get_offer_details, respond_to_offer, IDOR checks,
expired offers, already-responded offers, anonymous applicant guard.
Uses two-engine pattern.
"""

import pytest
import secrets
from datetime import date, datetime, timedelta, UTC
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_offer_prereqs(admin_session, tenant_id, *,
                               response_deadline=None,
                               app_status="offered",
                               with_applicant_user=True,
                               offer_responded_at=None,
                               offer_response=None):
    """Seed school, year, class, period, applicant user, application, and decision.
    Returns dict with all IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
    decision_id = uuid4()
    applicant_user_id = uuid4() if with_applicant_user else None
    admin_user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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

    # Admin user who made the decision
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Admin', 'Decider', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(admin_user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    # Applicant user (the person who registered to manage their application)
    if applicant_user_id:
        await admin_session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status,
                    email_verified, mfa_enabled, failed_login_attempts, timezone,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    'Applicant', 'Parent', 'applicant', 'active',
                    true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(applicant_user_id), "tid": str(tenant_id),
             "email": f"applicant-{uuid4().hex[:6]}@test.com",
             "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
        )

    # Build responded_at SQL
    responded_sql = "NULL"
    if offer_responded_at:
        responded_sql = f"'{offer_responded_at.isoformat()}'"

    response_sql = "NULL"
    if offer_response:
        response_sql = f"'{offer_response}'"

    applicant_uid_sql = f"CAST('{applicant_user_id}' AS uuid)" if applicant_user_id else "NULL"

    await admin_session.execute(
        text(f"""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                applicant_user_id,
                offer_responded_at, offer_response,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Ama', 'Osei',
                '2012-01-01', 'female', CAST(:cid AS uuid), :status,
                {applicant_uid_sql},
                {responded_sql}, {response_sql},
                '{{}}'::jsonb, false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
            "status": app_status,
        },
    )

    # Create the decision record
    deadline_sql = f"'{response_deadline.isoformat()}'" if response_deadline else "NULL"
    await admin_session.execute(
        text(f"""
            INSERT INTO admission_decisions (id, tenant_id, application_id,
                decision_type, decided_by, offered_class_id,
                decision_date, response_deadline, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'accepted', CAST(:uid AS uuid), CAST(:cid AS uuid),
                CURRENT_DATE, {deadline_sql}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(decision_id), "tid": str(tenant_id), "aid": str(app_id),
            "uid": str(admin_user_id), "cid": str(class_id),
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "class_id": class_id, "app_id": app_id,
        "admin_user_id": admin_user_id,
        "applicant_user_id": applicant_user_id,
        "decision_id": decision_id,
    }


# --- Get Offer Details Tests ---


async def test_get_offer_details(app_session, admin_session):
    """Applicant can fetch their own offer details."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(
        admin_session, tenant["id"],
        response_deadline=date(2026, 8, 15),
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    details = await svc.get_offer_details(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
    )

    assert details["application_id"] == prereqs["app_id"]
    assert details["decision_type"] == "accepted"
    assert details["is_expired"] is False
    assert "Ama Osei" in details["applicant_name"]


async def test_get_offer_details_not_own(app_session, admin_session):
    """IDOR: different applicant cannot access another's offer -> NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(admin_session, tenant["id"])

    # Create a second applicant user (the intruder)
    intruder_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Evil', 'User', 'applicant', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(intruder_id), "tid": str(tenant["id"]),
         "email": f"intruder-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import (
        ApplicantAccountError,
        ApplicantAccountService,
    )

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.get_offer_details(
            tenant["id"], prereqs["app_id"],
            user_id=intruder_id,  # NOT the owning applicant
        )
    assert exc_info.value.code == "NOT_FOUND"


async def test_get_offer_details_expired(app_session, admin_session):
    """Past deadline + no response -> is_expired=True."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(
        admin_session, tenant["id"],
        response_deadline=date(2025, 1, 1),  # Well in the past
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    details = await svc.get_offer_details(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
    )
    assert details["is_expired"] is True


# --- Respond to Offer Tests ---


async def test_accept_offer(app_session, admin_session):
    """Accepting offer -> application status becomes 'accepted'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    app = await svc.respond_to_offer(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
        response="accepted",
    )
    assert app.status == "accepted"
    assert app.offer_response == "accepted"


async def test_decline_offer(app_session, admin_session):
    """Declining offer -> application status becomes 'withdrawn'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    app = await svc.respond_to_offer(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
        response="declined",
    )
    assert app.status == "withdrawn"
    assert app.offer_response == "declined"


async def test_respond_with_notes(app_session, admin_session):
    """Notes are persisted on the application record."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    app = await svc.respond_to_offer(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
        response="accepted",
        notes="Very excited to join!",
    )
    assert app.offer_response_notes == "Very excited to join!"


async def test_respond_wrong_status(app_session, admin_session):
    """Application not in 'offered' status -> INVALID_STATUS."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(
        admin_session, tenant["id"], app_status="submitted",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import (
        ApplicantAccountError,
        ApplicantAccountService,
    )

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.respond_to_offer(
            tenant["id"], prereqs["app_id"],
            user_id=prereqs["applicant_user_id"],
            response="accepted",
        )
    assert exc_info.value.code == "INVALID_STATUS"


async def test_respond_already_responded(app_session, admin_session):
    """Responding to an already-accepted offer -> INVALID_STATUS (status is no longer 'offered')."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(
        admin_session, tenant["id"],
        app_status="accepted",  # Already accepted
        offer_responded_at=datetime.now(UTC),
        offer_response="accepted",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import (
        ApplicantAccountError,
        ApplicantAccountService,
    )

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.respond_to_offer(
            tenant["id"], prereqs["app_id"],
            user_id=prereqs["applicant_user_id"],
            response="declined",
        )
    # Status is "accepted", not "offered", so it should fail
    assert exc_info.value.code == "INVALID_STATUS"


async def test_anonymous_cannot_respond(app_session, admin_session):
    """Application without applicant_user_id -> NOT_FOUND (IDOR check fails)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(
        admin_session, tenant["id"], with_applicant_user=False,
    )

    # Create a random user who tries to respond
    random_user_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Random', 'User', 'applicant', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(random_user_id), "tid": str(tenant["id"]),
         "email": f"random-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import (
        ApplicantAccountError,
        ApplicantAccountService,
    )

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.respond_to_offer(
            tenant["id"], prereqs["app_id"],
            user_id=random_user_id,
            response="accepted",
        )
    # IDOR check: applicant_user_id is None, doesn't match random_user_id
    assert exc_info.value.code == "NOT_FOUND"


async def test_offer_responded_at_set(app_session, admin_session):
    """offer_responded_at timestamp is set after responding."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    app = await svc.respond_to_offer(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
        response="accepted",
    )
    assert app.offer_responded_at is not None


async def test_offer_response_persisted(app_session, admin_session):
    """offer_response field is correctly saved in the database."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_offer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.applicant_service import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    await svc.respond_to_offer(
        tenant["id"], prereqs["app_id"],
        user_id=prereqs["applicant_user_id"],
        response="declined",
    )

    # Verify via raw SQL
    result = await app_session.execute(
        text("SELECT offer_response, status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    row = result.fetchone()
    assert row[0] == "declined"
    assert row[1] == "withdrawn"

"""
Tests for EnrollmentService.

Covers: single enrollment, idempotency, guardian deduplication,
invalid status rejection, bulk enrollment partial success,
tenant isolation. Uses two-engine pattern.
"""

import pytest
import secrets
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_enrollment_prereqs(
    admin_session, tenant_id, *,
    app_status="accepted",
    with_guardian=True,
    with_decision=True,
    guardian_email=None,
    guardian_phone="0241234567",
):
    """Seed school, year, class, period, user, application, guardian, and decision.
    Returns dict with all IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
    user_id = uuid4()
    guardian_email = guardian_email or f"g-{uuid4().hex[:6]}@test.com"

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
                'Enroller', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"enroller-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Ama', 'Enroll',
                '2012-05-15', 'female', CAST(:cid AS uuid), :status,
                '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
            "status": app_status,
        },
    )

    if with_guardian:
        await admin_session.execute(
            text("""
                INSERT INTO application_guardians (
                    id, tenant_id, application_id,
                    first_name, last_name, phone, email, relationship, is_primary,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                    'Parent', 'One', :phone, :email, 'mother', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_id), "aid": str(app_id),
             "phone": guardian_phone, "email": guardian_email},
        )

    if with_decision:
        await admin_session.execute(
            text("""
                INSERT INTO admission_decisions (
                    id, tenant_id, application_id, decision_type,
                    decided_by, offered_class_id, decision_date,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                    'accepted', CAST(:uid AS uuid), CAST(:cid AS uuid),
                    CURRENT_DATE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_id), "aid": str(app_id),
             "uid": str(user_id), "cid": str(class_id)},
        )

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "class_id": class_id, "app_id": app_id, "user_id": user_id,
        "guardian_email": guardian_email, "guardian_phone": guardian_phone,
    }


# --- Tests ---


async def test_enroll_accepted_applicant(app_session, admin_session):
    """Enroll an accepted applicant -> creates student, returns student_id."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )

    assert result["already_enrolled"] is False
    assert result["student_id"] is not None
    assert result["student_number"] is not None
    assert result["guardian_count"] == 1

    # Verify application status changed to enrolled
    r = await app_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    assert r.scalar() == "enrolled"


async def test_enroll_invalid_status(app_session, admin_session):
    """Application not in ACCEPTED status -> INVALID_STATUS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(
        admin_session, tenant["id"], app_status="submitted", with_decision=False,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService, EnrollmentError

    svc = EnrollmentService(app_session)
    with pytest.raises(EnrollmentError) as exc_info:
        await svc.enroll(
            tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
        )
    assert exc_info.value.code == "INVALID_STATUS"


async def test_enroll_idempotent(app_session, admin_session):
    """Enrolling same application twice returns already_enrolled=True."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)

    # First enrollment
    result1 = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result1["already_enrolled"] is False

    # Second enrollment of same application
    result2 = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result2["already_enrolled"] is True
    assert result2["student_id"] == result1["student_id"]


async def test_enroll_creates_student_record(app_session, admin_session):
    """Enrollment creates a student in the students table with correct data."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )

    # Verify student record exists with correct fields
    r = await app_session.execute(
        text("""
            SELECT first_name, last_name, gender, status, class_id
            FROM students WHERE id = CAST(:id AS uuid)
        """),
        {"id": result["student_id"]},
    )
    row = r.one()
    assert row.first_name == "Ama"
    assert row.last_name == "Enroll"
    assert row.gender == "female"
    assert row.status == "active"
    assert str(row.class_id) == str(prereqs["class_id"])


async def test_enroll_guardian_dedup_by_email(app_session, admin_session):
    """Two applications with same guardian email -> only one guardian record."""
    tenant = await create_test_tenant(admin_session)
    shared_email = f"shared-{uuid4().hex[:6]}@test.com"

    # First app with guardian
    prereqs1 = await _seed_enrollment_prereqs(
        admin_session, tenant["id"],
        guardian_email=shared_email, guardian_phone="0241111111",
    )
    # Second app with same guardian email
    prereqs2 = await _seed_enrollment_prereqs(
        admin_session, tenant["id"],
        guardian_email=shared_email, guardian_phone="0242222222",
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)

    # Enroll first
    await svc.enroll(
        tenant["id"], prereqs1["school_id"], prereqs1["app_id"], prereqs1["user_id"],
    )

    # Enroll second (same guardian email)
    await svc.enroll(
        tenant["id"], prereqs2["school_id"], prereqs2["app_id"], prereqs2["user_id"],
    )

    # Should have only 1 guardian with that email (deduplicated)
    r = await app_session.execute(
        text("SELECT count(*) FROM guardians WHERE email = :email"),
        {"email": shared_email},
    )
    assert r.scalar() == 1


async def test_enroll_without_guardian(app_session, admin_session):
    """Application without guardians -> enrollment succeeds with 0 guardians."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(
        admin_session, tenant["id"], with_guardian=False,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result["guardian_count"] == 0
    assert result["already_enrolled"] is False


async def test_bulk_enroll_partial_success(app_session, admin_session):
    """Bulk enroll: 1 accepted + 1 submitted -> 1 succeeds, 1 fails."""
    tenant = await create_test_tenant(admin_session)

    # Accepted app
    prereqs_ok = await _seed_enrollment_prereqs(admin_session, tenant["id"])

    # Submitted app (not accepted)
    prereqs_bad = await _seed_enrollment_prereqs(
        admin_session, tenant["id"],
        app_status="submitted", with_decision=False,
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.bulk_enroll(
        tenant["id"],
        prereqs_ok["school_id"],
        [prereqs_ok["app_id"], prereqs_bad["app_id"]],
        prereqs_ok["user_id"],
    )
    assert len(result["succeeded"]) == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["error"] is not None


async def test_enrollment_sets_converted_student_id(app_session, admin_session):
    """After enrollment, application.converted_student_id points to the new student."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )

    r = await app_session.execute(
        text("SELECT converted_student_id FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    converted = r.scalar()
    assert str(converted) == result["student_id"]


async def test_enrollment_tenant_isolation(app_session, admin_session):
    """Students created by enrollment in Tenant A are invisible to Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant_a["id"])
    await set_app_tenant_context(app_session, tenant_a["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    await svc.enroll(
        tenant_a["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM students"))
    assert result.scalar() == 0, "Tenant B must NOT see Tenant A's students"


# --- Applicant role promotion tests ---


async def test_enroll_promotes_applicant_to_parent(app_session, admin_session):
    """Enrolling an applicant's child promotes user role from 'applicant' to 'parent'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])

    # Create applicant user
    applicant_user_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Applicant', 'Parent', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(applicant_user_id),
            "tid": str(tenant["id"]),
            "email": f"applicant-{uuid4().hex[:6]}@test.com",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake",
        },
    )

    # Link application to the applicant user
    await admin_session.execute(
        text("""
            UPDATE applications
            SET applicant_user_id = CAST(:uid AS uuid)
            WHERE id = CAST(:aid AS uuid)
        """),
        {"uid": str(applicant_user_id), "aid": str(prereqs["app_id"])},
    )
    await admin_session.commit()

    # Capture applicant_user_id before context switch
    captured_applicant_id = applicant_user_id

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result["already_enrolled"] is False
    assert result["student_id"] is not None

    # Verify applicant user role was promoted to 'parent'
    r = await app_session.execute(
        text("SELECT role FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": str(captured_applicant_id)},
    )
    role = r.scalar()
    assert role == "parent", (
        f"Expected role to be promoted from 'applicant' to 'parent', got '{role}'"
    )


async def test_enroll_does_not_demote_existing_parent(app_session, admin_session):
    """If applicant user already has role='parent', enrollment must NOT change it."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])

    # Create user with role='parent' (already promoted)
    parent_user_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Existing', 'Parent', 'parent', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(parent_user_id),
            "tid": str(tenant["id"]),
            "email": f"parent-{uuid4().hex[:6]}@test.com",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake",
        },
    )

    # Link application to the parent user
    await admin_session.execute(
        text("""
            UPDATE applications
            SET applicant_user_id = CAST(:uid AS uuid)
            WHERE id = CAST(:aid AS uuid)
        """),
        {"uid": str(parent_user_id), "aid": str(prereqs["app_id"])},
    )
    await admin_session.commit()

    captured_parent_id = parent_user_id

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import EnrollmentService

    svc = EnrollmentService(app_session)
    result = await svc.enroll(
        tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
    )
    assert result["already_enrolled"] is False

    # Verify role is still 'parent' (not changed)
    r = await app_session.execute(
        text("SELECT role FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": str(captured_parent_id)},
    )
    role = r.scalar()
    assert role == "parent", (
        f"Expected role to remain 'parent', got '{role}'"
    )


async def test_enroll_revokes_applicant_tokens_on_promotion(app_session, admin_session):
    """Role promotion from applicant to parent triggers token revocation.

    We verify the blacklist service is called when the role is promoted.
    Token revocation is best-effort (failure logged, not raised).
    """
    from unittest.mock import patch, AsyncMock

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_enrollment_prereqs(admin_session, tenant["id"])

    # Create applicant user
    applicant_user_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Token', 'Revoke', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(applicant_user_id),
            "tid": str(tenant["id"]),
            "email": f"token-{uuid4().hex[:6]}@test.com",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake",
        },
    )

    # Link application to applicant user
    await admin_session.execute(
        text("""
            UPDATE applications
            SET applicant_user_id = CAST(:uid AS uuid)
            WHERE id = CAST(:aid AS uuid)
        """),
        {"uid": str(applicant_user_id), "aid": str(prereqs["app_id"])},
    )
    await admin_session.commit()

    captured_applicant_id = str(applicant_user_id)

    await set_app_tenant_context(app_session, tenant["id"])

    # Mock the token blacklist service
    mock_blacklist = AsyncMock()
    mock_blacklist.blacklist_user_tokens = AsyncMock()

    with patch(
        "app.services.token_blacklist.get_token_blacklist_service",
        new_callable=AsyncMock,
        return_value=mock_blacklist,
    ):
        from app.services.admissions import EnrollmentService

        svc = EnrollmentService(app_session)
        result = await svc.enroll(
            tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["user_id"],
        )

    assert result["already_enrolled"] is False

    # Verify blacklist_user_tokens was called with the applicant user ID
    mock_blacklist.blacklist_user_tokens.assert_called_once_with(captured_applicant_id)

    # Verify role was promoted
    r = await app_session.execute(
        text("SELECT role FROM users WHERE id = CAST(:id AS uuid)"),
        {"id": captured_applicant_id},
    )
    assert r.scalar() == "parent"

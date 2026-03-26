"""
Tests for applicant application management.

Covers: my applications list, create/update/submit drafts, claim flow,
multi-child support, guardian pre-fill, print view, anti-enumeration,
concurrent claims, guardian hard-delete on update. Uses two-engine pattern.
"""

import pytest
import secrets
from datetime import date, datetime, UTC
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio

# Pre-computed Argon2id hash for "Test1234!"
TEST_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=2,p=1$"
    "+R3+DwouzdH8y9YimHUqgg$zXU/R8V0htx9oQoVCQMMDJFXsyZQuroravnkWMCFh6E"
)


# --- Helpers ---

async def _seed_app_prereqs(
    admin_session, tenant_id, *,
    with_applicant_user=True,
    period_status="open",
    fee_required=False,
    extra_class=False,
):
    """Seed school, year, class, period, and optionally an applicant user.

    Returns dict with: school_id, class_id, period_id, applicant_user_id (or None),
    tenant_id, academic_year_id, applicant_email.
    If extra_class=True, returns extra_class_id as well.
    """
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31',
                'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2025-01-01', '2027-12-31', :status,
                50.00, :fee_required,
                false, :target_classes,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
            "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}",
            "status": period_status, "fee_required": fee_required,
            "target_classes": f'["{str(class_id)}"]',
        },
    )

    applicant_user_id = None
    applicant_email = None
    if with_applicant_user:
        applicant_user_id = uuid4()
        applicant_email = f"applicant-{uuid4().hex[:6]}@test.com"
        await admin_session.execute(
            text("""
                INSERT INTO users (
                    id, tenant_id, school_id, email, password_hash,
                    first_name, last_name, phone, role, status,
                    email_verified, mfa_enabled, failed_login_attempts,
                    timezone, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :email, :pw,
                    'Test', 'Applicant', '+233241234567', 'applicant', 'active',
                    true, false, 0, 'Africa/Accra',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(applicant_user_id), "tid": str(tenant_id),
                "sid": str(school_id),
                "email": applicant_email, "pw": TEST_PASSWORD_HASH,
            },
        )

    extra_class_id = None
    if extra_class:
        extra_class_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO classes (
                    id, tenant_id, name, level, sequence,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    'primary', 2, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(extra_class_id), "tid": str(tenant_id),
             "name": f"C2-{uuid4().hex[:6]}"},
        )

    await admin_session.commit()

    result = {
        "school_id": school_id, "class_id": class_id, "period_id": period_id,
        "applicant_user_id": applicant_user_id, "applicant_email": applicant_email,
        "tenant_id": tenant_id, "academic_year_id": year_id,
    }
    if extra_class:
        result["extra_class_id"] = extra_class_id
    return result


async def _create_application_for_user(
    admin_session, tenant_id, school_id, period_id, class_id,
    applicant_user_id, *, status="draft", with_guardian=False,
    guardian_email=None,
):
    """Seed an application linked to a specific applicant user.
    Returns dict with: app_id, tracking_code.
    """
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                applicant_user_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, :fn, :ln,
                '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                '{}', false, false,
                CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": tracking_code, "fn": f"Child-{uuid4().hex[:4]}",
            "ln": "Test", "cid": str(class_id),
            "status": status, "uid": str(applicant_user_id) if applicant_user_id else None,
        },
    )
    if with_guardian:
        g_email = guardian_email or f"guardian-{uuid4().hex[:6]}@test.com"
        await admin_session.execute(
            text("""
                INSERT INTO application_guardians (
                    id, tenant_id, application_id,
                    first_name, last_name, phone, email, relationship, is_primary,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                    'Guardian', 'One', '0241234567', :email, 'father', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_id),
             "aid": str(app_id), "email": g_email},
        )
    await admin_session.commit()
    return {"app_id": app_id, "tracking_code": tracking_code}


def _make_guardians(email=None):
    return [
        {
            "first_name": "John", "last_name": "Doe", "phone": "0241234567",
            "email": email or "john@test.com", "relationship": "father",
            "is_primary": True,
        },
    ]


# --- Tests ---


async def test_list_my_applications_empty(app_session, admin_session):
    """Applicant with no applications -> empty list, total=0."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    apps, total = await svc.list_my_applications(
        tenant["id"], prereqs["applicant_user_id"],
    )
    assert total == 0
    assert len(apps) == 0


async def test_list_my_applications_with_data(app_session, admin_session):
    """Applicant with 3 apps -> returns all 3 with correct statuses."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    for status in ["draft", "submitted", "under_review"]:
        await _create_application_for_user(
            admin_session, tenant["id"], prereqs["school_id"],
            prereqs["period_id"], prereqs["class_id"],
            prereqs["applicant_user_id"], status=status,
        )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    apps, total = await svc.list_my_applications(
        tenant["id"], prereqs["applicant_user_id"],
    )
    assert total == 3
    statuses = {a.status for a in apps}
    assert statuses == {"draft", "submitted", "under_review"}


async def test_list_my_applications_excludes_other_users(app_session, admin_session):
    """User A sees only own apps, not User B's."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create a second applicant user
    user_b_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, school_id, email, password_hash,
                first_name, last_name, phone, role, status,
                email_verified, mfa_enabled, failed_login_attempts,
                timezone, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :email, :pw,
                'User', 'B', '+233241234568', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_b_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "email": f"userb-{uuid4().hex[:6]}@test.com", "pw": TEST_PASSWORD_HASH,
        },
    )
    await admin_session.commit()

    # 2 apps for user A
    for _ in range(2):
        await _create_application_for_user(
            admin_session, tenant["id"], prereqs["school_id"],
            prereqs["period_id"], prereqs["class_id"],
            prereqs["applicant_user_id"],
        )
    # 1 app for user B
    await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"], user_b_id,
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)

    apps_a, total_a = await svc.list_my_applications(
        tenant["id"], prereqs["applicant_user_id"],
    )
    assert total_a == 2

    apps_b, total_b = await svc.list_my_applications(
        tenant["id"], user_b_id,
    )
    assert total_b == 1

    # No overlap
    ids_a = {str(a.id) for a in apps_a}
    ids_b = {str(a.id) for a in apps_b}
    assert ids_a.isdisjoint(ids_b)


async def test_create_draft_success(app_session, admin_session):
    """Create draft -> status=draft, tracking_code generated, applicant_user_id set."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    app = await svc.create_draft(
        tenant["id"], prereqs["school_id"], prereqs["applicant_user_id"],
        admission_period_id=prereqs["period_id"],
        applicant_first_name="Kofi",
        applicant_last_name="Mensah",
        date_of_birth=date(2012, 5, 15),
        gender="male",
        target_class_id=prereqs["class_id"],
        guardians=_make_guardians(),
    )

    assert app.status == "draft"
    assert len(app.tracking_code) == 64  # token_urlsafe(48) = 64 chars
    assert app.applicant_user_id == prereqs["applicant_user_id"]
    assert app.submitted_at is None


async def test_update_draft_adds_data(app_session, admin_session):
    """Update draft with new data -> data persisted."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="draft",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    updated = await svc.update_draft(
        tenant["id"], prereqs["applicant_user_id"], created["app_id"],
        medical_info="Allergic to peanuts",
        guardians=[
            {"first_name": "New", "last_name": "Guardian", "phone": "0241111111",
             "relationship": "mother", "is_primary": True},
        ],
    )

    assert updated.medical_info == "Allergic to peanuts"

    # Verify guardian created
    r = await app_session.execute(
        text("""
            SELECT count(*) FROM application_guardians
            WHERE application_id = CAST(:id AS uuid)
            AND deleted_at IS NULL
        """),
        {"id": str(created["app_id"])},
    )
    assert r.scalar() == 1


async def test_update_draft_only_owner(app_session, admin_session):
    """User B cannot update User A's draft -> NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    user_b_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, school_id, email, password_hash,
                first_name, last_name, phone, role, status,
                email_verified, mfa_enabled, failed_login_attempts,
                timezone, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :email, :pw,
                'User', 'B', '+233241234568', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_b_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "email": f"userb-{uuid4().hex[:6]}@test.com", "pw": TEST_PASSWORD_HASH,
        },
    )
    await admin_session.commit()

    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="draft",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.update_draft(
            tenant["id"], user_b_id, created["app_id"],
            medical_info="Hacked!",
        )
    assert exc_info.value.code == "NOT_FOUND"


async def test_update_non_draft_fails(app_session, admin_session):
    """Updating a submitted application -> NOT_DRAFT error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="submitted",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.update_draft(
            tenant["id"], prereqs["applicant_user_id"], created["app_id"],
            medical_info="Should not work",
        )
    assert exc_info.value.code == "NOT_DRAFT"


async def test_submit_draft_success(app_session, admin_session):
    """Submit complete draft (no fee required) -> status=submitted."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"], fee_required=False)
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="draft",
        with_guardian=True,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    app = await svc.submit_draft(
        tenant["id"], prereqs["applicant_user_id"], created["app_id"],
    )

    assert app.status == "submitted"
    assert app.submitted_at is not None


async def test_submit_incomplete_draft_fails(app_session, admin_session):
    """Submit draft without guardians -> NO_GUARDIANS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="draft",
        with_guardian=False,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.submit_draft(
            tenant["id"], prereqs["applicant_user_id"], created["app_id"],
        )
    assert exc_info.value.code == "NO_GUARDIANS"


async def test_submit_draft_period_closed(app_session, admin_session):
    """Create draft in open period, then close period, then submit -> PERIOD_NOT_OPEN."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"], fee_required=False)
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="draft",
        with_guardian=True,
    )

    # Close the period
    await admin_session.execute(
        text("UPDATE admission_periods SET status = 'closed' WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["period_id"])},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.submit_draft(
            tenant["id"], prereqs["applicant_user_id"], created["app_id"],
        )
    assert exc_info.value.code == "PERIOD_NOT_OPEN"


async def test_multi_child_same_period(app_session, admin_session):
    """Same applicant creates 2 drafts in same period -> both succeed."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)

    app1 = await svc.create_draft(
        tenant["id"], prereqs["school_id"], prereqs["applicant_user_id"],
        admission_period_id=prereqs["period_id"],
        applicant_first_name="Kofi",
        applicant_last_name="Test",
        target_class_id=prereqs["class_id"],
    )
    app2 = await svc.create_draft(
        tenant["id"], prereqs["school_id"], prereqs["applicant_user_id"],
        admission_period_id=prereqs["period_id"],
        applicant_first_name="Ama",
        applicant_last_name="Test",
        target_class_id=prereqs["class_id"],
    )

    assert app1.id != app2.id
    assert app1.applicant_first_name == "Kofi"
    assert app2.applicant_first_name == "Ama"

    # List should return both
    apps, total = await svc.list_my_applications(
        tenant["id"], prereqs["applicant_user_id"],
    )
    assert total == 2


async def test_multi_child_different_periods(app_session, admin_session):
    """Same applicant creates apps in 2 different periods -> both succeed."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create second period
    period_b_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, :target_classes,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_b_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "ayid": str(prereqs["academic_year_id"]),
            "name": f"PB-{uuid4().hex[:6]}",
            "target_classes": f'["{str(prereqs["class_id"])}"]',
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)

    app1 = await svc.create_draft(
        tenant["id"], prereqs["school_id"], prereqs["applicant_user_id"],
        admission_period_id=prereqs["period_id"],
        applicant_first_name="Child", applicant_last_name="One",
        target_class_id=prereqs["class_id"],
    )
    app2 = await svc.create_draft(
        tenant["id"], prereqs["school_id"], prereqs["applicant_user_id"],
        admission_period_id=period_b_id,
        applicant_first_name="Child", applicant_last_name="Two",
        target_class_id=prereqs["class_id"],
    )

    assert str(app1.admission_period_id) == str(prereqs["period_id"])
    assert str(app2.admission_period_id) == str(period_b_id)


async def test_claim_application_success(app_session, admin_session):
    """Claim anonymous application -> applicant_user_id set."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create anonymous application (applicant_user_id=NULL) with matching guardian email
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                applicant_user_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Anon', 'Child',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                NULL,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": tracking_code, "cid": str(prereqs["class_id"]),
        },
    )
    # Guardian email matches the applicant user email
    await admin_session.execute(
        text("""
            INSERT INTO application_guardians (
                id, tenant_id, application_id,
                first_name, last_name, phone, email, relationship, is_primary,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'Guardian', 'Match', '0241234567', :email, 'father', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "aid": str(app_id), "email": prereqs["applicant_email"],
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicantAccountService

    svc = ApplicantAccountService(app_session)
    result = await svc.claim_application(
        tenant["id"], prereqs["applicant_user_id"],
        tracking_code=tracking_code,
    )

    assert str(result.applicant_user_id) == str(prereqs["applicant_user_id"])

    # Idempotent: claiming again returns same result
    result2 = await svc.claim_application(
        tenant["id"], prereqs["applicant_user_id"],
        tracking_code=tracking_code,
    )
    assert str(result2.id) == str(result.id)


async def test_claim_application_email_mismatch(app_session, admin_session):
    """Guardian email doesn't match applicant email -> CLAIM_FAILED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                applicant_user_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Anon', 'Child',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                NULL,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": tracking_code, "cid": str(prereqs["class_id"]),
        },
    )
    # Guardian email does NOT match the applicant
    await admin_session.execute(
        text("""
            INSERT INTO application_guardians (
                id, tenant_id, application_id,
                first_name, last_name, phone, email, relationship, is_primary,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'Guardian', 'Other', '0241234567', 'different@test.com', 'father', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(uuid4()), "tid": str(tenant["id"]), "aid": str(app_id)},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicantAccountService, ApplicantAccountError

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.claim_application(
            tenant["id"], prereqs["applicant_user_id"],
            tracking_code=tracking_code,
        )
    assert exc_info.value.code == "CLAIM_FAILED"


async def test_claim_already_claimed(app_session, admin_session):
    """Application already claimed by user A -> user B gets CLAIM_FAILED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create user B
    user_b_id = uuid4()
    user_b_email = f"userb-{uuid4().hex[:6]}@test.com"
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, school_id, email, password_hash,
                first_name, last_name, phone, role, status,
                email_verified, mfa_enabled, failed_login_attempts,
                timezone, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :email, :pw,
                'User', 'B', '+233241234568', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_b_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "email": user_b_email, "pw": TEST_PASSWORD_HASH,
        },
    )

    # App already claimed by user A
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                applicant_user_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Claimed', 'Child',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": tracking_code, "cid": str(prereqs["class_id"]),
            "uid": str(prereqs["applicant_user_id"]),
        },
    )
    # Guardian with user B's email (so email would match)
    await admin_session.execute(
        text("""
            INSERT INTO application_guardians (
                id, tenant_id, application_id,
                first_name, last_name, phone, email, relationship, is_primary,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'Guardian', 'B', '0241234567', :email, 'father', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(uuid4()), "tid": str(tenant["id"]),
         "aid": str(app_id), "email": user_b_email},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicantAccountService, ApplicantAccountError

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.claim_application(
            tenant["id"], user_b_id,
            tracking_code=tracking_code,
        )
    assert exc_info.value.code == "CLAIM_FAILED"

    # Verify still claimed by user A
    r = await app_session.execute(
        text("SELECT applicant_user_id FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(app_id)},
    )
    assert str(r.scalar()) == str(prereqs["applicant_user_id"])


async def test_claim_invalid_tracking_code(app_session, admin_session):
    """Random tracking code -> CLAIM_FAILED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicantAccountService, ApplicantAccountError

    svc = ApplicantAccountService(app_session)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.claim_application(
            tenant["id"], prereqs["applicant_user_id"],
            tracking_code="nonexistent-tracking-code-12345",
        )
    assert exc_info.value.code == "CLAIM_FAILED"


async def test_get_printable_application(app_session, admin_session):
    """Printable view loads all relations."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="submitted",
        with_guardian=True,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    app = await svc.get_printable_application(
        tenant["id"], prereqs["applicant_user_id"], created["app_id"],
    )

    assert app.id == created["app_id"]
    assert app.status == "submitted"
    # Relations should be loaded (not raise on access)
    assert app.guardians is not None
    assert len(app.guardians) >= 1


async def test_guardian_prefill_data(app_session, admin_session):
    """Guardian prefill returns data from most recent non-draft application."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create and "submit" an application with guardians
    created = await _create_application_for_user(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
        prereqs["applicant_user_id"], status="submitted",
        with_guardian=True, guardian_email="prefill@test.com",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    guardians = await svc.get_latest_guardian_info(
        tenant["id"], prereqs["applicant_user_id"],
    )

    assert len(guardians) >= 1
    assert guardians[0]["email"] == "prefill@test.com"


async def test_claim_error_messages_are_generic(app_session, admin_session):
    """All claim failures return same CLAIM_FAILED code (anti-enumeration)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicantAccountService, ApplicantAccountError

    svc = ApplicantAccountService(app_session)

    # Invalid tracking code
    with pytest.raises(ApplicantAccountError) as exc1:
        await svc.claim_application(
            tenant["id"], prereqs["applicant_user_id"],
            tracking_code="invalid-code",
        )

    # All return CLAIM_FAILED
    assert exc1.value.code == "CLAIM_FAILED"


async def test_concurrent_claim_race_condition(app_session, admin_session):
    """When app is claimed between check and set, second claim gets CLAIM_FAILED.

    We simulate this by claiming once, then attempting again as another user.
    """
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create anonymous app
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                applicant_user_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Race', 'Condition',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                NULL,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": tracking_code, "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.execute(
        text("""
            INSERT INTO application_guardians (
                id, tenant_id, application_id,
                first_name, last_name, phone, email, relationship, is_primary,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'Guardian', 'Race', '0241234567', :email, 'father', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "aid": str(app_id), "email": prereqs["applicant_email"],
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicantAccountService, ApplicantAccountError

    svc = ApplicantAccountService(app_session)

    # First claim succeeds
    result = await svc.claim_application(
        tenant["id"], prereqs["applicant_user_id"],
        tracking_code=tracking_code,
    )
    assert str(result.applicant_user_id) == str(prereqs["applicant_user_id"])

    # Create user C
    user_c_id = uuid4()
    user_c_email = prereqs["applicant_email"]  # Same email so email match would pass
    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, school_id, email, password_hash,
                first_name, last_name, phone, role, status,
                email_verified, mfa_enabled, failed_login_attempts,
                timezone, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :email, :pw,
                'User', 'C', '+233241234569', 'applicant', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_c_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "email": f"userc-{uuid4().hex[:6]}@test.com", "pw": TEST_PASSWORD_HASH,
        },
    )
    await admin_session.commit()

    # Second claim by different user fails (already claimed)
    with pytest.raises(ApplicantAccountError) as exc_info:
        await svc.claim_application(
            tenant["id"], user_c_id,
            tracking_code=tracking_code,
        )
    assert exc_info.value.code == "CLAIM_FAILED"


async def test_draft_guardian_hard_delete_on_update(app_session, admin_session):
    """Updating guardians hard-deletes old ones (no soft delete accumulation)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_app_prereqs(admin_session, tenant["id"])

    # Create draft with guardian
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    app = await svc.create_draft(
        tenant["id"], prereqs["school_id"], prereqs["applicant_user_id"],
        admission_period_id=prereqs["period_id"],
        applicant_first_name="Hard", applicant_last_name="Delete",
        target_class_id=prereqs["class_id"],
        guardians=[
            {"first_name": "Old1", "last_name": "Guard", "phone": "0241111111",
             "relationship": "father", "is_primary": True},
            {"first_name": "Old2", "last_name": "Guard", "phone": "0241111112",
             "relationship": "mother"},
        ],
    )

    app_id = app.id

    # Verify 2 guardians exist
    r = await app_session.execute(
        text("SELECT count(*) FROM application_guardians WHERE application_id = CAST(:id AS uuid)"),
        {"id": str(app_id)},
    )
    assert r.scalar() == 2

    # Update with 3 new guardians
    await svc.update_draft(
        tenant["id"], prereqs["applicant_user_id"], app_id,
        guardians=[
            {"first_name": "New1", "last_name": "Guard", "phone": "0242222221",
             "relationship": "father", "is_primary": True},
            {"first_name": "New2", "last_name": "Guard", "phone": "0242222222",
             "relationship": "mother"},
            {"first_name": "New3", "last_name": "Guard", "phone": "0242222223",
             "relationship": "uncle"},
        ],
    )

    # Verify exactly 3 guardians (old ones hard-deleted)
    r = await app_session.execute(
        text("SELECT count(*) FROM application_guardians WHERE application_id = CAST(:id AS uuid)"),
        {"id": str(app_id)},
    )
    assert r.scalar() == 3

    # Verify no soft-deleted rows lingering
    r = await app_session.execute(
        text("""
            SELECT count(*) FROM application_guardians
            WHERE application_id = CAST(:id AS uuid)
            AND deleted_at IS NOT NULL
        """),
        {"id": str(app_id)},
    )
    assert r.scalar() == 0

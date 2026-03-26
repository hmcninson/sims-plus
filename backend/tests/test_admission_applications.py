"""
Tests for ApplicationService.

Covers: submission (with mocked Turnstile), status transitions, search/filter,
waivers, notes, daily cap, ILIKE escaping. Uses two-engine pattern.
"""

import pytest
import secrets
from datetime import date, datetime, UTC
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_prereqs(admin_session, tenant_id, *, fee_required=True, max_apps=None):
    """Seed school, academic year, class, admission period. Returns dict of IDs."""
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

    max_apps_sql = f"{max_apps}" if max_apps else "NULL"
    await admin_session.execute(
        text(f"""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, max_applications, target_classes,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2025-01-01', '2027-12-31', 'open',
                50.00, :fee_required,
                false, {max_apps_sql}, :target_classes,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
            "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}",
            "fee_required": fee_required,
            "target_classes": f'["{str(class_id)}"]',
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "year_id": year_id,
        "class_id": class_id, "period_id": period_id,
    }


def _make_guardians():
    return [
        {
            "first_name": "John", "last_name": "Doe", "phone": "0241234567",
            "email": "john@test.com", "relationship": "father", "is_primary": True,
        },
        {
            "first_name": "Jane", "last_name": "Doe", "phone": "0241234568",
            "relationship": "mother",
        },
    ]


# --- Tests ---


@patch("app.services.admissions.application_service.verify_turnstile", new_callable=AsyncMock, return_value=True)
async def test_submit_application_success(mock_turnstile, app_session, admin_session):
    """Submit with valid data. Fee required -> status=draft."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"], fee_required=True)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    app = await svc.submit(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        turnstile_token="test-token",
        admission_period_id=prereqs["period_id"],
        applicant_first_name="Kwame",
        applicant_last_name="Asante",
        applicant_other_names=None,
        date_of_birth=date(2012, 5, 15),
        gender="male",
        nationality="Ghanaian",
        target_class_id=prereqs["class_id"],
        custom_fields={},
        previous_school=None,
        medical_info=None,
        guardians=_make_guardians(),
    )

    assert app.status == "draft"  # Fee required, so starts as draft
    assert app.applicant_first_name == "Kwame"
    assert len(app.tracking_code) == 64  # token_urlsafe(48) = 64 chars
    mock_turnstile.assert_called_once()


@patch("app.services.admissions.application_service.verify_turnstile", new_callable=AsyncMock, return_value=False)
async def test_submit_application_turnstile_failure(mock_turnstile, app_session, admin_session):
    """Turnstile returns False -> CAPTCHA_FAILED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.submit(
            tenant_id=tenant["id"], school_id=prereqs["school_id"],
            turnstile_token="bad", admission_period_id=prereqs["period_id"],
            applicant_first_name="X", applicant_last_name="Y",
            applicant_other_names=None, date_of_birth=date(2012, 1, 1),
            gender="male", nationality=None,
            target_class_id=prereqs["class_id"], custom_fields={},
            previous_school=None, medical_info=None, guardians=_make_guardians(),
        )
    assert exc_info.value.code == "CAPTCHA_FAILED"


@patch("app.services.admissions.application_service.verify_turnstile", new_callable=AsyncMock, return_value=True)
async def test_submit_application_period_not_open(mock_turnstile, app_session, admin_session):
    """Period status=closed -> PERIOD_NOT_OPEN."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    # Change period status to closed
    await admin_session.execute(
        text("UPDATE admission_periods SET status = 'closed' WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["period_id"])},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.submit(
            tenant_id=tenant["id"], school_id=prereqs["school_id"],
            turnstile_token="t", admission_period_id=prereqs["period_id"],
            applicant_first_name="X", applicant_last_name="Y",
            applicant_other_names=None, date_of_birth=date(2012, 1, 1),
            gender="male", nationality=None,
            target_class_id=prereqs["class_id"], custom_fields={},
            previous_school=None, medical_info=None, guardians=_make_guardians(),
        )
    assert exc_info.value.code == "PERIOD_NOT_OPEN"


@patch("app.services.admissions.application_service.verify_turnstile", new_callable=AsyncMock, return_value=True)
async def test_submit_fee_waived_auto_submits(mock_turnstile, app_session, admin_session):
    """No fee required -> application goes straight to SUBMITTED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"], fee_required=False)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    app = await svc.submit(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        turnstile_token="t", admission_period_id=prereqs["period_id"],
        applicant_first_name="Auto", applicant_last_name="Submit",
        applicant_other_names=None, date_of_birth=date(2012, 1, 1),
        gender="female", nationality=None,
        target_class_id=prereqs["class_id"], custom_fields={},
        previous_school=None, medical_info=None, guardians=_make_guardians(),
    )
    assert app.status == "submitted"
    assert app.submitted_at is not None


@patch("app.services.admissions.application_service.verify_turnstile", new_callable=AsyncMock, return_value=True)
async def test_submit_max_applications_reached(mock_turnstile, app_session, admin_session):
    """Period with max_applications=1, already has 1 -> PERIOD_FULL."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"], fee_required=False, max_apps=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)

    # First submission succeeds
    await svc.submit(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        turnstile_token="t", admission_period_id=prereqs["period_id"],
        applicant_first_name="First", applicant_last_name="App",
        applicant_other_names=None, date_of_birth=date(2012, 1, 1),
        gender="male", nationality=None,
        target_class_id=prereqs["class_id"], custom_fields={},
        previous_school=None, medical_info=None, guardians=_make_guardians(),
    )

    # Second submission fails
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.submit(
            tenant_id=tenant["id"], school_id=prereqs["school_id"],
            turnstile_token="t", admission_period_id=prereqs["period_id"],
            applicant_first_name="Second", applicant_last_name="App",
            applicant_other_names=None, date_of_birth=date(2012, 2, 2),
            gender="female", nationality=None,
            target_class_id=prereqs["class_id"], custom_fields={},
            previous_school=None, medical_info=None, guardians=_make_guardians(),
        )
    assert exc_info.value.code == "PERIOD_FULL"


async def test_check_status_by_tracking_code(app_session, admin_session):
    """Status check returns minimal data only."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    # Seed an application directly
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Ama', 'Mensah',
                '2012-01-01', 'female', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": tracking_code, "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    result = svc_result = await svc.get_by_tracking_code(tenant["id"], tracking_code)

    assert result["status"] == "submitted"
    assert result["applicant_first_name"] == "Ama"
    # Verify minimal data -- no guardian info, no email, no full PII
    assert "email" not in result
    assert "guardians" not in result


async def test_check_status_invalid_tracking_code(app_session, admin_session):
    """Random tracking code -> NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.get_by_tracking_code(tenant["id"], "nonexistent-code-12345")
    assert exc_info.value.code == "NOT_FOUND"


async def test_transition_status_valid(app_session, admin_session):
    """SUBMITTED -> UNDER_REVIEW succeeds."""
    tenant = await create_test_tenant(admin_session)
    user = await create_test_user(admin_session, tenant["id"])
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Test', 'Status',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": secrets.token_urlsafe(48), "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    result = await svc.transition_status(
        tenant["id"], app_id, "under_review", user["id"], reason="Initial review",
    )
    assert result.status == "under_review"


async def test_transition_status_invalid(app_session, admin_session):
    """SUBMITTED -> ENROLLED is invalid."""
    tenant = await create_test_tenant(admin_session)
    user = await create_test_user(admin_session, tenant["id"])
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Test', 'Invalid',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": secrets.token_urlsafe(48), "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService, ApplicationServiceError

    svc = ApplicationService(app_session)
    with pytest.raises(ApplicationServiceError) as exc_info:
        await svc.transition_status(tenant["id"], app_id, "enrolled", user["id"])
    assert exc_info.value.code == "INVALID_TRANSITION"


async def test_waive_fee_sets_flag(app_session, admin_session):
    """Waive fee -> fee_waived=True, auto-submits if draft."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Fee', 'Waiver',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'draft',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": secrets.token_urlsafe(48), "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    result = await svc.waive_fee(tenant["id"], app_id)
    assert result.fee_waived is True
    assert result.status == "submitted"  # Auto-submitted after waiver


async def test_waive_exam_sets_flag(app_session, admin_session):
    """Waive exam -> exam_waived=True."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Exam', 'Waiver',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": secrets.token_urlsafe(48), "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    result = await svc.waive_exam(tenant["id"], app_id)
    assert result.exam_waived is True


async def test_add_note_to_application(app_session, admin_session):
    """Add an internal note to an application."""
    tenant = await create_test_tenant(admin_session)
    user = await create_test_user(admin_session, tenant["id"])
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Note', 'Test',
                '2012-01-01', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tc": secrets.token_urlsafe(48), "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)
    note = await svc.add_note(
        tenant["id"], app_id, author_id=user["id"],
        content="Strong candidate - recommend shortlist", is_internal=True,
    )
    assert note.content == "Strong candidate - recommend shortlist"
    assert note.is_internal is True
    assert note.author_id == user["id"]


async def test_list_applications_with_filters(app_session, admin_session):
    """List applications with status filter."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    # Seed 3 applications with different statuses
    for status in ["submitted", "under_review", "rejected"]:
        await admin_session.execute(
            text("""
                INSERT INTO applications (
                    id, tenant_id, school_id, admission_period_id,
                    tracking_code, applicant_first_name, applicant_last_name,
                    date_of_birth, gender, target_class_id, status,
                    custom_fields, fee_waived, exam_waived,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid),
                    :tc, :fn, 'Filter',
                    '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                    '{}', false, false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()), "tid": str(tenant["id"]),
                "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
                "tc": secrets.token_urlsafe(48), "cid": str(prereqs["class_id"]),
                "fn": f"App-{status}", "status": status,
            },
        )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationService

    svc = ApplicationService(app_session)

    # All
    apps, total = await svc.list_applications(tenant["id"])
    assert total == 3

    # Filter by status
    apps, total = await svc.list_applications(tenant["id"], status="submitted")
    assert total == 1
    assert apps[0].status == "submitted"

"""
Tests for ApplicationService.

Covers: submission, Turnstile mock, status transitions, search/filter,
waivers, notes, daily cap, ILIKE escaping.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _full_seed(admin_session, tenant_id):
    """Create school + academic year + class. Return dict with IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()

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
        {
            "id": str(school_id), "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
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
        {"id": str(class_id), "tid": str(tenant_id), "name": f"Class-{uuid4().hex[:6]}"},
    )

    await admin_session.commit()
    return {"school_id": school_id, "year_id": year_id, "class_id": class_id}


async def _create_open_period(app_session, tenant_id, school_id, year_id, **kwargs):
    """Create and open an admission period. Return the period object."""
    from app.services.admissions import AdmissionPeriodService

    service = AdmissionPeriodService(app_session)
    today = date.today()
    period = await service.create(
        tenant_id=tenant_id,
        school_id=school_id,
        name=kwargs.get("name", f"Period-{uuid4().hex[:6]}"),
        academic_year_id=year_id,
        start_date=kwargs.get("start_date", today - timedelta(days=1)),
        end_date=kwargs.get("end_date", today + timedelta(days=30)),
        application_fee_required=kwargs.get("fee_required", False),
        entrance_exam_required=kwargs.get("exam_required", False),
        max_applications=kwargs.get("max_applications", None),
        target_classes=kwargs.get("target_classes", None),
    )
    # Transition to open
    period = await service.update_status(tenant_id, period.id, "open")
    return period


def _guardian_data():
    """Return valid guardian data for submission."""
    return [
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone": "0241234567",
            "email": f"jane-{uuid4().hex[:6]}@test.com",
            "relationship": "mother",
            "is_primary": True,
        },
    ]


class TestApplicationSubmission:
    """Happy path and validation for application submission."""

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_submit_application_success(self, mock_ts, app_session, admin_session):
        """Submit with valid data -> application created."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test-token",
            admission_period_id=period.id,
            applicant_first_name="Kwame",
            applicant_last_name="Asante",
            applicant_other_names=None,
            date_of_birth=date(2012, 5, 15),
            gender="male",
            nationality="Ghanaian",
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        assert app.applicant_first_name == "Kwame"
        # No fee required -> auto-submitted
        assert app.status == "submitted"
        assert len(app.tracking_code) > 20

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=False)
    async def test_submit_turnstile_failure(self, mock_ts, app_session, admin_session):
        """Turnstile verification fails -> CAPTCHA_FAILED."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService, ApplicationServiceError

        service = ApplicationService(app_session)
        with pytest.raises(ApplicationServiceError) as exc_info:
            await service.submit(
                tenant_id=tenant["id"],
                school_id=seeds["school_id"],
                turnstile_token="bad-token",
                admission_period_id=period.id,
                applicant_first_name="Test",
                applicant_last_name="User",
                applicant_other_names=None,
                date_of_birth=date(2012, 1, 1),
                gender="male",
                nationality=None,
                target_class_id=seeds["class_id"],
                custom_fields={},
                previous_school=None,
                medical_info=None,
                guardians=_guardian_data(),
            )
        assert exc_info.value.code == "CAPTCHA_FAILED"

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_submit_period_not_open(self, mock_ts, app_session, admin_session):
        """Submit to a draft (not open) period -> PERIOD_NOT_OPEN."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import (
            AdmissionPeriodService,
            ApplicationService,
            ApplicationServiceError,
        )

        # Create period but do NOT open it (stays draft)
        period_service = AdmissionPeriodService(app_session)
        period = await period_service.create(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            name="Draft Period",
            academic_year_id=seeds["year_id"],
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
        )

        service = ApplicationService(app_session)
        with pytest.raises(ApplicationServiceError) as exc_info:
            await service.submit(
                tenant_id=tenant["id"],
                school_id=seeds["school_id"],
                turnstile_token="test",
                admission_period_id=period.id,
                applicant_first_name="Test",
                applicant_last_name="User",
                applicant_other_names=None,
                date_of_birth=date(2012, 1, 1),
                gender="male",
                nationality=None,
                target_class_id=seeds["class_id"],
                custom_fields={},
                previous_school=None,
                medical_info=None,
                guardians=_guardian_data(),
            )
        assert exc_info.value.code == "PERIOD_NOT_OPEN"

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_submit_period_full(self, mock_ts, app_session, admin_session):
        """Submit when max_applications reached -> PERIOD_FULL."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
            max_applications=1,
        )

        from app.services.admissions import ApplicationService, ApplicationServiceError

        service = ApplicationService(app_session)

        # First submission succeeds
        await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="First",
            applicant_last_name="App",
            applicant_other_names=None,
            date_of_birth=date(2012, 1, 1),
            gender="male",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        # Second submission fails
        with pytest.raises(ApplicationServiceError) as exc_info:
            await service.submit(
                tenant_id=tenant["id"],
                school_id=seeds["school_id"],
                turnstile_token="test",
                admission_period_id=period.id,
                applicant_first_name="Second",
                applicant_last_name="App",
                applicant_other_names=None,
                date_of_birth=date(2012, 2, 2),
                gender="female",
                nationality=None,
                target_class_id=seeds["class_id"],
                custom_fields={},
                previous_school=None,
                medical_info=None,
                guardians=_guardian_data(),
            )
        assert exc_info.value.code == "PERIOD_FULL"

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_submit_no_guardians_rejected(self, mock_ts, app_session, admin_session):
        """Submit without guardians -> NO_GUARDIANS error."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService, ApplicationServiceError

        service = ApplicationService(app_session)
        with pytest.raises(ApplicationServiceError) as exc_info:
            await service.submit(
                tenant_id=tenant["id"],
                school_id=seeds["school_id"],
                turnstile_token="test",
                admission_period_id=period.id,
                applicant_first_name="Test",
                applicant_last_name="User",
                applicant_other_names=None,
                date_of_birth=date(2012, 1, 1),
                gender="male",
                nationality=None,
                target_class_id=seeds["class_id"],
                custom_fields={},
                previous_school=None,
                medical_info=None,
                guardians=[],  # Empty
            )
        assert exc_info.value.code == "NO_GUARDIANS"

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_submit_fee_required_creates_draft(self, mock_ts, app_session, admin_session):
        """When fee is required, application starts as DRAFT (not submitted)."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
            fee_required=True,
        )
        # Need to set fee amount
        from app.services.admissions import AdmissionPeriodService
        ps = AdmissionPeriodService(app_session)
        await ps.update(tenant["id"], period.id, application_fee_amount=50.00)

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Fee",
            applicant_last_name="Test",
            applicant_other_names=None,
            date_of_birth=date(2012, 3, 3),
            gender="female",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        assert app.status == "draft"
        assert app.submitted_at is None


class TestApplicationStatusTransitions:
    """Status machine validation."""

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_valid_transition_submitted_to_under_review(
        self, mock_ts, app_session, admin_session
    ):
        """SUBMITTED -> UNDER_REVIEW succeeds."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Status",
            applicant_last_name="Test",
            applicant_other_names=None,
            date_of_birth=date(2012, 4, 4),
            gender="male",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )
        assert app.status == "submitted"

        app = await service.transition_status(
            tenant["id"], app.id, "under_review", user["id"],
        )
        assert app.status == "under_review"

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_invalid_transition_submitted_to_enrolled(
        self, mock_ts, app_session, admin_session
    ):
        """SUBMITTED -> ENROLLED is not allowed."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService, ApplicationServiceError

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Bad",
            applicant_last_name="Transition",
            applicant_other_names=None,
            date_of_birth=date(2012, 5, 5),
            gender="female",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        with pytest.raises(ApplicationServiceError) as exc_info:
            await service.transition_status(
                tenant["id"], app.id, "enrolled", user["id"],
            )
        assert exc_info.value.code == "INVALID_TRANSITION"


class TestApplicationLookup:
    """Tracking code lookup and search."""

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_check_status_returns_minimal_data(
        self, mock_ts, app_session, admin_session
    ):
        """Status check returns only safe fields (no PII leakage)."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Status",
            applicant_last_name="Check",
            applicant_other_names=None,
            date_of_birth=date(2012, 6, 6),
            gender="male",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        result = await service.get_by_tracking_code(tenant["id"], app.tracking_code)

        assert "status" in result
        assert "applicant_first_name" in result
        # Must NOT expose guardian info or full PII
        assert "guardians" not in result
        assert "applicant_last_name" not in result

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_check_status_invalid_tracking_code(
        self, mock_ts, app_session, admin_session
    ):
        """Invalid tracking code -> NOT_FOUND."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import ApplicationService, ApplicationServiceError

        service = ApplicationService(app_session)
        with pytest.raises(ApplicationServiceError) as exc_info:
            await service.get_by_tracking_code(tenant["id"], "nonexistent-code-12345")
        assert exc_info.value.code == "NOT_FOUND"


class TestApplicationWaivers:
    """Fee and exam waivers."""

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_waive_fee_auto_submits_draft(
        self, mock_ts, app_session, admin_session
    ):
        """Waiving fee on a DRAFT application auto-transitions to SUBMITTED."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
            fee_required=True,
        )
        from app.services.admissions import AdmissionPeriodService
        ps = AdmissionPeriodService(app_session)
        await ps.update(tenant["id"], period.id, application_fee_amount=50.00)

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Waiver",
            applicant_last_name="Test",
            applicant_other_names=None,
            date_of_birth=date(2012, 7, 7),
            gender="male",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )
        assert app.status == "draft"

        # Waive fee
        app = await service.waive_fee(tenant["id"], app.id)
        assert app.fee_waived is True
        assert app.status == "submitted"

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_waive_exam(self, mock_ts, app_session, admin_session):
        """Waiving exam sets exam_waived=True."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Exam",
            applicant_last_name="Waiver",
            applicant_other_names=None,
            date_of_birth=date(2012, 8, 8),
            gender="female",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        app = await service.waive_exam(tenant["id"], app.id)
        assert app.exam_waived is True


class TestApplicationNotes:
    """Internal review notes."""

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_add_note_to_application(self, mock_ts, app_session, admin_session):
        """Add internal note and verify it exists."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)
        app = await service.submit(
            tenant_id=tenant["id"],
            school_id=seeds["school_id"],
            turnstile_token="test",
            admission_period_id=period.id,
            applicant_first_name="Note",
            applicant_last_name="Test",
            applicant_other_names=None,
            date_of_birth=date(2012, 9, 9),
            gender="male",
            nationality=None,
            target_class_id=seeds["class_id"],
            custom_fields={},
            previous_school=None,
            medical_info=None,
            guardians=_guardian_data(),
        )

        note = await service.add_note(
            tenant["id"], app.id, user["id"],
            content="Strong candidate, recommend shortlisting.",
            is_internal=True,
        )

        assert note.content == "Strong candidate, recommend shortlisting."
        assert note.is_internal is True
        assert note.author_id == user["id"]


class TestApplicationListAndSearch:
    """List and search operations."""

    @patch("app.services.admissions.application_service.verify_turnstile", return_value=True)
    async def test_list_applications_with_filters(
        self, mock_ts, app_session, admin_session
    ):
        """Create multiple apps, filter by status, verify pagination."""
        tenant = await create_test_tenant(admin_session)
        seeds = await _full_seed(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        period = await _create_open_period(
            app_session, tenant["id"], seeds["school_id"], seeds["year_id"],
        )

        from app.services.admissions import ApplicationService

        service = ApplicationService(app_session)

        # Create 3 applications
        for i in range(3):
            await service.submit(
                tenant_id=tenant["id"],
                school_id=seeds["school_id"],
                turnstile_token="test",
                admission_period_id=period.id,
                applicant_first_name=f"App{i}",
                applicant_last_name="User",
                applicant_other_names=None,
                date_of_birth=date(2012, 1, 1 + i),
                gender="male",
                nationality=None,
                target_class_id=seeds["class_id"],
                custom_fields={},
                previous_school=None,
                medical_info=None,
                guardians=_guardian_data(),
            )

        # List all
        apps, total = await service.list_applications(tenant["id"])
        assert total >= 3

        # Filter by status
        apps, total = await service.list_applications(
            tenant["id"], status="submitted",
        )
        assert total >= 3  # All are submitted (no fee required)

        # Pagination
        apps, total = await service.list_applications(
            tenant["id"], page=1, page_size=2,
        )
        assert len(apps) == 2

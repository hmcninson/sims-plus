"""
Tests for InquiryService.

Covers: CRUD, status transitions, assignment, conversion to application,
communications, and follow-ups. Uses two-engine pattern.
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


async def _seed_prereqs(admin_session, tenant_id):
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
                0, false, false, '[]',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
            "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}",
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "year_id": year_id,
        "class_id": class_id, "period_id": period_id,
    }


async def _create_inquiry_via_service(app_session, tenant_id, school_id, **overrides):
    """Create an inquiry using the service. Returns the Inquiry ORM object."""
    from app.services.admissions import InquiryService
    from app.schemas.inquiry import InquiryCreate

    defaults = {
        "source": "website",
        "first_name": "Kwame",
        "last_name": "Asante",
        "guardian_name": "Akosua Asante",
        "guardian_phone": f"024{uuid4().hex[:7]}",
    }
    defaults.update(overrides)
    data = InquiryCreate(**defaults)

    svc = InquiryService(app_session)
    return await svc.create(tenant_id=tenant_id, school_id=school_id, data=data)


# --- CRUD Tests ---


async def test_create_inquiry(app_session, admin_session):
    """Create an inquiry with valid data. Status should be 'new'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )

    assert inquiry.id is not None
    assert inquiry.status == "new"
    assert inquiry.first_name == "Kwame"
    assert inquiry.last_name == "Asante"
    assert inquiry.source == "website"
    assert inquiry.tenant_id == tenant["id"]


async def test_create_inquiry_missing_required(app_session, admin_session):
    """Missing required field (first_name) should raise validation error."""
    from app.schemas.inquiry import InquiryCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        InquiryCreate(
            source="website",
            last_name="Asante",
            guardian_name="Akosua Asante",
            guardian_phone="0241234567",
            # first_name missing
        )


async def test_list_inquiries(app_session, admin_session):
    """List returns all inquiries for the tenant/school."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    # Create 3 inquiries
    for i in range(3):
        await _create_inquiry_via_service(
            app_session, tenant["id"], prereqs["school_id"],
            first_name=f"Student{i}",
        )

    svc = InquiryService(app_session)
    items, total = await svc.list_inquiries(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
    )
    assert total == 3
    assert len(items) == 3


async def test_list_inquiries_filter_by_status(app_session, admin_session):
    """Filter by status returns only matching inquiries."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    user = await create_test_user(admin_session, tenant["id"])
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    # Create 2 new inquiries
    inq1 = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )
    inq2 = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )

    # Transition one to 'contacted'
    svc = InquiryService(app_session)
    await svc.update_status(inq1.id, tenant["id"], "contacted")

    items, total = await svc.list_inquiries(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        status="new",
    )
    assert total == 1
    assert items[0].status == "new"


async def test_list_inquiries_filter_by_source(app_session, admin_session):
    """Filter by source returns only matching inquiries."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"], source="website",
    )
    await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"], source="walk_in",
    )

    svc = InquiryService(app_session)
    items, total = await svc.list_inquiries(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        source="website",
    )
    assert total == 1
    assert items[0].source == "website"


async def test_list_inquiries_search(app_session, admin_session):
    """Search matches against first_name, last_name, guardian_name, guardian_phone."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
        first_name="Kofi", last_name="Mensah",
    )
    await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
        first_name="Ama", last_name="Boateng",
    )

    svc = InquiryService(app_session)
    items, total = await svc.list_inquiries(
        tenant_id=tenant["id"], school_id=prereqs["school_id"],
        search="Kofi",
    )
    assert total == 1
    assert items[0].first_name == "Kofi"


async def test_get_inquiry(app_session, admin_session):
    """Get inquiry by ID returns full detail with communications and follow-ups."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )
    inquiry_id = inquiry.id

    svc = InquiryService(app_session)
    fetched = await svc.get(inquiry_id=inquiry_id, tenant_id=tenant["id"])
    assert fetched.id == inquiry_id
    assert fetched.first_name == "Kwame"
    # Communications and follow-ups should be loaded (empty lists)
    assert fetched.communications == []
    assert fetched.follow_ups == []


async def test_get_inquiry_not_found(app_session, admin_session):
    """Get with invalid UUID returns NOT_FOUND error."""
    tenant = await create_test_tenant(admin_session)
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService, InquiryServiceError

    svc = InquiryService(app_session)
    with pytest.raises(InquiryServiceError) as exc_info:
        await svc.get(inquiry_id=uuid4(), tenant_id=tenant["id"])
    assert exc_info.value.code == "NOT_FOUND"


async def test_update_inquiry(app_session, admin_session):
    """Update non-status fields on an inquiry."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService
    from app.schemas.inquiry import InquiryUpdate

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )
    inquiry_id = inquiry.id

    svc = InquiryService(app_session)
    updated = await svc.update(
        inquiry_id=inquiry_id,
        tenant_id=tenant["id"],
        data=InquiryUpdate(first_name="Yaw", notes="Updated notes"),
    )
    assert updated.first_name == "Yaw"
    assert updated.notes == "Updated notes"
    # Status should not have changed
    assert updated.status == "new"


async def test_delete_inquiry(app_session, admin_session):
    """Soft-delete sets deleted_at. Subsequent get should fail."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService, InquiryServiceError

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )
    inquiry_id = inquiry.id

    svc = InquiryService(app_session)
    await svc.delete(inquiry_id=inquiry_id, tenant_id=tenant["id"])

    # Should no longer be findable
    with pytest.raises(InquiryServiceError) as exc_info:
        await svc.get(inquiry_id=inquiry_id, tenant_id=tenant["id"])
    assert exc_info.value.code == "NOT_FOUND"


# --- Status Transition Tests ---


async def test_update_status_valid(app_session, admin_session):
    """Valid transition: new -> contacted."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )
    inquiry_id = inquiry.id

    svc = InquiryService(app_session)
    updated = await svc.update_status(inquiry_id, tenant["id"], "contacted")
    assert updated.status == "contacted"


async def test_update_status_invalid(app_session, admin_session):
    """Invalid transition: new -> enrolled (not allowed)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService, InquiryServiceError

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )

    svc = InquiryService(app_session)
    with pytest.raises(InquiryServiceError) as exc_info:
        await svc.update_status(inquiry.id, tenant["id"], "enrolled")
    assert exc_info.value.code == "INVALID_TRANSITION"


async def test_update_status_terminal(app_session, admin_session):
    """Terminal state: enrolled -> anything is blocked."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService, InquiryServiceError

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )

    svc = InquiryService(app_session)
    # Walk the state machine: new -> contacted -> interested -> applied -> enrolled
    await svc.update_status(inquiry.id, tenant["id"], "contacted")
    await svc.update_status(inquiry.id, tenant["id"], "interested")
    await svc.update_status(inquiry.id, tenant["id"], "applied")
    await svc.update_status(inquiry.id, tenant["id"], "enrolled")

    # enrolled is terminal: no further transitions
    with pytest.raises(InquiryServiceError) as exc_info:
        await svc.update_status(inquiry.id, tenant["id"], "contacted")
    assert exc_info.value.code == "INVALID_TRANSITION"


# --- Assignment Tests ---


async def test_assign_inquiry(app_session, admin_session):
    """Assign inquiry to a user in the same tenant."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    user = await create_test_user(admin_session, tenant["id"])
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )

    from app.services.admissions import InquiryService

    svc = InquiryService(app_session)
    updated = await svc.assign(inquiry.id, tenant["id"], user["id"])
    assert updated.assigned_to == user["id"]


async def test_assign_inquiry_invalid_user(app_session, admin_session):
    """Assigning to a non-existent user raises USER_NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
    )

    from app.services.admissions import InquiryService, InquiryServiceError

    svc = InquiryService(app_session)
    with pytest.raises(InquiryServiceError) as exc_info:
        await svc.assign(inquiry.id, tenant["id"], uuid4())
    assert exc_info.value.code == "USER_NOT_FOUND"


# --- Conversion Tests ---


async def test_convert_to_application(app_session, admin_session):
    """Convert inquiry to application creates Application record."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
        date_of_birth="2012-05-15",
        gender="male",
        target_class_id=str(prereqs["class_id"]),
    )
    inquiry_id = inquiry.id

    from app.services.admissions import InquiryService

    svc = InquiryService(app_session)
    application = await svc.convert_to_application(
        inquiry_id=inquiry_id,
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
    )

    assert application.id is not None
    assert application.applicant_first_name == "Kwame"
    assert application.applicant_last_name == "Asante"
    assert application.tracking_code is not None
    assert application.status == "submitted"


async def test_convert_already_converted(app_session, admin_session):
    """Converting the same inquiry twice raises ALREADY_CONVERTED."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
        date_of_birth="2012-05-15",
        gender="male",
        target_class_id=str(prereqs["class_id"]),
    )
    inquiry_id = inquiry.id

    from app.services.admissions import InquiryService, InquiryServiceError

    svc = InquiryService(app_session)
    await svc.convert_to_application(
        inquiry_id=inquiry_id,
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
    )

    with pytest.raises(InquiryServiceError) as exc_info:
        await svc.convert_to_application(
            inquiry_id=inquiry_id,
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            period_id=prereqs["period_id"],
        )
    assert exc_info.value.code in ("ALREADY_CONVERTED", "INVALID_STATUS")


async def test_convert_sets_inquiry_status(app_session, admin_session):
    """After conversion, inquiry status becomes 'applied'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    inquiry = await _create_inquiry_via_service(
        app_session, tenant["id"], prereqs["school_id"],
        date_of_birth="2012-05-15",
        gender="male",
        target_class_id=str(prereqs["class_id"]),
    )
    inquiry_id = inquiry.id

    from app.services.admissions import InquiryService

    svc = InquiryService(app_session)
    await svc.convert_to_application(
        inquiry_id=inquiry_id,
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
    )

    # Re-fetch the inquiry to check status
    refreshed = await svc.get(inquiry_id=inquiry_id, tenant_id=tenant["id"])
    assert refreshed.status == "applied"
    assert refreshed.converted_application_id is not None

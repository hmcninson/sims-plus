"""
Tests for Enrollment Checklist, Deposit, and Boarding Status (Phase 3).

Covers: checklist CRUD, item completion, auto-complete, enrollment guards,
boarding status assignment, deposit recording, and confirmation generation.
Uses the two-engine pattern (admin_session for seeding, app_session for RLS queries).
"""

import pytest
import secrets
from datetime import date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_prereqs(admin_session, tenant_id):
    """Seed school, academic year, class, admission period, user. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    user_id = uuid4()

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
                'shs', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
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
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:6]}@example.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash"},
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "year_id": year_id,
        "class_id": class_id, "period_id": period_id,
        "user_id": user_id,
    }


async def _seed_accepted_application(
    admin_session, tenant_id, school_id, period_id, class_id,
    *, boarding_status=None,
):
    """Seed an application in ACCEPTED status. Returns app_id."""
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)

    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                boarding_status,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tracking_code, 'Kwame', 'Asante',
                '2012-05-15', 'male', CAST(:cid AS uuid), 'accepted',
                '{}', false, false,
                :boarding_status,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant_id), "sid": str(school_id),
            "pid": str(period_id), "tracking_code": tracking_code,
            "cid": str(class_id), "boarding_status": boarding_status,
        },
    )
    await admin_session.commit()
    return app_id


async def _seed_period_with_template(admin_session, tenant_id, school_id, year_id, template):
    """Seed an admission period with an enrollment_checklist_template. Returns period_id."""
    period_id = uuid4()
    import json

    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes,
                enrollment_checklist_template,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]',
                :template,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
            "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}",
            "template": json.dumps(template),
        },
    )
    await admin_session.commit()
    return period_id


# --- Checklist CRUD Tests ---


async def test_create_checklist(app_session, admin_session):
    """Create checklist for accepted application. Items populated from period template."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "Birth certificate", "is_required": True},
        {"item_type": "payment", "item_name": "Enrollment deposit", "is_required": True},
        {"item_type": "form", "item_name": "Health form", "is_required": False},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    checklist = await svc.create_enrollment_checklist(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        application_id=app_id,
    )

    assert checklist.id is not None
    assert checklist.application_id == app_id
    assert checklist.checklist_type == "standard"
    assert checklist.completed_at is None

    # Reload with items
    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert len(checklist.items) == 3
    item_names = {i.item_name for i in checklist.items}
    assert "Birth certificate" in item_names
    assert "Enrollment deposit" in item_names
    assert "Health form" in item_names


async def test_create_checklist_no_template(app_session, admin_session):
    """Period without template -> empty checklist (0 items)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    checklist = await svc.create_enrollment_checklist(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        application_id=app_id,
    )

    assert checklist.id is not None
    # Reload with items
    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert len(checklist.items) == 0


async def test_create_checklist_duplicate(app_session, admin_session):
    """Second create for same application -> CHECKLIST_EXISTS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService, EnrollmentError
    svc = EnrollmentService(app_session)

    await svc.create_enrollment_checklist(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        application_id=app_id,
    )

    with pytest.raises(EnrollmentError) as exc_info:
        await svc.create_enrollment_checklist(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            application_id=app_id,
        )
    assert exc_info.value.code == "CHECKLIST_EXISTS"


async def test_create_checklist_wrong_status(app_session, admin_session):
    """Checklist for non-accepted application -> INVALID_STATUS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    # Seed a SUBMITTED application (not accepted)
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
                :tracking_code, 'Ama', 'Mensah',
                '2012-01-01', 'female', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]), "pid": str(prereqs["period_id"]),
            "tracking_code": secrets.token_urlsafe(48),
            "cid": str(prereqs["class_id"]),
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService, EnrollmentError
    svc = EnrollmentService(app_session)

    with pytest.raises(EnrollmentError) as exc_info:
        await svc.create_enrollment_checklist(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            application_id=app_id,
        )
    assert exc_info.value.code == "INVALID_STATUS"


async def test_get_checklist(app_session, admin_session):
    """Get checklist returns items and correct data."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "ID copy", "is_required": True},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)

    checklist = await svc.get_checklist(tenant["id"], app_id)

    assert checklist.application_id == app_id
    assert len(checklist.items) == 1
    assert checklist.items[0].item_name == "ID copy"
    assert checklist.items[0].is_required is True
    assert checklist.items[0].is_completed is False


async def test_get_checklist_not_found(app_session, admin_session):
    """Get checklist for application without one -> NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService, EnrollmentError
    svc = EnrollmentService(app_session)

    with pytest.raises(EnrollmentError) as exc_info:
        await svc.get_checklist(tenant["id"], app_id)
    assert exc_info.value.code == "NOT_FOUND"


# --- Item Completion Tests ---


async def test_complete_item(app_session, admin_session):
    """Mark item complete -> is_completed=True, completed_at set."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "Birth cert", "is_required": True},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)

    checklist = await svc.get_checklist(tenant["id"], app_id)
    item_id = checklist.items[0].id

    item = await svc.complete_checklist_item(
        tenant_id=tenant["id"],
        item_id=item_id,
        user_id=prereqs["user_id"],
    )

    assert item.is_completed is True
    assert item.completed_at is not None
    assert item.completed_by == prereqs["user_id"]


async def test_complete_item_with_notes(app_session, admin_session):
    """Complete item with notes -> notes saved."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "Report card", "is_required": True},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)

    checklist = await svc.get_checklist(tenant["id"], app_id)
    item_id = checklist.items[0].id

    item = await svc.complete_checklist_item(
        tenant_id=tenant["id"],
        item_id=item_id,
        user_id=prereqs["user_id"],
        notes="Verified original document",
    )

    assert item.notes == "Verified original document"
    assert item.is_completed is True


async def test_auto_complete_checklist(app_session, admin_session):
    """All required items done -> checklist.completed_at auto-set."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "Birth cert", "is_required": True},
        {"item_type": "form", "item_name": "Health form", "is_required": True},
        {"item_type": "form", "item_name": "Optional form", "is_required": False},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)

    checklist = await svc.get_checklist(tenant["id"], app_id)
    required_items = [i for i in checklist.items if i.is_required]
    assert len(required_items) == 2

    # Complete first required item
    await svc.complete_checklist_item(
        tenant["id"], required_items[0].id, user_id=prereqs["user_id"],
    )
    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert checklist.completed_at is None  # Not yet -- one required left

    # Complete second required item (optional not needed)
    await svc.complete_checklist_item(
        tenant["id"], required_items[1].id, user_id=prereqs["user_id"],
    )
    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert checklist.completed_at is not None  # Auto-completed
    assert checklist.completed_by == prereqs["user_id"]


# --- Enrollment Guard Tests ---


async def test_enroll_with_incomplete_checklist(app_session, admin_session):
    """Enrollment with incomplete required checklist items -> CHECKLIST_INCOMPLETE."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "Birth cert", "is_required": True},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService, EnrollmentError
    svc = EnrollmentService(app_session)

    # Create checklist but do NOT complete items
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)

    with pytest.raises(EnrollmentError) as exc_info:
        await svc.enroll(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            application_id=app_id,
            enrolled_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "CHECKLIST_INCOMPLETE"


async def test_enroll_without_checklist(app_session, admin_session):
    """No checklist -> enrollment proceeds (AD-3: checklist is optional)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    # Patch out notification/welcome pack to avoid external dependencies
    with patch.object(svc, "generate_enrollment_confirmation", new_callable=AsyncMock), \
         patch.object(svc, "send_welcome_pack", new_callable=AsyncMock):
        result = await svc.enroll(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            application_id=app_id,
            enrolled_by=prereqs["user_id"],
        )

    assert result["already_enrolled"] is False
    assert result["student_id"] is not None
    assert result["student_number"] is not None


# --- Boarding Status Tests ---


async def test_assign_boarding_adds_items(app_session, admin_session):
    """Set boarding -> boarding items added to existing standard checklist."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    template = [
        {"item_type": "document", "item_name": "Birth cert", "is_required": True},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    # Create standard checklist first
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)

    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert len(checklist.items) == 1  # Just the template item
    assert checklist.checklist_type == "standard"

    # Assign boarding
    app_obj, items_added = await svc.assign_boarding_status(
        tenant_id=tenant["id"],
        application_id=app_id,
        boarding_status="boarding",
    )

    assert items_added == 4  # _BOARDING_CHECKLIST_ITEMS has 4 entries
    assert app_obj.boarding_status == "boarding"

    # Expire cached objects so selectinload re-fetches the items relationship
    app_session.expire_all()
    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert checklist.checklist_type == "boarding"
    assert len(checklist.items) == 5  # 1 template + 4 boarding


async def test_boarding_items_not_duplicated(app_session, admin_session):
    """Boarding items not added again if checklist is already type 'boarding'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])

    # Create application already marked as boarding
    template = [
        {"item_type": "document", "item_name": "ID copy", "is_required": True},
    ]
    period_id = await _seed_period_with_template(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["year_id"], template,
    )
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        period_id, prereqs["class_id"],
        boarding_status="boarding",
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    # Create checklist -- boarding items auto-added because boarding_status=='boarding'
    await svc.create_enrollment_checklist(tenant["id"], prereqs["school_id"], app_id)
    checklist = await svc.get_checklist(tenant["id"], app_id)
    initial_count = len(checklist.items)  # 1 template + 4 boarding = 5
    assert checklist.checklist_type == "boarding"

    # Re-assign boarding -- should NOT add more items (already boarding type)
    _, items_added = await svc.assign_boarding_status(
        tenant_id=tenant["id"],
        application_id=app_id,
        boarding_status="boarding",
    )

    assert items_added == 0  # Checklist already boarding type -- no duplicates

    checklist = await svc.get_checklist(tenant["id"], app_id)
    assert len(checklist.items) == initial_count  # Same count


# --- Deposit Tests ---


async def test_record_deposit(app_session, admin_session):
    """Record deposit -> amount, reference, paid_at saved on application."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    app_obj = await svc.record_enrollment_deposit(
        tenant_id=tenant["id"],
        application_id=app_id,
        amount=Decimal("500.00"),
        reference="TXN-12345",
    )

    assert app_obj.enrollment_deposit_paid is True
    assert app_obj.enrollment_deposit_amount == Decimal("500.00")
    assert app_obj.enrollment_deposit_reference == "TXN-12345"
    assert app_obj.enrollment_deposit_paid_at is not None


async def test_record_deposit_duplicate(app_session, admin_session):
    """Second deposit for same app -> DEPOSIT_ALREADY_PAID."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService, EnrollmentError
    svc = EnrollmentService(app_session)

    await svc.record_enrollment_deposit(
        tenant_id=tenant["id"],
        application_id=app_id,
        amount=Decimal("500.00"),
        reference="TXN-001",
    )

    with pytest.raises(EnrollmentError) as exc_info:
        await svc.record_enrollment_deposit(
            tenant_id=tenant["id"],
            application_id=app_id,
            amount=Decimal("500.00"),
            reference="TXN-002",
        )
    assert exc_info.value.code == "DEPOSIT_ALREADY_PAID"


# --- Confirmation Generation Test ---


async def test_generate_confirmation(app_session, admin_session):
    """Generate enrollment confirmation returns URL (mock S3)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    app_id = await _seed_accepted_application(
        admin_session, tenant["id"], prereqs["school_id"],
        prereqs["period_id"], prereqs["class_id"],
    )

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions.enrollment_service import EnrollmentService
    svc = EnrollmentService(app_session)

    mock_s3 = MagicMock()
    mock_s3.upload_file.return_value = "https://s3.example.com/confirmation.pdf"

    with patch("app.services.s3.get_s3_service", return_value=mock_s3), \
         patch.object(svc, "_render_pdf", return_value=b"%PDF-fake-content"):
        url = await svc.generate_enrollment_confirmation(
            tenant_id=tenant["id"],
            application_id=app_id,
        )

    assert url == "https://s3.example.com/confirmation.pdf"
    mock_s3.upload_file.assert_called_once()

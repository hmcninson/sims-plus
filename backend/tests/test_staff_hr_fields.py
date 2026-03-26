"""
Tests for staff HR field additions (Phase 1):
tin_number, employment_type, ges_staff_id, nationality, marital_status.

Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_staff_prereqs(admin_session, tenant_id):
    """Seed school and user. Returns dict with IDs."""
    school_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )

    await admin_session.commit()
    return {"school_id": school_id, "user_id": user_id}


def _base_staff_kwargs(tenant_id, school_id):
    """Return minimal kwargs for StaffService.create_staff()."""
    return dict(
        tenant_id=tenant_id,
        staff_id=f"STF-{uuid4().hex[:8]}",
        first_name="Kwame",
        last_name="Mensah",
        email=f"staff-{uuid4().hex[:8]}@test.com",
        phone="0241234567",
        gender="male",
        job_title="Teacher",
        employment_date=date(2024, 9, 1),
        staff_type="teaching",
        status="active",
        school_id=school_id,
    )


# --- Tests ---


async def test_create_staff_with_tin_number(app_session, admin_session):
    """Staff created with tin_number stores it correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
        tin_number="GHA-TIN-123456789",
    )

    assert staff.tin_number == "GHA-TIN-123456789"


async def test_create_staff_with_employment_type(app_session, admin_session):
    """Staff created with each employment_type value stores it correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)

    for emp_type in ("full_time", "part_time", "contract", "temporary", "intern"):
        staff = await svc.create_staff(
            **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
            employment_type=emp_type,
        )
        assert staff.employment_type.value == emp_type


async def test_create_staff_with_ges_staff_id(app_session, admin_session):
    """Staff created with ges_staff_id stores it correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
        ges_staff_id="GES-2024-00123",
    )

    assert staff.ges_staff_id == "GES-2024-00123"


async def test_create_staff_with_nationality_marital_status(app_session, admin_session):
    """Staff created with nationality and marital_status stores them correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
        nationality="Ghanaian",
        marital_status="married",
    )

    assert staff.nationality == "Ghanaian"
    assert staff.marital_status == "married"


async def test_update_staff_tin_number(app_session, admin_session):
    """Updating an existing staff member's TIN number works."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
    )
    staff_id = staff.id
    assert staff.tin_number is None

    updated = await svc.update_staff(
        tenant["id"], staff_id,
        tin_number="GHA-TIN-999888777",
    )

    assert updated.tin_number == "GHA-TIN-999888777"


async def test_update_employment_type_records_history(app_session, admin_session):
    """Updating employment_type with current_user_id auto-records a history event."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService, StaffHistoryService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
        employment_type="full_time",
    )
    staff_id = staff.id

    # Update with current_user_id to trigger auto-history recording
    await svc.update_staff(
        tenant["id"], staff_id,
        current_user_id=prereqs["user_id"],
        employment_type="contract",
    )

    # Check that a history event was recorded
    history_svc = StaffHistoryService(app_session)
    events = await history_svc.list_history(tenant["id"], staff_id)

    assert len(events) >= 1
    # The event type for employment_type changes is contract_renewed
    emp_events = [e for e in events if e.event_type.value == "contract_renewed"]
    assert len(emp_events) == 1
    assert emp_events[0].previous_value == "full_time"
    assert emp_events[0].new_value == "contract"


async def test_create_staff_without_new_fields(app_session, admin_session):
    """Staff created without any new HR fields defaults them to None."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
    )

    assert staff.tin_number is None
    assert staff.employment_type is None
    assert staff.ges_staff_id is None
    assert staff.nationality is None
    assert staff.marital_status is None


async def test_update_staff_all_new_fields_at_once(app_session, admin_session):
    """Update all new HR fields in a single update call."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService

    svc = StaffService(app_session)
    staff = await svc.create_staff(
        **_base_staff_kwargs(tenant["id"], prereqs["school_id"]),
    )
    staff_id = staff.id

    updated = await svc.update_staff(
        tenant["id"], staff_id,
        tin_number="TIN-UPDATE-001",
        employment_type="part_time",
        ges_staff_id="GES-UPD-001",
        nationality="Nigerian",
        marital_status="single",
    )

    assert updated.tin_number == "TIN-UPDATE-001"
    assert updated.employment_type.value == "part_time"
    assert updated.ges_staff_id == "GES-UPD-001"
    assert updated.nationality == "Nigerian"
    assert updated.marital_status == "single"

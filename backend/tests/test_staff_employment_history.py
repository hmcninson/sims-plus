"""
Tests for staff employment history tracking (Phase 1).

Covers: manual event creation, list ordering, auto-record on job_title/
department/status changes, no-record when non-tracked fields change,
and tenant isolation.
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


async def _seed_history_prereqs(admin_session, tenant_id):
    """Seed school, staff, user, and department. Returns dict with IDs."""
    school_id = uuid4()
    staff_db_id = uuid4()
    user_id = uuid4()
    dept_id = uuid4()

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
            INSERT INTO departments (id, tenant_id, name, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(dept_id), "tid": str(tenant_id),
         "name": f"Dept-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title,
                employment_date,
                created_at, updated_at)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Ama', 'Boateng',
                'female', :email, '0241234567',
                'teaching', 'active', 'Teacher',
                '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(staff_db_id), "tid": str(tenant_id), "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"staff-{uuid4().hex[:8]}@test.com",
        },
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
    return {
        "school_id": school_id,
        "staff_id": staff_db_id,
        "user_id": user_id,
        "department_id": dept_id,
    }


# --- Tests ---


async def test_create_manual_employment_event(app_session, admin_session):
    """Manually recording an employment event stores all fields correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffHistoryService

    svc = StaffHistoryService(app_session)
    record = await svc.record_event(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        event_type="promoted",
        effective_date=date(2026, 1, 15),
        recorded_by=prereqs["user_id"],
        school_id=prereqs["school_id"],
        previous_job_title="Teacher",
        new_job_title="Senior Teacher",
        notes="Annual promotion",
    )

    assert record.id is not None
    assert record.event_type.value == "promoted"
    assert record.effective_date == date(2026, 1, 15)
    assert record.previous_job_title == "Teacher"
    assert record.new_job_title == "Senior Teacher"
    assert record.notes == "Annual promotion"


async def test_list_employment_history_ordered_by_date(app_session, admin_session):
    """History events are returned newest first (effective_date DESC)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffHistoryService

    svc = StaffHistoryService(app_session)

    # Create two events with different dates
    await svc.record_event(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        event_type="hired",
        effective_date=date(2020, 9, 1),
        recorded_by=prereqs["user_id"],
        notes="Initial hire",
    )
    await svc.record_event(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        event_type="promoted",
        effective_date=date(2024, 1, 10),
        recorded_by=prereqs["user_id"],
        notes="Promotion",
    )

    history = await svc.list_history(tenant["id"], prereqs["staff_id"])

    assert len(history) == 2
    # Newest first
    assert history[0].effective_date == date(2024, 1, 10)
    assert history[1].effective_date == date(2020, 9, 1)


async def test_auto_record_on_job_title_change(app_session, admin_session):
    """Updating job_title via StaffService auto-creates a title_changed event."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService, StaffHistoryService

    svc = StaffService(app_session)
    await svc.update_staff(
        tenant["id"], prereqs["staff_id"],
        current_user_id=prereqs["user_id"],
        job_title="Head of Department",
    )

    history_svc = StaffHistoryService(app_session)
    events = await history_svc.list_history(tenant["id"], prereqs["staff_id"])

    title_events = [e for e in events if e.event_type.value == "title_changed"]
    assert len(title_events) == 1
    assert title_events[0].previous_job_title == "Teacher"
    assert title_events[0].new_job_title == "Head of Department"


async def test_auto_record_on_department_change(app_session, admin_session):
    """Updating department_id auto-creates a department_changed event."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_history_prereqs(admin_session, tenant["id"])

    # Create a second department
    dept2_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO departments (id, tenant_id, name, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(dept2_id), "tid": str(tenant["id"]),
         "name": f"Dept2-{uuid4().hex[:6]}"},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService, StaffHistoryService

    svc = StaffService(app_session)
    # Set initial department
    await svc.update_staff(
        tenant["id"], prereqs["staff_id"],
        current_user_id=prereqs["user_id"],
        department_id=prereqs["department_id"],
    )

    # Change to second department
    await svc.update_staff(
        tenant["id"], prereqs["staff_id"],
        current_user_id=prereqs["user_id"],
        department_id=dept2_id,
    )

    history_svc = StaffHistoryService(app_session)
    events = await history_svc.list_history(tenant["id"], prereqs["staff_id"])
    dept_events = [e for e in events if e.event_type.value == "department_changed"]

    # We expect 2 events: initial set (None->dept1) and change (dept1->dept2)
    assert len(dept_events) == 2
    # Verify at least one event has new_department_id == dept2_id
    dept2_events = [e for e in dept_events if e.new_department_id == dept2_id]
    assert len(dept2_events) == 1
    assert dept2_events[0].previous_department_id == prereqs["department_id"]


async def test_auto_record_on_status_change(app_session, admin_session):
    """Updating status auto-creates a status_changed event."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService, StaffHistoryService

    svc = StaffService(app_session)
    await svc.update_staff(
        tenant["id"], prereqs["staff_id"],
        current_user_id=prereqs["user_id"],
        status="on_leave",
    )

    history_svc = StaffHistoryService(app_session)
    events = await history_svc.list_history(tenant["id"], prereqs["staff_id"])
    status_events = [e for e in events if e.event_type.value == "status_changed"]

    assert len(status_events) == 1
    assert status_events[0].previous_value == "active"
    assert status_events[0].new_value == "on_leave"


async def test_no_auto_record_when_field_unchanged(app_session, admin_session):
    """Updating a non-tracked field (first_name) creates no history events."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_history_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffService, StaffHistoryService

    svc = StaffService(app_session)
    await svc.update_staff(
        tenant["id"], prereqs["staff_id"],
        current_user_id=prereqs["user_id"],
        first_name="Akosua",
    )

    history_svc = StaffHistoryService(app_session)
    events = await history_svc.list_history(tenant["id"], prereqs["staff_id"])

    assert len(events) == 0


async def test_employment_history_tenant_isolation(app_session, admin_session):
    """Tenant A's employment history is invisible from Tenant B (RLS)."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs_a = await _seed_history_prereqs(admin_session, tenant_a["id"])
    prereqs_b = await _seed_history_prereqs(admin_session, tenant_b["id"])

    # Record event in Tenant A
    await set_app_tenant_context(app_session, tenant_a["id"])
    from app.services.staff import StaffHistoryService

    svc_a = StaffHistoryService(app_session)
    await svc_a.record_event(
        tenant_id=tenant_a["id"],
        staff_id=prereqs_a["staff_id"],
        event_type="hired",
        effective_date=date(2020, 9, 1),
        recorded_by=prereqs_a["user_id"],
    )

    # Switch to Tenant B and check their staff's history is empty
    await set_app_tenant_context(app_session, tenant_b["id"])
    svc_b = StaffHistoryService(app_session)
    events = await svc_b.list_history(tenant_b["id"], prereqs_b["staff_id"])

    assert len(events) == 0

    # Also verify Tenant B can't query Tenant A's staff
    from app.services.staff import StaffServiceError

    with pytest.raises(StaffServiceError) as exc_info:
        await svc_b.list_history(tenant_b["id"], prereqs_a["staff_id"])
    assert exc_info.value.code == "staff_not_found"

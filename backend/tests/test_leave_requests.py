"""
Tests for leave request lifecycle (Phase 3 — Part B).

Covers: submit, weekend exclusion, holiday exclusion, overlap rejection,
insufficient balance, approve, reject, cancel (pending/approved/started),
auto-approve, and IDOR prevention.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


def _next_monday(from_date=None):
    """Return the next Monday on or after from_date (defaults to tomorrow)."""
    d = from_date or (date.today() + timedelta(days=1))
    days_until = (7 - d.weekday()) % 7
    if days_until == 0 and d.weekday() != 0:
        days_until = 7
    return d + timedelta(days=days_until)


async def _seed_request_prereqs(admin_session, tenant_id, *, num_staff=1):
    """
    Seed school, academic year, leave type, staff, user, and initialized balance.
    Returns dict with IDs.
    """
    school_id = uuid4()
    acad_year_id = uuid4()
    lt_id = uuid4()
    user_id = uuid4()
    staff_ids = []

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
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(acad_year_id), "tid": str(tenant_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO leave_types (id, tenant_id, name, code,
                default_days_per_year, max_carryover_days, is_active,
                requires_approval,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Annual Leave', 'ANNUAL',
                20.0, 5.0, true, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(lt_id), "tid": str(tenant_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Admin', 'Reviewer', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )

    for i in range(num_staff):
        sid = uuid4()
        staff_ids.append(sid)
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title, employment_date,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, :fname, 'TestStaff',
                    'male', :email, '0241234567',
                    'teaching', 'active', 'Teacher', '2020-09-01',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(sid), "tid": str(tenant_id), "sid": str(school_id),
                "staff_num": f"STF-{uuid4().hex[:8]}",
                "fname": f"Staff{i}",
                "email": f"staff-{uuid4().hex[:8]}@test.com",
            },
        )

    # Initialize balances via raw SQL (admin bypasses RLS)
    for sid in staff_ids:
        await admin_session.execute(
            text("""
                INSERT INTO leave_balances (id, tenant_id, staff_id, leave_type_id,
                    academic_year_id, entitled_days, used_days, pending_days, carried_over,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                    CAST(:year_id AS uuid), 20.0, 0.0, 0.0, 0.0,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(uuid4()), "tid": str(tenant_id),
                "staff_id": str(sid), "lt_id": str(lt_id),
                "year_id": str(acad_year_id),
            },
        )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "academic_year_id": acad_year_id,
        "leave_type_id": lt_id,
        "user_id": user_id,
        "staff_ids": staff_ids,
    }


# --- Tests ---


async def test_submit_leave_request(app_session, admin_session):
    """Submitting a leave request calculates days and sets status to pending."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()
    # Mon-Tue = 2 working days
    request = await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday + timedelta(days=1),
            "reason": "Personal matter",
        },
    )

    assert request.id is not None
    assert request.days_requested == Decimal("2")
    assert request.status.value == "pending"
    assert request.reason == "Personal matter"


async def test_submit_excludes_weekends(app_session, admin_session):
    """A 7-day span Mon-Sun counts only 5 working days."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()
    sunday = monday + timedelta(days=6)

    request = await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": sunday,
            "reason": "Week off",
        },
    )

    assert request.days_requested == Decimal("5")


async def test_submit_excludes_holidays(app_session, admin_session):
    """School holidays within the range are excluded from working days."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])

    monday = _next_monday()
    # Add a holiday on Tuesday (monday + 1)
    await admin_session.execute(
        text("""
            INSERT INTO school_holidays (id, tenant_id, date, name, holiday_type,
                is_recurring, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :holiday_date, 'Test Holiday',
                'holiday', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "holiday_date": monday + timedelta(days=1),
        },
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    # Mon-Fri = 5 weekdays, minus 1 holiday = 4 working days
    request = await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday + timedelta(days=4),
            "reason": "Holiday week",
        },
    )

    assert request.days_requested == Decimal("4")


async def test_submit_overlap_rejected(app_session, admin_session):
    """Overlapping dates for the same staff are rejected."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()

    # First request: Mon-Tue
    await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday + timedelta(days=1),
            "reason": "First request",
        },
    )

    # Second request: Tue-Wed (overlaps on Tuesday)
    with pytest.raises(LeaveRequestService.Error) as exc_info:
        await svc.submit(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_ids"][0],
            data={
                "leave_type_id": prereqs["leave_type_id"],
                "start_date": monday + timedelta(days=1),
                "end_date": monday + timedelta(days=2),
                "reason": "Overlapping request",
            },
        )
    assert "Overlapping" in exc_info.value.message


async def test_submit_insufficient_balance(app_session, admin_session):
    """Requesting more days than remaining balance is rejected."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])

    # Set balance to only 1 day via admin
    await admin_session.execute(
        text("""
            UPDATE leave_balances
            SET entitled_days = 1.0
            WHERE tenant_id = CAST(:tid AS uuid)
            AND staff_id = CAST(:staff_id AS uuid)
        """),
        {"tid": str(tenant["id"]), "staff_id": str(prereqs["staff_ids"][0])},
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()

    with pytest.raises(LeaveRequestService.Error) as exc_info:
        await svc.submit(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_ids"][0],
            data={
                "leave_type_id": prereqs["leave_type_id"],
                "start_date": monday,
                "end_date": monday + timedelta(days=4),  # 5 weekdays
                "reason": "Too many days",
            },
        )
    assert "Insufficient" in exc_info.value.message


async def test_approve_request(app_session, admin_session):
    """Approving a request sets status, increments used_days, decrements pending."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService, LeaveBalanceService

    req_svc = LeaveRequestService(app_session)
    monday = _next_monday()

    request = await req_svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday + timedelta(days=1),
            "reason": "Approve me",
        },
    )
    days = request.days_requested
    req_id = request.id

    approved = await req_svc.approve(
        tenant_id=tenant["id"],
        request_id=req_id,
        reviewer_id=prereqs["user_id"],
        notes="Approved by admin",
    )

    assert approved.status.value == "approved"
    assert approved.review_notes == "Approved by admin"
    assert approved.reviewed_by == prereqs["user_id"]

    # Check balance: used_days should be incremented, pending_days back to 0
    bal_svc = LeaveBalanceService(app_session)
    balances = await bal_svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_id"]][0]
    assert annual["used_days"] == days
    assert annual["pending_days"] == Decimal("0")


async def test_reject_request(app_session, admin_session):
    """Rejecting a request sets status and reverses pending_days."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService, LeaveBalanceService

    req_svc = LeaveRequestService(app_session)
    monday = _next_monday()

    request = await req_svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday + timedelta(days=1),
            "reason": "Reject me",
        },
    )
    req_id = request.id

    rejected = await req_svc.reject(
        tenant_id=tenant["id"],
        request_id=req_id,
        reviewer_id=prereqs["user_id"],
        notes="Denied",
    )

    assert rejected.status.value == "rejected"

    # Pending days should be back to 0
    bal_svc = LeaveBalanceService(app_session)
    balances = await bal_svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_id"]][0]
    assert annual["pending_days"] == Decimal("0")
    assert annual["used_days"] == Decimal("0")


async def test_cancel_pending_request(app_session, admin_session):
    """Cancelling a pending request reverses pending_days."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()

    request = await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday,
            "reason": "Cancel me",
        },
    )
    req_id = request.id

    cancelled = await svc.cancel(
        tenant_id=tenant["id"],
        request_id=req_id,
        staff_id=prereqs["staff_ids"][0],
    )

    assert cancelled.status.value == "cancelled"


async def test_cancel_approved_not_started(app_session, admin_session):
    """Cancelling an approved future leave reverses used_days."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService, LeaveBalanceService

    req_svc = LeaveRequestService(app_session)
    # Use a date far in the future to ensure it hasn't started
    future_monday = _next_monday(date.today() + timedelta(days=14))

    request = await req_svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": future_monday,
            "end_date": future_monday,
            "reason": "Future leave",
        },
    )
    days = request.days_requested
    req_id = request.id

    await req_svc.approve(
        tenant_id=tenant["id"],
        request_id=req_id,
        reviewer_id=prereqs["user_id"],
    )

    # Cancel it before it starts
    cancelled = await req_svc.cancel(
        tenant_id=tenant["id"],
        request_id=req_id,
        staff_id=prereqs["staff_ids"][0],
    )
    assert cancelled.status.value == "cancelled"

    # Balance should be fully restored
    bal_svc = LeaveBalanceService(app_session)
    balances = await bal_svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_id"]][0]
    assert annual["used_days"] == Decimal("0")


async def test_cancel_started_leave_blocked(app_session, admin_session):
    """Cannot cancel an approved leave that has already started (start_date <= today)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])

    # Insert a leave request that started yesterday (approved, in the past)
    req_id = uuid4()
    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)
    await admin_session.execute(
        text("""
            INSERT INTO leave_requests (id, tenant_id, staff_id, leave_type_id,
                academic_year_id, start_date, end_date, days_requested,
                reason, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                CAST(:year_id AS uuid), :start, :end, 2.0,
                'Started leave', 'approved',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(req_id), "tid": str(tenant["id"]),
            "staff_id": str(prereqs["staff_ids"][0]),
            "lt_id": str(prereqs["leave_type_id"]),
            "year_id": str(prereqs["academic_year_id"]),
            "start": yesterday, "end": tomorrow,
        },
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)

    with pytest.raises(LeaveRequestService.Error) as exc_info:
        await svc.cancel(
            tenant_id=tenant["id"],
            request_id=req_id,
            staff_id=prereqs["staff_ids"][0],
        )
    assert "already started" in exc_info.value.message


async def test_auto_approve_no_approval_required(app_session, admin_session):
    """Leave type with requires_approval=False is auto-approved on submit."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"])

    # Create a no-approval leave type
    no_approve_lt_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO leave_types (id, tenant_id, name, code,
                default_days_per_year, max_carryover_days, is_active,
                requires_approval,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Casual Leave', 'CASUAL',
                5.0, 0.0, true, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(no_approve_lt_id), "tid": str(tenant["id"])},
    )

    # Initialize balance for this type
    await admin_session.execute(
        text("""
            INSERT INTO leave_balances (id, tenant_id, staff_id, leave_type_id,
                academic_year_id, entitled_days, used_days, pending_days, carried_over,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                CAST(:year_id AS uuid), 5.0, 0.0, 0.0, 0.0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "staff_id": str(prereqs["staff_ids"][0]),
            "lt_id": str(no_approve_lt_id),
            "year_id": str(prereqs["academic_year_id"]),
        },
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()

    request = await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": no_approve_lt_id,
            "start_date": monday,
            "end_date": monday,
            "reason": "Quick casual leave",
        },
    )

    # Should be auto-approved, not pending
    assert request.status.value == "approved"
    assert request.review_notes == "Auto-approved"


async def test_leave_request_idor(app_session, admin_session):
    """Staff A cannot cancel Staff B's request."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_request_prereqs(admin_session, tenant["id"], num_staff=2)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveRequestService

    svc = LeaveRequestService(app_session)
    monday = _next_monday()

    # Staff A submits a request
    request = await svc.submit(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "leave_type_id": prereqs["leave_type_id"],
            "start_date": monday,
            "end_date": monday,
            "reason": "Staff A leave",
        },
    )
    req_id = request.id

    # Staff B tries to cancel Staff A's request
    with pytest.raises(LeaveRequestService.Error) as exc_info:
        await svc.cancel(
            tenant_id=tenant["id"],
            request_id=req_id,
            staff_id=prereqs["staff_ids"][1],  # Staff B
        )
    assert exc_info.value.code == 403

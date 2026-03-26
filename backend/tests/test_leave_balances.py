"""
Tests for leave balance management (Phase 3 — Part B).

Covers: initialize_for_year, carryover, adjust, get_staff_balances,
insufficient balance check, idempotent init, and FOR UPDATE locking.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_balance_prereqs(admin_session, tenant_id, *, num_staff=2):
    """
    Seed school, academic year, two leave types, and N staff members.
    Returns dict with IDs.
    """
    school_id = uuid4()
    acad_year_id = uuid4()
    lt_annual_id = uuid4()
    lt_sick_id = uuid4()
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

    # Leave types via raw SQL (admin bypasses RLS)
    await admin_session.execute(
        text("""
            INSERT INTO leave_types (id, tenant_id, name, code,
                default_days_per_year, max_carryover_days, is_active,
                created_at, updated_at)
            VALUES
                (CAST(:lt1 AS uuid), CAST(:tid AS uuid), 'Annual Leave', 'ANNUAL',
                 20.0, 5.0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (CAST(:lt2 AS uuid), CAST(:tid AS uuid), 'Sick Leave', 'SICK',
                 15.0, 0.0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"lt1": str(lt_annual_id), "lt2": str(lt_sick_id), "tid": str(tenant_id)},
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

    await admin_session.commit()
    return {
        "school_id": school_id,
        "academic_year_id": acad_year_id,
        "leave_type_annual_id": lt_annual_id,
        "leave_type_sick_id": lt_sick_id,
        "staff_ids": staff_ids,
    }


# --- Tests ---


async def test_initialize_balances_for_year(app_session, admin_session):
    """Bulk init creates balances for all staff x all leave types."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=3)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)
    result = await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )

    # 3 staff x 2 leave types = 6 balances
    assert result["created"] == 6
    assert "6 leave balances" in result["message"]


async def test_initialize_with_carryover(app_session, admin_session):
    """Carryover from previous year is capped by max_carryover_days."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=1)

    # Create a previous academic year
    prev_year_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2024/2025',
                '2024-09-01', '2025-07-31', 'completed', false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(prev_year_id), "tid": str(tenant["id"])},
    )

    # Create a balance for previous year: 20 entitled, 8 used = 12 remaining
    # max_carryover for ANNUAL is 5, so should carry over 5 (capped)
    staff_id = prereqs["staff_ids"][0]
    await admin_session.execute(
        text("""
            INSERT INTO leave_balances (id, tenant_id, staff_id, leave_type_id,
                academic_year_id, entitled_days, used_days, pending_days, carried_over,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                CAST(:year_id AS uuid), 20.0, 8.0, 0.0, 0.0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant["id"]),
            "staff_id": str(staff_id),
            "lt_id": str(prereqs["leave_type_annual_id"]),
            "year_id": str(prev_year_id),
        },
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)
    await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
        carry_over=True,
    )

    # Check the new year's annual balance
    balances = await svc.get_staff_balances(
        tenant["id"], staff_id, prereqs["academic_year_id"],
    )
    annual_balances = [
        b for b in balances
        if b["leave_type_id"] == prereqs["leave_type_annual_id"]
    ]
    assert len(annual_balances) == 1

    # Remaining was 12, max_carryover is 5 => carried_over = 5
    assert annual_balances[0]["carried_over"] == Decimal("5.0")
    assert annual_balances[0]["entitled_days"] == Decimal("20.0")


async def test_adjust_balance_entitled_days(app_session, admin_session):
    """Admin can adjust entitled_days on an existing balance."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)
    # Initialize first
    await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )

    # Get the annual balance
    balances = await svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_annual_id"]][0]

    # Adjust entitled days from 20 to 25
    adjusted = await svc.adjust(
        tenant["id"],
        annual["id"],
        {"entitled_days": Decimal("25.0"), "reason": "Manager override"},
    )

    assert adjusted["entitled_days"] == Decimal("25.0")
    # remaining = 25 + 0 (carried) - 0 (used) - 0 (pending) = 25
    assert adjusted["remaining_days"] == Decimal("25.0")


async def test_adjust_balance_carried_over(app_session, admin_session):
    """Admin can adjust carried_over on an existing balance."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)
    await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )

    balances = await svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_annual_id"]][0]

    adjusted = await svc.adjust(
        tenant["id"],
        annual["id"],
        {"carried_over": Decimal("3.0"), "reason": "Manual carryover"},
    )

    assert adjusted["carried_over"] == Decimal("3.0")
    # remaining = 20 + 3 - 0 - 0 = 23
    assert adjusted["remaining_days"] == Decimal("23.0")


async def test_get_staff_balances(app_session, admin_session):
    """Fetching balances for a staff member returns all leave types."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)
    await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )

    balances = await svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )

    # Should have 2 balances (annual + sick)
    assert len(balances) == 2
    type_ids = {b["leave_type_id"] for b in balances}
    assert prereqs["leave_type_annual_id"] in type_ids
    assert prereqs["leave_type_sick_id"] in type_ids


async def test_insufficient_balance_blocked(app_session, admin_session):
    """Submitting a request exceeding balance raises error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=1)

    # Create a user for the reviewer
    user_id = uuid4()
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
        {"id": str(user_id), "tid": str(tenant["id"]),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService, LeaveRequestService

    bal_svc = LeaveBalanceService(app_session)
    await bal_svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )

    # Adjust balance down to 2 days
    balances = await bal_svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_annual_id"]][0]
    await bal_svc.adjust(
        tenant["id"], annual["id"],
        {"entitled_days": Decimal("2.0"), "reason": "Reduced for test"},
    )

    # Try to submit 5-day leave request (Mon-Fri)
    from datetime import date, timedelta

    # Find the next Monday
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    next_friday = next_monday + timedelta(days=4)

    req_svc = LeaveRequestService(app_session)
    with pytest.raises(LeaveRequestService.Error) as exc_info:
        await req_svc.submit(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_ids"][0],
            data={
                "leave_type_id": prereqs["leave_type_annual_id"],
                "start_date": next_monday,
                "end_date": next_friday,
                "reason": "Vacation",
            },
        )
    assert "Insufficient" in exc_info.value.message


async def test_bulk_init_idempotent(app_session, admin_session):
    """Running init twice doesn't duplicate balances."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=2)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)

    # First run
    result1 = await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )
    assert result1["created"] == 4  # 2 staff x 2 types

    # Second run — should create 0
    result2 = await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )
    assert result2["created"] == 0


async def test_balance_for_update_lock(app_session, admin_session):
    """Verify _get_balance_for_update returns the correct balance (basic check)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_balance_prereqs(admin_session, tenant["id"], num_staff=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveBalanceService

    svc = LeaveBalanceService(app_session)
    await svc.initialize_for_year(
        tenant_id=tenant["id"],
        academic_year_id=prereqs["academic_year_id"],
    )

    # The adjust method uses with_for_update internally
    balances = await svc.get_staff_balances(
        tenant["id"], prereqs["staff_ids"][0], prereqs["academic_year_id"],
    )
    annual = [b for b in balances if b["leave_type_id"] == prereqs["leave_type_annual_id"]][0]

    # Adjust should succeed with FOR UPDATE lock
    adjusted = await svc.adjust(
        tenant["id"], annual["id"],
        {"entitled_days": Decimal("18.0"), "reason": "Lock test"},
    )
    assert adjusted["entitled_days"] == Decimal("18.0")

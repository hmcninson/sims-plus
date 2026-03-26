"""
Tests for leave management RLS isolation (Phase 3 — Part B).

Covers: cross-tenant isolation for leave_types, leave_balances,
leave_requests, and a combined full-workflow test.
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


async def _seed_full_leave_data(admin_session, tenant_id):
    """
    Seed school, academic year, leave type, staff, balance, and a leave request.
    Returns dict with all IDs.
    """
    school_id = uuid4()
    acad_year_id = uuid4()
    lt_id = uuid4()
    staff_id = uuid4()
    user_id = uuid4()
    balance_id = uuid4()
    request_id = uuid4()

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
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Kofi', 'RLS',
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher', '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(staff_id), "tid": str(tenant_id), "sid": str(school_id),
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
                'Admin', 'RLS', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO leave_balances (id, tenant_id, staff_id, leave_type_id,
                academic_year_id, entitled_days, used_days, pending_days, carried_over,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                CAST(:year_id AS uuid), 20.0, 3.0, 2.0, 1.0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(balance_id), "tid": str(tenant_id),
            "staff_id": str(staff_id), "lt_id": str(lt_id),
            "year_id": str(acad_year_id),
        },
    )

    # A leave request (future date to avoid "started" issues)
    future_monday = date.today() + timedelta(days=30)
    # Ensure it's a Monday
    while future_monday.weekday() != 0:
        future_monday += timedelta(days=1)

    await admin_session.execute(
        text("""
            INSERT INTO leave_requests (id, tenant_id, staff_id, leave_type_id,
                academic_year_id, start_date, end_date, days_requested,
                reason, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                CAST(:year_id AS uuid), :start, :end, 2.0,
                'RLS test leave', 'pending',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(request_id), "tid": str(tenant_id),
            "staff_id": str(staff_id), "lt_id": str(lt_id),
            "year_id": str(acad_year_id),
            "start": future_monday,
            "end": future_monday + timedelta(days=1),
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "academic_year_id": acad_year_id,
        "leave_type_id": lt_id,
        "staff_id": staff_id,
        "user_id": user_id,
        "balance_id": balance_id,
        "request_id": request_id,
    }


# --- Tests ---


async def test_leave_types_rls(app_session, admin_session):
    """Leave types created in Tenant A are invisible from Tenant B via raw SQL."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_full_leave_data(admin_session, tenant_a["id"])
    await _seed_full_leave_data(admin_session, tenant_b["id"])

    # Query as Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM leave_types WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["leave_type_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_leave_balances_rls(app_session, admin_session):
    """Leave balances from Tenant A are invisible from Tenant B via raw SQL."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_full_leave_data(admin_session, tenant_a["id"])
    await _seed_full_leave_data(admin_session, tenant_b["id"])

    # Query as Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM leave_balances WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["balance_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_leave_requests_rls(app_session, admin_session):
    """Leave requests from Tenant A are invisible from Tenant B via raw SQL."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_full_leave_data(admin_session, tenant_a["id"])
    await _seed_full_leave_data(admin_session, tenant_b["id"])

    # Query as Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM leave_requests WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["request_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_leave_combined_rls(app_session, admin_session):
    """Full workflow in Tenant A is completely invisible from Tenant B via service layer."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_full_leave_data(admin_session, tenant_a["id"])
    data_b = await _seed_full_leave_data(admin_session, tenant_b["id"])

    from app.services.leave import (
        LeaveTypeService,
        LeaveBalanceService,
        LeaveRequestService,
    )

    # Verify from Tenant B context: types, balances, requests are all isolated
    await set_app_tenant_context(app_session, tenant_b["id"])

    type_svc = LeaveTypeService(app_session)
    types = await type_svc.list(tenant_b["id"], active_only=False)
    type_ids = [t.id for t in types]
    assert data_a["leave_type_id"] not in type_ids
    # But Tenant B's own type IS visible
    assert data_b["leave_type_id"] in type_ids

    bal_svc = LeaveBalanceService(app_session)
    balances = await bal_svc.get_staff_balances(
        tenant_b["id"], data_b["staff_id"], data_b["academic_year_id"],
    )
    balance_ids = [b["id"] for b in balances]
    assert data_a["balance_id"] not in balance_ids

    req_svc = LeaveRequestService(app_session)
    requests = await req_svc.list_requests(tenant_b["id"])
    request_ids = [r["id"] for r in requests]
    assert data_a["request_id"] not in request_ids
    # Tenant B's own request IS visible
    assert data_b["request_id"] in request_ids

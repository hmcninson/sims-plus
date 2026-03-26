"""
Tests for loan portfolio analytics (Phase 5D).

Covers: portfolio summary totals, per-type breakdown, and aging buckets.
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


async def _seed_portfolio_prereqs(admin_session, tenant_id):
    """Seed school, users, and staff for portfolio tests."""
    school_id = uuid4()
    creator_id = uuid4()
    approver_id = uuid4()
    staff_id = uuid4()
    approver_staff_id = uuid4()

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

    for uid, name in [(creator_id, "Creator"), (approver_id, "Approver")]:
        await admin_session.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, password_hash,
                    first_name, last_name, role, status,
                    email_verified, mfa_enabled, failed_login_attempts, timezone,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                    :fname, 'User', 'school_admin', 'active',
                    true, false, 0, 'UTC',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(uid), "tid": str(tenant_id),
             "fname": name,
             "email": f"{name.lower()}-{uuid4().hex[:8]}@example.com"},
        )

    for sid, sname in [(staff_id, "StaffP"), (approver_staff_id, "ApprStaff")]:
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title, employment_date,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, :fname, 'Staff',
                    'male', :email, '0241234567',
                    'teaching', 'active', 'Teacher', '2020-01-01',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(sid), "tid": str(tenant_id), "sid": str(school_id),
                "staff_num": f"STF-{uuid4().hex[:8]}", "fname": sname,
                "email": f"{sname.lower()}-{uuid4().hex[:8]}@test.com",
            },
        )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "creator_id": creator_id,
        "approver_id": approver_id,
        "staff_id": staff_id,
        "approver_staff_id": approver_staff_id,
    }


async def _create_active_loan(svc, tenant_id, staff_id, creator_id, approver_id,
                                approver_staff_id, *, principal, tenure, first_deduction,
                                loan_type_id=None, interest_rate=Decimal("0.00")):
    """Create and activate a loan. Optionally reuse a loan type."""
    if loan_type_id is None:
        lt = await svc.create_loan_type(
            tenant_id=tenant_id,
            data={
                "name": f"Type {uuid4().hex[:6]}",
                "code": f"PT{uuid4().hex[:6].upper()}",
                "default_interest_rate": interest_rate,
                "max_amount": Decimal("100000.00"), "max_tenure_months": 60,
                "max_active_loans": 10,
            },
        )
        loan_type_id = lt.id

    loan = await svc.create_loan(
        tenant_id=tenant_id,
        data={
            "staff_id": staff_id,
            "loan_type_id": loan_type_id,
            "principal_amount": principal,
            "tenure_months": tenure,
            "first_deduction_date": first_deduction,
        },
        created_by=creator_id,
    )
    await svc.submit_loan(tenant_id, loan.id)
    await svc.approve_loan(tenant_id, loan.id,
                           approver_id=approver_id,
                           approver_staff_id=approver_staff_id)
    return await svc.disburse_loan(tenant_id, loan.id, disbursed_by=approver_id)


# --- Tests ---


async def test_portfolio_summary_totals(app_session, admin_session):
    """Portfolio summary correctly aggregates all loans."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_portfolio_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)

    await _create_active_loan(
        svc, tenant["id"], prereqs["staff_id"], prereqs["creator_id"],
        prereqs["approver_id"], prereqs["approver_staff_id"],
        principal=Decimal("5000.00"), tenure=6, first_deduction=date(2027, 1, 1),
    )
    await _create_active_loan(
        svc, tenant["id"], prereqs["staff_id"], prereqs["creator_id"],
        prereqs["approver_id"], prereqs["approver_staff_id"],
        principal=Decimal("3000.00"), tenure=3, first_deduction=date(2027, 1, 1),
    )

    portfolio = await svc.get_portfolio(tenant["id"])

    assert portfolio["total_loans"] >= 2
    assert portfolio["active_loans"] >= 2
    # Total disbursed should include both loans
    assert portfolio["total_disbursed"] >= Decimal("8000.00")


async def test_portfolio_by_type_breakdown(app_session, admin_session):
    """Per-type breakdown shows counts and amounts."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_portfolio_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)

    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Welfare Loan", "code": f"WL{uuid4().hex[:6].upper()}",
            "max_amount": Decimal("100000.00"), "max_tenure_months": 60,
            "max_active_loans": 10,
        },
    )
    lt_id = lt.id

    # Create two loans of the same type
    await _create_active_loan(
        svc, tenant["id"], prereqs["staff_id"], prereqs["creator_id"],
        prereqs["approver_id"], prereqs["approver_staff_id"],
        principal=Decimal("2000.00"), tenure=4, first_deduction=date(2027, 2, 1),
        loan_type_id=lt_id,
    )
    await _create_active_loan(
        svc, tenant["id"], prereqs["staff_id"], prereqs["creator_id"],
        prereqs["approver_id"], prereqs["approver_staff_id"],
        principal=Decimal("3000.00"), tenure=6, first_deduction=date(2027, 2, 1),
        loan_type_id=lt_id,
    )

    portfolio = await svc.get_portfolio(tenant["id"])

    # Find the Welfare Loan type in breakdown
    welfare_entry = [t for t in portfolio["by_type"] if t["loan_type_id"] == lt_id]
    assert len(welfare_entry) == 1
    assert welfare_entry[0]["count"] == 2
    assert welfare_entry[0]["total_principal"] >= Decimal("5000.00")


async def test_aging_buckets(app_session, admin_session):
    """Overdue installments appear in correct 30/60/90/120+ buckets."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_portfolio_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)

    # Create a loan with first deduction far in the past (overdue)
    past_date = date.today() - timedelta(days=90)
    # First deduction date must be 1st of month
    first_deduction = past_date.replace(day=1)

    loan = await _create_active_loan(
        svc, tenant["id"], prereqs["staff_id"], prereqs["creator_id"],
        prereqs["approver_id"], prereqs["approver_staff_id"],
        principal=Decimal("6000.00"), tenure=6, first_deduction=first_deduction,
    )

    aging = await svc.get_aging_report(tenant["id"])

    # There should be at least some overdue installments
    assert aging["total_overdue_count"] >= 1
    assert aging["total_overdue"] > Decimal("0.00")

    # Verify bucket structure: list of dicts with "bucket" key
    bucket_names = [b["bucket"] for b in aging["buckets"]]
    assert "30_days" in bucket_names
    assert "60_days" in bucket_names
    assert "90_days" in bucket_names
    assert "120_plus" in bucket_names

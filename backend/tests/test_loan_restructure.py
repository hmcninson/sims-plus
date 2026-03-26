"""
Tests for loan restructuring (Phase 5C).

Covers: old loan marked restructured, new loan created with remaining
balance, new installment schedule, old installments preserved, and
restructured_from_id linkage.

Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_and_create_active_loan(app_session, admin_session):
    """Seed and return (svc, tenant, active_loan, prereqs)."""
    tenant = await create_test_tenant(admin_session)
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
        {"id": str(school_id), "tid": str(tenant["id"]),
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
            {"id": str(uid), "tid": str(tenant["id"]),
             "fname": name,
             "email": f"{name.lower()}-{uuid4().hex[:8]}@example.com"},
        )

    for sid, sname in [(staff_id, "Borrower"), (approver_staff_id, "ApprStaff")]:
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
                "id": str(sid), "tid": str(tenant["id"]), "sid": str(school_id),
                "staff_num": f"STF-{uuid4().hex[:8]}", "fname": sname,
                "email": f"{sname.lower()}-{uuid4().hex[:8]}@test.com",
            },
        )

    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Welfare", "code": f"WF{uuid4().hex[:6].upper()}",
            "default_interest_rate": Decimal("10.00"),
            "max_amount": Decimal("100000.00"), "max_tenure_months": 60,
            "max_active_loans": 5,
        },
    )
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": staff_id,
            "loan_type_id": lt.id,
            "principal_amount": Decimal("10000.00"),
            "tenure_months": 12,
            "first_deduction_date": date(2027, 1, 1),
        },
        created_by=creator_id,
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(tenant["id"], loan.id,
                           approver_id=approver_id,
                           approver_staff_id=approver_staff_id)
    loan = await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=approver_id)

    return svc, tenant, loan, approver_id


# --- Tests ---


async def test_restructure_creates_new_loan(app_session, admin_session):
    """Restructuring marks old loan as restructured and creates a new active loan."""
    svc, tenant, old_loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session,
    )
    old_loan_id = old_loan.id

    new_loan = await svc.restructure_loan(
        tenant_id=tenant["id"],
        loan_id=old_loan_id,
        new_interest_rate=Decimal("8.00"),
        new_interest_method="flat",
        new_tenure_months=18,
        new_first_deduction_date=date(2027, 6, 1),
        reason="Staff requested extended term due to financial hardship",
        performed_by=user_id,
    )

    # Old loan is restructured
    old_refreshed = await svc.get_loan(tenant["id"], old_loan_id)
    assert old_refreshed.status.value == "restructured"

    # New loan is active
    assert new_loan.status.value == "active"
    assert new_loan.principal_amount == old_loan.outstanding_balance


async def test_restructure_new_schedule(app_session, admin_session):
    """New loan has installment count matching new tenure."""
    svc, tenant, old_loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session,
    )

    new_loan = await svc.restructure_loan(
        tenant_id=tenant["id"],
        loan_id=old_loan.id,
        new_interest_rate=Decimal("5.00"),
        new_interest_method="reducing_balance",
        new_tenure_months=24,
        new_first_deduction_date=date(2027, 7, 1),
        reason="Restructured to lower rate and longer term",
        performed_by=user_id,
    )

    installments = await svc.get_installments(tenant["id"], new_loan.id)
    assert len(installments) == 24


async def test_restructure_preserves_old_installments(app_session, admin_session):
    """Old loan's installments are not deleted after restructuring."""
    svc, tenant, old_loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session,
    )
    old_loan_id = old_loan.id

    # Get old installment count before restructuring
    old_installments_before = await svc.get_installments(tenant["id"], old_loan_id)
    assert len(old_installments_before) == 12

    await svc.restructure_loan(
        tenant_id=tenant["id"],
        loan_id=old_loan_id,
        new_interest_rate=Decimal("6.00"),
        new_interest_method="flat",
        new_tenure_months=6,
        new_first_deduction_date=date(2027, 8, 1),
        reason="Shortened term restructure",
        performed_by=user_id,
    )

    # Old installments still exist
    old_installments_after = await svc.get_installments(tenant["id"], old_loan_id)
    assert len(old_installments_after) == 12


async def test_restructure_links_loans(app_session, admin_session):
    """New loan's restructured_from_id points to the old loan."""
    svc, tenant, old_loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session,
    )
    old_loan_id = old_loan.id

    new_loan = await svc.restructure_loan(
        tenant_id=tenant["id"],
        loan_id=old_loan_id,
        new_interest_rate=Decimal("10.00"),
        new_interest_method="flat",
        new_tenure_months=12,
        new_first_deduction_date=date(2027, 9, 1),
        reason="Standard restructure for testing linkage",
        performed_by=user_id,
    )

    assert new_loan.restructured_from_id == old_loan_id

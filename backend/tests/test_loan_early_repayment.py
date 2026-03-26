"""
Tests for loan early repayment (Phase 5C).

Covers: partial repayment, full settlement, balance update,
overpayment rejection, and payment record creation.

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


async def _seed_and_create_active_loan(app_session, admin_session,
                                        principal=Decimal("6000.00"),
                                        tenure=6, interest_rate=Decimal("0.00")):
    """Seed everything and return an active loan."""
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
            "name": "Test Type", "code": f"TT{uuid4().hex[:6].upper()}",
            "default_interest_rate": interest_rate,
            "max_amount": Decimal("100000.00"), "max_tenure_months": 60,
            "max_active_loans": 5,
        },
    )
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": staff_id,
            "loan_type_id": lt.id,
            "principal_amount": principal,
            "tenure_months": tenure,
            "first_deduction_date": date(2027, 1, 1),
        },
        created_by=creator_id,
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(tenant["id"], loan.id,
                           approver_id=approver_id,
                           approver_staff_id=approver_staff_id)
    loan = await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=approver_id)

    return svc, tenant, loan, creator_id


# --- Tests ---


async def test_partial_early_repayment(app_session, admin_session):
    """Pay extra reduces balance; installments partially marked."""
    svc, tenant, loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session, principal=Decimal("6000.00"), tenure=6,
    )

    # Pay 2 installments worth
    installments = await svc.get_installments(tenant["id"], loan.id)
    two_installment_amount = installments[0].installment_amount + installments[1].installment_amount

    updated = await svc.early_repayment(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        amount=two_installment_amount,
        payment_date=date(2027, 1, 15),
        payment_method="bank_transfer",
        recorded_by=user_id,
    )

    assert updated.total_paid == two_installment_amount
    assert updated.installments_paid >= 2
    assert updated.status.value == "active"  # Not yet completed


async def test_full_settlement(app_session, admin_session):
    """Full settlement pays remaining balance and completes the loan."""
    svc, tenant, loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session, principal=Decimal("3000.00"), tenure=3,
    )

    completed = await svc.early_repayment(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        amount=loan.outstanding_balance,
        payment_date=date(2027, 1, 20),
        payment_method="cash",
        recorded_by=user_id,
        is_full_settlement=True,
    )

    assert completed.status.value == "completed"
    assert completed.outstanding_balance == Decimal("0.00")


async def test_early_repayment_balance_update(app_session, admin_session):
    """Outstanding balance is correct after partial repayment."""
    svc, tenant, loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session, principal=Decimal("4000.00"), tenure=4,
    )
    original_balance = loan.outstanding_balance
    pay_amount = Decimal("1000.00")

    updated = await svc.early_repayment(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        amount=pay_amount,
        payment_date=date(2027, 2, 1),
        payment_method="mobile_money",
        recorded_by=user_id,
    )

    assert updated.outstanding_balance == original_balance - pay_amount


async def test_overpayment_rejected(app_session, admin_session):
    """Amount exceeding outstanding balance raises an error."""
    svc, tenant, loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session, principal=Decimal("2000.00"), tenure=2,
    )

    from app.services.payroll.loan_service import LoanService

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.early_repayment(
            tenant_id=tenant["id"],
            loan_id=loan.id,
            amount=loan.outstanding_balance + Decimal("1.00"),
            payment_date=date(2027, 3, 1),
            payment_method="bank_transfer",
            recorded_by=user_id,
        )
    assert "exceeds" in exc_info.value.message.lower()


async def test_early_repayment_creates_payment_record(app_session, admin_session):
    """Early repayment creates a loan_payments record."""
    svc, tenant, loan, user_id = await _seed_and_create_active_loan(
        app_session, admin_session, principal=Decimal("5000.00"), tenure=5,
    )

    await svc.early_repayment(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        amount=Decimal("1000.00"),
        payment_date=date(2027, 4, 1),
        payment_method="bank_transfer",
        recorded_by=user_id,
        reference="TXN-12345",
    )

    payments = await svc.get_payments(tenant["id"], loan.id)
    assert len(payments) == 1
    assert payments[0].amount == Decimal("1000.00")
    assert payments[0].is_early_repayment is True
    assert payments[0].payment_method == "bank_transfer"
    assert payments[0].reference == "TXN-12345"

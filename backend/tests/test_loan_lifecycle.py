"""
Tests for loan lifecycle state machine (Phase 5B).

Covers: create draft, submit, approve, reject, re-edit, disburse,
self-approval prevention, invalid transitions, cancellation, loan number
format, installment count, and installment dates.

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


async def _seed_loan_prereqs(admin_session, tenant_id, *, extra_staff=False):
    """Seed school, users, and staff for loan tests."""
    school_id = uuid4()
    creator_id = uuid4()
    approver_id = uuid4()
    borrower_staff_id = uuid4()
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

    # Creator user (also the borrower's HR officer)
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Creator', 'User', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(creator_id), "tid": str(tenant_id),
         "email": f"creator-{uuid4().hex[:8]}@example.com"},
    )

    # Approver user (separate person)
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Approver', 'User', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(approver_id), "tid": str(tenant_id),
         "email": f"approver-{uuid4().hex[:8]}@example.com"},
    )

    # Borrower staff (employed since 2020)
    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Borrower', 'Staff',
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher', '2020-01-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(borrower_staff_id), "tid": str(tenant_id),
            "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"borrower-{uuid4().hex[:8]}@test.com",
        },
    )

    # Approver staff record
    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Approver', 'Staff',
                'female', :email, '0247654321',
                'non_teaching', 'active', 'HR Officer', '2019-06-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(approver_staff_id), "tid": str(tenant_id),
            "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"approver-staff-{uuid4().hex[:8]}@test.com",
        },
    )

    extra_staff_id = None
    if extra_staff:
        extra_staff_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title, employment_date,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, 'Extra', 'Staff',
                    'male', :email, '0249999999',
                    'teaching', 'active', 'Teacher', '2020-06-01',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(extra_staff_id), "tid": str(tenant_id),
                "sid": str(school_id),
                "staff_num": f"STF-{uuid4().hex[:8]}",
                "email": f"extra-{uuid4().hex[:8]}@test.com",
            },
        )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "creator_id": creator_id,
        "approver_id": approver_id,
        "borrower_staff_id": borrower_staff_id,
        "approver_staff_id": approver_staff_id,
        "extra_staff_id": extra_staff_id,
    }


async def _create_loan_type(svc, tenant_id, **overrides):
    """Create a loan type with sensible defaults."""
    data = {
        "name": f"Test Loan {uuid4().hex[:6]}",
        "code": f"TL{uuid4().hex[:6].upper()}",
        "default_interest_rate": Decimal("10.00"),
        "default_interest_method": "flat",
        "max_amount": Decimal("50000.00"),
        "max_tenure_months": 24,
        "max_active_loans": 2,
    }
    data.update(overrides)
    return await svc.create_loan_type(tenant_id=tenant_id, data=data)


async def _create_draft_loan(svc, tenant_id, borrower_staff_id, loan_type_id, creator_id, **overrides):
    """Create a draft loan with sensible defaults."""
    data = {
        "staff_id": borrower_staff_id,
        "loan_type_id": loan_type_id,
        "principal_amount": Decimal("5000.00"),
        "tenure_months": 12,
        "first_deduction_date": date(2027, 2, 1),
    }
    data.update(overrides)
    return await svc.create_loan(tenant_id=tenant_id, data=data, created_by=creator_id)


# --- Tests ---


async def test_create_loan_draft(app_session, admin_session):
    """Creating a loan produces draft status with a generated loan number."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )

    assert loan.status.value == "draft"
    assert loan.loan_number is not None
    assert loan.principal_amount == Decimal("5000.00")
    assert loan.outstanding_balance == loan.total_repayable
    assert loan.total_paid == Decimal("0.00")
    assert loan.installments_remaining == 12


async def test_submit_loan(app_session, admin_session):
    """Submitting a draft loan moves it to pending_approval."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )

    submitted = await svc.submit_loan(tenant["id"], loan.id)
    assert submitted.status.value == "pending_approval"


async def test_approve_loan(app_session, admin_session):
    """Approving a pending loan sets approved status and approver info."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)

    approved = await svc.approve_loan(
        tenant["id"], loan.id,
        approver_id=prereqs["approver_id"],
        approver_staff_id=prereqs["approver_staff_id"],
    )
    assert approved.status.value == "approved"
    assert approved.approval_date is not None


async def test_reject_loan(app_session, admin_session):
    """Rejecting a pending loan sets rejected status with reason."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)

    rejected = await svc.reject_loan(
        tenant["id"], loan.id,
        rejector_id=prereqs["approver_id"],
        reason="Insufficient documentation",
    )
    assert rejected.status.value == "rejected"
    assert "Insufficient documentation" in (rejected.notes or "")


async def test_reject_then_reedit(app_session, admin_session):
    """A rejected loan can be re-edited back to draft via the re-edit transition."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.reject_loan(tenant["id"], loan.id, rejector_id=prereqs["approver_id"])

    # The rejected -> draft transition (re-edit)
    # The service handles this via _validate_transition which allows REJECTED -> DRAFT
    from app.models.payroll import LoanStatus
    loan_obj = await svc.get_loan(tenant["id"], loan.id, load_relations=False)
    svc._validate_transition(loan_obj.status, LoanStatus.DRAFT)
    loan_obj.status = LoanStatus.DRAFT
    await app_session.flush()

    refreshed = await svc.get_loan(tenant["id"], loan.id)
    assert refreshed.status.value == "draft"


async def test_disburse_loan(app_session, admin_session):
    """Disbursing an approved loan sets active status and generates installments."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(
        tenant["id"], loan.id,
        approver_id=prereqs["approver_id"],
        approver_staff_id=prereqs["approver_staff_id"],
    )

    disbursed = await svc.disburse_loan(
        tenant["id"], loan.id,
        disbursed_by=prereqs["approver_id"],
    )
    assert disbursed.status.value == "active"
    assert disbursed.disbursement_date is not None

    # Verify installments were generated
    installments = await svc.get_installments(tenant["id"], loan.id)
    assert len(installments) == 12


async def test_self_approval_blocked_by_staff_id(app_session, admin_session):
    """Borrower cannot approve their own loan."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.approve_loan(
            tenant["id"], loan.id,
            approver_id=prereqs["approver_id"],
            approver_staff_id=prereqs["borrower_staff_id"],  # Same as borrower
        )
    assert "cannot approve" in exc_info.value.message.lower()


async def test_self_approval_blocked_by_created_by(app_session, admin_session):
    """Creator of the loan cannot also approve it."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.approve_loan(
            tenant["id"], loan.id,
            approver_id=prereqs["creator_id"],  # Same as creator
            approver_staff_id=prereqs["approver_staff_id"],
        )
    assert "submitted" in exc_info.value.message.lower() or "cannot" in exc_info.value.message.lower()


async def test_invalid_state_transition(app_session, admin_session):
    """Draft cannot jump directly to approved."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )

    # Try to approve a draft loan directly (skip submit)
    with pytest.raises(LoanService.Error) as exc_info:
        await svc.approve_loan(
            tenant["id"], loan.id,
            approver_id=prereqs["approver_id"],
            approver_staff_id=prereqs["approver_staff_id"],
        )
    assert "Cannot transition" in exc_info.value.message


async def test_cancel_draft_loan(app_session, admin_session):
    """Deleting a draft loan soft-deletes it."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    loan_id = loan.id

    await svc.delete_loan(tenant["id"], loan_id)

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.get_loan(tenant["id"], loan_id)
    assert exc_info.value.code == 404


async def test_cannot_cancel_active_loan(app_session, admin_session):
    """An active loan cannot be deleted."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(
        tenant["id"], loan.id,
        approver_id=prereqs["approver_id"],
        approver_staff_id=prereqs["approver_staff_id"],
    )
    await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=prereqs["approver_id"])

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.delete_loan(tenant["id"], loan.id)
    assert "Only draft" in exc_info.value.message


async def test_loan_number_format(app_session, admin_session):
    """Loan number matches LN-{YYYY}-{seq:04d} format."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService
    import re

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
    )

    pattern = r"^LN-\d{4}-\d{4}$"
    assert re.match(pattern, loan.loan_number), f"Loan number '{loan.loan_number}' doesn't match pattern"


async def test_installment_count_matches_tenure(app_session, admin_session):
    """Disbursed loan generates exactly N installments for N-month tenure."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
        tenure_months=6,
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(
        tenant["id"], loan.id,
        approver_id=prereqs["approver_id"],
        approver_staff_id=prereqs["approver_staff_id"],
    )
    await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=prereqs["approver_id"])

    installments = await svc.get_installments(tenant["id"], loan.id)
    assert len(installments) == 6


async def test_installment_dates_first_of_month(app_session, admin_session):
    """All installment due dates are the 1st of their respective month."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_loan_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await _create_loan_type(svc, tenant["id"])
    loan = await _create_draft_loan(
        svc, tenant["id"], prereqs["borrower_staff_id"], lt.id, prereqs["creator_id"],
        first_deduction_date=date(2027, 1, 1),
        tenure_months=6,
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(
        tenant["id"], loan.id,
        approver_id=prereqs["approver_id"],
        approver_staff_id=prereqs["approver_staff_id"],
    )
    await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=prereqs["approver_id"])

    installments = await svc.get_installments(tenant["id"], loan.id)
    for inst in installments:
        assert inst.due_date.day == 1, f"Installment #{inst.installment_number} due_date {inst.due_date} is not 1st of month"

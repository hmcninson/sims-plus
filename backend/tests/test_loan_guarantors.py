"""
Tests for loan guarantor management (Phase 5B).

Covers: add guarantor, record consent, self-guarantor blocked,
remove from draft vs active.

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


async def _seed_guarantor_prereqs(admin_session, tenant_id):
    """Seed school, users, borrower staff, and guarantor staff."""
    school_id = uuid4()
    creator_id = uuid4()
    approver_id = uuid4()
    borrower_staff_id = uuid4()
    guarantor_staff_id = uuid4()
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

    for sid, sname in [
        (borrower_staff_id, "Borrower"),
        (guarantor_staff_id, "Guarantor"),
        (approver_staff_id, "ApprStaff"),
    ]:
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
        "borrower_staff_id": borrower_staff_id,
        "guarantor_staff_id": guarantor_staff_id,
        "approver_staff_id": approver_staff_id,
    }


# --- Tests ---


async def test_add_guarantor(app_session, admin_session):
    """Adding a staff member as guarantor to a draft loan works."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_guarantor_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={"name": "Guarantor Test", "code": f"GT{uuid4().hex[:6].upper()}",
              "max_active_loans": 5, "max_amount": Decimal("100000.00"),
              "max_tenure_months": 60},
    )
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": prereqs["borrower_staff_id"],
            "loan_type_id": lt.id,
            "principal_amount": Decimal("5000.00"),
            "tenure_months": 12,
            "first_deduction_date": date(2027, 3, 1),
        },
        created_by=prereqs["creator_id"],
    )

    guarantor = await svc.add_guarantor(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        data={"guarantor_staff_id": prereqs["guarantor_staff_id"], "relationship": "HOD"},
    )

    assert guarantor.guarantor_staff_id == prereqs["guarantor_staff_id"]
    assert guarantor.consent_given is False


async def test_record_consent(app_session, admin_session):
    """Recording consent sets consent_given and consent_date."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_guarantor_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={"name": "Consent Test", "code": f"CT{uuid4().hex[:6].upper()}",
              "max_active_loans": 5, "max_amount": Decimal("100000.00"),
              "max_tenure_months": 60},
    )
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": prereqs["borrower_staff_id"],
            "loan_type_id": lt.id,
            "principal_amount": Decimal("3000.00"),
            "tenure_months": 6,
            "first_deduction_date": date(2027, 4, 1),
        },
        created_by=prereqs["creator_id"],
    )
    guarantor = await svc.add_guarantor(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        data={"guarantor_staff_id": prereqs["guarantor_staff_id"]},
    )

    updated = await svc.update_guarantor_consent(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        guarantor_id=guarantor.id,
        consent_given=True,
    )

    assert updated.consent_given is True
    assert updated.consent_date is not None


async def test_self_guarantor_blocked(app_session, admin_session):
    """Staff cannot guarantee their own loan."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_guarantor_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={"name": "Self Guar Test", "code": f"SG{uuid4().hex[:6].upper()}",
              "max_active_loans": 5, "max_amount": Decimal("100000.00"),
              "max_tenure_months": 60},
    )
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": prereqs["borrower_staff_id"],
            "loan_type_id": lt.id,
            "principal_amount": Decimal("2000.00"),
            "tenure_months": 4,
            "first_deduction_date": date(2027, 5, 1),
        },
        created_by=prereqs["creator_id"],
    )

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.add_guarantor(
            tenant_id=tenant["id"],
            loan_id=loan.id,
            data={"guarantor_staff_id": prereqs["borrower_staff_id"]},  # Same as borrower
        )
    assert "cannot guarantee" in exc_info.value.message.lower()


async def test_remove_guarantor_from_draft(app_session, admin_session):
    """Can remove from draft, but not from active loan."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_guarantor_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={"name": "Remove Test", "code": f"RT{uuid4().hex[:6].upper()}",
              "max_active_loans": 5, "max_amount": Decimal("100000.00"),
              "max_tenure_months": 60},
    )

    # Draft loan — remove should work
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": prereqs["borrower_staff_id"],
            "loan_type_id": lt.id,
            "principal_amount": Decimal("4000.00"),
            "tenure_months": 8,
            "first_deduction_date": date(2027, 6, 1),
        },
        created_by=prereqs["creator_id"],
    )
    guarantor = await svc.add_guarantor(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        data={"guarantor_staff_id": prereqs["guarantor_staff_id"]},
    )

    # Remove from draft — OK
    await svc.remove_guarantor(tenant["id"], loan.id, guarantor.id)

    # Now make the loan active
    guarantor2 = await svc.add_guarantor(
        tenant_id=tenant["id"],
        loan_id=loan.id,
        data={"guarantor_staff_id": prereqs["guarantor_staff_id"]},
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(tenant["id"], loan.id,
                           approver_id=prereqs["approver_id"],
                           approver_staff_id=prereqs["approver_staff_id"])
    await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=prereqs["approver_id"])

    # Remove from active — should fail
    with pytest.raises(LoanService.Error) as exc_info:
        await svc.remove_guarantor(tenant["id"], loan.id, guarantor2.id)
    assert "draft" in exc_info.value.message.lower()

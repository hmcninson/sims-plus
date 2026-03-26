"""
Tests for loan eligibility checks (Phase 5B).

Covers: eligible staff, min service months, max active loans,
max amount, max tenure.

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


async def _seed_eligibility_prereqs(admin_session, tenant_id, *,
                                     employment_date="2020-01-01"):
    """Seed school, users, and staff for eligibility tests."""
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

    for sid, sname, emp in [
        (staff_id, "Staff", employment_date),
        (approver_staff_id, "ApprStaff", "2019-01-01"),
    ]:
        # Use f-string for date literal because asyncpg rejects string->date param conversion
        await admin_session.execute(
            text(f"""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title, employment_date,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, :fname, 'Test',
                    'male', :email, '0241234567',
                    'teaching', 'active', 'Teacher', '{emp}',
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


# --- Tests ---


async def test_eligible_staff(app_session, admin_session):
    """Staff meeting all criteria returns eligible=True."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_eligibility_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Elig Test", "code": f"EL{uuid4().hex[:6].upper()}",
            "min_service_months": 6,
            "max_active_loans": 2,
            "max_amount": Decimal("10000.00"),
            "max_tenure_months": 24,
        },
    )

    result = await svc.check_eligibility(
        tenant["id"], prereqs["staff_id"], lt.id,
    )

    assert result["eligible"] is True
    assert result["reasons"] == []
    assert result["max_eligible_amount"] == Decimal("10000.00")
    assert result["max_eligible_tenure"] == 24


async def test_min_service_months_failed(app_session, admin_session):
    """Staff employed less than min_service_months is ineligible."""
    tenant = await create_test_tenant(admin_session)
    # Employed only recently
    prereqs = await _seed_eligibility_prereqs(
        admin_session, tenant["id"],
        employment_date=date.today().replace(day=1).isoformat(),  # This month
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Service Check", "code": f"SC{uuid4().hex[:6].upper()}",
            "min_service_months": 12,  # Requires 12 months
            "max_active_loans": 2,
        },
    )

    result = await svc.check_eligibility(
        tenant["id"], prereqs["staff_id"], lt.id,
    )

    assert result["eligible"] is False
    assert any("service" in r.lower() for r in result["reasons"])


async def test_max_active_loans_exceeded(app_session, admin_session):
    """Staff with max active loans of this type is ineligible."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_eligibility_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Max Loans", "code": f"ML{uuid4().hex[:6].upper()}",
            "max_active_loans": 1,  # Only 1 allowed
            "max_amount": Decimal("100000.00"),
            "max_tenure_months": 60,
        },
    )

    # Create and activate one loan
    loan = await svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": prereqs["staff_id"],
            "loan_type_id": lt.id,
            "principal_amount": Decimal("1000.00"),
            "tenure_months": 3,
            "first_deduction_date": date(2027, 1, 1),
        },
        created_by=prereqs["creator_id"],
    )
    await svc.submit_loan(tenant["id"], loan.id)
    await svc.approve_loan(tenant["id"], loan.id,
                           approver_id=prereqs["approver_id"],
                           approver_staff_id=prereqs["approver_staff_id"])
    await svc.disburse_loan(tenant["id"], loan.id, disbursed_by=prereqs["approver_id"])

    # Check eligibility — should fail
    result = await svc.check_eligibility(
        tenant["id"], prereqs["staff_id"], lt.id,
    )

    assert result["eligible"] is False
    assert any("maximum" in r.lower() for r in result["reasons"])


async def test_max_amount_exceeded(app_session, admin_session):
    """Loan type max_amount is returned for client-side validation."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_eligibility_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Max Amt", "code": f"MA{uuid4().hex[:6].upper()}",
            "max_amount": Decimal("5000.00"),
            "max_tenure_months": 12,
        },
    )

    # Eligibility check returns max_eligible_amount for client-side validation
    result = await svc.check_eligibility(
        tenant["id"], prereqs["staff_id"], lt.id,
    )

    assert result["max_eligible_amount"] == Decimal("5000.00")

    # Also verify the service rejects over-limit at creation time
    with pytest.raises(LoanService.Error) as exc_info:
        await svc.create_loan(
            tenant_id=tenant["id"],
            data={
                "staff_id": prereqs["staff_id"],
                "loan_type_id": lt.id,
                "principal_amount": Decimal("6000.00"),  # Over max
                "tenure_months": 6,
                "first_deduction_date": date(2027, 1, 1),
            },
            created_by=prereqs["creator_id"],
        )
    assert "exceeds" in exc_info.value.message.lower()


async def test_max_tenure_exceeded(app_session, admin_session):
    """Loan type max_tenure_months is returned and enforced at creation."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_eligibility_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll.loan_service import LoanService

    svc = LoanService(app_session)
    lt = await svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Max Tenure", "code": f"MT{uuid4().hex[:6].upper()}",
            "max_tenure_months": 6,
            "max_amount": Decimal("100000.00"),
        },
    )

    result = await svc.check_eligibility(
        tenant["id"], prereqs["staff_id"], lt.id,
    )
    assert result["max_eligible_tenure"] == 6

    with pytest.raises(LoanService.Error) as exc_info:
        await svc.create_loan(
            tenant_id=tenant["id"],
            data={
                "staff_id": prereqs["staff_id"],
                "loan_type_id": lt.id,
                "principal_amount": Decimal("3000.00"),
                "tenure_months": 12,  # Over max of 6
                "first_deduction_date": date(2027, 1, 1),
            },
            created_by=prereqs["creator_id"],
        )
    assert "exceeds" in exc_info.value.message.lower()

"""
Tests for loan statement PDF generation (Phase 5D).

Covers: PDF generation (mocked WeasyPrint/S3) and schedule totals.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_and_create_active_loan(app_session, admin_session):
    """Seed and return (loan_svc, stmt_svc, tenant, active_loan)."""
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
    from app.services.payroll.loan_statement_service import LoanStatementService

    loan_svc = LoanService(app_session)
    stmt_svc = LoanStatementService(app_session)

    lt = await loan_svc.create_loan_type(
        tenant_id=tenant["id"],
        data={
            "name": "Statement Type", "code": f"ST{uuid4().hex[:6].upper()}",
            "default_interest_rate": Decimal("10.00"),
            "max_amount": Decimal("100000.00"), "max_tenure_months": 60,
            "max_active_loans": 5,
        },
    )
    loan = await loan_svc.create_loan(
        tenant_id=tenant["id"],
        data={
            "staff_id": staff_id,
            "loan_type_id": lt.id,
            "principal_amount": Decimal("5000.00"),
            "tenure_months": 6,
            "first_deduction_date": date(2027, 1, 1),
        },
        created_by=creator_id,
    )
    await loan_svc.submit_loan(tenant["id"], loan.id)
    await loan_svc.approve_loan(tenant["id"], loan.id,
                                approver_id=approver_id,
                                approver_staff_id=approver_staff_id)
    loan = await loan_svc.disburse_loan(tenant["id"], loan.id, disbursed_by=approver_id)

    return loan_svc, stmt_svc, tenant, loan


# --- Tests ---


async def test_generate_loan_statement_pdf(app_session, admin_session):
    """Loan statement generation produces a URL (with mocked WeasyPrint + S3)."""
    loan_svc, stmt_svc, tenant, loan = await _seed_and_create_active_loan(
        app_session, admin_session,
    )

    mock_s3 = MagicMock()
    mock_s3.upload_fileobj = AsyncMock()
    mock_s3.generate_presigned_url = AsyncMock(return_value="https://s3.example.com/statement.pdf")

    with patch("app.services.payroll.loan_statement_service.HTML") as mock_html, \
         patch("app.services.payroll.loan_statement_service.get_s3_service", return_value=mock_s3):
        mock_html.return_value.write_pdf = MagicMock()

        result = await stmt_svc.generate_statement(
            tenant_id=tenant["id"],
            loan_id=loan.id,
        )

    assert "url" in result
    assert result["url"] == "https://s3.example.com/statement.pdf"
    assert result["loan_number"] == loan.loan_number


async def test_statement_correct_totals(app_session, admin_session):
    """Installment schedule totals match the loan summary."""
    loan_svc, _, tenant, loan = await _seed_and_create_active_loan(
        app_session, admin_session,
    )

    installments = await loan_svc.get_installments(tenant["id"], loan.id)

    total_amount = sum(i.installment_amount for i in installments)
    total_principal = sum(i.principal_component for i in installments)
    total_interest = sum(i.interest_component for i in installments)

    assert total_amount == loan.total_repayable
    assert total_principal == loan.principal_amount
    assert total_interest == loan.total_interest

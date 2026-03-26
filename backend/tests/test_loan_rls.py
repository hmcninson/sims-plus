"""
Tests for loan RLS isolation (Phase 5D).

Covers: cross-tenant isolation for loan_types, staff_loans,
loan_installments, loan_guarantors, and loan_payments.

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


async def _seed_loan_data(admin_session, tenant_id):
    """Seed a complete set of loan data for one tenant. Returns all IDs."""
    school_id = uuid4()
    user_id = uuid4()
    staff_id = uuid4()
    loan_type_id = uuid4()
    loan_id = uuid4()
    installment_id = uuid4()
    guarantor_id = uuid4()
    payment_id = uuid4()
    guarantor_staff_id = uuid4()

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
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )

    for sid, sname in [(staff_id, "Borrower"), (guarantor_staff_id, "Guarantor")]:
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title, employment_date,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, :fname, 'RLS',
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

    # Loan type
    await admin_session.execute(
        text("""
            INSERT INTO loan_types (id, tenant_id, name, code,
                default_interest_rate, default_interest_method,
                max_active_loans, min_service_months, max_deduction_pct,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                'RLS Test Type', :code,
                10.00, 'flat',
                1, 0, 50.00,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(loan_type_id), "tid": str(tenant_id),
         "code": f"RLS-{uuid4().hex[:4].upper()}"},
    )

    # Staff loan
    await admin_session.execute(
        text("""
            INSERT INTO staff_loans (id, tenant_id, loan_number, staff_id,
                loan_type_id, status, principal_amount, interest_rate,
                interest_method, total_interest, total_repayable,
                tenure_months, monthly_installment, total_paid,
                outstanding_balance, installments_paid, installments_remaining,
                first_deduction_date, created_by,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :ln,
                CAST(:staff_id AS uuid), CAST(:lt_id AS uuid),
                'active', 5000.00, 10.00, 'flat', 500.00, 5500.00,
                12, 458.33, 0.00, 5500.00, 0, 12,
                '2027-01-01', CAST(:user_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(loan_id), "tid": str(tenant_id),
            "ln": f"LN-2027-{uuid4().hex[:4]}",
            "staff_id": str(staff_id), "lt_id": str(loan_type_id),
            "user_id": str(user_id),
        },
    )

    # Loan installment
    await admin_session.execute(
        text("""
            INSERT INTO loan_installments (id, tenant_id, loan_id,
                installment_number, due_date,
                principal_component, interest_component, installment_amount,
                opening_balance, closing_balance, is_paid,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:lid AS uuid),
                1, '2027-01-01',
                416.67, 41.67, 458.33,
                5500.00, 5041.67, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(installment_id), "tid": str(tenant_id), "lid": str(loan_id)},
    )

    # Loan guarantor
    await admin_session.execute(
        text("""
            INSERT INTO loan_guarantors (id, tenant_id, loan_id,
                guarantor_staff_id, consent_given,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:lid AS uuid),
                CAST(:gid AS uuid), false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(guarantor_id), "tid": str(tenant_id),
            "lid": str(loan_id), "gid": str(guarantor_staff_id),
        },
    )

    # Loan payment
    await admin_session.execute(
        text("""
            INSERT INTO loan_payments (id, tenant_id, loan_id,
                payment_number, amount, payment_date, payment_method,
                is_early_repayment, recorded_by,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:lid AS uuid),
                :pn, 458.33, '2027-01-01', 'payroll',
                false, CAST(:user_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(payment_id), "tid": str(tenant_id),
            "lid": str(loan_id),
            "pn": f"LP-2027-{uuid4().hex[:4]}",
            "user_id": str(user_id),
        },
    )

    await admin_session.commit()
    return {
        "loan_type_id": loan_type_id,
        "loan_id": loan_id,
        "installment_id": installment_id,
        "guarantor_id": guarantor_id,
        "payment_id": payment_id,
    }


# --- Tests ---


async def test_loan_types_rls(app_session, admin_session):
    """Loan types from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_loan_data(admin_session, tenant_a["id"])
    await _seed_loan_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM loan_types WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["loan_type_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_staff_loans_rls(app_session, admin_session):
    """Staff loans from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_loan_data(admin_session, tenant_a["id"])
    await _seed_loan_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM staff_loans WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["loan_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_loan_installments_rls(app_session, admin_session):
    """Loan installments from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_loan_data(admin_session, tenant_a["id"])
    await _seed_loan_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM loan_installments WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["installment_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_loan_guarantors_rls(app_session, admin_session):
    """Loan guarantors from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_loan_data(admin_session, tenant_a["id"])
    await _seed_loan_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM loan_guarantors WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["guarantor_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_loan_payments_rls(app_session, admin_session):
    """Loan payments from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_loan_data(admin_session, tenant_a["id"])
    await _seed_loan_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM loan_payments WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["payment_id"])},
    )
    assert result.scalar_one_or_none() is None

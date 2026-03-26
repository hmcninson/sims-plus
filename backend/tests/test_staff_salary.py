"""
Tests for staff salary configuration service (Phase 4A).

Covers: create salary config, config deactivates previous, bank details,
bulk assign salary grade, salary history, and account masking.

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


async def _seed_salary_prereqs(admin_session, tenant_id, *, num_staff=1):
    """Seed school, user, and staff for salary tests. Returns dict with IDs."""
    school_id = uuid4()
    user_id = uuid4()

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

    staff_ids = []
    for i in range(num_staff):
        staff_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id,
                    staff_id, first_name, last_name,
                    gender, email, phone,
                    staff_type, status, job_title, employment_date,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_num, 'Staff', :last,
                    'male', :email, '0241234567',
                    'teaching', 'active', 'Teacher', '2020-09-01',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(staff_id), "tid": str(tenant_id), "sid": str(school_id),
                "staff_num": f"STF-{uuid4().hex[:8]}",
                "last": f"Member{i}",
                "email": f"staff-{uuid4().hex[:8]}@test.com",
            },
        )
        staff_ids.append(staff_id)

    await admin_session.commit()
    return {"school_id": school_id, "user_id": user_id, "staff_ids": staff_ids}


# --- Tests ---


async def test_create_salary_config(app_session, admin_session):
    """Creating a salary config with allowances and deductions stores correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_salary_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService, SalaryService

    cfg_svc = PayrollConfigService(app_session)

    # Create allowance and deduction types first
    at = await cfg_svc.create_allowance_type(
        tenant_id=tenant["id"],
        data={
            "name": "Responsibility",
            "code": "RESP",
            "calculation_method": "fixed",
            "default_amount": Decimal("500.00"),
        },
    )
    dt = await cfg_svc.create_deduction_type(
        tenant_id=tenant["id"],
        data={
            "name": "Welfare",
            "code": "WELF",
            "calculation_method": "fixed",
            "default_amount": Decimal("50.00"),
            "deduction_category": "voluntary",
        },
    )

    sal_svc = SalaryService(app_session)
    config = await sal_svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "basic_salary": Decimal("4000.00"),
            "effective_date": date(2026, 1, 1),
            "allowances": [{"allowance_type_id": at.id, "amount": Decimal("500.00")}],
            "deductions": [{"deduction_type_id": dt.id, "amount": Decimal("50.00")}],
        },
    )

    assert config.basic_salary == Decimal("4000.00")
    assert config.is_active is True
    assert len(config.allowances) == 1
    assert len(config.deductions) == 1


async def test_salary_config_deactivates_previous(app_session, admin_session):
    """Creating a new salary config deactivates the previous one."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_salary_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import SalaryService

    svc = SalaryService(app_session)
    staff_id = prereqs["staff_ids"][0]

    config1 = await svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=staff_id,
        data={
            "basic_salary": Decimal("3000.00"),
            "effective_date": date(2026, 1, 1),
        },
    )
    config1_id = config1.id

    config2 = await svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=staff_id,
        data={
            "basic_salary": Decimal("3500.00"),
            "effective_date": date(2026, 4, 1),
        },
    )

    assert config2.is_active is True

    # The active config should be config2
    current = await svc.get_staff_salary(tenant["id"], staff_id)
    assert current.id == config2.id
    assert current.id != config1_id


async def test_salary_config_with_bank_details(app_session, admin_session):
    """Salary config stores bank details for payment processing."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_salary_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import SalaryService

    svc = SalaryService(app_session)
    config = await svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_ids"][0],
        data={
            "basic_salary": Decimal("5000.00"),
            "effective_date": date(2026, 1, 1),
            "payment_method": "bank_transfer",
            "bank_name": "GCB Bank",
            "bank_branch": "Accra Main",
            "account_number": "1234567890",
            "tin_number": "GHA-TIN-001",
            "ssnit_number": "SSNIT-001",
        },
    )

    assert config.payment_method.value == "bank_transfer"
    assert config.bank_name == "GCB Bank"
    assert config.account_number == "1234567890"
    assert config.tin_number == "GHA-TIN-001"
    assert config.ssnit_number == "SSNIT-001"


async def test_bulk_assign_salary_grade(app_session, admin_session):
    """Bulk assigning a salary grade creates configs for multiple staff."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_salary_prereqs(admin_session, tenant["id"], num_staff=3)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService, SalaryService

    cfg_svc = PayrollConfigService(app_session)
    grade = await cfg_svc.create_salary_grade(
        tenant_id=tenant["id"],
        data={"name": "Grade B", "code": "GR-B", "basic_salary": Decimal("3500.00")},
    )

    sal_svc = SalaryService(app_session)
    result = await sal_svc.bulk_assign_salary_grade(
        tenant_id=tenant["id"],
        staff_ids=prereqs["staff_ids"],
        salary_grade_id=grade.id,
        effective_date=date(2026, 1, 1),
    )

    assert result["assigned_count"] == 3
    assert result["skipped_count"] == 0

    # Verify each staff has the correct salary
    for sid in prereqs["staff_ids"]:
        config = await sal_svc.get_staff_salary(tenant["id"], sid)
        assert config is not None
        assert config.basic_salary == Decimal("3500.00")
        assert config.salary_grade_id == grade.id


async def test_get_salary_history(app_session, admin_session):
    """Salary history returns all configs ordered by effective_date descending."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_salary_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import SalaryService

    svc = SalaryService(app_session)
    staff_id = prereqs["staff_ids"][0]

    await svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=staff_id,
        data={"basic_salary": Decimal("3000.00"), "effective_date": date(2025, 1, 1)},
    )
    await svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=staff_id,
        data={"basic_salary": Decimal("3500.00"), "effective_date": date(2025, 7, 1)},
    )
    await svc.create_or_update_salary(
        tenant_id=tenant["id"],
        staff_id=staff_id,
        data={"basic_salary": Decimal("4000.00"), "effective_date": date(2026, 1, 1)},
    )

    history = await svc.get_salary_history(tenant["id"], staff_id)

    assert len(history) == 3
    # Most recent first
    assert history[0].basic_salary == Decimal("4000.00")
    assert history[1].basic_salary == Decimal("3500.00")
    assert history[2].basic_salary == Decimal("3000.00")


async def test_account_number_masked_in_response(app_session, admin_session):
    """Account numbers in payslip context use _mask_account_number correctly."""
    # This tests the pure masking function, not a full payslip render
    from app.services.payroll.payslip_service import _mask_account_number

    assert _mask_account_number("1234567890") == "****7890"
    assert _mask_account_number("5678") == "****"
    assert _mask_account_number(None) == "N/A"
    assert _mask_account_number("") == "N/A"

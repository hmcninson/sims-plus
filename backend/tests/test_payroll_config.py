"""
Tests for payroll configuration service (Phase 4A).

Covers: salary grade CRUD, allowance type creation with all calculation
methods, deduction type (statutory), tax bracket seeding, duplicate code
rejection, soft delete, and contiguity validation.

Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_payroll_prereqs(admin_session, tenant_id):
    """Seed school for payroll config tests. Returns dict with IDs."""
    school_id = uuid4()

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
    await admin_session.commit()
    return {"school_id": school_id}


# --- Tests ---


async def test_create_salary_grade(app_session, admin_session):
    """Creating a salary grade stores name, code, and basic_salary correctly."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    grade = await svc.create_salary_grade(
        tenant_id=tenant["id"],
        data={
            "name": "Senior Teacher Scale",
            "code": "STS",
            "basic_salary": Decimal("4500.00"),
            "min_salary": Decimal("4000.00"),
            "max_salary": Decimal("6000.00"),
            "description": "Senior teacher pay scale",
        },
    )

    assert grade.id is not None
    assert grade.name == "Senior Teacher Scale"
    assert grade.code == "STS"
    assert grade.basic_salary == Decimal("4500.00")
    assert grade.is_active is True
    assert grade.deleted_at is None


async def test_create_allowance_type_with_calculation_methods(app_session, admin_session):
    """Creating allowance types with all 3 calculation methods succeeds."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)

    methods = [
        ("fixed", "RESP", Decimal("500.00")),
        ("percentage_basic", "HOUS", Decimal("15.00")),
        ("percentage_gross", "TRNS", Decimal("5.00")),
    ]

    for method, code, amount in methods:
        at = await svc.create_allowance_type(
            tenant_id=tenant["id"],
            data={
                "name": f"Allowance {code}",
                "code": code,
                "calculation_method": method,
                "default_amount": amount,
                "is_taxable": True,
            },
        )
        assert at.calculation_method.value == method
        assert at.default_amount == amount


async def test_create_deduction_type_statutory(app_session, admin_session):
    """Creating a statutory deduction type stores is_statutory and category correctly."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    dt = await svc.create_deduction_type(
        tenant_id=tenant["id"],
        data={
            "name": "SSNIT Employee",
            "code": "SSNIT_EE",
            "calculation_method": "percentage_basic",
            "default_amount": Decimal("5.50"),
            "is_statutory": True,
            "is_employer_portion": False,
            "deduction_category": "statutory",
        },
    )

    assert dt.id is not None
    assert dt.is_statutory is True
    assert dt.deduction_category.value == "statutory"
    assert dt.default_amount == Decimal("5.50")


async def test_seed_tax_brackets(app_session, admin_session):
    """Seeding GRA 2024 brackets creates 7 brackets for the tenant."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    count = await svc.seed_tax_brackets(tenant_id=tenant["id"], effective_year=2024)

    assert count == 7

    brackets = await svc.list_tax_brackets(tenant["id"], effective_year=2024)
    assert len(brackets) == 7
    # Band 1 is the tax-free band
    band1 = [b for b in brackets if b.band_number == 1][0]
    assert band1.rate == Decimal("0.0000")
    assert band1.upper_limit == Decimal("490.00")

    # Idempotent: seeding again returns 0
    count2 = await svc.seed_tax_brackets(tenant_id=tenant["id"], effective_year=2024)
    assert count2 == 0


async def test_duplicate_salary_grade_code_rejected(app_session, admin_session):
    """Creating a salary grade with a duplicate code raises 409."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    await svc.create_salary_grade(
        tenant_id=tenant["id"],
        data={"name": "Grade A", "code": "GR-A", "basic_salary": Decimal("3000.00")},
    )

    with pytest.raises(PayrollConfigService.Error) as exc_info:
        await svc.create_salary_grade(
            tenant_id=tenant["id"],
            data={"name": "Grade A Again", "code": "GR-A", "basic_salary": Decimal("3500.00")},
        )
    assert exc_info.value.code == 409


async def test_soft_delete_salary_grade(app_session, admin_session):
    """Deleting a salary grade sets deleted_at and removes from active list."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    grade = await svc.create_salary_grade(
        tenant_id=tenant["id"],
        data={"name": "To Delete", "code": "TDEL", "basic_salary": Decimal("2000.00")},
    )
    grade_id = grade.id

    await svc.delete_salary_grade(tenant["id"], grade_id)

    # Should not appear in list
    grades = await svc.list_salary_grades(tenant["id"], active_only=False)
    grade_ids = [g.id for g in grades]
    assert grade_id not in grade_ids

    # Getting by ID should 404
    with pytest.raises(PayrollConfigService.Error) as exc_info:
        await svc._get_salary_grade(tenant["id"], grade_id)
    assert exc_info.value.code == 404


async def test_tax_bracket_contiguity_validation(app_session, admin_session):
    """Updating a bracket to break contiguity raises 422."""
    tenant = await create_test_tenant(admin_session)
    await _seed_payroll_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    await svc.seed_tax_brackets(tenant_id=tenant["id"], effective_year=2024)

    brackets = await svc.list_tax_brackets(tenant["id"], effective_year=2024)
    band2 = [b for b in brackets if b.band_number == 2][0]

    # Break contiguity: set band 2 lower_limit to 500 (should be 490)
    with pytest.raises(PayrollConfigService.Error) as exc_info:
        await svc.update_tax_bracket(
            tenant["id"],
            band2.id,
            {"lower_limit": Decimal("500.00")},
        )
    assert exc_info.value.code == 422

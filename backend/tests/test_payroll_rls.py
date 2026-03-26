"""
Tests for payroll RLS isolation (Phase 4D).

Covers: salary grade, payroll run, payroll item, and salary config tenant
isolation. Also verifies payroll_audit_log is append-only (no UPDATE/DELETE).

Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_payroll_data(admin_session, tenant_id):
    """Seed a full set of payroll data for one tenant. Returns all IDs."""
    school_id = uuid4()
    staff_id = uuid4()
    user_id = uuid4()
    grade_id = uuid4()
    config_id = uuid4()
    run_id = uuid4()
    item_id = uuid4()
    audit_id = uuid4()

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

    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Staff', 'RLS',
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher', '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(staff_id), "tid": str(tenant_id), "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"staff-{uuid4().hex[:8]}@test.com",
        },
    )

    # Salary grade
    await admin_session.execute(
        text("""
            INSERT INTO salary_grades (id, tenant_id, name, code, basic_salary,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                'Grade A', :code, 4000.00,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(grade_id), "tid": str(tenant_id), "code": f"GR-{uuid4().hex[:4]}"},
    )

    # Salary config
    await admin_session.execute(
        text("""
            INSERT INTO staff_salary_configs (id, tenant_id, staff_id,
                salary_grade_id, basic_salary, effective_date, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:staff_id AS uuid), CAST(:grade_id AS uuid),
                4000.00, '2026-01-01', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(config_id), "tid": str(tenant_id),
            "staff_id": str(staff_id), "grade_id": str(grade_id),
        },
    )

    # Payroll run
    await admin_session.execute(
        text("""
            INSERT INTO payroll_runs (id, tenant_id, school_id,
                month, year, run_number, status, run_type,
                currency, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                3, 2026, 1, 'calculated', 'regular',
                'GHS', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(run_id), "tid": str(tenant_id), "sid": str(school_id)},
    )

    # Payroll item
    await admin_session.execute(
        text("""
            INSERT INTO payroll_items (id, tenant_id, payroll_run_id, staff_id,
                staff_name, staff_code,
                basic_salary, total_allowances, gross_salary,
                taxable_income, paye_tax, ssnit_employee, ssnit_employer,
                tier2_employer, tier3_employee, total_deductions, net_salary,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:run_id AS uuid), CAST(:staff_id AS uuid),
                'Staff RLS', 'STF-RLS',
                4000.00, 500.00, 4500.00,
                4280.00, 640.00, 220.00, 520.00,
                200.00, 0.00, 860.00, 3640.00,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(item_id), "tid": str(tenant_id),
            "run_id": str(run_id), "staff_id": str(staff_id),
        },
    )

    # Payroll audit log entry
    await admin_session.execute(
        text("""
            INSERT INTO payroll_audit_log (id, tenant_id, entity_type, entity_id,
                action, performed_by, performed_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                'payroll_run', CAST(:run_id AS uuid),
                'created', CAST(:user_id AS uuid), CURRENT_TIMESTAMP)
        """),
        {
            "id": str(audit_id), "tid": str(tenant_id),
            "run_id": str(run_id), "user_id": str(user_id),
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "staff_id": staff_id,
        "user_id": user_id,
        "grade_id": grade_id,
        "config_id": config_id,
        "run_id": run_id,
        "item_id": item_id,
        "audit_id": audit_id,
    }


# --- Tests ---


async def test_salary_grade_tenant_isolation(app_session, admin_session):
    """Salary grades from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_payroll_data(admin_session, tenant_a["id"])
    await _seed_payroll_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM salary_grades WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["grade_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_payroll_run_tenant_isolation(app_session, admin_session):
    """Payroll runs from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_payroll_data(admin_session, tenant_a["id"])
    await _seed_payroll_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM payroll_runs WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["run_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_payroll_item_tenant_isolation(app_session, admin_session):
    """Payroll items from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_payroll_data(admin_session, tenant_a["id"])
    await _seed_payroll_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM payroll_items WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["item_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_salary_config_tenant_isolation(app_session, admin_session):
    """Staff salary configs from Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    data_a = await _seed_payroll_data(admin_session, tenant_a["id"])
    await _seed_payroll_data(admin_session, tenant_b["id"])

    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(
        text("SELECT id FROM staff_salary_configs WHERE id = CAST(:id AS uuid)"),
        {"id": str(data_a["config_id"])},
    )
    assert result.scalar_one_or_none() is None


async def test_audit_log_insert_only(app_session, admin_session):
    """Attempting to UPDATE payroll_audit_log via app user fails."""
    tenant_a = await create_test_tenant(admin_session)
    data_a = await _seed_payroll_data(admin_session, tenant_a["id"])

    await set_app_tenant_context(app_session, tenant_a["id"])

    with pytest.raises(ProgrammingError):
        await app_session.execute(
            text("""
                UPDATE payroll_audit_log SET action = 'tampered'
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(data_a["audit_id"])},
        )
    await app_session.rollback()


async def test_audit_log_delete_blocked(app_session, admin_session):
    """Attempting to DELETE from payroll_audit_log via app user fails."""
    tenant_a = await create_test_tenant(admin_session)
    data_a = await _seed_payroll_data(admin_session, tenant_a["id"])

    await set_app_tenant_context(app_session, tenant_a["id"])

    with pytest.raises(ProgrammingError):
        await app_session.execute(
            text("""
                DELETE FROM payroll_audit_log WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(data_a["audit_id"])},
        )
    await app_session.rollback()

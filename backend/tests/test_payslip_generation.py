"""
Tests for payslip PDF generation (Phase 4C).

Covers: PDF generation (mocked WeasyPrint), account masking, YTD totals,
and school branding.

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


async def _seed_payslip_prereqs(admin_session, tenant_id, *, with_branding=False):
    """Seed school, staff, payroll run, and payroll item for payslip tests."""
    school_id = uuid4()
    staff_id = uuid4()
    run_id = uuid4()
    item_id = uuid4()

    logo_url = "https://s3.amazonaws.com/logos/school.png" if with_branding else None
    primary_color = "#1B4F72" if with_branding else None

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, staff_id_prefix, is_active,
                logo_url, primary_color,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', 'STF', true,
                :logo, :color,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(school_id), "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}",
            "logo": logo_url, "color": primary_color,
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Kofi', 'Mensah',
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

    # Create a payroll run in 'calculated' status
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

    # Create a payroll item
    await admin_session.execute(
        text("""
            INSERT INTO payroll_items (id, tenant_id, payroll_run_id, staff_id,
                staff_name, staff_code, department_name, salary_grade_name,
                basic_salary, total_allowances, gross_salary,
                taxable_income, paye_tax, ssnit_employee, ssnit_employer,
                tier2_employer, tier3_employee, total_deductions, net_salary,
                payment_method, bank_name, account_number,
                ssnit_number, tin_number,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:run_id AS uuid), CAST(:staff_id AS uuid),
                'Kofi Mensah', 'STF-001', 'Mathematics', 'Grade A',
                4000.00, 500.00, 4500.00,
                4280.00, 639.75, 220.00, 520.00,
                200.00, 0.00, 859.75, 3640.25,
                'bank_transfer', 'GCB Bank', '1234567890',
                'SSNIT-001', 'TIN-001',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(item_id), "tid": str(tenant_id),
            "run_id": str(run_id), "staff_id": str(staff_id),
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "staff_id": staff_id,
        "run_id": run_id,
        "item_id": item_id,
        "logo_url": logo_url,
        "primary_color": primary_color,
    }


# --- Tests ---


async def test_generate_payslip_pdf(app_session, admin_session):
    """Generating a payslip returns a dict with download_url and staff details.

    WeasyPrint and S3 are mocked since this is a service test.
    """
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_payslip_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayslipService
    from unittest.mock import patch, MagicMock

    svc = PayslipService(app_session)

    # Mock WeasyPrint HTML and S3
    mock_html = MagicMock()
    mock_html.return_value.write_pdf.return_value = b"%PDF-fake-content"

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/payslip.pdf"

    with patch("app.services.payroll.payslip_service.HTML", mock_html), \
         patch("app.services.payroll.payslip_service.get_s3_service", return_value=mock_s3):
        result = await svc.generate_payslip_pdf(
            tenant_id=tenant["id"],
            run_id=prereqs["run_id"],
            staff_id=prereqs["staff_id"],
        )

    assert "download_url" in result
    assert result["staff_name"] == "Kofi Mensah"
    assert result["staff_code"] == "STF-001"
    assert result["month"] == 3
    assert result["year"] == 2026
    assert result["expires_in_seconds"] == 300


async def test_payslip_account_masking(app_session, admin_session):
    """Account number in payslip context shows only last 4 digits."""
    from app.services.payroll.payslip_service import _mask_account_number

    assert _mask_account_number("1234567890") == "****7890"
    assert _mask_account_number("AB") == "****"
    assert _mask_account_number(None) == "N/A"


async def test_payslip_ytd_totals(app_session, admin_session):
    """YTD calculation sums prior months' items in the same year."""
    tenant = await create_test_tenant(admin_session)
    school_id = uuid4()
    staff_id = uuid4()

    tenant_id = tenant["id"]

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
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title, employment_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Kofi', 'YTD',
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

    # Create 3 months of payroll runs and items
    for month in (1, 2, 3):
        run_id = uuid4()
        item_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO payroll_runs (id, tenant_id, school_id,
                    month, year, run_number, status, run_type,
                    currency, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :month, 2026, 1, 'approved', 'regular',
                    'GHS', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(run_id), "tid": str(tenant_id), "sid": str(school_id),
             "month": month},
        )
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
                    'Kofi YTD', 'STF-YTD',
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

    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayslipService

    svc = PayslipService(app_session)
    ytd = await svc._calculate_ytd(tenant["id"], staff_id, 2026, 3)

    # 3 months x 4500 gross
    assert ytd["gross"] == Decimal("13500.00")
    # 3 months x 640 tax
    assert ytd["tax"] == Decimal("1920.00")
    # 3 months x 220 ssnit
    assert ytd["ssnit"] == Decimal("660.00")
    # 3 months x 3640 net
    assert ytd["net"] == Decimal("10920.00")


async def test_payslip_school_branding(app_session, admin_session):
    """Payslip render context includes school logo URL and primary color."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_payslip_prereqs(admin_session, tenant["id"], with_branding=True)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.payroll import PayslipService
    from unittest.mock import patch, MagicMock

    svc = PayslipService(app_session)

    # Capture the template context by mocking the template render
    rendered_contexts = []
    original_render = svc._render_payslip_html

    def capture_render(item, school, run, ytd):
        # The school object should have branding
        assert school is not None
        assert school.logo_url == prereqs["logo_url"]
        assert school.primary_color == prereqs["primary_color"]
        return "<html>mocked</html>"

    mock_html = MagicMock()
    mock_html.return_value.write_pdf.return_value = b"%PDF-fake"
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/payslip.pdf"

    with patch.object(svc, "_render_payslip_html", side_effect=capture_render), \
         patch("app.services.payroll.payslip_service.HTML", mock_html), \
         patch("app.services.payroll.payslip_service.get_s3_service", return_value=mock_s3):
        result = await svc.generate_payslip_pdf(
            tenant_id=tenant["id"],
            run_id=prereqs["run_id"],
            staff_id=prereqs["staff_id"],
        )

    assert result["download_url"] is not None

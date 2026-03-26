"""
Tests for bank file generation (Phase 4C).

Covers: GCB format, Ecobank format, Mobile Money file, CSV injection
protection, and S3 upload key format.

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


async def _seed_bank_file_prereqs(admin_session, tenant_id, *, payment_method="bank_transfer"):
    """Seed school, staff, approved payroll run, item, and bank config."""
    school_id = uuid4()
    staff_id = uuid4()
    run_id = uuid4()
    item_id = uuid4()
    config_id = uuid4()

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
                :staff_num, 'Kwame', 'Asante',
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

    # Approved payroll run
    await admin_session.execute(
        text("""
            INSERT INTO payroll_runs (id, tenant_id, school_id,
                month, year, run_number, status, run_type,
                currency, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                3, 2026, 1, 'approved', 'regular',
                'GHS', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(run_id), "tid": str(tenant_id), "sid": str(school_id)},
    )

    phone = "0241234567" if payment_method == "mobile_money" else None
    await admin_session.execute(
        text("""
            INSERT INTO payroll_items (id, tenant_id, payroll_run_id, staff_id,
                staff_name, staff_code,
                basic_salary, total_allowances, gross_salary,
                taxable_income, paye_tax, ssnit_employee, ssnit_employer,
                tier2_employer, tier3_employee, total_deductions, net_salary,
                payment_method, bank_name, account_number, mobile_money_number,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:run_id AS uuid), CAST(:staff_id AS uuid),
                'Kwame Asante', 'STF-001',
                4000.00, 500.00, 4500.00,
                4280.00, 640.00, 220.00, 520.00,
                200.00, 0.00, 860.00, 3640.00,
                :pm, :bank, :acct, :phone,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(item_id), "tid": str(tenant_id),
            "run_id": str(run_id), "staff_id": str(staff_id),
            "pm": payment_method,
            "bank": "GCB Bank" if payment_method == "bank_transfer" else None,
            "acct": "1234567890" if payment_method == "bank_transfer" else None,
            "phone": phone,
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "staff_id": staff_id,
        "run_id": run_id,
        "item_id": item_id,
    }


async def _create_bank_config(app_session, tenant_id, bank_name, column_mapping):
    """Create a bank file config via the service."""
    from app.services.payroll import PayrollConfigService

    svc = PayrollConfigService(app_session)
    return await svc.create_bank_file_config(
        tenant_id=tenant_id,
        data={
            "bank_name": bank_name,
            "column_mapping": column_mapping,
            "include_header_row": True,
        },
    )


# --- Tests ---


async def test_generate_gcb_format(app_session, admin_session):
    """GCB bank file contains correct CSV columns."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_bank_file_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    gcb_mapping = [
        {"header": "Beneficiary Name", "source": "staff_name"},
        {"header": "Account Number", "source": "account_number"},
        {"header": "Amount", "source": "net_salary", "format": "decimal_2"},
    ]
    await _create_bank_config(app_session, tenant["id"], "GCB Bank", gcb_mapping)

    from app.services.payroll import BankFileService
    from unittest.mock import patch, MagicMock

    svc = BankFileService(app_session)

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/gcb.csv"

    with patch("app.services.payroll.bank_file_service.get_s3_service", return_value=mock_s3):
        result = await svc.generate_bank_file(
            tenant_id=tenant["id"],
            run_id=prereqs["run_id"],
            bank_name="GCB Bank",
        )

    assert result["bank_name"] == "GCB Bank"
    assert result["record_count"] == 1
    assert result["total_amount"] == Decimal("3640.00")

    # Verify the uploaded content
    upload_call = mock_s3.upload_file.call_args
    content = upload_call.kwargs["file_content"].decode("utf-8")
    lines = content.strip().split("\n")

    # Header row + 1 data row
    assert len(lines) == 2
    assert "Beneficiary Name" in lines[0]
    assert "Kwame Asante" in lines[1]
    assert "3640.00" in lines[1]


async def test_generate_ecobank_format(app_session, admin_session):
    """Ecobank bank file uses pipe delimiter when configured."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_bank_file_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    eco_mapping = [
        {"header": "Name", "source": "staff_name"},
        {"header": "Account", "source": "account_number"},
        {"header": "Net Pay", "source": "net_salary", "format": "decimal_2"},
    ]

    from app.services.payroll import PayrollConfigService

    cfg_svc = PayrollConfigService(app_session)
    await cfg_svc.create_bank_file_config(
        tenant_id=tenant["id"],
        data={
            "bank_name": "Ecobank",
            "column_mapping": eco_mapping,
            "include_header_row": True,
            "delimiter": "|",
        },
    )

    from app.services.payroll import BankFileService
    from unittest.mock import patch, MagicMock

    svc = BankFileService(app_session)

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/eco.csv"

    with patch("app.services.payroll.bank_file_service.get_s3_service", return_value=mock_s3):
        result = await svc.generate_bank_file(
            tenant_id=tenant["id"],
            run_id=prereqs["run_id"],
            bank_name="Ecobank",
        )

    assert result["bank_name"] == "Ecobank"

    content = mock_s3.upload_file.call_args.kwargs["file_content"].decode("utf-8")
    lines = content.strip().split("\n")
    # Pipe delimiter
    assert "|" in lines[0]
    assert "Name|Account|Net Pay" == lines[0]


async def test_generate_mobile_money_file(app_session, admin_session):
    """MoMo bank file includes phone numbers and filters by mobile_money payment method."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_bank_file_prereqs(
        admin_session, tenant["id"], payment_method="mobile_money",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    momo_mapping = [
        {"header": "Name", "source": "staff_name"},
        {"header": "Phone", "source": "mobile_money_number"},
        {"header": "Amount", "source": "net_salary", "format": "decimal_2"},
    ]
    await _create_bank_config(app_session, tenant["id"], "MTN Mobile Money", momo_mapping)

    from app.services.payroll import BankFileService
    from unittest.mock import patch, MagicMock

    svc = BankFileService(app_session)

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/momo.csv"

    with patch("app.services.payroll.bank_file_service.get_s3_service", return_value=mock_s3):
        result = await svc.generate_bank_file(
            tenant_id=tenant["id"],
            run_id=prereqs["run_id"],
            bank_name="MTN Mobile Money",
        )

    assert result["record_count"] == 1

    content = mock_s3.upload_file.call_args.kwargs["file_content"].decode("utf-8")
    lines = content.strip().split("\n")
    assert "Phone" in lines[0]
    assert "0241234567" in lines[1]


async def test_csv_injection_protection():
    """Cells starting with =, +, -, @ get prefixed with apostrophe."""
    from app.services.payroll.bank_file_service import _escape_csv_cell

    assert _escape_csv_cell("=CMD()") == "'=CMD()"
    assert _escape_csv_cell("+123") == "'+123"
    assert _escape_csv_cell("-SUM(A1)") == "'-SUM(A1)"
    assert _escape_csv_cell("@SYSTEM") == "'@SYSTEM"
    assert _escape_csv_cell("Normal text") == "Normal text"
    assert _escape_csv_cell("") == ""


async def test_bank_file_uploaded_to_s3(app_session, admin_session):
    """S3 key follows the expected path format."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_bank_file_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    gcb_mapping = [
        {"header": "Name", "source": "staff_name"},
        {"header": "Amount", "source": "net_salary", "format": "decimal_2"},
    ]
    await _create_bank_config(app_session, tenant["id"], "GCB Bank", gcb_mapping)

    from app.services.payroll import BankFileService
    from unittest.mock import patch, MagicMock

    svc = BankFileService(app_session)

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/file.csv"

    with patch("app.services.payroll.bank_file_service.get_s3_service", return_value=mock_s3):
        await svc.generate_bank_file(
            tenant_id=tenant["id"],
            run_id=prereqs["run_id"],
            bank_name="GCB Bank",
        )

    # Verify S3 key format: tenants/{tid}/payroll/{year}/{month}/bank_file_*.csv
    upload_call = mock_s3.upload_file.call_args
    s3_key = upload_call.kwargs["key"]

    assert f"tenants/{tenant['id']}" in s3_key
    assert "payroll/2026/03" in s3_key
    assert "bank_file_gcb_bank_" in s3_key
    assert s3_key.endswith(".csv")

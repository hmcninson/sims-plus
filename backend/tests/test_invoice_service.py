"""
SIMS Plus - Invoice Service Integration Tests

Tests exercise InvoiceService directly with a real PostgreSQL database.
Admin session seeds data (bypasses RLS), app session runs under RLS.

Covers:
- Generate invoice from fee structure
- Invoice number auto-generation
- List invoices with filters
- Get invoice with details
- Cancel invoice
- Only draft invoices can be updated
- Only draft invoices can be deleted
- Invoice status transitions (state machine)
- Tenant isolation
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from app.models.finance import InvoiceStatus
from app.services.finance.invoice_service import InvoiceService
from app.services.finance.fee_structure_service import FeeStructureService
from app.services.finance._shared import FinanceServiceError
from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Raw SQL helpers for seeding
# ---------------------------------------------------------------------------

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_AY_INSERT = text("""
    INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
        status, is_current, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
        :start_date, :end_date, 'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_TERM_INSERT = text("""
    INSERT INTO terms (id, tenant_id, academic_year_id, name, short_name,
        sequence, start_date, end_date, status, is_current,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay_id AS uuid),
        :name, :short_name, :seq, :start_date, :end_date,
        'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name,
        last_name, date_of_birth, gender, status,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
        :fn, :ln, '2012-03-10', 'female', 'active',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_school(session, school_id, tenant_id, slug):
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": f"School {slug}", "slug": slug},
    )


async def _seed_academic_year(session, ay_id, tenant_id):
    await session.execute(
        _AY_INSERT,
        {
            "id": str(ay_id), "tid": str(tenant_id), "name": "2025/2026",
            "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
        },
    )


async def _seed_term(session, term_id, tenant_id, ay_id):
    await session.execute(
        _TERM_INSERT,
        {
            "id": str(term_id), "tid": str(tenant_id), "ay_id": str(ay_id),
            "name": "First Term", "short_name": "T1", "seq": 1,
            "start_date": date(2025, 9, 1), "end_date": date(2025, 12, 20),
        },
    )


async def _seed_student(session, student_id, tenant_id, sid, fn, ln):
    await session.execute(
        _STUDENT_INSERT,
        {"id": str(student_id), "tid": str(tenant_id), "sid": sid, "fn": fn, "ln": ln},
    )


async def _create_fee_structure_with_items(app_session, tenant_id, school_id, items=None):
    """Helper: create a fee structure with default items."""
    svc = FeeStructureService(app_session)
    default_items = items or [
        {"name": "Tuition", "amount": "500.00", "is_optional": False, "sequence": 0},
        {"name": "Exam Fee", "amount": "100.00", "is_optional": False, "sequence": 1},
    ]
    return await svc.create_fee_structure(
        tenant_id=tenant_id,
        school_id=school_id,
        name=f"FS-{uuid4().hex[:6]}",
        items=default_items,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestInvoiceService:
    """Service-level tests for InvoiceService."""

    async def test_create_invoice_from_fee_structure(self, admin_session, app_session):
        """Creating an invoice from a fee structure populates items and totals."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-001", "Ama", "Darko")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)

        inv_svc = InvoiceService(app_session)
        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"],
            school_id=school_id,
            student_id=student_id,
            academic_year_id=ay_id,
            term_id=term_id,
            fee_structure_id=fs.id,
            due_date=date(2026, 3, 15),
        )

        assert invoice.tenant_id == tenant["id"]
        assert invoice.student_id == student_id
        assert invoice.status == InvoiceStatus.DRAFT
        # Tuition (500) + Exam Fee (100) = 600
        assert invoice.subtotal == Decimal("600.00")
        assert invoice.total_amount == Decimal("600.00")
        assert invoice.balance == Decimal("600.00")
        assert invoice.amount_paid == Decimal("0.00")

    async def test_invoice_number_auto_generated(self, admin_session, app_session):
        """Each invoice gets a unique auto-generated invoice number."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id = uuid4(), uuid4(), uuid4()
        student_a, student_b = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_a, tenant["id"], "STU-A", "Alice", "Amoah")
        await _seed_student(admin_session, student_b, tenant["id"], "STU-B", "Ben", "Boateng")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        inv_1 = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_a, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )
        inv_2 = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_b, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        assert inv_1.invoice_number.startswith("INV-")
        assert inv_2.invoice_number.startswith("INV-")
        assert inv_1.invoice_number != inv_2.invoice_number

    async def test_create_invoice_with_manual_items(self, admin_session, app_session):
        """Creating an invoice with explicit items (no fee structure) works."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-MAN", "Kofi", "Mensah")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"],
            school_id=school_id,
            student_id=student_id,
            academic_year_id=ay_id,
            term_id=term_id,
            items=[
                {"description": "Special Workshop", "unit_price": "150.00", "quantity": 1},
                {"description": "Materials", "unit_price": "25.00", "quantity": 2},
            ],
        )

        # 150 + (25 * 2) = 200
        assert invoice.subtotal == Decimal("200.00")
        assert invoice.total_amount == Decimal("200.00")

    async def test_list_invoices_filtered_by_student(self, admin_session, app_session):
        """list_invoices filters by student_id."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id = uuid4(), uuid4(), uuid4()
        student_a, student_b = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_a, tenant["id"], "STU-LA", "Alice", "A")
        await _seed_student(admin_session, student_b, tenant["id"], "STU-LB", "Bob", "B")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_a, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )
        await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_b, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        invoices, total = await inv_svc.list_invoices(
            tenant_id=tenant["id"], student_id=student_a,
        )

        assert total == 1
        assert invoices[0].student_id == student_a

    async def test_get_invoice_with_details(self, admin_session, app_session):
        """get_invoice returns invoice with items and payments loaded."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-DET", "Ama", "Detail")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        fetched = await inv_svc.get_invoice(tenant["id"], invoice.id)
        assert fetched is not None
        assert len(fetched.items) == 2  # Two mandatory items from fee structure
        assert fetched.payments is not None  # Empty list, but loaded

    async def test_cancel_draft_invoice(self, admin_session, app_session):
        """Cancelling a draft invoice sets status to cancelled."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-CAN", "Kofi", "Cancel")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        # Draft -> Issued first (DRAFT cannot go directly to CANCELLED via cancel_invoice
        # unless state machine allows DRAFT -> CANCELLED)
        # Actually, the state machine DOES allow DRAFT -> CANCELLED
        cancelled = await inv_svc.cancel_invoice(
            tenant_id=tenant["id"],
            invoice_id=invoice.id,
            cancelled_by=user["id"],
            reason="Created by mistake",
        )

        assert cancelled.status == InvoiceStatus.CANCELLED
        assert cancelled.cancel_reason == "Created by mistake"

    async def test_update_only_draft_invoices(self, admin_session, app_session):
        """update_invoice raises error for non-draft invoices."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-UP", "Yaa", "Update")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        # Issue the invoice
        await inv_svc.issue_invoice(
            tenant_id=tenant["id"], invoice_id=invoice.id, issued_by=user["id"],
        )

        # Now try to update the issued invoice
        with pytest.raises(FinanceServiceError) as exc_info:
            await inv_svc.update_invoice(
                tenant_id=tenant["id"], invoice_id=invoice.id,
                notes="Updated notes",
            )

        assert exc_info.value.code == "invalid_status"

    async def test_delete_only_draft_invoices(self, admin_session, app_session):
        """delete_invoice raises error for non-draft invoices."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-DEL", "Kwame", "Delete")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        # Issue the invoice
        await inv_svc.issue_invoice(
            tenant_id=tenant["id"], invoice_id=invoice.id, issued_by=user["id"],
        )

        with pytest.raises(FinanceServiceError) as exc_info:
            await inv_svc.delete_invoice(tenant_id=tenant["id"], invoice_id=invoice.id)

        assert exc_info.value.code == "invalid_status"

    async def test_issue_invoice_transitions_status(self, admin_session, app_session):
        """Issuing a draft invoice transitions status to issued."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-ISS", "Esi", "Issue")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        issued = await inv_svc.issue_invoice(
            tenant_id=tenant["id"],
            invoice_id=invoice.id,
            issued_by=user["id"],
            issue_date=date(2026, 1, 15),
        )

        assert issued.status == InvoiceStatus.ISSUED
        assert issued.issue_date == date(2026, 1, 15)
        assert issued.issued_by == user["id"]

    async def test_invalid_status_transition_raises_error(self, admin_session, app_session):
        """Attempting an invalid status transition raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-INV", "Kojo", "Invalid")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant["id"], school_id)
        inv_svc = InvoiceService(app_session)

        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        # Issue the invoice
        await inv_svc.issue_invoice(
            tenant_id=tenant["id"], invoice_id=invoice.id, issued_by=user["id"],
        )
        # Cancel the issued invoice
        await inv_svc.cancel_invoice(
            tenant_id=tenant["id"], invoice_id=invoice.id,
            cancelled_by=user["id"], reason="Test",
        )

        # Cancelled is a terminal state -- cannot issue again
        with pytest.raises(FinanceServiceError) as exc_info:
            await inv_svc.issue_invoice(
                tenant_id=tenant["id"], invoice_id=invoice.id, issued_by=user["id"],
            )

        assert exc_info.value.code == "invalid_status_transition"


class TestInvoiceTenantIsolation:
    """Tenant A must NOT see Tenant B's invoices."""

    async def test_tenant_a_cannot_see_tenant_b_invoices(self, admin_session, app_session):
        """Invoices from Tenant A are invisible to Tenant B under RLS."""
        # Tenant A setup
        tenant_a = await create_test_tenant(admin_session)
        school_a, ay_a, term_a, student_a = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_a, tenant_a["id"], tenant_a["subdomain"])
        await _seed_academic_year(admin_session, ay_a, tenant_a["id"])
        await _seed_term(admin_session, term_a, tenant_a["id"], ay_a)
        await _seed_student(admin_session, student_a, tenant_a["id"], "STU-TA", "Alice", "A")

        # Tenant B setup
        tenant_b = await create_test_tenant(admin_session)
        school_b = uuid4()
        await _seed_school(admin_session, school_b, tenant_b["id"], tenant_b["subdomain"])
        await admin_session.commit()

        # Create invoice as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        fs = await _create_fee_structure_with_items(app_session, tenant_a["id"], school_a)
        inv_svc = InvoiceService(app_session)
        inv_a = await inv_svc.create_invoice(
            tenant_id=tenant_a["id"], school_id=school_a,
            student_id=student_a, academic_year_id=ay_a, term_id=term_a,
            fee_structure_id=fs.id,
        )
        inv_a_id = inv_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        invoices, total = await inv_svc.list_invoices(tenant_id=tenant_b["id"])
        invoice_ids = {inv.id for inv in invoices}
        assert inv_a_id not in invoice_ids
        assert total == 0

        found = await inv_svc.get_invoice(tenant_b["id"], inv_a_id)
        assert found is None

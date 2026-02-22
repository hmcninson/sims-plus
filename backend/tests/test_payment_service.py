"""
SIMS Plus - Payment Service Integration Tests

Tests exercise PaymentService directly with a real PostgreSQL database.
Admin session seeds data (bypasses RLS), app session runs under RLS.

Covers:
- Record cash payment (updates invoice balance)
- Record MoMo payment (stores transaction reference and provider)
- Void payment (reverses invoice balance, records reason)
- List payments with filters
- Cannot void already-voided payment
- Tenant isolation
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from app.models.finance import InvoiceStatus, PaymentMethod, PaymentStatus
from app.services.finance.payment_service import PaymentService
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


async def _create_issued_invoice(app_session, tenant_id, school_id, ay_id, term_id, student_id, user_id, amount="600.00"):
    """Helper: create and issue an invoice with one fee item."""
    fs_svc = FeeStructureService(app_session)
    fs = await fs_svc.create_fee_structure(
        tenant_id=tenant_id, school_id=school_id,
        name=f"FS-{uuid4().hex[:6]}",
        items=[{"name": "Tuition", "amount": amount, "is_optional": False}],
    )

    inv_svc = InvoiceService(app_session)
    invoice = await inv_svc.create_invoice(
        tenant_id=tenant_id, school_id=school_id,
        student_id=student_id, academic_year_id=ay_id, term_id=term_id,
        fee_structure_id=fs.id,
    )
    # Issue it so payments can update status
    issued = await inv_svc.issue_invoice(
        tenant_id=tenant_id, invoice_id=invoice.id, issued_by=user_id,
    )
    return issued


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestPaymentService:
    """Service-level tests for PaymentService."""

    async def test_record_cash_payment_updates_invoice_balance(self, admin_session, app_session):
        """Recording a cash payment against an invoice reduces the balance."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-CP", "Kofi", "Cash")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
        )

        pay_svc = PaymentService(app_session)
        payment = await pay_svc.record_payment(
            tenant_id=tenant["id"],
            school_id=school_id,
            student_id=student_id,
            amount=Decimal("200.00"),
            payment_method="cash",
            invoice_id=invoice.id,
            payer_name="Mr. Cash",
        )

        assert payment.amount == Decimal("200.00")
        assert payment.payment_method == PaymentMethod.CASH
        assert payment.status == PaymentStatus.COMPLETED
        assert payment.receipt_number.startswith("RCP-")

        # Verify invoice was updated
        inv_svc = InvoiceService(app_session)
        updated_inv = await inv_svc.get_invoice(tenant["id"], invoice.id)
        assert updated_inv.amount_paid == Decimal("200.00")
        assert updated_inv.balance == Decimal("400.00")
        assert updated_inv.status == InvoiceStatus.PARTIAL

    async def test_full_payment_marks_invoice_paid(self, admin_session, app_session):
        """Paying the full invoice amount transitions status to paid."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-FP", "Ama", "Full")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
            amount="500.00",
        )

        pay_svc = PaymentService(app_session)
        await pay_svc.record_payment(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, amount=Decimal("500.00"),
            payment_method="cash", invoice_id=invoice.id,
        )

        inv_svc = InvoiceService(app_session)
        updated = await inv_svc.get_invoice(tenant["id"], invoice.id)
        assert updated.status == InvoiceStatus.PAID
        assert updated.balance == Decimal("0.00")

    async def test_record_momo_payment_stores_transaction_details(self, admin_session, app_session):
        """MoMo payment stores phone, transaction ID, and provider."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-MM", "Akua", "MoMo")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
        )

        pay_svc = PaymentService(app_session)
        payment = await pay_svc.record_payment(
            tenant_id=tenant["id"],
            school_id=school_id,
            student_id=student_id,
            amount=Decimal("300.00"),
            payment_method="momo_mtn",
            invoice_id=invoice.id,
            momo_phone="+233241234567",
            momo_transaction_id="TXN-MTN-12345",
        )

        assert payment.payment_method == PaymentMethod.MOMO_MTN
        assert payment.momo_phone == "+233241234567"
        assert payment.momo_transaction_id == "TXN-MTN-12345"
        assert payment.momo_provider == "MTN"

    async def test_void_payment_reverses_invoice_balance(self, admin_session, app_session):
        """Voiding a payment reverses the invoice balance and records reason."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-VP", "Kwesi", "Void")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
            amount="500.00",
        )

        pay_svc = PaymentService(app_session)
        payment = await pay_svc.record_payment(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, amount=Decimal("500.00"),
            payment_method="cash", invoice_id=invoice.id,
        )

        # Now void it
        voided = await pay_svc.void_payment(
            tenant_id=tenant["id"],
            payment_id=payment.id,
            voided_by=user["id"],
            reason="Duplicate payment",
        )

        assert voided.is_voided is True
        assert voided.void_reason == "Duplicate payment"
        assert voided.status == PaymentStatus.CANCELLED

        # Invoice balance should be restored
        inv_svc = InvoiceService(app_session)
        updated_inv = await inv_svc.get_invoice(tenant["id"], invoice.id)
        assert updated_inv.amount_paid == Decimal("0.00")
        assert updated_inv.balance == Decimal("500.00")
        assert updated_inv.status == InvoiceStatus.ISSUED

    async def test_void_already_voided_raises_error(self, admin_session, app_session):
        """Voiding an already-voided payment raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-DV", "Aba", "Double")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
        )

        pay_svc = PaymentService(app_session)
        payment = await pay_svc.record_payment(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, amount=Decimal("100.00"),
            payment_method="cash", invoice_id=invoice.id,
        )

        await pay_svc.void_payment(
            tenant_id=tenant["id"], payment_id=payment.id,
            voided_by=user["id"], reason="First void",
        )

        with pytest.raises(FinanceServiceError) as exc_info:
            await pay_svc.void_payment(
                tenant_id=tenant["id"], payment_id=payment.id,
                voided_by=user["id"], reason="Second void",
            )

        assert exc_info.value.code == "already_voided"

    async def test_list_payments_by_student(self, admin_session, app_session):
        """list_payments filters by student_id."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id = uuid4(), uuid4(), uuid4()
        student_a, student_b = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_a, tenant["id"], "STU-PA", "Alice", "A")
        await _seed_student(admin_session, student_b, tenant["id"], "STU-PB", "Bob", "B")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        inv_a = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_a, user["id"],
        )
        inv_b = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_b, user["id"],
        )

        pay_svc = PaymentService(app_session)
        await pay_svc.record_payment(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_a, amount=Decimal("100.00"),
            payment_method="cash", invoice_id=inv_a.id,
        )
        await pay_svc.record_payment(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_b, amount=Decimal("200.00"),
            payment_method="cash", invoice_id=inv_b.id,
        )

        payments, total = await pay_svc.list_payments(
            tenant_id=tenant["id"], student_id=student_a,
        )

        assert total == 1
        assert payments[0].student_id == student_a


class TestPaymentTenantIsolation:
    """Tenant A must NOT see Tenant B's payments."""

    async def test_tenant_a_cannot_see_tenant_b_payments(self, admin_session, app_session):
        """Payments from Tenant A are invisible to Tenant B under RLS."""
        # Tenant A
        tenant_a = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        school_a, ay_a, term_a, student_a = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_a, tenant_a["id"], tenant_a["subdomain"])
        await _seed_academic_year(admin_session, ay_a, tenant_a["id"])
        await _seed_term(admin_session, term_a, tenant_a["id"], ay_a)
        await _seed_student(admin_session, student_a, tenant_a["id"], "STU-IA", "Alice", "A")

        # Tenant B
        tenant_b = await create_test_tenant(admin_session)
        school_b = uuid4()
        await _seed_school(admin_session, school_b, tenant_b["id"], tenant_b["subdomain"])
        await admin_session.commit()

        # Record payment as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        inv = await _create_issued_invoice(
            app_session, tenant_a["id"], school_a, ay_a, term_a, student_a, user_a["id"],
        )
        pay_svc = PaymentService(app_session)
        pay_a = await pay_svc.record_payment(
            tenant_id=tenant_a["id"], school_id=school_a,
            student_id=student_a, amount=Decimal("100.00"),
            payment_method="cash", invoice_id=inv.id,
        )
        pay_a_id = pay_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        payments, total = await pay_svc.list_payments(tenant_id=tenant_b["id"])
        payment_ids = {p.id for p in payments}
        assert pay_a_id not in payment_ids
        assert total == 0

        found = await pay_svc.get_payment(tenant_b["id"], pay_a_id)
        assert found is None

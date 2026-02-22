"""
SIMS Plus - Credit Note Service Integration Tests

Tests exercise CreditNoteService directly with a real PostgreSQL database.
Admin session seeds data (bypasses RLS), app session runs under RLS.

Covers:
- Create credit note (draft status)
- Issue credit note (updates student credit balance)
- Issue with auto-apply to oldest unpaid invoice
- Apply credit note to specific invoice
- Cancel credit note (draft and issued)
- Refund credit note (records method/reference)
- Immutability: cannot edit issued credit note
- Cannot cancel applied or refunded credit notes
- Tenant isolation
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from app.models.finance import (
    CreditNoteStatus,
    CreditNoteType,
    InvoiceStatus,
)
from app.services.finance.credit_note_service import CreditNoteService
from app.services.finance.invoice_service import InvoiceService
from app.services.finance.fee_structure_service import FeeStructureService
from app.schemas.finance import (
    CreditNoteCreate,
    CreditNoteUpdate,
    CreditNoteApply,
    CreditNoteRefund,
    CreditNoteCancel,
)
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
    """Helper: create and issue an invoice."""
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
    issued = await inv_svc.issue_invoice(
        tenant_id=tenant_id, invoice_id=invoice.id, issued_by=user_id,
    )
    return issued


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestCreditNoteService:
    """Service-level tests for CreditNoteService."""

    async def test_create_credit_note_draft_status(self, admin_session, app_session):
        """Creating a credit note returns it in draft status."""
        tenant = await create_test_tenant(admin_session)
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-CN", "Ama", "Credit")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("150.00"),
                reason="Overpaid tuition",
            ),
        )

        assert cn.status == CreditNoteStatus.DRAFT
        assert cn.amount == Decimal("150.00")
        assert cn.tenant_id == tenant["id"]
        assert cn.student_id == student_id
        assert cn.credit_note_number.startswith("CN-")

    async def test_issue_credit_note_updates_student_balance(self, admin_session, app_session):
        """Issuing a credit note increases the student's credit_balance."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-IS", "Kofi", "Issue")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("200.00"),
                reason="Overpayment on last term",
            ),
        )

        issued_cn, applied_invoice = await svc.issue_credit_note(
            credit_note_id=cn.id,
            tenant_id=tenant["id"],
            issued_by=user["id"],
            auto_apply=False,
        )

        assert issued_cn.status == CreditNoteStatus.ISSUED
        assert issued_cn.issued_by == user["id"]

        # Student credit balance should increase
        balance = await svc.get_student_credit_balance(student_id, tenant["id"])
        assert balance == Decimal("200.00")

    async def test_issue_with_auto_apply_to_oldest_invoice(self, admin_session, app_session):
        """Issuing with auto_apply=True applies credit to the oldest unpaid invoice."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-AA", "Abena", "Auto")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        # Create an unpaid invoice (500 balance)
        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
            amount="500.00",
        )

        # Create and issue a credit note with auto-apply
        svc = CreditNoteService(app_session)
        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("200.00"),
                reason="Overpayment",
            ),
        )

        issued_cn, applied_invoice = await svc.issue_credit_note(
            credit_note_id=cn.id,
            tenant_id=tenant["id"],
            issued_by=user["id"],
            auto_apply=True,
        )

        assert issued_cn.status == CreditNoteStatus.APPLIED
        assert issued_cn.applied_to_invoice_id == invoice.id
        assert issued_cn.applied_amount == Decimal("200.00")

        # Invoice balance should be reduced
        assert applied_invoice is not None
        assert applied_invoice.balance == Decimal("300.00")
        assert applied_invoice.status == InvoiceStatus.PARTIAL

    async def test_apply_credit_note_to_specific_invoice(self, admin_session, app_session):
        """Manually applying a credit note to a specific invoice updates the balance."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-AP", "Kwesi", "Apply")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
            amount="400.00",
        )

        svc = CreditNoteService(app_session)
        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="fee_reduction",
                student_id=student_id,
                amount=Decimal("400.00"),
                reason="Fee reduction approved",
            ),
        )

        # Issue first
        await svc.issue_credit_note(
            credit_note_id=cn.id, tenant_id=tenant["id"],
            issued_by=user["id"], auto_apply=False,
        )

        # Apply to specific invoice
        applied_cn = await svc.apply_credit_note(
            credit_note_id=cn.id,
            tenant_id=tenant["id"],
            data=CreditNoteApply(invoice_id=invoice.id),
            applied_by=user["id"],
        )

        assert applied_cn.status == CreditNoteStatus.APPLIED
        assert applied_cn.applied_to_invoice_id == invoice.id
        assert applied_cn.applied_amount == Decimal("400.00")

        # Invoice should now be paid
        inv_svc = InvoiceService(app_session)
        updated_inv = await inv_svc.get_invoice(tenant["id"], invoice.id)
        assert updated_inv.balance <= Decimal("0.00")
        assert updated_inv.status == InvoiceStatus.PAID

    async def test_cancel_draft_credit_note(self, admin_session, app_session):
        """Cancelling a draft credit note sets status to cancelled."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-CD", "Akua", "CancelD")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="error_correction",
                student_id=student_id,
                amount=Decimal("100.00"),
                reason="Created by mistake",
            ),
        )

        cancelled = await svc.cancel_credit_note(
            credit_note_id=cn.id,
            tenant_id=tenant["id"],
            data=CreditNoteCancel(reason="Wrong student"),
            cancelled_by=user["id"],
        )

        assert cancelled.status == CreditNoteStatus.CANCELLED
        assert cancelled.cancel_reason == "Wrong student"

    async def test_cancel_issued_credit_note_reverses_balance(self, admin_session, app_session):
        """Cancelling an issued credit note reverses the student's credit balance."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-CI", "Esi", "CancelI")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("300.00"),
                reason="Overpayment",
            ),
        )

        # Issue first (increases student balance by 300)
        await svc.issue_credit_note(
            credit_note_id=cn.id, tenant_id=tenant["id"],
            issued_by=user["id"], auto_apply=False,
        )

        balance_after_issue = await svc.get_student_credit_balance(student_id, tenant["id"])
        assert balance_after_issue == Decimal("300.00")

        # Cancel (should reverse the 300)
        await svc.cancel_credit_note(
            credit_note_id=cn.id,
            tenant_id=tenant["id"],
            data=CreditNoteCancel(reason="Issued in error"),
            cancelled_by=user["id"],
        )

        balance_after_cancel = await svc.get_student_credit_balance(student_id, tenant["id"])
        assert balance_after_cancel == Decimal("0.00")

    async def test_refund_credit_note_records_method_and_reference(self, admin_session, app_session):
        """Refunding a credit note records the refund method and reference."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-RF", "Yaa", "Refund")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("250.00"),
                reason="Overpayment to refund",
            ),
        )

        await svc.issue_credit_note(
            credit_note_id=cn.id, tenant_id=tenant["id"],
            issued_by=user["id"], auto_apply=False,
        )

        refunded = await svc.refund_credit_note(
            credit_note_id=cn.id,
            tenant_id=tenant["id"],
            data=CreditNoteRefund(
                refund_method="momo_mtn",
                refund_reference="TXN-REFUND-001",
            ),
            refunded_by=user["id"],
        )

        assert refunded.status == CreditNoteStatus.REFUNDED
        assert refunded.refund_method == "momo_mtn"
        assert refunded.refund_reference == "TXN-REFUND-001"

        # Credit balance should be reversed
        balance = await svc.get_student_credit_balance(student_id, tenant["id"])
        assert balance == Decimal("0.00")

    async def test_cannot_update_issued_credit_note(self, admin_session, app_session):
        """Attempting to update an issued credit note raises ValueError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-IM", "Kofi", "Immut")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("100.00"),
                reason="Test",
            ),
        )

        await svc.issue_credit_note(
            credit_note_id=cn.id, tenant_id=tenant["id"],
            issued_by=user["id"], auto_apply=False,
        )

        with pytest.raises(ValueError, match="Can only update draft credit notes"):
            await svc.update_credit_note(
                credit_note_id=cn.id,
                tenant_id=tenant["id"],
                data=CreditNoteUpdate(amount=Decimal("200.00")),
            )

    async def test_cannot_cancel_applied_credit_note(self, admin_session, app_session):
        """Cancelling an applied credit note raises ValueError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-CA", "Aba", "CancelA")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        invoice = await _create_issued_invoice(
            app_session, tenant["id"], school_id, ay_id, term_id, student_id, user["id"],
            amount="500.00",
        )

        svc = CreditNoteService(app_session)
        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_id,
                amount=Decimal("100.00"),
                reason="Overpayment",
            ),
        )

        # Issue + auto-apply
        await svc.issue_credit_note(
            credit_note_id=cn.id, tenant_id=tenant["id"],
            issued_by=user["id"], auto_apply=True,
        )

        with pytest.raises(ValueError, match="Cannot cancel applied or refunded"):
            await svc.cancel_credit_note(
                credit_note_id=cn.id,
                tenant_id=tenant["id"],
                data=CreditNoteCancel(reason="Too late"),
                cancelled_by=user["id"],
            )

    async def test_cannot_delete_issued_credit_note(self, admin_session, app_session):
        """Deleting an issued credit note raises ValueError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, student_id = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-DI", "Kojo", "DelIss")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CreditNoteService(app_session)

        cn = await svc.create_credit_note(
            tenant_id=tenant["id"],
            school_id=school_id,
            data=CreditNoteCreate(
                credit_note_type="other",
                student_id=student_id,
                amount=Decimal("50.00"),
                reason="Test",
            ),
        )

        await svc.issue_credit_note(
            credit_note_id=cn.id, tenant_id=tenant["id"],
            issued_by=user["id"], auto_apply=False,
        )

        with pytest.raises(ValueError, match="Can only delete draft credit notes"):
            await svc.delete_credit_note(credit_note_id=cn.id, tenant_id=tenant["id"])


class TestCreditNoteTenantIsolation:
    """Tenant A must NOT see Tenant B's credit notes."""

    async def test_tenant_a_cannot_see_tenant_b_credit_notes(self, admin_session, app_session):
        """Credit notes from Tenant A are invisible to Tenant B under RLS."""
        tenant_a = await create_test_tenant(admin_session)
        school_a, student_a = uuid4(), uuid4()
        await _seed_school(admin_session, school_a, tenant_a["id"], tenant_a["subdomain"])
        await _seed_student(admin_session, student_a, tenant_a["id"], "STU-TA", "Alice", "A")

        tenant_b = await create_test_tenant(admin_session)
        school_b = uuid4()
        await _seed_school(admin_session, school_b, tenant_b["id"], tenant_b["subdomain"])
        await admin_session.commit()

        # Create credit note as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = CreditNoteService(app_session)
        cn_a = await svc.create_credit_note(
            tenant_id=tenant_a["id"],
            school_id=school_a,
            data=CreditNoteCreate(
                credit_note_type="overpayment",
                student_id=student_a,
                amount=Decimal("100.00"),
                reason="Tenant A overpayment",
            ),
        )
        cn_a_id = cn_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        credit_notes, total = await svc.list_credit_notes(tenant_id=tenant_b["id"])
        cn_ids = {cn.id for cn in credit_notes}
        assert cn_a_id not in cn_ids
        assert total == 0

        found = await svc.get_credit_note(cn_a_id, tenant_b["id"])
        assert found is None

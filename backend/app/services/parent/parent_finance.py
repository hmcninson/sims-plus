"""
SIMS Plus - Parent Finance Service

Invoice, payment, and fee statement data for parents.
All methods enforce parent-child access verification before returning any data.
Parents see only issued/active invoices (not drafts) and completed payments.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.finance import (
    CreditNote,
    CreditNoteStatus,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Payment,
    PaymentStatus,
)
from app.models.academic import Term
from app.models.student import Student

from app.services.parent._shared import ParentServiceError
from app.services.parent.parent_service import ParentService

logger = structlog.get_logger()


class ParentFinanceService:
    """
    Service for parent access to financial data: invoices, payments, and fee statements.

    Every method verifies parent-child access before returning data.
    Draft invoices and voided/failed payments are excluded from parent views.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._parent = ParentService(db)

    async def get_child_invoices(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """
        Get all non-draft invoices for a child.

        Parents should not see DRAFT invoices (internal workflow state).
        Returns invoices ordered by creation date, most recent first.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Returns:
            List of dicts matching ParentInvoiceSummary schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        result = await self.db.execute(
            select(Invoice)
            .where(
                and_(
                    Invoice.student_id == student_id,
                    Invoice.tenant_id == tenant_id,
                    Invoice.deleted_at.is_(None),
                    # Parents should not see draft invoices
                    Invoice.status != InvoiceStatus.DRAFT,
                )
            )
            .options(joinedload(Invoice.term))
            .order_by(desc(Invoice.created_at))
        )
        invoices = result.scalars().unique().all()

        return [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "term_name": inv.term.name if inv.term else None,
                "total_amount": inv.total_amount,
                "amount_paid": inv.amount_paid,
                "balance": inv.total_amount - inv.amount_paid,
                "status": inv.status.value,
                "due_date": inv.due_date,
                "created_at": inv.created_at,
            }
            for inv in invoices
        ]

    async def get_child_invoice_detail(
        self,
        user_id: UUID,
        student_id: UUID,
        invoice_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """
        Get full invoice detail with line items, payments, and scholarship info.

        Also verifies the invoice belongs to the specified student (IDOR check).

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            invoice_id: The invoice to retrieve
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Returns:
            Dict matching ParentInvoiceDetail schema

        Raises:
            ParentServiceError: If access denied, invoice not found, or IDOR mismatch
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        result = await self.db.execute(
            select(Invoice)
            .where(
                and_(
                    Invoice.id == invoice_id,
                    Invoice.tenant_id == tenant_id,
                    # IDOR check: verify invoice belongs to this student
                    Invoice.student_id == student_id,
                    Invoice.deleted_at.is_(None),
                    # Parents should not see draft invoices
                    Invoice.status != InvoiceStatus.DRAFT,
                )
            )
            .options(
                selectinload(Invoice.items),
                selectinload(Invoice.payments),
                selectinload(Invoice.scholarship_items),
                joinedload(Invoice.term),
            )
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise ParentServiceError(
                "Invoice not found", code="invoice_not_found"
            )

        # Build line items from invoice items
        items = [
            {
                "fee_type_name": item.description,
                "amount": item.amount,
                "description": item.description,
            }
            for item in invoice.items
        ]

        # Build payment list, excluding voided and failed payments
        payments = [
            {
                "id": pmt.id,
                "amount": pmt.amount,
                "method": pmt.payment_method.value,
                "reference_number": pmt.bank_reference or pmt.momo_transaction_id,
                "receipt_number": pmt.receipt_number,
                "date": pmt.payment_date,
                "invoice_number": invoice.invoice_number,
            }
            for pmt in invoice.payments
            if pmt.status == PaymentStatus.COMPLETED and not pmt.is_voided
        ]

        # Sum applied credit notes for display
        credit_notes_applied = Decimal("0.00")
        credit_notes_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditNote.amount), Decimal("0.00")))
            .where(
                and_(
                    CreditNote.tenant_id == tenant_id,
                    CreditNote.student_id == student_id,
                    CreditNote.status == CreditNoteStatus.APPLIED,
                    CreditNote.deleted_at.is_(None),
                    # Only count credit notes applied to this invoice
                    CreditNote.applied_to_invoice_id == invoice.id,
                )
            )
        )
        credit_notes_applied = credit_notes_result.scalar() or Decimal("0.00")

        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "term_name": invoice.term.name if invoice.term else None,
            "total_amount": invoice.total_amount,
            "amount_paid": invoice.amount_paid,
            "balance": invoice.total_amount - invoice.amount_paid,
            "status": invoice.status.value,
            "due_date": invoice.due_date,
            "created_at": invoice.created_at,
            "items": items,
            "payments": payments,
            "scholarship_discount": invoice.scholarship_discount,
            "credit_notes_applied": credit_notes_applied,
        }

    async def get_child_fee_statement(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
        term_id: Optional[UUID] = None,
    ) -> dict:
        """
        Get a complete fee statement: total billed, paid, and outstanding.

        If term_id is provided, scope to that term only. Otherwise,
        aggregate across all terms.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)
            term_id: Optional term filter

        Returns:
            Dict matching FeeStatement schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        # Get student summary for the response
        student_result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.class_),
                selectinload(Student.section),
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise ParentServiceError("Student not found", code="student_not_found")

        # Query invoices (excluding drafts and cancelled)
        invoice_conditions = [
            Invoice.student_id == student_id,
            Invoice.tenant_id == tenant_id,
            Invoice.deleted_at.is_(None),
            Invoice.status.notin_([InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]),
        ]
        if term_id:
            invoice_conditions.append(Invoice.term_id == term_id)

        invoices_result = await self.db.execute(
            select(Invoice)
            .where(and_(*invoice_conditions))
            .options(joinedload(Invoice.term))
            .order_by(desc(Invoice.created_at))
        )
        invoices = invoices_result.scalars().unique().all()

        # Aggregate totals
        total_billed = sum(inv.total_amount for inv in invoices)
        total_paid = sum(inv.amount_paid for inv in invoices)

        # Sum issued/applied credit notes for this student
        credit_conditions = [
            CreditNote.student_id == student_id,
            CreditNote.tenant_id == tenant_id,
            CreditNote.status.in_([CreditNoteStatus.ISSUED, CreditNoteStatus.APPLIED]),
            CreditNote.deleted_at.is_(None),
        ]
        credits_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditNote.amount), Decimal("0.00")))
            .where(and_(*credit_conditions))
        )
        total_credits = credits_result.scalar() or Decimal("0.00")

        outstanding = total_billed - total_paid

        # Resolve term name
        term_name = None
        if term_id:
            term_result = await self.db.execute(
                select(Term.name)
                .where(
                    and_(
                        Term.id == term_id,
                        Term.tenant_id == tenant_id,
                        Term.deleted_at.is_(None),
                    )
                )
            )
            term_row = term_result.scalar_one_or_none()
            term_name = term_row if term_row else None

        # Build invoice summaries
        invoice_summaries = [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "term_name": inv.term.name if inv.term else None,
                "total_amount": inv.total_amount,
                "amount_paid": inv.amount_paid,
                "balance": inv.total_amount - inv.amount_paid,
                "status": inv.status.value,
                "due_date": inv.due_date,
                "created_at": inv.created_at,
            }
            for inv in invoices
        ]

        child_summary = {
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "photo_url": student.photo_url,
            "class_name": student.class_.name if student.class_ else None,
            "section_name": student.section.name if student.section else None,
            "admission_number": student.admission_number,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender.value if student.gender else None,
        }

        return {
            "student": child_summary,
            "term_name": term_name,
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_credits": total_credits,
            "outstanding_balance": outstanding,
            "invoices": invoice_summaries,
        }

    async def get_child_payment_history(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """
        Get all completed, non-voided payments for a child.

        Returns payments ordered by date, most recent first.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Returns:
            List of dicts matching ParentPaymentSummary schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        result = await self.db.execute(
            select(Payment)
            .where(
                and_(
                    Payment.student_id == student_id,
                    Payment.tenant_id == tenant_id,
                    # Only show completed, non-voided payments to parents
                    Payment.status == PaymentStatus.COMPLETED,
                    Payment.is_voided == False,
                )
            )
            .options(joinedload(Payment.invoice))
            .order_by(desc(Payment.payment_date))
        )
        payments = result.scalars().unique().all()

        return [
            {
                "id": pmt.id,
                "amount": pmt.amount,
                "method": pmt.payment_method.value,
                "reference_number": pmt.bank_reference or pmt.momo_transaction_id,
                "receipt_number": pmt.receipt_number,
                "date": pmt.payment_date,
                "invoice_number": (
                    pmt.invoice.invoice_number if pmt.invoice else None
                ),
            }
            for pmt in payments
        ]

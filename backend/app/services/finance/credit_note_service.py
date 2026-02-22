"""
SIMS Plus - Credit Note Service

Business logic for credit note operations.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.finance import (
    Invoice,
    InvoiceStatus,
    CreditNote,
    CreditNoteStatus,
    CreditNoteType,
)
from app.models.student import Student
from app.utils.sanitize import escape_ilike


class CreditNoteService:
    """Service for credit note operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_credit_note_number(self, tenant_id: UUID) -> str:
        """Generate unique credit note number for tenant."""
        from sqlalchemy import text

        year = datetime.now().year
        # Get next sequence value
        result = await self.db.execute(text("SELECT nextval('credit_note_number_seq')"))
        seq_num = result.scalar()
        return f"CN-{year}-{seq_num:05d}"

    async def create_credit_note(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data: "CreditNoteCreate",
    ) -> CreditNote:
        """Create a new credit note."""
        credit_note_number = await self._generate_credit_note_number(tenant_id)

        credit_note = CreditNote(
            tenant_id=tenant_id,
            school_id=school_id,
            credit_note_number=credit_note_number,
            credit_note_type=data.credit_note_type,
            original_invoice_id=data.original_invoice_id,
            student_id=data.student_id,
            amount=data.amount,
            currency=data.currency or "GHS",
            reason=data.reason,
            status=CreditNoteStatus.DRAFT,
            notes=data.notes,
        )
        self.db.add(credit_note)
        await self.db.flush()
        await self.db.refresh(credit_note)
        return credit_note

    async def get_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
    ) -> Optional[CreditNote]:
        """Get credit note by ID."""
        query = (
            select(CreditNote)
            .options(
                joinedload(CreditNote.student),
                joinedload(CreditNote.original_invoice),
                joinedload(CreditNote.applied_to_invoice),
                joinedload(CreditNote.issued_by_user),
            )
            .where(
                CreditNote.id == credit_note_id,
                CreditNote.tenant_id == tenant_id,
                CreditNote.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_credit_notes(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        status: Optional[CreditNoteStatus] = None,
        credit_note_type: Optional[CreditNoteType] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[CreditNote], int]:
        """List credit notes with filters."""
        query = select(CreditNote).where(
            CreditNote.tenant_id == tenant_id,
            CreditNote.deleted_at.is_(None),
        )

        if school_id:
            query = query.where(CreditNote.school_id == school_id)
        if student_id:
            query = query.where(CreditNote.student_id == student_id)
        if status:
            query = query.where(CreditNote.status == status)
        if credit_note_type:
            query = query.where(CreditNote.credit_note_type == credit_note_type)
        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            safe_search = f"%{escape_ilike(search)}%"
            # Use subquery to find matching student IDs to avoid join conflicts with joinedload
            student_subq = (
                select(Student.id)
                .where(
                    or_(
                        Student.first_name.ilike(safe_search),
                        Student.last_name.ilike(safe_search),
                        Student.student_id.ilike(safe_search),
                    )
                )
            )
            query = query.where(
                or_(
                    CreditNote.credit_note_number.ilike(safe_search),
                    CreditNote.student_id.in_(student_subq),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(CreditNote.student),
        ).order_by(desc(CreditNote.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteUpdate",
    ) -> Optional[CreditNote]:
        """Update a draft credit note."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Can only update draft credit notes")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(credit_note, key, value)

        credit_note.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(credit_note)
        return credit_note

    async def issue_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        issued_by: UUID,
        auto_apply: bool = False,
    ) -> tuple[Optional[CreditNote], Optional[Invoice]]:
        """
        Issue a credit note, making it active.

        Args:
            credit_note_id: The credit note ID
            tenant_id: The tenant ID
            issued_by: The user issuing the credit note
            auto_apply: If True, automatically apply to oldest unpaid invoice

        Returns:
            Tuple of (credit_note, applied_invoice) - applied_invoice is None if not auto-applied
        """
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None, None

        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Can only issue draft credit notes")

        credit_note.status = CreditNoteStatus.ISSUED
        credit_note.issued_by = issued_by
        credit_note.issued_at = datetime.now(timezone.utc)
        credit_note.updated_at = datetime.now(timezone.utc)

        # Update student's credit balance
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        student_query = select(Student).where(
            Student.id == credit_note.student_id,
            Student.tenant_id == tenant_id,
        )
        student_result = await self.db.execute(student_query)
        student = student_result.scalars().first()
        if student:
            current_balance = student.credit_balance or Decimal("0.00")
            student.credit_balance = current_balance + credit_note.amount

        await self.db.flush()
        await self.db.refresh(credit_note)

        applied_invoice = None

        # Auto-apply to oldest unpaid invoice if requested
        if auto_apply and student:
            # Find oldest unpaid invoice for this student
            invoice_query = (
                select(Invoice)
                .where(
                    Invoice.student_id == credit_note.student_id,
                    Invoice.tenant_id == tenant_id,
                    Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE]),
                    Invoice.balance > 0,
                    Invoice.deleted_at.is_(None),
                )
                .order_by(Invoice.issue_date.asc(), Invoice.created_at.asc())
                .limit(1)
            )
            invoice_result = await self.db.execute(invoice_query)
            oldest_invoice = invoice_result.scalars().first()

            if oldest_invoice:
                # Apply the credit to this invoice
                apply_amount = min(credit_note.amount, oldest_invoice.balance)

                credit_note.status = CreditNoteStatus.APPLIED
                credit_note.applied_to_invoice_id = oldest_invoice.id
                credit_note.applied_amount = apply_amount
                credit_note.applied_by = issued_by
                credit_note.applied_at = datetime.now(timezone.utc)
                credit_note.updated_at = datetime.now(timezone.utc)

                # Update invoice
                oldest_invoice.amount_paid = oldest_invoice.amount_paid + apply_amount
                oldest_invoice.balance = oldest_invoice.total_amount - oldest_invoice.amount_paid
                if oldest_invoice.balance <= 0:
                    oldest_invoice.status = InvoiceStatus.PAID
                elif oldest_invoice.amount_paid > 0:
                    oldest_invoice.status = InvoiceStatus.PARTIAL

                # Update student credit balance (subtract what was applied)
                student.credit_balance = student.credit_balance - apply_amount

                await self.db.flush()
                await self.db.refresh(credit_note)
                await self.db.refresh(oldest_invoice)
                applied_invoice = oldest_invoice

        return credit_note, applied_invoice

    async def apply_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteApply",
        applied_by: UUID,
    ) -> Optional[CreditNote]:
        """Apply a credit note to an invoice."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status != CreditNoteStatus.ISSUED:
            raise ValueError("Can only apply issued credit notes")

        # Get the invoice to apply to
        invoice_query = select(Invoice).where(
            Invoice.id == data.invoice_id,
            Invoice.tenant_id == tenant_id,
            Invoice.deleted_at.is_(None),
        )
        invoice_result = await self.db.execute(invoice_query)
        invoice = invoice_result.scalars().first()
        if not invoice:
            raise ValueError("Invoice not found")

        # Validate invoice belongs to same student
        if invoice.student_id != credit_note.student_id:
            raise ValueError("Invoice belongs to a different student")

        # Calculate apply amount
        apply_amount = min(data.amount or credit_note.amount, credit_note.amount, invoice.balance)

        credit_note.status = CreditNoteStatus.APPLIED
        credit_note.applied_to_invoice_id = data.invoice_id
        credit_note.applied_amount = apply_amount
        credit_note.applied_by = applied_by
        credit_note.applied_at = datetime.now(timezone.utc)
        credit_note.updated_at = datetime.now(timezone.utc)

        # Update invoice
        invoice.amount_paid = invoice.amount_paid + apply_amount
        invoice.balance = invoice.total_amount - invoice.amount_paid
        if invoice.balance <= 0:
            invoice.status = InvoiceStatus.PAID
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIAL

        # Update student credit balance
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        student_query = select(Student).where(
            Student.id == credit_note.student_id,
            Student.tenant_id == tenant_id,
        )
        student_result = await self.db.execute(student_query)
        student = student_result.scalars().first()
        if student:
            current_balance = student.credit_balance or Decimal("0.00")
            student.credit_balance = current_balance - apply_amount

        await self.db.flush()
        await self.db.refresh(credit_note)
        return credit_note

    async def refund_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteRefund",
        refunded_by: UUID,
    ) -> Optional[CreditNote]:
        """Refund a credit note to the student/guardian."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status != CreditNoteStatus.ISSUED:
            raise ValueError("Can only refund issued credit notes")

        credit_note.status = CreditNoteStatus.REFUNDED
        credit_note.refund_method = data.refund_method
        credit_note.refund_reference = data.refund_reference
        credit_note.refunded_by = refunded_by
        credit_note.refunded_at = datetime.now(timezone.utc)
        credit_note.updated_at = datetime.now(timezone.utc)

        # Update student credit balance
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        student_query = select(Student).where(
            Student.id == credit_note.student_id,
            Student.tenant_id == tenant_id,
        )
        student_result = await self.db.execute(student_query)
        student = student_result.scalars().first()
        if student:
            current_balance = student.credit_balance or Decimal("0.00")
            student.credit_balance = current_balance - credit_note.amount

        await self.db.flush()
        await self.db.refresh(credit_note)
        return credit_note

    async def cancel_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteCancel",
        cancelled_by: UUID,
    ) -> Optional[CreditNote]:
        """Cancel a credit note."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status in [CreditNoteStatus.APPLIED, CreditNoteStatus.REFUNDED]:
            raise ValueError("Cannot cancel applied or refunded credit notes")

        # If issued, need to reverse the credit balance
        if credit_note.status == CreditNoteStatus.ISSUED:
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            student_query = select(Student).where(
                Student.id == credit_note.student_id,
                Student.tenant_id == tenant_id,
            )
            student_result = await self.db.execute(student_query)
            student = student_result.scalars().first()
            if student:
                current_balance = student.credit_balance or Decimal("0.00")
                student.credit_balance = current_balance - credit_note.amount

        credit_note.status = CreditNoteStatus.CANCELLED
        credit_note.cancelled_by = cancelled_by
        credit_note.cancelled_at = datetime.now(timezone.utc)
        credit_note.cancel_reason = data.reason
        credit_note.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(credit_note)
        return credit_note

    async def delete_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        """Soft delete a draft credit note."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return False

        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Can only delete draft credit notes")

        credit_note.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def get_student_credit_balance(
        self,
        student_id: UUID,
        tenant_id: UUID,
    ) -> Decimal:
        """Get student's available credit balance."""
        student_query = select(Student).where(
            Student.id == student_id,
            Student.tenant_id == tenant_id,
        )
        result = await self.db.execute(student_query)
        student = result.scalars().first()
        if not student:
            return Decimal("0.00")
        return student.credit_balance or Decimal("0.00")

    async def get_student_credit_notes(
        self,
        student_id: UUID,
        tenant_id: UUID,
        include_cancelled: bool = False,
    ) -> Sequence[CreditNote]:
        """Get all credit notes for a student."""
        query = select(CreditNote).where(
            CreditNote.student_id == student_id,
            CreditNote.tenant_id == tenant_id,
            CreditNote.deleted_at.is_(None),
        )

        if not include_cancelled:
            query = query.where(CreditNote.status != CreditNoteStatus.CANCELLED)

        query = query.order_by(desc(CreditNote.created_at))
        result = await self.db.execute(query)
        return result.scalars().all()

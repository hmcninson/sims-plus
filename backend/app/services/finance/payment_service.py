"""
SIMS Plus - Payment Service

Business logic for payment recording and management.
"""

from datetime import datetime, UTC, date
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, desc, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.notification import NotificationCategory, NotificationType
from app.models.finance import (
    Invoice,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from app.models.student import Student
from app.services.finance._shared import FinanceServiceError
from app.services.finance.invoice_service import InvoiceService
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class PaymentService:
    """Service for managing payments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_receipt_number(self, tenant_id: UUID) -> str:
        """
        Generate unique receipt number using database sequence.

        Uses a PostgreSQL sequence to ensure thread-safe, race-condition-free
        generation of unique receipt numbers even under concurrent access.
        """
        year = datetime.now().year
        prefix = f"RCP-{year}-"

        # Use database sequence to get next value atomically
        result = await self.db.execute(text("SELECT nextval('receipt_number_seq')"))
        seq_num = result.scalar()

        return f"{prefix}{seq_num:05d}"

    async def record_payment(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        amount: Decimal,
        payment_method: str,
        invoice_id: Optional[UUID] = None,
        payment_date: Optional[datetime] = None,
        payer_name: Optional[str] = None,
        payer_phone: Optional[str] = None,
        payer_email: Optional[str] = None,
        notes: Optional[str] = None,
        momo_phone: Optional[str] = None,
        momo_transaction_id: Optional[str] = None,
        bank_name: Optional[str] = None,
        bank_reference: Optional[str] = None,
        cheque_number: Optional[str] = None,
        recorded_by: Optional[UUID] = None,
    ) -> Payment:
        """Record a payment."""
        receipt_number = await self._generate_receipt_number(tenant_id)

        # Determine MoMo provider from payment method
        momo_provider = None
        if payment_method == "momo_mtn":
            momo_provider = "MTN"
        elif payment_method == "momo_vodafone":
            momo_provider = "Vodafone"
        elif payment_method == "momo_airteltigo":
            momo_provider = "AirtelTigo"

        payment = Payment(
            tenant_id=tenant_id,
            school_id=school_id,
            receipt_number=receipt_number,
            invoice_id=invoice_id,
            student_id=student_id,
            amount=amount,
            payment_method=PaymentMethod(payment_method),
            payment_date=payment_date or datetime.now(UTC),
            payer_name=payer_name,
            payer_phone=payer_phone,
            payer_email=payer_email,
            notes=notes,
            momo_phone=momo_phone,
            momo_transaction_id=momo_transaction_id,
            momo_provider=momo_provider,
            bank_name=bank_name,
            bank_reference=bank_reference,
            cheque_number=cheque_number,
            status=PaymentStatus.COMPLETED,
            recorded_by=recorded_by,
        )
        self.db.add(payment)

        # Update invoice if linked
        if invoice_id:
            invoice_result = await self.db.execute(
                select(Invoice).where(
                    and_(
                        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                        Invoice.tenant_id == tenant_id,
                        Invoice.id == invoice_id,
                    )
                )
            )
            invoice = invoice_result.scalar_one_or_none()
            if invoice:
                invoice.amount_paid += amount
                InvoiceService(self.db)._update_invoice_status(invoice)

        await self.db.flush()
        await self.db.refresh(payment)

        # Best-effort notification for the user who recorded the payment
        if recorded_by:
            try:
                from app.services.notification import NotificationService
                notification_svc = NotificationService(self.db)

                # Build a more informative message when invoice is linked
                if invoice_id and invoice:
                    msg = f"Payment of {payment.amount:.2f} received for invoice #{invoice.invoice_number}."
                else:
                    msg = f"Payment of {payment.amount:.2f} recorded (receipt #{payment.receipt_number})."

                await notification_svc.create(
                    tenant_id=payment.tenant_id,
                    user_id=recorded_by,
                    title="Payment Recorded",
                    message=msg,
                    type=NotificationType.SUCCESS,
                    category=NotificationCategory.FINANCE,
                    reference_id=payment.id,
                    reference_type="payment",
                )
            except Exception:
                logger.warning("notification_create_failed", payment_id=str(payment.id), exc_info=True)

        return payment

    async def get_payment(self, tenant_id: UUID, payment_id: UUID) -> Optional[Payment]:
        """Get payment by ID with student, invoice, and user relationships."""
        query = select(Payment).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Payment.tenant_id == tenant_id,
                Payment.id == payment_id,
            )
        ).options(
            # Chain class_ loading for receipt endpoint (payment.student.class_.name)
            joinedload(Payment.student).selectinload(Student.class_),
            joinedload(Payment.invoice),
            joinedload(Payment.recorded_by_user),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_payments(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        invoice_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Payment], int]:
        """List payments with filters."""
        query = select(Payment).where(Payment.tenant_id == tenant_id)

        if school_id:
            query = query.where(Payment.school_id == school_id)
        if student_id:
            query = query.where(Payment.student_id == student_id)
        if invoice_id:
            query = query.where(Payment.invoice_id == invoice_id)
        # Filter by academic year and term through the invoice
        if academic_year_id or term_id:
            query = query.join(Invoice, Payment.invoice_id == Invoice.id, isouter=True)
            if academic_year_id:
                query = query.where(Invoice.academic_year_id == academic_year_id)
            if term_id:
                query = query.where(Invoice.term_id == term_id)
        if status:
            query = query.where(Payment.status == PaymentStatus(status))
        if payment_method:
            query = query.where(Payment.payment_method == PaymentMethod(payment_method))
        if start_date:
            query = query.where(func.date(Payment.payment_date) >= start_date)
        if end_date:
            query = query.where(func.date(Payment.payment_date) <= end_date)
        if search:
            # Search by receipt number, payer name, or student name
            # Escape ILIKE wildcards to prevent wildcard injection
            search_term = f"%{escape_ilike(search)}%"
            query = query.outerjoin(Payment.student).where(
                or_(
                    Payment.receipt_number.ilike(search_term),
                    Payment.payer_name.ilike(search_term),
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(Payment.student),
            joinedload(Payment.invoice),
        ).order_by(desc(Payment.payment_date))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def void_payment(
        self,
        tenant_id: UUID,
        payment_id: UUID,
        voided_by: UUID,
        reason: str,
    ) -> Optional[Payment]:
        """Void a payment."""
        payment = await self.get_payment(tenant_id, payment_id)
        if not payment:
            return None

        if payment.is_voided:
            raise FinanceServiceError(
                "Payment is already voided",
                code="already_voided",
            )

        payment.is_voided = True
        payment.voided_by = voided_by
        payment.voided_at = datetime.now(UTC)
        payment.void_reason = reason
        payment.status = PaymentStatus.CANCELLED

        # Update invoice if linked
        if payment.invoice_id:
            invoice_result = await self.db.execute(
                select(Invoice).where(
                    and_(
                        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                        Invoice.tenant_id == tenant_id,
                        Invoice.id == payment.invoice_id,
                    )
                )
            )
            invoice = invoice_result.scalar_one_or_none()
            if invoice:
                invoice.amount_paid -= payment.amount
                if invoice.amount_paid < 0:
                    invoice.amount_paid = Decimal("0.00")
                InvoiceService(self.db)._update_invoice_status(invoice)

        await self.db.flush()
        await self.db.refresh(payment)
        return payment

    async def get_student_payments(
        self,
        tenant_id: UUID,
        student_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> Sequence[Payment]:
        """Get all payments for a student."""
        query = select(Payment).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Payment.tenant_id == tenant_id,
                Payment.student_id == student_id,
                Payment.is_voided == False,
            )
        )

        if academic_year_id:
            query = query.join(Invoice).where(Invoice.academic_year_id == academic_year_id)

        query = query.order_by(desc(Payment.payment_date))
        result = await self.db.execute(query)
        return result.scalars().all()

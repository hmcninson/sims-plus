"""
SIMS Plus - Finance Dashboard Service

Business logic for finance dashboard statistics and analytics.
"""

from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.finance import (
    Invoice,
    InvoiceStatus,
    Payment,
    StudentScholarship,
    ScholarshipStatus,
)
from app.models.academic import Class
from app.models.student import Student


class FinanceDashboardService:
    """Service for finance dashboard and analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_stats(
        self,
        tenant_id: UUID,
        school_id: UUID,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> dict:
        """Get finance dashboard statistics."""
        # Build base filter
        invoice_filter = [
            Invoice.tenant_id == tenant_id,
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status != InvoiceStatus.CANCELLED,
        ]
        if academic_year_id:
            invoice_filter.append(Invoice.academic_year_id == academic_year_id)
        if term_id:
            invoice_filter.append(Invoice.term_id == term_id)

        # Get invoice stats
        invoice_stats = await self.db.execute(
            select(
                func.sum(Invoice.total_amount).label("expected"),
                func.sum(Invoice.amount_paid).label("collected"),
                func.count(Invoice.id).label("total"),
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.PAID, 1),
                        else_=0,
                    )
                ).label("paid"),
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.PARTIAL, 1),
                        else_=0,
                    )
                ).label("partial"),
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.OVERDUE, 1),
                        else_=0,
                    )
                ).label("overdue"),
            ).where(and_(*invoice_filter))
        )
        stats = invoice_stats.one()

        # Get payment count
        payment_filter = [
            Payment.tenant_id == tenant_id,
            Payment.school_id == school_id,
            Payment.is_voided == False,
        ]
        payment_count = await self.db.execute(
            select(func.count(Payment.id)).where(and_(*payment_filter))
        )

        # Get scholarship stats
        scholarship_filter = [
            StudentScholarship.tenant_id == tenant_id,
            StudentScholarship.status == ScholarshipStatus.ACTIVE,
        ]
        if academic_year_id:
            scholarship_filter.append(StudentScholarship.academic_year_id == academic_year_id)

        scholarship_stats = await self.db.execute(
            select(func.count(StudentScholarship.id)).where(and_(*scholarship_filter))
        )

        # Get total scholarship discount value from invoices
        scholarship_value_result = await self.db.execute(
            select(func.sum(Invoice.scholarship_discount)).where(and_(*invoice_filter))
        )
        total_scholarships_value = scholarship_value_result.scalar() or Decimal("0.00")

        return {
            "expected_revenue": stats.expected or Decimal("0.00"),
            "collected_revenue": stats.collected or Decimal("0.00"),
            "outstanding_balance": (stats.expected or Decimal("0.00")) - (stats.collected or Decimal("0.00")),
            "total_invoices": stats.total or 0,
            "paid_invoices": stats.paid or 0,
            "partial_invoices": stats.partial or 0,
            "overdue_invoices": stats.overdue or 0,
            "total_payments": payment_count.scalar() or 0,
            "total_scholarships_value": total_scholarships_value,
            "scholarship_recipients": scholarship_stats.scalar() or 0,
        }

    async def get_recent_payments(
        self,
        tenant_id: UUID,
        school_id: UUID,
        limit: int = 5,
    ) -> Sequence[Payment]:
        """Get recent payments for dashboard."""
        query = select(Payment).where(
            and_(
                Payment.tenant_id == tenant_id,
                Payment.school_id == school_id,
                Payment.is_voided == False,
            )
        ).options(
            joinedload(Payment.student),
        ).order_by(desc(Payment.payment_date)).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_outstanding_by_class(
        self,
        tenant_id: UUID,
        school_id: UUID,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Get outstanding balance grouped by class."""
        filter_conditions = [
            Invoice.tenant_id == tenant_id,
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status.in_([
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIAL,
                InvoiceStatus.OVERDUE,
            ]),
        ]
        if academic_year_id:
            filter_conditions.append(Invoice.academic_year_id == academic_year_id)
        if term_id:
            filter_conditions.append(Invoice.term_id == term_id)

        query = (
            select(
                Class.id,
                Class.name,
                func.count(func.distinct(Invoice.student_id)).label("student_count"),
                func.sum(Invoice.total_amount - Invoice.amount_paid).label("total_outstanding"),
            )
            .select_from(Invoice)
            .join(Student, Invoice.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .where(and_(*filter_conditions))
            .group_by(Class.id, Class.name)
            .order_by(desc("total_outstanding"))
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "class_id": row.id,
                "class_name": row.name,
                "student_count": row.student_count,
                "total_outstanding": row.total_outstanding or Decimal("0.00"),
            }
            for row in rows
        ]

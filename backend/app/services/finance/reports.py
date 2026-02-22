"""
SIMS Plus - Finance Report Service

Provides aggregated data for financial report generation including
fee collection breakdowns, outstanding balances, and payment summaries.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    FeeItem,
    FeeType,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Payment,
    PaymentStatus,
)
from app.models.student import Student
from app.models.academic import Class

logger = structlog.get_logger()


class FinanceReportError(Exception):
    """Finance report operation failed."""

    def __init__(self, message: str, code: str = "finance_report_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class FinanceReportService:
    """Service for generating financial report data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_fee_collection_data(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Get fee collection data grouped by fee type.

        Returns payment totals broken down by fee type for the given filters.
        The join path is: Payment -> Invoice -> InvoiceItem -> FeeItem -> FeeType.
        """
        # Defense-in-depth: always scope by tenant_id
        stmt = (
            select(
                FeeType.name.label("fee_type_name"),
                func.count(Payment.id).label("payment_count"),
                func.coalesce(func.sum(Payment.amount), Decimal("0")).label("total_collected"),
            )
            .select_from(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .join(FeeItem, InvoiceItem.fee_item_id == FeeItem.id)
            .join(FeeType, FeeItem.fee_type_id == FeeType.id)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status == PaymentStatus.COMPLETED,
                Invoice.academic_year_id == academic_year_id,
            )
        )

        if term_id:
            stmt = stmt.where(Invoice.term_id == term_id)
        if class_id:
            stmt = stmt.join(Student, Invoice.student_id == Student.id).where(
                Student.class_id == class_id
            )
        if date_from:
            stmt = stmt.where(Payment.payment_date >= date_from)
        if date_to:
            stmt = stmt.where(Payment.payment_date <= date_to)

        stmt = stmt.group_by(FeeType.name).order_by(FeeType.name)

        result = await self.db.execute(stmt)
        rows = result.all()

        fee_type_breakdown = []
        grand_total = Decimal("0")
        for row in rows:
            amount = row.total_collected or Decimal("0")
            fee_type_breakdown.append({
                "fee_type": row.fee_type_name,
                "payment_count": row.payment_count,
                "total_collected": float(amount),
            })
            grand_total += amount

        return {
            "fee_type_breakdown": fee_type_breakdown,
            "grand_total": float(grand_total),
            "total_payments": sum(r["payment_count"] for r in fee_type_breakdown),
        }

    async def get_outstanding_fees_data(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Get students with outstanding balances.

        Returns list of students with unpaid invoice balances,
        filtering to ISSUED and OVERDUE invoices (i.e., actively owed).
        """
        # Defense-in-depth: always scope by tenant_id
        stmt = (
            select(
                Student.id.label("student_id"),
                Student.student_id.label("student_number"),
                Student.first_name,
                Student.last_name,
                Class.name.label("class_name"),
                func.coalesce(func.sum(Invoice.total_amount), Decimal("0")).label("total_invoiced"),
                func.coalesce(func.sum(Invoice.amount_paid), Decimal("0")).label("total_paid"),
                (
                    func.coalesce(func.sum(Invoice.total_amount), Decimal("0"))
                    - func.coalesce(func.sum(Invoice.amount_paid), Decimal("0"))
                ).label("balance_due"),
            )
            .select_from(Invoice)
            .join(Student, Invoice.student_id == Student.id)
            .outerjoin(Class, Student.class_id == Class.id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.academic_year_id == academic_year_id,
                Invoice.status.in_([
                    InvoiceStatus.ISSUED,
                    InvoiceStatus.OVERDUE,
                ]),
                Invoice.deleted_at.is_(None),
            )
        )

        if term_id:
            stmt = stmt.where(Invoice.term_id == term_id)
        if class_id:
            stmt = stmt.where(Student.class_id == class_id)

        stmt = stmt.group_by(
            Student.id, Student.student_id, Student.first_name,
            Student.last_name, Class.name,
        ).having(
            # Only include students who actually owe money
            func.coalesce(func.sum(Invoice.total_amount), Decimal("0"))
            - func.coalesce(func.sum(Invoice.amount_paid), Decimal("0"))
            > 0
        ).order_by(Student.last_name, Student.first_name)

        result = await self.db.execute(stmt)
        rows = result.all()

        students = []
        total_outstanding = Decimal("0")
        for row in rows:
            balance = row.balance_due or Decimal("0")
            students.append({
                "student_id": str(row.student_id),
                "student_number": row.student_number,
                "name": f"{row.first_name} {row.last_name}",
                "class_name": row.class_name or "N/A",
                "total_invoiced": float(row.total_invoiced or 0),
                "total_paid": float(row.total_paid or 0),
                "balance_due": float(balance),
            })
            total_outstanding += balance

        return {
            "students": students,
            "total_students": len(students),
            "total_outstanding": float(total_outstanding),
        }

    async def get_payment_summary_data(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Get payment summary broken down by payment method.

        Useful for understanding which payment channels are most used
        and reconciling cash vs. mobile money vs. bank transfers.
        """
        # Defense-in-depth: always scope by tenant_id
        stmt = (
            select(
                Payment.payment_method,
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), Decimal("0")).label("total"),
            )
            .select_from(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status == PaymentStatus.COMPLETED,
                Invoice.academic_year_id == academic_year_id,
            )
        )

        if term_id:
            stmt = stmt.where(Invoice.term_id == term_id)
        if date_from:
            stmt = stmt.where(Payment.payment_date >= date_from)
        if date_to:
            stmt = stmt.where(Payment.payment_date <= date_to)

        stmt = stmt.group_by(Payment.payment_method).order_by(Payment.payment_method)

        result = await self.db.execute(stmt)
        rows = result.all()

        method_breakdown = []
        grand_total = Decimal("0")
        for row in rows:
            amount = row.total or Decimal("0")
            method_breakdown.append({
                "payment_method": row.payment_method.value if row.payment_method else "unknown",
                "count": row.count,
                "total": float(amount),
            })
            grand_total += amount

        return {
            "method_breakdown": method_breakdown,
            "grand_total": float(grand_total),
            "total_payments": sum(r["count"] for r in method_breakdown),
        }

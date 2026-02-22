"""
SIMS Plus - Dashboard Service

Aggregates analytics data from students, staff, attendance, finance, and exams
for the school dashboard overview.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student, StudentStatus, Gender
from app.models.staff import Staff, StaffStatus
from app.models.academic import AcademicYear, AcademicYearStatus, Class, Term
from app.models.attendance import StudentAttendance, AttendanceStatus
from app.models.finance import Invoice, InvoiceStatus, Payment, PaymentStatus
from app.models.exam import ExamScore, ExamSubject

logger = structlog.get_logger()


class DashboardServiceError(Exception):
    """Base exception for dashboard service errors."""

    def __init__(self, message: str, code: str = "dashboard_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class DashboardService:
    """Service for aggregating dashboard analytics data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview_stats(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Get overview statistics for the dashboard.

        Aggregates:
        - Active student count
        - Active staff count
        - Active class count
        - Today's attendance summary (present/absent/rate)
        - Finance summary for the current term (billed/collected/outstanding)
        """
        # --- Student count (active, not soft-deleted) ---
        student_count_q = select(func.count(Student.id)).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Student.tenant_id == tenant_id,
                Student.status == StudentStatus.ACTIVE,
                Student.deleted_at.is_(None),
            )
        )
        if school_id:
            student_count_q = student_count_q.where(Student.school_id == school_id)
        total_students = (await self.db.execute(student_count_q)).scalar() or 0

        # --- Staff count (active, not soft-deleted) ---
        staff_count_q = select(func.count(Staff.id)).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Staff.tenant_id == tenant_id,
                Staff.status == StaffStatus.ACTIVE,
                Staff.deleted_at.is_(None),
            )
        )
        if school_id:
            staff_count_q = staff_count_q.where(Staff.school_id == school_id)
        total_staff = (await self.db.execute(staff_count_q)).scalar() or 0

        # --- Active class count (not soft-deleted, is_active) ---
        class_count_q = select(func.count(Class.id)).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Class.tenant_id == tenant_id,
                Class.is_active.is_(True),
                Class.deleted_at.is_(None),
            )
        )
        if school_id:
            class_count_q = class_count_q.where(Class.school_id == school_id)
        total_classes = (await self.db.execute(class_count_q)).scalar() or 0

        # --- Today's attendance ---
        today = date.today()
        attendance_q = select(
            func.count(StudentAttendance.id).label("total"),
            func.count(
                case(
                    (StudentAttendance.status == AttendanceStatus.PRESENT, 1),
                    (StudentAttendance.status == AttendanceStatus.LATE, 1),
                )
            ).label("present"),
            func.count(
                case(
                    (StudentAttendance.status == AttendanceStatus.ABSENT, 1),
                )
            ).label("absent"),
        ).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                StudentAttendance.tenant_id == tenant_id,
                StudentAttendance.date == today,
                StudentAttendance.deleted_at.is_(None),
            )
        )
        att_result = (await self.db.execute(attendance_q)).one_or_none()
        att_total = att_result.total if att_result else 0
        att_present = att_result.present if att_result else 0
        att_absent = att_result.absent if att_result else 0
        att_rate = round((att_present / att_total * 100), 1) if att_total > 0 else 0.0

        # --- Finance summary (current academic year + current term) ---
        total_billed = Decimal("0.00")
        total_collected = Decimal("0.00")

        # Find the active academic year and its current term
        active_year_q = select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.is_current.is_(True),
                AcademicYear.deleted_at.is_(None),
            )
        )
        active_year = (await self.db.execute(active_year_q)).scalar_one_or_none()

        if active_year:
            # Find current term within the active year
            current_term_q = select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.academic_year_id == active_year.id,
                    Term.is_current.is_(True),
                    Term.deleted_at.is_(None),
                )
            )
            current_term = (await self.db.execute(current_term_q)).scalar_one_or_none()

            if current_term:
                # Sum total billed (non-cancelled, non-deleted invoices for this term)
                billed_q = select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                    and_(
                        Invoice.tenant_id == tenant_id,
                        Invoice.academic_year_id == active_year.id,
                        Invoice.term_id == current_term.id,
                        Invoice.status != InvoiceStatus.CANCELLED,
                        Invoice.deleted_at.is_(None),
                    )
                )
                total_billed = (await self.db.execute(billed_q)).scalar() or Decimal("0.00")

                # Sum total collected (completed payments for this term's invoices)
                collected_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    and_(
                        Payment.tenant_id == tenant_id,
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.is_voided.is_(False),
                        Payment.invoice_id.in_(
                            select(Invoice.id).where(
                                and_(
                                    Invoice.tenant_id == tenant_id,
                                    Invoice.academic_year_id == active_year.id,
                                    Invoice.term_id == current_term.id,
                                    Invoice.deleted_at.is_(None),
                                )
                            )
                        ),
                    )
                )
                total_collected = (await self.db.execute(collected_q)).scalar() or Decimal("0.00")

        outstanding = total_billed - total_collected
        collection_rate = (
            round(float(total_collected / total_billed * 100), 1)
            if total_billed > 0
            else 0.0
        )

        return {
            "total_students": total_students,
            "total_staff": total_staff,
            "total_classes": total_classes,
            "attendance_today": {
                "present": att_present,
                "absent": att_absent,
                "rate": att_rate,
            },
            "finance": {
                "total_billed": float(total_billed),
                "total_collected": float(total_collected),
                "collection_rate": collection_rate,
                "outstanding": float(outstanding),
            },
        }

    async def get_attendance_trend(
        self,
        tenant_id: UUID,
        days: int = 30,
    ) -> list[dict]:
        """
        Get daily attendance rates for the last N days.

        Returns a list of {date, present, absent, late, rate} dicts
        ordered by date ascending.
        """
        start_date = date.today() - timedelta(days=days)

        query = (
            select(
                StudentAttendance.date,
                func.count(
                    case(
                        (StudentAttendance.status == AttendanceStatus.PRESENT, 1),
                    )
                ).label("present"),
                func.count(
                    case(
                        (StudentAttendance.status == AttendanceStatus.ABSENT, 1),
                    )
                ).label("absent"),
                func.count(
                    case(
                        (StudentAttendance.status == AttendanceStatus.LATE, 1),
                    )
                ).label("late"),
                func.count(StudentAttendance.id).label("total"),
            )
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.date >= start_date,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .group_by(StudentAttendance.date)
            .order_by(StudentAttendance.date)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "date": str(row.date),
                "present": row.present,
                "absent": row.absent,
                "late": row.late,
                "rate": round((row.present + row.late) / row.total * 100, 1)
                if row.total > 0
                else 0.0,
            }
            for row in rows
        ]

    async def get_fee_collection_trend(
        self,
        tenant_id: UUID,
        months: int = 6,
    ) -> list[dict]:
        """
        Get monthly billed vs collected amounts using date_trunc.

        Returns a list of {month, billed, collected} dicts ordered chronologically.
        """
        start_date = date.today() - timedelta(days=months * 31)

        # Monthly billed amounts (from invoice created_at)
        billed_month = func.date_trunc("month", Invoice.created_at).label("month")
        billed_q = (
            select(
                billed_month,
                func.coalesce(func.sum(Invoice.total_amount), 0).label("billed"),
            )
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Invoice.tenant_id == tenant_id,
                    Invoice.status != InvoiceStatus.CANCELLED,
                    Invoice.deleted_at.is_(None),
                    Invoice.created_at >= start_date,
                )
            )
            .group_by(billed_month)
            .order_by(billed_month)
        )
        billed_result = await self.db.execute(billed_q)
        billed_rows = {row.month: float(row.billed) for row in billed_result.all()}

        # Monthly collected amounts (from payment payment_date)
        collected_month = func.date_trunc("month", Payment.payment_date).label("month")
        collected_q = (
            select(
                collected_month,
                func.coalesce(func.sum(Payment.amount), 0).label("collected"),
            )
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Payment.tenant_id == tenant_id,
                    Payment.status == PaymentStatus.COMPLETED,
                    Payment.is_voided.is_(False),
                    Payment.payment_date >= start_date,
                )
            )
            .group_by(collected_month)
            .order_by(collected_month)
        )
        collected_result = await self.db.execute(collected_q)
        collected_rows = {row.month: float(row.collected) for row in collected_result.all()}

        # Merge both result sets into a unified timeline
        all_months = sorted(set(billed_rows.keys()) | set(collected_rows.keys()))

        return [
            {
                "month": month.strftime("%Y-%m") if month else "",
                "billed": billed_rows.get(month, 0.0),
                "collected": collected_rows.get(month, 0.0),
            }
            for month in all_months
        ]

    async def get_class_performance(
        self,
        tenant_id: UUID,
        term_id: UUID,
    ) -> list[dict]:
        """
        Get average, highest, and lowest exam scores per class for a given term.

        Only includes non-absent scores from exams in the specified term.
        """
        # ExamScore -> ExamSubject -> Exam -> term_id
        # ExamSubject has class_id which links to Class
        query = (
            select(
                Class.name.label("class_name"),
                func.round(func.avg(ExamScore.score), 1).label("average"),
                func.max(ExamScore.score).label("highest"),
                func.min(ExamScore.score).label("lowest"),
            )
            .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
            .join(Class, ExamSubject.class_id == Class.id)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ExamScore.tenant_id == tenant_id,
                    ExamSubject.tenant_id == tenant_id,
                    Class.tenant_id == tenant_id,
                    ExamScore.is_absent.is_(False),
                    ExamScore.score.isnot(None),
                    ExamScore.deleted_at.is_(None),
                    Class.deleted_at.is_(None),
                    # Filter by term: ExamSubject -> Exam -> term_id
                    ExamSubject.exam_id.in_(
                        select(ExamSubject.exam_id)
                        .join(ExamSubject.exam)
                        .where(ExamSubject.exam.has(term_id=term_id))
                        .correlate(None)
                    ),
                )
            )
            .group_by(Class.name, Class.sequence)
            .order_by(Class.sequence)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "class_name": row.class_name,
                "average": float(row.average) if row.average else 0.0,
                "highest": float(row.highest) if row.highest else 0.0,
                "lowest": float(row.lowest) if row.lowest else 0.0,
            }
            for row in rows
        ]

    async def get_gender_distribution(
        self,
        tenant_id: UUID,
    ) -> dict:
        """
        Count active students by gender.

        Returns {male: int, female: int}.
        """
        query = (
            select(
                func.count(
                    case(
                        (Student.gender == Gender.MALE, 1),
                    )
                ).label("male"),
                func.count(
                    case(
                        (Student.gender == Gender.FEMALE, 1),
                    )
                ).label("female"),
            )
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Student.tenant_id == tenant_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
        )

        result = (await self.db.execute(query)).one_or_none()

        return {
            "male": result.male if result else 0,
            "female": result.female if result else 0,
        }

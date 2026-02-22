"""
SIMS Plus - Parent Attendance Service

Monthly attendance views and trend data for parents.
All methods enforce parent-child access verification before returning any data.
"""

from datetime import date
from uuid import UUID
import calendar

import structlog
from sqlalchemy import case, select, and_, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.student import Student

from app.services.parent._shared import ParentServiceError
from app.services.parent.parent_service import ParentService

logger = structlog.get_logger()


class ParentAttendanceService:
    """
    Service for parent access to attendance data.

    Provides monthly attendance summaries with daily breakdowns
    and multi-month attendance rate trends for charting.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._parent = ParentService(db)

    async def get_child_attendance(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
        month: str,
    ) -> dict:
        """
        Get monthly attendance summary with daily breakdown.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)
            month: Month in YYYY-MM format (e.g., "2026-02")

        Returns:
            Dict matching AttendanceSummary schema

        Raises:
            ParentServiceError: If access denied or invalid month format
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        # Parse the month string
        try:
            year, month_num = month.split("-")
            year_int = int(year)
            month_int = int(month_num)
            if not (1 <= month_int <= 12):
                raise ValueError
        except (ValueError, AttributeError):
            raise ParentServiceError(
                "Invalid month format. Use YYYY-MM (e.g., 2026-02)",
                code="invalid_month",
            )

        # Calculate date range for the month
        _, last_day = calendar.monthrange(year_int, month_int)
        start_date = date(year_int, month_int, 1)
        end_date = date(year_int, month_int, last_day)

        # Fetch student for response summary (with class/section for display)
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

        # Fetch all attendance records for this student in the month
        attendance_result = await self.db.execute(
            select(StudentAttendance)
            .where(
                and_(
                    StudentAttendance.student_id == student_id,
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.date >= start_date,
                    StudentAttendance.date <= end_date,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .order_by(StudentAttendance.date)
        )
        records = attendance_result.scalars().all()

        # Count by status
        present_count = 0
        absent_count = 0
        late_count = 0
        excused_count = 0

        daily = []
        for record in records:
            status = record.status
            if status == AttendanceStatus.PRESENT:
                present_count += 1
            elif status == AttendanceStatus.ABSENT:
                absent_count += 1
            elif status == AttendanceStatus.LATE:
                late_count += 1
            elif status in (AttendanceStatus.EXCUSED, AttendanceStatus.SICK):
                excused_count += 1

            daily.append({
                "date": record.date,
                "status": status.value,
                "note": record.remarks,
            })

        total_school_days = len(records)
        # Attendance rate: present + late count as "attended"
        rate = 0.0
        if total_school_days > 0:
            rate = round(
                ((present_count + late_count) / total_school_days) * 100, 2
            )

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
            "month": month,
            "total_school_days": total_school_days,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "excused": excused_count,
            "rate": rate,
            "daily": daily,
        }

    async def get_child_attendance_trend(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
        months: int = 6,
    ) -> list[dict]:
        """
        Get monthly attendance rate trend for charting.

        Returns up to N months of data, most recent first, going backwards
        from the current date.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)
            months: Number of months to look back (default 6, max 12)

        Returns:
            List of dicts matching AttendanceTrend schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        # Clamp months to reasonable range
        months = min(max(months, 1), 12)

        # Calculate start date (first day of the month N months ago)
        today = date.today()
        # Go back N months from the current month
        start_year = today.year
        start_month = today.month - months + 1
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start_date = date(start_year, start_month, 1)

        # Aggregate attendance by month using extract + conditional count
        # Single query replaces the previous N+1 pattern (1 query per month)
        result = await self.db.execute(
            select(
                extract("year", StudentAttendance.date).label("yr"),
                extract("month", StudentAttendance.date).label("mo"),
                func.count(StudentAttendance.id).label("total_days"),
                func.sum(
                    case(
                        (
                            StudentAttendance.status.in_([
                                AttendanceStatus.PRESENT,
                                AttendanceStatus.LATE,
                            ]),
                            1,
                        ),
                        else_=0,
                    )
                ).label("present_count_raw"),
            )
            .where(
                and_(
                    StudentAttendance.student_id == student_id,
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.date >= start_date,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .group_by(
                extract("year", StudentAttendance.date),
                extract("month", StudentAttendance.date),
            )
            .order_by(
                extract("year", StudentAttendance.date),
                extract("month", StudentAttendance.date),
            )
        )
        rows = result.all()

        trend = []
        for row in rows:
            yr = int(row.yr)
            mo = int(row.mo)
            month_label = f"{yr:04d}-{mo:02d}"
            total_days = row.total_days or 0
            present_count = row.present_count_raw or 0

            rate = 0.0
            if total_days > 0:
                rate = round((present_count / total_days) * 100, 2)

            trend.append({
                "month": month_label,
                "rate": rate,
                "present": present_count,
                "total_days": total_days,
            })

        return trend

"""
SIMS Plus - Teacher Attendance Service

Provides attendance summary statistics for the teacher portal.
Teachers can view attendance data for their assigned classes.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, ClassSection
from app.models.attendance import AttendanceStatus, StudentAttendance
from app.models.student import Student, StudentStatus

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherAttendanceService:
    """
    Attendance summary operations for the teacher portal.

    Provides per-student and per-class attendance statistics
    for classes the teacher is assigned to.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_class_attendance_summary(
        self,
        tenant_id: UUID,
        class_id: UUID,
        section_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict:
        """
        Build attendance summary for a class within a date range.

        Returns per-student attendance counts and overall class statistics.
        Defaults to current month if no date range is provided.
        """
        today = date.today()
        if not date_from:
            date_from = today.replace(day=1)
        if not date_to:
            date_to = today

        # Get students in this class/section
        student_query = (
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
        )
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)
        else:
            student_query = student_query.join(
                ClassSection, Student.section_id == ClassSection.id
            ).where(ClassSection.class_id == class_id)

        student_query = student_query.order_by(Student.last_name, Student.first_name)
        students = (await self.db.execute(student_query)).scalars().all()

        if not students:
            return {
                "class_id": class_id,
                "class_name": "",
                "section_id": section_id,
                "section_name": None,
                "total_students": 0,
                "present_today": 0,
                "absent_today": 0,
                "late_today": 0,
                "attendance_percentage": None,
                "students": [],
            }

        student_ids = [s.id for s in students]

        # Attendance records grouped by student for the date range
        attendance_result = await self.db.execute(
            select(
                StudentAttendance.student_id,
                func.count(StudentAttendance.id).label("total"),
                func.count(StudentAttendance.id).filter(
                    StudentAttendance.status == AttendanceStatus.PRESENT
                ).label("present"),
                func.count(StudentAttendance.id).filter(
                    StudentAttendance.status == AttendanceStatus.ABSENT
                ).label("absent"),
                func.count(StudentAttendance.id).filter(
                    StudentAttendance.status == AttendanceStatus.LATE
                ).label("late"),
            )
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.student_id.in_(student_ids),
                    StudentAttendance.date >= date_from,
                    StudentAttendance.date <= date_to,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .group_by(StudentAttendance.student_id)
        )
        attendance_data = {
            row.student_id: {
                "total": row.total,
                "present": row.present,
                "absent": row.absent,
                "late": row.late,
            }
            for row in attendance_result.all()
        }

        # Today's attendance counts
        today_result = await self.db.execute(
            select(
                StudentAttendance.status,
                func.count(StudentAttendance.id),
            )
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.student_id.in_(student_ids),
                    StudentAttendance.date == today,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .group_by(StudentAttendance.status)
        )
        today_counts: dict[str, int] = {}
        for row in today_result.all():
            today_counts[row[0].value if hasattr(row[0], "value") else str(row[0])] = row[1]

        # Build per-student summaries
        student_summaries = []
        total_present = 0
        total_total = 0

        for s in students:
            data = attendance_data.get(s.id, {"total": 0, "present": 0, "absent": 0, "late": 0})
            pct = None
            if data["total"] > 0:
                pct = Decimal(str(data["present"] / data["total"] * 100)).quantize(Decimal("0.01"))
            total_present += data["present"]
            total_total += data["total"]

            student_summaries.append({
                "student_id": s.id,
                "student_name": f"{s.first_name} {s.last_name}",
                "days_present": data["present"],
                "days_absent": data["absent"],
                "days_late": data["late"],
                "total_days": data["total"],
                "attendance_percentage": pct,
            })

        overall_pct = None
        if total_total > 0:
            overall_pct = Decimal(str(total_present / total_total * 100)).quantize(Decimal("0.01"))

        # Get class and section names
        cls = (await self.db.execute(
            select(Class).where(and_(Class.id == class_id, Class.tenant_id == tenant_id))
        )).scalar_one_or_none()

        sec_name = None
        if section_id:
            sec = (await self.db.execute(
                select(ClassSection).where(
                    and_(ClassSection.id == section_id, ClassSection.tenant_id == tenant_id)
                )
            )).scalar_one_or_none()
            sec_name = sec.name if sec else None

        return {
            "class_id": class_id,
            "class_name": cls.name if cls else "",
            "section_id": section_id,
            "section_name": sec_name,
            "total_students": len(students),
            "present_today": today_counts.get("present", 0),
            "absent_today": today_counts.get("absent", 0),
            "late_today": today_counts.get("late", 0),
            "attendance_percentage": overall_pct,
            "students": student_summaries,
        }

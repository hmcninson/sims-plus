"""
SIMS Plus - Attendance Service

Business logic for student and staff attendance management.
"""

from datetime import date, time, datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import case, select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import (
    StudentAttendance,
    StaffAttendance,
    AttendanceStatus,
)
from app.models.notification import NotificationCategory, NotificationType
from app.models.student import Student

logger = structlog.get_logger()


class AttendanceServiceError(Exception):
    """Base exception for attendance service errors."""

    def __init__(self, message: str, code: str = "attendance_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class AttendanceService:
    """Service for managing student and staff attendance."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Student Attendance Methods
    # =========================

    async def mark_student_attendance(
        self,
        tenant_id: UUID,
        student_id: UUID,
        section_id: UUID,
        attendance_date: date,
        status: str,
        term_id: Optional[UUID] = None,
        check_in_time: Optional[time] = None,
        check_out_time: Optional[time] = None,
        remarks: Optional[str] = None,
        excuse_reason: Optional[str] = None,
        marked_by: Optional[UUID] = None,
    ) -> StudentAttendance:
        """Mark or update attendance for a single student."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        # Also exclude soft-deleted records so we don't resurrect them
        existing = await self.db.execute(
            select(StudentAttendance).where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.student_id == student_id,
                    StudentAttendance.date == attendance_date,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
        )
        attendance = existing.scalar_one_or_none()

        if attendance:
            # Update existing record
            attendance.status = AttendanceStatus(status)
            attendance.section_id = section_id
            attendance.term_id = term_id
            attendance.check_in_time = check_in_time
            attendance.check_out_time = check_out_time
            attendance.remarks = remarks
            attendance.excuse_reason = excuse_reason
            attendance.marked_by = marked_by
            attendance.updated_at = datetime.now(UTC)
        else:
            # Create new record
            attendance = StudentAttendance(
                tenant_id=tenant_id,
                student_id=student_id,
                section_id=section_id,
                date=attendance_date,
                status=AttendanceStatus(status),
                term_id=term_id,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                remarks=remarks,
                excuse_reason=excuse_reason,
                marked_by=marked_by,
            )
            self.db.add(attendance)

        await self.db.flush()

        # Best-effort notification when a student is marked absent
        if AttendanceStatus(status) == AttendanceStatus.ABSENT and marked_by:
            try:
                from app.services.notification import NotificationService
                notification_svc = NotificationService(self.db)
                await notification_svc.create(
                    tenant_id=tenant_id,
                    user_id=marked_by,
                    title="Absence Recorded",
                    message=f"Student marked absent on {attendance_date.isoformat()}.",
                    type=NotificationType.WARNING,
                    category=NotificationCategory.ATTENDANCE,
                    reference_id=attendance.id,
                    reference_type="attendance",
                )
            except Exception:
                logger.warning("notification_create_failed", attendance_id=str(attendance.id), exc_info=True)

        # Re-query with eager loading so endpoint can safely access relationships
        result = await self.db.execute(
            select(StudentAttendance)
            .where(StudentAttendance.id == attendance.id)
            .options(
                selectinload(StudentAttendance.student),
                selectinload(StudentAttendance.section),
            )
        )
        return result.scalar_one()

    async def bulk_mark_student_attendance(
        self,
        tenant_id: UUID,
        section_id: UUID,
        attendance_date: date,
        attendance_records: list[dict],
        term_id: Optional[UUID] = None,
        marked_by: Optional[UUID] = None,
    ) -> dict:
        """Bulk mark attendance for multiple students in a section."""
        created = 0
        updated = 0
        failed = 0
        errors = []
        absent_count = 0

        for record in attendance_records:
            try:
                student_id = record.get("student_id")
                status = record.get("status", "present")

                if not student_id:
                    failed += 1
                    errors.append({"error": "student_id is required"})
                    continue

                # Defense-in-depth: always filter by tenant_id and exclude soft-deleted
                existing = await self.db.execute(
                    select(StudentAttendance).where(
                        and_(
                            StudentAttendance.tenant_id == tenant_id,
                            StudentAttendance.student_id == UUID(student_id) if isinstance(student_id, str) else student_id,
                            StudentAttendance.date == attendance_date,
                            StudentAttendance.deleted_at.is_(None),
                        )
                    )
                )
                attendance = existing.scalar_one_or_none()

                if attendance:
                    attendance.status = AttendanceStatus(status)
                    attendance.section_id = section_id
                    attendance.term_id = term_id
                    attendance.check_in_time = record.get("check_in_time")
                    attendance.remarks = record.get("remarks")
                    attendance.excuse_reason = record.get("excuse_reason")
                    attendance.marked_by = marked_by
                    attendance.updated_at = datetime.now(UTC)
                    updated += 1
                else:
                    attendance = StudentAttendance(
                        tenant_id=tenant_id,
                        student_id=UUID(student_id) if isinstance(student_id, str) else student_id,
                        section_id=section_id,
                        date=attendance_date,
                        status=AttendanceStatus(status),
                        term_id=term_id,
                        check_in_time=record.get("check_in_time"),
                        remarks=record.get("remarks"),
                        excuse_reason=record.get("excuse_reason"),
                        marked_by=marked_by,
                    )
                    self.db.add(attendance)
                    created += 1

                # Track absent students for summary notification
                if AttendanceStatus(status) == AttendanceStatus.ABSENT:
                    absent_count += 1

            except Exception as e:
                failed += 1
                errors.append({
                    "student_id": record.get("student_id"),
                    "error": str(e),
                })

        await self.db.flush()

        # Best-effort summary notification when absences were recorded in bulk
        if absent_count > 0 and marked_by:
            try:
                from app.services.notification import NotificationService
                notification_svc = NotificationService(self.db)
                student_word = "student" if absent_count == 1 else "students"
                await notification_svc.create(
                    tenant_id=tenant_id,
                    user_id=marked_by,
                    title="Absences Recorded",
                    message=f"{absent_count} {student_word} marked absent on {attendance_date.isoformat()}.",
                    type=NotificationType.WARNING,
                    category=NotificationCategory.ATTENDANCE,
                    reference_type="attendance",
                )
            except Exception:
                logger.warning("notification_create_failed", exc_info=True)

        return {
            "created": created,
            "updated": updated,
            "failed": failed,
            "errors": errors,
        }

    async def get_student_attendance(
        self,
        tenant_id: UUID,
        student_id: UUID,
        attendance_date: date,
    ) -> Optional[StudentAttendance]:
        """Get attendance record for a specific student and date."""
        result = await self.db.execute(
            select(StudentAttendance)
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.student_id == student_id,
                    StudentAttendance.date == attendance_date,
                    # Exclude soft-deleted records
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(StudentAttendance.student),
                selectinload(StudentAttendance.section),
            )
        )
        return result.scalar_one_or_none()

    async def get_section_attendance(
        self,
        tenant_id: UUID,
        section_id: UUID,
        attendance_date: date,
    ) -> Sequence[StudentAttendance]:
        """Get all attendance records for a section on a specific date."""
        result = await self.db.execute(
            select(StudentAttendance)
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.section_id == section_id,
                    StudentAttendance.date == attendance_date,
                    # Exclude soft-deleted records
                    StudentAttendance.deleted_at.is_(None),
                )
            )
            .options(selectinload(StudentAttendance.student))
            .order_by(StudentAttendance.student_id)
        )
        return result.scalars().all()

    async def get_students_for_attendance(
        self,
        tenant_id: UUID,
        section_id: UUID,
        attendance_date: date,
    ) -> list[dict]:
        """
        Get all students in a section with their attendance status for a date.
        Returns students even if they don't have attendance marked.
        """
        # Get all active students in the section (soft delete filter on Student)
        students_result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.section_id == section_id,
                    Student.deleted_at.is_(None),
                )
            )
            .order_by(Student.last_name, Student.first_name)
        )
        students = students_result.scalars().all()

        # Get existing attendance records, excluding soft-deleted ones
        attendance_result = await self.db.execute(
            select(StudentAttendance)
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.section_id == section_id,
                    StudentAttendance.date == attendance_date,
                    StudentAttendance.deleted_at.is_(None),
                )
            )
        )
        attendance_map = {a.student_id: a for a in attendance_result.scalars().all()}

        # Combine students with their attendance
        result = []
        for student in students:
            attendance = attendance_map.get(student.id)
            result.append({
                "student_id": student.id,
                "student_number": student.student_id,
                "first_name": student.first_name,
                "middle_name": student.middle_name,
                "last_name": student.last_name,
                "gender": student.gender.value,
                "photo_url": student.photo_url,
                "attendance_id": attendance.id if attendance else None,
                "status": attendance.status.value if attendance else None,
                "check_in_time": attendance.check_in_time if attendance else None,
                "remarks": attendance.remarks if attendance else None,
            })

        return result

    async def list_student_attendance(
        self,
        tenant_id: UUID,
        student_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[StudentAttendance], int]:
        """List student attendance records with filters."""
        # Defense-in-depth: always scope by tenant_id and exclude soft-deleted
        conditions = [
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.deleted_at.is_(None),
        ]

        if student_id:
            conditions.append(StudentAttendance.student_id == student_id)
        if section_id:
            conditions.append(StudentAttendance.section_id == section_id)
        if term_id:
            conditions.append(StudentAttendance.term_id == term_id)
        if start_date:
            conditions.append(StudentAttendance.date >= start_date)
        if end_date:
            conditions.append(StudentAttendance.date <= end_date)
        if status:
            conditions.append(StudentAttendance.status == AttendanceStatus(status))

        # Count
        count_query = select(func.count(StudentAttendance.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Fetch
        query = (
            select(StudentAttendance)
            .where(and_(*conditions))
            .options(
                selectinload(StudentAttendance.student),
                selectinload(StudentAttendance.section),
            )
            .order_by(StudentAttendance.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        records = result.scalars().all()

        return records, total

    async def delete_student_attendance(
        self,
        tenant_id: UUID,
        attendance_id: UUID,
    ) -> bool:
        """Soft-delete a student attendance record."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(StudentAttendance).where(
                and_(
                    StudentAttendance.id == attendance_id,
                    StudentAttendance.tenant_id == tenant_id,
                    # Only find non-deleted records
                    StudentAttendance.deleted_at.is_(None),
                )
            )
        )
        attendance = result.scalar_one_or_none()
        if not attendance:
            return False

        # Soft delete: set deleted_at timestamp instead of physical deletion
        attendance.deleted_at = func.now()
        await self.db.flush()
        return True

    # =========================
    # Student Attendance Statistics
    # =========================

    async def get_student_attendance_summary(
        self,
        tenant_id: UUID,
        student_id: UUID,
        term_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Get attendance summary for a student."""
        # Defense-in-depth: always scope by tenant_id and exclude soft-deleted
        conditions = [
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.student_id == student_id,
            StudentAttendance.deleted_at.is_(None),
        ]
        if term_id:
            conditions.append(StudentAttendance.term_id == term_id)
        if start_date:
            conditions.append(StudentAttendance.date >= start_date)
        if end_date:
            conditions.append(StudentAttendance.date <= end_date)

        # Count by status
        query = select(
            StudentAttendance.status,
            func.count(StudentAttendance.id).label("count"),
        ).where(and_(*conditions)).group_by(StudentAttendance.status)

        result = await self.db.execute(query)
        status_counts = {row.status.value: row.count for row in result.all()}

        total = sum(status_counts.values())
        present = status_counts.get("present", 0)
        late = status_counts.get("late", 0)
        attendance_rate = ((present + late) / total * 100) if total > 0 else 0

        return {
            "total_days": total,
            "present": present,
            "absent": status_counts.get("absent", 0),
            "late": late,
            "excused": status_counts.get("excused", 0),
            "sick": status_counts.get("sick", 0),
            "attendance_rate": round(attendance_rate, 2),
        }

    async def get_section_attendance_summary(
        self,
        tenant_id: UUID,
        section_id: UUID,
        attendance_date: date,
    ) -> dict:
        """Get attendance summary for a section on a specific date."""
        # Get total active students in section (soft delete filter on Student)
        student_count_query = select(func.count(Student.id)).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.section_id == section_id,
                Student.deleted_at.is_(None),
            )
        )
        total_students = (await self.db.execute(student_count_query)).scalar_one()

        # Count by status, excluding soft-deleted attendance records
        status_query = select(
            StudentAttendance.status,
            func.count(StudentAttendance.id).label("count"),
        ).where(
            and_(
                StudentAttendance.tenant_id == tenant_id,
                StudentAttendance.section_id == section_id,
                StudentAttendance.date == attendance_date,
                StudentAttendance.deleted_at.is_(None),
            )
        ).group_by(StudentAttendance.status)

        result = await self.db.execute(status_query)
        status_counts = {row.status.value: row.count for row in result.all()}

        marked = sum(status_counts.values())
        present = status_counts.get("present", 0)
        late = status_counts.get("late", 0)

        return {
            "date": attendance_date.isoformat(),
            "total_students": total_students,
            "marked": marked,
            "unmarked": total_students - marked,
            "present": present,
            "absent": status_counts.get("absent", 0),
            "late": late,
            "excused": status_counts.get("excused", 0),
            "sick": status_counts.get("sick", 0),
            "attendance_rate": round((present + late) / total_students * 100, 2) if total_students > 0 else 0,
        }

    async def get_daily_attendance_report(
        self,
        tenant_id: UUID,
        attendance_date: date,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """Get school-wide attendance report for a date."""
        # Base conditions for students (soft delete filter on Student)
        student_conditions = [
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
        ]
        if school_id:
            student_conditions.append(Student.school_id == school_id)

        # Total active students
        total_students = (await self.db.execute(
            select(func.count(Student.id)).where(and_(*student_conditions))
        )).scalar_one()

        # Attendance counts, excluding soft-deleted attendance records
        attendance_conditions = [
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.date == attendance_date,
            StudentAttendance.deleted_at.is_(None),
        ]

        status_query = select(
            StudentAttendance.status,
            func.count(StudentAttendance.id).label("count"),
        ).where(and_(*attendance_conditions)).group_by(StudentAttendance.status)

        result = await self.db.execute(status_query)
        status_counts = {row.status.value: row.count for row in result.all()}

        marked = sum(status_counts.values())
        present = status_counts.get("present", 0)
        late = status_counts.get("late", 0)

        return {
            "date": attendance_date.isoformat(),
            "total_students": total_students,
            "marked": marked,
            "unmarked": total_students - marked,
            "present": present,
            "absent": status_counts.get("absent", 0),
            "late": late,
            "excused": status_counts.get("excused", 0),
            "sick": status_counts.get("sick", 0),
            "attendance_rate": round((present + late) / marked * 100, 2) if marked > 0 else 0,
            "marking_rate": round(marked / total_students * 100, 2) if total_students > 0 else 0,
        }

    # =========================
    # Staff Attendance Methods
    # =========================

    async def mark_staff_attendance(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        attendance_date: date,
        status: str,
        term_id: Optional[UUID] = None,
        check_in_time: Optional[time] = None,
        check_out_time: Optional[time] = None,
        remarks: Optional[str] = None,
        excuse_reason: Optional[str] = None,
        marked_by: Optional[UUID] = None,
    ) -> StaffAttendance:
        """Mark or update attendance for a staff member."""
        # Defense-in-depth: filter by tenant_id and exclude soft-deleted
        existing = await self.db.execute(
            select(StaffAttendance).where(
                and_(
                    StaffAttendance.tenant_id == tenant_id,
                    StaffAttendance.staff_id == staff_id,
                    StaffAttendance.date == attendance_date,
                    StaffAttendance.deleted_at.is_(None),
                )
            )
        )
        attendance = existing.scalar_one_or_none()

        if attendance:
            attendance.status = AttendanceStatus(status)
            attendance.term_id = term_id
            attendance.check_in_time = check_in_time
            attendance.check_out_time = check_out_time
            attendance.remarks = remarks
            attendance.excuse_reason = excuse_reason
            attendance.marked_by = marked_by
            attendance.updated_at = datetime.now(UTC)
        else:
            attendance = StaffAttendance(
                tenant_id=tenant_id,
                staff_id=staff_id,
                date=attendance_date,
                status=AttendanceStatus(status),
                term_id=term_id,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                remarks=remarks,
                excuse_reason=excuse_reason,
                marked_by=marked_by,
            )
            self.db.add(attendance)

        await self.db.flush()

        # Re-query with eager loading so endpoint can safely access relationships
        result = await self.db.execute(
            select(StaffAttendance)
            .where(StaffAttendance.id == attendance.id)
            .options(selectinload(StaffAttendance.staff))
        )
        return result.scalar_one()

    async def bulk_mark_staff_attendance(
        self,
        tenant_id: UUID,
        attendance_date: date,
        attendance_records: list[dict],
        term_id: Optional[UUID] = None,
        marked_by: Optional[UUID] = None,
    ) -> dict:
        """Bulk mark attendance for multiple staff members."""
        created = 0
        updated = 0
        failed = 0
        errors = []

        for record in attendance_records:
            try:
                staff_id = record.get("staff_id")
                status = record.get("status", "present")

                if not staff_id:
                    failed += 1
                    errors.append({"error": "staff_id is required"})
                    continue

                # Defense-in-depth: always filter by tenant_id and exclude soft-deleted
                existing = await self.db.execute(
                    select(StaffAttendance).where(
                        and_(
                            StaffAttendance.tenant_id == tenant_id,
                            StaffAttendance.staff_id == UUID(staff_id) if isinstance(staff_id, str) else staff_id,
                            StaffAttendance.date == attendance_date,
                            StaffAttendance.deleted_at.is_(None),
                        )
                    )
                )
                attendance = existing.scalar_one_or_none()

                if attendance:
                    attendance.status = AttendanceStatus(status)
                    attendance.term_id = term_id
                    attendance.check_in_time = record.get("check_in_time")
                    attendance.check_out_time = record.get("check_out_time")
                    attendance.remarks = record.get("remarks")
                    attendance.excuse_reason = record.get("excuse_reason")
                    attendance.marked_by = marked_by
                    attendance.updated_at = datetime.now(UTC)
                    updated += 1
                else:
                    attendance = StaffAttendance(
                        tenant_id=tenant_id,
                        staff_id=UUID(staff_id) if isinstance(staff_id, str) else staff_id,
                        date=attendance_date,
                        status=AttendanceStatus(status),
                        term_id=term_id,
                        check_in_time=record.get("check_in_time"),
                        check_out_time=record.get("check_out_time"),
                        remarks=record.get("remarks"),
                        excuse_reason=record.get("excuse_reason"),
                        marked_by=marked_by,
                    )
                    self.db.add(attendance)
                    created += 1

            except Exception as e:
                failed += 1
                errors.append({
                    "staff_id": record.get("staff_id"),
                    "error": str(e),
                })

        await self.db.flush()

        return {
            "created": created,
            "updated": updated,
            "failed": failed,
            "errors": errors,
        }

    async def get_staff_attendance(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        attendance_date: date,
    ) -> Optional[StaffAttendance]:
        """Get attendance record for a specific staff and date."""
        result = await self.db.execute(
            select(StaffAttendance)
            .where(
                and_(
                    StaffAttendance.tenant_id == tenant_id,
                    StaffAttendance.staff_id == staff_id,
                    StaffAttendance.date == attendance_date,
                    # Exclude soft-deleted records
                    StaffAttendance.deleted_at.is_(None),
                )
            )
            .options(selectinload(StaffAttendance.staff))
        )
        return result.scalar_one_or_none()

    async def list_staff_attendance(
        self,
        tenant_id: UUID,
        staff_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[StaffAttendance], int]:
        """List staff attendance records with filters."""
        # Defense-in-depth: always scope by tenant_id and exclude soft-deleted
        conditions = [
            StaffAttendance.tenant_id == tenant_id,
            StaffAttendance.deleted_at.is_(None),
        ]

        if staff_id:
            conditions.append(StaffAttendance.staff_id == staff_id)
        if term_id:
            conditions.append(StaffAttendance.term_id == term_id)
        if start_date:
            conditions.append(StaffAttendance.date >= start_date)
        if end_date:
            conditions.append(StaffAttendance.date <= end_date)
        if status:
            conditions.append(StaffAttendance.status == AttendanceStatus(status))

        # Count
        count_query = select(func.count(StaffAttendance.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Fetch
        query = (
            select(StaffAttendance)
            .where(and_(*conditions))
            .options(selectinload(StaffAttendance.staff))
            .order_by(StaffAttendance.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        records = result.scalars().all()

        return records, total

    async def get_staff_attendance_summary(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        term_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Get attendance summary for a staff member."""
        # Defense-in-depth: always scope by tenant_id and exclude soft-deleted
        conditions = [
            StaffAttendance.tenant_id == tenant_id,
            StaffAttendance.staff_id == staff_id,
            StaffAttendance.deleted_at.is_(None),
        ]
        if term_id:
            conditions.append(StaffAttendance.term_id == term_id)
        if start_date:
            conditions.append(StaffAttendance.date >= start_date)
        if end_date:
            conditions.append(StaffAttendance.date <= end_date)

        query = select(
            StaffAttendance.status,
            func.count(StaffAttendance.id).label("count"),
        ).where(and_(*conditions)).group_by(StaffAttendance.status)

        result = await self.db.execute(query)
        status_counts = {row.status.value: row.count for row in result.all()}

        total = sum(status_counts.values())
        present = status_counts.get("present", 0)
        late = status_counts.get("late", 0)
        attendance_rate = ((present + late) / total * 100) if total > 0 else 0

        return {
            "total_days": total,
            "present": present,
            "absent": status_counts.get("absent", 0),
            "late": late,
            "excused": status_counts.get("excused", 0),
            "sick": status_counts.get("sick", 0),
            "attendance_rate": round(attendance_rate, 2),
        }

    async def delete_staff_attendance(
        self,
        tenant_id: UUID,
        attendance_id: UUID,
    ) -> bool:
        """Soft-delete a staff attendance record."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(StaffAttendance).where(
                and_(
                    StaffAttendance.id == attendance_id,
                    StaffAttendance.tenant_id == tenant_id,
                    # Only find non-deleted records
                    StaffAttendance.deleted_at.is_(None),
                )
            )
        )
        attendance = result.scalar_one_or_none()
        if not attendance:
            return False

        # Soft delete: set deleted_at timestamp instead of physical deletion
        attendance.deleted_at = func.now()
        await self.db.flush()
        return True

    # =========================
    # Attendance Report Data
    # =========================

    async def get_attendance_report_data(
        self,
        tenant_id: UUID,
        class_id: UUID,
        section_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> dict:
        """
        Get attendance report data aggregated by student.

        Returns per-student attendance counts and percentages for the
        specified class, with optional section and date range filters.
        """
        # Defense-in-depth: always scope by tenant_id
        stmt = (
            select(
                Student.id.label("student_id"),
                Student.student_id.label("student_number"),
                Student.first_name,
                Student.last_name,
                func.count(StudentAttendance.id).label("total_days"),
                func.count(case(
                    (StudentAttendance.status == AttendanceStatus.PRESENT, 1),
                )).label("present"),
                func.count(case(
                    (StudentAttendance.status == AttendanceStatus.ABSENT, 1),
                )).label("absent"),
                func.count(case(
                    (StudentAttendance.status == AttendanceStatus.LATE, 1),
                )).label("late"),
                func.count(case(
                    (StudentAttendance.status == AttendanceStatus.EXCUSED, 1),
                )).label("excused"),
                func.count(case(
                    (StudentAttendance.status == AttendanceStatus.SICK, 1),
                )).label("sick"),
            )
            .select_from(StudentAttendance)
            .join(Student, StudentAttendance.student_id == Student.id)
            .where(
                StudentAttendance.tenant_id == tenant_id,
                StudentAttendance.deleted_at.is_(None),
                Student.class_id == class_id,
            )
        )

        if section_id:
            stmt = stmt.where(StudentAttendance.section_id == section_id)
        if date_from:
            stmt = stmt.where(StudentAttendance.date >= date_from)
        if date_to:
            stmt = stmt.where(StudentAttendance.date <= date_to)

        stmt = stmt.group_by(
            Student.id, Student.student_id, Student.first_name, Student.last_name,
        ).order_by(Student.last_name, Student.first_name)

        result = await self.db.execute(stmt)
        rows = result.all()

        students = []
        for row in rows:
            total = row.total_days or 0
            present = row.present or 0
            rate = round((present / total * 100), 1) if total > 0 else 0
            students.append({
                "student_number": row.student_number,
                "name": f"{row.first_name} {row.last_name}",
                "total_days": total,
                "present": present,
                "absent": row.absent or 0,
                "late": row.late or 0,
                "excused": row.excused or 0,
                "sick": row.sick or 0,
                "attendance_rate": rate,
            })

        return {
            "students": students,
            "total_students": len(students),
        }

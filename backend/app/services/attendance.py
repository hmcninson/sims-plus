"""
SIMS Plus - Attendance Service

Business logic for student and staff attendance management.
"""

from datetime import date, time, datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import (
    StudentAttendance,
    StaffAttendance,
    AttendanceStatus,
)
from app.models.student import Student
from app.models.staff import Staff
from app.models.academic import ClassSection, Term


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
        # Check for existing attendance record
        existing = await self.db.execute(
            select(StudentAttendance).where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.student_id == student_id,
                    StudentAttendance.date == attendance_date,
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

        await self.db.commit()
        await self.db.refresh(attendance)
        return attendance

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

        for record in attendance_records:
            try:
                student_id = record.get("student_id")
                status = record.get("status", "present")

                if not student_id:
                    failed += 1
                    errors.append({"error": "student_id is required"})
                    continue

                # Check for existing
                existing = await self.db.execute(
                    select(StudentAttendance).where(
                        and_(
                            StudentAttendance.tenant_id == tenant_id,
                            StudentAttendance.student_id == UUID(student_id) if isinstance(student_id, str) else student_id,
                            StudentAttendance.date == attendance_date,
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

            except Exception as e:
                failed += 1
                errors.append({
                    "student_id": record.get("student_id"),
                    "error": str(e),
                })

        await self.db.commit()

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
        # Get all active students in the section
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

        # Get existing attendance records
        attendance_result = await self.db.execute(
            select(StudentAttendance)
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.section_id == section_id,
                    StudentAttendance.date == attendance_date,
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
        conditions = [StudentAttendance.tenant_id == tenant_id]

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
        """Delete a student attendance record."""
        result = await self.db.execute(
            select(StudentAttendance).where(
                and_(
                    StudentAttendance.id == attendance_id,
                    StudentAttendance.tenant_id == tenant_id,
                )
            )
        )
        attendance = result.scalar_one_or_none()
        if not attendance:
            return False

        await self.db.delete(attendance)
        await self.db.commit()
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
        conditions = [
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.student_id == student_id,
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
        # Get total students in section
        student_count_query = select(func.count(Student.id)).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.section_id == section_id,
                Student.deleted_at.is_(None),
            )
        )
        total_students = (await self.db.execute(student_count_query)).scalar_one()

        # Count by status
        status_query = select(
            StudentAttendance.status,
            func.count(StudentAttendance.id).label("count"),
        ).where(
            and_(
                StudentAttendance.tenant_id == tenant_id,
                StudentAttendance.section_id == section_id,
                StudentAttendance.date == attendance_date,
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
        # Base conditions for students
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

        # Attendance counts
        attendance_conditions = [
            StudentAttendance.tenant_id == tenant_id,
            StudentAttendance.date == attendance_date,
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
        # Check for existing
        existing = await self.db.execute(
            select(StaffAttendance).where(
                and_(
                    StaffAttendance.tenant_id == tenant_id,
                    StaffAttendance.staff_id == staff_id,
                    StaffAttendance.date == attendance_date,
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

        await self.db.commit()
        await self.db.refresh(attendance)
        return attendance

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

                existing = await self.db.execute(
                    select(StaffAttendance).where(
                        and_(
                            StaffAttendance.tenant_id == tenant_id,
                            StaffAttendance.staff_id == UUID(staff_id) if isinstance(staff_id, str) else staff_id,
                            StaffAttendance.date == attendance_date,
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

        await self.db.commit()

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
        conditions = [StaffAttendance.tenant_id == tenant_id]

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
        conditions = [
            StaffAttendance.tenant_id == tenant_id,
            StaffAttendance.staff_id == staff_id,
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
        """Delete a staff attendance record."""
        result = await self.db.execute(
            select(StaffAttendance).where(
                and_(
                    StaffAttendance.id == attendance_id,
                    StaffAttendance.tenant_id == tenant_id,
                )
            )
        )
        attendance = result.scalar_one_or_none()
        if not attendance:
            return False

        await self.db.delete(attendance)
        await self.db.commit()
        return True

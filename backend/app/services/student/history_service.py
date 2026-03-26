"""
SIMS Plus - Student History Service

Class assignment history, status change tracking, and enrollment analytics.
"""

from datetime import date as date_type
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.academic import AcademicYear, Class, ClassSection
from app.models.student import (
    Student,
    StudentClassHistory,
    StudentStatus,
    StudentStatusChange,
    Gender,
)
from app.models.user import User

from app.services.student._shared import StudentServiceError


class StudentHistoryMixin:
    """Mixin for class assignment history, status change tracking, and enrollment analytics."""

    # Type hint for self.db -- set by StudentService.__init__
    db: AsyncSession

    # ===========================
    # Class Assignment History
    # ===========================

    async def record_class_assignment(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        class_id: UUID,
        section_id: UUID | None,
        academic_year_id: UUID,
        enrolled_date: date_type,
    ) -> StudentClassHistory:
        """Insert a new class assignment record.

        Creates an immutable audit record of a student being assigned to a class/section
        for a given academic year.
        """
        record = StudentClassHistory(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            class_id=class_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            enrolled_date=enrolled_date,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def close_class_assignment(
        self,
        tenant_id: UUID,
        student_id: UUID,
        academic_year_id: UUID,
        left_date: date_type,
        reason: str,
    ) -> None:
        """Close the current active assignment for a student in a given academic year.

        Finds the row WHERE left_date IS NULL for that student+year and sets
        left_date and reason. This is used when a student moves to another class,
        withdraws, or the academic year ends.
        """
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(StudentClassHistory).where(
                and_(
                    StudentClassHistory.tenant_id == tenant_id,
                    StudentClassHistory.student_id == student_id,
                    StudentClassHistory.academic_year_id == academic_year_id,
                    StudentClassHistory.left_date.is_(None),
                )
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            raise StudentServiceError(
                "No active class assignment found for this student and academic year",
                code="no_active_assignment",
            )

        record.left_date = left_date
        record.reason = reason
        await self.db.flush()

    async def get_class_history(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[dict]:
        """Get full class assignment history for a student.

        Returns dicts matching StudentClassHistoryResponse schema,
        ordered by enrolled_date DESC (most recent first).
        """
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(StudentClassHistory)
            .where(
                and_(
                    StudentClassHistory.tenant_id == tenant_id,
                    StudentClassHistory.student_id == student_id,
                )
            )
            .options(
                joinedload(StudentClassHistory.class_),
                joinedload(StudentClassHistory.section),
                joinedload(StudentClassHistory.academic_year),
            )
            .order_by(StudentClassHistory.enrolled_date.desc())
        )
        records = result.scalars().unique().all()

        return [
            {
                "id": r.id,
                "student_id": r.student_id,
                "school_id": r.school_id,
                "class_id": r.class_id,
                "section_id": r.section_id,
                "academic_year_id": r.academic_year_id,
                "enrolled_date": r.enrolled_date,
                "left_date": r.left_date,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "class_name": r.class_.name if r.class_ else None,
                "section_name": r.section.name if r.section else None,
                "academic_year_name": r.academic_year.name if r.academic_year else None,
            }
            for r in records
        ]

    # ===========================
    # Status Change Tracking
    # ===========================

    async def record_status_change(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        effective_date: date_type,
        performed_by: UUID,
        change_metadata: dict | None = None,
    ) -> StudentStatusChange:
        """Insert a status change record.

        Creates an immutable audit record of a student enrollment status transition.
        The model attribute is change_metadata (maps to DB column 'metadata').
        """
        record = StudentStatusChange(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            effective_date=effective_date,
            performed_by=performed_by,
            change_metadata=change_metadata,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_status_history(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[dict]:
        """Get full status change timeline for a student.

        Returns dicts matching StudentStatusChangeResponse schema,
        ordered by created_at DESC (most recent first).
        """
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(StudentStatusChange)
            .where(
                and_(
                    StudentStatusChange.tenant_id == tenant_id,
                    StudentStatusChange.student_id == student_id,
                )
            )
            .options(
                # Load the performer user to populate performed_by_name
                joinedload(StudentStatusChange.performed_by_user),
            )
            .order_by(StudentStatusChange.created_at.desc())
        )
        records = result.scalars().unique().all()

        return [
            {
                "id": r.id,
                "student_id": r.student_id,
                "school_id": r.school_id,
                "from_status": r.from_status,
                "to_status": r.to_status,
                "reason": r.reason,
                "effective_date": r.effective_date,
                "performed_by": r.performed_by,
                "metadata": r.change_metadata,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "performed_by_name": (
                    f"{r.performed_by_user.first_name} {r.performed_by_user.last_name}"
                    if r.performed_by_user
                    else None
                ),
            }
            for r in records
        ]

    # ===========================
    # Enrollment Analytics
    # ===========================

    async def get_enrollment_analytics(
        self,
        tenant_id: UUID,
        school_id: UUID,
    ) -> dict:
        """Get enhanced enrollment analytics for a school.

        F-6 CRITICAL: Uses a SINGLE aggregated query for status counts,
        NOT N+1 per-student queries.

        Returns dict matching EnrollmentAnalyticsResponse schema.
        """
        base_conditions = [
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
            Student.school_id == school_id,
        ]

        # --- Status counts in ONE aggregated query (F-6) ---
        status_result = await self.db.execute(
            select(
                func.count(case((Student.status == StudentStatus.ACTIVE, 1))).label("active"),
                func.count(case((Student.status == StudentStatus.INACTIVE, 1))).label("inactive"),
                func.count(case((Student.status == StudentStatus.GRADUATED, 1))).label("graduated"),
                func.count(case((Student.status == StudentStatus.TRANSFERRED, 1))).label("transferred"),
                func.count(case((Student.status == StudentStatus.WITHDRAWN, 1))).label("withdrawn"),
                func.count(case((Student.status == StudentStatus.SUSPENDED, 1))).label("suspended"),
            ).where(and_(*base_conditions))
        )
        counts = status_result.one()

        total_active = counts.active
        total_inactive = counts.inactive
        total_graduated = counts.graduated
        total_transferred = counts.transferred
        total_withdrawn = counts.withdrawn
        total_suspended = counts.suspended

        # --- By-class breakdown ---
        # Join students with their current class for the active academic year,
        # group by class, and count gender/boarder splits.
        class_result = await self.db.execute(
            select(
                Student.class_id,
                Class.name.label("class_name"),
                func.count(Student.id).label("total"),
                func.count(case((Student.gender == Gender.MALE, 1))).label("male"),
                func.count(case((Student.gender == Gender.FEMALE, 1))).label("female"),
                func.count(case((Student.is_boarder == True, 1))).label("boarders"),  # noqa: E712
                func.count(case((Student.is_boarder == False, 1))).label("day_students"),  # noqa: E712
            )
            .join(Class, Student.class_id == Class.id)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.school_id == school_id,
                    Student.deleted_at.is_(None),
                    Student.status == StudentStatus.ACTIVE,
                )
            )
            .group_by(Student.class_id, Class.name)
            .order_by(Class.name)
        )
        by_class = [
            {
                "class_id": row.class_id,
                "class_name": row.class_name,
                "total": row.total,
                "male": row.male,
                "female": row.female,
                "boarders": row.boarders,
                "day_students": row.day_students,
            }
            for row in class_result.all()
        ]

        # --- Trends: last 5 academic years ---
        # Query student_status_changes grouped by academic year (via effective_date
        # falling within academic year date ranges). We join with academic_years to
        # get year names and date boundaries.
        years_result = await self.db.execute(
            select(AcademicYear)
            .where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.deleted_at.is_(None),
                )
            )
            .order_by(AcademicYear.start_date.desc())
            .limit(5)
        )
        recent_years = years_result.scalars().all()

        trends = []
        for year in reversed(recent_years):
            # Count status changes within this academic year's date range
            year_conditions = [
                StudentStatusChange.tenant_id == tenant_id,
                StudentStatusChange.school_id == school_id,
                StudentStatusChange.effective_date >= year.start_date,
                StudentStatusChange.effective_date <= year.end_date,
            ]

            trend_result = await self.db.execute(
                select(
                    func.count(StudentStatusChange.id).label("total_changes"),
                    func.count(
                        case((StudentStatusChange.from_status.is_(None), 1))
                    ).label("new_enrollments"),
                    func.count(
                        case((StudentStatusChange.to_status == "withdrawn", 1))
                    ).label("withdrawals"),
                    func.count(
                        case((StudentStatusChange.to_status == "transferred", 1))
                    ).label("transfers_out"),
                    func.count(
                        case((StudentStatusChange.to_status == "graduated", 1))
                    ).label("graduations"),
                ).where(and_(*year_conditions))
            )
            t = trend_result.one()

            # Total enrolled = count of active students who had an assignment in this year
            enrolled_result = await self.db.execute(
                select(func.count(StudentClassHistory.id)).where(
                    and_(
                        StudentClassHistory.tenant_id == tenant_id,
                        StudentClassHistory.school_id == school_id,
                        StudentClassHistory.academic_year_id == year.id,
                    )
                )
            )
            total_enrolled = enrolled_result.scalar_one()

            trends.append({
                "academic_year_id": year.id,
                "academic_year_name": year.name,
                "total_enrolled": total_enrolled,
                "new_enrollments": t.new_enrollments,
                "withdrawals": t.withdrawals,
                "transfers_out": t.transfers_out,
                "graduations": t.graduations,
            })

        # --- Attrition and new enrollment rates ---
        total_all = total_active + total_inactive + total_graduated + total_transferred + total_withdrawn + total_suspended
        # Attrition = (withdrawn + transferred) / total * 100
        attrition_rate = (
            round((total_withdrawn + total_transferred) / total_all * 100, 2)
            if total_all > 0
            else 0.0
        )
        # New enrollment rate based on most recent year's new enrollments
        latest_new = trends[-1]["new_enrollments"] if trends else 0
        new_enrollment_rate = (
            round(latest_new / total_all * 100, 2)
            if total_all > 0
            else 0.0
        )

        return {
            "total_active": total_active,
            "total_inactive": total_inactive,
            "total_graduated": total_graduated,
            "total_transferred": total_transferred,
            "total_withdrawn": total_withdrawn,
            "total_suspended": total_suspended,
            "by_class": by_class,
            "trends": trends,
            "attrition_rate": attrition_rate,
            "new_enrollment_rate": new_enrollment_rate,
        }

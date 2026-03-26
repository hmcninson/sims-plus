"""
SIMS Plus - Preschool Extended Care Service

Business logic for extended care sessions, billing summaries,
and caregiver ratio management.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.preschool import (
    ClassCaregiverRatio,
    ExtendedCareSession,
)
from app.models.school import School
from app.models.student import Student
from app.schemas.preschool import (
    CaregiverRatioSet,
    ExtendedCareCheckInRequest,
)
from app.services.preschool._shared import PreschoolServiceError


class PreschoolExtendedCareService:
    """Service for extended care sessions, billing, and caregiver ratios."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Extended Care Sessions
    # =========================

    async def check_in_extended_care(
        self,
        tenant_id: UUID,
        data: ExtendedCareCheckInRequest,
        checked_in_by: UUID,
    ) -> ExtendedCareSession:
        """Check in a student for before-care or after-care.

        Sets session_date to today and check_in_time to current time.
        """
        # Validate student belongs to tenant
        await self._validate_student(tenant_id, data.student_id)

        now = datetime.utcnow()
        session = ExtendedCareSession(
            tenant_id=tenant_id,
            student_id=data.student_id,
            session_date=now.date(),
            session_type=data.session_type,
            check_in_time=now.time().replace(microsecond=0),
            notes=data.notes,
            checked_in_by=checked_in_by,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def check_out_extended_care(
        self,
        tenant_id: UUID,
        session_id: UUID,
        checked_out_by: UUID,
        notes: str | None = None,
    ) -> ExtendedCareSession:
        """Check out a student from extended care.

        Calculates duration_minutes from check-in to check-out time.
        Raises error if student is already checked out.
        """
        result = await self.db.execute(
            select(ExtendedCareSession).where(
                and_(
                    ExtendedCareSession.id == session_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ExtendedCareSession.tenant_id == tenant_id,
                )
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise PreschoolServiceError("Extended care session not found", "not_found")

        if session.check_out_time is not None:
            raise PreschoolServiceError("Student is already checked out", "already_checked_out")

        now = datetime.utcnow()
        checkout_time = now.time().replace(microsecond=0)
        # Ensure checkout is strictly after check-in (DB CHECK constraint requires >)
        if checkout_time <= session.check_in_time:
            check_in_dt = datetime.combine(session.session_date, session.check_in_time)
            checkout_time = (check_in_dt + timedelta(seconds=1)).time()
        session.check_out_time = checkout_time
        session.checked_out_by = checked_out_by

        # Calculate duration in minutes
        check_in_dt = datetime.combine(session.session_date, session.check_in_time)
        check_out_dt = datetime.combine(session.session_date, checkout_time)
        # Handle edge case where checkout crosses midnight (unlikely but safe)
        if check_out_dt < check_in_dt:
            check_out_dt += timedelta(days=1)
        duration = check_out_dt - check_in_dt
        session.duration_minutes = int(duration.total_seconds() / 60)

        if notes:
            # Append checkout notes to existing notes if any
            if session.notes:
                session.notes = f"{session.notes}\n[Check-out] {notes}"
            else:
                session.notes = f"[Check-out] {notes}"

        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def list_extended_care_sessions(
        self,
        tenant_id: UUID,
        *,
        student_id: UUID | None = None,
        class_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        checked_out: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[ExtendedCareSession]:
        """List extended care sessions with filters.

        checked_out=False returns only active sessions (not yet checked out).
        """
        query = select(ExtendedCareSession).where(
            ExtendedCareSession.tenant_id == tenant_id,
        )

        if student_id:
            query = query.where(ExtendedCareSession.student_id == student_id)
        if date_from:
            query = query.where(ExtendedCareSession.session_date >= date_from)
        if date_to:
            query = query.where(ExtendedCareSession.session_date <= date_to)
        if checked_out is not None:
            if checked_out:
                query = query.where(ExtendedCareSession.check_out_time.isnot(None))
            else:
                query = query.where(ExtendedCareSession.check_out_time.is_(None))

        # Filter by class requires joining through student
        if class_id:
            query = query.join(
                Student,
                and_(
                    Student.id == ExtendedCareSession.student_id,
                    Student.class_id == class_id,
                ),
            )

        query = query.order_by(
            desc(ExtendedCareSession.session_date),
            desc(ExtendedCareSession.check_in_time),
        ).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_extended_care_billing_summary(
        self,
        tenant_id: UUID,
        *,
        student_id: UUID | None = None,
        class_id: UUID | None = None,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Calculate billing summary for extended care sessions.

        Groups by student, sums duration_minutes for checked-out sessions.
        Reads rate from schools.preschool_settings to compute estimated charges.
        """
        # Build base query for completed sessions (checked out only)
        query = (
            select(
                ExtendedCareSession.student_id,
                func.count(ExtendedCareSession.id).label("total_sessions"),
                func.coalesce(func.sum(ExtendedCareSession.duration_minutes), 0).label("total_minutes"),
            )
            .where(
                and_(
                    ExtendedCareSession.tenant_id == tenant_id,
                    ExtendedCareSession.session_date >= date_from,
                    ExtendedCareSession.session_date <= date_to,
                    # Only count completed sessions for billing
                    ExtendedCareSession.check_out_time.isnot(None),
                )
            )
            .group_by(ExtendedCareSession.student_id)
        )

        if student_id:
            query = query.where(ExtendedCareSession.student_id == student_id)

        if class_id:
            query = query.join(
                Student,
                and_(
                    Student.id == ExtendedCareSession.student_id,
                    Student.class_id == class_id,
                ),
            )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Fetch rate settings from the school's preschool_settings
        rate_per_hour, flat_rate = await self._get_extended_care_rates(tenant_id)

        # Fetch student names for the summary
        student_ids = [row.student_id for row in rows]
        students_result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.id.in_(student_ids),
                    Student.tenant_id == tenant_id,
                )
            )
        )
        students = {s.id: s for s in students_result.scalars().all()}

        summaries = []
        for row in rows:
            student = students.get(row.student_id)
            student_name = (
                f"{student.first_name} {student.last_name}"
                if student
                else "Unknown"
            )
            total_minutes = int(row.total_minutes)
            total_hours = Decimal(total_minutes) / Decimal(60)
            total_sessions = int(row.total_sessions)

            # Calculate estimated charge based on rate type
            if flat_rate and flat_rate > 0:
                estimated_charge = flat_rate * total_sessions
            elif rate_per_hour and rate_per_hour > 0:
                estimated_charge = rate_per_hour * total_hours
            else:
                estimated_charge = Decimal(0)

            summaries.append({
                "student_id": row.student_id,
                "student_name": student_name,
                "total_sessions": total_sessions,
                "total_minutes": total_minutes,
                "total_hours": total_hours.quantize(Decimal("0.01")),
                "rate_per_hour": rate_per_hour,
                "flat_rate": flat_rate,
                "estimated_charge": estimated_charge.quantize(Decimal("0.01")),
            })

        return summaries

    # =========================
    # Caregiver Ratios
    # =========================

    async def list_caregiver_ratios(
        self,
        tenant_id: UUID,
        academic_year_id: UUID | None = None,
    ) -> list[dict]:
        """List caregiver ratios for preschool classes.

        Joins with students to compute current_enrollment and
        determines compliance (enrollment <= ratio * caregiver_count).
        """
        query = select(ClassCaregiverRatio).where(
            ClassCaregiverRatio.tenant_id == tenant_id,
        )
        if academic_year_id:
            query = query.where(ClassCaregiverRatio.academic_year_id == academic_year_id)

        result = await self.db.execute(query)
        ratios = result.scalars().all()

        if not ratios:
            return []

        # Query current enrollment per class
        class_ids = [r.class_id for r in ratios]
        enrollment_result = await self.db.execute(
            select(
                Student.class_id,
                func.count(Student.id).label("enrollment"),
            )
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.class_id.in_(class_ids),
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                )
            )
            .group_by(Student.class_id)
        )
        enrollment_by_class = {row.class_id: int(row.enrollment) for row in enrollment_result.all()}

        return [
            {
                "id": r.id,
                "tenant_id": r.tenant_id,
                "class_id": r.class_id,
                "academic_year_id": r.academic_year_id,
                "max_children_per_caregiver": r.max_children_per_caregiver,
                "current_caregiver_count": r.current_caregiver_count,
                "max_capacity": r.max_children_per_caregiver * r.current_caregiver_count,
                "current_enrollment": enrollment_by_class.get(r.class_id, 0),
                "is_compliant": (
                    enrollment_by_class.get(r.class_id, 0)
                    <= r.max_children_per_caregiver * r.current_caregiver_count
                ),
            }
            for r in ratios
        ]

    async def set_caregiver_ratio(
        self,
        tenant_id: UUID,
        class_id: UUID,
        academic_year_id: UUID,
        data: CaregiverRatioSet,
    ) -> ClassCaregiverRatio:
        """Upsert caregiver ratio for a class/year combination."""
        # Check if ratio already exists
        result = await self.db.execute(
            select(ClassCaregiverRatio).where(
                and_(
                    ClassCaregiverRatio.tenant_id == tenant_id,
                    ClassCaregiverRatio.class_id == class_id,
                    ClassCaregiverRatio.academic_year_id == academic_year_id,
                )
            )
        )
        ratio = result.scalar_one_or_none()

        if ratio:
            ratio.max_children_per_caregiver = data.max_children_per_caregiver
            ratio.current_caregiver_count = data.current_caregiver_count
        else:
            ratio = ClassCaregiverRatio(
                tenant_id=tenant_id,
                class_id=class_id,
                academic_year_id=academic_year_id,
                max_children_per_caregiver=data.max_children_per_caregiver,
                current_caregiver_count=data.current_caregiver_count,
            )
            self.db.add(ratio)

        await self.db.flush()
        await self.db.refresh(ratio)
        return ratio

    # =========================
    # Private Helpers
    # =========================

    async def _validate_student(self, tenant_id: UUID, student_id: UUID) -> Student:
        """Validate student exists and belongs to tenant."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", "not_found")
        return student

    async def _get_extended_care_rates(
        self, tenant_id: UUID
    ) -> tuple[Decimal | None, Decimal | None]:
        """Read extended care rate settings from school's preschool_settings.

        Returns (rate_per_hour, flat_rate). Both may be None if not configured.
        """
        result = await self.db.execute(
            select(School.preschool_settings).where(
                School.tenant_id == tenant_id,
            ).limit(1)
        )
        settings = result.scalar_one_or_none()

        if not settings or not isinstance(settings, dict):
            return None, None

        rate_per_hour = settings.get("extended_care_rate_per_hour")
        flat_rate = settings.get("extended_care_flat_rate")

        return (
            Decimal(str(rate_per_hour)) if rate_per_hour is not None else None,
            Decimal(str(flat_rate)) if flat_rate is not None else None,
        )

"""
SIMS Plus - Exeat Service

Business logic for managing student exeat (leave of absence) requests,
including the full lifecycle: request -> approve/deny -> activate -> return.
"""

from datetime import date, datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.boarding import (
    Exeat,
    ExeatStatus,
    ExeatType,
    StudentBoarding,
    BoardingStatus,
    House,
)
from app.models.student import Student

from app.services.boarding._shared import BoardingServiceError

logger = structlog.get_logger()

# Valid exeat status transitions -- enforces the state machine
_VALID_EXEAT_TRANSITIONS: dict[ExeatStatus, set[ExeatStatus]] = {
    ExeatStatus.PENDING: {ExeatStatus.APPROVED, ExeatStatus.DENIED},
    ExeatStatus.APPROVED: {ExeatStatus.ACTIVE},
    ExeatStatus.DENIED: set(),  # Terminal state
    ExeatStatus.ACTIVE: {ExeatStatus.RETURNED, ExeatStatus.OVERDUE},
    ExeatStatus.RETURNED: set(),  # Terminal state
    ExeatStatus.OVERDUE: {ExeatStatus.RETURNED},  # Can still return after overdue
}


class ExeatService:
    """Service for managing exeat requests and their lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def request_exeat(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        requested_by_id: UUID,
        data: dict,
    ) -> Exeat:
        """
        Create a new exeat request with status=pending.

        Validates the student exists and is actively assigned to a boarding house.
        """
        # Verify student exists
        student = await self._get_student_or_raise(tenant_id, student_id)

        # Verify student is an active boarder
        boarding_result = await self.db.execute(
            select(StudentBoarding).where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.student_id == student_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
        )
        if not boarding_result.scalar_one_or_none():
            raise BoardingServiceError(
                "Student is not currently assigned to a boarding house",
                code="not_a_boarder",
            )

        exeat = Exeat(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_id,
            requested_by_id=requested_by_id,
            exeat_type=ExeatType(data["exeat_type"]),
            reason=data["reason"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            guardian_phone=data.get("guardian_phone"),
            notes=data.get("notes"),
            status=ExeatStatus.PENDING,
        )
        self.db.add(exeat)
        await self.db.flush()
        await self.db.refresh(exeat)
        return exeat

    async def approve_exeat(
        self,
        tenant_id: UUID,
        exeat_id: UUID,
        approver_id: UUID,
    ) -> Exeat:
        """
        Approve a pending exeat request.

        Only pending exeats can be approved (state machine enforced).
        """
        exeat = await self._get_exeat_or_raise(tenant_id, exeat_id)
        self._validate_transition(exeat, ExeatStatus.APPROVED, "approve")

        exeat.status = ExeatStatus.APPROVED
        exeat.approved_by_id = approver_id

        await self.db.flush()
        await self.db.refresh(exeat)
        return exeat

    async def deny_exeat(
        self,
        tenant_id: UUID,
        exeat_id: UUID,
        approver_id: UUID,
        reason: Optional[str] = None,
    ) -> Exeat:
        """
        Deny a pending exeat request.

        Appends the denial reason to notes if provided.
        """
        exeat = await self._get_exeat_or_raise(tenant_id, exeat_id)
        self._validate_transition(exeat, ExeatStatus.DENIED, "deny")

        exeat.status = ExeatStatus.DENIED
        exeat.approved_by_id = approver_id

        if reason:
            denial_note = f"[DENIED] {reason}"
            if exeat.notes:
                exeat.notes = f"{exeat.notes}\n{denial_note}"
            else:
                exeat.notes = denial_note

        await self.db.flush()
        await self.db.refresh(exeat)
        return exeat

    async def activate_exeat(
        self,
        tenant_id: UUID,
        exeat_id: UUID,
    ) -> Exeat:
        """
        Activate an approved exeat (student departs campus).

        Only approved exeats can be activated -- this records the moment
        the student actually leaves.
        """
        exeat = await self._get_exeat_or_raise(tenant_id, exeat_id)
        self._validate_transition(exeat, ExeatStatus.ACTIVE, "activate")

        exeat.status = ExeatStatus.ACTIVE

        await self.db.flush()
        await self.db.refresh(exeat)
        return exeat

    async def record_return(
        self,
        tenant_id: UUID,
        exeat_id: UUID,
        actual_return_date: Optional[date] = None,
    ) -> Exeat:
        """
        Record that a student has returned from exeat.

        Accepts exeats in either 'active' or 'overdue' status. Sets the
        actual_return_date (defaults to today if not provided).
        """
        exeat = await self._get_exeat_or_raise(tenant_id, exeat_id)
        self._validate_transition(exeat, ExeatStatus.RETURNED, "record return for")

        exeat.status = ExeatStatus.RETURNED
        exeat.actual_return_date = actual_return_date or date.today()

        await self.db.flush()
        await self.db.refresh(exeat)
        return exeat

    async def get_exeats(
        self,
        tenant_id: UUID,
        school_id: UUID,
        status: Optional[str] = None,
        student_id: Optional[UUID] = None,
        house_id: Optional[UUID] = None,
    ) -> Sequence[Exeat]:
        """
        List exeats with optional filters.

        When filtering by house_id, joins through StudentBoarding to find
        students in the specified house.
        """
        conditions = [
            Exeat.tenant_id == tenant_id,
            Exeat.school_id == school_id,
            Exeat.deleted_at.is_(None),
        ]

        if status:
            conditions.append(Exeat.status == ExeatStatus(status))
        if student_id:
            conditions.append(Exeat.student_id == student_id)

        query = select(Exeat).where(and_(*conditions))

        # If filtering by house, join with StudentBoarding to get students in that house
        if house_id:
            query = query.join(
                StudentBoarding,
                and_(
                    StudentBoarding.student_id == Exeat.student_id,
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.house_id == house_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                ),
            )

        query = query.options(
            selectinload(Exeat.student),
            selectinload(Exeat.requested_by),
            selectinload(Exeat.approved_by),
        ).order_by(Exeat.created_at.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_exeat(
        self,
        tenant_id: UUID,
        exeat_id: UUID,
    ) -> Exeat:
        """Get a single exeat with all related data loaded."""
        query = (
            select(Exeat)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Exeat.tenant_id == tenant_id,
                    Exeat.id == exeat_id,
                    Exeat.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Exeat.student),
                selectinload(Exeat.requested_by),
                selectinload(Exeat.approved_by),
            )
        )
        result = await self.db.execute(query)
        exeat = result.scalar_one_or_none()
        if not exeat:
            raise BoardingServiceError("Exeat not found", code="not_found")
        return exeat

    async def get_active_exeats(
        self,
        tenant_id: UUID,
        school_id: UUID,
        house_id: Optional[UUID] = None,
    ) -> Sequence[Exeat]:
        """
        Get exeats where the student is currently out of campus.

        Returns exeats with status=active (student has departed but not returned).
        Optionally filters by house.
        """
        return await self.get_exeats(
            tenant_id=tenant_id,
            school_id=school_id,
            status=ExeatStatus.ACTIVE.value,
            house_id=house_id,
        )

    async def get_overdue_exeats(
        self,
        tenant_id: UUID,
        school_id: UUID,
    ) -> Sequence[Exeat]:
        """
        Get exeats that are overdue (past end_date, student not returned).

        Read-only query — returns overdue exeats without modifying any records.
        """
        query = (
            select(Exeat)
            .where(
                and_(
                    Exeat.tenant_id == tenant_id,
                    Exeat.school_id == school_id,
                    Exeat.status == ExeatStatus.OVERDUE,
                    Exeat.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Exeat.student),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def check_and_mark_overdue(
        self,
        tenant_id: UUID,
        school_id: UUID,
    ) -> Sequence[Exeat]:
        """
        Find active exeats past their end_date and transition to overdue.

        This is a write operation — call via POST endpoint or Celery task.
        Returns the list of exeats that were marked overdue.
        """
        today = date.today()

        # Find active exeats past their end date
        query = (
            select(Exeat)
            .where(
                and_(
                    Exeat.tenant_id == tenant_id,
                    Exeat.school_id == school_id,
                    Exeat.status == ExeatStatus.ACTIVE,
                    Exeat.end_date < today,
                    Exeat.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Exeat.student),
            )
        )
        result = await self.db.execute(query)
        overdue_exeats = result.scalars().all()

        # Transition each to overdue
        for exeat in overdue_exeats:
            exeat.status = ExeatStatus.OVERDUE

        if overdue_exeats:
            await self.db.flush()
            logger.info(
                "exeats_marked_overdue",
                tenant_id=str(tenant_id),
                count=len(overdue_exeats),
            )

        return overdue_exeats

    # =========================
    # Internal Helpers
    # =========================

    async def _get_exeat_or_raise(self, tenant_id: UUID, exeat_id: UUID) -> Exeat:
        """Fetch an exeat or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(Exeat).where(
                and_(
                    Exeat.tenant_id == tenant_id,
                    Exeat.id == exeat_id,
                    Exeat.deleted_at.is_(None),
                )
            )
        )
        exeat = result.scalar_one_or_none()
        if not exeat:
            raise BoardingServiceError("Exeat not found", code="not_found")
        return exeat

    async def _get_student_or_raise(self, tenant_id: UUID, student_id: UUID) -> Student:
        """Fetch a student or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise BoardingServiceError("Student not found", code="not_found")
        return student

    def _validate_transition(
        self,
        exeat: Exeat,
        target_status: ExeatStatus,
        operation: str,
    ) -> None:
        """
        Validate the exeat status transition against the state machine.

        Raises BoardingServiceError with a descriptive message if the
        transition is not allowed.
        """
        valid_targets = _VALID_EXEAT_TRANSITIONS.get(exeat.status, set())
        if target_status not in valid_targets:
            valid_names = (
                [s.value for s in valid_targets] if valid_targets else ["none (terminal state)"]
            )
            raise BoardingServiceError(
                f"Cannot {operation} exeat: invalid transition from "
                f"'{exeat.status.value}' to '{target_status.value}'. "
                f"Valid transitions: {', '.join(valid_names)}",
                code="invalid_status_transition",
            )

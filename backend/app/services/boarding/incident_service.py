"""
SIMS Plus - Boarding Incident Service

Business logic for reporting and resolving boarding house incidents.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.boarding import (
    BoardingIncident,
    IncidentType,
    IncidentSeverity,
)
from app.models.student import Student
from app.utils.sanitize import escape_ilike

from app.services.boarding._shared import BoardingServiceError

logger = structlog.get_logger()


class IncidentService:
    """Service for managing boarding house incidents."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def report_incident(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data: dict,
    ) -> BoardingIncident:
        """
        Report a new boarding incident.

        Validates the student exists and creates the incident record
        with initial resolved=False.
        """
        # Verify student exists and belongs to tenant
        await self._get_student_or_raise(tenant_id, data["student_id"])

        incident = BoardingIncident(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=data["student_id"],
            reported_by_id=data["reported_by_id"],
            incident_type=IncidentType(data["incident_type"]),
            severity=IncidentSeverity(data["severity"]),
            description=data["description"],
            action_taken=data.get("action_taken"),
            resolved=False,
            parent_notified=data.get("parent_notified", False),
        )
        self.db.add(incident)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def resolve_incident(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        resolver_id: UUID,
        action_taken: str,
    ) -> BoardingIncident:
        """
        Mark an incident as resolved.

        Records who resolved it, what action was taken, and the timestamp.
        An already-resolved incident cannot be re-resolved.
        """
        incident = await self._get_incident_or_raise(tenant_id, incident_id)

        if incident.resolved:
            raise BoardingServiceError(
                "Incident is already resolved",
                code="already_resolved",
            )

        incident.resolved = True
        incident.resolved_by_id = resolver_id
        incident.resolved_at = datetime.now(UTC)
        incident.action_taken = action_taken

        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def get_incidents(
        self,
        tenant_id: UUID,
        school_id: UUID,
        house_id: Optional[UUID] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        student_id: Optional[UUID] = None,
        search: Optional[str] = None,
    ) -> Sequence[BoardingIncident]:
        """
        List incidents with optional filters.

        When filtering by house_id, joins through StudentBoarding to find
        students assigned to that house.
        """
        from app.models.boarding import StudentBoarding, BoardingStatus

        conditions = [
            BoardingIncident.tenant_id == tenant_id,
            BoardingIncident.school_id == school_id,
            BoardingIncident.deleted_at.is_(None),
        ]

        if severity:
            conditions.append(
                BoardingIncident.severity == IncidentSeverity(severity)
            )
        if resolved is not None:
            conditions.append(BoardingIncident.resolved == resolved)
        if student_id:
            conditions.append(BoardingIncident.student_id == student_id)

        if search:
            safe_search = escape_ilike(search)
            search_term = f"%{safe_search}%"
            conditions.append(
                BoardingIncident.description.ilike(search_term)
            )

        query = select(BoardingIncident).where(and_(*conditions))

        # Join with StudentBoarding to filter by house
        if house_id:
            query = query.join(
                StudentBoarding,
                and_(
                    StudentBoarding.student_id == BoardingIncident.student_id,
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.house_id == house_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                ),
            )

        query = query.options(
            selectinload(BoardingIncident.student),
            selectinload(BoardingIncident.reported_by),
            selectinload(BoardingIncident.resolved_by),
        ).order_by(BoardingIncident.created_at.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_incident(
        self,
        tenant_id: UUID,
        incident_id: UUID,
    ) -> BoardingIncident:
        """Get a single incident with all related data loaded."""
        query = (
            select(BoardingIncident)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    BoardingIncident.tenant_id == tenant_id,
                    BoardingIncident.id == incident_id,
                    BoardingIncident.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(BoardingIncident.student),
                selectinload(BoardingIncident.reported_by),
                selectinload(BoardingIncident.resolved_by),
            )
        )
        result = await self.db.execute(query)
        incident = result.scalar_one_or_none()
        if not incident:
            raise BoardingServiceError("Incident not found", code="not_found")
        return incident

    async def get_student_incidents(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> Sequence[BoardingIncident]:
        """
        Get all incidents for a specific student.

        Returns incidents ordered by most recent first, useful for viewing
        a student's behavioral history.
        """
        # Verify student exists
        await self._get_student_or_raise(tenant_id, student_id)

        query = (
            select(BoardingIncident)
            .where(
                and_(
                    BoardingIncident.tenant_id == tenant_id,
                    BoardingIncident.student_id == student_id,
                    BoardingIncident.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(BoardingIncident.reported_by),
                selectinload(BoardingIncident.resolved_by),
            )
            .order_by(BoardingIncident.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    # =========================
    # Internal Helpers
    # =========================

    async def _get_incident_or_raise(
        self, tenant_id: UUID, incident_id: UUID
    ) -> BoardingIncident:
        """Fetch an incident or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(BoardingIncident).where(
                and_(
                    BoardingIncident.tenant_id == tenant_id,
                    BoardingIncident.id == incident_id,
                    BoardingIncident.deleted_at.is_(None),
                )
            )
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise BoardingServiceError("Incident not found", code="not_found")
        return incident

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

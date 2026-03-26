"""
SIMS Plus - Preschool Incident Service

Business logic for preschool incident reporting, status workflow, and resolution.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preschool import (
    AuthorizedPickup,
    PreschoolIncident,
    PreschoolIncidentStatus,
    VALID_INCIDENT_TRANSITIONS,
)
from app.models.student import Student
from app.schemas.preschool.incident import (
    PreschoolIncidentCreate,
    PreschoolIncidentUpdate,
)
from app.services.preschool._shared import PreschoolServiceError


class PreschoolIncidentService:
    """Service for preschool incident management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_incident(
        self,
        tenant_id: uuid.UUID,
        data: PreschoolIncidentCreate,
        reported_by: uuid.UUID,
    ) -> PreschoolIncident:
        """
        Create a new preschool incident report.

        For "serious" severity, the endpoint layer should trigger parent
        notification via NotificationDispatcher (if available).
        """
        # Defense-in-depth: verify student belongs to tenant
        student = await self._get_student(tenant_id, data.student_id)

        incident = PreschoolIncident(
            tenant_id=tenant_id,
            school_id=student.school_id,
            student_id=data.student_id,
            incident_type=data.incident_type,
            severity=data.severity,
            status=PreschoolIncidentStatus.REPORTED.value,
            incident_date=data.incident_date,
            incident_time=data.incident_time,
            location=data.location,
            description=data.description,
            action_taken=data.action_taken,
            first_aid_given=data.first_aid_given,
            medical_attention_required=data.medical_attention_required,
            witnesses=data.witnesses,
            attachments=(
                [att.model_dump() for att in data.attachments]
                if data.attachments
                else None
            ),
            reported_by=reported_by,
        )
        self.db.add(incident)
        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def list_incidents(
        self,
        tenant_id: uuid.UUID,
        *,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[PreschoolIncident]:
        """List incidents with optional filters."""
        query = (
            select(PreschoolIncident)
            .where(PreschoolIncident.tenant_id == tenant_id)
            .where(PreschoolIncident.deleted_at.is_(None))
            .order_by(
                PreschoolIncident.incident_date.desc(),
                PreschoolIncident.created_at.desc(),
            )
        )
        if student_id:
            query = query.where(PreschoolIncident.student_id == student_id)
        if class_id:
            # Defense-in-depth: also filter joined Student by tenant_id
            query = query.join(
                Student, PreschoolIncident.student_id == Student.id
            ).where(
                Student.class_id == class_id,
                Student.tenant_id == tenant_id,
            )
        if status:
            query = query.where(PreschoolIncident.status == status)
        if severity:
            query = query.where(PreschoolIncident.severity == severity)
        if date_from:
            query = query.where(PreschoolIncident.incident_date >= date_from)
        if date_to:
            query = query.where(PreschoolIncident.incident_date <= date_to)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_incident(
        self, tenant_id: uuid.UUID, incident_id: uuid.UUID
    ) -> PreschoolIncident:
        """Get a single incident by ID."""
        result = await self.db.execute(
            select(PreschoolIncident)
            .where(PreschoolIncident.id == incident_id)
            .where(PreschoolIncident.tenant_id == tenant_id)
            .where(PreschoolIncident.deleted_at.is_(None))
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise PreschoolServiceError(
                "Incident not found", code="INCIDENT_NOT_FOUND"
            )
        return incident

    async def update_incident(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        data: PreschoolIncidentUpdate,
    ) -> PreschoolIncident:
        """Update incident details (not status -- use dedicated methods for that).

        SECURITY: PROTECTED_FIELDS blocklist prevents accidental overwrite
        of status, ownership, and audit fields even if the schema is
        extended incorrectly in the future.
        """
        incident = await self.get_incident(tenant_id, incident_id)

        PROTECTED_FIELDS = {
            "id", "tenant_id", "school_id", "student_id", "status",
            "reported_by", "parent_notified_at", "parent_notified_by",
            "resolved_at", "resolved_by", "created_at", "deleted_at",
        }

        update_data = data.model_dump(exclude_unset=True)

        # Serialize attachment objects to dicts for JSONB storage
        if "attachments" in update_data and update_data["attachments"] is not None:
            update_data["attachments"] = [
                att.model_dump() if hasattr(att, "model_dump") else att
                for att in update_data["attachments"]
            ]

        for field, value in update_data.items():
            if field in PROTECTED_FIELDS:
                continue
            setattr(incident, field, value)

        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def notify_parent_incident(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        notified_by: uuid.UUID,
    ) -> PreschoolIncident:
        """
        Mark incident as parent_notified and record who notified.

        The actual SMS/email sending is handled by the endpoint layer
        which has access to NotificationDispatcher.
        """
        incident = await self.get_incident(tenant_id, incident_id)

        # Validate status transition against the state machine
        current_status = PreschoolIncidentStatus(incident.status)
        allowed = VALID_INCIDENT_TRANSITIONS.get(current_status, [])
        if PreschoolIncidentStatus.PARENT_NOTIFIED not in allowed:
            raise PreschoolServiceError(
                f"Cannot transition from '{incident.status}' to 'parent_notified'",
                code="INVALID_TRANSITION",
            )

        incident.status = PreschoolIncidentStatus.PARENT_NOTIFIED.value
        incident.parent_notified_at = datetime.now(timezone.utc)
        incident.parent_notified_by = notified_by

        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    async def resolve_incident(
        self,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        follow_up_notes: str | None,
        resolved_by: uuid.UUID,
    ) -> PreschoolIncident:
        """Resolve an incident with optional follow-up notes.

        CHILD SAFETY: Moderate and serious incidents MUST go through
        parent notification before resolution. Only minor incidents
        can be resolved from REVIEWED without parent notification.
        """
        incident = await self.get_incident(tenant_id, incident_id)
        current_status = PreschoolIncidentStatus(incident.status)

        # Severity gate: moderate/serious require parent notification first
        if incident.severity in ("moderate", "serious"):
            if current_status != PreschoolIncidentStatus.PARENT_NOTIFIED:
                raise PreschoolServiceError(
                    "Moderate and serious incidents must have parent "
                    "notification before resolution",
                    code="PARENT_NOTIFICATION_REQUIRED",
                )

        allowed = VALID_INCIDENT_TRANSITIONS.get(current_status, [])
        if PreschoolIncidentStatus.RESOLVED not in allowed:
            raise PreschoolServiceError(
                f"Cannot transition from '{incident.status}' to 'resolved'",
                code="INVALID_TRANSITION",
            )

        incident.status = PreschoolIncidentStatus.RESOLVED.value
        incident.follow_up_notes = follow_up_notes
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolved_by = resolved_by

        await self.db.flush()
        await self.db.refresh(incident)
        return incident

    # ---------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------

    async def _get_student(
        self, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> Student:
        """Verify student belongs to tenant and return the record."""
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .where(Student.tenant_id == tenant_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError(
                "Student not found", code="STUDENT_NOT_FOUND"
            )
        return student

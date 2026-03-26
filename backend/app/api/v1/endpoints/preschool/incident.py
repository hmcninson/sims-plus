"""
SIMS Plus - Preschool Incident Endpoints

API routes for preschool incident reporting, parent notification, and resolution.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.audit import AuditService
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    PreschoolIncidentCreate,
    PreschoolIncidentUpdate,
    PreschoolIncidentResponse,
    IncidentResolveRequest,
    convert_uuid,
)

router = APIRouter()


# =========================
# Incident Endpoints
# =========================


@router.post(
    "/incidents",
    response_model=PreschoolIncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a new incident",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_incident(
    data: PreschoolIncidentCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Report a new preschool incident."""
    service = PreschoolService(db)
    try:
        incident = await service.create_incident(
            tenant_id=convert_uuid(tenant.tenant_id),
            data=data,
            reported_by=convert_uuid(current_user["user_id"]),
        )

        # Audit trail for child safety incident creation
        audit = AuditService(db)
        await audit.log(
            event_type="preschool.incident.create",
            tenant_id=convert_uuid(tenant.tenant_id),
            user_id=convert_uuid(current_user["user_id"]),
            target_type="preschool_incident",
            target_id=incident.id,
            details={"severity": data.severity, "incident_type": data.incident_type},
        )

        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == "STUDENT_NOT_FOUND"
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.get(
    "/incidents",
    response_model=list[PreschoolIncidentResponse],
    summary="List incidents",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_incidents(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = None,
    class_id: UUID | None = None,
    incident_status: str | None = Query(None, alias="status"),
    severity: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List incidents with optional filters."""
    service = PreschoolService(db)
    incidents = await service.list_incidents(
        tenant_id=convert_uuid(tenant.tenant_id),
        student_id=student_id,
        class_id=class_id,
        status=incident_status,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [PreschoolIncidentResponse.model_validate(i) for i in incidents]


@router.get(
    "/incidents/{incident_id}",
    response_model=PreschoolIncidentResponse,
    summary="Get incident",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_incident(
    incident_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a single incident by ID."""
    service = PreschoolService(db)
    try:
        incident = await service.get_incident(
            convert_uuid(tenant.tenant_id), incident_id
        )
        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )


@router.put(
    "/incidents/{incident_id}",
    response_model=PreschoolIncidentResponse,
    summary="Update incident",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_incident(
    incident_id: UUID,
    data: PreschoolIncidentUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update incident details."""
    service = PreschoolService(db)
    try:
        incident = await service.update_incident(
            convert_uuid(tenant.tenant_id), incident_id, data
        )
        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == "INCIDENT_NOT_FOUND"
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.post(
    "/incidents/{incident_id}/notify-parent",
    response_model=PreschoolIncidentResponse,
    summary="Notify parent about incident",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def notify_parent_incident(
    incident_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """
    Mark incident as parent_notified and trigger SMS/email.

    IMPORTANT: The notification dispatch MUST happen BEFORE the status update.
    If SMS/email fails, the status should NOT be changed to parent_notified.
    """
    service = PreschoolService(db)
    try:
        # TODO: Integrate NotificationDispatcher -- dispatch BEFORE status change.
        # If dispatch fails, raise error and do NOT update status.

        # Update status after successful dispatch
        incident = await service.notify_parent_incident(
            convert_uuid(tenant.tenant_id),
            incident_id,
            notified_by=convert_uuid(current_user["user_id"]),
        )

        # Audit trail for parent notification of child safety incident
        audit = AuditService(db)
        await audit.log(
            event_type="preschool.incident.notify_parent",
            tenant_id=convert_uuid(tenant.tenant_id),
            user_id=convert_uuid(current_user["user_id"]),
            target_type="preschool_incident",
            target_id=incident.id,
            details={"severity": incident.severity},
        )

        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == "INCIDENT_NOT_FOUND"
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=PreschoolIncidentResponse,
    summary="Resolve incident",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def resolve_incident(
    incident_id: UUID,
    data: IncidentResolveRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Resolve an incident with optional follow-up notes."""
    service = PreschoolService(db)
    try:
        incident = await service.resolve_incident(
            convert_uuid(tenant.tenant_id),
            incident_id,
            follow_up_notes=data.follow_up_notes,
            resolved_by=convert_uuid(current_user["user_id"]),
        )

        # Audit trail for child safety incident resolution
        audit = AuditService(db)
        await audit.log(
            event_type="preschool.incident.resolve",
            tenant_id=convert_uuid(tenant.tenant_id),
            user_id=convert_uuid(current_user["user_id"]),
            target_type="preschool_incident",
            target_id=incident.id,
            details={"follow_up_notes": bool(data.follow_up_notes)},
        )

        return PreschoolIncidentResponse.model_validate(incident)
    except PreschoolServiceError as e:
        code = (
            status.HTTP_404_NOT_FOUND
            if e.code == "INCIDENT_NOT_FOUND"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=e.message)

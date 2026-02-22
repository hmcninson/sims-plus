"""
SIMS Plus - Boarding Incident Endpoints

Endpoints for reporting, viewing, and resolving boarding house incidents.
Incidents track disciplinary, health, and safety events for boarding students.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.boarding import (
    BoardingIncidentCreate,
    BoardingIncidentDetailResponse,
    BoardingIncidentListResponse,
    BoardingIncidentResolve,
    BoardingIncidentResponse,
)
from app.services.boarding import BoardingServiceError, IncidentService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


@router.post(
    "/incidents",
    response_model=BoardingIncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report incident",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def report_incident(
    data: BoardingIncidentCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingIncidentResponse:
    """
    Report a new boarding incident.

    The reporting user is automatically set from the authenticated user's JWT.
    """
    school_id = _get_school_id(user)
    service = IncidentService(db)

    try:
        incident = await service.report_incident(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            data={
                **data.model_dump(),
                "reported_by_id": UUID(user["user_id"]),
            },
        )
        return BoardingIncidentResponse.model_validate(incident)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/incidents",
    response_model=BoardingIncidentListResponse,
    summary="List incidents",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_incidents(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    house_id: UUID | None = Query(None, description="Filter by house"),
    severity: str | None = Query(None, description="Filter by severity"),
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    student_id: UUID | None = Query(None, description="Filter by student"),
    search: str | None = Query(None, description="Search in description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> BoardingIncidentListResponse:
    """List boarding incidents with optional filters and pagination."""
    school_id = _get_school_id(user)
    service = IncidentService(db)

    incidents = await service.get_incidents(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        house_id=house_id,
        severity=severity,
        resolved=resolved,
        student_id=student_id,
        search=search,
    )

    # Manual pagination over the result set
    total = len(incidents)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = incidents[start:end]

    items = [_build_incident_detail(i) for i in page_items]

    return BoardingIncidentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/incidents/student/{student_id}",
    response_model=list[BoardingIncidentDetailResponse],
    summary="Get student incidents",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_student_incidents(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[BoardingIncidentDetailResponse]:
    """Get all incidents for a specific student."""
    service = IncidentService(db)

    try:
        incidents = await service.get_student_incidents(
            tenant_id=tenant.tenant_id,
            student_id=student_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    return [_build_incident_detail(i) for i in incidents]


@router.get(
    "/incidents/{incident_id}",
    response_model=BoardingIncidentDetailResponse,
    summary="Get incident detail",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_incident(
    incident_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingIncidentDetailResponse:
    """Get a boarding incident by ID with full details."""
    service = IncidentService(db)

    try:
        incident = await service.get_incident(
            tenant_id=tenant.tenant_id,
            incident_id=incident_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    return _build_incident_detail(incident)


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=BoardingIncidentResponse,
    summary="Resolve incident",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def resolve_incident(
    incident_id: UUID,
    data: BoardingIncidentResolve,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingIncidentResponse:
    """
    Mark a boarding incident as resolved.

    Records who resolved it and the action taken.
    """
    service = IncidentService(db)

    try:
        incident = await service.resolve_incident(
            tenant_id=tenant.tenant_id,
            incident_id=incident_id,
            resolver_id=UUID(user["user_id"]),
            action_taken=data.action_taken,
        )
        return BoardingIncidentResponse.model_validate(incident)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


def _build_incident_detail(incident) -> BoardingIncidentDetailResponse:
    """Build an incident detail response with resolved names."""
    student_name = None
    if hasattr(incident, "student") and incident.student:
        student_name = (
            f"{incident.student.first_name} {incident.student.last_name}"
        )

    reported_by_name = None
    if hasattr(incident, "reported_by") and incident.reported_by:
        reported_by_name = (
            f"{incident.reported_by.first_name} {incident.reported_by.last_name}"
        )

    resolved_by_name = None
    if hasattr(incident, "resolved_by") and incident.resolved_by:
        resolved_by_name = (
            f"{incident.resolved_by.first_name} {incident.resolved_by.last_name}"
        )

    return BoardingIncidentDetailResponse(
        id=incident.id,
        tenant_id=incident.tenant_id,
        school_id=incident.school_id,
        student_id=incident.student_id,
        reported_by_id=incident.reported_by_id,
        incident_type=incident.incident_type.value
        if hasattr(incident.incident_type, "value")
        else incident.incident_type,
        severity=incident.severity.value
        if hasattr(incident.severity, "value")
        else incident.severity,
        description=incident.description,
        action_taken=incident.action_taken,
        resolved=incident.resolved,
        resolved_by_id=incident.resolved_by_id,
        resolved_at=incident.resolved_at,
        parent_notified=incident.parent_notified,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        student_name=student_name,
        reported_by_name=reported_by_name,
        resolved_by_name=resolved_by_name,
    )

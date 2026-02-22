"""
SIMS Plus - Transport Assignment Endpoints

Endpoints for assigning students to transport routes and stops,
updating assignments, and cancelling assignments.
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
from app.schemas.transport import (
    StudentTransportCreate,
    StudentTransportDetailResponse,
    StudentTransportListResponse,
    StudentTransportResponse,
    StudentTransportUpdate,
)
from app.services.transport import TransportAssignmentService, TransportServiceError

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


# =========================
# Assignment Endpoints
# =========================


@router.post(
    "/assignments",
    response_model=StudentTransportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign student to transport",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def assign_student(
    data: StudentTransportCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentTransportResponse:
    """
    Assign a student to a transport route and stop for an academic year.

    Validates student, route, stop, and academic year existence. Checks
    that the stop belongs to the route and that route capacity is not exceeded.
    """
    school_id = _get_school_id(user)
    service = TransportAssignmentService(db)

    try:
        assignment = await service.assign_student(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            student_id=data.student_id,
            route_id=data.route_id,
            stop_id=data.stop_id,
            academic_year_id=data.academic_year_id,
            status=data.status,
            pickup_guardian_phone=data.pickup_guardian_phone,
            special_instructions=data.special_instructions,
        )
        return StudentTransportResponse.model_validate(assignment)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/assignments",
    response_model=StudentTransportListResponse,
    summary="List transport assignments",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def list_assignments(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    route_id: UUID | None = Query(None, description="Filter by route"),
    academic_year_id: UUID | None = Query(None, description="Filter by academic year"),
    assignment_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status (active, suspended, cancelled)",
    ),
) -> StudentTransportListResponse:
    """List transport assignments with optional filters."""
    school_id = _get_school_id(user)
    service = TransportAssignmentService(db)

    assignments, total = await service.get_assignments(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        route_id=route_id,
        academic_year_id=academic_year_id,
        status=assignment_status,
        page=page,
        page_size=page_size,
    )

    items = [_build_assignment_detail(a) for a in assignments]

    return StudentTransportListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/assignments/{assignment_id}",
    response_model=StudentTransportDetailResponse,
    summary="Get assignment detail",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_assignment(
    assignment_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentTransportDetailResponse:
    """Get a transport assignment by ID with student, route, and stop details."""
    service = TransportAssignmentService(db)

    try:
        assignment = await service.get_assignment(
            tenant_id=tenant.tenant_id,
            assignment_id=assignment_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

    return _build_assignment_detail(assignment)


@router.put(
    "/assignments/{assignment_id}",
    response_model=StudentTransportResponse,
    summary="Update assignment",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def update_assignment(
    assignment_id: UUID,
    data: StudentTransportUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentTransportResponse:
    """
    Update a transport assignment (change route, stop, status, or contact info).

    When changing routes, validates capacity. When changing stops, validates
    the stop belongs to the (possibly new) route.
    """
    service = TransportAssignmentService(db)

    try:
        assignment = await service.update_assignment(
            tenant_id=tenant.tenant_id,
            assignment_id=assignment_id,
            route_id=data.route_id,
            stop_id=data.stop_id,
            status=data.status,
            pickup_guardian_phone=data.pickup_guardian_phone,
            special_instructions=data.special_instructions,
        )
        return StudentTransportResponse.model_validate(assignment)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/assignments/{assignment_id}/cancel",
    response_model=StudentTransportResponse,
    summary="Cancel assignment",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def cancel_assignment(
    assignment_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StudentTransportResponse:
    """
    Cancel a student's transport assignment.

    Sets the assignment status to 'cancelled'. The assignment record is
    preserved for reporting purposes rather than being deleted.
    """
    service = TransportAssignmentService(db)

    try:
        assignment = await service.unassign_student(
            tenant_id=tenant.tenant_id,
            assignment_id=assignment_id,
        )
        return StudentTransportResponse.model_validate(assignment)
    except TransportServiceError as e:
        raise _handle_service_error(e)


# =========================
# Helper Functions
# =========================


def _build_assignment_detail(assignment) -> StudentTransportDetailResponse:
    """
    Build a StudentTransportDetailResponse from a StudentTransport model
    with eagerly loaded relationships (student, route, stop, academic_year).
    """
    student_name = None
    if hasattr(assignment, "student") and assignment.student:
        student = assignment.student
        student_name = f"{student.first_name} {student.last_name}"

    route_name = None
    if hasattr(assignment, "route") and assignment.route:
        route_name = assignment.route.name

    stop_name = None
    pickup_time = None
    dropoff_time = None
    if hasattr(assignment, "stop") and assignment.stop:
        stop_name = assignment.stop.stop_name
        pickup_time = assignment.stop.pickup_time
        dropoff_time = assignment.stop.dropoff_time

    academic_year_name = None
    if hasattr(assignment, "academic_year") and assignment.academic_year:
        academic_year_name = assignment.academic_year.name

    return StudentTransportDetailResponse(
        id=assignment.id,
        tenant_id=assignment.tenant_id,
        school_id=assignment.school_id,
        student_id=assignment.student_id,
        route_id=assignment.route_id,
        stop_id=assignment.stop_id,
        academic_year_id=assignment.academic_year_id,
        status=assignment.status.value if hasattr(assignment.status, "value") else assignment.status,
        pickup_guardian_phone=assignment.pickup_guardian_phone,
        special_instructions=assignment.special_instructions,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        student_name=student_name,
        route_name=route_name,
        stop_name=stop_name,
        academic_year_name=academic_year_name,
        pickup_time=pickup_time,
        dropoff_time=dropoff_time,
    )

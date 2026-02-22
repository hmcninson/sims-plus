"""
SIMS Plus - Exeat Endpoints

Endpoints for the full exeat lifecycle: request, approve/deny, activate, return.
Exeats track student leave of absence from the boarding house.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.boarding import (
    ExeatApprovalUpdate,
    ExeatCreate,
    ExeatDetailResponse,
    ExeatListResponse,
    ExeatResponse,
    ExeatReturnUpdate,
)
from app.services.boarding import BoardingServiceError, ExeatService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


@router.post(
    "/exeats",
    response_model=ExeatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request exeat",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def request_exeat(
    data: ExeatCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExeatResponse:
    """
    Create a new exeat request for a student.

    The requesting user is automatically set from the authenticated user's JWT.
    """
    school_id = _get_school_id(user)
    service = ExeatService(db)

    try:
        exeat = await service.request_exeat(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            student_id=data.student_id,
            requested_by_id=UUID(user["user_id"]),
            data=data.model_dump(),
        )
        return ExeatResponse.model_validate(exeat)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/exeats",
    response_model=ExeatListResponse,
    summary="List exeats",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_exeats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    exeat_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status (pending, approved, denied, active, returned, overdue)",
    ),
    student_id: UUID | None = Query(None, description="Filter by student"),
    house_id: UUID | None = Query(None, description="Filter by house"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> ExeatListResponse:
    """List exeats with optional filters and pagination."""
    import math

    school_id = _get_school_id(user)
    service = ExeatService(db)

    exeats = await service.get_exeats(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        status=exeat_status,
        student_id=student_id,
        house_id=house_id,
    )

    # Manual pagination over the result set
    total = len(exeats)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = exeats[start:end]

    items = [_build_exeat_detail(e) for e in page_items]

    return ExeatListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/exeats/active",
    response_model=list[ExeatDetailResponse],
    summary="Get active exeats",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_active_exeats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    house_id: UUID | None = Query(None, description="Filter by house"),
) -> list[ExeatDetailResponse]:
    """Get exeats where the student is currently out of campus (status=active)."""
    school_id = _get_school_id(user)
    service = ExeatService(db)

    exeats = await service.get_active_exeats(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        house_id=house_id,
    )

    return [_build_exeat_detail(e) for e in exeats]


@router.get(
    "/exeats/overdue",
    response_model=list[ExeatDetailResponse],
    summary="Get overdue exeats",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_overdue_exeats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ExeatDetailResponse]:
    """Get exeats that are overdue (past end date, student not returned)."""
    school_id = _get_school_id(user)
    service = ExeatService(db)

    exeats = await service.get_overdue_exeats(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
    )

    return [_build_exeat_detail(e) for e in exeats]


@router.post(
    "/exeats/check-overdue",
    response_model=list[ExeatDetailResponse],
    summary="Check and mark overdue exeats",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def check_overdue_exeats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ExeatDetailResponse]:
    """
    Find active exeats past their end date and transition them to overdue.

    This is a write operation that marks active exeats as overdue.
    """
    school_id = _get_school_id(user)
    service = ExeatService(db)

    exeats = await service.check_and_mark_overdue(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
    )

    return [_build_exeat_detail(e) for e in exeats]


@router.post(
    "/exeats/{exeat_id}/approve",
    response_model=ExeatResponse,
    summary="Approve exeat",
    dependencies=[Depends(require_permissions("boarding.exeat.approve"))],
)
async def approve_exeat(
    exeat_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExeatResponse:
    """Approve a pending exeat request."""
    service = ExeatService(db)

    try:
        exeat = await service.approve_exeat(
            tenant_id=tenant.tenant_id,
            exeat_id=exeat_id,
            approver_id=UUID(user["user_id"]),
        )
        return ExeatResponse.model_validate(exeat)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/exeats/{exeat_id}/deny",
    response_model=ExeatResponse,
    summary="Deny exeat",
    dependencies=[Depends(require_permissions("boarding.exeat.approve"))],
)
async def deny_exeat(
    exeat_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    data: ExeatApprovalUpdate | None = None,
) -> ExeatResponse:
    """Deny a pending exeat request with an optional reason."""
    service = ExeatService(db)

    reason = data.notes if data else None

    try:
        exeat = await service.deny_exeat(
            tenant_id=tenant.tenant_id,
            exeat_id=exeat_id,
            approver_id=UUID(user["user_id"]),
            reason=reason,
        )
        return ExeatResponse.model_validate(exeat)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/exeats/{exeat_id}/activate",
    response_model=ExeatResponse,
    summary="Activate exeat",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def activate_exeat(
    exeat_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExeatResponse:
    """Activate an approved exeat (student departs campus)."""
    service = ExeatService(db)

    try:
        exeat = await service.activate_exeat(
            tenant_id=tenant.tenant_id,
            exeat_id=exeat_id,
        )
        return ExeatResponse.model_validate(exeat)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/exeats/{exeat_id}/return",
    response_model=ExeatResponse,
    summary="Record exeat return",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def record_return(
    exeat_id: UUID,
    data: ExeatReturnUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExeatResponse:
    """Record that a student has returned from exeat."""
    service = ExeatService(db)

    try:
        exeat = await service.record_return(
            tenant_id=tenant.tenant_id,
            exeat_id=exeat_id,
            actual_return_date=data.actual_return_date,
        )
        return ExeatResponse.model_validate(exeat)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


def _build_exeat_detail(exeat) -> ExeatDetailResponse:
    """Build an exeat detail response with resolved names."""
    student_name = None
    if hasattr(exeat, "student") and exeat.student:
        student_name = f"{exeat.student.first_name} {exeat.student.last_name}"

    requested_by_name = None
    if hasattr(exeat, "requested_by") and exeat.requested_by:
        requested_by_name = (
            f"{exeat.requested_by.first_name} {exeat.requested_by.last_name}"
        )

    approved_by_name = None
    if hasattr(exeat, "approved_by") and exeat.approved_by:
        approved_by_name = (
            f"{exeat.approved_by.first_name} {exeat.approved_by.last_name}"
        )

    return ExeatDetailResponse(
        id=exeat.id,
        tenant_id=exeat.tenant_id,
        school_id=exeat.school_id,
        student_id=exeat.student_id,
        requested_by_id=exeat.requested_by_id,
        approved_by_id=exeat.approved_by_id,
        exeat_type=exeat.exeat_type.value
        if hasattr(exeat.exeat_type, "value")
        else exeat.exeat_type,
        reason=exeat.reason,
        start_date=exeat.start_date,
        end_date=exeat.end_date,
        actual_return_date=exeat.actual_return_date,
        status=exeat.status.value
        if hasattr(exeat.status, "value")
        else exeat.status,
        guardian_notified=exeat.guardian_notified,
        guardian_phone=exeat.guardian_phone,
        notes=exeat.notes,
        created_at=exeat.created_at,
        updated_at=exeat.updated_at,
        student_name=student_name,
        requested_by_name=requested_by_name,
        approved_by_name=approved_by_name,
    )

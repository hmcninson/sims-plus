"""
SIMS Plus - Capacity Planning Endpoints

Enrollment targets and capacity dashboard for admissions planning.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.capacity import (
    CapacityCheckResponse,
    CapacityDashboardResponse,
    EnrollmentTargetCreate,
    EnrollmentTargetListResponse,
    EnrollmentTargetResponse,
)
from app.services.admissions import CapacityService, CapacityServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/capacity")


def _handle_error(e: CapacityServiceError) -> HTTPException:
    status_map = {
        "YEAR_NOT_FOUND": 404,
        "CLASS_NOT_FOUND": 404,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "/targets",
    response_model=EnrollmentTargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set enrollment target",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def set_target(
    data: EnrollmentTargetCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EnrollmentTargetResponse:
    """Set or update enrollment target for a class/year (upsert semantics)."""
    try:
        svc = CapacityService(db)
        target = await svc.set_target(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            target_count=data.target_count,
            boarding_target=data.boarding_target,
            day_target=data.day_target,
        )
        return EnrollmentTargetResponse.model_validate(target)
    except CapacityServiceError as e:
        raise _handle_error(e)


@router.get(
    "/targets",
    response_model=EnrollmentTargetListResponse,
    summary="List enrollment targets",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_targets(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(
        ..., description="Academic year to get targets for"
    ),
) -> EnrollmentTargetListResponse:
    svc = CapacityService(db)
    targets = await svc.get_targets(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        academic_year_id=academic_year_id,
    )
    return EnrollmentTargetListResponse(
        items=targets,
        academic_year_id=academic_year_id,
    )


@router.get(
    "/dashboard",
    response_model=CapacityDashboardResponse,
    summary="Capacity planning dashboard",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_dashboard(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(
        ..., description="Academic year for dashboard"
    ),
) -> CapacityDashboardResponse:
    try:
        svc = CapacityService(db)
        return await svc.get_dashboard(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=academic_year_id,
        )
    except CapacityServiceError as e:
        raise _handle_error(e)


@router.get(
    "/check/{class_id}",
    response_model=CapacityCheckResponse,
    summary="Check class capacity",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def check_capacity(
    class_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> CapacityCheckResponse:
    try:
        svc = CapacityService(db)
        return await svc.check_capacity(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            class_id=class_id,
        )
    except CapacityServiceError as e:
        raise _handle_error(e)

"""
SIMS Plus - Preschool Extended Care Endpoints

API routes for extended care sessions, billing summaries,
and caregiver ratio management.
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
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    CaregiverRatioResponse,
    CaregiverRatioSet,
    ExtendedCareBillingSummary,
    ExtendedCareCheckInRequest,
    ExtendedCareCheckOutRequest,
    ExtendedCareSessionResponse,
    convert_uuid,
)

router = APIRouter()


# =========================
# Extended Care Sessions
# =========================


@router.post(
    "/extended-care/check-in",
    response_model=ExtendedCareSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Check in student for extended care",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def check_in_extended_care(
    data: ExtendedCareCheckInRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Check in a student for before-care or after-care."""
    service = PreschoolService(db)
    try:
        return await service.check_in_extended_care(
            convert_uuid(tenant.tenant_id),
            data,
            convert_uuid(current_user["user_id"]),
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/extended-care/{session_id}/check-out",
    response_model=ExtendedCareSessionResponse,
    summary="Check out student from extended care",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def check_out_extended_care(
    session_id: UUID,
    data: ExtendedCareCheckOutRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Check out a student and calculate session duration."""
    service = PreschoolService(db)
    try:
        return await service.check_out_extended_care(
            convert_uuid(tenant.tenant_id),
            session_id,
            convert_uuid(current_user["user_id"]),
            notes=data.notes,
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        if e.code == "already_checked_out":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/extended-care/sessions",
    response_model=list[ExtendedCareSessionResponse],
    summary="List extended care sessions",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_extended_care_sessions(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    checked_out: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
):
    """List extended care sessions with filters.

    Use checked_out=false to show only active (not yet checked out) sessions.
    """
    service = PreschoolService(db)
    return await service.list_extended_care_sessions(
        convert_uuid(tenant.tenant_id),
        student_id=student_id,
        class_id=class_id,
        date_from=date_from,
        date_to=date_to,
        checked_out=checked_out,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/extended-care/billing-summary",
    response_model=list[ExtendedCareBillingSummary],
    summary="Get extended care billing summary",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_extended_care_billing_summary(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    date_from: date = Query(..., description="Start date (required)"),
    date_to: date = Query(..., description="End date (required)"),
    student_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
):
    """Calculate billing summary for extended care sessions.

    Groups by student, sums duration, and calculates estimated charges
    based on the school's configured rate settings.
    """
    service = PreschoolService(db)
    return await service.get_extended_care_billing_summary(
        convert_uuid(tenant.tenant_id),
        student_id=student_id,
        class_id=class_id,
        date_from=date_from,
        date_to=date_to,
    )


# =========================
# Caregiver Ratios
# =========================


@router.get(
    "/caregiver-ratios",
    response_model=list[CaregiverRatioResponse],
    summary="List caregiver ratios",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_caregiver_ratios(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    academic_year_id: UUID | None = Query(None),
):
    """List caregiver-to-child ratios for preschool classes with compliance status."""
    service = PreschoolService(db)
    return await service.list_caregiver_ratios(
        convert_uuid(tenant.tenant_id),
        academic_year_id=academic_year_id,
    )


@router.put(
    "/caregiver-ratios/{class_id}",
    response_model=CaregiverRatioResponse,
    summary="Set caregiver ratio",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def set_caregiver_ratio(
    class_id: UUID,
    data: CaregiverRatioSet,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    academic_year_id: UUID = Query(..., description="Academic year ID (required)"),
):
    """Set or update caregiver ratio for a class/year combination.

    Returns the ratio with computed compliance info (requires a separate
    query for current_enrollment).
    """
    service = PreschoolService(db)
    ratio = await service.set_caregiver_ratio(
        convert_uuid(tenant.tenant_id),
        class_id,
        academic_year_id,
        data,
    )

    # Fetch enrollment to compute compliance for the response
    ratios = await service.list_caregiver_ratios(
        convert_uuid(tenant.tenant_id),
        academic_year_id=academic_year_id,
    )
    # Find the one we just upserted
    for r in ratios:
        if r["class_id"] == ratio.class_id and r["academic_year_id"] == ratio.academic_year_id:
            return r

    # Fallback: return basic response without enrollment data
    return {
        "id": ratio.id,
        "tenant_id": ratio.tenant_id,
        "class_id": ratio.class_id,
        "academic_year_id": ratio.academic_year_id,
        "max_children_per_caregiver": ratio.max_children_per_caregiver,
        "current_caregiver_count": ratio.current_caregiver_count,
        "max_capacity": ratio.max_children_per_caregiver * ratio.current_caregiver_count,
        "current_enrollment": 0,
        "is_compliant": True,
    }

"""
SIMS Plus - Admission Period Management Endpoints

Admin endpoints for creating and managing admission periods.
Requires authentication + admissions permissions.
"""

import math
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    AdmissionPeriodCreate,
    AdmissionPeriodListResponse,
    AdmissionPeriodResponse,
    AdmissionPeriodStatusUpdate,
    AdmissionPeriodUpdate,
    FormConfigResponse,
    FormConfigUpdate,
)
from app.services.admissions import AdmissionPeriodError, AdmissionPeriodService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/periods")


def _handle_error(e: AdmissionPeriodError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "PERIOD_OVERLAP": 409,
        "PERIOD_LOCKED": 409,
        "INVALID_DATES": 422,
        "INVALID_TRANSITION": 422,
        "INVALID_SCHEMA": 422,
        "VALIDATION_ERROR": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=AdmissionPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create admission period",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_period(
    data: AdmissionPeriodCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """
    Create a new admission period.

    Validates:
    - academic_year_id exists and belongs to tenant
    - target_classes are valid class IDs in the school
    - No overlapping periods for the same classes
    """
    service = AdmissionPeriodService(db)
    try:
        # Unpack Pydantic model fields into individual kwargs
        period = await service.create(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            name=data.name,
            academic_year_id=data.academic_year_id,
            start_date=data.start_date,
            end_date=data.end_date,
            description=data.description,
            application_fee_amount=float(data.application_fee_amount) if data.application_fee_amount else None,
            application_fee_required=data.application_fee_required,
            entrance_exam_required=data.entrance_exam_required,
            max_applications=data.max_applications,
            target_classes=data.target_classes,
            require_applicant_account=data.require_applicant_account,
        )
        return period
    except AdmissionPeriodError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=AdmissionPeriodListResponse,
    summary="List admission periods",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_periods(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    academic_year_id: UUID | None = Query(None),
) -> AdmissionPeriodListResponse:
    """List admission periods with optional filters."""
    service = AdmissionPeriodService(db)
    # list_periods returns (items, total) tuple
    items, total = await service.list_periods(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        status=status_filter,
        academic_year_id=academic_year_id,
        page=page,
        page_size=page_size,
    )
    return AdmissionPeriodListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{period_id}",
    response_model=AdmissionPeriodResponse,
    summary="Get admission period details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_period(
    period_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """Get admission period details including application count."""
    service = AdmissionPeriodService(db)
    try:
        return await service.get_period(
            tenant_id=UUID(user["tenant_id"]),
            period_id=period_id,
        )
    except AdmissionPeriodError as e:
        raise _handle_error(e)


@router.put(
    "/{period_id}",
    response_model=AdmissionPeriodResponse,
    summary="Update admission period",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_period(
    period_id: UUID,
    data: AdmissionPeriodUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """Update admission period. Only draft periods can be fully edited."""
    service = AdmissionPeriodService(db)
    try:
        # Unpack only the fields that were provided (exclude_unset)
        update_data = data.model_dump(exclude_unset=True)
        # Convert target_classes UUIDs if present
        if "target_classes" in update_data and update_data["target_classes"] is not None:
            update_data["target_classes"] = [
                UUID(str(c)) if not isinstance(c, UUID) else c
                for c in update_data["target_classes"]
            ]
        # Convert Decimal to float for fee amount
        if "application_fee_amount" in update_data and update_data["application_fee_amount"] is not None:
            update_data["application_fee_amount"] = float(update_data["application_fee_amount"])

        return await service.update(
            tenant_id=UUID(user["tenant_id"]),
            period_id=period_id,
            **update_data,
        )
    except AdmissionPeriodError as e:
        raise _handle_error(e)


@router.put(
    "/{period_id}/status",
    response_model=AdmissionPeriodResponse,
    summary="Change admission period status",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def change_period_status(
    period_id: UUID,
    data: AdmissionPeriodStatusUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """
    Change admission period status.
    Valid transitions: draft->open, open->closed, closed->archived.
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.update_status(
            tenant_id=UUID(user["tenant_id"]),
            period_id=period_id,
            new_status=data.status.value,
        )
    except AdmissionPeriodError as e:
        raise _handle_error(e)


@router.put(
    "/{period_id}/form-config",
    response_model=FormConfigResponse,
    summary="Update form configuration",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_form_config(
    period_id: UUID,
    data: FormConfigUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> FormConfigResponse:
    """
    Update the custom form schema and required documents for a period.
    Creates the form config if it doesn't exist (upsert).
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.update_form_config(
            tenant_id=UUID(user["tenant_id"]),
            period_id=period_id,
            form_schema=data.form_schema,
            required_documents=data.required_documents,
        )
    except AdmissionPeriodError as e:
        raise _handle_error(e)

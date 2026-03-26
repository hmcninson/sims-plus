"""
SIMS Plus - Application Management Endpoints

Admin endpoints for reviewing and managing applications.
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
    ApplicationListResponse,
    ApplicationNoteCreate,
    ApplicationNoteResponse,
    ApplicationResponse,
    ApplicationStatusChangeRequest,
    ExamWaiverRequest,
    FeeWaiverRequest,
)
from app.services.admissions import ApplicationService, ApplicationServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/applications")


def _handle_error(e: ApplicationServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_TRANSITION": 422,
        "VALIDATION_ERROR": 422,
        "FEE_REQUIRED": 422,
        "EXAM_REQUIRED": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.get(
    "",
    response_model=ApplicationListResponse,
    summary="List applications",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_applications(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    admission_period_id: UUID | None = Query(None),
    target_class_id: UUID | None = Query(None),
    search: str | None = Query(None, max_length=100),
    sort_by: str = Query(
        "created_at",
        pattern="^(created_at|submitted_at|applicant_last_name|status)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> ApplicationListResponse:
    """
    List applications with filtering, search, sort, and pagination.

    Search queries applicant_first_name, applicant_last_name, tracking_code.
    """
    service = ApplicationService(db)
    # list_applications returns (items, total) tuple
    items, total = await service.list_applications(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        status=status_filter,
        admission_period_id=admission_period_id,
        target_class_id=target_class_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ApplicationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get application details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_application(
    application_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Get full application detail including guardians, documents,
    payments, notes, status history, exam results, and decision.
    """
    service = ApplicationService(db)
    try:
        return await service.get_application(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{application_id}/status",
    response_model=ApplicationResponse,
    summary="Change application status",
    dependencies=[Depends(require_permissions("admissions.review"))],
)
async def change_application_status(
    application_id: UUID,
    data: ApplicationStatusChangeRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Change application status with validation against the status machine.
    Records transition in application_status_history.
    Sends notification on relevant transitions (offered, etc.).
    """
    service = ApplicationService(db)
    try:
        return await service.transition_status(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            new_status=data.status.value,
            changed_by=UUID(user["user_id"]),
            reason=data.reason,
        )
    except ApplicationServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{application_id}/notes",
    response_model=ApplicationNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add note to application",
    dependencies=[Depends(require_permissions("admissions.review"))],
)
async def add_note(
    application_id: UUID,
    data: ApplicationNoteCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationNoteResponse:
    """Add an internal note to an application."""
    service = ApplicationService(db)
    try:
        return await service.add_note(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            author_id=UUID(user["user_id"]),
            content=data.content,
            is_internal=data.is_internal,
        )
    except ApplicationServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{application_id}/waive-fee",
    response_model=ApplicationResponse,
    summary="Waive application fee",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def waive_fee(
    application_id: UUID,
    data: FeeWaiverRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Waive the application fee. Sets fee_waived=true.
    If application is in DRAFT status and payment was the only blocker,
    automatically transitions to SUBMITTED.
    Records the waiver reason in status_history.
    """
    service = ApplicationService(db)
    try:
        return await service.waive_fee(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{application_id}/waive-exam",
    response_model=ApplicationResponse,
    summary="Waive entrance exam",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def waive_exam(
    application_id: UUID,
    data: ExamWaiverRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Waive the entrance exam. Sets exam_waived=true.
    Allows application to skip EXAM_SCHEDULED/EXAM_COMPLETED states.
    Records the waiver reason in status_history.
    """
    service = ApplicationService(db)
    try:
        return await service.waive_exam(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
    except ApplicationServiceError as e:
        raise _handle_error(e)

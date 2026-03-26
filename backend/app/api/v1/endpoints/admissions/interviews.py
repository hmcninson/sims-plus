"""
SIMS Plus - Interview & Screening Management Endpoints

Admin endpoints for scheduling interviews, recording feedback,
and managing screening checklists for admission applications.
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
from app.schemas.interview import (
    InterviewCreate,
    InterviewFeedback,
    InterviewListResponse,
    InterviewResponse,
    InterviewUpdate,
    ScreeningItemBulkCreate,
    ScreeningItemComplete,
    ScreeningItemCreate,
    ScreeningItemResponse,
    ScreeningProgressResponse,
)
from app.services.admissions import InterviewService, InterviewServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/interviews")


def _handle_error(e: InterviewServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "APP_NOT_FOUND": 404,
        "TERMINAL_STATUS": 422,
        "INTERVIEW_EXISTS": 409,
        "INTERVIEWER_CONFLICT": 409,
        "NOT_SCHEDULED": 422,
        "INVALID_STATUS": 422,
        "INVALID_TRANSITION": 422,
        "DUPLICATE_ITEM": 409,
        "ALREADY_COMPLETED": 409,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


# =========================
# Interview Endpoints
# =========================


@router.post(
    "",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule interview",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def schedule_interview(
    data: InterviewCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InterviewResponse:
    """
    Schedule an interview for an application.

    Validates:
    - Application exists and is not in a terminal status
    - No existing active interview for this application
    - Interviewer has no overlapping interview at same date/time
    """
    service = InterviewService(db)
    try:
        interview = await service.schedule(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            application_id=data.application_id,
            interviewer_id=data.interviewer_id,
            scheduled_date=data.scheduled_date,
            scheduled_time=data.scheduled_time,
            duration_minutes=data.duration_minutes,
            venue=data.venue,
        )
        return interview
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=InterviewListResponse,
    summary="List interviews",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_interviews(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    interviewer_id: UUID | None = Query(None),
    date_from: str | None = Query(None, description="YYYY-MM-DD"),
    date_to: str | None = Query(None, description="YYYY-MM-DD"),
) -> InterviewListResponse:
    """List interviews with optional filters for status, interviewer, and date range."""
    from datetime import date as date_cls

    # Parse date strings if provided
    parsed_date_from = None
    parsed_date_to = None
    if date_from:
        try:
            parsed_date_from = date_cls.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid date_from format. Use YYYY-MM-DD.",
            )
    if date_to:
        try:
            parsed_date_to = date_cls.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid date_to format. Use YYYY-MM-DD.",
            )

    service = InterviewService(db)
    items, total = await service.list_interviews(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        status=status_filter,
        interviewer_id=interviewer_id,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=page,
        page_size=page_size,
    )
    return InterviewListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{interview_id}",
    response_model=InterviewResponse,
    summary="Get interview detail",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_interview(
    interview_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InterviewResponse:
    """Get interview details by ID."""
    service = InterviewService(db)
    try:
        return await service.get(
            tenant_id=UUID(user["tenant_id"]),
            interview_id=interview_id,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{interview_id}",
    response_model=InterviewResponse,
    summary="Reschedule/update interview",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def update_interview(
    interview_id: UUID,
    data: InterviewUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InterviewResponse:
    """
    Update interview details (reschedule).

    Only scheduled or rescheduled interviews can be updated.
    If date/time changes, status transitions to 'rescheduled' and
    interviewer overlap is re-checked.
    """
    service = InterviewService(db)
    try:
        # Only pass non-None fields to the service
        update_data = data.model_dump(exclude_unset=True)
        return await service.update(
            tenant_id=UUID(user["tenant_id"]),
            interview_id=interview_id,
            **update_data,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{interview_id}/feedback",
    response_model=InterviewResponse,
    summary="Record interview feedback",
    dependencies=[Depends(require_permissions("admissions.review"))],
)
async def record_feedback(
    interview_id: UUID,
    data: InterviewFeedback,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InterviewResponse:
    """
    Record interview outcome and scoring.

    Sets interview status to 'completed' or 'no_show'.
    If scoring_criteria is provided, auto-calculates total score
    from per-criterion values. Otherwise uses explicit score/max_score.
    """
    service = InterviewService(db)
    try:
        return await service.record_feedback(
            tenant_id=UUID(user["tenant_id"]),
            interview_id=interview_id,
            status=data.status,
            feedback=data.feedback,
            score=data.score,
            max_score=data.max_score,
            scoring_criteria=data.scoring_criteria,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.delete(
    "/{interview_id}",
    response_model=InterviewResponse,
    summary="Cancel interview",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def cancel_interview(
    interview_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InterviewResponse:
    """Cancel an interview. Only scheduled/rescheduled interviews can be cancelled."""
    service = InterviewService(db)
    try:
        return await service.cancel(
            tenant_id=UUID(user["tenant_id"]),
            interview_id=interview_id,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


# =========================
# Screening Checklist Endpoints
# =========================


@router.post(
    "/applications/{application_id}/screening",
    response_model=ScreeningItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add screening item",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def create_screening_item(
    application_id: UUID,
    data: ScreeningItemCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ScreeningItemResponse:
    """Add a screening checklist item to an application."""
    service = InterviewService(db)
    try:
        return await service.create_screening_item(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            item_name=data.item_name,
            item_category=data.item_category,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/screening/bulk",
    response_model=list[ScreeningItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk add screening items",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def bulk_create_screening_items(
    application_id: UUID,
    data: ScreeningItemBulkCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ScreeningItemResponse]:
    """
    Bulk-add screening items to an application (apply a template).

    Skips duplicates silently. Max 50 items per request.
    """
    service = InterviewService(db)
    try:
        items_dicts = [item.model_dump() for item in data.items]
        return await service.bulk_create_screening_items(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            items=items_dicts,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/screening/{item_id}/complete",
    response_model=ScreeningItemResponse,
    summary="Complete screening item",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def complete_screening_item(
    item_id: UUID,
    data: ScreeningItemComplete,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ScreeningItemResponse:
    """Mark a screening item as completed."""
    service = InterviewService(db)
    try:
        return await service.complete_screening_item(
            tenant_id=UUID(user["tenant_id"]),
            item_id=item_id,
            user_id=UUID(user["user_id"]),
            notes=data.notes,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)


@router.get(
    "/applications/{application_id}/screening",
    response_model=ScreeningProgressResponse,
    summary="Get screening progress",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_screening_progress(
    application_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ScreeningProgressResponse:
    """Get screening completion progress for an application."""
    service = InterviewService(db)
    try:
        return await service.get_screening_progress(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
    except InterviewServiceError as e:
        raise _handle_error(e)

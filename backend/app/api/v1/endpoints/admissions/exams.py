"""
SIMS Plus - Entrance Exam Management Endpoints

Admin endpoints for creating and managing entrance exam sessions,
registering applicants, and submitting exam results.
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
    EntranceExamCreate,
    EntranceExamListResponse,
    EntranceExamResponse,
    EntranceExamUpdate,
    ExamRegistrationRequest,
    ExamRegistrationResponse,
    ExamResultResponse,
    ExamResultsSubmitRequest,
)
from app.services.admissions import EntranceExamService, EntranceExamServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/exams")


def _handle_error(e: EntranceExamServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "PERIOD_NOT_FOUND": 404,
        "PERIOD_ARCHIVED": 409,
        "INVALID_CAPACITY": 422,
        "INVALID_TRANSITION": 422,
        "EXAM_NOT_SCHEDULED": 409,
        "EXAM_NOT_ACTIVE": 409,
        "VALIDATION_ERROR": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=EntranceExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create entrance exam session",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_exam(
    data: EntranceExamCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EntranceExamResponse:
    """Create an entrance exam session for an admission period."""
    service = EntranceExamService(db)
    try:
        # Unpack Pydantic model fields into individual kwargs
        return await service.create_exam(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            admission_period_id=data.admission_period_id,
            name=data.name,
            exam_date=data.exam_date,
            start_time=data.start_time,
            end_time=data.end_time,
            venue=data.venue,
            capacity=data.capacity,
            instructions=data.instructions,
        )
    except EntranceExamServiceError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=EntranceExamListResponse,
    summary="List entrance exams",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_exams(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admission_period_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> EntranceExamListResponse:
    """List entrance exam sessions with optional filters."""
    service = EntranceExamService(db)
    # list_exams returns (items, total) tuple
    items, total = await service.list_exams(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        admission_period_id=admission_period_id,
        page=page,
        page_size=page_size,
    )
    return EntranceExamListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{exam_id}",
    response_model=EntranceExamResponse,
    summary="Get entrance exam details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_exam(
    exam_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EntranceExamResponse:
    """Get exam details including registration and attendance counts."""
    service = EntranceExamService(db)
    try:
        return await service.get_exam(
            tenant_id=UUID(user["tenant_id"]),
            exam_id=exam_id,
        )
    except EntranceExamServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{exam_id}",
    response_model=EntranceExamResponse,
    summary="Update entrance exam",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_exam(
    exam_id: UUID,
    data: EntranceExamUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EntranceExamResponse:
    """Update exam details. Cannot update completed/cancelled exams."""
    service = EntranceExamService(db)
    try:
        # If status change is requested, use update_status
        if data.status is not None:
            return await service.update_status(
                tenant_id=UUID(user["tenant_id"]),
                exam_id=exam_id,
                new_status=data.status.value,
            )
        # For other field updates, the service doesn't have a generic update yet
        # For now, only status updates are supported via this endpoint
        # Return the current exam state
        return await service.get_exam(
            tenant_id=UUID(user["tenant_id"]),
            exam_id=exam_id,
        )
    except EntranceExamServiceError as e:
        raise _handle_error(e)


@router.get(
    "/{exam_id}/registrations",
    response_model=list[ExamRegistrationResponse],
    summary="List exam registrations",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_registrations(
    exam_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ExamRegistrationResponse]:
    """List all registrations for an exam session."""
    from sqlalchemy import select
    from app.models.admissions import EntranceExamRegistration

    result = await db.execute(
        select(EntranceExamRegistration).where(
            EntranceExamRegistration.entrance_exam_id == exam_id,
            EntranceExamRegistration.tenant_id == UUID(user["tenant_id"]),
            EntranceExamRegistration.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


@router.get(
    "/{exam_id}/results",
    response_model=list[ExamResultResponse],
    summary="List exam results",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_results(
    exam_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ExamResultResponse]:
    """List all results for an exam session."""
    from sqlalchemy import select
    from app.models.admissions import EntranceExamResult

    result = await db.execute(
        select(EntranceExamResult).where(
            EntranceExamResult.entrance_exam_id == exam_id,
            EntranceExamResult.tenant_id == UUID(user["tenant_id"]),
            EntranceExamResult.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


@router.put(
    "/{exam_id}/registrations/{registration_id}/attendance",
    response_model=ExamRegistrationResponse,
    summary="Mark exam attendance",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def mark_attendance(
    exam_id: UUID,
    registration_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExamRegistrationResponse:
    """Toggle attendance for a single registration."""
    from sqlalchemy import select
    from app.models.admissions import EntranceExamRegistration

    result = await db.execute(
        select(EntranceExamRegistration).where(
            EntranceExamRegistration.id == registration_id,
            EntranceExamRegistration.entrance_exam_id == exam_id,
            EntranceExamRegistration.tenant_id == UUID(user["tenant_id"]),
            EntranceExamRegistration.deleted_at.is_(None),
        )
    )
    reg = result.scalar_one_or_none()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
    reg.attended = not reg.attended
    await db.flush()
    await db.refresh(reg)
    return reg


@router.post(
    "/{exam_id}/register",
    response_model=ExamRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register applicants to exam",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def register_applicants(
    exam_id: UUID,
    data: ExamRegistrationRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExamRegistrationResponse:
    """
    Register applicants to an exam session.
    Validates capacity is not exceeded. Auto-assigns seat numbers.
    Updates application status to EXAM_SCHEDULED.
    """
    service = EntranceExamService(db)
    try:
        # register_applicants returns a dict with registered_count, already_registered_count, errors
        result = await service.register_applicants(
            tenant_id=UUID(user["tenant_id"]),
            exam_id=exam_id,
            application_ids=data.application_ids,
        )
        return result
    except EntranceExamServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{exam_id}/results",
    response_model=ExamResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit exam results",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def submit_results(
    exam_id: UUID,
    data: ExamResultsSubmitRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ExamResultResponse:
    """
    Submit or update exam results for registered applicants.
    Updates application status to EXAM_COMPLETED.
    Upserts results (create if new, update if existing).
    """
    service = EntranceExamService(db)
    try:
        # record_results expects list[dict], returns int (count)
        results_dicts = [r.model_dump() for r in data.results]
        # Convert UUID application_id to string for compatibility
        for r in results_dicts:
            r["application_id"] = str(r["application_id"])
            r["score"] = float(r["score"])
            r["max_score"] = float(r["max_score"])

        count = await service.record_results(
            tenant_id=UUID(user["tenant_id"]),
            exam_id=exam_id,
            results=results_dicts,
            scored_by=UUID(user["user_id"]),
        )
        return {"results_recorded": count}
    except EntranceExamServiceError as e:
        raise _handle_error(e)

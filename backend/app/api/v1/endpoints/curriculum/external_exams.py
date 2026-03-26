"""
SIMS Plus - External Exam Endpoints

CRUD endpoints for external examination registrations (WAEC, Cambridge,
Edexcel, IB, etc.) and CSV-based results import/export.
"""

import math
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.deps import DatabaseSession, SchoolCtx, require_permissions
from app.schemas.curriculum import (
    BulkExternalExamRegistrationCreate,
    ExternalExamRegistrationCreate,
    ExternalExamRegistrationListResponse,
    ExternalExamRegistrationResponse,
    ExternalExamRegistrationUpdate,
    ResultsImportCommit,
    ResultsImportPreview,
)
from app.services.curriculum import CurriculumServiceError, ExternalExamService

router = APIRouter(
    prefix="/external-exams",
    tags=["External Exams"],
)

# Maximum upload size for CSV results import (5 MB)
_MAX_CSV_SIZE_BYTES = 5 * 1024 * 1024


# =========================
# Error Handling
# =========================

_STATUS_MAP = {
    "not_found": 404,
    "immutable_field": 422,
    "bulk_limit_exceeded": 422,
    "plan_limit": 403,
}


def _handle_error(e: CurriculumServiceError) -> None:
    """Convert service errors to appropriate HTTP responses."""
    raise HTTPException(
        status_code=_STATUS_MAP.get(e.code, 400),
        detail=e.message,
    )


# =========================
# Registration CRUD
# =========================


@router.post(
    "/registrations",
    response_model=ExternalExamRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create external exam registration",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_registration(
    data: ExternalExamRegistrationCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Register a student for an external examination."""
    service = ExternalExamService(db)
    try:
        registration = await service.create_registration(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            data=data.model_dump(),
        )
        return registration
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/registrations",
    response_model=ExternalExamRegistrationListResponse,
    summary="List external exam registrations",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_registrations(
    db: DatabaseSession,
    school: SchoolCtx,
    student_id: UUID | None = Query(None, description="Filter by student"),
    exam_board: str | None = Query(None, description="Filter by exam board"),
    exam_session: str | None = Query(None, description="Filter by exam session"),
    registration_status: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List external exam registrations with optional filters."""
    service = ExternalExamService(db)
    try:
        items, total = await service.list_registrations(
            tenant_id=school.tenant_id,
            student_id=student_id,
            exam_board=exam_board,
            exam_session=exam_session,
            status=registration_status,
            page=page,
            page_size=page_size,
        )
        return ExternalExamRegistrationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/registrations/{registration_id}",
    response_model=ExternalExamRegistrationResponse,
    summary="Get external exam registration",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_registration(
    registration_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Get a single external exam registration by ID."""
    service = ExternalExamService(db)
    try:
        registration = await service.get_registration(
            tenant_id=school.tenant_id,
            registration_id=registration_id,
        )
        return registration
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/registrations/{registration_id}",
    response_model=ExternalExamRegistrationResponse,
    summary="Update external exam registration",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_registration(
    registration_id: UUID,
    data: ExternalExamRegistrationUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """
    Update an external exam registration.

    Identity fields (student_id, exam_board, exam_session) cannot be changed.
    """
    service = ExternalExamService(db)
    try:
        registration = await service.update_registration(
            tenant_id=school.tenant_id,
            registration_id=registration_id,
            data=data.model_dump(exclude_unset=True),
        )
        return registration
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/registrations/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete external exam registration",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_registration(
    registration_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Soft delete an external exam registration."""
    service = ExternalExamService(db)
    try:
        await service.soft_delete_registration(
            tenant_id=school.tenant_id,
            registration_id=registration_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Bulk Registration
# =========================


@router.post(
    "/registrations/bulk",
    response_model=list[ExternalExamRegistrationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk register students for external exams",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def bulk_register(
    data: BulkExternalExamRegistrationCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Register multiple students for external exams in a single request (max 200)."""
    service = ExternalExamService(db)
    try:
        registrations = await service.bulk_register(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            registrations_data=[r.model_dump() for r in data.registrations],
        )
        return registrations
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Results Import
# =========================


@router.post(
    "/results/import",
    response_model=ResultsImportPreview | ResultsImportCommit,
    summary="Import exam results from CSV",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def import_results_csv(
    file: UploadFile,
    db: DatabaseSession,
    school: SchoolCtx,
    exam_board: str = Query(
        ...,
        description="Exam board for matching registrations",
    ),
    exam_session: str = Query(
        ...,
        description="Exam session for matching registrations",
    ),
    dry_run: bool = Query(
        True,
        description="Preview results without saving (default: true)",
    ),
):
    """
    Import exam results from a CSV file.

    Supports WAEC format (CandidateNumber,SubjectCode,SubjectName,Grade,Score)
    and Cambridge format (CandidateNumber,CenterNumber,ComponentCode,
    ComponentName,Grade,Mark,MaxMark).

    Use dry_run=true (default) to preview matches before committing.
    """
    # Validate file size to prevent memory exhaustion
    content = await file.read()
    if len(content) > _MAX_CSV_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {_MAX_CSV_SIZE_BYTES // (1024 * 1024)}MB",
        )

    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be UTF-8 encoded CSV",
        )

    service = ExternalExamService(db)
    try:
        result = await service.import_results_csv(
            tenant_id=school.tenant_id,
            exam_board=exam_board,
            exam_session=exam_session,
            csv_content=csv_text,
            dry_run=dry_run,
        )

        if dry_run:
            return ResultsImportPreview(
                total_rows=result.total_rows,
                matched=result.matched,
                unmatched=result.unmatched,
                errors=result.errors,
                preview_rows=result.preview_rows,
            )
        else:
            return ResultsImportCommit(
                imported=result.matched,
                skipped=result.unmatched,
                errors=result.errors,
            )
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Export
# =========================


@router.get(
    "/export",
    summary="Export external exam registration data",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def export_registrations(
    db: DatabaseSession,
    school: SchoolCtx,
    exam_board: str = Query(
        ...,
        description="Exam board (waec, cambridge_international, edexcel, or ibo)",
    ),
    exam_session: str = Query(..., description="Exam session to export"),
):
    """
    Export external exam registration data for a specific board and session.

    Returns structured data suitable for downstream CSV generation or
    submission to the exam board.
    """
    service = ExternalExamService(db)
    try:
        if exam_board == "waec":
            data = await service.export_waec(
                tenant_id=school.tenant_id,
                exam_session=exam_session,
            )
        elif exam_board == "cambridge_international":
            data = await service.export_cambridge(
                tenant_id=school.tenant_id,
                exam_session=exam_session,
            )
        elif exam_board == "edexcel":
            data = await service.export_edexcel(
                tenant_id=school.tenant_id,
                exam_session=exam_session,
            )
        elif exam_board == "ibo":
            data = await service.export_ib(
                tenant_id=school.tenant_id,
                exam_session=exam_session,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Export supports 'waec', 'cambridge_international', 'edexcel', and 'ibo' boards",
            )
        return data
    except CurriculumServiceError as e:
        _handle_error(e)

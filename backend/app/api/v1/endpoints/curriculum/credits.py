"""
SIMS Plus - Credit & GPA Endpoints

Endpoints for student credit accumulation, GPA calculation,
transcript generation, and credit recalculation.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DatabaseSession, SchoolCtx, require_permissions
from app.schemas.curriculum import (
    StudentCreditListResponse,
    StudentCreditRecordCreate,
    StudentCreditResponse,
    StudentGPAResponse,
    TranscriptResponse,
)
from app.services.curriculum import CurriculumServiceError
from app.services.curriculum.credit_service import CreditService

router = APIRouter(prefix="/credits", tags=["Credits & GPA"])


# =========================
# Error Handling
# =========================

_STATUS_MAP = {
    "not_found": 404,
    "invalid_operation": 422,
    "validation_error": 422,
    "plan_limit": 403,
}


def _handle_error(e: CurriculumServiceError) -> None:
    """Convert service errors to appropriate HTTP responses."""
    raise HTTPException(
        status_code=_STATUS_MAP.get(e.code, 400),
        detail=e.message,
    )


# =========================
# Credit CRUD
# =========================


@router.post(
    "",
    response_model=StudentCreditResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record student credit",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def record_credit(
    data: StudentCreditRecordCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Create or update a credit record for a student (upsert semantics)."""
    service = CreditService(db)
    try:
        record = await service.record_credit(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            data=data,
        )
        return record
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "",
    response_model=StudentCreditListResponse,
    summary="List student credits",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_credits(
    db: DatabaseSession,
    school: SchoolCtx,
    student_id: UUID = Query(..., description="Student ID"),
    profile_id: UUID = Query(..., description="Curriculum profile ID"),
    academic_year_id: UUID | None = Query(None, description="Filter by academic year"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Get paginated credit records for a student under a curriculum profile."""
    service = CreditService(db)
    try:
        records, total = await service.get_student_credits(
            tenant_id=school.tenant_id,
            student_id=student_id,
            profile_id=profile_id,
            academic_year_id=academic_year_id,
            page=page,
            page_size=page_size,
        )
        return StudentCreditListResponse(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# GPA Calculation
# =========================


@router.get(
    "/gpa/{student_id}",
    response_model=StudentGPAResponse,
    summary="Get student GPA",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_student_gpa(
    student_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
    profile_id: UUID = Query(..., description="Curriculum profile ID"),
    academic_year_id: UUID | None = Query(None, description="Filter by academic year"),
    term_id: UUID | None = Query(None, description="Filter by term"),
):
    """
    Calculate GPA for a student.

    Returns term-specific and cumulative GPAs with honor roll status.
    Unweighted GPA uses raw grade points; weighted GPA applies AP (+1.0)
    and Honors (+0.5) bonuses.
    """
    service = CreditService(db)
    try:
        gpa_data = await service.get_student_gpa(
            tenant_id=school.tenant_id,
            student_id=student_id,
            profile_id=profile_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
        )
        return StudentGPAResponse(**gpa_data)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Transcript
# =========================


@router.get(
    "/transcript/{student_id}",
    response_model=TranscriptResponse,
    summary="Get student transcript data",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_transcript(
    student_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
    profile_id: UUID = Query(..., description="Curriculum profile ID"),
):
    """
    Generate full transcript data for a student.

    Returns academic records grouped by year/term with cumulative GPA,
    credit totals, and honor designations.
    """
    service = CreditService(db)
    try:
        transcript = await service.generate_transcript_data(
            tenant_id=school.tenant_id,
            student_id=student_id,
            profile_id=profile_id,
            school_id=school.school_id,
        )
        return TranscriptResponse(**transcript)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Recalculation
# =========================


@router.post(
    "/recalculate/{student_id}",
    summary="Recalculate student credits",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def recalculate_credits(
    student_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
    profile_id: UUID = Query(..., description="Curriculum profile ID"),
):
    """
    Recalculate all credit records for a student from term reports.

    Deletes existing records and rebuilds from exam score data.
    """
    service = CreditService(db)
    try:
        count = await service.recalculate_credits(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            student_id=student_id,
            profile_id=profile_id,
        )
        return {"records_updated": count}
    except CurriculumServiceError as e:
        _handle_error(e)

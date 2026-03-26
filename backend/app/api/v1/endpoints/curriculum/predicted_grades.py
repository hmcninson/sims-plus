"""
SIMS Plus - Predicted Grade Endpoints

CRUD endpoints for teacher-predicted and target grades,
used by Cambridge and IB schools for university applications.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import DatabaseSession, SchoolCtx, ValidatedUser, require_permissions
from app.schemas.curriculum import (
    BulkPredictedGradeCreate,
    PredictedGradeCreate,
    PredictedGradeListResponse,
    PredictedGradeResponse,
    PredictedGradeUpdate,
)
from app.services.curriculum import CurriculumServiceError
from app.services.curriculum.predicted_grade_service import PredictedGradeService

router = APIRouter(prefix="/predicted-grades", tags=["Predicted Grades"])


# =========================
# Error Handling
# =========================

_STATUS_MAP = {
    "not_found": 404,
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
# CRUD
# =========================


@router.post(
    "",
    response_model=PredictedGradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create predicted grade",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_prediction(
    data: PredictedGradeCreate,
    db: DatabaseSession,
    school: SchoolCtx,
    user: ValidatedUser,
):
    """Create a new predicted grade for a student."""
    service = PredictedGradeService(db)
    try:
        prediction = await service.create_prediction(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            user_id=UUID(user["user_id"]),
            data=data,
        )
        return prediction
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "",
    response_model=PredictedGradeListResponse,
    summary="List predicted grades",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_predictions(
    db: DatabaseSession,
    school: SchoolCtx,
    student_id: UUID | None = Query(None, description="Filter by student"),
    subject_id: UUID | None = Query(None, description="Filter by subject"),
    academic_year_id: UUID | None = Query(None, description="Filter by academic year"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List predicted grades with optional filters."""
    service = PredictedGradeService(db)
    try:
        predictions, total = await service.get_predictions(
            tenant_id=school.tenant_id,
            student_id=student_id,
            subject_id=subject_id,
            academic_year_id=academic_year_id,
            page=page,
            page_size=page_size,
        )
        return PredictedGradeListResponse(
            items=predictions,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/{prediction_id}",
    response_model=PredictedGradeResponse,
    summary="Get predicted grade",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_prediction(
    prediction_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Get a single predicted grade by ID."""
    service = PredictedGradeService(db)
    try:
        prediction = await service.get_prediction(
            tenant_id=school.tenant_id,
            prediction_id=prediction_id,
        )
        return prediction
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/{prediction_id}",
    response_model=PredictedGradeResponse,
    summary="Update predicted grade",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_prediction(
    prediction_id: UUID,
    data: PredictedGradeUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
    user: ValidatedUser,
):
    """Update an existing predicted grade (mutable fields only)."""
    service = PredictedGradeService(db)
    try:
        prediction = await service.update_prediction(
            tenant_id=school.tenant_id,
            prediction_id=prediction_id,
            user_id=UUID(user["user_id"]),
            data=data,
        )
        return prediction
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/{prediction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete predicted grade",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_prediction(
    prediction_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Soft delete a predicted grade."""
    service = PredictedGradeService(db)
    try:
        await service.delete_prediction(
            tenant_id=school.tenant_id,
            prediction_id=prediction_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Bulk Operations
# =========================


@router.post(
    "/bulk",
    response_model=list[PredictedGradeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create predicted grades",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def bulk_create_predictions(
    data: BulkPredictedGradeCreate,
    db: DatabaseSession,
    school: SchoolCtx,
    user: ValidatedUser,
):
    """
    Bulk create predicted grades (up to 200 at a time).

    All referenced students and subjects are validated before any
    records are created.
    """
    service = PredictedGradeService(db)
    try:
        predictions = await service.bulk_create_predictions(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            user_id=UUID(user["user_id"]),
            data=data,
        )
        return predictions
    except CurriculumServiceError as e:
        _handle_error(e)

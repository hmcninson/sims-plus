"""
SIMS Plus - Grade Equivalency Endpoints

CRUD endpoints for cross-curriculum grade mappings and grade conversion.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import DatabaseSession, SchoolCtx, require_permissions
from app.schemas.curriculum import (
    GradeConvertRequest,
    GradeEquivalencyCreate,
    GradeEquivalencyListResponse,
    GradeEquivalencyResponse,
    GradeEquivalencyUpdate,
)
from app.services.curriculum import CurriculumServiceError, GradeEquivalencyService

router = APIRouter(prefix="/grade-equivalencies", tags=["Grade Equivalencies"])


# =========================
# Error Handling
# =========================

_STATUS_MAP = {
    "not_found": 404,
    "self_mapping": 422,
    "duplicate": 409,
    "plan_limit": 403,
}


def _handle_error(e: CurriculumServiceError) -> None:
    """Convert service errors to appropriate HTTP responses."""
    raise HTTPException(
        status_code=_STATUS_MAP.get(e.code, 400),
        detail=e.message,
    )


# =========================
# Equivalency CRUD
# =========================


@router.post(
    "",
    response_model=list[GradeEquivalencyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create grade equivalencies",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_equivalency(
    data: GradeEquivalencyCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Create a batch of grade equivalency mappings between two grading scales."""
    service = GradeEquivalencyService(db)
    try:
        equivalencies = await service.create_equivalency(
            data, tenant_id=school.tenant_id, school_id=school.school_id
        )
        return equivalencies
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "",
    response_model=GradeEquivalencyListResponse,
    summary="List grade equivalencies",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_equivalencies(
    db: DatabaseSession,
    school: SchoolCtx,
    source_scale_id: UUID | None = Query(None, description="Filter by source grading scale"),
    target_scale_id: UUID | None = Query(None, description="Filter by target grading scale"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List grade equivalencies with optional scale filters."""
    service = GradeEquivalencyService(db)
    try:
        equivalencies, total = await service.get_equivalencies(
            tenant_id=school.tenant_id,
            source_scale_id=source_scale_id,
            target_scale_id=target_scale_id,
            page=page,
            page_size=page_size,
        )
        return GradeEquivalencyListResponse(
            items=equivalencies,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/{equivalency_id}",
    response_model=GradeEquivalencyResponse,
    summary="Get grade equivalency",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_equivalency(
    equivalency_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Get a single grade equivalency by ID."""
    service = GradeEquivalencyService(db)
    try:
        equivalency = await service.get_equivalency(
            equivalency_id, tenant_id=school.tenant_id
        )
        return equivalency
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/{equivalency_id}",
    response_model=GradeEquivalencyResponse,
    summary="Update grade equivalency",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_equivalency(
    equivalency_id: UUID,
    data: GradeEquivalencyUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Update an existing grade equivalency (notes only)."""
    service = GradeEquivalencyService(db)
    try:
        equivalency = await service.update_equivalency(
            equivalency_id, data, tenant_id=school.tenant_id
        )
        return equivalency
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/{equivalency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete grade equivalency",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_equivalency(
    equivalency_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Hard delete a grade equivalency."""
    service = GradeEquivalencyService(db)
    try:
        await service.delete_equivalency(
            equivalency_id, tenant_id=school.tenant_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Grade Conversion
# =========================


@router.post(
    "/convert",
    response_model=GradeEquivalencyResponse | None,
    summary="Convert grade between scales",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def convert_grade(
    data: GradeConvertRequest,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """
    Look up the equivalent grade in a target grading scale.

    Returns the equivalency mapping if found, null otherwise.
    """
    service = GradeEquivalencyService(db)
    try:
        equivalency = await service.convert_grade(
            source_grade_id=data.source_grade_id,
            source_scale_id=data.source_grading_scale_id,
            target_scale_id=data.target_grading_scale_id,
            tenant_id=school.tenant_id,
        )
        return equivalency
    except CurriculumServiceError as e:
        _handle_error(e)

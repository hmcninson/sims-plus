"""
SIMS Plus - Subject Curriculum Mapping Endpoints

CRUD endpoints for mapping internal subjects to curriculum-specific
codes, names, levels, credits, and coefficients.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import DatabaseSession, SchoolCtx, require_permissions
from app.schemas.curriculum import (
    SubjectCurriculumMappingCreate,
    SubjectCurriculumMappingListResponse,
    SubjectCurriculumMappingResponse,
    SubjectCurriculumMappingUpdate,
)
from app.services.curriculum import CurriculumServiceError, SubjectMappingService

router = APIRouter(prefix="/subject-mappings", tags=["Subject Mappings"])


# =========================
# Error Handling
# =========================

_STATUS_MAP = {
    "not_found": 404,
    "duplicate": 409,
}


def _handle_error(e: CurriculumServiceError) -> None:
    """Convert service errors to appropriate HTTP responses."""
    raise HTTPException(
        status_code=_STATUS_MAP.get(e.code, 400),
        detail=e.message,
    )


# =========================
# Subject Mapping CRUD
# =========================


@router.post(
    "",
    response_model=SubjectCurriculumMappingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create subject mapping",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_mapping(
    data: SubjectCurriculumMappingCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Create a subject-to-curriculum mapping."""
    service = SubjectMappingService(db)
    try:
        mapping = await service.create_mapping(
            data, tenant_id=school.tenant_id, school_id=school.school_id
        )
        return mapping
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "",
    response_model=SubjectCurriculumMappingListResponse,
    summary="List subject mappings",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_mappings(
    db: DatabaseSession,
    school: SchoolCtx,
    curriculum_profile_id: UUID | None = Query(None, description="Filter by curriculum profile"),
    subject_id: UUID | None = Query(None, description="Filter by subject"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List subject-to-curriculum mappings with optional filters."""
    service = SubjectMappingService(db)
    try:
        mappings, total = await service.get_mappings(
            tenant_id=school.tenant_id,
            curriculum_profile_id=curriculum_profile_id,
            subject_id=subject_id,
            page=page,
            page_size=page_size,
        )
        return SubjectCurriculumMappingListResponse(
            items=mappings,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/{mapping_id}",
    response_model=SubjectCurriculumMappingResponse,
    summary="Get subject mapping",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_mapping(
    mapping_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Get a single subject-to-curriculum mapping by ID."""
    service = SubjectMappingService(db)
    try:
        mapping = await service.get_mapping(
            mapping_id, tenant_id=school.tenant_id
        )
        return mapping
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/{mapping_id}",
    response_model=SubjectCurriculumMappingResponse,
    summary="Update subject mapping",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_mapping(
    mapping_id: UUID,
    data: SubjectCurriculumMappingUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Update an existing subject-to-curriculum mapping."""
    service = SubjectMappingService(db)
    try:
        mapping = await service.update_mapping(
            mapping_id, data, tenant_id=school.tenant_id
        )
        return mapping
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete subject mapping",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_mapping(
    mapping_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Hard delete a subject-to-curriculum mapping."""
    service = SubjectMappingService(db)
    try:
        await service.delete_mapping(
            mapping_id, tenant_id=school.tenant_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)

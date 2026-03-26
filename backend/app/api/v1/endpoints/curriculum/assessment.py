"""
SIMS Plus - Assessment Structure Endpoints

CRUD endpoints for assessment structures and their components.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import DatabaseSession, SchoolCtx, require_permissions
from app.schemas.curriculum import (
    AssessmentComponentCreate,
    AssessmentComponentResponse,
    AssessmentComponentSyncRequest,
    AssessmentComponentUpdate,
    AssessmentStructureCreate,
    AssessmentStructureResponse,
    AssessmentStructureUpdate,
    ReorderComponentsRequest,
    ValidateStructureResponse,
)
from app.services.curriculum import AssessmentStructureService, CurriculumServiceError

router = APIRouter()


# =========================
# Error Handling
# =========================

_STATUS_MAP = {
    "not_found": 404,
    "plan_limit": 403,
    "duplicate": 409,
    "weight_mismatch": 422,
    "profile_in_use": 409,
    "invalid_template": 422,
}


def _handle_error(e: CurriculumServiceError) -> None:
    """Convert service errors to appropriate HTTP responses."""
    raise HTTPException(
        status_code=_STATUS_MAP.get(e.code, 400),
        detail=e.message,
    )


# =========================
# Assessment Structure CRUD
# =========================


@router.post(
    "/profiles/{profile_id}/assessment-structures",
    response_model=AssessmentStructureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create assessment structure",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_structure(
    profile_id: UUID,
    data: AssessmentStructureCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Create an assessment structure for a curriculum profile."""
    service = AssessmentStructureService(db)
    try:
        structure = await service.create_structure(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            profile_id=profile_id,
            data=data,
        )
        return structure
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/profiles/{profile_id}/assessment-structures",
    response_model=AssessmentStructureResponse | None,
    summary="Get assessment structure for profile",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_structure_for_profile(
    profile_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
    academic_year_id: UUID | None = Query(None, description="Optional academic year for year-specific structure"),
):
    """
    Resolve the active assessment structure for a profile.

    Returns year-specific structure if available, otherwise the default.
    """
    service = AssessmentStructureService(db)
    try:
        structure = await service.get_structure_for_profile(
            tenant_id=school.tenant_id,
            profile_id=profile_id,
            academic_year_id=academic_year_id,
        )
        return structure
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/assessment-structures/{structure_id}",
    response_model=AssessmentStructureResponse,
    summary="Update assessment structure",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_structure(
    structure_id: UUID,
    data: AssessmentStructureUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Update assessment structure metadata (not components)."""
    service = AssessmentStructureService(db)
    try:
        structure = await service.update_structure(
            tenant_id=school.tenant_id,
            structure_id=structure_id,
            data=data,
        )
        return structure
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/assessment-structures/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete assessment structure",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_assessment_structure(
    structure_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """
    Soft delete an assessment structure.

    Blocks deletion if it is the only active structure for its profile.
    """
    service = AssessmentStructureService(db)
    try:
        await service.delete_structure(
            tenant_id=school.tenant_id,
            structure_id=structure_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Component CRUD
# =========================


@router.post(
    "/assessment-structures/{structure_id}/components",
    response_model=AssessmentComponentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add assessment component",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def add_component(
    structure_id: UUID,
    data: AssessmentComponentCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Add a component to an assessment structure."""
    service = AssessmentStructureService(db)
    try:
        component = await service.add_component(
            tenant_id=school.tenant_id,
            structure_id=structure_id,
            data=data,
        )
        return component
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/assessment-components/{component_id}",
    response_model=AssessmentComponentResponse,
    summary="Update assessment component",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_component(
    component_id: UUID,
    data: AssessmentComponentUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Update a single assessment component."""
    service = AssessmentStructureService(db)
    try:
        component = await service.update_component(
            tenant_id=school.tenant_id,
            component_id=component_id,
            data=data,
        )
        return component
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/assessment-components/{component_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete assessment component",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_component(
    component_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Hard delete an assessment component."""
    service = AssessmentStructureService(db)
    try:
        await service.delete_component(
            tenant_id=school.tenant_id,
            component_id=component_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Bulk Component Sync
# =========================


@router.put(
    "/assessment-structures/{structure_id}/components/sync",
    response_model=AssessmentStructureResponse,
    summary="Sync assessment components",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def sync_components(
    structure_id: UUID,
    data: AssessmentComponentSyncRequest,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """
    Replace all components of a structure in a single request.

    Accepts the full desired list of components. Components with an `id`
    are updated in place; those without `id` are created. Existing
    components whose id is absent from the request are deleted.

    Weight validation (must sum to 100) is enforced at the schema level.
    """
    service = AssessmentStructureService(db)
    try:
        structure = await service.sync_components(
            tenant_id=school.tenant_id,
            structure_id=structure_id,
            components_data=data.components,
        )
        return structure
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Structure Validation & Ordering
# =========================


@router.post(
    "/assessment-structures/{structure_id}/validate",
    response_model=ValidateStructureResponse,
    summary="Validate assessment structure weights",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def validate_structure(
    structure_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Check if component weights in a structure sum to 100%."""
    service = AssessmentStructureService(db)
    try:
        result = await service.validate_structure(
            tenant_id=school.tenant_id,
            structure_id=structure_id,
        )
        return result
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/assessment-structures/{structure_id}/reorder",
    response_model=list[AssessmentComponentResponse],
    summary="Reorder assessment components",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def reorder_components(
    structure_id: UUID,
    data: ReorderComponentsRequest,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Reorder components within an assessment structure."""
    service = AssessmentStructureService(db)
    try:
        components = await service.reorder_components(
            tenant_id=school.tenant_id,
            structure_id=structure_id,
            component_ids=data.component_ids,
        )
        return components
    except CurriculumServiceError as e:
        _handle_error(e)

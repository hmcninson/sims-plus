"""
SIMS Plus - Curriculum Profile Endpoints

CRUD endpoints for curriculum profiles, templates, and report card configuration.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import DatabaseSession, SchoolCtx, require_permissions
from app.schemas.curriculum import (
    AssessmentStructureResponse,
    CreateFromTemplateRequest,
    CurriculumProfileCreate,
    CurriculumProfileDetailResponse,
    CurriculumProfileListResponse,
    CurriculumProfileResponse,
    CurriculumTemplateInfo,
    CurriculumProfileUpdate,
    ReportCardConfigResponse,
    ReportCardConfigUpdate,
)
from app.services.curriculum import CurriculumProfileService, CurriculumServiceError

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
# Profile CRUD
# =========================


@router.post(
    "/profiles",
    response_model=CurriculumProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create curriculum profile",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_profile(
    data: CurriculumProfileCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Create a new curriculum profile for the school."""
    service = CurriculumProfileService(db)
    try:
        profile = await service.create_profile(
            data,
            tenant_id=school.tenant_id,
            school_id=school.school_id,
        )
        return profile
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/profiles",
    response_model=CurriculumProfileListResponse,
    summary="List curriculum profiles",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def list_profiles(
    db: DatabaseSession,
    school: SchoolCtx,
    curriculum_type: str | None = Query(None, description="Filter by curriculum type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, max_length=100, description="Search by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List curriculum profiles for the school with optional filters."""
    service = CurriculumProfileService(db)
    try:
        profiles, total = await service.list_profiles(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            curriculum_type=curriculum_type,
            is_active=is_active,
            search=search,
            page=page,
            page_size=page_size,
        )
        return CurriculumProfileListResponse(
            items=profiles,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/profiles/templates",
    response_model=list[CurriculumTemplateInfo],
    summary="List available curriculum templates",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_templates(
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Return metadata about all built-in curriculum templates."""
    service = CurriculumProfileService(db)
    return service.list_templates()


@router.post(
    "/profiles/from-template",
    response_model=CurriculumProfileDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create profile from template",
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_from_template(
    data: CreateFromTemplateRequest,
    db: DatabaseSession,
    school: SchoolCtx,
    template_key: str = Query(..., min_length=1, description="Template key"),
):
    """Instantiate a built-in curriculum template into database records."""
    service = CurriculumProfileService(db)
    try:
        profile = await service.create_from_template(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            template_key=template_key,
            name_override=data.name_override,
        )
        return _build_detail_response(profile)
    except CurriculumServiceError as e:
        _handle_error(e)


@router.get(
    "/profiles/{profile_id}",
    response_model=CurriculumProfileDetailResponse,
    summary="Get curriculum profile detail",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_profile(
    profile_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Get a curriculum profile with its assessment structure and report config."""
    service = CurriculumProfileService(db)
    try:
        profile = await service.get_profile(school.tenant_id, profile_id)
        return _build_detail_response(profile)
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/profiles/{profile_id}",
    response_model=CurriculumProfileResponse,
    summary="Update curriculum profile",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_profile(
    profile_id: UUID,
    data: CurriculumProfileUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Update an existing curriculum profile."""
    service = CurriculumProfileService(db)
    try:
        profile = await service.update_profile(
            school.tenant_id, profile_id, data
        )
        return profile
    except CurriculumServiceError as e:
        _handle_error(e)


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete curriculum profile",
    dependencies=[Depends(require_permissions("curriculum.delete"))],
)
async def delete_profile(
    profile_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Soft delete a curriculum profile (blocks if classes reference it)."""
    service = CurriculumProfileService(db)
    try:
        await service.delete_profile(school.tenant_id, profile_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CurriculumServiceError as e:
        _handle_error(e)


@router.post(
    "/profiles/{profile_id}/set-default",
    response_model=CurriculumProfileResponse,
    summary="Set profile as default",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def set_default(
    profile_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Set a curriculum profile as the default for the school."""
    service = CurriculumProfileService(db)
    try:
        profile = await service.set_default(school.tenant_id, profile_id)
        return profile
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Report Card Config
# =========================


@router.get(
    "/profiles/{profile_id}/report-config",
    response_model=ReportCardConfigResponse | None,
    summary="Get report card config",
    dependencies=[Depends(require_permissions("curriculum.read"))],
)
async def get_report_config(
    profile_id: UUID,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Get the report card configuration for a curriculum profile."""
    service = CurriculumProfileService(db)
    try:
        config = await service.get_report_config(school.tenant_id, profile_id)
        return config
    except CurriculumServiceError as e:
        _handle_error(e)


@router.put(
    "/profiles/{profile_id}/report-config",
    response_model=ReportCardConfigResponse,
    summary="Update report card config",
    dependencies=[Depends(require_permissions("curriculum.update"))],
)
async def update_report_config(
    profile_id: UUID,
    data: ReportCardConfigUpdate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    """Update the report card configuration for a curriculum profile."""
    service = CurriculumProfileService(db)
    try:
        config = await service.update_report_config(
            school.tenant_id, profile_id, data
        )
        return config
    except CurriculumServiceError as e:
        _handle_error(e)


# =========================
# Response Helpers
# =========================


def _build_detail_response(profile) -> dict:
    """
    Build a CurriculumProfileDetailResponse from a profile with loaded
    relationships. Picks the first active/default assessment structure
    and the first report config.
    """
    # Find the default assessment structure (prefer NULL academic_year_id)
    assessment_structure = None
    if profile.assessment_structures:
        # Prefer the default (no academic year) active structure
        for s in profile.assessment_structures:
            if s.deleted_at is None and s.is_active and s.academic_year_id is None:
                assessment_structure = s
                break
        # Fall back to any active structure
        if not assessment_structure:
            for s in profile.assessment_structures:
                if s.deleted_at is None and s.is_active:
                    assessment_structure = s
                    break

    # Pick the first non-deleted report config
    report_config = None
    if profile.report_config:
        for rc in profile.report_config:
            if rc.deleted_at is None:
                report_config = rc
                break

    # Build base profile from columns only, excluding list relationships
    # that don't match the schema's singular types (e.g. report_config is a
    # list on the ORM model but Optional[single] on the response schema).
    profile_dict = {
        c.key: getattr(profile, c.key)
        for c in profile.__table__.columns
    }
    profile_dict["assessment_structure"] = None
    profile_dict["report_config"] = None
    response = CurriculumProfileDetailResponse.model_validate(profile_dict)

    if assessment_structure:
        response.assessment_structure = AssessmentStructureResponse.model_validate(
            assessment_structure
        )
    if report_config:
        response.report_config = ReportCardConfigResponse.model_validate(report_config)

    return response

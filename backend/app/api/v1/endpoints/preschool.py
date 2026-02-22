"""
SIMS Plus - Preschool API Endpoints

API routes for preschool functionality including learning areas,
developmental skills, assessments, observations, daily logs, and reports.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.services.pdf import PDFService
from app.schemas.preschool import (
    LearningAreaCreate,
    LearningAreaUpdate,
    LearningAreaResponse,
    LearningAreaWithSkills,
    DevelopmentalSkillCreate,
    DevelopmentalSkillUpdate,
    DevelopmentalSkillResponse,
    DevelopmentalSkillBulkCreate,
    PreschoolRatingScaleCreate,
    PreschoolRatingScaleUpdate,
    PreschoolRatingScaleResponse,
    PreschoolRatingScaleWithRatings,
    PreschoolRatingResponse,
    PreschoolRatingCreate,
    StudentSkillAssessmentCreate,
    StudentSkillAssessmentBulk,
    StudentSkillAssessmentResponse,
    BulkAssessmentResult,
    ProgressObservationCreate,
    ProgressObservationUpdate,
    ProgressObservationResponse,
    DailyActivityLogCreate,
    DailyActivityLogUpdate,
    DailyActivityLogResponse,
    PreschoolReportCreate,
    PreschoolReportUpdate,
    PreschoolReportResponse,
    PreschoolReportGenerateRequest,
    PreschoolReportPublishRequest,
    SeedLearningAreasRequest,
    SeedRatingScaleRequest,
    convert_uuid,
)

router = APIRouter(prefix="/preschool", tags=["Preschool"])


# =========================
# Learning Areas
# =========================


@router.get(
    "/learning-areas",
    response_model=list[LearningAreaResponse],
    summary="List learning areas",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_learning_areas(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    include_inactive: bool = Query(False),
):
    """List all learning areas for the current tenant."""
    service = PreschoolService(db)
    areas = await service.list_learning_areas(
        convert_uuid(tenant.tenant_id), include_inactive
    )
    return [
        LearningAreaResponse(
            id=convert_uuid(a.id),
            tenant_id=convert_uuid(a.tenant_id),
            name=a.name,
            code=a.code,
            description=a.description,
            icon=a.icon,
            color=a.color,
            display_order=a.display_order,
            is_active=a.is_active,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in areas
    ]


@router.post(
    "/learning-areas",
    response_model=LearningAreaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create learning area",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_learning_area(
    data: LearningAreaCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a new learning area."""
    service = PreschoolService(db)
    try:
        return await service.create_learning_area(convert_uuid(tenant.tenant_id), data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/learning-areas/{area_id}",
    response_model=LearningAreaWithSkills,
    summary="Get learning area",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_learning_area(
    area_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a learning area with its skills."""
    service = PreschoolService(db)
    try:
        area = await service.get_learning_area(convert_uuid(tenant.tenant_id), area_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    return area


@router.get(
    "/learning-areas/{area_id}/skills",
    response_model=LearningAreaWithSkills,
    summary="Get learning area with skills",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_learning_area_with_skills(
    area_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a learning area with its skills (explicit skills endpoint)."""
    service = PreschoolService(db)
    try:
        area = await service.get_learning_area(convert_uuid(tenant.tenant_id), area_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    # Construct response with skills, filtering out soft-deleted ones
    return LearningAreaWithSkills(
        id=convert_uuid(area.id),
        tenant_id=convert_uuid(area.tenant_id),
        name=area.name,
        code=area.code,
        description=area.description,
        icon=area.icon,
        color=area.color,
        display_order=area.display_order,
        is_active=area.is_active,
        created_at=area.created_at,
        updated_at=area.updated_at,
        skills=[
            DevelopmentalSkillResponse(
                id=convert_uuid(s.id),
                tenant_id=convert_uuid(s.tenant_id),
                learning_area_id=convert_uuid(s.learning_area_id),
                name=s.name,
                description=s.description,
                age_range_months_min=s.age_range_months_min,
                age_range_months_max=s.age_range_months_max,
                display_order=s.display_order,
                is_active=s.is_active,
                applicable_levels=s.applicable_levels,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in (area.skills or [])
            if s.deleted_at is None
        ],
    )


@router.put(
    "/learning-areas/{area_id}",
    response_model=LearningAreaResponse,
    summary="Update learning area",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_learning_area(
    area_id: UUID,
    data: LearningAreaUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update a learning area."""
    service = PreschoolService(db)
    try:
        area = await service.get_learning_area(convert_uuid(tenant.tenant_id), area_id)
        return await service.update_learning_area(area, data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete(
    "/learning-areas/{area_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete learning area",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_learning_area(
    area_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Delete a learning area (soft delete)."""
    service = PreschoolService(db)
    try:
        area = await service.get_learning_area(convert_uuid(tenant.tenant_id), area_id)
        await service.delete_learning_area(area)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =========================
# Developmental Skills
# =========================


@router.get(
    "/skills",
    response_model=list[DevelopmentalSkillResponse],
    summary="List skills",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_skills(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    learning_area_id: UUID | None = Query(None),
    class_level: str | None = Query(None),
    include_inactive: bool = Query(False),
):
    """List developmental skills with optional filters."""
    service = PreschoolService(db)
    return await service.list_skills(
        convert_uuid(tenant.tenant_id), learning_area_id, class_level, include_inactive
    )


@router.post(
    "/skills",
    response_model=DevelopmentalSkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create skill",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_skill(
    data: DevelopmentalSkillCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a new developmental skill."""
    service = PreschoolService(db)
    try:
        return await service.create_skill(convert_uuid(tenant.tenant_id), data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/skills/bulk",
    response_model=list[DevelopmentalSkillResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create skills",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def bulk_create_skills(
    data: DevelopmentalSkillBulkCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Bulk create skills for a learning area."""
    service = PreschoolService(db)
    try:
        return await service.bulk_create_skills(convert_uuid(tenant.tenant_id), data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/skills/{skill_id}",
    response_model=DevelopmentalSkillResponse,
    summary="Get skill",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_skill(
    skill_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a skill by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_skill(convert_uuid(tenant.tenant_id), skill_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/skills/{skill_id}",
    response_model=DevelopmentalSkillResponse,
    summary="Update skill",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_skill(
    skill_id: UUID,
    data: DevelopmentalSkillUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update a skill."""
    service = PreschoolService(db)
    try:
        skill = await service.get_skill(convert_uuid(tenant.tenant_id), skill_id)
        return await service.update_skill(skill, data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete(
    "/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete skill",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_skill(
    skill_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Delete a skill (soft delete)."""
    service = PreschoolService(db)
    try:
        skill = await service.get_skill(convert_uuid(tenant.tenant_id), skill_id)
        await service.delete_skill(skill)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =========================
# Rating Scales
# =========================


@router.get(
    "/rating-scales",
    response_model=list[PreschoolRatingScaleWithRatings],
    summary="List rating scales",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_rating_scales(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """List all rating scales."""
    service = PreschoolService(db)
    scales = await service.list_rating_scales(convert_uuid(tenant.tenant_id))
    return [
        PreschoolRatingScaleWithRatings(
            id=convert_uuid(s.id),
            tenant_id=convert_uuid(s.tenant_id),
            name=s.name,
            description=s.description,
            is_default=s.is_default,
            created_at=s.created_at,
            updated_at=s.updated_at,
            ratings=[
                PreschoolRatingResponse(
                    id=convert_uuid(r.id),
                    tenant_id=convert_uuid(r.tenant_id),
                    scale_id=convert_uuid(r.scale_id),
                    name=r.name,
                    short_code=r.short_code,
                    description=r.description,
                    numeric_value=r.numeric_value,
                    color=r.color,
                    icon=r.icon,
                    display_order=r.display_order,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in (s.ratings or [])
                if r.deleted_at is None
            ],
        )
        for s in scales
    ]


@router.post(
    "/rating-scales",
    response_model=PreschoolRatingScaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create rating scale",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_rating_scale(
    data: PreschoolRatingScaleCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a rating scale with ratings."""
    service = PreschoolService(db)
    try:
        scale = await service.create_rating_scale(convert_uuid(tenant.tenant_id), data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return PreschoolRatingScaleResponse(
        id=convert_uuid(scale.id),
        tenant_id=convert_uuid(scale.tenant_id),
        name=scale.name,
        description=scale.description,
        is_default=scale.is_default,
        created_at=scale.created_at,
        updated_at=scale.updated_at,
    )


@router.get(
    "/rating-scales/default",
    response_model=PreschoolRatingScaleWithRatings,
    summary="Get default rating scale",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_default_rating_scale(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get the default rating scale for the tenant."""
    service = PreschoolService(db)
    try:
        return await service.get_default_rating_scale(convert_uuid(tenant.tenant_id))
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/rating-scales/{scale_id}",
    response_model=PreschoolRatingScaleWithRatings,
    summary="Get rating scale",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_rating_scale(
    scale_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a rating scale by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_rating_scale(convert_uuid(tenant.tenant_id), scale_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/rating-scales/{scale_id}",
    response_model=PreschoolRatingScaleResponse,
    summary="Update rating scale",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_rating_scale(
    scale_id: UUID,
    data: PreschoolRatingScaleUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update a rating scale."""
    service = PreschoolService(db)
    try:
        scale = await service.get_rating_scale(convert_uuid(tenant.tenant_id), scale_id)
        updated = await service.update_rating_scale(scale, data, convert_uuid(tenant.tenant_id))
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    return PreschoolRatingScaleResponse(
        id=convert_uuid(updated.id),
        tenant_id=convert_uuid(updated.tenant_id),
        name=updated.name,
        description=updated.description,
        is_default=updated.is_default,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete(
    "/rating-scales/{scale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete rating scale",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_rating_scale(
    scale_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Delete a rating scale."""
    service = PreschoolService(db)
    try:
        scale = await service.get_rating_scale(convert_uuid(tenant.tenant_id), scale_id)
        await service.delete_rating_scale(scale)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =========================
# Student Assessments
# =========================


@router.get(
    "/assessments",
    response_model=list[StudentSkillAssessmentResponse],
    summary="List assessments",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_assessments(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    learning_area_id: UUID | None = Query(None),
):
    """List assessments with optional filters."""
    service = PreschoolService(db)
    return await service.list_assessments(
        convert_uuid(tenant.tenant_id), student_id, term_id, learning_area_id
    )


@router.post(
    "/assessments",
    response_model=StudentSkillAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update assessment",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_or_update_assessment(
    data: StudentSkillAssessmentCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create or update a skill assessment."""
    service = PreschoolService(db)
    try:
        return await service.create_or_update_assessment(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/assessments/bulk",
    response_model=BulkAssessmentResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk assess",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def bulk_assess(
    data: StudentSkillAssessmentBulk,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Bulk create/update assessments for a student."""
    service = PreschoolService(db)
    try:
        result = await service.bulk_assess(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return BulkAssessmentResult(**result)


@router.get(
    "/assessments/student/{student_id}",
    response_model=list[StudentSkillAssessmentResponse],
    summary="Get student assessments",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_assessments(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    term_id: UUID | None = Query(None),
):
    """Get all assessments for a student."""
    service = PreschoolService(db)
    return await service.list_assessments(
        convert_uuid(tenant.tenant_id), student_id, term_id
    )


# =========================
# Progress Observations
# =========================


@router.get(
    "/observations",
    response_model=list[ProgressObservationResponse],
    summary="List observations",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_observations(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    observation_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(50, le=100),
):
    """List observations with filters."""
    service = PreschoolService(db)
    return await service.list_observations(
        convert_uuid(tenant.tenant_id), student_id, observation_type, start_date, end_date, limit
    )


@router.post(
    "/observations",
    response_model=ProgressObservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create observation",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_observation(
    data: ProgressObservationCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a progress observation."""
    service = PreschoolService(db)
    try:
        return await service.create_observation(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/observations/{observation_id}",
    response_model=ProgressObservationResponse,
    summary="Get observation",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_observation(
    observation_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get an observation by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_observation(convert_uuid(tenant.tenant_id), observation_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/observations/{observation_id}",
    response_model=ProgressObservationResponse,
    summary="Update observation",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_observation(
    observation_id: UUID,
    data: ProgressObservationUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update an observation."""
    service = PreschoolService(db)
    try:
        observation = await service.get_observation(convert_uuid(tenant.tenant_id), observation_id)
        return await service.update_observation(observation, data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete(
    "/observations/{observation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete observation",
    dependencies=[Depends(require_permissions("preschool.delete"))],
)
async def delete_observation(
    observation_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Delete an observation (soft delete)."""
    service = PreschoolService(db)
    try:
        observation = await service.get_observation(convert_uuid(tenant.tenant_id), observation_id)
        await service.delete_observation(observation)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/observations/student/{student_id}",
    response_model=list[ProgressObservationResponse],
    summary="Get student observations",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_observations(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    limit: int = Query(50, le=100),
):
    """Get all observations for a student."""
    service = PreschoolService(db)
    return await service.list_observations(
        convert_uuid(tenant.tenant_id), student_id, limit=limit
    )


# =========================
# Daily Activity Logs
# =========================


@router.get(
    "/daily-logs",
    response_model=list[DailyActivityLogResponse],
    summary="List daily logs",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_daily_logs(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    log_date: date | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    class_id: UUID | None = Query(None),
    limit: int = Query(50, le=100),
):
    """List daily logs with filters."""
    service = PreschoolService(db)
    return await service.list_daily_logs(
        convert_uuid(tenant.tenant_id), student_id, log_date, start_date, end_date, class_id, limit
    )


@router.post(
    "/daily-logs",
    response_model=DailyActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update daily log",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_or_update_daily_log(
    data: DailyActivityLogCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create or update a daily activity log."""
    service = PreschoolService(db)
    try:
        return await service.create_or_update_daily_log(
            convert_uuid(tenant.tenant_id), data, convert_uuid(current_user["user_id"])
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/daily-logs/{log_id}",
    response_model=DailyActivityLogResponse,
    summary="Get daily log",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_daily_log(
    log_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a daily log by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_daily_log(convert_uuid(tenant.tenant_id), log_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/daily-logs/student/{student_id}",
    response_model=list[DailyActivityLogResponse],
    summary="Get student daily logs",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_student_daily_logs(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    limit: int = Query(30, le=100),
):
    """Get daily logs for a student."""
    service = PreschoolService(db)
    return await service.list_daily_logs(
        convert_uuid(tenant.tenant_id), student_id, limit=limit
    )


# =========================
# Preschool Reports
# =========================


@router.get(
    "/reports",
    response_model=list[PreschoolReportResponse],
    summary="List reports",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_reports(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    is_published: bool | None = Query(None),
):
    """List preschool reports with filters."""
    service = PreschoolService(db)
    return await service.list_reports(
        convert_uuid(tenant.tenant_id), student_id, term_id, class_id, is_published
    )


@router.post(
    "/reports",
    response_model=PreschoolReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create report",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def create_report(
    data: PreschoolReportCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Create a preschool report."""
    service = PreschoolService(db)
    try:
        return await service.create_report(convert_uuid(tenant.tenant_id), data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/reports/{report_id}",
    response_model=PreschoolReportResponse,
    summary="Get report",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def get_report(
    report_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Get a report by ID."""
    service = PreschoolService(db)
    try:
        return await service.get_report(convert_uuid(tenant.tenant_id), report_id)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put(
    "/reports/{report_id}",
    response_model=PreschoolReportResponse,
    summary="Update report",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_report(
    report_id: UUID,
    data: PreschoolReportUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update a report."""
    service = PreschoolService(db)
    try:
        report = await service.get_report(convert_uuid(tenant.tenant_id), report_id)
        return await service.update_report(report, data)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/reports/generate",
    summary="Generate reports",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def generate_reports(
    data: PreschoolReportGenerateRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Generate reports for all students in a class for a given term."""
    service = PreschoolService(db)
    try:
        result = await service.generate_reports(
            convert_uuid(tenant.tenant_id),
            data.class_id,
            data.academic_year_id,
            data.term_id,
        )
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return result


@router.post(
    "/reports/publish",
    response_model=list[PreschoolReportResponse],
    summary="Publish reports",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def publish_reports(
    data: PreschoolReportPublishRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Publish multiple reports."""
    service = PreschoolService(db)
    try:
        return await service.publish_reports(convert_uuid(tenant.tenant_id), data.report_ids)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/reports/{report_id}/pdf",
    summary="Download report PDF",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def download_report_pdf(
    report_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Download a preschool report as PDF. Only published reports can be downloaded."""
    try:
        pdf_bytes, filename = await PDFService.generate_preschool_report_pdf(
            db,
            convert_uuid(tenant.tenant_id),
            report_id,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =========================
# Seed Data Endpoints
# =========================


@router.post(
    "/seed/learning-areas",
    response_model=list[LearningAreaResponse],
    summary="Seed learning areas",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def seed_learning_areas(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    data: SeedLearningAreasRequest | None = None,
):
    """Seed default learning areas and skills for the tenant."""
    service = PreschoolService(db)
    include_skills = data.include_skills if data else True
    try:
        areas = await service.seed_learning_areas(convert_uuid(tenant.tenant_id), include_skills)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return [
        LearningAreaResponse(
            id=convert_uuid(a.id),
            tenant_id=convert_uuid(a.tenant_id),
            name=a.name,
            code=a.code,
            description=a.description,
            icon=a.icon,
            color=a.color,
            display_order=a.display_order,
            is_active=a.is_active,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in areas
    ]


@router.post(
    "/seed/rating-scale",
    response_model=PreschoolRatingScaleWithRatings,
    summary="Seed rating scale",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def seed_rating_scale(
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
    data: SeedRatingScaleRequest | None = None,
):
    """Seed the default rating scale for the tenant."""
    service = PreschoolService(db)
    set_as_default = data.set_as_default if data else True
    try:
        scale = await service.seed_rating_scale(convert_uuid(tenant.tenant_id), set_as_default)
    except PreschoolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return PreschoolRatingScaleWithRatings(
        id=convert_uuid(scale.id),
        tenant_id=convert_uuid(scale.tenant_id),
        name=scale.name,
        description=scale.description,
        is_default=scale.is_default,
        created_at=scale.created_at,
        updated_at=scale.updated_at,
        ratings=[
            PreschoolRatingResponse(
                id=convert_uuid(r.id),
                tenant_id=convert_uuid(r.tenant_id),
                scale_id=convert_uuid(r.scale_id),
                name=r.name,
                short_code=r.short_code,
                description=r.description,
                numeric_value=r.numeric_value,
                color=r.color,
                icon=r.icon,
                display_order=r.display_order,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in (scale.ratings or [])
            if r.deleted_at is None
        ],
    )

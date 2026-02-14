"""
SIMS Plus - Preschool API Endpoints

API routes for preschool functionality including learning areas,
developmental skills, assessments, observations, daily logs, and reports.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
)
from app.middleware.tenant import TenantContext
from app.services.preschool import PreschoolService
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


@router.get("/learning-areas", response_model=list[LearningAreaResponse])
async def list_learning_areas(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    include_inactive: bool = Query(False),
):
    """List all learning areas for the current tenant."""
    areas = await PreschoolService.list_learning_areas(
        db, convert_uuid(tenant.tenant_id), include_inactive
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
)
async def create_learning_area(
    data: LearningAreaCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create a new learning area."""
    return await PreschoolService.create_learning_area(db, convert_uuid(tenant.tenant_id), data)


@router.get("/learning-areas/{area_id}", response_model=LearningAreaWithSkills)
async def get_learning_area(
    area_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get a learning area with its skills."""
    area = await PreschoolService.get_learning_area(db, convert_uuid(tenant.tenant_id), area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning area not found",
        )
    return area


@router.get("/learning-areas/{area_id}/skills", response_model=LearningAreaWithSkills)
async def get_learning_area_with_skills(
    area_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get a learning area with its skills (explicit skills endpoint)."""
    area = await PreschoolService.get_learning_area(db, convert_uuid(tenant.tenant_id), area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning area not found",
        )
    # Construct response with skills
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


@router.put("/learning-areas/{area_id}", response_model=LearningAreaResponse)
async def update_learning_area(
    area_id: UUID,
    data: LearningAreaUpdate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Update a learning area."""
    area = await PreschoolService.get_learning_area(db, convert_uuid(tenant.tenant_id), area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning area not found",
        )
    return await PreschoolService.update_learning_area(db, area, data)


@router.delete("/learning-areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learning_area(
    area_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Delete a learning area (soft delete)."""
    area = await PreschoolService.get_learning_area(db, convert_uuid(tenant.tenant_id), area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning area not found",
        )
    await PreschoolService.delete_learning_area(db, area)


# =========================
# Developmental Skills
# =========================


@router.get("/skills", response_model=list[DevelopmentalSkillResponse])
async def list_skills(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    learning_area_id: UUID | None = Query(None),
    class_level: str | None = Query(None),
    include_inactive: bool = Query(False),
):
    """List developmental skills with optional filters."""
    return await PreschoolService.list_skills(
        db, convert_uuid(tenant.tenant_id), learning_area_id, class_level, include_inactive
    )


@router.post(
    "/skills",
    response_model=DevelopmentalSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_skill(
    data: DevelopmentalSkillCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create a new developmental skill."""
    return await PreschoolService.create_skill(db, convert_uuid(tenant.tenant_id), data)


@router.post(
    "/skills/bulk",
    response_model=list[DevelopmentalSkillResponse],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_skills(
    data: DevelopmentalSkillBulkCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Bulk create skills for a learning area."""
    return await PreschoolService.bulk_create_skills(db, convert_uuid(tenant.tenant_id), data)


@router.get("/skills/{skill_id}", response_model=DevelopmentalSkillResponse)
async def get_skill(
    skill_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get a skill by ID."""
    skill = await PreschoolService.get_skill(db, convert_uuid(tenant.tenant_id), skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )
    return skill


@router.put("/skills/{skill_id}", response_model=DevelopmentalSkillResponse)
async def update_skill(
    skill_id: UUID,
    data: DevelopmentalSkillUpdate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Update a skill."""
    skill = await PreschoolService.get_skill(db, convert_uuid(tenant.tenant_id), skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )
    return await PreschoolService.update_skill(db, skill, data)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Delete a skill (soft delete)."""
    skill = await PreschoolService.get_skill(db, convert_uuid(tenant.tenant_id), skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )
    await PreschoolService.delete_skill(db, skill)


# =========================
# Rating Scales
# =========================


@router.get("/rating-scales", response_model=list[PreschoolRatingScaleWithRatings])
async def list_rating_scales(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """List all rating scales."""
    scales = await PreschoolService.list_rating_scales(db, convert_uuid(tenant.tenant_id))
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
            ],
        )
        for s in scales
    ]


@router.post(
    "/rating-scales",
    response_model=PreschoolRatingScaleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rating_scale(
    data: PreschoolRatingScaleCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create a rating scale with ratings."""
    scale = await PreschoolService.create_rating_scale(db, convert_uuid(tenant.tenant_id), data)
    return PreschoolRatingScaleResponse(
        id=convert_uuid(scale.id),
        tenant_id=convert_uuid(scale.tenant_id),
        name=scale.name,
        description=scale.description,
        is_default=scale.is_default,
        created_at=scale.created_at,
        updated_at=scale.updated_at,
    )


@router.get("/rating-scales/default", response_model=PreschoolRatingScaleWithRatings)
async def get_default_rating_scale(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get the default rating scale for the tenant."""
    scale = await PreschoolService.get_default_rating_scale(db, convert_uuid(tenant.tenant_id))
    if not scale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default rating scale found. Please seed the default scale first.",
        )
    return scale


@router.get("/rating-scales/{scale_id}", response_model=PreschoolRatingScaleWithRatings)
async def get_rating_scale(
    scale_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get a rating scale by ID."""
    scale = await PreschoolService.get_rating_scale(db, convert_uuid(tenant.tenant_id), scale_id)
    if not scale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rating scale not found",
        )
    return scale


@router.put("/rating-scales/{scale_id}", response_model=PreschoolRatingScaleResponse)
async def update_rating_scale(
    scale_id: UUID,
    data: PreschoolRatingScaleUpdate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Update a rating scale."""
    scale = await PreschoolService.get_rating_scale(db, convert_uuid(tenant.tenant_id), scale_id)
    if not scale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rating scale not found",
        )
    updated = await PreschoolService.update_rating_scale(db, scale, data, convert_uuid(tenant.tenant_id))
    return PreschoolRatingScaleResponse(
        id=convert_uuid(updated.id),
        tenant_id=convert_uuid(updated.tenant_id),
        name=updated.name,
        description=updated.description,
        is_default=updated.is_default,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/rating-scales/{scale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rating_scale(
    scale_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Delete a rating scale."""
    scale = await PreschoolService.get_rating_scale(db, convert_uuid(tenant.tenant_id), scale_id)
    if not scale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rating scale not found",
        )
    await PreschoolService.delete_rating_scale(db, scale)
    return None


# =========================
# Student Assessments
# =========================


@router.get("/assessments", response_model=list[StudentSkillAssessmentResponse])
async def list_assessments(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    learning_area_id: UUID | None = Query(None),
):
    """List assessments with optional filters."""
    return await PreschoolService.list_assessments(
        db, convert_uuid(tenant.tenant_id), student_id, term_id, learning_area_id
    )


@router.post(
    "/assessments",
    response_model=StudentSkillAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_assessment(
    data: StudentSkillAssessmentCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create or update a skill assessment."""
    return await PreschoolService.create_or_update_assessment(
        db, convert_uuid(tenant.tenant_id), data, convert_uuid(current_user)
    )


@router.post(
    "/assessments/bulk",
    response_model=BulkAssessmentResult,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_assess(
    data: StudentSkillAssessmentBulk,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Bulk create/update assessments for a student."""
    result = await PreschoolService.bulk_assess(
        db, convert_uuid(tenant.tenant_id), data, convert_uuid(current_user)
    )
    return BulkAssessmentResult(**result)


@router.get("/assessments/student/{student_id}", response_model=list[StudentSkillAssessmentResponse])
async def get_student_assessments(
    student_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    term_id: UUID | None = Query(None),
):
    """Get all assessments for a student."""
    return await PreschoolService.list_assessments(
        db, convert_uuid(tenant.tenant_id), student_id, term_id
    )


# =========================
# Progress Observations
# =========================


@router.get("/observations", response_model=list[ProgressObservationResponse])
async def list_observations(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    observation_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int = Query(50, le=100),
):
    """List observations with filters."""
    return await PreschoolService.list_observations(
        db, convert_uuid(tenant.tenant_id), student_id, observation_type, start_date, end_date, limit
    )


@router.post(
    "/observations",
    response_model=ProgressObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_observation(
    data: ProgressObservationCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create a progress observation."""
    return await PreschoolService.create_observation(
        db, convert_uuid(tenant.tenant_id), data, convert_uuid(current_user)
    )


@router.get("/observations/{observation_id}", response_model=ProgressObservationResponse)
async def get_observation(
    observation_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get an observation by ID."""
    observation = await PreschoolService.get_observation(db, convert_uuid(tenant.tenant_id), observation_id)
    if not observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )
    return observation


@router.put("/observations/{observation_id}", response_model=ProgressObservationResponse)
async def update_observation(
    observation_id: UUID,
    data: ProgressObservationUpdate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Update an observation."""
    observation = await PreschoolService.get_observation(db, convert_uuid(tenant.tenant_id), observation_id)
    if not observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )
    return await PreschoolService.update_observation(db, observation, data)


@router.delete("/observations/{observation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observation(
    observation_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Delete an observation (soft delete)."""
    observation = await PreschoolService.get_observation(db, convert_uuid(tenant.tenant_id), observation_id)
    if not observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found",
        )
    await PreschoolService.delete_observation(db, observation)


@router.get("/observations/student/{student_id}", response_model=list[ProgressObservationResponse])
async def get_student_observations(
    student_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    limit: int = Query(50, le=100),
):
    """Get all observations for a student."""
    return await PreschoolService.list_observations(
        db, convert_uuid(tenant.tenant_id), student_id, limit=limit
    )


# =========================
# Daily Activity Logs
# =========================


@router.get("/daily-logs", response_model=list[DailyActivityLogResponse])
async def list_daily_logs(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    log_date: date | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    class_id: UUID | None = Query(None),
    limit: int = Query(50, le=100),
):
    """List daily logs with filters."""
    return await PreschoolService.list_daily_logs(
        db, convert_uuid(tenant.tenant_id), student_id, log_date, start_date, end_date, class_id, limit
    )


@router.post(
    "/daily-logs",
    response_model=DailyActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_daily_log(
    data: DailyActivityLogCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create or update a daily activity log."""
    return await PreschoolService.create_or_update_daily_log(
        db, convert_uuid(tenant.tenant_id), data, convert_uuid(current_user)
    )


@router.get("/daily-logs/{log_id}", response_model=DailyActivityLogResponse)
async def get_daily_log(
    log_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get a daily log by ID."""
    log = await PreschoolService.get_daily_log(db, convert_uuid(tenant.tenant_id), log_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily log not found",
        )
    return log


@router.get("/daily-logs/student/{student_id}", response_model=list[DailyActivityLogResponse])
async def get_student_daily_logs(
    student_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    limit: int = Query(30, le=100),
):
    """Get daily logs for a student."""
    return await PreschoolService.list_daily_logs(
        db, convert_uuid(tenant.tenant_id), student_id, limit=limit
    )


# =========================
# Preschool Reports
# =========================


@router.get("/reports", response_model=list[PreschoolReportResponse])
async def list_reports(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    student_id: UUID | None = Query(None),
    term_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    is_published: bool | None = Query(None),
):
    """List preschool reports with filters."""
    return await PreschoolService.list_reports(
        db, convert_uuid(tenant.tenant_id), student_id, term_id, class_id, is_published
    )


@router.post(
    "/reports",
    response_model=PreschoolReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    data: PreschoolReportCreate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Create a preschool report."""
    return await PreschoolService.create_report(db, convert_uuid(tenant.tenant_id), data)


@router.get("/reports/{report_id}", response_model=PreschoolReportResponse)
async def get_report(
    report_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Get a report by ID."""
    report = await PreschoolService.get_report(db, convert_uuid(tenant.tenant_id), report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return report


@router.put("/reports/{report_id}", response_model=PreschoolReportResponse)
async def update_report(
    report_id: UUID,
    data: PreschoolReportUpdate,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Update a report."""
    report = await PreschoolService.get_report(db, convert_uuid(tenant.tenant_id), report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return await PreschoolService.update_report(db, report, data)


@router.post("/reports/generate")
async def generate_reports(
    data: PreschoolReportGenerateRequest,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Generate reports for all students in a class for a given term."""
    result = await PreschoolService.generate_reports(
        db,
        convert_uuid(tenant.tenant_id),
        data.class_id,
        data.academic_year_id,
        data.term_id,
    )
    return result


@router.post("/reports/publish", response_model=list[PreschoolReportResponse])
async def publish_reports(
    data: PreschoolReportPublishRequest,
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
):
    """Publish multiple reports."""
    return await PreschoolService.publish_reports(db, convert_uuid(tenant.tenant_id), data.report_ids)


@router.get("/reports/{report_id}/pdf")
async def download_report_pdf(
    report_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUserId,
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


@router.post("/seed/learning-areas", response_model=list[LearningAreaResponse])
async def seed_learning_areas(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    data: SeedLearningAreasRequest | None = None,
):
    """Seed default learning areas and skills for the tenant."""
    include_skills = data.include_skills if data else True
    areas = await PreschoolService.seed_learning_areas(db, convert_uuid(tenant.tenant_id), include_skills)
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


@router.post("/seed/rating-scale", response_model=PreschoolRatingScaleWithRatings)
async def seed_rating_scale(
    db: DatabaseSession,
    current_user: CurrentUserId,
    tenant: RequestTenant,
    data: SeedRatingScaleRequest | None = None,
):
    """Seed the default rating scale for the tenant."""
    set_as_default = data.set_as_default if data else True
    scale = await PreschoolService.seed_rating_scale(db, convert_uuid(tenant.tenant_id), set_as_default)
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
        ],
    )

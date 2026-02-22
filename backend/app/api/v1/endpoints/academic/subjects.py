"""
SIMS Plus - Subject, Grading, Assessment Weight, and Academic Settings Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.academic import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    ClassSubjectCreate,
    ClassSubjectResponse,
    GradingScaleCreate,
    GradingScaleUpdate,
    GradingScaleResponse,
    GradingScaleWithGradesResponse,
    GradeResponse,
    AssessmentWeightCreate,
    AssessmentWeightResponse,
    AcademicSettingsUpdate,
    AcademicSettingsResponse,
)
from app.services.academic import AcademicService, AcademicServiceError

router = APIRouter()


# =========================
# Subject Endpoints
# =========================


@router.post(
    "/subjects",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create subject",
    dependencies=[Depends(require_permissions("subjects.create"))],
)
async def create_subject(
    data: SubjectCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SubjectResponse:
    """Create a new subject."""
    service = AcademicService(db)
    try:
        subject = await service.create_subject(
            tenant_id=tenant.tenant_id,
            name=data.name,
            code=data.code,
            description=data.description,
            category=data.category,
        )
        return SubjectResponse(
            id=subject.id,
            name=subject.name,
            code=subject.code,
            description=subject.description,
            category=subject.category.value if hasattr(subject.category, 'value') else subject.category,
            is_active=subject.is_active,
            created_at=subject.created_at,
            updated_at=subject.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/subjects",
    response_model=list[SubjectResponse],
    summary="List subjects",
    dependencies=[Depends(require_permissions("subjects.read"))],
)
async def list_subjects(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    category: Optional[str] = Query(None),
    class_level: Optional[str] = Query(
        None,
        description="Filter by class level (preschool, primary, jhs, shs). Returns subjects applicable to this level.",
    ),
    active_only: bool = Query(True),
) -> list[SubjectResponse]:
    """List all subjects, optionally filtered by class level."""
    service = AcademicService(db)
    subjects = await service.list_subjects(
        tenant.tenant_id,
        category=category,
        class_level=class_level,
        active_only=active_only,
    )
    return [
        SubjectResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            description=s.description,
            category=s.category.value if hasattr(s.category, 'value') else s.category,
            applicable_levels=s.applicable_levels,
            is_active=s.is_active,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in subjects
    ]


@router.get(
    "/subjects/{subject_id}",
    response_model=SubjectResponse,
    summary="Get subject",
    dependencies=[Depends(require_permissions("subjects.read"))],
)
async def get_subject(
    subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SubjectResponse:
    """Get subject by ID."""
    service = AcademicService(db)
    subject = await service.get_subject(tenant.tenant_id, subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return SubjectResponse(
        id=subject.id,
        name=subject.name,
        code=subject.code,
        description=subject.description,
        category=subject.category.value if hasattr(subject.category, 'value') else subject.category,
        applicable_levels=subject.applicable_levels,
        is_active=subject.is_active,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
    )


@router.put(
    "/subjects/{subject_id}",
    response_model=SubjectResponse,
    summary="Update subject",
    dependencies=[Depends(require_permissions("subjects.update"))],
)
async def update_subject(
    subject_id: UUID,
    data: SubjectUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SubjectResponse:
    """Update a subject."""
    service = AcademicService(db)
    subject = await service.update_subject(tenant.tenant_id, subject_id, **data.model_dump(exclude_unset=True))
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return SubjectResponse(
        id=subject.id,
        name=subject.name,
        code=subject.code,
        description=subject.description,
        category=subject.category.value if hasattr(subject.category, 'value') else subject.category,
        is_active=subject.is_active,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
    )


@router.delete(
    "/subjects/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete subject",
    dependencies=[Depends(require_permissions("subjects.delete"))],
)
async def delete_subject(
    subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a subject."""
    service = AcademicService(db)
    deleted = await service.delete_subject(tenant.tenant_id, subject_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")


# =========================
# Class Subject Endpoints
# =========================


@router.post(
    "/classes/{class_id}/subjects",
    response_model=ClassSubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign subject to class",
    dependencies=[Depends(require_permissions("classes.update"))],
)
async def assign_subject_to_class(
    class_id: UUID,
    data: ClassSubjectCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> ClassSubjectResponse:
    """Assign a subject to a class."""
    service = AcademicService(db)
    try:
        assignment = await service.assign_subject_to_class(
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            subject_id=data.subject_id,
            periods_per_week=data.periods_per_week,
            is_compulsory=data.is_compulsory,
        )
        return ClassSubjectResponse(
            id=assignment.id,
            class_id=assignment.class_id,
            subject_id=assignment.subject_id,
            periods_per_week=assignment.periods_per_week,
            is_compulsory=assignment.is_compulsory,
            created_at=assignment.created_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/classes/{class_id}/subjects",
    response_model=list[ClassSubjectResponse],
    summary="Get class subjects",
    dependencies=[Depends(require_permissions("classes.read"))],
)
async def get_class_subjects(
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[ClassSubjectResponse]:
    """Get all subjects assigned to a class."""
    service = AcademicService(db)
    assignments = await service.get_class_subjects(tenant.tenant_id, class_id)
    return [
        ClassSubjectResponse(
            id=a.id,
            class_id=a.class_id,
            subject_id=a.subject_id,
            periods_per_week=a.periods_per_week,
            is_compulsory=a.is_compulsory,
            created_at=a.created_at,
            subject=SubjectResponse(
                id=a.subject.id,
                name=a.subject.name,
                code=a.subject.code,
                description=a.subject.description,
                category=a.subject.category.value if hasattr(a.subject.category, 'value') else a.subject.category,
                is_active=a.subject.is_active,
                created_at=a.subject.created_at,
                updated_at=a.subject.updated_at,
            ) if a.subject else None,
        )
        for a in assignments
    ]


@router.delete(
    "/classes/{class_id}/subjects/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove subject from class",
    dependencies=[Depends(require_permissions("classes.update"))],
)
async def remove_subject_from_class(
    class_id: UUID,
    subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Remove a subject assignment from a class."""
    service = AcademicService(db)
    deleted = await service.remove_subject_from_class(tenant.tenant_id, class_id, subject_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")


@router.post(
    "/classes/subjects/bulk",
    response_model=list[ClassSubjectResponse],
    summary="Get subjects for multiple classes",
    dependencies=[Depends(require_permissions("classes.read"))],
)
async def get_subjects_for_classes(
    class_ids: list[UUID],
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[ClassSubjectResponse]:
    """Get all subjects assigned to multiple classes in a single request."""
    service = AcademicService(db)
    assignments = await service.get_subjects_for_classes(tenant.tenant_id, class_ids)
    return [
        ClassSubjectResponse(
            id=a.id,
            class_id=a.class_id,
            subject_id=a.subject_id,
            periods_per_week=a.periods_per_week,
            is_compulsory=a.is_compulsory,
            created_at=a.created_at,
            subject=SubjectResponse(
                id=a.subject.id,
                name=a.subject.name,
                code=a.subject.code,
                description=a.subject.description,
                category=a.subject.category.value if hasattr(a.subject.category, 'value') else a.subject.category,
                is_active=a.subject.is_active,
                created_at=a.subject.created_at,
                updated_at=a.subject.updated_at,
            ) if a.subject else None,
        )
        for a in assignments
    ]


# =========================
# Grading Scale Endpoints
# =========================


@router.post(
    "/grading-scales",
    response_model=GradingScaleWithGradesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create grading scale",
    dependencies=[Depends(require_permissions("grading.create"))],
)
async def create_grading_scale(
    data: GradingScaleCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> GradingScaleWithGradesResponse:
    """Create a new grading scale with grades."""
    service = AcademicService(db)
    try:
        scale = await service.create_grading_scale(
            tenant_id=tenant.tenant_id,
            name=data.name,
            description=data.description,
            scale_type=data.scale_type,
            is_default=data.is_default,
            grades=[g.model_dump() for g in data.grades],
        )
        # Reload with grades
        scale = await service.get_grading_scale(tenant.tenant_id, scale.id, include_grades=True)

        return GradingScaleWithGradesResponse(
            id=scale.id,
            name=scale.name,
            description=scale.description,
            scale_type=scale.scale_type.value,
            is_default=scale.is_default,
            is_active=scale.is_active,
            created_at=scale.created_at,
            updated_at=scale.updated_at,
            grades=[
                GradeResponse(
                    id=g.id,
                    grading_scale_id=g.grading_scale_id,
                    grade=g.grade,
                    min_score=g.min_score,
                    max_score=g.max_score,
                    grade_point=g.grade_point,
                    remark=g.remark,
                ) for g in scale.grades
            ],
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/grading-scales",
    response_model=list[GradingScaleWithGradesResponse],
    summary="List grading scales",
    dependencies=[Depends(require_permissions("grading.read"))],
)
async def list_grading_scales(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    include_grades: bool = Query(False),
    active_only: bool = Query(True),
) -> list:
    """List all grading scales."""
    service = AcademicService(db)
    scales = await service.list_grading_scales(tenant.tenant_id, include_grades=include_grades, active_only=active_only)

    response_model = GradingScaleWithGradesResponse if include_grades else GradingScaleResponse
    return [
        response_model(
            id=s.id,
            name=s.name,
            description=s.description,
            scale_type=s.scale_type.value,
            is_default=s.is_default,
            is_active=s.is_active,
            created_at=s.created_at,
            updated_at=s.updated_at,
            **({"grades": [
                GradeResponse(
                    id=g.id,
                    grading_scale_id=g.grading_scale_id,
                    grade=g.grade,
                    min_score=g.min_score,
                    max_score=g.max_score,
                    grade_point=g.grade_point,
                    remark=g.remark,
                ) for g in s.grades
            ]} if include_grades else {}),
        )
        for s in scales
    ]


@router.get(
    "/grading-scales/{scale_id}",
    response_model=GradingScaleWithGradesResponse,
    summary="Get grading scale",
    dependencies=[Depends(require_permissions("grading.read"))],
)
async def get_grading_scale(
    scale_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> GradingScaleWithGradesResponse:
    """Get grading scale by ID with grades."""
    service = AcademicService(db)
    scale = await service.get_grading_scale(tenant.tenant_id, scale_id, include_grades=True)
    if not scale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading scale not found")

    return GradingScaleWithGradesResponse(
        id=scale.id,
        name=scale.name,
        description=scale.description,
        scale_type=scale.scale_type.value,
        is_default=scale.is_default,
        is_active=scale.is_active,
        created_at=scale.created_at,
        updated_at=scale.updated_at,
        grades=[
            GradeResponse(
                id=g.id,
                grading_scale_id=g.grading_scale_id,
                grade=g.grade,
                min_score=g.min_score,
                max_score=g.max_score,
                grade_point=g.grade_point,
                remark=g.remark,
            ) for g in scale.grades
        ],
    )


@router.put(
    "/grading-scales/{scale_id}",
    response_model=GradingScaleResponse,
    summary="Update grading scale",
    dependencies=[Depends(require_permissions("grading.update"))],
)
async def update_grading_scale(
    scale_id: UUID,
    data: GradingScaleUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> GradingScaleResponse:
    """Update a grading scale."""
    service = AcademicService(db)
    scale = await service.update_grading_scale(scale_id, tenant.tenant_id, **data.model_dump(exclude_unset=True))
    if not scale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading scale not found")

    return GradingScaleResponse(
        id=scale.id,
        name=scale.name,
        description=scale.description,
        scale_type=scale.scale_type.value,
        is_default=scale.is_default,
        is_active=scale.is_active,
        created_at=scale.created_at,
        updated_at=scale.updated_at,
    )


@router.delete(
    "/grading-scales/{scale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete grading scale",
    dependencies=[Depends(require_permissions("grading.delete"))],
)
async def delete_grading_scale(
    scale_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a grading scale."""
    service = AcademicService(db)
    deleted = await service.delete_grading_scale(tenant.tenant_id, scale_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading scale not found")


# =========================
# Assessment Weight Endpoints
# =========================


@router.get(
    "/assessment-weights",
    response_model=AssessmentWeightResponse,
    summary="Get assessment weights",
    dependencies=[Depends(require_permissions("grading.read"))],
)
async def get_assessment_weights(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    academic_year_id: Optional[UUID] = Query(None),
) -> AssessmentWeightResponse:
    """Get assessment weights."""
    service = AcademicService(db)
    weights = await service.get_assessment_weights(tenant.tenant_id, academic_year_id)
    if not weights:
        # Return defaults
        return AssessmentWeightResponse(
            id=None,
            academic_year_id=None,
            class_work_weight=20,
            homework_weight=10,
            midterm_weight=20,
            end_term_weight=50,
            ca_total_weight=50,
            exam_total_weight=50,
            created_at=None,
            updated_at=None,
        )

    return AssessmentWeightResponse(
        id=weights.id,
        academic_year_id=weights.academic_year_id,
        class_work_weight=weights.class_work_weight,
        homework_weight=weights.homework_weight,
        midterm_weight=weights.midterm_weight,
        end_term_weight=weights.end_term_weight,
        ca_total_weight=weights.ca_total_weight,
        exam_total_weight=weights.exam_total_weight,
        created_at=weights.created_at,
        updated_at=weights.updated_at,
    )


@router.put(
    "/assessment-weights",
    response_model=AssessmentWeightResponse,
    summary="Set assessment weights",
    dependencies=[Depends(require_permissions("grading.update"))],
)
async def set_assessment_weights(
    data: AssessmentWeightCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AssessmentWeightResponse:
    """Set assessment weights."""
    service = AcademicService(db)
    weights = await service.set_assessment_weights(
        tenant_id=tenant.tenant_id,
        academic_year_id=data.academic_year_id,
        class_work_weight=data.class_work_weight,
        homework_weight=data.homework_weight,
        midterm_weight=data.midterm_weight,
        end_term_weight=data.end_term_weight,
        ca_total_weight=data.ca_total_weight,
        exam_total_weight=data.exam_total_weight,
    )

    return AssessmentWeightResponse(
        id=weights.id,
        academic_year_id=weights.academic_year_id,
        class_work_weight=weights.class_work_weight,
        homework_weight=weights.homework_weight,
        midterm_weight=weights.midterm_weight,
        end_term_weight=weights.end_term_weight,
        ca_total_weight=weights.ca_total_weight,
        exam_total_weight=weights.exam_total_weight,
        created_at=weights.created_at,
        updated_at=weights.updated_at,
    )


# =========================
# Academic Settings Endpoints
# =========================


@router.get(
    "/settings",
    response_model=AcademicSettingsResponse,
    summary="Get academic settings",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_academic_settings(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AcademicSettingsResponse:
    """Get academic settings for the current tenant."""
    service = AcademicService(db)
    settings = await service.get_academic_settings(tenant.tenant_id)

    if not settings:
        # Return defaults
        return AcademicSettingsResponse(
            id=None,
            auto_promote_students=False,
            allow_grade_amendments=True,
            show_position_on_report_cards=True,
            require_attendance_for_exams=False,
            enable_continuous_assessment=True,
            created_at=None,
            updated_at=None,
        )

    return AcademicSettingsResponse(
        id=settings.id,
        auto_promote_students=settings.auto_promote_students,
        allow_grade_amendments=settings.allow_grade_amendments,
        show_position_on_report_cards=settings.show_position_on_report_cards,
        require_attendance_for_exams=settings.require_attendance_for_exams,
        enable_continuous_assessment=settings.enable_continuous_assessment,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


@router.put(
    "/settings",
    response_model=AcademicSettingsResponse,
    summary="Update academic settings",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_academic_settings(
    data: AcademicSettingsUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AcademicSettingsResponse:
    """Update academic settings for the current tenant."""
    service = AcademicService(db)
    settings = await service.update_academic_settings(
        tenant_id=tenant.tenant_id,
        auto_promote_students=data.auto_promote_students,
        allow_grade_amendments=data.allow_grade_amendments,
        show_position_on_report_cards=data.show_position_on_report_cards,
        require_attendance_for_exams=data.require_attendance_for_exams,
        enable_continuous_assessment=data.enable_continuous_assessment,
    )

    return AcademicSettingsResponse(
        id=settings.id,
        auto_promote_students=settings.auto_promote_students,
        allow_grade_amendments=settings.allow_grade_amendments,
        show_position_on_report_cards=settings.show_position_on_report_cards,
        require_attendance_for_exams=settings.require_attendance_for_exams,
        enable_continuous_assessment=settings.enable_continuous_assessment,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )

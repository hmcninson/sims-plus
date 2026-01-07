"""
SIMS Plus - Academic Endpoints

API endpoints for academic management (Sprint 6).
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.academic import (
    # Academic Year
    AcademicYearCreate,
    AcademicYearUpdate,
    AcademicYearResponse,
    AcademicYearWithTermsResponse,
    # Term
    TermCreate,
    TermUpdate,
    TermResponse,
    # Class
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    ClassWithSectionsResponse,
    # Section
    ClassSectionCreate,
    ClassSectionUpdate,
    ClassSectionResponse,
    # Subject
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    # Class Subject
    ClassSubjectCreate,
    ClassSubjectResponse,
    # Grading
    GradingScaleCreate,
    GradingScaleUpdate,
    GradingScaleResponse,
    GradingScaleWithGradesResponse,
    GradeCreate,
    GradeUpdate,
    GradeResponse,
    # Assessment
    AssessmentWeightCreate,
    AssessmentWeightResponse,
    # Academic Settings
    AcademicSettingsUpdate,
    AcademicSettingsResponse,
)
from app.services.academic import AcademicService, AcademicServiceError

router = APIRouter()


# =========================
# Academic Year Endpoints
# =========================


@router.post(
    "/academic-years",
    response_model=AcademicYearResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create academic year",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_academic_year(
    data: AcademicYearCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> AcademicYearResponse:
    """Create a new academic year."""
    service = AcademicService(db)
    try:
        academic_year = await service.create_academic_year(
            tenant_id=tenant.tenant_id,
            name=data.name,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
            is_current=data.is_current,
        )
        return AcademicYearResponse(
            id=academic_year.id,
            name=academic_year.name,
            description=academic_year.description,
            start_date=academic_year.start_date,
            end_date=academic_year.end_date,
            status=academic_year.status.value,
            is_current=academic_year.is_current,
            created_at=academic_year.created_at,
            updated_at=academic_year.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/academic-years",
    response_model=list[AcademicYearResponse],
    summary="List academic years",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def list_academic_years(
    tenant: RequestTenant,
    db: DatabaseSession,
    include_terms: bool = Query(False, description="Include terms in response"),
) -> list:
    """List all academic years."""
    service = AcademicService(db)
    years = await service.list_academic_years(tenant.tenant_id, include_terms=include_terms)

    response_model = AcademicYearWithTermsResponse if include_terms else AcademicYearResponse
    return [
        response_model(
            id=y.id,
            name=y.name,
            description=y.description,
            start_date=y.start_date,
            end_date=y.end_date,
            status=y.status.value,
            is_current=y.is_current,
            created_at=y.created_at,
            updated_at=y.updated_at,
            **({"terms": [
                TermResponse(
                    id=t.id,
                    academic_year_id=t.academic_year_id,
                    name=t.name,
                    short_name=t.short_name,
                    sequence=t.sequence,
                    start_date=t.start_date,
                    end_date=t.end_date,
                    status=t.status.value,
                    is_current=t.is_current,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                ) for t in y.terms
            ]} if include_terms else {}),
        )
        for y in years
    ]


@router.get(
    "/academic-years/{academic_year_id}",
    response_model=AcademicYearWithTermsResponse,
    summary="Get academic year",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_academic_year(
    academic_year_id: UUID,
    db: DatabaseSession,
) -> AcademicYearWithTermsResponse:
    """Get academic year by ID with terms."""
    service = AcademicService(db)
    year = await service.get_academic_year(academic_year_id, include_terms=True)
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    return AcademicYearWithTermsResponse(
        id=year.id,
        name=year.name,
        description=year.description,
        start_date=year.start_date,
        end_date=year.end_date,
        status=year.status.value,
        is_current=year.is_current,
        created_at=year.created_at,
        updated_at=year.updated_at,
        terms=[
            TermResponse(
                id=t.id,
                academic_year_id=t.academic_year_id,
                name=t.name,
                short_name=t.short_name,
                sequence=t.sequence,
                start_date=t.start_date,
                end_date=t.end_date,
                status=t.status.value,
                is_current=t.is_current,
                created_at=t.created_at,
                updated_at=t.updated_at,
            ) for t in year.terms
        ],
    )


@router.put(
    "/academic-years/{academic_year_id}",
    response_model=AcademicYearResponse,
    summary="Update academic year",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_academic_year(
    academic_year_id: UUID,
    data: AcademicYearUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> AcademicYearResponse:
    """Update an academic year."""
    service = AcademicService(db)
    year = await service.update_academic_year(
        academic_year_id,
        tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )
    if not year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    return AcademicYearResponse(
        id=year.id,
        name=year.name,
        description=year.description,
        start_date=year.start_date,
        end_date=year.end_date,
        status=year.status.value,
        is_current=year.is_current,
        created_at=year.created_at,
        updated_at=year.updated_at,
    )


@router.delete(
    "/academic-years/{academic_year_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete academic year",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_academic_year(
    academic_year_id: UUID,
    db: DatabaseSession,
) -> None:
    """Delete an academic year."""
    service = AcademicService(db)
    deleted = await service.delete_academic_year(academic_year_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")


# =========================
# Term Endpoints
# =========================


@router.post(
    "/terms",
    response_model=TermResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create term",
    dependencies=[Depends(require_permissions("academics.create"))],
)
async def create_term(
    data: TermCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TermResponse:
    """Create a new term."""
    service = AcademicService(db)
    try:
        term = await service.create_term(
            tenant_id=tenant.tenant_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            short_name=data.short_name,
            sequence=data.sequence,
            start_date=data.start_date,
            end_date=data.end_date,
        )
        return TermResponse(
            id=term.id,
            academic_year_id=term.academic_year_id,
            name=term.name,
            short_name=term.short_name,
            sequence=term.sequence,
            start_date=term.start_date,
            end_date=term.end_date,
            status=term.status.value,
            is_current=term.is_current,
            created_at=term.created_at,
            updated_at=term.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/terms",
    response_model=list[TermResponse],
    summary="List terms",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def list_terms(
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None, description="Filter by academic year"),
) -> list[TermResponse]:
    """List all terms."""
    service = AcademicService(db)
    terms = await service.list_terms(tenant.tenant_id, academic_year_id)
    return [
        TermResponse(
            id=t.id,
            academic_year_id=t.academic_year_id,
            name=t.name,
            short_name=t.short_name,
            sequence=t.sequence,
            start_date=t.start_date,
            end_date=t.end_date,
            status=t.status.value,
            is_current=t.is_current,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in terms
    ]


@router.get(
    "/terms/{term_id}",
    response_model=TermResponse,
    summary="Get term",
    dependencies=[Depends(require_permissions("academics.read"))],
)
async def get_term(
    term_id: UUID,
    db: DatabaseSession,
) -> TermResponse:
    """Get term by ID."""
    service = AcademicService(db)
    term = await service.get_term(term_id)
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

    return TermResponse(
        id=term.id,
        academic_year_id=term.academic_year_id,
        name=term.name,
        short_name=term.short_name,
        sequence=term.sequence,
        start_date=term.start_date,
        end_date=term.end_date,
        status=term.status.value,
        is_current=term.is_current,
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


@router.put(
    "/terms/{term_id}",
    response_model=TermResponse,
    summary="Update term",
    dependencies=[Depends(require_permissions("academics.update"))],
)
async def update_term(
    term_id: UUID,
    data: TermUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TermResponse:
    """Update a term."""
    service = AcademicService(db)
    term = await service.update_term(term_id, tenant.tenant_id, **data.model_dump(exclude_unset=True))
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

    return TermResponse(
        id=term.id,
        academic_year_id=term.academic_year_id,
        name=term.name,
        short_name=term.short_name,
        sequence=term.sequence,
        start_date=term.start_date,
        end_date=term.end_date,
        status=term.status.value,
        is_current=term.is_current,
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


@router.delete(
    "/terms/{term_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete term",
    dependencies=[Depends(require_permissions("academics.delete"))],
)
async def delete_term(
    term_id: UUID,
    db: DatabaseSession,
) -> None:
    """Delete a term."""
    service = AcademicService(db)
    deleted = await service.delete_term(term_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")


# =========================
# Class Endpoints
# =========================


@router.post(
    "/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create class",
    dependencies=[Depends(require_permissions("classes.create"))],
)
async def create_class(
    data: ClassCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ClassResponse:
    """Create a new class."""
    service = AcademicService(db)
    try:
        class_ = await service.create_class(
            tenant_id=tenant.tenant_id,
            name=data.name,
            short_name=data.short_name,
            level=data.level,
            sequence=data.sequence,
            capacity=data.capacity,
            school_id=data.school_id,
        )
        return ClassResponse(
            id=class_.id,
            name=class_.name,
            short_name=class_.short_name,
            level=class_.level.value if class_.level else None,
            sequence=class_.sequence,
            capacity=class_.capacity,
            school_id=class_.school_id,
            is_active=class_.is_active,
            created_at=class_.created_at,
            updated_at=class_.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/classes",
    response_model=list[ClassWithSectionsResponse],
    summary="List classes",
    dependencies=[Depends(require_permissions("classes.read"))],
)
async def list_classes(
    tenant: RequestTenant,
    db: DatabaseSession,
    school_id: Optional[UUID] = Query(None),
    include_sections: bool = Query(False),
    active_only: bool = Query(True),
    include_student_counts: bool = Query(True, description="Include student counts per class"),
) -> list:
    """List all classes with optional student counts."""
    service = AcademicService(db)
    classes = await service.list_classes(
        tenant.tenant_id,
        school_id=school_id,
        include_sections=include_sections,
        active_only=active_only,
    )

    # Get student counts per class if requested
    student_counts = {}
    if include_student_counts and classes:
        from sqlalchemy import select, func
        from app.models.student import Student, Gender

        class_ids = [c.id for c in classes]

        # Query for total, male, and female counts per class
        count_query = (
            select(
                Student.class_id,
                func.count(Student.id).label("total"),
                func.count(Student.id).filter(Student.gender == Gender.MALE).label("male"),
                func.count(Student.id).filter(Student.gender == Gender.FEMALE).label("female"),
            )
            .where(
                Student.tenant_id == tenant.tenant_id,
                Student.class_id.in_(class_ids),
                Student.deleted_at.is_(None),
            )
            .group_by(Student.class_id)
        )
        result = await db.execute(count_query)
        for row in result.all():
            student_counts[row.class_id] = {
                "total": row.total,
                "male": row.male,
                "female": row.female,
            }

    # Get section student counts if sections are included
    section_counts: dict = {}
    if include_sections and classes:
        from sqlalchemy import select, func
        from app.models.student import Student, Gender

        # Collect all section IDs
        section_ids = []
        for c in classes:
            for s in c.sections:
                section_ids.append(s.id)

        if section_ids:
            section_count_query = (
                select(
                    Student.section_id,
                    func.count(Student.id).label("total"),
                    func.count(Student.id).filter(Student.gender == Gender.MALE).label("male"),
                    func.count(Student.id).filter(Student.gender == Gender.FEMALE).label("female"),
                )
                .where(
                    Student.tenant_id == tenant.tenant_id,
                    Student.section_id.in_(section_ids),
                    Student.deleted_at.is_(None),
                )
                .group_by(Student.section_id)
            )
            section_result = await db.execute(section_count_query)
            for row in section_result.all():
                section_counts[row.section_id] = {
                    "total": row.total,
                    "male": row.male,
                    "female": row.female,
                }

    response_model = ClassWithSectionsResponse if include_sections else ClassResponse
    return [
        response_model(
            id=c.id,
            name=c.name,
            short_name=c.short_name,
            level=c.level.value if c.level else None,
            sequence=c.sequence,
            capacity=c.capacity,
            school_id=c.school_id,
            is_active=c.is_active,
            created_at=c.created_at,
            updated_at=c.updated_at,
            student_count=student_counts.get(c.id, {}).get("total", 0),
            male_count=student_counts.get(c.id, {}).get("male", 0),
            female_count=student_counts.get(c.id, {}).get("female", 0),
            **({"sections": [
                ClassSectionResponse(
                    id=s.id,
                    class_id=s.class_id,
                    name=s.name,
                    capacity=s.capacity,
                    class_teacher_id=s.class_teacher_id,
                    is_active=s.is_active,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                    student_count=section_counts.get(s.id, {}).get("total", 0),
                    male_count=section_counts.get(s.id, {}).get("male", 0),
                    female_count=section_counts.get(s.id, {}).get("female", 0),
                ) for s in c.sections
            ]} if include_sections else {}),
        )
        for c in classes
    ]


@router.get(
    "/classes/{class_id}",
    response_model=ClassWithSectionsResponse,
    summary="Get class",
    dependencies=[Depends(require_permissions("classes.read"))],
)
async def get_class(
    class_id: UUID,
    db: DatabaseSession,
) -> ClassWithSectionsResponse:
    """Get class by ID with sections."""
    service = AcademicService(db)
    class_ = await service.get_class(class_id, include_sections=True)
    if not class_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    return ClassWithSectionsResponse(
        id=class_.id,
        name=class_.name,
        short_name=class_.short_name,
        level=class_.level.value if class_.level else None,
        sequence=class_.sequence,
        capacity=class_.capacity,
        school_id=class_.school_id,
        is_active=class_.is_active,
        created_at=class_.created_at,
        updated_at=class_.updated_at,
        sections=[
            ClassSectionResponse(
                id=s.id,
                class_id=s.class_id,
                name=s.name,
                capacity=s.capacity,
                class_teacher_id=s.class_teacher_id,
                is_active=s.is_active,
                created_at=s.created_at,
                updated_at=s.updated_at,
            ) for s in class_.sections
        ],
    )


@router.put(
    "/classes/{class_id}",
    response_model=ClassResponse,
    summary="Update class",
    dependencies=[Depends(require_permissions("classes.update"))],
)
async def update_class(
    class_id: UUID,
    data: ClassUpdate,
    db: DatabaseSession,
) -> ClassResponse:
    """Update a class."""
    service = AcademicService(db)
    class_ = await service.update_class(class_id, **data.model_dump(exclude_unset=True))
    if not class_:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    return ClassResponse(
        id=class_.id,
        name=class_.name,
        short_name=class_.short_name,
        level=class_.level.value if class_.level else None,
        sequence=class_.sequence,
        capacity=class_.capacity,
        school_id=class_.school_id,
        is_active=class_.is_active,
        created_at=class_.created_at,
        updated_at=class_.updated_at,
    )


@router.delete(
    "/classes/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete class",
    dependencies=[Depends(require_permissions("classes.delete"))],
)
async def delete_class(
    class_id: UUID,
    db: DatabaseSession,
) -> None:
    """Delete a class."""
    service = AcademicService(db)
    deleted = await service.delete_class(class_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")


# =========================
# Class Section Endpoints
# =========================


@router.post(
    "/sections",
    response_model=ClassSectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create section",
    dependencies=[Depends(require_permissions("classes.create"))],
)
async def create_section(
    data: ClassSectionCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ClassSectionResponse:
    """Create a new class section."""
    service = AcademicService(db)
    try:
        section = await service.create_section(
            tenant_id=tenant.tenant_id,
            class_id=data.class_id,
            name=data.name,
            capacity=data.capacity,
            class_teacher_id=data.class_teacher_id,
        )
        return ClassSectionResponse(
            id=section.id,
            class_id=section.class_id,
            name=section.name,
            capacity=section.capacity,
            class_teacher_id=section.class_teacher_id,
            is_active=section.is_active,
            created_at=section.created_at,
            updated_at=section.updated_at,
        )
    except AcademicServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/sections",
    response_model=list[ClassSectionResponse],
    summary="List sections",
    dependencies=[Depends(require_permissions("classes.read"))],
)
async def list_sections(
    tenant: RequestTenant,
    db: DatabaseSession,
    class_id: Optional[UUID] = Query(None),
    active_only: bool = Query(True),
) -> list[ClassSectionResponse]:
    """List all sections."""
    service = AcademicService(db)
    sections = await service.list_sections(tenant.tenant_id, class_id=class_id, active_only=active_only)
    return [
        ClassSectionResponse(
            id=s.id,
            class_id=s.class_id,
            name=s.name,
            capacity=s.capacity,
            class_teacher_id=s.class_teacher_id,
            is_active=s.is_active,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sections
    ]


@router.put(
    "/sections/{section_id}",
    response_model=ClassSectionResponse,
    summary="Update section",
    dependencies=[Depends(require_permissions("classes.update"))],
)
async def update_section(
    section_id: UUID,
    data: ClassSectionUpdate,
    db: DatabaseSession,
) -> ClassSectionResponse:
    """Update a section."""
    service = AcademicService(db)
    section = await service.update_section(section_id, **data.model_dump(exclude_unset=True))
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    return ClassSectionResponse(
        id=section.id,
        class_id=section.class_id,
        name=section.name,
        capacity=section.capacity,
        class_teacher_id=section.class_teacher_id,
        is_active=section.is_active,
        created_at=section.created_at,
        updated_at=section.updated_at,
    )


@router.delete(
    "/sections/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete section",
    dependencies=[Depends(require_permissions("classes.delete"))],
)
async def delete_section(
    section_id: UUID,
    db: DatabaseSession,
) -> None:
    """Delete a section."""
    service = AcademicService(db)
    deleted = await service.delete_section(section_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")


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
    category: Optional[str] = Query(None),
    active_only: bool = Query(True),
) -> list[SubjectResponse]:
    """List all subjects."""
    service = AcademicService(db)
    subjects = await service.list_subjects(tenant.tenant_id, category=category, active_only=active_only)
    return [
        SubjectResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            description=s.description,
            category=s.category.value if hasattr(s.category, 'value') else s.category,
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
    db: DatabaseSession,
) -> SubjectResponse:
    """Get subject by ID."""
    service = AcademicService(db)
    subject = await service.get_subject(subject_id)
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


@router.put(
    "/subjects/{subject_id}",
    response_model=SubjectResponse,
    summary="Update subject",
    dependencies=[Depends(require_permissions("subjects.update"))],
)
async def update_subject(
    subject_id: UUID,
    data: SubjectUpdate,
    db: DatabaseSession,
) -> SubjectResponse:
    """Update a subject."""
    service = AcademicService(db)
    subject = await service.update_subject(subject_id, **data.model_dump(exclude_unset=True))
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
    db: DatabaseSession,
) -> None:
    """Delete a subject."""
    service = AcademicService(db)
    deleted = await service.delete_subject(subject_id)
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
    db: DatabaseSession,
) -> None:
    """Remove a subject assignment from a class."""
    service = AcademicService(db)
    deleted = await service.remove_subject_from_class(class_id, subject_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject assignment not found")


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
        scale = await service.get_grading_scale(scale.id, include_grades=True)

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
    db: DatabaseSession,
) -> GradingScaleWithGradesResponse:
    """Get grading scale by ID with grades."""
    service = AcademicService(db)
    scale = await service.get_grading_scale(scale_id, include_grades=True)
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
    db: DatabaseSession,
) -> None:
    """Delete a grading scale."""
    service = AcademicService(db)
    deleted = await service.delete_grading_scale(scale_id)
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
    )

    return AssessmentWeightResponse(
        id=weights.id,
        academic_year_id=weights.academic_year_id,
        class_work_weight=weights.class_work_weight,
        homework_weight=weights.homework_weight,
        midterm_weight=weights.midterm_weight,
        end_term_weight=weights.end_term_weight,
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

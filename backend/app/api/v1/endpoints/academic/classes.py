"""
SIMS Plus - Class and Section Endpoints
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
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    ClassWithSectionsResponse,
    ClassSectionCreate,
    ClassSectionUpdate,
    ClassSectionResponse,
)
from app.services.academic import AcademicService, AcademicServiceError

router = APIRouter()


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
    current_user: ValidatedUser,
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
        # Return 409 Conflict for duplicate class names so the frontend
        # can distinguish duplicates from other validation errors
        if e.code == "duplicate_class":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
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
    current_user: ValidatedUser,
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
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> ClassWithSectionsResponse:
    """Get class by ID with sections."""
    service = AcademicService(db)
    class_ = await service.get_class(tenant.tenant_id, class_id, include_sections=True)
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
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> ClassResponse:
    """Update a class."""
    service = AcademicService(db)
    class_ = await service.update_class(tenant.tenant_id, class_id, **data.model_dump(exclude_unset=True))
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
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a class."""
    service = AcademicService(db)
    deleted = await service.delete_class(tenant.tenant_id, class_id)
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
    current_user: ValidatedUser,
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
        # Return 409 for duplicates so the frontend can handle them gracefully
        if e.code in ("duplicate_section", "class_not_found"):
            http_status = (
                status.HTTP_409_CONFLICT
                if e.code == "duplicate_section"
                else status.HTTP_404_NOT_FOUND
            )
            raise HTTPException(status_code=http_status, detail=e.message)
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
    current_user: ValidatedUser,
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
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> ClassSectionResponse:
    """Update a section."""
    service = AcademicService(db)
    section = await service.update_section(tenant.tenant_id, section_id, **data.model_dump(exclude_unset=True))
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
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Delete a section."""
    service = AcademicService(db)
    deleted = await service.delete_section(tenant.tenant_id, section_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

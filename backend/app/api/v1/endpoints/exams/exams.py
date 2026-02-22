"""
SIMS Plus - Exam CRUD and Exam Subject Endpoints
"""

from typing import Optional
from uuid import UUID
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.exam import (
    ExamCreate,
    ExamUpdate,
    ExamStatusUpdate,
    ExamResponse,
    ExamWithContextResponse,
    ExamListResponse,
    ExamSubjectBulkCreate,
    ExamSubjectAutoPopulate,
    ExamSubjectUpdate,
    ExamSubjectResponse,
    ExamSubjectWithDetailsResponse,
)
from app.services.exam import ExamService, ExamServiceError
from app.models.student import Student
from app.models.exam import ExamSubject

router = APIRouter()


# =========================
# Exam CRUD Endpoints
# =========================


@router.post(
    "/",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create exam",
    dependencies=[Depends(require_permissions("exams.create"))],
)
async def create_exam(
    data: ExamCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ExamResponse:
    """Create a new examination."""
    service = ExamService(db)
    try:
        exam = await service.create_exam(
            tenant_id=tenant.tenant_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            name=data.name,
            description=data.description,
            exam_type=data.exam_type,
            start_date=data.start_date,
            end_date=data.end_date,
            created_by=user_id,
        )
        return ExamResponse(
            id=exam.id,
            tenant_id=exam.tenant_id,
            academic_year_id=exam.academic_year_id,
            term_id=exam.term_id,
            name=exam.name,
            description=exam.description,
            exam_type=exam.exam_type.value,
            start_date=exam.start_date,
            end_date=exam.end_date,
            status=exam.status.value,
            created_by=exam.created_by,
            created_at=exam.created_at,
            updated_at=exam.updated_at,
        )
    except ExamServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/",
    response_model=ExamListResponse,
    summary="List exams",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def list_exams(
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    exam_type: Optional[str] = Query(None),
    exam_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ExamListResponse:
    """List all exams with filters."""
    service = ExamService(db)
    exams, total = await service.list_exams(
        tenant_id=tenant.tenant_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        exam_type=exam_type,
        status=exam_status,
        page=page,
        page_size=page_size,
    )

    items = []
    for exam in exams:
        # Count subjects
        subjects_count = len(exam.subjects) if hasattr(exam, "subjects") else 0

        items.append(ExamWithContextResponse(
            id=exam.id,
            tenant_id=exam.tenant_id,
            academic_year_id=exam.academic_year_id,
            term_id=exam.term_id,
            name=exam.name,
            description=exam.description,
            exam_type=exam.exam_type.value,
            start_date=exam.start_date,
            end_date=exam.end_date,
            status=exam.status.value,
            created_by=exam.created_by,
            created_at=exam.created_at,
            updated_at=exam.updated_at,
            academic_year_name=exam.academic_year.name if exam.academic_year else None,
            term_name=exam.term.name if exam.term else None,
            subjects_count=subjects_count,
        ))

    return ExamListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/{exam_id}",
    response_model=ExamWithContextResponse,
    summary="Get exam",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_exam(
    exam_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    include_subjects: bool = Query(False),
) -> ExamWithContextResponse:
    """Get exam by ID."""
    service = ExamService(db)
    exam = await service.get_exam(tenant.tenant_id, exam_id, include_subjects=include_subjects)

    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    subjects_count = len(exam.subjects) if hasattr(exam, "subjects") and exam.subjects else 0

    return ExamWithContextResponse(
        id=exam.id,
        tenant_id=exam.tenant_id,
        academic_year_id=exam.academic_year_id,
        term_id=exam.term_id,
        name=exam.name,
        description=exam.description,
        exam_type=exam.exam_type.value,
        start_date=exam.start_date,
        end_date=exam.end_date,
        status=exam.status.value,
        created_by=exam.created_by,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        academic_year_name=exam.academic_year.name if exam.academic_year else None,
        term_name=exam.term.name if exam.term else None,
        subjects_count=subjects_count,
    )


@router.put(
    "/{exam_id}",
    response_model=ExamResponse,
    summary="Update exam",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def update_exam(
    exam_id: UUID,
    data: ExamUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ExamResponse:
    """Update an exam."""
    service = ExamService(db)
    exam = await service.update_exam(
        exam_id=exam_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )

    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    return ExamResponse(
        id=exam.id,
        tenant_id=exam.tenant_id,
        academic_year_id=exam.academic_year_id,
        term_id=exam.term_id,
        name=exam.name,
        description=exam.description,
        exam_type=exam.exam_type.value,
        start_date=exam.start_date,
        end_date=exam.end_date,
        status=exam.status.value,
        created_by=exam.created_by,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


@router.patch(
    "/{exam_id}/status",
    response_model=ExamResponse,
    summary="Update exam status",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def update_exam_status(
    exam_id: UUID,
    data: ExamStatusUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ExamResponse:
    """Update exam status."""
    service = ExamService(db)
    exam = await service.update_exam_status(
        exam_id=exam_id,
        tenant_id=tenant.tenant_id,
        status=data.status,
    )

    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    return ExamResponse(
        id=exam.id,
        tenant_id=exam.tenant_id,
        academic_year_id=exam.academic_year_id,
        term_id=exam.term_id,
        name=exam.name,
        description=exam.description,
        exam_type=exam.exam_type.value,
        start_date=exam.start_date,
        end_date=exam.end_date,
        status=exam.status.value,
        created_by=exam.created_by,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


@router.delete(
    "/{exam_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete exam",
    dependencies=[Depends(require_permissions("exams.delete"))],
)
async def delete_exam(
    exam_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Delete an exam (soft delete)."""
    service = ExamService(db)
    deleted = await service.delete_exam(exam_id, tenant.tenant_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )


# =========================
# Exam Subject Endpoints
# =========================


@router.post(
    "/{exam_id}/subjects",
    response_model=list[ExamSubjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add subjects to exam",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def add_exam_subjects(
    exam_id: UUID,
    data: ExamSubjectBulkCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> list[ExamSubjectResponse]:
    """Add subjects to an exam for multiple classes."""
    service = ExamService(db)

    # Verify exam exists and belongs to this tenant
    exam = await service.get_exam(tenant.tenant_id, exam_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    subjects = await service.add_exam_subjects_bulk(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
        class_ids=data.class_ids,
        section_ids=data.section_ids,
        subject_ids=data.subject_ids,
        grading_scale_id=data.grading_scale_id,
        max_score=data.max_score,
        pass_mark=data.pass_mark,
    )

    return [
        ExamSubjectResponse(
            id=es.id,
            tenant_id=es.tenant_id,
            exam_id=es.exam_id,
            subject_id=es.subject_id,
            class_id=es.class_id,
            section_id=es.section_id,
            grading_scale_id=es.grading_scale_id,
            max_score=es.max_score,
            pass_mark=es.pass_mark,
            exam_date=es.exam_date,
            exam_time=es.exam_time,
            duration_minutes=es.duration_minutes,
            venue=es.venue,
            status=es.status.value,
            created_at=es.created_at,
            updated_at=es.updated_at,
        )
        for es in subjects
    ]


@router.post(
    "/{exam_id}/subjects/auto-populate",
    response_model=list[ExamSubjectWithDetailsResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Auto-populate subjects from curriculum",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def auto_populate_exam_subjects(
    exam_id: UUID,
    data: ExamSubjectAutoPopulate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> list[ExamSubjectWithDetailsResponse]:
    """
    Auto-populate exam subjects from curriculum (ClassSubjects).

    Fetches all subjects assigned to the selected classes and creates
    ExamSubject records for each class-subject combination.
    """
    service = ExamService(db)

    # Verify exam exists and belongs to this tenant
    exam = await service.get_exam(tenant.tenant_id, exam_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    try:
        subjects = await service.auto_populate_from_curriculum(
            tenant_id=tenant.tenant_id,
            exam_id=exam_id,
            class_ids=data.class_ids,
            max_score=data.max_score,
            pass_mark=data.pass_mark,
            grading_scale_id=data.grading_scale_id,
        )
    except ExamServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    # Get unique class IDs and fetch student counts
    class_ids = list(set(es.class_id for es in subjects))
    students_count_map: dict[UUID, int] = {}
    if class_ids:
        counts_result = await db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(
                Student.tenant_id == tenant.tenant_id,
                Student.class_id.in_(class_ids),
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
            .group_by(Student.class_id)
        )
        for class_id, count in counts_result.all():
            students_count_map[class_id] = count

    return [
        ExamSubjectWithDetailsResponse(
            id=es.id,
            tenant_id=es.tenant_id,
            exam_id=es.exam_id,
            subject_id=es.subject_id,
            class_id=es.class_id,
            section_id=es.section_id,
            grading_scale_id=es.grading_scale_id,
            max_score=es.max_score,
            pass_mark=es.pass_mark,
            exam_date=es.exam_date,
            exam_time=es.exam_time,
            duration_minutes=es.duration_minutes,
            venue=es.venue,
            status=es.status.value,
            created_at=es.created_at,
            updated_at=es.updated_at,
            subject_name=es.subject.name if es.subject else None,
            subject_code=es.subject.code if es.subject else None,
            class_name=es.class_.name if es.class_ else None,
            class_sequence=es.class_.sequence if es.class_ else 0,
            section_name=es.section.name if es.section else None,
            grading_scale_name=es.grading_scale.name if es.grading_scale else None,
            scores_count=len(es.scores) if es.scores else 0,
            students_count=students_count_map.get(es.class_id, 0),
        )
        for es in subjects
    ]


@router.get(
    "/{exam_id}/subjects",
    response_model=list[ExamSubjectWithDetailsResponse],
    summary="List exam subjects",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def list_exam_subjects(
    exam_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> list[ExamSubjectWithDetailsResponse]:
    """List all subjects for an exam."""
    service = ExamService(db)

    # Verify exam exists and belongs to this tenant
    exam = await service.get_exam(tenant.tenant_id, exam_id)
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    subjects = await service.list_exam_subjects(tenant.tenant_id, exam_id)

    # Get unique class IDs and section IDs for student counts
    class_ids = list(set(es.class_id for es in subjects))
    section_ids = list(set(es.section_id for es in subjects if es.section_id))

    # Maps for student counts: by class (for whole-class exams) and by section
    class_students_count: dict[UUID, int] = {}
    section_students_count: dict[UUID, int] = {}

    if class_ids:
        # Query student counts per class (only active, enrolled students)
        counts_result = await db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(
                Student.tenant_id == tenant.tenant_id,
                Student.class_id.in_(class_ids),
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
            .group_by(Student.class_id)
        )
        for class_id, count in counts_result.all():
            class_students_count[class_id] = count

    if section_ids:
        # Query student counts per section
        section_counts_result = await db.execute(
            select(Student.section_id, func.count(Student.id))
            .where(
                Student.tenant_id == tenant.tenant_id,
                Student.section_id.in_(section_ids),
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
            .group_by(Student.section_id)
        )
        for section_id, count in section_counts_result.all():
            section_students_count[section_id] = count

    def get_student_count(es: ExamSubject) -> int:
        """Get student count: use section count if section specified, else class count."""
        if es.section_id:
            return section_students_count.get(es.section_id, 0)
        return class_students_count.get(es.class_id, 0)

    return [
        ExamSubjectWithDetailsResponse(
            id=es.id,
            tenant_id=es.tenant_id,
            exam_id=es.exam_id,
            subject_id=es.subject_id,
            class_id=es.class_id,
            section_id=es.section_id,
            grading_scale_id=es.grading_scale_id,
            max_score=es.max_score,
            pass_mark=es.pass_mark,
            exam_date=es.exam_date,
            exam_time=es.exam_time,
            duration_minutes=es.duration_minutes,
            venue=es.venue,
            status=es.status.value,
            created_at=es.created_at,
            updated_at=es.updated_at,
            subject_name=es.subject.name if es.subject else None,
            subject_code=es.subject.code if es.subject else None,
            class_name=es.class_.name if es.class_ else None,
            class_sequence=es.class_.sequence if es.class_ else 0,
            section_name=es.section.name if es.section else None,
            grading_scale_name=es.grading_scale.name if es.grading_scale else None,
            scores_count=len(es.scores) if hasattr(es, "scores") and es.scores else 0,
            students_count=get_student_count(es),
        )
        for es in subjects
    ]


@router.put(
    "/{exam_id}/subjects/{exam_subject_id}",
    response_model=ExamSubjectResponse,
    summary="Update exam subject",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def update_exam_subject(
    exam_id: UUID,
    exam_subject_id: UUID,
    data: ExamSubjectUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ExamSubjectResponse:
    """Update an exam subject."""
    service = ExamService(db)
    es = await service.update_exam_subject(
        exam_subject_id=exam_subject_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )

    if not es:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam subject not found",
        )

    return ExamSubjectResponse(
        id=es.id,
        tenant_id=es.tenant_id,
        exam_id=es.exam_id,
        subject_id=es.subject_id,
        class_id=es.class_id,
        max_score=es.max_score,
        pass_mark=es.pass_mark,
        exam_date=es.exam_date,
        exam_time=es.exam_time,
        duration_minutes=es.duration_minutes,
        venue=es.venue,
        status=es.status.value,
        created_at=es.created_at,
        updated_at=es.updated_at,
    )


@router.delete(
    "/{exam_id}/subjects/{exam_subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove exam subject",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def delete_exam_subject(
    exam_id: UUID,
    exam_subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Remove a subject from an exam."""
    service = ExamService(db)
    deleted = await service.delete_exam_subject(exam_subject_id, tenant.tenant_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam subject not found",
        )

"""
SIMS Plus - Examination Endpoints

API endpoints for examination management, score entry, CA, and results.
"""

from typing import Optional
from uuid import UUID
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.exam import (
    # Exam
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    ExamWithContextResponse,
    ExamListResponse,
    # Exam Subject
    ExamSubjectCreate,
    ExamSubjectBulkCreate,
    ExamSubjectAutoPopulate,
    ExamSubjectUpdate,
    ExamSubjectResponse,
    ExamSubjectWithDetailsResponse,
    # Scores
    ScoreEntry,
    ExamScoreBulkCreate,
    ExamScoreUpdate,
    ExamScoreResponse,
    ExamScoreWithStudentResponse,
    ScoreEntryFormResponse,
    BulkScoreResult,
    ScoreChangeLogResponse,
    ScoreChangeLogListResponse,
    # CA
    CACreate,
    CABulkCreate,
    CAUpdate,
    CAResponse,
    CAWithDetailsResponse,
    CASummaryResponse,
    # Results
    SubjectResult,
    StudentExamResult,
    ClassResultsResponse,
    # Term Reports
    TermReportGenerate,
    TermReportRemarksUpdate,
    TermReportResponse,
    TermReportWithDetailsResponse,
    TermReportListResponse,
    # Analytics
    GradeDistributionResponse,
    ClassStatisticsResponse,
    SubjectStatisticsResponse,
    SubjectRankingsResponse,
    # Timetable
    ExamTimetableResponse,
    TimetableConflictsResponse,
    BulkTimetableUpdate,
    BulkTimetableUpdateResult,
)
from app.services.exam import (
    ExamService,
    ScoreService,
    CAService,
    TermReportService,
    AnalyticsService,
    ExamServiceError,
)
from app.models.student import Student
from app.models.exam import ExamSubject

router = APIRouter()


# =========================
# Exam CRUD Endpoints
# =========================


@router.post(
    "",
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
    "",
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


# =========================
# Continuous Assessment Endpoints (before dynamic routes)
# =========================


@router.post(
    "/ca",
    response_model=CAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create CA entry",
    dependencies=[Depends(require_permissions("exams.ca.enter"))],
)
async def create_ca(
    data: CACreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> CAResponse:
    """Create a continuous assessment entry."""
    from app.services.academic import AcademicService
    academic_service = AcademicService(db)
    term = await academic_service.get_term(data.term_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = CAService(db)
    ca = await service.create_ca(
        tenant_id=tenant.tenant_id,
        academic_year_id=term.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        student_id=data.student_id,
        assessment_type=data.assessment_type,
        title=data.title,
        assessment_date=data.assessment_date,
        max_score=data.max_score,
        score=data.score,
        entered_by=user_id,
    )

    return CAResponse(
        id=ca.id,
        tenant_id=ca.tenant_id,
        academic_year_id=ca.academic_year_id,
        term_id=ca.term_id,
        class_id=ca.class_id,
        subject_id=ca.subject_id,
        student_id=ca.student_id,
        assessment_type=ca.assessment_type.value,
        title=ca.title,
        max_score=ca.max_score,
        score=ca.score,
        assessment_date=ca.assessment_date,
        entered_by=ca.entered_by,
        created_at=ca.created_at,
        updated_at=ca.updated_at,
    )


@router.post(
    "/ca/bulk",
    response_model=BulkScoreResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create CA entries",
    dependencies=[Depends(require_permissions("exams.ca.enter"))],
)
async def bulk_create_ca(
    data: CABulkCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> BulkScoreResult:
    """Bulk create CA entries for a class."""
    from app.services.academic import AcademicService
    academic_service = AcademicService(db)
    term = await academic_service.get_term(data.term_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = CAService(db)
    result = await service.bulk_create_ca(
        tenant_id=tenant.tenant_id,
        academic_year_id=term.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        assessment_type=data.assessment_type,
        title=data.title,
        assessment_date=data.assessment_date,
        max_score=data.max_score,
        scores=[s.model_dump() for s in data.scores],
        entered_by=user_id,
    )

    return BulkScoreResult(**result)


@router.get(
    "/ca",
    response_model=list[CAWithDetailsResponse],
    summary="List CA entries",
    dependencies=[Depends(require_permissions("exams.ca.read"))],
)
async def list_ca(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: Optional[UUID] = Query(None),
    class_id: Optional[UUID] = Query(None),
    subject_id: Optional[UUID] = Query(None),
    student_id: Optional[UUID] = Query(None),
    assessment_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> list[CAWithDetailsResponse]:
    """List CA entries with filters."""
    service = CAService(db)
    entries, total = await service.list_ca(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        subject_id=subject_id,
        student_id=student_id,
        assessment_type=assessment_type,
        page=page,
        page_size=page_size,
    )

    return [
        CAWithDetailsResponse(
            id=ca.id,
            tenant_id=ca.tenant_id,
            academic_year_id=ca.academic_year_id,
            term_id=ca.term_id,
            class_id=ca.class_id,
            subject_id=ca.subject_id,
            student_id=ca.student_id,
            assessment_type=ca.assessment_type.value,
            title=ca.title,
            max_score=ca.max_score,
            score=ca.score,
            assessment_date=ca.assessment_date,
            entered_by=ca.entered_by,
            created_at=ca.created_at,
            updated_at=ca.updated_at,
            student_name=f"{ca.student.first_name} {ca.student.last_name}" if ca.student else "",
            student_id_number=ca.student.student_id if ca.student else "",
            subject_name=ca.subject.name if ca.subject else "",
            class_name=ca.class_.name if ca.class_ else "",
        )
        for ca in entries
    ]


@router.get(
    "/ca/summary",
    response_model=list[CASummaryResponse],
    summary="Get CA summary",
    dependencies=[Depends(require_permissions("exams.ca.read"))],
)
async def get_ca_summary(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: UUID = Query(...),
    subject_id: UUID = Query(...),
) -> list[CASummaryResponse]:
    """Get CA summary totals per student for a subject."""
    service = CAService(db)
    summaries = await service.get_ca_summary(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        subject_id=subject_id,
    )

    return [CASummaryResponse(**s) for s in summaries]


@router.put(
    "/ca/{ca_id}",
    response_model=CAResponse,
    summary="Update CA entry",
    dependencies=[Depends(require_permissions("exams.ca.enter"))],
)
async def update_ca(
    ca_id: UUID,
    data: CAUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> CAResponse:
    """Update a CA entry."""
    service = CAService(db)
    ca = await service.update_ca(
        ca_id=ca_id,
        tenant_id=tenant.tenant_id,
        **data.model_dump(exclude_unset=True),
    )

    if not ca:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CA entry not found",
        )

    return CAResponse(
        id=ca.id,
        tenant_id=ca.tenant_id,
        academic_year_id=ca.academic_year_id,
        term_id=ca.term_id,
        class_id=ca.class_id,
        subject_id=ca.subject_id,
        student_id=ca.student_id,
        assessment_type=ca.assessment_type.value,
        title=ca.title,
        max_score=ca.max_score,
        score=ca.score,
        assessment_date=ca.assessment_date,
        entered_by=ca.entered_by,
        created_at=ca.created_at,
        updated_at=ca.updated_at,
    )


@router.delete(
    "/ca/{ca_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete CA entry",
    dependencies=[Depends(require_permissions("exams.ca.delete"))],
)
async def delete_ca(
    ca_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Delete a CA entry."""
    service = CAService(db)
    deleted = await service.delete_ca(ca_id, tenant.tenant_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CA entry not found",
        )


# =========================
# Exam CRUD (dynamic routes)
# =========================


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
    exam = await service.get_exam(exam_id, include_subjects=include_subjects)

    if not exam or exam.tenant_id != tenant.tenant_id:
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
    exam_status: str = Query(..., alias="status"),
    tenant: RequestTenant = None,
    db: DatabaseSession = None,
) -> ExamResponse:
    """Update exam status."""
    service = ExamService(db)
    exam = await service.update_exam_status(
        exam_id=exam_id,
        tenant_id=tenant.tenant_id,
        status=exam_status,
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

    # Verify exam exists
    exam = await service.get_exam(exam_id)
    if not exam or exam.tenant_id != tenant.tenant_id:
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

    # Verify exam exists
    exam = await service.get_exam(exam_id)
    if not exam or exam.tenant_id != tenant.tenant_id:
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

    # Verify exam exists
    exam = await service.get_exam(exam_id)
    if not exam or exam.tenant_id != tenant.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    subjects = await service.list_exam_subjects(exam_id)

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


# =========================
# Score Entry Endpoints
# =========================


@router.get(
    "/{exam_id}/subjects/{exam_subject_id}/scores",
    response_model=ScoreEntryFormResponse,
    summary="Get score entry form",
    dependencies=[Depends(require_permissions("exams.scores.read"))],
)
async def get_score_entry_form(
    exam_id: UUID,
    exam_subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    section_id: Optional[UUID] = Query(None),
) -> ScoreEntryFormResponse:
    """Get score entry form with exam subject details and students."""
    service = ScoreService(db)
    form_data = await service.get_score_entry_form(exam_subject_id, section_id)

    if not form_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam subject not found",
        )

    return ScoreEntryFormResponse(**form_data)


@router.post(
    "/{exam_id}/subjects/{exam_subject_id}/scores",
    response_model=BulkScoreResult,
    summary="Bulk enter scores",
    dependencies=[Depends(require_permissions("exams.scores.enter"))],
)
async def bulk_enter_scores(
    exam_id: UUID,
    exam_subject_id: UUID,
    data: ExamScoreBulkCreate,
    request: Request,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> BulkScoreResult:
    """Bulk enter or update scores for students with audit trail."""
    service = ScoreService(db)

    # Get client IP for audit logging
    client_ip = request.client.host if request.client else None

    try:
        result = await service.bulk_enter_scores(
            tenant_id=tenant.tenant_id,
            exam_subject_id=exam_subject_id,
            scores=[s.model_dump() for s in data.scores],
            entered_by=user_id,
            grading_scale_id=data.grading_scale_id,
            ip_address=client_ip,
        )
        return BulkScoreResult(**result)
    except ExamServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{exam_id}/subjects/{exam_subject_id}/scores/audit-log",
    response_model=ScoreChangeLogListResponse,
    summary="Get score change audit log",
    dependencies=[Depends(require_permissions("exams.scores.read"))],
)
async def get_score_audit_log(
    exam_id: UUID,
    exam_subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    score_id: Optional[UUID] = Query(None, description="Filter by specific score ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ScoreChangeLogListResponse:
    """Get audit trail of score changes for an exam subject."""
    service = ScoreService(db)

    logs, total = await service.get_score_change_logs(
        tenant_id=tenant.tenant_id,
        exam_score_id=score_id,
        exam_subject_id=exam_subject_id,
        limit=limit,
        offset=offset,
    )

    return ScoreChangeLogListResponse(
        items=[ScoreChangeLogResponse(**log) for log in logs],
        total=total,
    )


@router.post(
    "/{exam_id}/subjects/{exam_subject_id}/submit",
    response_model=ExamSubjectResponse,
    summary="Submit scores",
    dependencies=[Depends(require_permissions("exams.scores.submit"))],
)
async def submit_scores(
    exam_id: UUID,
    exam_subject_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ExamSubjectResponse:
    """Submit scores (lock for editing)."""
    service = ScoreService(db)
    es = await service.submit_scores(exam_subject_id, tenant.tenant_id)

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


# =========================
# Term Report Endpoints
# =========================


@router.post(
    "/reports/term/generate",
    response_model=list[TermReportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate term reports",
    dependencies=[Depends(require_permissions("reports.generate"))],
)
async def generate_term_reports(
    data: TermReportGenerate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> list[TermReportResponse]:
    """Generate term reports for a class."""
    # Get academic year from term
    from app.services.academic import AcademicService
    academic_service = AcademicService(db)
    term = await academic_service.get_term(data.term_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = TermReportService(db)
    reports = await service.generate_term_reports(
        tenant_id=tenant.tenant_id,
        academic_year_id=term.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        section_id=data.section_id,
    )

    # Calculate rankings after generating reports
    await service.calculate_rankings(
        tenant_id=tenant.tenant_id,
        term_id=data.term_id,
        class_id=data.class_id,
    )

    # Refresh reports to get updated rankings
    refreshed_reports = []
    for r in reports:
        await db.refresh(r)
        refreshed_reports.append(r)

    return [
        TermReportResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            academic_year_id=r.academic_year_id,
            term_id=r.term_id,
            student_id=r.student_id,
            class_id=r.class_id,
            section_id=r.section_id,
            total_score=r.total_score,
            average_score=r.average_score,
            subjects_count=r.subjects_count,
            class_position=r.class_position,
            section_position=r.section_position,
            class_size=r.class_size,
            section_size=r.section_size,
            attendance_percentage=r.attendance_percentage,
            days_present=r.days_present,
            days_absent=r.days_absent,
            total_school_days=r.total_school_days,
            conduct_grade=r.conduct_grade,
            interest=r.interest,
            class_teacher_remark=r.class_teacher_remark,
            headmaster_remark=r.headmaster_remark,
            is_published=r.is_published,
            published_at=r.published_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in refreshed_reports
    ]


@router.get(
    "/reports/term",
    response_model=TermReportListResponse,
    summary="List term reports",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def list_term_reports(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: Optional[UUID] = Query(None),
    class_id: Optional[UUID] = Query(None),
    section_id: Optional[UUID] = Query(None),
    is_published: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> TermReportListResponse:
    """List term reports with filters."""
    service = TermReportService(db)
    reports, total = await service.list_term_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        is_published=is_published,
        page=page,
        page_size=page_size,
    )

    items = []
    for r in reports:
        items.append(TermReportWithDetailsResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            academic_year_id=r.academic_year_id,
            term_id=r.term_id,
            student_id=r.student_id,
            class_id=r.class_id,
            section_id=r.section_id,
            total_score=r.total_score,
            average_score=r.average_score,
            subjects_count=r.subjects_count,
            class_position=r.class_position,
            section_position=r.section_position,
            class_size=r.class_size,
            section_size=r.section_size,
            attendance_percentage=r.attendance_percentage,
            days_present=r.days_present,
            days_absent=r.days_absent,
            total_school_days=r.total_school_days,
            conduct_grade=r.conduct_grade,
            interest=r.interest,
            class_teacher_remark=r.class_teacher_remark,
            headmaster_remark=r.headmaster_remark,
            is_published=r.is_published,
            published_at=r.published_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
            student_name=f"{r.student.first_name} {r.student.last_name}" if r.student else "",
            student_id_number=r.student.student_id if r.student else "",
            class_name=r.class_.name if r.class_ else "",
            section_name=r.section.name if r.section else None,
            term_name=r.term.name if r.term else "",
            academic_year_name=r.academic_year.name if hasattr(r, "academic_year") and r.academic_year else "",
        ))

    return TermReportListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/reports/term/{report_id}",
    response_model=TermReportWithDetailsResponse,
    summary="Get term report",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def get_term_report(
    report_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TermReportWithDetailsResponse:
    """Get term report by ID."""
    service = TermReportService(db)
    report = await service.get_term_report(report_id)

    if not report or report.tenant_id != tenant.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Get subject results for this student's term report
    subject_results = await service.get_student_subject_results(
        tenant_id=tenant.tenant_id,
        term_id=report.term_id,
        student_id=report.student_id,
        class_id=report.class_id,
        academic_year_id=report.academic_year_id,
        section_id=report.section_id,
    )

    return TermReportWithDetailsResponse(
        id=report.id,
        tenant_id=report.tenant_id,
        academic_year_id=report.academic_year_id,
        term_id=report.term_id,
        student_id=report.student_id,
        class_id=report.class_id,
        section_id=report.section_id,
        total_score=report.total_score,
        average_score=report.average_score,
        subjects_count=report.subjects_count,
        class_position=report.class_position,
        section_position=report.section_position,
        class_size=report.class_size,
        section_size=report.section_size,
        attendance_percentage=report.attendance_percentage,
        days_present=report.days_present,
        days_absent=report.days_absent,
        total_school_days=report.total_school_days,
        conduct_grade=report.conduct_grade,
        interest=report.interest,
        class_teacher_remark=report.class_teacher_remark,
        headmaster_remark=report.headmaster_remark,
        is_published=report.is_published,
        published_at=report.published_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        student_name=f"{report.student.first_name} {report.student.last_name}" if report.student else "",
        student_id_number=report.student.student_id if report.student else "",
        class_name=report.class_.name if report.class_ else "",
        section_name=report.section.name if report.section else None,
        term_name=report.term.name if report.term else "",
        academic_year_name=report.academic_year.name if report.academic_year else "",
        subject_results=[
            SubjectResult(
                subject_id=s["subject_id"],
                subject_name=s["subject_name"],
                subject_code=s.get("subject_code"),
                # Raw scores
                ca_score=s.get("ca_score"),
                ca_max=s.get("ca_max"),
                end_term_score=s.get("end_term_score"),
                end_term_max=s.get("end_term_max"),
                # Normalized scores (Ghana 50/50 system)
                class_score=s.get("class_score"),
                exams_score=s.get("exams_score"),
                total_score=s.get("total_score"),
                grade=s.get("grade"),
                grade_remark=s.get("grade_remark"),
                subject_position=s.get("subject_position"),
            )
            for s in subject_results
        ],
    )


@router.get(
    "/reports/term/{report_id}/pdf",
    summary="Download term report PDF",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def download_term_report_pdf(
    report_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
):
    """Download term report as PDF."""
    from fastapi.responses import Response
    from app.services.pdf import PDFService

    try:
        pdf_bytes, filename = await PDFService.generate_term_report_pdf(
            db=db,
            tenant_id=tenant.tenant_id,
            report_id=report_id,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}",
        )


@router.get(
    "/reports/term/batch-pdf",
    summary="Download multiple term reports as ZIP",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def download_batch_term_reports_pdf(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: Optional[UUID] = Query(None),
    section_id: Optional[UUID] = Query(None),
):
    """Download multiple term reports as a ZIP file containing individual PDFs."""
    from fastapi.responses import Response
    from app.services.pdf import PDFService
    import zipfile
    from io import BytesIO

    service = TermReportService(db)
    reports, total = await service.list_term_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        page=1,
        page_size=500,  # Limit for safety
    )

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found for the specified criteria",
        )

    # Create ZIP file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for report in reports:
            try:
                pdf_bytes, filename = await PDFService.generate_term_report_pdf(
                    db=db,
                    tenant_id=tenant.tenant_id,
                    report_id=report.id,
                )
                zip_file.writestr(filename, pdf_bytes)
            except Exception as e:
                # Skip failed PDFs but continue with others
                continue

    zip_buffer.seek(0)
    zip_content = zip_buffer.getvalue()

    # Create filename
    term_name = reports[0].term.name if reports and reports[0].term else "Term"
    class_name = reports[0].class_.name if reports and reports[0].class_ else "Class"
    zip_filename = f"Report_Cards_{class_name}_{term_name}.zip"
    zip_filename = zip_filename.replace(" ", "_")

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )


@router.put(
    "/reports/term/{report_id}/remarks",
    response_model=TermReportResponse,
    summary="Update report remarks",
    dependencies=[Depends(require_permissions("reports.remarks.update"))],
)
async def update_report_remarks(
    report_id: UUID,
    data: TermReportRemarksUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TermReportResponse:
    """Update term report remarks."""
    service = TermReportService(db)
    report = await service.update_remarks(
        report_id=report_id,
        tenant_id=tenant.tenant_id,
        conduct_grade=data.conduct_grade,
        interest=data.interest,
        class_teacher_remark=data.class_teacher_remark,
        headmaster_remark=data.headmaster_remark,
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return TermReportResponse(
        id=report.id,
        tenant_id=report.tenant_id,
        academic_year_id=report.academic_year_id,
        term_id=report.term_id,
        student_id=report.student_id,
        class_id=report.class_id,
        section_id=report.section_id,
        total_score=report.total_score,
        average_score=report.average_score,
        subjects_count=report.subjects_count,
        class_position=report.class_position,
        section_position=report.section_position,
        class_size=report.class_size,
        section_size=report.section_size,
        attendance_percentage=report.attendance_percentage,
        days_present=report.days_present,
        days_absent=report.days_absent,
        total_school_days=report.total_school_days,
        conduct_grade=report.conduct_grade,
        interest=report.interest,
        class_teacher_remark=report.class_teacher_remark,
        headmaster_remark=report.headmaster_remark,
        is_published=report.is_published,
        published_at=report.published_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post(
    "/reports/term/publish",
    summary="Publish term reports",
    dependencies=[Depends(require_permissions("reports.publish"))],
)
async def publish_term_reports(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: Optional[UUID] = Query(None),
) -> dict:
    """Publish term reports (make visible to parents)."""
    service = TermReportService(db)
    count = await service.publish_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
    )

    return {"published": count, "message": f"Published {count} reports"}


# =========================
# Results / Rankings Endpoints
# =========================


@router.get(
    "/{exam_id}/results/class/{class_id}",
    response_model=ClassResultsResponse,
    summary="Get class results",
    dependencies=[Depends(require_permissions("exams.results.read"))],
)
async def get_class_results(
    exam_id: UUID,
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    section_id: Optional[UUID] = Query(None),
) -> ClassResultsResponse:
    """Get exam results for a class with rankings."""
    service = ScoreService(db)
    try:
        results = await service.get_class_results(
            exam_id=exam_id,
            class_id=class_id,
            tenant_id=tenant.tenant_id,
            section_id=section_id,
        )

        # Convert to response model
        students = [
            StudentExamResult(
                student_id=s["student_id"],
                student_name=s["student_name"],
                student_id_number=s["student_id_number"],
                class_name=s["class_name"],
                section_name=s.get("section_name"),
                subjects=[SubjectResult(**sub) for sub in s["subjects"]],
                total_score=s["total_score"],
                average_score=s["average_score"],
                subjects_count=s["subjects_count"],
                class_position=s["class_position"],
                section_position=s.get("section_position"),
                class_size=s["class_size"],
                section_size=s.get("section_size"),
            )
            for s in results["students"]
        ]

        return ClassResultsResponse(
            exam_id=results["exam_id"],
            exam_name=results["exam_name"],
            class_id=results["class_id"],
            class_name=results["class_name"],
            term_name=results["term_name"],
            students=students,
            class_average=results["class_average"],
            highest_score=results["highest_score"],
            lowest_score=results["lowest_score"],
        )
    except ExamServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{exam_id}/results/class/{class_id}/export",
    summary="Export class results to CSV",
    dependencies=[Depends(require_permissions("exams.results.read"))],
)
async def export_class_results_csv(
    exam_id: UUID,
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    section_id: Optional[UUID] = Query(None),
):
    """Export exam results for a class as CSV."""
    import csv
    from io import StringIO
    from fastapi.responses import Response

    service = ScoreService(db)
    try:
        results = await service.get_class_results(
            exam_id=exam_id,
            class_id=class_id,
            tenant_id=tenant.tenant_id,
            section_id=section_id,
        )

        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        # Get all unique subjects from results
        all_subjects = set()
        for student in results["students"]:
            for subject in student["subjects"]:
                all_subjects.add(subject["subject_name"])
        subject_list = sorted(all_subjects)

        # Write header row
        headers = ["Rank", "Student ID", "Student Name", "Class", "Section"]
        for subject in subject_list:
            headers.extend([f"{subject} (Score)", f"{subject} (Grade)"])
        headers.extend(["Total Score", "Average", "Subjects Count"])
        writer.writerow(headers)

        # Write data rows
        for student in results["students"]:
            row = [
                student["class_position"],
                student["student_id_number"],
                student["student_name"],
                student["class_name"],
                student.get("section_name", ""),
            ]

            # Create subject lookup
            subject_scores = {s["subject_name"]: s for s in student["subjects"]}

            for subject_name in subject_list:
                if subject_name in subject_scores:
                    s = subject_scores[subject_name]
                    row.extend([
                        s.get("total_score", ""),
                        s.get("grade", ""),
                    ])
                else:
                    row.extend(["", ""])

            row.extend([
                student["total_score"],
                student["average_score"],
                student["subjects_count"],
            ])
            writer.writerow(row)

        # Create response
        csv_content = output.getvalue()
        filename = f"{results['exam_name']}_{results['class_name']}_Results.csv"
        filename = filename.replace(" ", "_")

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ExamServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/reports/term/export",
    summary="Export term reports to CSV",
    dependencies=[Depends(require_permissions("reports.read"))],
)
async def export_term_reports_csv(
    tenant: RequestTenant,
    db: DatabaseSession,
    term_id: UUID = Query(...),
    class_id: Optional[UUID] = Query(None),
    section_id: Optional[UUID] = Query(None),
):
    """Export term reports for a class as CSV."""
    import csv
    from io import StringIO
    from fastapi.responses import Response

    service = TermReportService(db)
    reports, total = await service.list_term_reports(
        tenant_id=tenant.tenant_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
        page=1,
        page_size=1000,  # Get all
    )

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reports found for the specified criteria",
        )

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Write header row
    headers = [
        "Rank", "Student ID", "Student Name", "Class", "Section",
        "Total Score", "Average (%)", "Subjects",
        "Days Present", "Days Absent", "Attendance (%)",
        "Conduct", "Class Teacher Remark", "Published"
    ]
    writer.writerow(headers)

    # Write data rows
    for report in reports:
        row = [
            report.class_position or "",
            report.student.student_id if report.student else "",
            f"{report.student.first_name} {report.student.last_name}" if report.student else "",
            report.class_.name if report.class_ else "",
            report.section.name if report.section else "",
            report.total_score or "",
            report.average_score or "",
            report.subjects_count or "",
            report.days_present or 0,
            report.days_absent or 0,
            report.attendance_percentage or "",
            report.conduct_grade or "",
            report.class_teacher_remark or "",
            "Yes" if report.is_published else "No",
        ]
        writer.writerow(row)

    # Create response
    csv_content = output.getvalue()
    term_name = reports[0].term.name if reports and reports[0].term else "Term"
    class_name = reports[0].class_.name if reports and reports[0].class_ else "Class"
    filename = f"Report_Cards_{class_name}_{term_name}.csv"
    filename = filename.replace(" ", "_")

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/{exam_id}/publish",
    summary="Publish exam results",
    dependencies=[Depends(require_permissions("exams.results.publish"))],
)
async def publish_exam_results(
    exam_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> dict:
    """Publish all results for an exam."""
    service = ScoreService(db)
    count = await service.publish_exam_results(
        exam_id=exam_id,
        tenant_id=tenant.tenant_id,
    )

    return {"published_subjects": count, "message": f"Published results for {count} subjects"}


@router.put(
    "/scores/{score_id}",
    response_model=ExamScoreResponse,
    summary="Update a single score",
    dependencies=[Depends(require_permissions("exams.scores.enter"))],
)
async def update_score(
    score_id: UUID,
    data: ExamScoreUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ExamScoreResponse:
    """Update a single exam score."""
    service = ScoreService(db)
    score = await service.update_score(
        score_id=score_id,
        tenant_id=tenant.tenant_id,
        score=data.score,
        is_absent=data.is_absent,
        teacher_remark=data.teacher_remark,
    )

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Score not found",
        )

    return ExamScoreResponse(
        id=score.id,
        tenant_id=score.tenant_id,
        exam_subject_id=score.exam_subject_id,
        student_id=score.student_id,
        score=score.score,
        grade=score.grade,
        grade_point=score.grade_point,
        grade_remark=score.grade_remark,
        is_absent=score.is_absent,
        teacher_remark=score.teacher_remark,
        entered_by=score.entered_by,
        entered_at=score.entered_at,
        updated_at=score.updated_at,
    )


@router.get(
    "/{exam_id}/results/student/{student_id}",
    response_model=ClassResultsResponse,
    summary="Get student exam results",
    dependencies=[Depends(require_permissions("exams.results.read"))],
)
async def get_student_results(
    exam_id: UUID,
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ClassResultsResponse:
    """Get exam results for a single student."""
    service = ScoreService(db)
    try:
        results = await service.get_student_results(
            exam_id=exam_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )

        # Convert to response model
        students = [
            StudentExamResult(
                student_id=s["student_id"],
                student_name=s["student_name"],
                student_id_number=s["student_id_number"],
                class_name=s["class_name"],
                section_name=s.get("section_name"),
                subjects=[SubjectResult(**sub) for sub in s["subjects"]],
                total_score=s["total_score"],
                average_score=s["average_score"],
                subjects_count=s["subjects_count"],
                class_position=s["class_position"],
                section_position=s.get("section_position"),
                class_size=s["class_size"],
                section_size=s.get("section_size"),
            )
            for s in results["students"]
        ]

        return ClassResultsResponse(
            exam_id=results["exam_id"],
            exam_name=results["exam_name"],
            class_id=results["class_id"],
            class_name=results["class_name"],
            term_name=results["term_name"],
            students=students,
            class_average=results["class_average"],
            highest_score=results["highest_score"],
            lowest_score=results["lowest_score"],
        )
    except ExamServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =========================
# Analytics Endpoints
# =========================


@router.get(
    "/{exam_id}/analytics/grade-distribution",
    response_model=GradeDistributionResponse,
    summary="Get grade distribution",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_grade_distribution(
    exam_id: UUID,
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    subject_id: Optional[UUID] = Query(None, description="Filter by subject"),
) -> GradeDistributionResponse:
    """Get grade distribution for a class, optionally filtered by subject."""
    service = AnalyticsService(db)
    result = await service.get_grade_distribution(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
        class_id=class_id,
        subject_id=subject_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam or class not found",
        )

    return GradeDistributionResponse(**result)


@router.get(
    "/{exam_id}/analytics/class-statistics",
    response_model=ClassStatisticsResponse,
    summary="Get class statistics",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_class_statistics(
    exam_id: UUID,
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
) -> ClassStatisticsResponse:
    """Get overall class statistics including pass/fail rates and grade distribution."""
    service = AnalyticsService(db)
    result = await service.get_class_statistics(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
        class_id=class_id,
        section_id=section_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam or class not found",
        )

    return ClassStatisticsResponse(**result)


@router.get(
    "/{exam_id}/analytics/subject-statistics",
    response_model=list[SubjectStatisticsResponse],
    summary="Get subject statistics",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_subject_statistics(
    exam_id: UUID,
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
) -> list[SubjectStatisticsResponse]:
    """Get statistics for each subject in the exam."""
    service = AnalyticsService(db)
    result = await service.get_subject_statistics(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
        class_id=class_id,
        section_id=section_id,
    )

    return [SubjectStatisticsResponse(**s) for s in result]


@router.get(
    "/{exam_id}/analytics/subject-rankings/{subject_id}",
    response_model=SubjectRankingsResponse,
    summary="Get subject rankings",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_subject_rankings(
    exam_id: UUID,
    subject_id: UUID,
    class_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    section_id: Optional[UUID] = Query(None, description="Filter by section"),
) -> SubjectRankingsResponse:
    """Get student rankings for a specific subject."""
    service = AnalyticsService(db)
    result = await service.get_subject_rankings(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
        subject_id=subject_id,
        class_id=class_id,
        section_id=section_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam subject not found",
        )

    return SubjectRankingsResponse(**result)


# =========================
# Timetabling Endpoints
# =========================


@router.get(
    "/{exam_id}/timetable",
    response_model=ExamTimetableResponse,
    summary="Get exam timetable",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_exam_timetable(
    exam_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> ExamTimetableResponse:
    """Get full exam timetable with all scheduled subjects."""
    service = AnalyticsService(db)
    result = await service.get_exam_timetable(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    return ExamTimetableResponse(**result)


@router.get(
    "/{exam_id}/timetable/conflicts",
    response_model=TimetableConflictsResponse,
    summary="Check timetable conflicts",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def check_timetable_conflicts(
    exam_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> TimetableConflictsResponse:
    """Check for scheduling conflicts in exam timetable."""
    service = AnalyticsService(db)
    result = await service.check_timetable_conflicts(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
    )

    return TimetableConflictsResponse(**result)


@router.put(
    "/{exam_id}/timetable/bulk",
    response_model=BulkTimetableUpdateResult,
    summary="Bulk update timetable",
    dependencies=[Depends(require_permissions("exams.update"))],
)
async def bulk_update_timetable(
    exam_id: UUID,
    data: BulkTimetableUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> BulkTimetableUpdateResult:
    """Bulk update exam timetable entries."""
    service = AnalyticsService(db)
    result = await service.bulk_update_timetable(
        tenant_id=tenant.tenant_id,
        exam_id=exam_id,
        entries=[e.model_dump() for e in data.entries],
    )

    return BulkTimetableUpdateResult(**result)

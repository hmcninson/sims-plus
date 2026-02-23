"""
SIMS Plus - Teacher Portal Grading Endpoints

Pending score entry, bulk score submission, and grade summaries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import (
    BulkScoreEntryRequest,
    BulkScoreEntryResponse,
    ClassGradeSummary,
    PendingScoreEntry,
    ScoreEntryResult,
)
from sqlalchemy import and_, select

from app.models.exam import ExamSubject
from app.services.teacher import (
    TeacherContextService,
    TeacherGradingService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/grading/pending",
    response_model=list[PendingScoreEntry],
    summary="Get pending score entries",
    dependencies=[Depends(require_permissions("teacher.grading.read"))],
)
async def get_pending_scores(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[PendingScoreEntry]:
    """
    Get all exam subjects where the teacher has pending score entry.

    Returns exam subjects that are in pending/scores_entered status
    for classes this teacher is assigned to.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)
        term = await context.get_current_term(tenant.tenant_id, academic_year.id)

        grading_service = TeacherGradingService(db)
        pending = await grading_service.get_pending_scores(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year.id,
            term_id=term.id,
        )
        return [PendingScoreEntry(**p) for p in pending]

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.post(
    "/grading/exam-subjects/{exam_subject_id}/scores",
    response_model=BulkScoreEntryResponse,
    summary="Enter scores for an exam subject",
    dependencies=[Depends(require_permissions("teacher.grading.write"))],
)
async def enter_scores(
    exam_subject_id: UUID,
    body: BulkScoreEntryRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkScoreEntryResponse:
    """
    Bulk enter or update scores for an exam subject.

    Each item in the scores array should specify:
    - student_id: UUID of the student
    - score: numeric score (nullable if absent)
    - is_absent: whether the student was absent
    - teacher_remark: optional per-subject remark

    Scores are auto-graded using the exam subject's grading scale.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Authorization: load exam subject to verify teacher is assigned
        # to the class+subject combination before allowing score entry
        es_result = await db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    ExamSubject.tenant_id == tenant.tenant_id,
                )
            )
        )
        exam_subject = es_result.scalar_one_or_none()
        if not exam_subject:
            raise TeacherServiceError("Exam subject not found", code="not_found")

        await context.verify_class_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=exam_subject.class_id,
        )
        await context.verify_subject_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            subject_id=exam_subject.subject_id,
            class_id=exam_subject.class_id,
        )

        grading_service = TeacherGradingService(db)
        result = await grading_service.enter_scores(
            staff_id=staff.id,
            user_id=user_id,
            tenant_id=tenant.tenant_id,
            exam_subject_id=exam_subject_id,
            scores=[s.model_dump() for s in body.scores],
        )
        return BulkScoreEntryResponse(
            total=result["total"],
            successful=result["successful"],
            failed=result["failed"],
            results=[ScoreEntryResult(**r) for r in result["results"]],
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.get(
    "/grading/classes/{class_id}/subjects/{subject_id}/summary",
    response_model=ClassGradeSummary,
    summary="Get grade summary for a class-subject",
    dependencies=[Depends(require_permissions("teacher.grading.read"))],
)
async def get_class_grade_summary(
    class_id: UUID,
    subject_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current term)"),
) -> ClassGradeSummary:
    """
    Get a grade summary for all students in a class for a specific subject.

    Combines exam scores and CA averages into a unified view with
    class average, highest/lowest scores, and per-student details.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify access to this class and subject
        await context.verify_class_access(
            staff_id=staff.id, tenant_id=tenant.tenant_id, class_id=class_id,
        )
        await context.verify_subject_access(
            staff_id=staff.id, tenant_id=tenant.tenant_id,
            subject_id=subject_id, class_id=class_id,
        )

        # Resolve term
        if not term_id:
            academic_year = await context.get_current_academic_year(tenant.tenant_id)
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id

        grading_service = TeacherGradingService(db)
        summary = await grading_service.get_class_grade_summary(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            subject_id=subject_id,
            term_id=term_id,
        )
        return ClassGradeSummary(**summary)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)

"""
SIMS Plus - Score Entry and Results Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.exam import (
    ExamScoreBulkCreate,
    ExamScoreUpdate,
    ExamScoreResponse,
    ScoreEntryFormResponse,
    BulkScoreResult,
    ScoreChangeLogResponse,
    ScoreChangeLogListResponse,
    ExamSubjectResponse,
    SubjectResult,
    StudentExamResult,
    ClassResultsResponse,
)
from app.services.exam import ScoreService, ExamServiceError

router = APIRouter()


# =========================
# Score Entry Endpoints
# =========================


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
    form_data = await service.get_score_entry_form(tenant.tenant_id, exam_subject_id, section_id)

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

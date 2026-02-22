"""
SIMS Plus - Parent Portal Grades Endpoints

Endpoints for parents to view their children's academic performance:
term grades, grade trends, continuous assessments, and report card downloads.
Only published results are visible to parents.
"""

from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    AssessmentScore,
    GradeTrend,
    TermGrades,
)
from app.services.parent import (
    ParentAcademicService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/children/{student_id}/grades",
    response_model=TermGrades,
    summary="Get child term grades",
    dependencies=[Depends(require_permissions("parent.grades.read"))],
)
async def get_child_grades(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID = Query(..., description="Term to fetch grades for"),
) -> TermGrades:
    """
    Get term grades for a child: per-subject scores, totals, and positions.

    Only returns scores from published exams and assessments.
    Verifies parent-child access before returning data.
    """
    user_id = _get_user_id(user)
    service = ParentAcademicService(db)

    try:
        result = await service.get_child_grades(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
            term_id=term_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return TermGrades(**result)


@router.get(
    "/children/{student_id}/grades/trend",
    response_model=list[GradeTrend],
    summary="Get child grade trend",
    dependencies=[Depends(require_permissions("parent.grades.read"))],
)
async def get_child_grade_trend(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[GradeTrend]:
    """
    Get grade trend across available terms for charting.

    Returns average score and position from published term reports,
    ordered chronologically. Used for parent dashboard charts.
    """
    user_id = _get_user_id(user)
    service = ParentAcademicService(db)

    try:
        results = await service.get_child_grade_trend(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return [GradeTrend(**item) for item in results]


@router.get(
    "/children/{student_id}/assessments",
    response_model=list[AssessmentScore],
    summary="Get child assessments",
    dependencies=[Depends(require_permissions("parent.grades.read"))],
)
async def get_child_assessments(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID = Query(..., description="Term to fetch assessments for"),
) -> list[AssessmentScore]:
    """
    Get continuous assessment scores for a child in a specific term.

    Returns individual CA entries (class work, homework, tests, projects)
    across all subjects for the given term.
    """
    user_id = _get_user_id(user)
    service = ParentAcademicService(db)

    try:
        results = await service.get_child_assessments(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
            term_id=term_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return [AssessmentScore(**item) for item in results]


@router.get(
    "/children/{student_id}/report-card/{term_id}/download",
    summary="Download report card PDF",
    dependencies=[Depends(require_permissions("parent.grades.read"))],
)
async def download_report_card(
    student_id: UUID,
    term_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> StreamingResponse:
    """
    Download term report card as PDF.

    Only published term reports can be downloaded by parents.
    Returns the PDF as a streaming response with appropriate content
    disposition for browser download.
    """
    user_id = _get_user_id(user)
    service = ParentAcademicService(db)

    try:
        pdf_bytes, filename = await service.get_child_report_card_pdf(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
            term_id=term_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

"""
SIMS Plus - Exam Analytics and Timetabling Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.exam import (
    GradeDistributionResponse,
    ClassStatisticsResponse,
    SubjectStatisticsResponse,
    SubjectRankingsResponse,
    ExamTimetableResponse,
    TimetableConflictsResponse,
    BulkTimetableUpdate,
    BulkTimetableUpdateResult,
)
from app.services.exam import AnalyticsService

router = APIRouter()


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

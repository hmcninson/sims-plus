"""
SIMS Plus - Admissions Analytics Endpoints

Enrollment funnel, trends, lead source effectiveness, re-enrollment rates,
attrition analysis, and enrollment-vs-capacity comparisons.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.enrollment_analytics import (
    AttritionResponse,
    EnrollmentVsCapacityResponse,
    FunnelResponse,
    ReEnrollmentResponse,
    SourceEffectivenessResponse,
    TrendsResponse,
)
from app.services.admissions import AdmissionsAnalyticsService, AnalyticsServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics")


def _handle_error(e: AnalyticsServiceError) -> HTTPException:
    status_map = {
        "YEAR_NOT_FOUND": 404,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.get(
    "/funnel",
    response_model=FunnelResponse,
    summary="Admissions funnel",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_funnel(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    period_id: UUID | None = Query(
        None, description="Filter by admission period"
    ),
) -> FunnelResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_full_funnel(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        period_id=period_id,
    )


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Year-over-year enrollment trends",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_trends(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    year_count: int = Query(
        3, ge=1, le=10, description="Number of years to show"
    ),
) -> TrendsResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_enrollment_trends(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        year_count=year_count,
    )


@router.get(
    "/lead-sources",
    response_model=SourceEffectivenessResponse,
    summary="Lead source effectiveness",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_lead_sources(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    period_id: UUID | None = Query(None),
) -> SourceEffectivenessResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_lead_source_effectiveness(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        period_id=period_id,
    )


@router.get(
    "/re-enrollment",
    response_model=ReEnrollmentResponse,
    summary="Re-enrollment rates",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_re_enrollment(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    year_count: int = Query(3, ge=1, le=10),
) -> ReEnrollmentResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_re_enrollment_rates(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        year_count=year_count,
    )


@router.get(
    "/attrition",
    response_model=AttritionResponse,
    summary="Attrition analysis",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_attrition(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID | None = Query(None),
) -> AttritionResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_attrition_analysis(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        academic_year_id=academic_year_id,
    )


@router.get(
    "/capacity",
    response_model=EnrollmentVsCapacityResponse,
    summary="Enrollment vs capacity",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_enrollment_vs_capacity(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(
        ..., description="Academic year for comparison"
    ),
) -> EnrollmentVsCapacityResponse:
    try:
        svc = AdmissionsAnalyticsService(db)
        return await svc.get_enrollment_vs_capacity(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=academic_year_id,
        )
    except AnalyticsServiceError as e:
        raise _handle_error(e)

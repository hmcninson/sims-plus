"""
SIMS Plus - Admissions Dashboard Endpoints

Admin endpoints for admissions pipeline statistics and demographics.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import DashboardStatsResponse, DemographicsResponse
from app.services.admissions import ApplicationService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard")


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get admissions pipeline statistics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_stats(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    admission_period_id: UUID | None = Query(None),
) -> DashboardStatsResponse:
    """
    Get admissions pipeline statistics:
    - Total applications count
    - Breakdown by status (pipeline)
    - Breakdown by target class
    - Breakdown by admission period
    - Conversion rate (enrolled / total)
    - Pending decisions count
    - Pending enrollment count (accepted but not enrolled)
    - Recent applications (last 10)
    """
    service = ApplicationService(db)
    result = await service.get_dashboard_stats(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        admission_period_id=admission_period_id,
    )
    return DashboardStatsResponse(**result)


@router.get(
    "/demographics",
    response_model=DemographicsResponse,
    summary="Get applicant demographics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_demographics(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    admission_period_id: UUID | None = Query(None),
) -> DemographicsResponse:
    """
    Get applicant demographic breakdown:
    - Gender distribution
    - Nationality breakdown
    - Previous school distribution
    - Age distribution
    """
    service = ApplicationService(db)
    result = await service.get_demographics(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        admission_period_id=admission_period_id,
    )
    return DemographicsResponse(**result)

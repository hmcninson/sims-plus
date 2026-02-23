"""
SIMS Plus - Dashboard Endpoints

API endpoints for dashboard analytics.

All dashboard data is school-specific, so every endpoint resolves a
SchoolCtx to scope queries and cache keys correctly.  For chain tenants
this requires the X-Active-School header; for single-school tenants the
lone school is auto-resolved.

NOTE: Dashboard endpoints (get_dashboard_stats, get_attendance_trend,
get_gender_distribution) do not use require_permissions() because dashboard
overview data should be accessible to any authenticated user within their
tenant.  Authentication is enforced via ValidatedUser; authorization is
tenant-scoped via RLS.  The fee-trend and class-performance endpoints DO
require specific permissions (finance.read and exams.read respectively)
because they expose sensitive financial and academic data.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.dashboard import (
    DashboardStats,
    AttendanceTodayStats,
    FinanceSummaryStats,
    AttendanceTrendPoint,
    FeeCollectionTrendPoint,
    ClassPerformancePoint,
    GenderDistribution,
)
from app.services.dashboard import DashboardService
from app.services.cache import CacheService
from app.utils.cache_keys import CacheKeys

router = APIRouter()


@router.get(
    "",
    response_model=DashboardStats,
    summary="Dashboard overview stats",
)
async def get_dashboard_stats(
    request: Request,
    tenant: RequestTenant,
    db: DatabaseSession,
    user: ValidatedUser,
    school: SchoolCtx,
) -> DashboardStats:
    """Get overview statistics (cached 60s), scoped to the active school."""
    redis = getattr(request.app.state, "redis", None)
    cache = CacheService(redis)

    # School-scoped cache key prevents stale data when chain admins switch schools
    school_id_str = str(school.school_id)

    async def fetch_stats():
        service = DashboardService(db)
        return await service.get_overview_stats(
            tenant.tenant_id, school_id=school.school_id
        )

    data = await cache.get_or_set(
        CacheKeys.dashboard_stats(str(tenant.tenant_id), school_id_str),
        CacheKeys.DASHBOARD_STATS_TTL,
        fetch_stats,
    )

    return DashboardStats(
        total_students=data["total_students"],
        total_staff=data["total_staff"],
        total_classes=data["total_classes"],
        attendance_today=AttendanceTodayStats(**data["attendance_today"]),
        finance=FinanceSummaryStats(**data["finance"]),
    )


@router.get(
    "/attendance-trend",
    response_model=list[AttendanceTrendPoint],
    summary="Attendance trend",
)
async def get_attendance_trend(
    tenant: RequestTenant,
    db: DatabaseSession,
    user: ValidatedUser,
    school: SchoolCtx,
    days: int = Query(30, ge=1, le=365),
) -> list[AttendanceTrendPoint]:
    """Get daily attendance trend for last N days, scoped to the active school."""
    service = DashboardService(db)
    data = await service.get_attendance_trend(
        tenant.tenant_id, days=days, school_id=school.school_id
    )
    return [AttendanceTrendPoint(**point) for point in data]


@router.get(
    "/fee-trend",
    response_model=list[FeeCollectionTrendPoint],
    summary="Fee collection trend",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_fee_collection_trend(
    tenant: RequestTenant,
    db: DatabaseSession,
    school: SchoolCtx,
    months: int = Query(6, ge=1, le=24),
) -> list[FeeCollectionTrendPoint]:
    """Get monthly fee collection trend, scoped to the active school."""
    service = DashboardService(db)
    data = await service.get_fee_collection_trend(
        tenant.tenant_id, months=months, school_id=school.school_id
    )
    return [FeeCollectionTrendPoint(**point) for point in data]


@router.get(
    "/class-performance",
    response_model=list[ClassPerformancePoint],
    summary="Class performance",
    dependencies=[Depends(require_permissions("exams.read"))],
)
async def get_class_performance(
    tenant: RequestTenant,
    db: DatabaseSession,
    school: SchoolCtx,
    term_id: UUID = Query(..., description="Term ID"),
) -> list[ClassPerformancePoint]:
    """Get average exam scores per class for a term, scoped to the active school."""
    service = DashboardService(db)
    data = await service.get_class_performance(
        tenant.tenant_id, term_id, school_id=school.school_id
    )
    return [ClassPerformancePoint(**point) for point in data]


@router.get(
    "/gender-distribution",
    response_model=GenderDistribution,
    summary="Gender distribution",
)
async def get_gender_distribution(
    tenant: RequestTenant,
    db: DatabaseSession,
    user: ValidatedUser,
    school: SchoolCtx,
) -> GenderDistribution:
    """Get student gender distribution, scoped to the active school."""
    service = DashboardService(db)
    data = await service.get_gender_distribution(
        tenant.tenant_id, school_id=school.school_id
    )
    return GenderDistribution(**data)

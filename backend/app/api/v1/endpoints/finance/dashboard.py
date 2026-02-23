"""
SIMS Plus - Finance Dashboard Endpoints

Dashboard and statistics endpoints for the finance module.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    require_permissions,
)
from app.schemas.finance import (
    FinanceDashboardResponse,
    FinanceDashboardStats,
    OutstandingByClass,
    RecentPayment,
)
from app.services.finance import FinanceDashboardService

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=FinanceDashboardResponse,
    summary="Get finance dashboard",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_finance_dashboard(
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
) -> FinanceDashboardResponse:
    """Get finance dashboard with stats and recent activity."""
    service = FinanceDashboardService(db)

    stats = await service.get_dashboard_stats(
        tenant_id=school_ctx.tenant_id,
        school_id=school_ctx.school_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )

    recent_payments = await service.get_recent_payments(
        tenant_id=school_ctx.tenant_id,
        school_id=school_ctx.school_id,
        limit=5,
    )

    outstanding = await service.get_outstanding_by_class(
        tenant_id=school_ctx.tenant_id,
        school_id=school_ctx.school_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )

    return FinanceDashboardResponse(
        stats=FinanceDashboardStats(**stats),
        recent_payments=[
            RecentPayment(
                id=p.id,
                receipt_number=p.receipt_number,
                student_name=f"{p.student.first_name} {p.student.last_name}" if p.student else "Unknown",
                amount=p.amount,
                payment_method=p.payment_method.value,
                payment_date=p.payment_date,
            )
            for p in recent_payments
        ],
        outstanding_by_class=[
            OutstandingByClass(**item) for item in outstanding
        ],
    )

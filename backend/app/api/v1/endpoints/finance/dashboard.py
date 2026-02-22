"""
SIMS Plus - Finance Dashboard Endpoints

Dashboard and statistics endpoints for the finance module.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.finance import (
    FinanceDashboardResponse,
    FinanceDashboardStats,
    OutstandingByClass,
    RecentPayment,
)
from app.services.finance import FinanceDashboardService

from ._helpers import get_school_for_tenant

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=FinanceDashboardResponse,
    summary="Get finance dashboard",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_finance_dashboard(
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
) -> FinanceDashboardResponse:
    """Get finance dashboard with stats and recent activity."""
    try:
        school = await get_school_for_tenant(db, tenant.tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    service = FinanceDashboardService(db)

    stats = await service.get_dashboard_stats(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )

    recent_payments = await service.get_recent_payments(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        limit=5,
    )

    outstanding = await service.get_outstanding_by_class(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
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

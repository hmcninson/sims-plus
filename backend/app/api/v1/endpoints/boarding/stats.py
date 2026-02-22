"""
SIMS Plus - Boarding Stats Endpoint

Aggregated statistics for the boarding module dashboard.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.models.boarding import (
    House,
    Dormitory,
    Bed,
    BedStatus,
    StudentBoarding,
    BoardingStatus,
    Exeat,
    ExeatStatus,
    BoardingIncident,
)
from app.schemas.boarding import BoardingStatsResponse

from ._helpers import _get_school_id

router = APIRouter()


@router.get(
    "/stats",
    response_model=BoardingStatsResponse,
    summary="Get boarding statistics",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_boarding_stats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingStatsResponse:
    """Get aggregated boarding statistics for the dashboard."""
    school_id = _get_school_id(user)
    tenant_id = tenant.tenant_id

    # Houses count
    houses_q = select(func.count(House.id)).where(
        and_(House.tenant_id == tenant_id, House.deleted_at.is_(None))
    )
    total_houses = (await db.execute(houses_q)).scalar() or 0

    # Dormitories count
    dorms_q = select(func.count(Dormitory.id)).where(
        and_(Dormitory.tenant_id == tenant_id, Dormitory.deleted_at.is_(None))
    )
    total_dormitories = (await db.execute(dorms_q)).scalar() or 0

    # Beds: total, available, occupied
    beds_q = select(
        func.count(Bed.id),
        func.count(Bed.id).filter(Bed.status == BedStatus.AVAILABLE),
        func.count(Bed.id).filter(Bed.status == BedStatus.OCCUPIED),
    ).where(
        and_(Bed.tenant_id == tenant_id, Bed.deleted_at.is_(None))
    )
    beds_result = (await db.execute(beds_q)).one()
    total_beds = beds_result[0] or 0
    available_beds = beds_result[1] or 0
    occupied_beds = beds_result[2] or 0

    # Active boarders
    boarders_q = select(func.count(StudentBoarding.id)).where(
        and_(
            StudentBoarding.tenant_id == tenant_id,
            StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
            StudentBoarding.deleted_at.is_(None),
        )
    )
    total_boarders = (await db.execute(boarders_q)).scalar() or 0

    # Active exeats
    active_exeats_q = select(func.count(Exeat.id)).where(
        and_(
            Exeat.tenant_id == tenant_id,
            Exeat.status == ExeatStatus.ACTIVE,
            Exeat.deleted_at.is_(None),
        )
    )
    active_exeats = (await db.execute(active_exeats_q)).scalar() or 0

    # Pending exeats
    pending_exeats_q = select(func.count(Exeat.id)).where(
        and_(
            Exeat.tenant_id == tenant_id,
            Exeat.status == ExeatStatus.PENDING,
            Exeat.deleted_at.is_(None),
        )
    )
    pending_exeats = (await db.execute(pending_exeats_q)).scalar() or 0

    # Unresolved incidents
    incidents_q = select(func.count(BoardingIncident.id)).where(
        and_(
            BoardingIncident.tenant_id == tenant_id,
            BoardingIncident.resolved == False,
            BoardingIncident.deleted_at.is_(None),
        )
    )
    unresolved_incidents = (await db.execute(incidents_q)).scalar() or 0

    return BoardingStatsResponse(
        total_houses=total_houses,
        total_dormitories=total_dormitories,
        total_beds=total_beds,
        available_beds=available_beds,
        occupied_beds=occupied_beds,
        total_boarders=total_boarders,
        active_exeats=active_exeats,
        pending_exeats=pending_exeats,
        unresolved_incidents=unresolved_incidents,
    )

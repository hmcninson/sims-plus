"""
SIMS Plus - Transport Stats Endpoint

Aggregated statistics for the transport module dashboard.
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
from app.models.transport import (
    Vehicle,
    VehicleStatus,
    Driver,
    DriverStatus,
    Route,
    StudentTransport,
    TransportAssignmentStatus,
    TripLog,
)
from app.schemas.transport import TransportStatsResponse

from ._helpers import _get_school_id

router = APIRouter()


@router.get(
    "/stats",
    response_model=TransportStatsResponse,
    summary="Get transport statistics",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_transport_stats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> TransportStatsResponse:
    """Get aggregated transport statistics for the dashboard."""
    school_id = _get_school_id(user)
    tenant_id = tenant.tenant_id

    # Vehicles: total, active, in maintenance
    vehicles_q = select(
        func.count(Vehicle.id),
        func.count(Vehicle.id).filter(Vehicle.status == VehicleStatus.ACTIVE),
        func.count(Vehicle.id).filter(Vehicle.status == VehicleStatus.MAINTENANCE),
    ).where(
        and_(Vehicle.tenant_id == tenant_id, Vehicle.deleted_at.is_(None))
    )
    vehicles_result = (await db.execute(vehicles_q)).one()
    total_vehicles = vehicles_result[0] or 0
    active_vehicles = vehicles_result[1] or 0
    maintenance_vehicles = vehicles_result[2] or 0

    # Drivers: total, active
    drivers_q = select(
        func.count(Driver.id),
        func.count(Driver.id).filter(Driver.status == DriverStatus.ACTIVE),
    ).where(
        and_(Driver.tenant_id == tenant_id, Driver.deleted_at.is_(None))
    )
    drivers_result = (await db.execute(drivers_q)).one()
    total_drivers = drivers_result[0] or 0
    active_drivers = drivers_result[1] or 0

    # Routes: total, active
    routes_q = select(
        func.count(Route.id),
        func.count(Route.id).filter(Route.is_active == True),
    ).where(
        and_(Route.tenant_id == tenant_id, Route.deleted_at.is_(None))
    )
    routes_result = (await db.execute(routes_q)).one()
    total_routes = routes_result[0] or 0
    active_routes = routes_result[1] or 0

    # Students assigned (active assignments)
    students_q = select(func.count(StudentTransport.id)).where(
        and_(
            StudentTransport.tenant_id == tenant_id,
            StudentTransport.status == TransportAssignmentStatus.ACTIVE,
            StudentTransport.deleted_at.is_(None),
        )
    )
    total_students_assigned = (await db.execute(students_q)).scalar() or 0

    # Trips today
    today = date.today()
    trips_q = select(func.count(TripLog.id)).where(
        and_(
            TripLog.tenant_id == tenant_id,
            TripLog.trip_date == today,
            TripLog.deleted_at.is_(None),
        )
    )
    trips_today = (await db.execute(trips_q)).scalar() or 0

    return TransportStatsResponse(
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        maintenance_vehicles=maintenance_vehicles,
        total_drivers=total_drivers,
        active_drivers=active_drivers,
        total_routes=total_routes,
        active_routes=active_routes,
        total_students_assigned=total_students_assigned,
        trips_today=trips_today,
    )

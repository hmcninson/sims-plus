"""
SIMS Plus - Transport Trip Log Endpoints

Endpoints for creating and managing trip logs, trip lifecycle transitions
(start, complete, cancel), and trip statistics.
"""

import math
from datetime import date, time
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.transport import (
    TripLogCreate,
    TripLogDetailResponse,
    TripLogListResponse,
    TripLogResponse,
)
from app.services.transport import TransportServiceError, TripService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


# =========================
# Inline schemas for trip lifecycle actions
# =========================


class TripStartRequest(BaseModel):
    """Optional request body for starting a trip."""

    departure_time: Optional[time] = None


class TripCompleteRequest(BaseModel):
    """Optional request body for completing a trip."""

    arrival_time: Optional[time] = None
    odometer_end: Optional[int] = Field(None, ge=0)
    incidents: Optional[str] = None


# =========================
# Trip Endpoints
# =========================

# Static routes (/stats) must come before parameterized /{trip_id} routes.


@router.get(
    "/trips/stats",
    summary="Get trip statistics",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_trip_stats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2000, le=2100, description="Year"),
) -> dict:
    """
    Get aggregate trip statistics for a given month.

    Returns total trips, completed trips, cancelled trips, average student
    count, and per-route breakdowns for fleet management dashboards.
    """
    school_id = _get_school_id(user)
    service = TripService(db)

    return await service.get_trip_stats(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        month=month,
        year=year,
    )


@router.post(
    "/trips",
    response_model=TripLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create trip log",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def create_trip(
    data: TripLogCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> TripLogResponse:
    """
    Create a new trip log entry.

    Validates that the route, vehicle, and driver all exist and belong to the tenant.
    """
    school_id = _get_school_id(user)
    service = TripService(db)

    try:
        trip = await service.create_trip(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            route_id=data.route_id,
            vehicle_id=data.vehicle_id,
            driver_id=data.driver_id,
            trip_date=data.trip_date,
            trip_type=data.trip_type,
            student_count=data.student_count,
            logged_by_id=UUID(user["user_id"]),
            departure_time=data.departure_time,
            arrival_time=data.arrival_time,
            odometer_start=data.odometer_start,
            odometer_end=data.odometer_end,
            status=data.status,
            incidents=data.incidents,
        )
        return TripLogResponse.model_validate(trip)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/trips",
    response_model=TripLogListResponse,
    summary="List trips",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def list_trips(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    route_id: UUID | None = Query(None, description="Filter by route"),
    date_from: date | None = Query(None, description="Filter trips from this date"),
    date_to: date | None = Query(None, description="Filter trips up to this date"),
    trip_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status (scheduled, in_progress, completed, cancelled)",
    ),
) -> TripLogListResponse:
    """List trip logs with optional filters for route, date range, and status."""
    school_id = _get_school_id(user)
    service = TripService(db)

    trips, total = await service.get_trips(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        route_id=route_id,
        date_from=date_from,
        date_to=date_to,
        status=trip_status,
        page=page,
        page_size=page_size,
    )

    items = [_build_trip_detail(t) for t in trips]

    return TripLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/trips/{trip_id}",
    response_model=TripLogDetailResponse,
    summary="Get trip detail",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_trip(
    trip_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> TripLogDetailResponse:
    """Get a trip log by ID with route, vehicle, and driver details."""
    service = TripService(db)

    try:
        trip = await service.get_trip(
            tenant_id=tenant.tenant_id,
            trip_id=trip_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

    return _build_trip_detail(trip)


# =========================
# Trip Lifecycle Endpoints
# =========================


@router.post(
    "/trips/{trip_id}/start",
    response_model=TripLogResponse,
    summary="Start trip",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def start_trip(
    trip_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    data: TripStartRequest | None = None,
) -> TripLogResponse:
    """
    Start a scheduled trip by transitioning its status to 'in_progress'.

    Optionally accepts a departure_time; defaults to current time if omitted.
    """
    service = TripService(db)

    departure_time = data.departure_time if data else None

    try:
        trip = await service.start_trip(
            tenant_id=tenant.tenant_id,
            trip_id=trip_id,
            departure_time=departure_time,
        )
        return TripLogResponse.model_validate(trip)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/trips/{trip_id}/complete",
    response_model=TripLogResponse,
    summary="Complete trip",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def complete_trip(
    trip_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    data: TripCompleteRequest | None = None,
) -> TripLogResponse:
    """
    Complete an in-progress trip by transitioning its status to 'completed'.

    Optionally accepts arrival_time, odometer_end, and incidents.
    """
    service = TripService(db)

    arrival_time = data.arrival_time if data else None
    odometer_end = data.odometer_end if data else None
    incidents = data.incidents if data else None

    try:
        trip = await service.complete_trip(
            tenant_id=tenant.tenant_id,
            trip_id=trip_id,
            arrival_time=arrival_time,
            odometer_end=odometer_end,
            incidents=incidents,
        )
        return TripLogResponse.model_validate(trip)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.post(
    "/trips/{trip_id}/cancel",
    response_model=TripLogResponse,
    summary="Cancel trip",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def cancel_trip(
    trip_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> TripLogResponse:
    """
    Cancel a trip.

    Only scheduled or in-progress trips can be cancelled. Completed trips
    cannot be reverted.
    """
    service = TripService(db)

    try:
        trip = await service.cancel_trip(
            tenant_id=tenant.tenant_id,
            trip_id=trip_id,
        )
        return TripLogResponse.model_validate(trip)
    except TransportServiceError as e:
        raise _handle_service_error(e)


# =========================
# Helper Functions
# =========================


def _build_trip_detail(trip) -> TripLogDetailResponse:
    """
    Build a TripLogDetailResponse from a TripLog model with eagerly loaded
    relationships (route, vehicle, driver, logged_by).
    """
    route_name = None
    if hasattr(trip, "route") and trip.route:
        route_name = trip.route.name

    vehicle_registration = None
    if hasattr(trip, "vehicle") and trip.vehicle:
        vehicle_registration = trip.vehicle.registration_number

    driver_name = None
    if hasattr(trip, "driver") and trip.driver:
        driver_name = f"{trip.driver.first_name} {trip.driver.last_name}"

    logged_by_name = None
    if hasattr(trip, "logged_by") and trip.logged_by:
        logged_by_name = f"{trip.logged_by.first_name} {trip.logged_by.last_name}"

    return TripLogDetailResponse(
        id=trip.id,
        tenant_id=trip.tenant_id,
        school_id=trip.school_id,
        route_id=trip.route_id,
        vehicle_id=trip.vehicle_id,
        driver_id=trip.driver_id,
        trip_date=trip.trip_date,
        trip_type=trip.trip_type.value if hasattr(trip.trip_type, "value") else trip.trip_type,
        departure_time=trip.departure_time,
        arrival_time=trip.arrival_time,
        odometer_start=trip.odometer_start,
        odometer_end=trip.odometer_end,
        student_count=trip.student_count,
        status=trip.status.value if hasattr(trip.status, "value") else trip.status,
        incidents=trip.incidents,
        logged_by_id=trip.logged_by_id,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
        route_name=route_name,
        vehicle_registration=vehicle_registration,
        driver_name=driver_name,
        logged_by_name=logged_by_name,
    )

"""
SIMS Plus - Transport Route & Stop Endpoints

CRUD endpoints for managing transport routes, route stops, route manifests,
and capacity information.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.transport import (
    RouteCreate,
    RouteDetailResponse,
    RouteListResponse,
    RouteResponse,
    RouteStopCreate,
    RouteStopResponse,
    RouteStopUpdate,
    RouteUpdate,
)
from app.services.transport import RouteService, TransportServiceError

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


# =========================
# Inline schemas for specific endpoint needs
# =========================


class StopReorderRequest(BaseModel):
    """Request body for reordering route stops."""

    stop_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Ordered list of all stop IDs for the route",
    )


# =========================
# Route Endpoints
# =========================

# Static routes must be declared before parameterized /{route_id} routes
# to avoid FastAPI treating "with-stops" as a UUID path parameter.


@router.post(
    "/routes/with-stops",
    response_model=RouteDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create route with stops",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def create_route_with_stops(
    data: RouteCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RouteDetailResponse:
    """
    Create a route and its stops in a single atomic operation.

    The stops field in the request body is required for this endpoint.
    Use POST /routes to create a route without stops.
    """
    school_id = _get_school_id(user)
    service = RouteService(db)

    if not data.stops:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one stop is required when creating a route with stops",
        )

    # Convert stop schemas to dicts for the service layer
    stops_data = [s.model_dump() for s in data.stops]

    try:
        route = await service.create_route_with_stops(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            name=data.name,
            route_code=data.route_code,
            route_type=data.route_type,
            stops_data=stops_data,
            description=data.description,
            distance_km=data.distance_km,
            estimated_duration_minutes=data.estimated_duration_minutes,
            vehicle_id=data.vehicle_id,
            driver_id=data.driver_id,
            is_active=data.is_active,
            transport_fee_per_term=data.transport_fee_per_term,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

    return _build_route_detail(route)


@router.post(
    "/routes",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create route",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def create_route(
    data: RouteCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RouteResponse:
    """Create a new transport route (without stops)."""
    school_id = _get_school_id(user)
    service = RouteService(db)

    try:
        route = await service.create_route(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            name=data.name,
            route_code=data.route_code,
            route_type=data.route_type,
            description=data.description,
            distance_km=data.distance_km,
            estimated_duration_minutes=data.estimated_duration_minutes,
            vehicle_id=data.vehicle_id,
            driver_id=data.driver_id,
            is_active=data.is_active,
            transport_fee_per_term=data.transport_fee_per_term,
        )
        return RouteResponse.model_validate(route)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/routes",
    response_model=RouteListResponse,
    summary="List routes",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def list_routes(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by route name or code"),
) -> RouteListResponse:
    """List all routes with optional filters."""
    school_id = _get_school_id(user)
    service = RouteService(db)

    routes, total = await service.get_routes(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )

    return RouteListResponse(
        items=[RouteResponse.model_validate(r) for r in routes],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/routes/{route_id}",
    response_model=RouteDetailResponse,
    summary="Get route detail",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_route(
    route_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RouteDetailResponse:
    """Get a route by ID with stops, vehicle, and driver info."""
    service = RouteService(db)

    try:
        route = await service.get_route(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

    return _build_route_detail(route)


@router.put(
    "/routes/{route_id}",
    response_model=RouteResponse,
    summary="Update route",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def update_route(
    route_id: UUID,
    data: RouteUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RouteResponse:
    """Update an existing route."""
    service = RouteService(db)

    try:
        route = await service.update_route(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
            **data.model_dump(exclude_unset=True),
        )
        return RouteResponse.model_validate(route)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete route",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def delete_route(
    route_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft delete a route. Fails if route has active student assignments."""
    service = RouteService(db)

    try:
        await service.delete_route(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)


# =========================
# Route Stop Endpoints
# =========================


@router.post(
    "/routes/{route_id}/stops",
    response_model=RouteStopResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add stop to route",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def add_stop(
    route_id: UUID,
    data: RouteStopCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RouteStopResponse:
    """Add a new stop to a route."""
    service = RouteService(db)

    try:
        stop = await service.add_stop(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
            stop_name=data.stop_name,
            stop_order=data.stop_order,
            pickup_time=data.pickup_time,
            dropoff_time=data.dropoff_time,
            latitude=data.latitude,
            longitude=data.longitude,
            landmark=data.landmark,
        )
        return RouteStopResponse.model_validate(stop)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.put(
    "/routes/{route_id}/stops/{stop_id}",
    response_model=RouteStopResponse,
    summary="Update stop",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def update_stop(
    route_id: UUID,
    stop_id: UUID,
    data: RouteStopUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RouteStopResponse:
    """Update an existing route stop."""
    service = RouteService(db)

    # The route_id in the URL path provides context; the service validates
    # that the stop belongs to the tenant via tenant_id filtering.
    try:
        stop = await service.update_stop(
            tenant_id=tenant.tenant_id,
            stop_id=stop_id,
            **data.model_dump(exclude_unset=True),
        )
        return RouteStopResponse.model_validate(stop)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/routes/{route_id}/stops/{stop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete stop",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def delete_stop(
    route_id: UUID,
    stop_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Hard delete a route stop.

    Fails if the stop has active student transport assignments.
    """
    service = RouteService(db)

    try:
        await service.delete_stop(
            tenant_id=tenant.tenant_id,
            stop_id=stop_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.put(
    "/routes/{route_id}/stops/reorder",
    response_model=list[RouteStopResponse],
    summary="Reorder stops",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def reorder_stops(
    route_id: UUID,
    data: StopReorderRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[RouteStopResponse]:
    """
    Reorder all stops on a route.

    All stop IDs for the route must be provided in the desired order.
    """
    service = RouteService(db)

    try:
        stops = await service.reorder_stops(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
            stop_ids_in_order=data.stop_ids,
        )
        return [RouteStopResponse.model_validate(s) for s in stops]
    except TransportServiceError as e:
        raise _handle_service_error(e)


# =========================
# Route Manifest & Capacity
# =========================


@router.get(
    "/routes/{route_id}/manifest",
    summary="Get route manifest",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_route_manifest(
    route_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(
        ..., description="Academic year to get manifest for"
    ),
) -> dict:
    """
    Get the route manifest: students grouped by stop with guardian contact info.

    Used for generating printable manifests for drivers and for the route
    detail view showing who is at each stop.
    """
    service = RouteService(db)

    try:
        return await service.get_route_manifest(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
            academic_year_id=academic_year_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/routes/{route_id}/capacity",
    summary="Get route capacity",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_route_capacity(
    route_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(
        ..., description="Academic year to check capacity for"
    ),
) -> dict:
    """
    Get route capacity information: vehicle seats vs active student assignments.

    Used to show capacity utilization on the route management view.
    """
    from app.services.transport import TransportAssignmentService

    service = TransportAssignmentService(db)

    try:
        return await service.get_route_capacity(
            tenant_id=tenant.tenant_id,
            route_id=route_id,
            academic_year_id=academic_year_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)


# =========================
# Helper Functions
# =========================


def _build_route_detail(route) -> RouteDetailResponse:
    """
    Build a RouteDetailResponse from a Route model with eagerly loaded
    relationships (stops, vehicle, driver).
    """
    vehicle_registration = None
    if hasattr(route, "vehicle") and route.vehicle:
        vehicle_registration = route.vehicle.registration_number

    driver_name = None
    if hasattr(route, "driver") and route.driver:
        driver_name = f"{route.driver.first_name} {route.driver.last_name}"

    stops = []
    if hasattr(route, "stops") and route.stops:
        stops = [
            RouteStopResponse.model_validate(s)
            for s in sorted(route.stops, key=lambda s: s.stop_order)
        ]

    return RouteDetailResponse(
        id=route.id,
        tenant_id=route.tenant_id,
        school_id=route.school_id,
        name=route.name,
        route_code=route.route_code,
        description=route.description,
        distance_km=route.distance_km,
        estimated_duration_minutes=route.estimated_duration_minutes,
        vehicle_id=route.vehicle_id,
        driver_id=route.driver_id,
        route_type=route.route_type.value if hasattr(route.route_type, "value") else route.route_type,
        is_active=route.is_active,
        transport_fee_per_term=route.transport_fee_per_term,
        created_at=route.created_at,
        updated_at=route.updated_at,
        vehicle_registration=vehicle_registration,
        driver_name=driver_name,
        stops=stops,
        student_count=0,
    )

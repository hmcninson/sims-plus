"""
SIMS Plus - Transport Vehicle & Maintenance Endpoints

CRUD endpoints for managing transport vehicles, document expiry alerts,
and vehicle maintenance records.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.transport import (
    VehicleCreate,
    VehicleDetailResponse,
    VehicleListResponse,
    VehicleMaintenanceCreate,
    VehicleMaintenanceDetailResponse,
    VehicleMaintenanceListResponse,
    VehicleMaintenanceResponse,
    VehicleResponse,
    VehicleUpdate,
)
from app.services.transport import TransportServiceError, VehicleService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


# =========================
# Vehicle Endpoints
# =========================


@router.post(
    "/vehicles",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create vehicle",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def create_vehicle(
    data: VehicleCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> VehicleResponse:
    """Register a new vehicle in the transport fleet."""
    school_id = _get_school_id(user)
    service = VehicleService(db)

    try:
        vehicle = await service.create_vehicle(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            registration_number=data.registration_number,
            vehicle_type=data.vehicle_type,
            capacity=data.capacity,
            make=data.make,
            model_name=data.model_name,
            year=data.year,
            status=data.status,
            insurance_expiry=data.insurance_expiry,
            roadworthy_expiry=data.roadworthy_expiry,
            gps_tracker_id=data.gps_tracker_id,
            notes=data.notes,
        )
        return VehicleResponse.model_validate(vehicle)
    except TransportServiceError as e:
        raise _handle_service_error(e)


# Static route must come before parameterized /{vehicle_id} routes
@router.get(
    "/vehicles/alerts",
    summary="Get vehicle alerts",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_vehicle_alerts(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[dict]:
    """
    Get vehicles with expiring or expired documents.

    Returns vehicles whose insurance or roadworthy certificates expire
    within 30 days or have already expired.
    """
    school_id = _get_school_id(user)
    service = VehicleService(db)

    return await service.get_vehicles_with_alerts(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
    )


@router.get(
    "/vehicles",
    response_model=VehicleListResponse,
    summary="List vehicles",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def list_vehicles(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    vehicle_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status (active, maintenance, retired)",
    ),
    search: str | None = Query(None, description="Search by registration, make, or model"),
) -> VehicleListResponse:
    """List all vehicles with optional status filter and search."""
    school_id = _get_school_id(user)
    service = VehicleService(db)

    vehicles, total = await service.get_vehicles(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        status=vehicle_status,
        search=search,
        page=page,
        page_size=page_size,
    )

    return VehicleListResponse(
        items=[VehicleResponse.model_validate(v) for v in vehicles],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleDetailResponse,
    summary="Get vehicle detail",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_vehicle(
    vehicle_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> VehicleDetailResponse:
    """Get a vehicle by ID with route and maintenance summary."""
    service = VehicleService(db)

    try:
        vehicle = await service.get_vehicle(
            tenant_id=tenant.tenant_id,
            vehicle_id=vehicle_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

    return VehicleDetailResponse.model_validate(vehicle)


@router.put(
    "/vehicles/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Update vehicle",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> VehicleResponse:
    """Update an existing vehicle."""
    service = VehicleService(db)

    try:
        vehicle = await service.update_vehicle(
            tenant_id=tenant.tenant_id,
            vehicle_id=vehicle_id,
            **data.model_dump(exclude_unset=True),
        )
        return VehicleResponse.model_validate(vehicle)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete vehicle",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def delete_vehicle(
    vehicle_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft delete a vehicle. Fails if vehicle is assigned to active routes."""
    service = VehicleService(db)

    try:
        await service.delete_vehicle(
            tenant_id=tenant.tenant_id,
            vehicle_id=vehicle_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)


# =========================
# Vehicle Maintenance Endpoints
# =========================


@router.post(
    "/vehicles/{vehicle_id}/maintenance",
    response_model=VehicleMaintenanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log vehicle maintenance",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def create_maintenance(
    vehicle_id: UUID,
    data: VehicleMaintenanceCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> VehicleMaintenanceResponse:
    """Log a maintenance record for a vehicle."""
    school_id = _get_school_id(user)
    service = VehicleService(db)

    try:
        record = await service.create_maintenance(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            vehicle_id=vehicle_id,
            logged_by_id=UUID(user["user_id"]),
            maintenance_type=data.maintenance_type,
            description=data.description,
            service_date=data.service_date,
            cost=data.cost,
            next_service_date=data.next_service_date,
            odometer_reading=data.odometer_reading,
            service_provider=data.service_provider,
            invoice_number=data.invoice_number,
        )
        return VehicleMaintenanceResponse.model_validate(record)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/vehicles/{vehicle_id}/maintenance",
    response_model=VehicleMaintenanceListResponse,
    summary="Get vehicle maintenance history",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_maintenance_history(
    vehicle_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> VehicleMaintenanceListResponse:
    """Get paginated maintenance history for a vehicle."""
    service = VehicleService(db)

    try:
        records, total = await service.get_maintenance_history(
            tenant_id=tenant.tenant_id,
            vehicle_id=vehicle_id,
            page=page,
            page_size=page_size,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

    return VehicleMaintenanceListResponse(
        items=[VehicleMaintenanceDetailResponse.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )

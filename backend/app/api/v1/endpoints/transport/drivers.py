"""
SIMS Plus - Transport Driver Endpoints

CRUD endpoints for managing transport drivers, including license tracking.
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
    DriverCreate,
    DriverListResponse,
    DriverResponse,
    DriverUpdate,
)
from app.services.transport import DriverService, TransportServiceError

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


# =========================
# Driver Endpoints
# =========================


@router.post(
    "/drivers",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create driver",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def create_driver(
    data: DriverCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DriverResponse:
    """Register a new driver."""
    school_id = _get_school_id(user)
    service = DriverService(db)

    try:
        driver = await service.create_driver(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            license_number=data.license_number,
            license_expiry=data.license_expiry,
            license_class=data.license_class,
            staff_id=data.staff_id,
            status=data.status,
            emergency_contact_name=data.emergency_contact_name,
            emergency_contact_phone=data.emergency_contact_phone,
        )
        return DriverResponse.model_validate(driver)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/drivers",
    response_model=DriverListResponse,
    summary="List drivers",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def list_drivers(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    driver_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status (active, on_leave, terminated)",
    ),
    search: str | None = Query(
        None,
        description="Search by name, phone, or license number",
    ),
) -> DriverListResponse:
    """List all drivers with optional status filter and search."""
    school_id = _get_school_id(user)
    service = DriverService(db)

    drivers, total = await service.get_drivers(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        status=driver_status,
        search=search,
        page=page,
        page_size=page_size,
    )

    return DriverListResponse(
        items=[DriverResponse.model_validate(d) for d in drivers],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/drivers/{driver_id}",
    response_model=DriverResponse,
    summary="Get driver detail",
    dependencies=[Depends(require_permissions("transport.read"))],
)
async def get_driver(
    driver_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DriverResponse:
    """Get a driver by ID."""
    service = DriverService(db)

    try:
        driver = await service.get_driver(
            tenant_id=tenant.tenant_id,
            driver_id=driver_id,
        )
        return DriverResponse.model_validate(driver)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.put(
    "/drivers/{driver_id}",
    response_model=DriverResponse,
    summary="Update driver",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def update_driver(
    driver_id: UUID,
    data: DriverUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DriverResponse:
    """Update an existing driver."""
    service = DriverService(db)

    try:
        driver = await service.update_driver(
            tenant_id=tenant.tenant_id,
            driver_id=driver_id,
            **data.model_dump(exclude_unset=True),
        )
        return DriverResponse.model_validate(driver)
    except TransportServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/drivers/{driver_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete driver",
    dependencies=[Depends(require_permissions("transport.write"))],
)
async def delete_driver(
    driver_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft delete a driver. Fails if driver is assigned to active routes."""
    service = DriverService(db)

    try:
        await service.delete_driver(
            tenant_id=tenant.tenant_id,
            driver_id=driver_id,
        )
    except TransportServiceError as e:
        raise _handle_service_error(e)

"""
SIMS Plus - Boarding House, Dormitory & Bed Endpoints

CRUD endpoints for managing boarding houses, their dormitories, and individual beds.
Houses are top-level containers; dormitories are nested within houses; beds are
nested within dormitories.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.boarding import (
    BedBulkCreate,
    BedDetailResponse,
    BedResponse,
    BedUpdate,
    DormitoryCreate,
    DormitoryDetailResponse,
    DormitoryUpdate,
    HouseCreate,
    HouseDetailResponse,
    HouseListResponse,
    HouseResponse,
    HouseUpdate,
)
from app.services.boarding import BoardingServiceError, HouseService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


# =========================
# House Endpoints
# =========================


@router.post(
    "/houses",
    response_model=HouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create house",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def create_house(
    data: HouseCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> HouseResponse:
    """Create a new boarding house."""
    school_id = _get_school_id(user)
    service = HouseService(db)

    try:
        house = await service.create_house(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            data=data.model_dump(),
        )
        return HouseResponse.model_validate(house)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/houses",
    response_model=HouseListResponse,
    summary="List houses",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_houses(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    search: str | None = Query(None, description="Search by house name"),
    is_active: bool | None = Query(None, description="Filter by active status"),
) -> HouseListResponse:
    """List all boarding houses with occupancy information."""
    school_id = _get_school_id(user)
    service = HouseService(db)

    house_data = await service.get_houses(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        search=search,
        is_active=is_active,
    )

    # Build response items with occupancy from service result
    items = []
    for item in house_data:
        house = item["house"]
        response = HouseDetailResponse(
            id=house.id,
            tenant_id=house.tenant_id,
            school_id=house.school_id,
            name=house.name,
            house_code=house.house_code,
            gender=house.gender,
            capacity=house.capacity,
            house_parent_id=house.house_parent_id,
            description=house.description,
            is_active=house.is_active,
            created_at=house.created_at,
            updated_at=house.updated_at,
            current_occupancy=item["current_occupancy"],
        )
        items.append(response)

    total = len(items)
    return HouseListResponse(
        items=items,
        total=total,
        page=1,
        page_size=total or 1,
        pages=1,
    )


@router.get(
    "/houses/{house_id}",
    response_model=HouseDetailResponse,
    summary="Get house detail",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_house(
    house_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> HouseDetailResponse:
    """Get a boarding house by ID with dormitory and occupancy information."""
    service = HouseService(db)

    try:
        house = await service.get_house(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    # Get occupancy stats for the detail view
    try:
        occupancy = await service.get_house_occupancy(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
        )
    except BoardingServiceError:
        occupancy = {"current_occupancy": 0}

    # Count active dormitories
    dormitory_count = 0
    if hasattr(house, "dormitories") and house.dormitories:
        dormitory_count = len([
            d for d in house.dormitories if d.deleted_at is None
        ])

    # Get house parent name if assigned
    house_parent_name = None
    if hasattr(house, "house_parent") and house.house_parent:
        hp = house.house_parent
        house_parent_name = f"{hp.first_name} {hp.last_name}"

    return HouseDetailResponse(
        id=house.id,
        tenant_id=house.tenant_id,
        school_id=house.school_id,
        name=house.name,
        house_code=house.house_code,
        gender=house.gender,
        capacity=house.capacity,
        house_parent_id=house.house_parent_id,
        description=house.description,
        is_active=house.is_active,
        created_at=house.created_at,
        updated_at=house.updated_at,
        house_parent_name=house_parent_name,
        dormitory_count=dormitory_count,
        current_occupancy=occupancy["current_occupancy"],
    )


@router.put(
    "/houses/{house_id}",
    response_model=HouseResponse,
    summary="Update house",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def update_house(
    house_id: UUID,
    data: HouseUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> HouseResponse:
    """Update an existing boarding house."""
    service = HouseService(db)

    try:
        house = await service.update_house(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
            data=data.model_dump(exclude_unset=True),
        )
        return HouseResponse.model_validate(house)
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/houses/{house_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete house",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def delete_house(
    house_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft delete a boarding house."""
    service = HouseService(db)

    try:
        await service.delete_house(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/houses/{house_id}/occupancy",
    summary="Get house occupancy",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_house_occupancy(
    house_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """Get occupancy statistics for a boarding house."""
    service = HouseService(db)

    try:
        return await service.get_house_occupancy(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


# =========================
# Dormitory Endpoints
# =========================


@router.post(
    "/houses/{house_id}/dormitories",
    response_model=DormitoryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create dormitory",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def create_dormitory(
    house_id: UUID,
    data: DormitoryCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DormitoryDetailResponse:
    """Create a new dormitory within a house."""
    school_id = _get_school_id(user)
    service = HouseService(db)

    try:
        dormitory = await service.create_dormitory(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            house_id=house_id,
            data=data.model_dump(),
        )
        return DormitoryDetailResponse(
            id=dormitory.id,
            tenant_id=dormitory.tenant_id,
            school_id=dormitory.school_id,
            house_id=dormitory.house_id,
            name=dormitory.name,
            floor=dormitory.floor,
            capacity=dormitory.capacity,
            dormitory_type=dormitory.dormitory_type,
            is_active=dormitory.is_active,
            created_at=dormitory.created_at,
            updated_at=dormitory.updated_at,
            bed_count=0,
            occupied_beds=0,
            available_beds=0,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/houses/{house_id}/dormitories",
    response_model=list[DormitoryDetailResponse],
    summary="List dormitories",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_dormitories(
    house_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[DormitoryDetailResponse]:
    """List all dormitories for a house with bed statistics."""
    service = HouseService(db)

    try:
        dorm_data = await service.get_dormitories(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    results = []
    for item in dorm_data:
        dorm = item["dormitory"]
        results.append(
            DormitoryDetailResponse(
                id=dorm.id,
                tenant_id=dorm.tenant_id,
                school_id=dorm.school_id,
                house_id=dorm.house_id,
                name=dorm.name,
                floor=dorm.floor,
                capacity=dorm.capacity,
                dormitory_type=dorm.dormitory_type,
                is_active=dorm.is_active,
                created_at=dorm.created_at,
                updated_at=dorm.updated_at,
                bed_count=item["bed_count"],
                occupied_beds=item["occupied_beds"],
                available_beds=item["available_beds"],
            )
        )
    return results


@router.put(
    "/dormitories/{dormitory_id}",
    response_model=DormitoryDetailResponse,
    summary="Update dormitory",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def update_dormitory(
    dormitory_id: UUID,
    data: DormitoryUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DormitoryDetailResponse:
    """Update a dormitory."""
    service = HouseService(db)

    try:
        dormitory = await service.update_dormitory(
            tenant_id=tenant.tenant_id,
            dormitory_id=dormitory_id,
            data=data.model_dump(exclude_unset=True),
        )
        return DormitoryDetailResponse(
            id=dormitory.id,
            tenant_id=dormitory.tenant_id,
            school_id=dormitory.school_id,
            house_id=dormitory.house_id,
            name=dormitory.name,
            floor=dormitory.floor,
            capacity=dormitory.capacity,
            dormitory_type=dormitory.dormitory_type,
            is_active=dormitory.is_active,
            created_at=dormitory.created_at,
            updated_at=dormitory.updated_at,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/dormitories/{dormitory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete dormitory",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def delete_dormitory(
    dormitory_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft delete a dormitory."""
    service = HouseService(db)

    try:
        await service.delete_dormitory(
            tenant_id=tenant.tenant_id,
            dormitory_id=dormitory_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


# =========================
# Bed Endpoints
# =========================


@router.post(
    "/dormitories/{dormitory_id}/beds",
    response_model=list[BedResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create beds",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def create_beds(
    dormitory_id: UUID,
    data: BedBulkCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[BedResponse]:
    """
    Bulk create beds for a dormitory.

    Generates bed numbers using the provided prefix and sequential numbering
    (e.g., B-001, B-002, ...).
    """
    school_id = _get_school_id(user)
    service = HouseService(db)

    # Generate bed data from the bulk create schema
    beds_data = [
        {
            "bed_number": f"{data.prefix}-{str(i + 1).zfill(3)}",
            "bed_type": data.bed_type,
        }
        for i in range(data.count)
    ]

    try:
        beds = await service.create_beds(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            dormitory_id=dormitory_id,
            beds_data=beds_data,
        )
        return [BedResponse.model_validate(bed) for bed in beds]
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/dormitories/{dormitory_id}/beds",
    response_model=list[BedDetailResponse],
    summary="List beds",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_beds(
    dormitory_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    bed_status: str | None = Query(
        None,
        alias="status",
        description="Filter by bed status (available, occupied, maintenance)",
    ),
) -> list[BedDetailResponse]:
    """List all beds for a dormitory with occupant information."""
    service = HouseService(db)

    try:
        bed_data = await service.get_beds(
            tenant_id=tenant.tenant_id,
            dormitory_id=dormitory_id,
            status=bed_status,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    results = []
    for item in bed_data:
        bed = item["bed"]
        results.append(
            BedDetailResponse(
                id=bed.id,
                tenant_id=bed.tenant_id,
                school_id=bed.school_id,
                dormitory_id=bed.dormitory_id,
                bed_number=bed.bed_number,
                bed_type=bed.bed_type,
                status=bed.status.value if hasattr(bed.status, "value") else bed.status,
                is_active=bed.is_active,
                created_at=bed.created_at,
                updated_at=bed.updated_at,
                occupant_id=item.get("occupant_id"),
            )
        )
    return results


@router.put(
    "/beds/{bed_id}",
    response_model=BedResponse,
    summary="Update bed",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def update_bed(
    bed_id: UUID,
    data: BedUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BedResponse:
    """Update a bed's details (number, type, status)."""
    service = HouseService(db)

    try:
        bed = await service.update_bed(
            tenant_id=tenant.tenant_id,
            bed_id=bed_id,
            data=data.model_dump(exclude_unset=True),
        )
        return BedResponse(
            id=bed.id,
            tenant_id=bed.tenant_id,
            school_id=bed.school_id,
            dormitory_id=bed.dormitory_id,
            bed_number=bed.bed_number,
            bed_type=bed.bed_type,
            status=bed.status.value if hasattr(bed.status, "value") else bed.status,
            is_active=bed.is_active,
            created_at=bed.created_at,
            updated_at=bed.updated_at,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

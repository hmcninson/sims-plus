"""
SIMS Plus - Preschool Supply Endpoints

API routes for per-student supply inventory tracking:
add, list, update metadata, use (decrement), and restock (increment).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.services.preschool import PreschoolService, PreschoolServiceError
from app.schemas.preschool import (
    PreschoolSupplyCreate,
    PreschoolSupplyUpdate,
    PreschoolSupplyResponse,
    SupplyUseRequest,
    SupplyRestockRequest,
    convert_uuid,
)

router = APIRouter()


# =========================
# Student-scoped routes
# =========================


@router.post(
    "/students/{student_id}/supplies",
    response_model=PreschoolSupplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add supply item for a student",
    dependencies=[Depends(require_permissions("preschool.create"))],
)
async def add_supply(
    student_id: UUID,
    data: PreschoolSupplyCreate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Add a new supply item (e.g., diapers, wipes) for a preschool student."""
    service = PreschoolService(db)
    try:
        return await service.add_supply(
            convert_uuid(tenant.tenant_id),
            student_id,
            data,
            school_id=convert_uuid(getattr(tenant, "school_id", None)),
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/students/{student_id}/supplies",
    response_model=list[PreschoolSupplyResponse],
    summary="List supply items for a student",
    dependencies=[Depends(require_permissions("preschool.read"))],
)
async def list_supplies(
    student_id: UUID,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """List all active supply items for a preschool student."""
    service = PreschoolService(db)
    return await service.list_supplies(
        convert_uuid(tenant.tenant_id),
        student_id,
    )


# =========================
# Supply-scoped routes
# =========================


@router.put(
    "/supplies/{supply_id}",
    response_model=PreschoolSupplyResponse,
    summary="Update supply item metadata",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def update_supply(
    supply_id: UUID,
    data: PreschoolSupplyUpdate,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Update supply item name, threshold, or notes."""
    service = PreschoolService(db)
    try:
        return await service.update_supply(
            convert_uuid(tenant.tenant_id),
            supply_id,
            data,
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/supplies/{supply_id}/use",
    response_model=PreschoolSupplyResponse,
    summary="Use (decrement) a supply item",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def use_supply(
    supply_id: UUID,
    data: SupplyUseRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Decrement supply quantity by the given amount (default 1).

    Returns 409 Conflict if there is insufficient stock.
    """
    service = PreschoolService(db)
    try:
        return await service.use_supply(
            convert_uuid(tenant.tenant_id),
            supply_id,
            quantity=data.quantity,
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        if e.code == "insufficient_stock":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/supplies/{supply_id}/restock",
    response_model=PreschoolSupplyResponse,
    summary="Restock a supply item",
    dependencies=[Depends(require_permissions("preschool.update"))],
)
async def restock_supply(
    supply_id: UUID,
    data: SupplyRestockRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
    tenant: RequestTenant,
):
    """Increment supply quantity and record the restock timestamp."""
    service = PreschoolService(db)
    try:
        return await service.restock_supply(
            convert_uuid(tenant.tenant_id),
            supply_id,
            quantity=data.quantity,
        )
    except PreschoolServiceError as e:
        if e.code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

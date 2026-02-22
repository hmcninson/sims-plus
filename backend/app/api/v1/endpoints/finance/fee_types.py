"""
SIMS Plus - Fee Type Endpoints

CRUD endpoints for fee type management.
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.finance import (
    FeeTypeCreate,
    FeeTypeUpdate,
    FeeTypeResponse,
    FeeTypeListResponse,
)
from app.services.finance import FeeTypeService, FinanceAuditService, FinanceServiceError

from ._helpers import get_school_for_tenant

router = APIRouter()


@router.post(
    "/fee-types",
    response_model=FeeTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create fee type",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_fee_type(
    data: FeeTypeCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeTypeResponse:
    """Create a new fee type."""
    try:
        school = await get_school_for_tenant(db, tenant.tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    service = FeeTypeService(db)
    try:
        fee_type = await service.create_fee_type(
            tenant_id=tenant.tenant_id,
            school_id=school.id,
            name=data.name,
            description=data.description,
            category=data.category,
            is_active=data.is_active,
        )
        # Log audit trail for fee type creation
        audit_service = FinanceAuditService(db)
        await audit_service.log_create(
            tenant_id=tenant.tenant_id,
            entity_type="fee_type",
            entity_id=fee_type.id,
            performed_by=UUID(user_id),
            metadata={"name": fee_type.name, "category": fee_type.category},
        )
        return FeeTypeResponse.model_validate(fee_type)
    except FinanceServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get(
    "/fee-types",
    response_model=FeeTypeListResponse,
    summary="List fee types",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_fee_types(
    tenant: RequestTenant,
    db: DatabaseSession,
    search: Optional[str] = Query(None, description="Search by name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> FeeTypeListResponse:
    """List all fee types with optional filtering."""
    service = FeeTypeService(db)
    items, total = await service.list_fee_types(
        tenant_id=tenant.tenant_id,
        search=search,
        category=category,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return FeeTypeListResponse(
        items=[FeeTypeResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/fee-types/search",
    response_model=list[FeeTypeResponse],
    summary="Search fee types",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def search_fee_types(
    tenant: RequestTenant,
    db: DatabaseSession,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
) -> list[FeeTypeResponse]:
    """Quick search for fee types (for autocomplete)."""
    service = FeeTypeService(db)
    items = await service.search_fee_types(
        tenant_id=tenant.tenant_id,
        query=q,
        limit=limit,
    )
    return [FeeTypeResponse.model_validate(item) for item in items]


@router.get(
    "/fee-types/{fee_type_id}",
    response_model=FeeTypeResponse,
    summary="Get fee type",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_fee_type(
    fee_type_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> FeeTypeResponse:
    """Get a fee type by ID."""
    service = FeeTypeService(db)
    fee_type = await service.get_fee_type(tenant.tenant_id, fee_type_id)
    if not fee_type:
        raise HTTPException(status_code=404, detail="Fee type not found")
    return FeeTypeResponse.model_validate(fee_type)


@router.put(
    "/fee-types/{fee_type_id}",
    response_model=FeeTypeResponse,
    summary="Update fee type",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_fee_type(
    fee_type_id: UUID,
    data: FeeTypeUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeTypeResponse:
    """Update a fee type."""
    service = FeeTypeService(db)
    try:
        fee_type = await service.update_fee_type(
            tenant_id=tenant.tenant_id,
            fee_type_id=fee_type_id,
            name=data.name,
            description=data.description,
            category=data.category,
            is_active=data.is_active,
        )
        if not fee_type:
            raise HTTPException(status_code=404, detail="Fee type not found")
        # Log audit trail for fee type update
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="fee_type",
            entity_id=fee_type.id,
            action="update",
            performed_by=UUID(user_id),
            metadata=data.model_dump(exclude_unset=True),
        )
        return FeeTypeResponse.model_validate(fee_type)
    except FinanceServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete(
    "/fee-types/{fee_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete fee type",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_fee_type(
    fee_type_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> None:
    """Delete a fee type."""
    service = FeeTypeService(db)
    if not await service.delete_fee_type(tenant.tenant_id, fee_type_id):
        raise HTTPException(status_code=404, detail="Fee type not found")
    # Log audit trail for fee type deletion
    audit_service = FinanceAuditService(db)
    await audit_service.log(
        tenant_id=tenant.tenant_id,
        entity_type="fee_type",
        entity_id=fee_type_id,
        action="delete",
        performed_by=UUID(user_id),
    )

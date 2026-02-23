"""
SIMS Plus - Fee Structure Endpoints

CRUD endpoints for fee structures and fee items.
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    OptionalSchoolCtx,
    RequestTenant,
    SchoolCtx,
    require_permissions,
)
from app.schemas.finance import (
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureWithItemsResponse,
    FeeStructureListResponse,
    FeeStructureCopy,
    FeeItemCreate,
    FeeItemUpdate,
    FeeItemResponse,
)
from app.services.finance import FeeStructureService, FinanceAuditService, FinanceServiceError

from ._helpers import _build_fee_structure_response

router = APIRouter()


@router.post(
    "/fee-structures",
    response_model=FeeStructureWithItemsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create fee structure",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_fee_structure(
    data: FeeStructureCreate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeStructureWithItemsResponse:
    """Create a new fee structure with items."""
    service = FeeStructureService(db)
    fee_structure = await service.create_fee_structure(
        tenant_id=school_ctx.tenant_id,
        school_id=school_ctx.school_id,
        name=data.name,
        description=data.description,
        academic_year_id=data.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        level=data.level,
        level_category=data.level_category,
        student_type=data.student_type,
        is_active=data.is_active,
        items=[item.model_dump() for item in data.items] if data.items else None,
    )

    # Log audit trail for fee structure creation
    audit_service = FinanceAuditService(db)
    await audit_service.log_create(
        tenant_id=school_ctx.tenant_id,
        entity_type="fee_structure",
        entity_id=fee_structure.id,
        performed_by=UUID(user_id),
        metadata={"name": fee_structure.name},
    )

    return _build_fee_structure_response(fee_structure)


@router.get(
    "/fee-structures",
    response_model=FeeStructureListResponse,
    summary="List fee structures",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_fee_structures(
    tenant: RequestTenant,
    db: DatabaseSession,
    school_ctx: OptionalSchoolCtx,
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> FeeStructureListResponse:
    """List all fee structures with filters."""
    # Chain support: scope to active school when header is present
    school_id = school_ctx.school_id if school_ctx else None
    service = FeeStructureService(db)
    fee_structures, total = await service.list_fee_structures(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return FeeStructureListResponse(
        items=[_build_fee_structure_response(fs) for fs in fee_structures],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/fee-structures/{fee_structure_id}",
    response_model=FeeStructureWithItemsResponse,
    summary="Get fee structure",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_fee_structure(
    fee_structure_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> FeeStructureWithItemsResponse:
    """Get fee structure by ID."""
    service = FeeStructureService(db)
    fee_structure = await service.get_fee_structure(tenant.tenant_id, fee_structure_id)
    if not fee_structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
        )
    return _build_fee_structure_response(fee_structure)


@router.put(
    "/fee-structures/{fee_structure_id}",
    response_model=FeeStructureWithItemsResponse,
    summary="Update fee structure",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_fee_structure(
    fee_structure_id: UUID,
    data: FeeStructureUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeStructureWithItemsResponse:
    """Update fee structure with optional item sync."""
    service = FeeStructureService(db)

    # Extract items from the data
    update_data = data.model_dump(exclude_unset=True)
    items = update_data.pop("items", None)

    # Convert items to dict format if provided
    items_list = None
    if items is not None:
        items_list = [item if isinstance(item, dict) else item.model_dump() for item in items]

    fee_structure = await service.update_fee_structure(
        tenant.tenant_id,
        fee_structure_id,
        items=items_list,
        **update_data,
    )
    if not fee_structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
        )
    # Log audit trail for fee structure update
    audit_service = FinanceAuditService(db)
    await audit_service.log(
        tenant_id=tenant.tenant_id,
        entity_type="fee_structure",
        entity_id=fee_structure.id,
        action="update",
        performed_by=UUID(user_id),
    )
    return _build_fee_structure_response(fee_structure)


@router.delete(
    "/fee-structures/{fee_structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete fee structure",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_fee_structure(
    fee_structure_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> None:
    """Delete fee structure."""
    service = FeeStructureService(db)
    if not await service.delete_fee_structure(tenant.tenant_id, fee_structure_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
        )
    # Log audit trail for fee structure deletion (soft delete)
    audit_service = FinanceAuditService(db)
    await audit_service.log(
        tenant_id=tenant.tenant_id,
        entity_type="fee_structure",
        entity_id=fee_structure_id,
        action="delete",
        performed_by=UUID(user_id),
    )


@router.post(
    "/fee-structures/{fee_structure_id}/items",
    response_model=FeeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add fee item",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def add_fee_item(
    fee_structure_id: UUID,
    data: FeeItemCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeItemResponse:
    """Add item to fee structure."""
    service = FeeStructureService(db)
    fee_item = await service.add_fee_item(
        tenant_id=tenant.tenant_id,
        fee_structure_id=fee_structure_id,
        name=data.name,
        amount=data.amount,
        description=data.description,
        fee_type_id=data.fee_type_id,
        is_optional=data.is_optional,
        sequence=data.sequence,
    )
    # Log audit trail for fee item creation
    audit_service = FinanceAuditService(db)
    await audit_service.log_create(
        tenant_id=tenant.tenant_id,
        entity_type="fee_item",
        entity_id=fee_item.id,
        performed_by=UUID(user_id),
        metadata={"fee_structure_id": str(fee_structure_id), "name": fee_item.name},
    )
    # Build response with fee_type_name
    return FeeItemResponse(
        id=fee_item.id,
        tenant_id=fee_item.tenant_id,
        fee_structure_id=fee_item.fee_structure_id,
        fee_type_id=fee_item.fee_type_id,
        fee_type_name=fee_item.fee_type.name if fee_item.fee_type else None,
        name=fee_item.name,
        description=fee_item.description,
        amount=fee_item.amount,
        is_optional=fee_item.is_optional,
        sequence=fee_item.sequence,
        created_at=fee_item.created_at,
        updated_at=fee_item.updated_at,
    )


@router.put(
    "/fee-structures/{fee_structure_id}/items/{item_id}",
    response_model=FeeItemResponse,
    summary="Update fee item",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_fee_item(
    fee_structure_id: UUID,
    item_id: UUID,
    data: FeeItemUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeItemResponse:
    """Update fee item."""
    service = FeeStructureService(db)
    fee_item = await service.update_fee_item(
        tenant.tenant_id,
        item_id,
        **data.model_dump(exclude_unset=True),
    )
    if not fee_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee item not found",
        )
    # Log audit trail for fee item update
    audit_service = FinanceAuditService(db)
    await audit_service.log(
        tenant_id=tenant.tenant_id,
        entity_type="fee_item",
        entity_id=fee_item.id,
        action="update",
        performed_by=UUID(user_id),
        metadata={"fee_structure_id": str(fee_structure_id)},
    )
    # Build response with fee_type_name
    return FeeItemResponse(
        id=fee_item.id,
        tenant_id=fee_item.tenant_id,
        fee_structure_id=fee_item.fee_structure_id,
        fee_type_id=fee_item.fee_type_id,
        fee_type_name=fee_item.fee_type.name if fee_item.fee_type else None,
        name=fee_item.name,
        description=fee_item.description,
        amount=fee_item.amount,
        is_optional=fee_item.is_optional,
        sequence=fee_item.sequence,
        created_at=fee_item.created_at,
        updated_at=fee_item.updated_at,
    )


@router.delete(
    "/fee-structures/{fee_structure_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete fee item",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_fee_item(
    fee_structure_id: UUID,
    item_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> None:
    """Delete fee item."""
    service = FeeStructureService(db)
    if not await service.delete_fee_item(tenant.tenant_id, item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee item not found",
        )
    # Log audit trail for fee item deletion
    audit_service = FinanceAuditService(db)
    await audit_service.log(
        tenant_id=tenant.tenant_id,
        entity_type="fee_item",
        entity_id=item_id,
        action="delete",
        performed_by=UUID(user_id),
        metadata={"fee_structure_id": str(fee_structure_id)},
    )


@router.post(
    "/fee-structures/{fee_structure_id}/copy",
    response_model=FeeStructureWithItemsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Copy fee structure",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def copy_fee_structure(
    fee_structure_id: UUID,
    data: FeeStructureCopy,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeStructureWithItemsResponse:
    """Copy an existing fee structure with all its items."""
    service = FeeStructureService(db)
    try:
        fee_structure = await service.copy_fee_structure(
            tenant_id=tenant.tenant_id,
            fee_structure_id=fee_structure_id,
            new_name=data.new_name,
            new_academic_year_id=data.new_academic_year_id,
            new_term_id=data.new_term_id,
        )
        if not fee_structure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee structure not found",
            )
        # Log audit trail for fee structure copy (creates new structure)
        audit_service = FinanceAuditService(db)
        await audit_service.log_create(
            tenant_id=tenant.tenant_id,
            entity_type="fee_structure",
            entity_id=fee_structure.id,
            performed_by=UUID(user_id),
            metadata={"copied_from": str(fee_structure_id), "name": fee_structure.name},
        )
        return _build_fee_structure_response(fee_structure)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

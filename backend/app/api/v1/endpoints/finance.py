"""
SIMS Plus - Finance Endpoints

API endpoints for finance management: fee structures, invoices, payments, scholarships.
"""

import math
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.schemas.finance import (
    # Fee Types
    FeeTypeCreate,
    FeeTypeUpdate,
    FeeTypeResponse,
    FeeTypeListResponse,
    # Fee Structures
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureResponse,
    FeeStructureWithItemsResponse,
    FeeStructureListResponse,
    FeeStructureCopy,
    FeeItemCreate,
    FeeItemUpdate,
    FeeItemResponse,
    # Invoices
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceWithDetailsResponse,
    InvoiceListResponse,
    InvoiceBulkGenerate,
    InvoiceBulkResult,
    InvoiceIssue,
    InvoiceCancel,
    InvoiceWriteOff,
    # Payments
    PaymentCreate,
    PaymentResponse,
    PaymentWithDetailsResponse,
    PaymentListResponse,
    PaymentVoid,
    PaymentReceiptResponse,
    # Scholarships
    ScholarshipCreate,
    ScholarshipUpdate,
    ScholarshipResponse,
    ScholarshipWithStatsResponse,
    ScholarshipListResponse,
    ScholarshipAward,
    ScholarshipBulkAward,
    ScholarshipBulkAwardResult,
    ScholarshipRevoke,
    StudentScholarshipResponse,
    StudentScholarshipWithDetailsResponse,
    StudentScholarshipListResponse,
    # Dashboard
    FinanceDashboardResponse,
    FinanceDashboardStats,
    RecentPayment,
    OutstandingByClass,
    # Invoice Email
    InvoiceEmailRequest,
    InvoiceEmailResponse,
    # Missing Invoices
    StudentMissingInvoice,
    StudentsMissingInvoicesResponse,
    # Invoice Sync
    InvoiceSyncRequest,
    InvoiceSyncPreview,
    InvoiceSyncResult,
    # Credit Notes
    CreditNoteCreate,
    CreditNoteUpdate,
    CreditNoteIssue,
    CreditNoteApply,
    CreditNoteRefund,
    CreditNoteCancel,
    CreditNoteResponse,
    CreditNoteWithDetailsResponse,
    CreditNoteListResponse,
    StudentCreditBalance,
)
from app.services.finance import (
    FeeTypeService,
    FeeStructureService,
    InvoiceService,
    PaymentService,
    ScholarshipService,
    FinanceDashboardService,
    CreditNoteService,
    FinanceServiceError,
)

router = APIRouter()


# =========================
# Dashboard Endpoints
# =========================


@router.get(
    "/dashboard",
    response_model=FinanceDashboardResponse,
    summary="Get finance dashboard",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_finance_dashboard(
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
) -> FinanceDashboardResponse:
    """Get finance dashboard with stats and recent activity."""
    service = FinanceDashboardService(db)

    # Get school_id from tenant (assume first school for now)
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    stats = await service.get_dashboard_stats(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )

    recent_payments = await service.get_recent_payments(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        limit=5,
    )

    outstanding = await service.get_outstanding_by_class(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )

    return FinanceDashboardResponse(
        stats=FinanceDashboardStats(**stats),
        recent_payments=[
            RecentPayment(
                id=p.id,
                receipt_number=p.receipt_number,
                student_name=f"{p.student.first_name} {p.student.last_name}" if p.student else "Unknown",
                amount=p.amount,
                payment_method=p.payment_method.value,
                payment_date=p.payment_date,
            )
            for p in recent_payments
        ],
        outstanding_by_class=[
            OutstandingByClass(**item) for item in outstanding
        ],
    )


# =========================
# Fee Type Endpoints
# =========================


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
) -> FeeTypeResponse:
    """Create a new fee type."""
    # Get school_id from tenant
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
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
    db: DatabaseSession,
) -> FeeTypeResponse:
    """Get a fee type by ID."""
    service = FeeTypeService(db)
    fee_type = await service.get_fee_type(fee_type_id)
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
    db: DatabaseSession,
) -> FeeTypeResponse:
    """Update a fee type."""
    service = FeeTypeService(db)
    try:
        fee_type = await service.update_fee_type(
            fee_type_id=fee_type_id,
            name=data.name,
            description=data.description,
            category=data.category,
            is_active=data.is_active,
        )
        if not fee_type:
            raise HTTPException(status_code=404, detail="Fee type not found")
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
    db: DatabaseSession,
) -> None:
    """Delete a fee type."""
    service = FeeTypeService(db)
    if not await service.delete_fee_type(fee_type_id):
        raise HTTPException(status_code=404, detail="Fee type not found")


# =========================
# Fee Structure Endpoints
# =========================


@router.post(
    "/fee-structures",
    response_model=FeeStructureWithItemsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create fee structure",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_fee_structure(
    data: FeeStructureCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> FeeStructureWithItemsResponse:
    """Create a new fee structure with items."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = FeeStructureService(db)
    fee_structure = await service.create_fee_structure(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
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
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> FeeStructureListResponse:
    """List all fee structures with filters."""
    service = FeeStructureService(db)
    fee_structures, total = await service.list_fee_structures(
        tenant_id=tenant.tenant_id,
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
    db: DatabaseSession,
) -> FeeStructureWithItemsResponse:
    """Get fee structure by ID."""
    service = FeeStructureService(db)
    fee_structure = await service.get_fee_structure(fee_structure_id)
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
    db: DatabaseSession,
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
        fee_structure_id,
        items=items_list,
        **update_data,
    )
    if not fee_structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
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
    db: DatabaseSession,
) -> None:
    """Delete fee structure."""
    service = FeeStructureService(db)
    if not await service.delete_fee_structure(fee_structure_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
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
    db: DatabaseSession,
) -> FeeItemResponse:
    """Update fee item."""
    service = FeeStructureService(db)
    fee_item = await service.update_fee_item(
        item_id,
        **data.model_dump(exclude_unset=True),
    )
    if not fee_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee item not found",
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
    db: DatabaseSession,
) -> None:
    """Delete fee item."""
    service = FeeStructureService(db)
    if not await service.delete_fee_item(item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee item not found",
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
) -> FeeStructureWithItemsResponse:
    """Copy an existing fee structure with all its items."""
    service = FeeStructureService(db)
    try:
        fee_structure = await service.copy_fee_structure(
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
        return _build_fee_structure_response(fee_structure)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =========================
# Invoice Endpoints
# =========================


@router.post(
    "/invoices",
    response_model=InvoiceWithDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invoice",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_invoice(
    data: InvoiceCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceWithDetailsResponse:
    """Create a new invoice."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = InvoiceService(db)
    try:
        invoice = await service.create_invoice(
            tenant_id=tenant.tenant_id,
            school_id=school.id,
            student_id=data.student_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            fee_structure_id=data.fee_structure_id,
            due_date=data.due_date,
            discount_amount=data.discount_amount,
            notes=data.notes,
            items=[item.model_dump() for item in data.items] if data.items else None,
            created_by=UUID(user_id),
        )
        # Reload with details
        invoice = await service.get_invoice(invoice.id)
        return _build_invoice_response(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_invoices(
    tenant: RequestTenant,
    db: DatabaseSession,
    student_id: Optional[UUID] = Query(None),
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    invoice_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    """List all invoices with filters and search."""
    service = InvoiceService(db)
    invoices, total = await service.list_invoices(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        status=invoice_status,
        search=search,
        page=page,
        page_size=page_size,
    )

    return InvoiceListResponse(
        items=[_build_invoice_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


# --- Specific invoice routes (must come before {invoice_id} routes) ---


@router.post(
    "/invoices/bulk-generate",
    response_model=InvoiceBulkResult,
    summary="Bulk generate invoices",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def bulk_generate_invoices(
    data: InvoiceBulkGenerate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceBulkResult:
    """Bulk generate invoices for students."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = InvoiceService(db)
    result = await service.bulk_generate_invoices(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        fee_structure_id=data.fee_structure_id,
        academic_year_id=data.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        section_id=data.section_id,
        due_date=data.due_date,
        student_ids=data.student_ids,
        created_by=UUID(user_id),
        issue_immediately=data.issue_immediately,
    )
    return InvoiceBulkResult(**result)


@router.get(
    "/invoices/sync-preview",
    response_model=InvoiceSyncPreview,
    summary="Preview invoice sync with fee structure",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_invoice_sync_preview(
    tenant: RequestTenant,
    db: DatabaseSession,
    fee_structure_id: UUID = Query(..., description="Fee structure ID"),
    academic_year_id: UUID = Query(..., description="Academic year ID"),
    term_id: UUID = Query(..., description="Term ID"),
) -> InvoiceSyncPreview:
    """
    Get preview of how many invoices would be affected by syncing with fee structure.

    Returns counts of:
    - Draft invoices (can be synced)
    - Issued/Partial/Paid invoices (cannot be synced)
    - New fee structure total amount
    """
    service = InvoiceService(db)
    result = await service.get_invoices_sync_preview(
        tenant_id=tenant.tenant_id,
        fee_structure_id=fee_structure_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )
    return InvoiceSyncPreview(**result)


@router.post(
    "/invoices/sync",
    response_model=InvoiceSyncResult,
    summary="Sync draft invoices with fee structure",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def sync_invoices_with_fee_structure(
    data: InvoiceSyncRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> InvoiceSyncResult:
    """
    Sync draft invoices with the current fee structure.

    This will:
    - Update all DRAFT invoices to match the current fee structure items and amounts
    - Recalculate totals including scholarship discounts
    - Skip issued, partial, and paid invoices (they are not modified)

    Use this after updating a fee structure to apply changes to existing draft invoices.
    """
    service = InvoiceService(db)
    result = await service.sync_invoices_with_fee_structure(
        tenant_id=tenant.tenant_id,
        fee_structure_id=data.fee_structure_id,
        academic_year_id=data.academic_year_id,
        term_id=data.term_id,
    )
    return InvoiceSyncResult(**result)


@router.get(
    "/invoices/missing",
    response_model=StudentsMissingInvoicesResponse,
    summary="Get students missing invoices",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_students_missing_invoices(
    tenant: RequestTenant,
    db: DatabaseSession,
    fee_structure_id: UUID = Query(..., description="Fee structure to check against"),
    academic_year_id: UUID = Query(..., description="Academic year"),
    term_id: UUID = Query(..., description="Term"),
    class_id: Optional[UUID] = Query(None, description="Filter by specific class"),
    section_id: Optional[UUID] = Query(None, description="Filter by specific section"),
) -> StudentsMissingInvoicesResponse:
    """
    Get students who match the fee structure criteria but don't have
    an invoice for the specified academic year and term.

    Useful for finding late enrollees or students who were missed during bulk generation.
    """
    from sqlalchemy import select
    from app.models.finance import FeeStructure
    from app.models.academic import AcademicYear, Term, Class, ClassSection

    # Get fee structure name
    fee_structure_result = await db.execute(
        select(FeeStructure).where(FeeStructure.id == fee_structure_id)
    )
    fee_structure = fee_structure_result.scalar_one_or_none()
    if not fee_structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
        )

    # Get academic year name
    year_result = await db.execute(
        select(AcademicYear).where(AcademicYear.id == academic_year_id)
    )
    academic_year = year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found",
        )

    # Get term name
    term_result = await db.execute(
        select(Term).where(Term.id == term_id)
    )
    term = term_result.scalar_one_or_none()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = InvoiceService(db)
    students = await service.get_students_missing_invoices(
        tenant_id=tenant.tenant_id,
        fee_structure_id=fee_structure_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
    )

    # Build response with class/section names
    student_items = []
    for student in students:
        class_name = None
        section_name = None

        if student.class_id:
            class_result = await db.execute(
                select(Class).where(Class.id == student.class_id)
            )
            cls = class_result.scalar_one_or_none()
            if cls:
                class_name = cls.name

        if student.section_id:
            section_result = await db.execute(
                select(ClassSection).where(ClassSection.id == student.section_id)
            )
            section = section_result.scalar_one_or_none()
            if section:
                section_name = section.name

        student_items.append(
            StudentMissingInvoice(
                id=student.id,
                student_id=student.student_id,
                first_name=student.first_name,
                middle_name=student.middle_name,
                last_name=student.last_name,
                class_id=student.class_id,
                class_name=class_name,
                section_id=student.section_id,
                section_name=section_name,
            )
        )

    return StudentsMissingInvoicesResponse(
        students=student_items,
        total=len(student_items),
        fee_structure_name=fee_structure.name,
        academic_year_name=academic_year.name,
        term_name=term.name,
    )


# --- Parameterized invoice routes ---


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceWithDetailsResponse,
    summary="Get invoice",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_invoice(
    invoice_id: UUID,
    db: DatabaseSession,
) -> InvoiceWithDetailsResponse:
    """Get invoice by ID."""
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return _build_invoice_response(invoice)


@router.put(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    db: DatabaseSession,
) -> InvoiceResponse:
    """Update invoice (draft only)."""
    service = InvoiceService(db)
    try:
        invoice = await service.update_invoice(
            invoice_id,
            **data.model_dump(exclude_unset=True),
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete invoice",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_invoice(
    invoice_id: UUID,
    db: DatabaseSession,
) -> None:
    """Delete invoice (draft only)."""
    service = InvoiceService(db)
    try:
        if not await service.delete_invoice(invoice_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/invoices/{invoice_id}/issue",
    response_model=InvoiceResponse,
    summary="Issue invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def issue_invoice(
    invoice_id: UUID,
    data: InvoiceIssue,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """Issue a draft invoice."""
    service = InvoiceService(db)
    try:
        invoice = await service.issue_invoice(
            invoice_id=invoice_id,
            issued_by=UUID(user_id),
            issue_date=data.issue_date,
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def cancel_invoice(
    invoice_id: UUID,
    data: InvoiceCancel,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """Cancel an invoice."""
    service = InvoiceService(db)
    try:
        invoice = await service.cancel_invoice(
            invoice_id=invoice_id,
            cancelled_by=UUID(user_id),
            reason=data.reason,
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/invoices/{invoice_id}/write-off",
    response_model=InvoiceResponse,
    summary="Write off invoice",
    description="Write off an overdue invoice as uncollectible. This is a terminal state.",
    dependencies=[Depends(require_permissions("finance.delete"))],  # Higher permission required
)
async def write_off_invoice(
    invoice_id: UUID,
    data: InvoiceWriteOff,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """
    Write off an overdue invoice as uncollectible.

    Only OVERDUE invoices can be written off. This is a terminal state -
    the invoice cannot be recovered after write-off.
    """
    service = InvoiceService(db)
    try:
        invoice = await service.write_off_invoice(
            invoice_id=invoice_id,
            written_off_by=UUID(user_id),
            reason=data.reason,
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/invoices/{invoice_id}/pdf",
    summary="Download invoice PDF",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def download_invoice_pdf(
    invoice_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> Response:
    """Download invoice as PDF."""
    from app.services.pdf import PDFService

    try:
        pdf_bytes, filename = await PDFService.generate_invoice_pdf(
            db=db,
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/invoices/{invoice_id}/email",
    response_model=InvoiceEmailResponse,
    summary="Send invoice via email",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def email_invoice(
    invoice_id: UUID,
    data: InvoiceEmailRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> InvoiceEmailResponse:
    """Send invoice via email with PDF attachment."""
    from sqlalchemy import select, and_
    from sqlalchemy.orm import joinedload, selectinload
    from app.services.pdf import PDFService
    from app.services.email import email_service
    from app.models.school import School
    from app.models.student import Student, Guardian, StudentGuardian
    from app.models.finance import Invoice

    # Fetch the invoice with related data
    invoice_result = await db.execute(
        select(Invoice)
        .where(
            and_(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant.tenant_id,
                Invoice.deleted_at.is_(None),
            )
        )
        .options(
            joinedload(Invoice.student),
            joinedload(Invoice.academic_year),
            joinedload(Invoice.term),
        )
    )
    invoice = invoice_result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    student = invoice.student
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Fetch school
    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id)
    )
    school = school_result.scalar_one_or_none()
    school_name = school.name if school else "School"

    # Get recipient name - use provided name or try to get guardian name
    recipient_name = data.recipient_name
    if not recipient_name:
        # Try to get primary guardian
        guardian_link_result = await db.execute(
            select(StudentGuardian)
            .where(
                and_(
                    StudentGuardian.student_id == student.id,
                    StudentGuardian.is_primary == True,
                )
            )
        )
        guardian_link = guardian_link_result.scalar_one_or_none()
        if guardian_link:
            guardian_result = await db.execute(
                select(Guardian).where(Guardian.id == guardian_link.guardian_id)
            )
            guardian = guardian_result.scalar_one_or_none()
            if guardian:
                recipient_name = f"{guardian.first_name} {guardian.last_name}"

        if not recipient_name:
            recipient_name = "Parent/Guardian"

    # Generate PDF
    try:
        pdf_bytes, pdf_filename = await PDFService.generate_invoice_pdf(
            db=db,
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}",
        )

    # Format student name
    student_name = f"{student.first_name}"
    if student.middle_name:
        student_name += f" {student.middle_name}"
    student_name += f" {student.last_name}"

    # Format due date
    due_date = invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else None

    # Calculate balance
    balance_due = float(invoice.total_amount) - float(invoice.amount_paid)

    # Send email
    success = await email_service.send_invoice_email(
        to_email=data.email,
        recipient_name=recipient_name,
        student_name=student_name,
        invoice_number=invoice.invoice_number,
        total_amount=float(invoice.total_amount),
        balance_due=balance_due,
        currency=invoice.currency or "GHS",
        due_date=due_date,
        school_name=school_name,
        pdf_data=pdf_bytes,
        pdf_filename=pdf_filename,
        cc_emails=data.cc_emails,
    )

    cc_info = f" (CC: {', '.join(data.cc_emails)})" if data.cc_emails else ""
    if success:
        return InvoiceEmailResponse(
            success=True,
            message=f"Invoice sent successfully to {data.email}{cc_info}",
            email=data.email,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Please check email configuration.",
        )


@router.post(
    "/invoices/update-overdue",
    summary="Update overdue invoices",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_overdue_invoices(
    tenant: RequestTenant,
    db: DatabaseSession,
) -> dict:
    """
    Update status of invoices that have passed their due date.

    Marks ISSUED or PARTIAL invoices as OVERDUE if their due date has passed.
    This endpoint can be called manually or scheduled via a cron job/Celery task.

    Returns count of invoices updated.
    """
    service = InvoiceService(db)
    result = await service.update_overdue_invoices(tenant.tenant_id)
    return {
        "message": f"Updated {result['updated']} invoices to OVERDUE status",
        "updated": result["updated"],
        "checked": result["checked"],
    }


@router.get(
    "/students/{student_id}/invoices",
    response_model=InvoiceListResponse,
    summary="Get student invoices",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_invoices(
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    """Get all invoices for a student."""
    service = InvoiceService(db)
    invoices, total = await service.list_invoices(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        page=page,
        page_size=page_size,
    )

    return InvoiceListResponse(
        items=[_build_invoice_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


# =========================
# Payment Endpoints
# =========================


@router.post(
    "/payments",
    response_model=PaymentWithDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record payment",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def record_payment(
    data: PaymentCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> PaymentWithDetailsResponse:
    """Record a payment."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = PaymentService(db)
    payment = await service.record_payment(
        tenant_id=tenant.tenant_id,
        school_id=school.id,
        student_id=data.student_id,
        amount=data.amount,
        payment_method=data.payment_method,
        invoice_id=data.invoice_id,
        payment_date=data.payment_date,
        payer_name=data.payer_name,
        payer_phone=data.payer_phone,
        payer_email=data.payer_email,
        notes=data.notes,
        momo_phone=data.momo_phone,
        momo_transaction_id=data.momo_transaction_id,
        bank_name=data.bank_name,
        bank_reference=data.bank_reference,
        cheque_number=data.cheque_number,
        recorded_by=UUID(user_id),
    )
    # Reload with details
    payment = await service.get_payment(payment.id)
    return _build_payment_response(payment)


@router.get(
    "/payments",
    response_model=PaymentListResponse,
    summary="List payments",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_payments(
    tenant: RequestTenant,
    db: DatabaseSession,
    student_id: Optional[UUID] = Query(None),
    invoice_id: Optional[UUID] = Query(None),
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    payment_status: Optional[str] = Query(None, alias="status"),
    payment_method: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaymentListResponse:
    """List all payments with filters."""
    service = PaymentService(db)
    payments, total = await service.list_payments(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        invoice_id=invoice_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        status=payment_status,
        payment_method=payment_method,
        search=search,
        start_date=date_from,
        end_date=date_to,
        page=page,
        page_size=page_size,
    )

    return PaymentListResponse(
        items=[_build_payment_response(p) for p in payments],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentWithDetailsResponse,
    summary="Get payment",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_payment(
    payment_id: UUID,
    db: DatabaseSession,
) -> PaymentWithDetailsResponse:
    """Get payment by ID."""
    service = PaymentService(db)
    payment = await service.get_payment(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return _build_payment_response(payment)


@router.post(
    "/payments/{payment_id}/void",
    response_model=PaymentResponse,
    summary="Void payment",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def void_payment(
    payment_id: UUID,
    data: PaymentVoid,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> PaymentResponse:
    """Void a payment."""
    service = PaymentService(db)
    try:
        payment = await service.void_payment(
            payment_id=payment_id,
            voided_by=UUID(user_id),
            reason=data.reason,
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        return PaymentResponse.model_validate(payment)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/students/{student_id}/payments",
    response_model=PaymentListResponse,
    summary="Get student payments",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_payments(
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaymentListResponse:
    """Get all payments for a student."""
    service = PaymentService(db)
    payments, total = await service.list_payments(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        page=page,
        page_size=page_size,
    )

    return PaymentListResponse(
        items=[_build_payment_response(p) for p in payments],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


def amount_to_words(amount: float, currency: str = "Ghana Cedis") -> str:
    """Convert numeric amount to words."""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_less_than_thousand(n: int) -> str:
        if n == 0:
            return ""
        elif n < 20:
            return ones[n]
        elif n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
        else:
            return ones[n // 100] + " Hundred" + (" and " + convert_less_than_thousand(n % 100) if n % 100 != 0 else "")

    def convert(n: int) -> str:
        if n == 0:
            return "Zero"

        result = ""
        if n >= 1000000:
            result += convert_less_than_thousand(n // 1000000) + " Million "
            n %= 1000000
        if n >= 1000:
            result += convert_less_than_thousand(n // 1000) + " Thousand "
            n %= 1000
        if n > 0:
            if result:
                result += "and "
            result += convert_less_than_thousand(n)

        return result.strip()

    # Split into cedis and pesewas
    cedis = int(amount)
    pesewas = round((amount - cedis) * 100)

    result = convert(cedis) + f" {currency}"
    if pesewas > 0:
        result += " and " + convert(pesewas) + " Pesewas"
    result += " Only"

    return result


@router.get(
    "/payments/{payment_id}/receipt",
    response_model=PaymentReceiptResponse,
    summary="Get payment receipt",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_payment_receipt(
    payment_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> PaymentReceiptResponse:
    """Get payment receipt details for printing."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = PaymentService(db)
    payment = await service.get_payment(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Build receipt data
    return PaymentReceiptResponse(
        receipt_number=payment.receipt_number,
        payment_date=payment.payment_date,
        amount=payment.amount,
        amount_in_words=amount_to_words(float(payment.amount)),
        currency=payment.currency,
        payment_method=payment.payment_method.value,
        status=payment.status.value,
        student_name=f"{payment.student.first_name} {payment.student.last_name}" if payment.student else "Unknown",
        student_id_number=payment.student.student_id if payment.student else "",
        class_name=payment.student.class_.name if payment.student and payment.student.class_ else None,
        payer_name=payment.payer_name,
        payer_phone=payment.payer_phone,
        invoice_number=payment.invoice.invoice_number if payment.invoice else None,
        momo_transaction_id=payment.momo_transaction_id,
        notes=payment.notes,
        school_name=school.name,
        school_address=school.address,
        school_phone=school.phone,
        school_email=school.email,
        school_logo_url=school.logo_url,
        recorded_by_name=f"{payment.recorded_by_user.first_name} {payment.recorded_by_user.last_name}" if payment.recorded_by_user else None,
    )


# =========================
# Scholarship Endpoints
# =========================


@router.post(
    "/scholarships",
    response_model=ScholarshipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create scholarship",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_scholarship(
    data: ScholarshipCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ScholarshipResponse:
    """Create a new scholarship."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = ScholarshipService(db)
    try:
        scholarship = await service.create_scholarship(
            tenant_id=tenant.tenant_id,
            school_id=school.id,
            name=data.name,
            code=data.code,
            description=data.description,
            scholarship_type=data.scholarship_type,
            coverage_type=data.coverage_type,
            coverage_value=data.coverage_value,
            applicable_fees=data.applicable_fees,
            max_recipients=data.max_recipients,
            academic_year_id=data.academic_year_id,
            eligibility_criteria=data.eligibility_criteria,
            is_active=data.is_active,
            created_by=UUID(user_id),
        )
        return ScholarshipResponse(
            id=scholarship.id,
            tenant_id=scholarship.tenant_id,
            school_id=scholarship.school_id,
            name=scholarship.name,
            code=scholarship.code,
            description=scholarship.description,
            scholarship_type=scholarship.scholarship_type.value,
            coverage_type=scholarship.coverage_type.value,
            coverage_value=scholarship.coverage_value,
            applicable_fees=scholarship.applicable_fees,
            max_recipients=scholarship.max_recipients,
            academic_year_id=scholarship.academic_year_id,
            eligibility_criteria=scholarship.eligibility_criteria,
            is_active=scholarship.is_active,
            created_at=scholarship.created_at,
            updated_at=scholarship.updated_at,
        )
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/scholarships",
    response_model=ScholarshipListResponse,
    summary="List scholarships",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_scholarships(
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    scholarship_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ScholarshipListResponse:
    """List all scholarships with filters."""
    service = ScholarshipService(db)
    scholarships, total = await service.list_scholarships(
        tenant_id=tenant.tenant_id,
        academic_year_id=academic_year_id,
        scholarship_type=scholarship_type,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return ScholarshipListResponse(
        items=[_build_scholarship_response(s) for s in scholarships],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/scholarships/{scholarship_id}",
    response_model=ScholarshipWithStatsResponse,
    summary="Get scholarship",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_scholarship(
    scholarship_id: UUID,
    db: DatabaseSession,
) -> ScholarshipWithStatsResponse:
    """Get scholarship by ID."""
    service = ScholarshipService(db)
    scholarship = await service.get_scholarship(scholarship_id)
    if not scholarship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found",
        )
    return _build_scholarship_response(scholarship)


@router.put(
    "/scholarships/{scholarship_id}",
    response_model=ScholarshipResponse,
    summary="Update scholarship",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_scholarship(
    scholarship_id: UUID,
    data: ScholarshipUpdate,
    db: DatabaseSession,
) -> ScholarshipResponse:
    """Update scholarship."""
    service = ScholarshipService(db)
    try:
        scholarship = await service.update_scholarship(
            scholarship_id,
            **data.model_dump(exclude_unset=True),
        )
        if not scholarship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scholarship not found",
            )
        return ScholarshipResponse(
            id=scholarship.id,
            tenant_id=scholarship.tenant_id,
            school_id=scholarship.school_id,
            name=scholarship.name,
            code=scholarship.code,
            description=scholarship.description,
            scholarship_type=scholarship.scholarship_type.value,
            coverage_type=scholarship.coverage_type.value,
            coverage_value=scholarship.coverage_value,
            applicable_fees=scholarship.applicable_fees,
            max_recipients=scholarship.max_recipients,
            academic_year_id=scholarship.academic_year_id,
            eligibility_criteria=scholarship.eligibility_criteria,
            is_active=scholarship.is_active,
            created_at=scholarship.created_at,
            updated_at=scholarship.updated_at,
        )
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/scholarships/{scholarship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete scholarship",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_scholarship(
    scholarship_id: UUID,
    db: DatabaseSession,
) -> None:
    """Delete scholarship."""
    service = ScholarshipService(db)
    if not await service.delete_scholarship(scholarship_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found",
        )


@router.post(
    "/scholarships/{scholarship_id}/award",
    response_model=StudentScholarshipWithDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Award scholarship",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def award_scholarship(
    scholarship_id: UUID,
    data: ScholarshipAward,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> StudentScholarshipWithDetailsResponse:
    """Award scholarship to a student."""
    # Get current academic year
    from sqlalchemy import select
    from app.models.academic import AcademicYear

    year_result = await db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.tenant_id == tenant.tenant_id,
            AcademicYear.is_current == True,
        )
        .limit(1)
    )
    academic_year = year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current academic year found",
        )

    service = ScholarshipService(db)
    try:
        student_scholarship = await service.award_scholarship(
            tenant_id=tenant.tenant_id,
            scholarship_id=scholarship_id,
            student_id=data.student_id,
            academic_year_id=academic_year.id,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            coverage_override=data.coverage_override,
            notes=data.notes,
            awarded_by=UUID(user_id),
            # Enhanced award settings
            justification=data.justification,
            renewal_type=data.renewal_type,
            is_provisional=data.is_provisional,
            provisional_conditions=data.provisional_conditions,
            # Reinstatement
            reinstated_from=data.reinstated_from,
        )
        return _build_student_scholarship_response(student_scholarship)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/scholarships/{scholarship_id}/award-bulk",
    response_model=ScholarshipBulkAwardResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk award scholarship",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def bulk_award_scholarship(
    scholarship_id: UUID,
    data: ScholarshipBulkAward,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ScholarshipBulkAwardResult:
    """Award scholarship to multiple students at once."""
    # Get current academic year
    from sqlalchemy import select
    from app.models.academic import AcademicYear

    year_result = await db.execute(
        select(AcademicYear)
        .where(
            AcademicYear.tenant_id == tenant.tenant_id,
            AcademicYear.is_current == True,
        )
        .limit(1)
    )
    academic_year = year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current academic year found",
        )

    service = ScholarshipService(db)
    try:
        result = await service.bulk_award_scholarship(
            tenant_id=tenant.tenant_id,
            scholarship_id=scholarship_id,
            student_ids=data.student_ids,
            academic_year_id=academic_year.id,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            coverage_override=data.coverage_override,
            notes=data.notes,
            awarded_by=UUID(user_id),
            # Enhanced award settings
            justification=data.justification,
            renewal_type=data.renewal_type,
            is_provisional=data.is_provisional,
            provisional_conditions=data.provisional_conditions,
        )
        return ScholarshipBulkAwardResult(**result)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/scholarships/{scholarship_id}/recipients/{student_scholarship_id}/revoke",
    response_model=StudentScholarshipResponse,
    summary="Revoke scholarship",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def revoke_scholarship(
    scholarship_id: UUID,
    student_scholarship_id: UUID,
    data: ScholarshipRevoke,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> StudentScholarshipResponse:
    """Revoke a student's scholarship."""
    service = ScholarshipService(db)
    try:
        student_scholarship = await service.revoke_scholarship(
            student_scholarship_id=student_scholarship_id,
            revoked_by=UUID(user_id),
            reason=data.reason,
        )
        if not student_scholarship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student scholarship not found",
            )
        return StudentScholarshipResponse.model_validate(student_scholarship)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/scholarships/{scholarship_id}/recipients",
    response_model=StudentScholarshipListResponse,
    summary="Get scholarship recipients",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_scholarship_recipients(
    scholarship_id: UUID,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    recipient_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StudentScholarshipListResponse:
    """Get all recipients of a scholarship."""
    service = ScholarshipService(db)
    recipients, total = await service.get_scholarship_recipients(
        scholarship_id=scholarship_id,
        academic_year_id=academic_year_id,
        status=recipient_status,
        page=page,
        page_size=page_size,
    )

    return StudentScholarshipListResponse(
        items=[_build_student_scholarship_response(r) for r in recipients],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/students/{student_id}/scholarships",
    response_model=StudentScholarshipListResponse,
    summary="Get student scholarships",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_scholarships(
    student_id: UUID,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    scholarship_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StudentScholarshipListResponse:
    """Get all scholarships for a student."""
    service = ScholarshipService(db)
    scholarships = await service.get_student_scholarships(
        student_id=student_id,
        academic_year_id=academic_year_id,
        status=scholarship_status,
    )

    # Manual pagination since service returns all
    total = len(scholarships)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = scholarships[start:end]

    return StudentScholarshipListResponse(
        items=[_build_student_scholarship_response(s) for s in page_items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


# =========================
# Helper Functions
# =========================


def _build_fee_structure_response(fs) -> FeeStructureWithItemsResponse:
    """Build fee structure response with items."""
    total = sum(item.amount for item in fs.items if not item.is_optional)

    # Build fee item responses with fee_type_name
    fee_items = []
    for item in fs.items:
        fee_item_response = FeeItemResponse(
            id=item.id,
            tenant_id=item.tenant_id,
            fee_structure_id=item.fee_structure_id,
            fee_type_id=item.fee_type_id,
            fee_type_name=item.fee_type.name if item.fee_type else None,
            name=item.name,
            description=item.description,
            amount=item.amount,
            is_optional=item.is_optional,
            sequence=item.sequence,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        fee_items.append(fee_item_response)

    return FeeStructureWithItemsResponse(
        id=fs.id,
        tenant_id=fs.tenant_id,
        school_id=fs.school_id,
        name=fs.name,
        description=fs.description,
        academic_year_id=fs.academic_year_id,
        term_id=fs.term_id,
        class_id=fs.class_id,
        level=fs.level,
        level_category=fs.level_category,
        student_type=fs.student_type,
        is_active=fs.is_active,
        created_at=fs.created_at,
        updated_at=fs.updated_at,
        items=fee_items,
        total_amount=total,
        academic_year_name=fs.academic_year.name if fs.academic_year else None,
        term_name=fs.term.name if fs.term else None,
        class_name=fs.class_.name if fs.class_ else None,
    )


def _build_invoice_response_basic(inv) -> InvoiceResponse:
    """Build basic invoice response."""
    return InvoiceResponse(
        id=inv.id,
        tenant_id=inv.tenant_id,
        school_id=inv.school_id,
        invoice_number=inv.invoice_number,
        student_id=inv.student_id,
        fee_structure_id=inv.fee_structure_id,
        academic_year_id=inv.academic_year_id,
        term_id=inv.term_id,
        subtotal=inv.subtotal,
        discount_amount=inv.discount_amount,
        scholarship_discount=inv.scholarship_discount,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        amount_paid=inv.amount_paid,
        balance=inv.balance,
        status=inv.status.value,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        currency=inv.currency,
        notes=inv.notes,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


def _is_relationship_loaded(obj, attr_name: str) -> bool:
    """Check if a SQLAlchemy relationship is loaded without triggering lazy load."""
    from sqlalchemy import inspect
    insp = inspect(obj)
    return attr_name in insp.dict


def _build_invoice_response(inv) -> InvoiceWithDetailsResponse:
    """Build invoice response with details."""
    from app.schemas.finance import InvoiceItemResponse, InvoiceScholarshipItemResponse, PaymentResponse

    # Build payment responses for completed payments (only if loaded)
    payments = []
    # Only access payments if the relationship was eagerly loaded
    if _is_relationship_loaded(inv, 'payments'):
        for p in inv.payments:
            if not p.is_voided:  # Only include non-voided payments
                payments.append(PaymentResponse(
                    id=p.id,
                    tenant_id=p.tenant_id,
                    school_id=p.school_id,
                    receipt_number=p.receipt_number,
                    invoice_id=p.invoice_id,
                    student_id=p.student_id,
                    amount=p.amount,
                    currency=p.currency,
                    payment_method=p.payment_method.value,
                    momo_phone=p.momo_phone,
                    momo_transaction_id=p.momo_transaction_id,
                    momo_provider=p.momo_provider,
                    bank_name=p.bank_name,
                    bank_reference=p.bank_reference,
                    cheque_number=p.cheque_number,
                    payer_name=p.payer_name,
                    payer_phone=p.payer_phone,
                    payer_email=p.payer_email,
                    status=p.status.value,
                    payment_date=p.payment_date,
                    notes=p.notes,
                    is_voided=p.is_voided,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                ))

    # Build scholarship item responses (only if loaded)
    scholarship_items = []
    if _is_relationship_loaded(inv, 'scholarship_items'):
        for si in inv.scholarship_items:
            scholarship_items.append(InvoiceScholarshipItemResponse(
                id=si.id,
                tenant_id=si.tenant_id,
                invoice_id=si.invoice_id,
                student_scholarship_id=si.student_scholarship_id,
                scholarship_id=si.scholarship_id,
                scholarship_name=si.scholarship_name,
                scholarship_code=si.scholarship_code,
                coverage_type=si.coverage_type,
                coverage_value=si.coverage_value,
                calculated_amount=si.calculated_amount,
                applicable_subtotal=si.applicable_subtotal,
                created_at=si.created_at,
            ))

    return InvoiceWithDetailsResponse(
        id=inv.id,
        tenant_id=inv.tenant_id,
        school_id=inv.school_id,
        invoice_number=inv.invoice_number,
        student_id=inv.student_id,
        fee_structure_id=inv.fee_structure_id,
        academic_year_id=inv.academic_year_id,
        term_id=inv.term_id,
        subtotal=inv.subtotal,
        discount_amount=inv.discount_amount,
        scholarship_discount=inv.scholarship_discount,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        amount_paid=inv.amount_paid,
        balance=inv.balance,
        status=inv.status.value,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        currency=inv.currency,
        notes=inv.notes,
        # Adjustment tracking
        adjustment_for_invoice_id=inv.adjustment_for_invoice_id if hasattr(inv, 'adjustment_for_invoice_id') else None,
        adjustment_type=inv.adjustment_type if hasattr(inv, 'adjustment_type') else None,
        adjustment_reason=inv.adjustment_reason if hasattr(inv, 'adjustment_reason') else None,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        student_name=f"{inv.student.first_name} {inv.student.last_name}" if inv.student else "Unknown",
        student_id_number=inv.student.student_id if inv.student else "",
        class_name=inv.student.class_.name if inv.student and inv.student.class_ else None,
        academic_year_name=inv.academic_year.name if inv.academic_year else "",
        term_name=inv.term.name if inv.term else "",
        items=[InvoiceItemResponse.model_validate(item) for item in inv.items] if hasattr(inv, 'items') else [],
        scholarship_items=scholarship_items,
        payments=payments,
    )


def _build_payment_response(p) -> PaymentWithDetailsResponse:
    """Build payment response with details."""
    return PaymentWithDetailsResponse(
        id=p.id,
        tenant_id=p.tenant_id,
        school_id=p.school_id,
        receipt_number=p.receipt_number,
        invoice_id=p.invoice_id,
        student_id=p.student_id,
        amount=p.amount,
        currency=p.currency,
        payment_method=p.payment_method.value,
        momo_phone=p.momo_phone,
        momo_transaction_id=p.momo_transaction_id,
        momo_provider=p.momo_provider,
        bank_name=p.bank_name,
        bank_reference=p.bank_reference,
        cheque_number=p.cheque_number,
        payer_name=p.payer_name,
        payer_phone=p.payer_phone,
        payer_email=p.payer_email,
        status=p.status.value,
        payment_date=p.payment_date,
        notes=p.notes,
        is_voided=p.is_voided,
        created_at=p.created_at,
        updated_at=p.updated_at,
        student_name=f"{p.student.first_name} {p.student.last_name}" if p.student else "Unknown",
        student_id_number=p.student.student_id if p.student else "",
        invoice_number=p.invoice.invoice_number if p.invoice else None,
        recorded_by_name=f"{p.recorded_by_user.first_name} {p.recorded_by_user.last_name}" if p.recorded_by_user else None,
    )


def _build_scholarship_response(s) -> ScholarshipWithStatsResponse:
    """Build scholarship response with stats."""
    from app.models.finance import ScholarshipStatus

    active_count = len([r for r in s.recipients if r.status == ScholarshipStatus.ACTIVE]) if hasattr(s, 'recipients') else 0
    total_count = len(s.recipients) if hasattr(s, 'recipients') else 0

    return ScholarshipWithStatsResponse(
        id=s.id,
        tenant_id=s.tenant_id,
        school_id=s.school_id,
        name=s.name,
        code=s.code,
        description=s.description,
        scholarship_type=s.scholarship_type.value,
        coverage_type=s.coverage_type.value,
        coverage_value=s.coverage_value,
        applicable_fees=s.applicable_fees,
        max_recipients=s.max_recipients,
        academic_year_id=s.academic_year_id,
        eligibility_criteria=s.eligibility_criteria,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
        recipients_count=total_count,
        active_recipients_count=active_count,
        academic_year_name=s.academic_year.name if s.academic_year else None,
    )


def _build_student_scholarship_response(ss) -> StudentScholarshipWithDetailsResponse:
    """Build student scholarship response with details."""
    return StudentScholarshipWithDetailsResponse(
        id=ss.id,
        tenant_id=ss.tenant_id,
        scholarship_id=ss.scholarship_id,
        student_id=ss.student_id,
        academic_year_id=ss.academic_year_id,
        awarded_by=ss.awarded_by,
        awarded_at=ss.awarded_at,
        status=ss.status.value,
        effective_from=ss.effective_from,
        effective_to=ss.effective_to,
        coverage_override=ss.coverage_override,
        notes=ss.notes,
        # Enhanced award settings
        justification=ss.justification,
        renewal_type=ss.renewal_type or "one_time",
        is_provisional=ss.is_provisional or False,
        provisional_conditions=ss.provisional_conditions,
        # Revocation info
        revoked_at=ss.revoked_at,
        revoked_by=ss.revoked_by,
        revoke_reason=ss.revoke_reason,
        # Reinstatement tracking
        reinstated_from=ss.reinstated_from,
        created_at=ss.created_at,
        updated_at=ss.updated_at,
        scholarship_name=ss.scholarship.name if ss.scholarship else "",
        scholarship_code=ss.scholarship.code if ss.scholarship else "",
        scholarship_type=ss.scholarship.scholarship_type.value if ss.scholarship else "",
        coverage_type=ss.scholarship.coverage_type.value if ss.scholarship else "",
        coverage_value=ss.scholarship.coverage_value if ss.scholarship else 0,
        student_name=f"{ss.student.first_name} {ss.student.last_name}" if ss.student else "Unknown",
        student_id_number=ss.student.student_id if ss.student else "",
        academic_year_name=ss.academic_year.name if ss.academic_year else "",
        awarded_by_name=f"{ss.awarded_by_user.first_name} {ss.awarded_by_user.last_name}" if ss.awarded_by_user else None,
    )


def _build_credit_note_response(cn) -> CreditNoteWithDetailsResponse:
    """Build credit note response with details."""
    # Calculate remaining amount
    remaining = cn.amount - (cn.applied_amount or 0)

    return CreditNoteWithDetailsResponse(
        id=cn.id,
        tenant_id=cn.tenant_id,
        school_id=cn.school_id,
        credit_note_number=cn.credit_note_number,
        credit_note_type=cn.credit_note_type.value,
        original_invoice_id=cn.original_invoice_id,
        student_id=cn.student_id,
        amount=cn.amount,
        currency=cn.currency,
        reason=cn.reason,
        status=cn.status.value,
        issued_by=cn.issued_by,
        issued_at=cn.issued_at,
        applied_to_invoice_id=cn.applied_to_invoice_id,
        applied_amount=cn.applied_amount,
        applied_by=cn.applied_by,
        applied_at=cn.applied_at,
        refund_method=cn.refund_method,
        refund_reference=cn.refund_reference,
        refunded_by=cn.refunded_by,
        refunded_at=cn.refunded_at,
        cancelled_by=cn.cancelled_by,
        cancelled_at=cn.cancelled_at,
        cancel_reason=cn.cancel_reason,
        notes=cn.notes,
        remaining_amount=remaining,
        created_at=cn.created_at,
        updated_at=cn.updated_at,
        student_name=f"{cn.student.first_name} {cn.student.last_name}" if cn.student else "Unknown",
        student_id_number=cn.student.student_id if cn.student else "",
        original_invoice_number=cn.original_invoice.invoice_number if cn.original_invoice else None,
        applied_to_invoice_number=cn.applied_to_invoice.invoice_number if cn.applied_to_invoice else None,
        issued_by_name=f"{cn.issued_by_user.first_name} {cn.issued_by_user.last_name}" if cn.issued_by_user else None,
        applied_by_name=f"{cn.applied_by_user.first_name} {cn.applied_by_user.last_name}" if hasattr(cn, 'applied_by_user') and cn.applied_by_user else None,
        refunded_by_name=f"{cn.refunded_by_user.first_name} {cn.refunded_by_user.last_name}" if hasattr(cn, 'refunded_by_user') and cn.refunded_by_user else None,
    )


# =========================
# Credit Note Endpoints
# =========================


@router.post(
    "/credit-notes",
    response_model=CreditNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create credit note",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_credit_note(
    data: CreditNoteCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> CreditNoteResponse:
    """Create a new credit note."""
    from sqlalchemy import select
    from app.models.school import School

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    service = CreditNoteService(db)
    try:
        credit_note = await service.create_credit_note(
            tenant_id=tenant.tenant_id,
            school_id=school.id,
            data=data,
        )
        # Calculate remaining amount (amount - applied_amount)
        remaining = credit_note.amount - (credit_note.applied_amount or 0)

        return CreditNoteResponse(
            id=credit_note.id,
            tenant_id=credit_note.tenant_id,
            school_id=credit_note.school_id,
            credit_note_number=credit_note.credit_note_number,
            credit_note_type=credit_note.credit_note_type.value,
            original_invoice_id=credit_note.original_invoice_id,
            student_id=credit_note.student_id,
            amount=credit_note.amount,
            currency=credit_note.currency,
            reason=credit_note.reason,
            status=credit_note.status.value,
            issued_by=credit_note.issued_by,
            issued_at=credit_note.issued_at,
            applied_to_invoice_id=credit_note.applied_to_invoice_id,
            applied_amount=credit_note.applied_amount,
            applied_by=credit_note.applied_by,
            applied_at=credit_note.applied_at,
            refund_method=credit_note.refund_method,
            refund_reference=credit_note.refund_reference,
            refunded_by=credit_note.refunded_by,
            refunded_at=credit_note.refunded_at,
            cancelled_by=credit_note.cancelled_by,
            cancelled_at=credit_note.cancelled_at,
            cancel_reason=credit_note.cancel_reason,
            notes=credit_note.notes,
            remaining_amount=remaining,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/credit-notes",
    response_model=CreditNoteListResponse,
    summary="List credit notes",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_credit_notes(
    tenant: RequestTenant,
    db: DatabaseSession,
    student_id: Optional[UUID] = Query(None),
    credit_note_status: Optional[str] = Query(None, alias="status"),
    credit_note_type: Optional[str] = Query(None, alias="type"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CreditNoteListResponse:
    """List all credit notes with filters."""
    from sqlalchemy import select
    from app.models.school import School
    from app.models.finance import CreditNoteStatus, CreditNoteType

    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()

    # Parse status and type enums
    status_enum = None
    type_enum = None
    if credit_note_status:
        try:
            status_enum = CreditNoteStatus(credit_note_status)
        except ValueError:
            pass
    if credit_note_type:
        try:
            type_enum = CreditNoteType(credit_note_type)
        except ValueError:
            pass

    service = CreditNoteService(db)
    credit_notes, total = await service.list_credit_notes(
        tenant_id=tenant.tenant_id,
        school_id=school.id if school else None,
        student_id=student_id,
        status=status_enum,
        credit_note_type=type_enum,
        search=search,
        page=page,
        page_size=page_size,
    )

    return CreditNoteListResponse(
        items=[_build_credit_note_response(cn) for cn in credit_notes],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get(
    "/credit-notes/{credit_note_id}",
    response_model=CreditNoteWithDetailsResponse,
    summary="Get credit note",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_credit_note(
    credit_note_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> CreditNoteWithDetailsResponse:
    """Get credit note by ID."""
    service = CreditNoteService(db)
    credit_note = await service.get_credit_note(credit_note_id, tenant.tenant_id)
    if not credit_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit note not found",
        )
    return _build_credit_note_response(credit_note)


@router.put(
    "/credit-notes/{credit_note_id}",
    response_model=CreditNoteResponse,
    summary="Update credit note",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_credit_note(
    credit_note_id: UUID,
    data: CreditNoteUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> CreditNoteResponse:
    """Update a draft credit note."""
    service = CreditNoteService(db)
    try:
        credit_note = await service.update_credit_note(
            credit_note_id, tenant.tenant_id, data
        )
        if not credit_note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
        # Calculate remaining amount (amount - applied_amount)
        remaining = credit_note.amount - (credit_note.applied_amount or 0)

        return CreditNoteResponse(
            id=credit_note.id,
            tenant_id=credit_note.tenant_id,
            school_id=credit_note.school_id,
            credit_note_number=credit_note.credit_note_number,
            credit_note_type=credit_note.credit_note_type.value,
            original_invoice_id=credit_note.original_invoice_id,
            student_id=credit_note.student_id,
            amount=credit_note.amount,
            currency=credit_note.currency,
            reason=credit_note.reason,
            status=credit_note.status.value,
            issued_by=credit_note.issued_by,
            issued_at=credit_note.issued_at,
            applied_to_invoice_id=credit_note.applied_to_invoice_id,
            applied_amount=credit_note.applied_amount,
            applied_by=credit_note.applied_by,
            applied_at=credit_note.applied_at,
            refund_method=credit_note.refund_method,
            refund_reference=credit_note.refund_reference,
            refunded_by=credit_note.refunded_by,
            refunded_at=credit_note.refunded_at,
            cancelled_by=credit_note.cancelled_by,
            cancelled_at=credit_note.cancelled_at,
            cancel_reason=credit_note.cancel_reason,
            notes=credit_note.notes,
            remaining_amount=remaining,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/credit-notes/{credit_note_id}/issue",
    response_model=CreditNoteResponse,
    summary="Issue credit note",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def issue_credit_note(
    credit_note_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
    auto_apply: bool = Query(False, description="Automatically apply to oldest unpaid invoice"),
) -> CreditNoteResponse:
    """
    Issue a draft credit note, activating it.

    If auto_apply is True, the credit will be automatically applied to the
    student's oldest unpaid invoice (if any exists).
    """
    service = CreditNoteService(db)
    try:
        credit_note, applied_invoice = await service.issue_credit_note(
            credit_note_id, tenant.tenant_id, UUID(user_id), auto_apply=auto_apply
        )
        if not credit_note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
        # Calculate remaining amount (amount - applied_amount)
        remaining = credit_note.amount - (credit_note.applied_amount or 0)

        return CreditNoteResponse(
            id=credit_note.id,
            tenant_id=credit_note.tenant_id,
            school_id=credit_note.school_id,
            credit_note_number=credit_note.credit_note_number,
            credit_note_type=credit_note.credit_note_type.value,
            original_invoice_id=credit_note.original_invoice_id,
            student_id=credit_note.student_id,
            amount=credit_note.amount,
            currency=credit_note.currency,
            reason=credit_note.reason,
            status=credit_note.status.value,
            issued_by=credit_note.issued_by,
            issued_at=credit_note.issued_at,
            applied_to_invoice_id=credit_note.applied_to_invoice_id,
            applied_amount=credit_note.applied_amount,
            applied_by=credit_note.applied_by,
            applied_at=credit_note.applied_at,
            refund_method=credit_note.refund_method,
            refund_reference=credit_note.refund_reference,
            refunded_by=credit_note.refunded_by,
            refunded_at=credit_note.refunded_at,
            cancelled_by=credit_note.cancelled_by,
            cancelled_at=credit_note.cancelled_at,
            cancel_reason=credit_note.cancel_reason,
            notes=credit_note.notes,
            remaining_amount=remaining,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/credit-notes/{credit_note_id}/apply",
    response_model=CreditNoteResponse,
    summary="Apply credit note to invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def apply_credit_note(
    credit_note_id: UUID,
    data: CreditNoteApply,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> CreditNoteResponse:
    """Apply a credit note to an invoice."""
    service = CreditNoteService(db)
    try:
        credit_note = await service.apply_credit_note(
            credit_note_id, tenant.tenant_id, data, UUID(user_id)
        )
        if not credit_note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
        # Calculate remaining amount (amount - applied_amount)
        remaining = credit_note.amount - (credit_note.applied_amount or 0)

        return CreditNoteResponse(
            id=credit_note.id,
            tenant_id=credit_note.tenant_id,
            school_id=credit_note.school_id,
            credit_note_number=credit_note.credit_note_number,
            credit_note_type=credit_note.credit_note_type.value,
            original_invoice_id=credit_note.original_invoice_id,
            student_id=credit_note.student_id,
            amount=credit_note.amount,
            currency=credit_note.currency,
            reason=credit_note.reason,
            status=credit_note.status.value,
            issued_by=credit_note.issued_by,
            issued_at=credit_note.issued_at,
            applied_to_invoice_id=credit_note.applied_to_invoice_id,
            applied_amount=credit_note.applied_amount,
            applied_by=credit_note.applied_by,
            applied_at=credit_note.applied_at,
            refund_method=credit_note.refund_method,
            refund_reference=credit_note.refund_reference,
            refunded_by=credit_note.refunded_by,
            refunded_at=credit_note.refunded_at,
            cancelled_by=credit_note.cancelled_by,
            cancelled_at=credit_note.cancelled_at,
            cancel_reason=credit_note.cancel_reason,
            notes=credit_note.notes,
            remaining_amount=remaining,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/credit-notes/{credit_note_id}/refund",
    response_model=CreditNoteResponse,
    summary="Refund credit note",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def refund_credit_note(
    credit_note_id: UUID,
    data: CreditNoteRefund,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> CreditNoteResponse:
    """Refund a credit note to the student/guardian."""
    service = CreditNoteService(db)
    try:
        credit_note = await service.refund_credit_note(
            credit_note_id, tenant.tenant_id, data, UUID(user_id)
        )
        if not credit_note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
        # Calculate remaining amount (amount - applied_amount)
        remaining = credit_note.amount - (credit_note.applied_amount or 0)

        return CreditNoteResponse(
            id=credit_note.id,
            tenant_id=credit_note.tenant_id,
            school_id=credit_note.school_id,
            credit_note_number=credit_note.credit_note_number,
            credit_note_type=credit_note.credit_note_type.value,
            original_invoice_id=credit_note.original_invoice_id,
            student_id=credit_note.student_id,
            amount=credit_note.amount,
            currency=credit_note.currency,
            reason=credit_note.reason,
            status=credit_note.status.value,
            issued_by=credit_note.issued_by,
            issued_at=credit_note.issued_at,
            applied_to_invoice_id=credit_note.applied_to_invoice_id,
            applied_amount=credit_note.applied_amount,
            applied_by=credit_note.applied_by,
            applied_at=credit_note.applied_at,
            refund_method=credit_note.refund_method,
            refund_reference=credit_note.refund_reference,
            refunded_by=credit_note.refunded_by,
            refunded_at=credit_note.refunded_at,
            cancelled_by=credit_note.cancelled_by,
            cancelled_at=credit_note.cancelled_at,
            cancel_reason=credit_note.cancel_reason,
            notes=credit_note.notes,
            remaining_amount=remaining,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/credit-notes/{credit_note_id}/cancel",
    response_model=CreditNoteResponse,
    summary="Cancel credit note",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def cancel_credit_note(
    credit_note_id: UUID,
    data: CreditNoteCancel,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> CreditNoteResponse:
    """Cancel a credit note."""
    service = CreditNoteService(db)
    try:
        credit_note = await service.cancel_credit_note(
            credit_note_id, tenant.tenant_id, data, UUID(user_id)
        )
        if not credit_note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
        # Calculate remaining amount (amount - applied_amount)
        remaining = credit_note.amount - (credit_note.applied_amount or 0)

        return CreditNoteResponse(
            id=credit_note.id,
            tenant_id=credit_note.tenant_id,
            school_id=credit_note.school_id,
            credit_note_number=credit_note.credit_note_number,
            credit_note_type=credit_note.credit_note_type.value,
            original_invoice_id=credit_note.original_invoice_id,
            student_id=credit_note.student_id,
            amount=credit_note.amount,
            currency=credit_note.currency,
            reason=credit_note.reason,
            status=credit_note.status.value,
            issued_by=credit_note.issued_by,
            issued_at=credit_note.issued_at,
            applied_to_invoice_id=credit_note.applied_to_invoice_id,
            applied_amount=credit_note.applied_amount,
            applied_by=credit_note.applied_by,
            applied_at=credit_note.applied_at,
            refund_method=credit_note.refund_method,
            refund_reference=credit_note.refund_reference,
            refunded_by=credit_note.refunded_by,
            refunded_at=credit_note.refunded_at,
            cancelled_by=credit_note.cancelled_by,
            cancelled_at=credit_note.cancelled_at,
            cancel_reason=credit_note.cancel_reason,
            notes=credit_note.notes,
            remaining_amount=remaining,
            created_at=credit_note.created_at,
            updated_at=credit_note.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/credit-notes/{credit_note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credit note",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_credit_note(
    credit_note_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> None:
    """Delete a draft credit note."""
    service = CreditNoteService(db)
    try:
        if not await service.delete_credit_note(credit_note_id, tenant.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/students/{student_id}/credit-balance",
    response_model=StudentCreditBalance,
    summary="Get student credit balance",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_credit_balance(
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> StudentCreditBalance:
    """Get a student's available credit balance."""
    service = CreditNoteService(db)
    balance = await service.get_student_credit_balance(student_id, tenant.tenant_id)
    return StudentCreditBalance(
        student_id=student_id,
        credit_balance=balance,
        currency="GHS",
    )


@router.get(
    "/students/{student_id}/credit-notes",
    response_model=CreditNoteListResponse,
    summary="Get student credit notes",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_credit_notes(
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    include_cancelled: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CreditNoteListResponse:
    """Get all credit notes for a student."""
    service = CreditNoteService(db)
    credit_notes = await service.get_student_credit_notes(
        student_id, tenant.tenant_id, include_cancelled
    )

    # Manual pagination
    total = len(credit_notes)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = list(credit_notes)[start:end]

    return CreditNoteListResponse(
        items=[_build_credit_note_response(cn) for cn in page_items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )

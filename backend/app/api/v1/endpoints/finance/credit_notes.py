"""
SIMS Plus - Credit Note Endpoints

Endpoints for credit note management: CRUD, issue, apply, refund, cancel, student balance.
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy import select

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    RequestTenant,
    require_permissions,
)
from app.models.finance import CreditNoteStatus, CreditNoteType
from app.models.school import School
from app.schemas.finance import (
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
from app.services.finance import CreditNoteService, FinanceAuditService

from ._helpers import get_school_for_tenant, _build_credit_note_response

router = APIRouter()


def _build_credit_note_basic_response(credit_note) -> CreditNoteResponse:
    """Build a basic CreditNoteResponse from a credit note model instance."""
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
    user_id: CurrentUserId,
) -> CreditNoteResponse:
    """Create a new credit note."""
    try:
        school = await get_school_for_tenant(db, tenant.tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    service = CreditNoteService(db)
    try:
        credit_note = await service.create_credit_note(
            tenant_id=tenant.tenant_id,
            school_id=school.id,
            data=data,
        )
        # Log audit trail for credit note creation
        audit_service = FinanceAuditService(db)
        await audit_service.log_create(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note.id,
            performed_by=UUID(user_id),
            metadata={"credit_note_number": credit_note.credit_note_number},
        )
        return _build_credit_note_basic_response(credit_note)
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
    user_id: CurrentUserId,
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
        # Log audit trail for credit note update
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note.id,
            action="update",
            performed_by=UUID(user_id),
        )
        return _build_credit_note_basic_response(credit_note)
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
        # Log audit trail for credit note issuance
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note.id,
            action="issue",
            performed_by=UUID(user_id),
            metadata={"auto_apply": auto_apply, "applied_invoice_id": str(applied_invoice.id) if applied_invoice else None},
        )
        return _build_credit_note_basic_response(credit_note)
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
        # Log audit trail for credit note application
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note.id,
            action="update",
            performed_by=UUID(user_id),
            metadata={"applied_to_invoice_id": str(data.invoice_id), "applied_amount": str(credit_note.applied_amount)},
        )
        return _build_credit_note_basic_response(credit_note)
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
        # Log audit trail for credit note refund
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note.id,
            action="refund",
            performed_by=UUID(user_id),
            metadata={"refund_method": data.refund_method, "refund_reference": data.refund_reference},
        )
        return _build_credit_note_basic_response(credit_note)
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
        # Log audit trail for credit note cancellation
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note.id,
            action="cancel",
            performed_by=UUID(user_id),
            metadata={"cancel_reason": data.reason},
        )
        return _build_credit_note_basic_response(credit_note)
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
    user_id: CurrentUserId,
) -> None:
    """Delete a draft credit note."""
    service = CreditNoteService(db)
    try:
        if not await service.delete_credit_note(credit_note_id, tenant.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit note not found",
            )
        # Log audit trail for credit note deletion (soft delete)
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="credit_note",
            entity_id=credit_note_id,
            action="delete",
            performed_by=UUID(user_id),
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

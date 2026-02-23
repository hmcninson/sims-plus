"""
SIMS Plus - Payment Endpoints

Endpoints for payment recording, listing, voiding, and receipts.
"""

import math
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    OptionalSchoolCtx,
    RequestTenant,
    SchoolCtx,
    require_permissions,
)
from app.schemas.finance import (
    PaymentCreate,
    PaymentResponse,
    PaymentWithDetailsResponse,
    PaymentListResponse,
    PaymentVoid,
    PaymentReceiptResponse,
)
from app.services.finance import PaymentService, FinanceAuditService, FinanceServiceError

from ._helpers import (
    _build_payment_response,
    amount_to_words,
)

router = APIRouter()


@router.post(
    "/payments",
    response_model=PaymentWithDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record payment",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def record_payment(
    data: PaymentCreate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> PaymentWithDetailsResponse:
    """Record a payment."""
    service = PaymentService(db)
    payment = await service.record_payment(
        tenant_id=school_ctx.tenant_id,
        school_id=school_ctx.school_id,
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
    payment = await service.get_payment(school_ctx.tenant_id, payment.id)
    # Log audit trail for payment recording
    audit_service = FinanceAuditService(db)
    await audit_service.log_create(
        tenant_id=school_ctx.tenant_id,
        entity_type="payment",
        entity_id=payment.id,
        performed_by=UUID(user_id),
        metadata={
            "receipt_number": payment.receipt_number,
            "amount": str(data.amount),
            "payment_method": data.payment_method,
            "student_id": str(data.student_id),
        },
    )
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
    school_ctx: OptionalSchoolCtx,
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
    # Chain support: scope to active school when header is present
    school_id = school_ctx.school_id if school_ctx else None
    service = PaymentService(db)
    payments, total = await service.list_payments(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
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
    tenant: RequestTenant,
    db: DatabaseSession,
) -> PaymentWithDetailsResponse:
    """Get payment by ID."""
    service = PaymentService(db)
    payment = await service.get_payment(tenant.tenant_id, payment_id)
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
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> PaymentResponse:
    """Void a payment."""
    service = PaymentService(db)
    try:
        payment = await service.void_payment(
            tenant_id=tenant.tenant_id,
            payment_id=payment_id,
            voided_by=UUID(user_id),
            reason=data.reason,
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        # Log audit trail for payment void
        audit_service = FinanceAuditService(db)
        await audit_service.log_void(
            tenant_id=tenant.tenant_id,
            entity_type="payment",
            entity_id=payment.id,
            performed_by=UUID(user_id),
            reason=data.reason,
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


@router.get(
    "/payments/{payment_id}/receipt",
    response_model=PaymentReceiptResponse,
    summary="Get payment receipt",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_payment_receipt(
    payment_id: UUID,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
) -> PaymentReceiptResponse:
    """Get payment receipt details for printing."""
    # Fetch full school record for receipt details (address, phone, logo)
    from app.models.school import School
    school_result = await db.execute(
        select(School)
        .where(School.tenant_id == school_ctx.tenant_id)
        .where(School.id == school_ctx.school_id)
    )
    school = school_result.scalar_one_or_none()

    service = PaymentService(db)
    payment = await service.get_payment(school_ctx.tenant_id, payment_id)
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

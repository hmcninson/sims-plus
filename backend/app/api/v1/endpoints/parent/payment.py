"""
SIMS Plus - Parent Portal Payment Endpoints

Endpoints for online payment flow via Paystack:
1. Parent initiates payment (creates Paystack transaction)
2. Parent returns from Paystack -> verify payment
3. Paystack sends webhook -> verify and record payment

The webhook endpoint is unauthenticated (called by Paystack servers)
and verifies integrity via HMAC-SHA512 signature.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    UnscopedDatabaseSession,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentVerifyResponse,
)
from app.services.parent import ParentService, ParentServiceError
from app.services.payment import OnlinePaymentError, OnlinePaymentService

from ._helpers import _get_user_id, _handle_parent_error, _handle_payment_error

router = APIRouter()


@router.post(
    "/children/{student_id}/payments/initiate",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate online payment",
    dependencies=[Depends(require_permissions("parent.finance.read"))],
)
async def initiate_payment(
    student_id: UUID,
    data: PaymentInitiateRequest,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> PaymentInitiateResponse:
    """
    Start an online payment for a child's invoice via Paystack.

    Validates the invoice exists and belongs to the student, checks the
    amount does not exceed the outstanding balance, then creates a
    Paystack transaction. Returns the authorization URL for redirect
    or access code for inline popup.

    Supports Mobile Money (MTN MoMo, Vodafone Cash, AirtelTigo) and Card.
    """
    user_id = _get_user_id(user)

    # Security gate: verify parent has access to this child
    parent_service = ParentService(db)
    try:
        await parent_service.require_parent_child_access(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    payment_service = OnlinePaymentService(db)

    try:
        result = await payment_service.initiate_payment(
            tenant_id=tenant.tenant_id,
            student_id=student_id,
            invoice_id=data.invoice_id,
            amount=data.amount,
            method=data.method.value,
            payer_email=user.get("email", ""),
            payer_phone=data.phone,
        )
    except OnlinePaymentError as e:
        raise _handle_payment_error(e)

    return PaymentInitiateResponse(**result)


@router.get(
    "/payments/verify/{reference}",
    response_model=PaymentVerifyResponse,
    summary="Verify payment status",
    dependencies=[Depends(require_permissions("parent.finance.read"))],
)
async def verify_payment(
    reference: str,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> PaymentVerifyResponse:
    """
    Verify a payment transaction by its Paystack reference.

    Called when the parent returns from Paystack to check if the
    payment was successful. This endpoint is idempotent: if the
    payment was already recorded (e.g., via webhook), it returns
    the existing payment info without double-recording.
    """
    payment_service = OnlinePaymentService(db)

    try:
        result = await payment_service.verify_payment(reference=reference)
    except OnlinePaymentError as e:
        raise _handle_payment_error(e)

    return PaymentVerifyResponse(**result)


@router.post(
    "/webhook/paystack",
    status_code=status.HTTP_200_OK,
    summary="Paystack webhook handler",
    # No auth dependency -- Paystack servers call this endpoint directly.
    # Integrity is verified via HMAC-SHA512 signature in the request header.
    # Uses UnscopedDatabaseSession because webhooks arrive without subdomain context.
    # Tenant context is set manually from the transaction metadata after signature verification.
)
async def paystack_webhook(
    request: Request,
    db: UnscopedDatabaseSession,
) -> dict:
    """
    Handle Paystack webhook events (e.g., charge.success).

    SECURITY: This endpoint has NO authentication dependency because
    it is called by Paystack servers, not by a browser session.
    Instead, the request body is verified against the X-Paystack-Signature
    header using HMAC-SHA512 with the Paystack secret key.

    Uses UnscopedDatabaseSession because webhooks arrive without a subdomain.
    The tenant context is resolved from the transaction metadata (set by us
    during payment initiation) and applied manually to the DB session.

    Currently handles:
    - charge.success: verify and record the payment (idempotent)

    Returns 200 OK to acknowledge receipt. Paystack retries on non-2xx.
    """
    payload_body = await request.body()
    signature = request.headers.get("X-Paystack-Signature", "")

    payment_service = OnlinePaymentService(db)

    try:
        await payment_service.handle_webhook(
            payload_body=payload_body,
            signature=signature,
        )
    except OnlinePaymentError as e:
        raise _handle_payment_error(e)

    return {"status": "ok"}

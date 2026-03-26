"""
SIMS Plus - Admissions Portal Paystack Webhook

Unauthenticated webhook for Paystack payment confirmations.
Uses UnscopedDatabaseSession + manual set_tenant_context from metadata.
Verifies HMAC-SHA512 signature before processing.
"""

import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select, text

from app.api.deps import UnscopedDatabaseSession
from app.config import settings
from app.models.admissions.application import ApplicationPayment
from app.services.admissions import ApplicationPaymentError, ApplicationPaymentService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/public/webhook")


@router.post(
    "/paystack",
    status_code=status.HTTP_200_OK,
    summary="Paystack webhook for application payments",
)
async def handle_paystack_webhook(
    request: Request,
    db: UnscopedDatabaseSession,
) -> dict:
    """
    Handle Paystack webhook for application fee payment confirmation.

    Security:
    1. Verify HMAC-SHA512 signature using PAYSTACK_WEBHOOK_SECRET
       (or PAYSTACK_SECRET_KEY fallback)
    2. Extract tenant_id from event metadata
    3. Look up payment by provider_reference (unscoped) and
       cross-validate tenant_id
    4. Set tenant context with VALIDATED tenant_id from DB record
    5. Process payment confirmation

    Uses UnscopedDatabaseSession because:
    - Webhook has no subdomain context (called by Paystack servers)
    - tenant_id comes from Paystack metadata (set during payment initiation)
    - We manually set_tenant_context after extracting from metadata

    Returns 200 OK immediately -- Paystack retries on non-200.
    """
    # 1. Read raw body for signature verification
    body = await request.body()

    # 2. Verify HMAC-SHA512 signature
    signature = request.headers.get("x-paystack-signature", "")
    # Prefer dedicated webhook secret, fall back to API secret key
    secret_key = settings.PAYSTACK_WEBHOOK_SECRET or settings.PAYSTACK_SECRET_KEY
    if not secret_key:
        logger.error("admissions_webhook_no_secret_key_configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook not configured",
        )

    expected = hmac.new(
        secret_key.encode(),
        body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # 3. Parse event
    event = json.loads(body)

    # Only process charge.success events
    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    # 4. Extract metadata
    data = event.get("data", {})
    metadata = data.get("metadata", {})

    # Validate context is application_fee -- ignore other payment contexts
    if metadata.get("context") != "application_fee":
        return {"status": "ignored", "reason": "not application_fee context"}

    webhook_tenant_id = metadata.get("tenant_id")
    if not webhook_tenant_id:
        return {"status": "ignored", "reason": "no tenant_id in metadata"}

    reference = data.get("reference")
    if not reference:
        return {"status": "ignored", "reason": "no reference in data"}

    # 5. Cross-validate tenant_id: look up payment by provider_reference
    #    (unscoped query since we have no tenant context yet)
    result = await db.execute(
        select(ApplicationPayment).where(
            ApplicationPayment.provider_reference == reference,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning(
            "admissions_webhook_payment_not_found",
            reference=reference,
        )
        return {"status": "ignored", "reason": "payment not found"}

    # Validate metadata tenant_id matches actual payment's tenant_id
    if str(payment.tenant_id) != webhook_tenant_id:
        logger.error(
            "admissions_webhook_tenant_mismatch",
            expected=str(payment.tenant_id),
            received=webhook_tenant_id,
        )
        return {"status": "ignored", "reason": "tenant mismatch"}

    # 6. Set tenant context with VALIDATED tenant_id from DB record
    await db.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(payment.tenant_id)},
    )

    # 7. Process payment using the simplified process_webhook method
    #    (HMAC verification already done above in the endpoint)
    try:
        service = ApplicationPaymentService(db)
        await service.process_webhook(
            provider_reference=reference,
            # Paystack sends amount in kobo/pesewas (smallest currency unit)
            amount=data.get("amount", 0) / 100,
            payment_method=data.get("channel"),
            metadata=metadata,
        )
    except ApplicationPaymentError:
        # Log but don't raise -- return 200 to prevent Paystack retries
        logger.exception(
            "admissions_webhook_processing_failed",
            reference=reference,
            tenant_id=str(payment.tenant_id),
        )

    return {"status": "processed"}

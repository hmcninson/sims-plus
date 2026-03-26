"""
SIMS Plus - Application Payment Service

Handles Paystack payment initialization and webhook processing
for application fees. Separate from the main payment system since
applicants are not yet students.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admissions import (
    AdmissionPeriod,
    Application,
    ApplicationGuardian,
    ApplicationPayment,
    ApplicationStatusHistory,
    AdmissionApplicationStatus,
)

logger = structlog.get_logger(__name__)

PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"


class ApplicationPaymentError(Exception):
    def __init__(self, message: str, code: str = "PAYMENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ApplicationPaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_payment(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_id: uuid.UUID,
        tracking_code: str,
    ) -> dict:
        """
        Initialize Paystack payment for application fee.

        Creates a payment record and calls Paystack API to get the
        authorization URL for the payment page.

        Returns: { authorization_url, reference, amount }
        """
        # Get application
        app = await self._get_application(tenant_id, application_id)

        if app.fee_waived:
            raise ApplicationPaymentError(
                "Application fee has been waived", code="FEE_WAIVED"
            )

        if app.status != AdmissionApplicationStatus.DRAFT.value:
            raise ApplicationPaymentError(
                "Application is not in draft status", code="INVALID_STATUS"
            )

        # Get fee amount from the admission period
        period_result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == app.admission_period_id,
                AdmissionPeriod.tenant_id == tenant_id,
            )
        )
        period = period_result.scalar_one_or_none()
        if not period or not period.application_fee_amount:
            raise ApplicationPaymentError(
                "No fee configured for this period", code="NO_FEE"
            )

        # Paystack expects amount in lowest currency unit (pesewas for GHS)
        amount_pesewas = int(period.application_fee_amount * 100)

        # Get primary guardian email for Paystack customer field
        guardian_result = await self.db.execute(
            select(ApplicationGuardian).where(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.is_primary.is_(True),
            )
        )
        guardian = guardian_result.scalar_one_or_none()
        # Paystack requires an email — fall back to a generated one if guardian has none
        email = (
            guardian.email
            if guardian and guardian.email
            else f"{tracking_code}@applicant.simsplus.io"
        )

        # Create payment record before calling Paystack
        payment = ApplicationPayment(
            tenant_id=tenant_id,
            application_id=application_id,
            amount=period.application_fee_amount,
            currency="GHS",
            status="pending",
        )
        self.db.add(payment)
        await self.db.flush()

        # Build callback URL using the existing config pattern
        callback_url = settings.PAYMENT_CALLBACK_URL or ""

        payload = {
            "email": email,
            "amount": amount_pesewas,
            "currency": "GHS",
            "callback_url": callback_url,
            "metadata": {
                "application_id": str(application_id),
                "payment_id": str(payment.id),
                "tenant_id": str(tenant_id),
                "school_id": str(school_id),
                "tracking_code": tracking_code,
                "context": "application_fee",
                "custom_fields": [
                    {
                        "display_name": "Application",
                        "variable_name": "tracking_code",
                        "value": tracking_code,
                    }
                ],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    PAYSTACK_INIT_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                        "Content-Type": "application/json",
                    },
                )
        except Exception:
            logger.exception("paystack_request_failed")
            raise ApplicationPaymentError(
                "Payment service unavailable. Please try again.",
                code="PROVIDER_UNAVAILABLE",
            )

        if response.status_code != 200:
            logger.error(
                "paystack_init_failed",
                status=response.status_code,
                # Never log the full response body — may contain PII
            )
            raise ApplicationPaymentError(
                "Payment initialization failed", code="INIT_FAILED"
            )

        data = response.json().get("data", {})
        reference = data.get("reference")

        # Store the Paystack reference for webhook correlation
        payment.provider_reference = reference
        await self.db.flush()

        return {
            "authorization_url": data.get("authorization_url"),
            "reference": reference,
            "amount": float(period.application_fee_amount),
        }

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload_body: bytes,
        signature: str,
    ) -> None:
        """
        Process Paystack webhook for application payments.

        Uses UnscopedDatabaseSession — manually sets tenant context
        from webhook metadata after cross-validating against the DB record.

        Security:
        - Verifies HMAC-SHA512 signature before processing
        - Cross-validates tenant_id from metadata against payment record
        - Idempotent: ignores already-completed payments
        """
        # 1. Verify HMAC-SHA512 signature
        secret_key = (
            settings.PAYSTACK_WEBHOOK_SECRET or settings.PAYSTACK_SECRET_KEY
        )
        if not secret_key:
            logger.error("paystack_webhook_no_secret")
            return

        secret = secret_key.encode()
        expected = hmac.new(secret, payload_body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ApplicationPaymentError(
                "Invalid webhook signature", code="INVALID_SIGNATURE"
            )

        # 2. Parse payload
        payload = json.loads(payload_body)
        event = payload.get("event")
        if event != "charge.success":
            return  # Ignore non-success events

        data = payload.get("data", {})
        metadata = data.get("metadata", {})

        # Only process application_fee context (ignore tuition fee webhooks)
        if metadata.get("context") != "application_fee":
            return

        # 3. Extract and validate metadata fields
        webhook_tenant_id = metadata.get("tenant_id")
        payment_id = metadata.get("payment_id")
        reference = data.get("reference")

        if not all([webhook_tenant_id, payment_id, reference]):
            logger.warning("webhook_missing_metadata")
            return

        try:
            uuid.UUID(webhook_tenant_id)
            uuid.UUID(payment_id)
        except ValueError:
            logger.warning("webhook_invalid_uuid")
            return

        # 4. Look up payment by provider_reference (UNIQUE constraint)
        # Using unscoped session — no tenant context set yet
        result = await db.execute(
            select(ApplicationPayment).where(
                ApplicationPayment.provider_reference == reference,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.warning("webhook_payment_not_found", reference=reference)
            return

        # 5. Cross-validate tenant_id from metadata against DB record
        if str(payment.tenant_id) != webhook_tenant_id:
            logger.error(
                "webhook_tenant_mismatch",
                expected=str(payment.tenant_id),
                received=webhook_tenant_id,
            )
            return

        # 6. Set tenant context with the VALIDATED tenant_id from the DB record
        await db.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(payment.tenant_id)},
        )

        # Idempotency: skip if already processed
        if payment.status == "completed":
            return

        payment.status = "completed"
        payment.paid_at = datetime.now(UTC)
        payment.provider_reference = reference
        payment.payment_method = data.get("channel", "unknown")
        payment.metadata = {
            "paystack_reference": reference,
            "channel": data.get("channel"),
            "ip_address": data.get("ip_address"),
        }

        # 7. If application is in DRAFT, transition to SUBMITTED
        app_result = await db.execute(
            select(Application).where(
                Application.id == payment.application_id,
                Application.tenant_id == payment.tenant_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if app and app.status == AdmissionApplicationStatus.DRAFT.value:
            app.status = AdmissionApplicationStatus.SUBMITTED.value
            app.submitted_at = datetime.now(UTC)

            history = ApplicationStatusHistory(
                tenant_id=payment.tenant_id,
                application_id=app.id,
                from_status=AdmissionApplicationStatus.DRAFT.value,
                to_status=AdmissionApplicationStatus.SUBMITTED.value,
                changed_by=None,
                reason="Application fee payment confirmed via Paystack",
            )
            db.add(history)

        # Webhook handler flushes changes — transaction commit handled by endpoint middleware
        await db.flush()

        logger.info(
            "application_payment_completed",
            payment_id=payment_id,
            application_id=str(payment.application_id),
            reference=reference,
        )

    async def process_webhook(
        self,
        provider_reference: str,
        amount: float,
        payment_method: str | None,
        metadata: dict,
    ) -> None:
        """
        Process a verified Paystack webhook for application fee payment.

        Called by the webhook endpoint AFTER HMAC verification and tenant
        context setup. This method handles the payment record update and
        application status transition.

        Idempotent: ignores already-completed payments.
        """
        # Look up payment by provider_reference within the (already set) tenant context
        result = await self.db.execute(
            select(ApplicationPayment).where(
                ApplicationPayment.provider_reference == provider_reference,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise ApplicationPaymentError(
                "Payment not found", code="NOT_FOUND"
            )

        # Idempotency: skip if already processed
        if payment.status == "completed":
            return

        payment.status = "completed"
        payment.paid_at = datetime.now(UTC)
        payment.payment_method = payment_method or "unknown"
        payment.payment_metadata = {
            "paystack_reference": provider_reference,
            "channel": payment_method,
        }

        # If application is in DRAFT, transition to SUBMITTED
        app_result = await self.db.execute(
            select(Application).where(
                Application.id == payment.application_id,
                Application.tenant_id == payment.tenant_id,
            )
        )
        app = app_result.scalar_one_or_none()
        if app and app.status == AdmissionApplicationStatus.DRAFT.value:
            app.status = AdmissionApplicationStatus.SUBMITTED.value
            app.submitted_at = datetime.now(UTC)

            history = ApplicationStatusHistory(
                tenant_id=payment.tenant_id,
                application_id=app.id,
                from_status=AdmissionApplicationStatus.DRAFT.value,
                to_status=AdmissionApplicationStatus.SUBMITTED.value,
                changed_by=None,
                reason="Application fee payment confirmed via Paystack webhook",
            )
            self.db.add(history)

        await self.db.flush()

        logger.info(
            "webhook_payment_processed",
            reference=provider_reference,
            application_id=str(payment.application_id),
        )

    async def _get_application(
        self, tenant_id: uuid.UUID, app_id: uuid.UUID
    ) -> Application:
        result = await self.db.execute(
            select(Application).where(
                Application.id == app_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise ApplicationPaymentError("Application not found", code="NOT_FOUND")
        return app

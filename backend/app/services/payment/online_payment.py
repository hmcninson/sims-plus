"""
SIMS Plus - Online Payment Service

Handles online payment flows via Paystack for the parent portal.

Supported payment methods:
- Mobile Money (MTN MoMo, Vodafone Cash, AirtelTigo Money)
- Card (Visa/Mastercard)

Payment flow:
1. Parent calls initiate_payment -> we create a Paystack transaction
2. Parent completes payment on Paystack (redirect or USSD prompt)
3. Paystack sends webhook (charge.success) -> we verify and record
4. Parent returns to callback URL -> we verify again (idempotent)

Security:
- Paystack secret key never leaves the backend
- Webhook signature verified with HMAC-SHA512 (timing-safe)
- Amount validated server-side against invoice balance
- Payment recording is idempotent (keyed on reference)
- All transactions logged to finance_audit_log
"""

import hashlib
import hmac
import json
import uuid as uuid_mod
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.finance import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from app.models.student import Student
from app.services.finance._shared import FinanceServiceError
from app.services.finance.audit_service import FinanceAuditService
from app.services.finance.invoice_service import InvoiceService
from app.services.finance.payment_service import PaymentService

logger = structlog.get_logger()


class OnlinePaymentError(Exception):
    """Raised when an online payment operation fails."""

    def __init__(self, message: str, code: str = "PAYMENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class OnlinePaymentService:
    """
    Handles online payment flow via Paystack.

    This service orchestrates between Paystack's API and the existing
    PaymentService/InvoiceService to ensure consistent payment recording
    and invoice status updates. All operations are idempotent where it
    matters (verify_payment checks for existing records before recording).
    """

    PAYSTACK_BASE_URL = "https://api.paystack.co"

    # Map our schema-level payment methods to Paystack channel names
    _CHANNEL_MAP = {
        "mobile_money": ["mobile_money"],
        "card": ["card"],
    }

    # Map Paystack channel/authorization type back to our PaymentMethod enum
    _PAYSTACK_TO_PAYMENT_METHOD = {
        "mobile_money": PaymentMethod.MOMO_MTN,  # Default MoMo; refined by provider
        "card": PaymentMethod.CARD,
        "bank": PaymentMethod.BANK_TRANSFER,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initiate_payment(
        self,
        tenant_id: UUID,
        student_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
        method: str,
        payer_email: str,
        payer_phone: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> dict:
        """
        Start an online payment flow by creating a Paystack transaction.

        Validates the invoice exists and belongs to the student, checks
        the amount does not exceed the outstanding balance, then calls
        Paystack's transaction/initialize endpoint.

        Args:
            tenant_id: Tenant ID for defense-in-depth scoping.
            student_id: The student the payment is for.
            invoice_id: The invoice being paid.
            amount: Payment amount in cedis (must be > 0 and <= balance).
            method: "mobile_money" or "card".
            payer_email: Email for Paystack transaction (required by Paystack).
            payer_phone: Phone number (required for mobile money).
            callback_url: URL to redirect parent after payment. Falls back to
                          settings.PAYMENT_CALLBACK_URL.

        Returns:
            dict with keys: authorization_url, reference, access_code

        Raises:
            OnlinePaymentError: If validation fails or Paystack returns an error.
        """
        # Validate that the invoice exists, belongs to the student, and is payable
        invoice = await self._get_payable_invoice(tenant_id, student_id, invoice_id)

        # Server-side amount validation: cannot exceed outstanding balance
        outstanding = invoice.total_amount - invoice.amount_paid
        if amount > outstanding:
            raise OnlinePaymentError(
                f"Amount {amount} exceeds outstanding balance {outstanding}",
                code="AMOUNT_EXCEEDS_BALANCE",
            )

        if amount <= Decimal("0"):
            raise OnlinePaymentError(
                "Payment amount must be greater than zero",
                code="INVALID_AMOUNT",
            )

        # Mobile money requires a phone number
        if method == "mobile_money" and not payer_phone:
            raise OnlinePaymentError(
                "Phone number is required for mobile money payments",
                code="PHONE_REQUIRED",
            )

        reference = self._generate_reference()
        resolved_callback = callback_url or settings.PAYMENT_CALLBACK_URL

        # Paystack expects amount in pesewas (smallest currency unit)
        amount_pesewas = int(amount * 100)

        channels = self._CHANNEL_MAP.get(method)
        if not channels:
            raise OnlinePaymentError(
                f"Unsupported payment method: {method}",
                code="INVALID_METHOD",
            )

        payload = {
            "amount": amount_pesewas,
            "email": payer_email,
            "currency": "GHS",
            "reference": reference,
            "channels": channels,
            "metadata": {
                "invoice_id": str(invoice_id),
                "student_id": str(student_id),
                "tenant_id": str(tenant_id),
                "invoice_number": invoice.invoice_number,
                "custom_fields": [
                    {
                        "display_name": "Invoice Number",
                        "variable_name": "invoice_number",
                        "value": invoice.invoice_number,
                    },
                ],
            },
        }

        if resolved_callback:
            payload["callback_url"] = resolved_callback

        # For mobile money, include the phone number in metadata so Paystack
        # can send the USSD prompt directly
        if method == "mobile_money" and payer_phone:
            payload["mobile_money"] = {"phone": payer_phone}

        logger.info(
            "paystack_initiate",
            reference=reference,
            invoice_id=str(invoice_id),
            amount=str(amount),
            method=method,
        )

        response = await self._call_paystack("POST", "/transaction/initialize", data=payload)

        return {
            "authorization_url": response["data"].get("authorization_url"),
            "reference": response["data"]["reference"],
            "access_code": response["data"].get("access_code"),
        }

    async def verify_payment(self, reference: str) -> dict:
        """
        Verify a payment with Paystack and record it if successful.

        This method is idempotent: if a payment with this reference has
        already been recorded, it returns the existing payment info
        without double-recording.

        Called from both the callback endpoint (parent returns from
        Paystack) and the webhook handler (async notification).

        Args:
            reference: The unique Paystack transaction reference.

        Returns:
            dict with keys: status, amount, method, receipt_number,
                           invoice_number, balance_remaining

        Raises:
            OnlinePaymentError: If verification fails or Paystack returns an error.
        """
        # Idempotency check: see if we already recorded this payment
        existing = await self._find_payment_by_reference(reference)
        if existing:
            logger.info(
                "paystack_verify_already_recorded",
                reference=reference,
                payment_id=str(existing.id),
            )
            return await self._build_verify_response(existing)

        # Call Paystack to verify the transaction
        logger.info("paystack_verify", reference=reference)
        response = await self._call_paystack("GET", f"/transaction/verify/{reference}")

        txn_data = response["data"]
        txn_status = txn_data.get("status", "")

        if txn_status != "success":
            logger.warning(
                "paystack_verify_not_success",
                reference=reference,
                status=txn_status,
                gateway_response=txn_data.get("gateway_response"),
            )
            return {
                "status": txn_status,
                "amount": Decimal("0"),
                "method": "",
                "receipt_number": None,
                "invoice_number": None,
                "balance_remaining": Decimal("0"),
            }

        # Extract metadata to find our invoice and student
        metadata = txn_data.get("metadata", {})
        invoice_id = metadata.get("invoice_id")
        student_id = metadata.get("student_id")
        tenant_id = metadata.get("tenant_id")

        if not all([invoice_id, student_id, tenant_id]):
            raise OnlinePaymentError(
                "Transaction metadata is missing required fields (invoice_id, student_id, tenant_id)",
                code="INVALID_METADATA",
            )

        # Validate metadata UUIDs are well-formed before using them
        try:
            UUID(invoice_id)
            UUID(student_id)
            UUID(tenant_id)
        except (ValueError, AttributeError):
            raise OnlinePaymentError(
                "Transaction metadata contains malformed identifiers",
                code="INVALID_METADATA",
            )

        # Convert amount from pesewas back to cedis
        amount_cedis = Decimal(str(txn_data["amount"])) / Decimal("100")

        # Determine payment method from Paystack's authorization info
        payment_method = self._resolve_payment_method(txn_data)

        # Determine MoMo phone if applicable
        momo_phone = None
        authorization = txn_data.get("authorization", {})
        if authorization.get("channel") == "mobile_money":
            # Paystack returns the phone in the authorization object for MoMo
            momo_phone = authorization.get("mobile_money_number") or metadata.get("phone")

        # Idempotency re-check after Paystack call (another request may have
        # recorded the payment between our first check and now)
        existing = await self._find_payment_by_reference(reference, tenant_id=UUID(tenant_id))
        if existing:
            return await self._build_verify_response(existing, tenant_id=UUID(tenant_id))

        # Record the payment using the existing PaymentService pattern
        payment_svc = PaymentService(self.db)
        try:
            payment = await payment_svc.record_payment(
                tenant_id=UUID(tenant_id),
                school_id=await self._get_student_school_id(UUID(tenant_id), UUID(student_id)),
                student_id=UUID(student_id),
                amount=amount_cedis,
                payment_method=payment_method.value,
                invoice_id=UUID(invoice_id),
                payment_date=datetime.now(UTC),
                payer_name=txn_data.get("customer", {}).get("first_name"),
                payer_phone=momo_phone,
                payer_email=txn_data.get("customer", {}).get("email"),
                notes=f"Online payment via Paystack (ref: {reference})",
                momo_phone=momo_phone,
                momo_transaction_id=reference,
                bank_reference=reference,
            )
        except FinanceServiceError as e:
            raise OnlinePaymentError(
                f"Failed to record payment: {e.message}",
                code="RECORD_FAILED",
            ) from e

        # Log to finance audit trail
        audit_svc = FinanceAuditService(self.db)
        await audit_svc.log(
            tenant_id=UUID(tenant_id),
            entity_type="payment",
            entity_id=payment.id,
            action="payment",
            performed_by=UUID(student_id),  # Parent portal: use student ID as actor
            metadata={
                "source": "paystack",
                "reference": reference,
                "channel": authorization.get("channel", "unknown"),
                "invoice_id": invoice_id,
                "amount": str(amount_cedis),
                "currency": "GHS",
                "paystack_id": str(txn_data.get("id", "")),
            },
        )

        logger.info(
            "paystack_payment_recorded",
            reference=reference,
            payment_id=str(payment.id),
            receipt_number=payment.receipt_number,
            amount=str(amount_cedis),
            invoice_id=invoice_id,
        )

        # Best-effort: notify the student's parents that a payment was received.
        # Notification failure must never break the payment flow -- the payment
        # is already recorded and the invoice updated at this point.
        invoice_number = metadata.get("invoice_number", "N/A")
        try:
            from app.services.notification_dispatcher import NotificationDispatcher
            dispatcher = NotificationDispatcher(self.db)
            await dispatcher.dispatch_to_parents_of_student(
                student_id=UUID(student_id),
                tenant_id=UUID(tenant_id),
                title="Payment Received",
                body=f"Payment of GHS {amount_cedis} received for invoice {invoice_number}. Receipt: {payment.receipt_number}",
                category="finance",
                priority="normal",
            )
        except Exception:
            logger.warning(
                "payment_notification_dispatch_failed",
                reference=reference,
                exc_info=True,
            )

        return await self._build_verify_response(payment, tenant_id=UUID(tenant_id))

    async def handle_webhook(self, payload_body: bytes, signature: str) -> None:
        """
        Process a Paystack webhook event.

        Verifies the HMAC-SHA512 signature, then dispatches based on
        event type. Currently handles "charge.success" by delegating
        to verify_payment (which is idempotent).

        SECURITY: This method may run on an unscoped DB session (webhooks
        arrive without subdomain context). It extracts tenant_id from the
        transaction metadata and manually sets the DB tenant context before
        recording any payments.

        Args:
            payload_body: Raw request body bytes (for signature verification).
            signature: Value of the X-Paystack-Signature header.

        Raises:
            OnlinePaymentError: If signature verification fails or the
                               event cannot be processed.
        """
        # Use PAYSTACK_WEBHOOK_SECRET if configured, fall back to PAYSTACK_SECRET_KEY
        # (Paystack signs webhooks with the secret key by default)
        secret_key = getattr(settings, "PAYSTACK_WEBHOOK_SECRET", None) or settings.PAYSTACK_SECRET_KEY
        if not secret_key:
            raise OnlinePaymentError(
                "Paystack webhook secret not configured",
                code="CONFIG_ERROR",
            )

        # Verify HMAC-SHA512 signature before trusting the payload
        if not self.verify_webhook_signature(payload_body, signature, secret_key):
            logger.warning("paystack_webhook_invalid_signature")
            raise OnlinePaymentError(
                "Invalid webhook signature",
                code="INVALID_SIGNATURE",
            )

        try:
            payload = json.loads(payload_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise OnlinePaymentError(
                "Malformed webhook payload",
                code="INVALID_PAYLOAD",
            ) from e

        event_type = payload.get("event", "")

        logger.info(
            "paystack_webhook_received",
            event=event_type,
            reference=payload.get("data", {}).get("reference"),
        )

        if event_type == "charge.success":
            reference = payload.get("data", {}).get("reference")
            if not reference:
                raise OnlinePaymentError(
                    "Webhook payload missing transaction reference",
                    code="MISSING_REFERENCE",
                )

            # SECURITY: Webhooks arrive without subdomain context, so the DB
            # session may be unscoped. Extract tenant_id from the transaction
            # metadata (set by us during initiation) and set tenant context
            # before recording any payments.
            webhook_metadata = payload.get("data", {}).get("metadata", {})
            webhook_tenant_id = webhook_metadata.get("tenant_id")
            if webhook_tenant_id:
                try:
                    UUID(webhook_tenant_id)  # Validate it's a real UUID
                    await self.db.execute(
                        text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                        {"tenant_id": webhook_tenant_id},
                    )
                except (ValueError, Exception) as exc:
                    logger.error(
                        "paystack_webhook_tenant_context_failed",
                        tenant_id=webhook_tenant_id,
                        error=str(exc),
                    )
                    raise OnlinePaymentError(
                        "Unable to process webhook: tenant context unavailable",
                        code="CONFIG_ERROR",
                    ) from exc
            else:
                logger.error(
                    "paystack_webhook_missing_tenant_id",
                    reference=reference,
                )
                raise OnlinePaymentError(
                    "Unable to process webhook: missing tenant context in metadata",
                    code="INVALID_METADATA",
                )

            # verify_payment is idempotent, safe to call from both
            # webhook and callback
            await self.verify_payment(reference)

        # We intentionally ignore other event types (refund.*, transfer.*, etc.)
        # since we only handle charge.success for now. Future expansion can
        # add handlers for charge.failed, refund.processed, etc.

    @staticmethod
    def verify_webhook_signature(
        payload_body: bytes, signature: str, secret_key: str
    ) -> bool:
        """
        Verify Paystack webhook HMAC-SHA512 signature.

        Uses hmac.compare_digest for timing-safe comparison to prevent
        timing side-channel attacks.

        Args:
            payload_body: Raw request body bytes.
            signature: The X-Paystack-Signature header value.
            secret_key: The Paystack secret key used to sign webhooks.

        Returns:
            True if the signature is valid, False otherwise.
        """
        expected = hmac.new(
            secret_key.encode("utf-8"),
            payload_body,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_reference(self) -> str:
        """
        Generate a unique payment reference.

        Format: SIMS-<16 hex chars> (e.g., SIMS-A1B2C3D4E5F6G7H8).
        The UUID4 base ensures collision resistance across concurrent
        requests without requiring a database round-trip.
        """
        return f"SIMS-{uuid_mod.uuid4().hex[:16].upper()}"

    async def _call_paystack(
        self, method: str, path: str, data: Optional[dict] = None
    ) -> dict:
        """
        Make an authenticated request to the Paystack API.

        Uses httpx async client with a short timeout to avoid blocking
        the event loop on slow Paystack responses. Raises
        OnlinePaymentError on any HTTP or network failure.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (e.g., "/transaction/initialize").
            data: JSON payload for POST/PUT requests.

        Returns:
            Parsed JSON response dict from Paystack.

        Raises:
            OnlinePaymentError: On network errors or non-2xx responses.
        """
        secret_key = settings.PAYSTACK_SECRET_KEY
        if not secret_key:
            raise OnlinePaymentError(
                "Paystack secret key not configured. Set PAYSTACK_SECRET_KEY in environment.",
                code="CONFIG_ERROR",
            )

        url = f"{self.PAYSTACK_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    resp = await client.post(url, headers=headers, json=data)
                else:
                    raise OnlinePaymentError(
                        f"Unsupported HTTP method: {method}",
                        code="INTERNAL_ERROR",
                    )

            if resp.status_code >= 400:
                # Log the full error for debugging, but never forward raw
                # Paystack messages to the client (may contain internal details)
                logger.error(
                    "paystack_api_error",
                    status_code=resp.status_code,
                    path=path,
                    response_body=resp.text[:500],
                )

                raise OnlinePaymentError(
                    "Payment could not be processed. Please try again or contact support.",
                    code="GATEWAY_ERROR",
                )

            result = resp.json()

            if not result.get("status"):
                logger.warning(
                    "paystack_unsuccessful_response",
                    path=path,
                    message=result.get("message", ""),
                )
                raise OnlinePaymentError(
                    "Payment could not be processed. Please try again or contact support.",
                    code="GATEWAY_ERROR",
                )

            return result

        except httpx.TimeoutException as e:
            logger.error("paystack_timeout", path=path)
            raise OnlinePaymentError(
                "Payment gateway timed out. Please try again.",
                code="GATEWAY_TIMEOUT",
            ) from e
        except httpx.RequestError as e:
            logger.error("paystack_network_error", path=path, error=str(e))
            raise OnlinePaymentError(
                "Unable to reach payment gateway. Please try again later.",
                code="GATEWAY_UNREACHABLE",
            ) from e

    async def _get_payable_invoice(
        self, tenant_id: UUID, student_id: UUID, invoice_id: UUID
    ) -> Invoice:
        """
        Fetch and validate an invoice for online payment.

        Ensures the invoice exists, belongs to the correct tenant and
        student, is in a payable status, and has an outstanding balance.

        Args:
            tenant_id: Tenant ID for defense-in-depth.
            student_id: Expected student on the invoice (IDOR check).
            invoice_id: The invoice to pay.

        Returns:
            The validated Invoice ORM object.

        Raises:
            OnlinePaymentError: If validation fails.
        """
        result = await self.db.execute(
            select(Invoice).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Invoice.tenant_id == tenant_id,
                    Invoice.id == invoice_id,
                    Invoice.deleted_at.is_(None),
                )
            )
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise OnlinePaymentError(
                "Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        # IDOR check: verify the invoice belongs to the student
        if invoice.student_id != student_id:
            logger.warning(
                "paystack_idor_attempt",
                invoice_id=str(invoice_id),
                expected_student=str(student_id),
                actual_student=str(invoice.student_id),
            )
            raise OnlinePaymentError(
                "Invoice not found",
                code="INVOICE_NOT_FOUND",
            )

        # Only issued, partial, or overdue invoices can be paid
        payable_statuses = {
            InvoiceStatus.ISSUED,
            InvoiceStatus.PARTIAL,
            InvoiceStatus.OVERDUE,
        }
        if invoice.status not in payable_statuses:
            raise OnlinePaymentError(
                f"Invoice cannot be paid (status: {invoice.status.value})",
                code="INVOICE_NOT_PAYABLE",
            )

        # Must have an outstanding balance
        outstanding = invoice.total_amount - invoice.amount_paid
        if outstanding <= Decimal("0"):
            raise OnlinePaymentError(
                "Invoice has no outstanding balance",
                code="INVOICE_FULLY_PAID",
            )

        return invoice

    async def _find_payment_by_reference(
        self, reference: str, tenant_id: Optional[UUID] = None
    ) -> Optional[Payment]:
        """
        Look up an existing payment by its Paystack reference.

        We store the Paystack reference in both bank_reference and
        momo_transaction_id on the Payment model. Checking bank_reference
        is sufficient since we always set it for Paystack transactions.

        Args:
            reference: The Paystack transaction reference.
            tenant_id: Tenant ID for defense-in-depth (optional for initial
                       idempotency check when tenant_id is not yet known).

        Returns:
            The existing Payment if found, None otherwise.
        """
        conditions = [
            Payment.bank_reference == reference,
            Payment.is_voided == False,
        ]
        # Defense-in-depth: filter by tenant_id when available
        if tenant_id is not None:
            conditions.append(Payment.tenant_id == tenant_id)

        result = await self.db.execute(
            select(Payment).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def _get_student_school_id(self, tenant_id: UUID, student_id: UUID) -> UUID:
        """
        Fetch the school_id for a student.

        The PaymentService.record_payment requires a school_id. We fetch
        it from the student record rather than trusting client input.

        Args:
            tenant_id: Tenant ID for defense-in-depth.
            student_id: The student whose school_id we need.

        Returns:
            The student's school_id.

        Raises:
            OnlinePaymentError: If the student is not found or has no school.
        """
        result = await self.db.execute(
            select(Student.school_id).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        school_id = result.scalar_one_or_none()

        if not school_id:
            raise OnlinePaymentError(
                "Student not found or has no school assigned",
                code="STUDENT_NOT_FOUND",
            )

        return school_id

    async def _build_verify_response(
        self, payment: Payment, tenant_id: Optional[UUID] = None
    ) -> dict:
        """
        Build a standardized verification response from a Payment record.

        Loads the associated invoice to include the invoice number and
        remaining balance in the response.

        Args:
            payment: The recorded Payment ORM object.
            tenant_id: Tenant ID for defense-in-depth on the invoice lookup.

        Returns:
            dict matching the PaymentVerifyResponse schema.
        """
        invoice_number = None
        balance_remaining = Decimal("0")

        if payment.invoice_id:
            conditions = [
                Invoice.id == payment.invoice_id,
                Invoice.deleted_at.is_(None),
            ]
            # Defense-in-depth: filter by tenant_id when available
            if tenant_id is not None:
                conditions.append(Invoice.tenant_id == tenant_id)

            inv_result = await self.db.execute(
                select(Invoice).where(and_(*conditions))
            )
            invoice = inv_result.scalar_one_or_none()
            if invoice:
                invoice_number = invoice.invoice_number
                balance_remaining = invoice.total_amount - invoice.amount_paid

        return {
            "status": "success",
            "amount": payment.amount,
            "method": payment.payment_method.value,
            "receipt_number": payment.receipt_number,
            "invoice_number": invoice_number,
            "balance_remaining": max(balance_remaining, Decimal("0")),
        }

    @staticmethod
    def _resolve_payment_method(txn_data: dict) -> PaymentMethod:
        """
        Determine the PaymentMethod enum value from Paystack transaction data.

        Paystack returns authorization.channel ("card", "mobile_money", "bank")
        and for mobile money, the bank name indicates the MoMo provider
        (e.g., "MTN Mobile Money", "Vodafone Cash", "AirtelTigo Money").

        Args:
            txn_data: The "data" object from Paystack's verify response.

        Returns:
            The resolved PaymentMethod enum value.
        """
        authorization = txn_data.get("authorization", {})
        channel = authorization.get("channel", "card")

        if channel == "mobile_money":
            # Refine by MoMo provider using the bank name from Paystack
            bank_name = (authorization.get("bank") or "").lower()
            if "mtn" in bank_name:
                return PaymentMethod.MOMO_MTN
            elif "vodafone" in bank_name:
                return PaymentMethod.MOMO_VODAFONE
            elif "airteltigo" in bank_name or "airtel" in bank_name:
                return PaymentMethod.MOMO_AIRTELTIGO
            # Fallback to MTN as the most common provider in Ghana
            return PaymentMethod.MOMO_MTN

        if channel == "bank":
            return PaymentMethod.BANK_TRANSFER

        # Default to card for "card" channel or anything unexpected
        return PaymentMethod.CARD

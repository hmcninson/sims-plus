"""
SIMS Plus - Subscription Enforcement Service

Checks plan limits (student count, user accounts, SMS) and feature access
before allowing creation of new resources. Also handles upgrade cost
calculation and Paystack payment initiation.

Pricing model: per-student, per-term (not flat rate).
See docs/SIMS_Plus_Subscription_Tiers.md for full details.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants.subscription import (
    ADDON_PRICING_PER_TERM,
    AVAILABLE_ADDONS_BY_TIER,
    FEATURE_TIER_REQUIREMENTS,
    MAX_STUDENTS_BY_TIER,
    MAX_USERS_BY_TIER,
    PLAN_FEATURES,
    PRICE_PER_STUDENT_PER_TERM,
    PRICE_PER_STUDENT_PER_YEAR,
    SMS_LIMIT_BY_TIER,
    TERM_DURATION_DAYS,
    UNLIMITED,
    VALID_ADDONS,
    YEAR_DURATION_DAYS,
)
from app.models.student import Student
from app.models.tenant import SubscriptionTier, Tenant, TenantStatus
from app.models.user import User

logger = structlog.get_logger()


# ============================================================================
# Custom Exceptions
# ============================================================================


class SubscriptionError(Exception):
    """Base class for subscription-related errors."""

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class LimitExceededError(SubscriptionError):
    """Raised when a plan limit is reached."""

    pass


class FeatureNotAvailableError(SubscriptionError):
    """Raised when accessing a feature not in the current plan."""

    pass


# ============================================================================
# Subscription Service
# ============================================================================


def _advisory_lock_key(tenant_id: UUID, resource: str) -> int:
    """
    Deterministic advisory lock key from tenant_id + resource.

    Uses MD5 (not Python's hash()) because hash() is randomized across
    processes (PYTHONHASHSEED) and would cause lock misses in multi-worker
    deployments (e.g. gunicorn with multiple workers).
    """
    h = hashlib.md5(f"{tenant_id}_{resource}".encode()).hexdigest()
    return int(h[:15], 16)


class SubscriptionService:
    """Service for subscription limit checks, feature gating, and payments."""

    PAYSTACK_BASE_URL = "https://api.paystack.co"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_tenant(self, tenant_id: UUID) -> Tenant:
        """Fetch tenant or raise."""
        tenant = await self.db.get(Tenant, tenant_id)
        if not tenant:
            raise SubscriptionError("Tenant not found", "TENANT_NOT_FOUND")
        return tenant

    # ========================================================================
    # STUDENT LIMIT (H2: advisory lock for atomicity)
    # ========================================================================

    async def check_student_limit(self, tenant_id: UUID, additional: int = 1) -> None:
        """
        Check if adding `additional` students would exceed the plan limit.

        Uses pg_advisory_xact_lock to prevent TOCTOU race conditions under
        concurrent student creation (H2).
        """
        tenant = await self._get_tenant(tenant_id)
        max_students = MAX_STUDENTS_BY_TIER.get(tenant.subscription_tier, 100)

        if max_students >= UNLIMITED:
            return  # Unlimited tier

        # Advisory lock keyed on tenant + resource type to serialize concurrent checks
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _advisory_lock_key(tenant_id, "student_limit")},
        )

        count = (
            await self.db.scalar(
                select(func.count(Student.id)).where(
                    Student.tenant_id == tenant_id,
                    Student.status.in_(["active", "inactive"]),
                    Student.deleted_at.is_(None),
                )
            )
            or 0
        )

        if count + additional > max_students:
            raise LimitExceededError(
                message=(
                    f"Student limit reached. Your {tenant.subscription_tier.value} plan "
                    f"allows {max_students} students (current: {count}). "
                    f"Upgrade your plan to add more students."
                ),
                code="STUDENT_LIMIT_EXCEEDED",
            )

    # ========================================================================
    # USER ACCOUNT LIMIT (H2: advisory lock)
    # ========================================================================

    async def check_user_limit(self, tenant_id: UUID, additional: int = 1) -> None:
        """
        Check if adding `additional` user accounts would exceed the plan limit.

        Uses pg_advisory_xact_lock to prevent TOCTOU race conditions.
        """
        tenant = await self._get_tenant(tenant_id)
        max_users = MAX_USERS_BY_TIER.get(tenant.subscription_tier, 10)

        if max_users >= UNLIMITED:
            return  # Unlimited tier

        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _advisory_lock_key(tenant_id, "user_limit")},
        )

        count = (
            await self.db.scalar(
                select(func.count(User.id)).where(
                    User.tenant_id == tenant_id,
                    User.status.in_(["active", "pending"]),
                    User.deleted_at.is_(None),
                )
            )
            or 0
        )

        if count + additional > max_users:
            raise LimitExceededError(
                message=(
                    f"User account limit reached. Your {tenant.subscription_tier.value} plan "
                    f"allows {max_users} user accounts (current: {count}). "
                    f"Upgrade your plan to add more."
                ),
                code="USER_LIMIT_EXCEEDED",
            )

    # ========================================================================
    # SMS LIMIT (Monthly) (H2: advisory lock)
    # ========================================================================

    async def check_sms_limit(self, tenant_id: UUID, count: int = 1) -> None:
        """
        Check if sending `count` SMS messages would exceed the monthly limit.

        Uses pg_advisory_xact_lock to prevent TOCTOU race conditions.
        """
        tenant = await self._get_tenant(tenant_id)
        monthly_limit = SMS_LIMIT_BY_TIER.get(tenant.subscription_tier, 50)

        if monthly_limit >= UNLIMITED:
            return  # Unlimited tier

        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _advisory_lock_key(tenant_id, "sms_limit")},
        )

        # Count SMS sent this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        from app.models.sms import SMSLog

        sent_this_month = (
            await self.db.scalar(
                select(func.count(SMSLog.id)).where(
                    SMSLog.tenant_id == tenant_id,
                    SMSLog.created_at >= month_start,
                    SMSLog.status.in_(["sent", "pending"]),
                )
            )
            or 0
        )

        if sent_this_month + count > monthly_limit:
            remaining = max(0, monthly_limit - sent_this_month)
            raise LimitExceededError(
                message=(
                    f"SMS limit reached. Your {tenant.subscription_tier.value} plan "
                    f"allows {monthly_limit} SMS/month ({remaining} remaining). "
                    f"Upgrade for more SMS capacity."
                ),
                code="SMS_LIMIT_EXCEEDED",
            )

    # ========================================================================
    # FEATURE ACCESS (H4: add-on expiry check)
    # ========================================================================

    async def check_feature_access(self, tenant_id: UUID, feature: str) -> None:
        """
        Check if a feature is available on the tenant's current plan.

        Resolution order:
        1. tenant.features JSONB (admin overrides & purchased add-ons)
           — for add-ons, checks expiry date if stored as dict with expires_at (H4)
        2. PLAN_FEATURES defaults for the subscription tier
        """
        tenant = await self._get_tenant(tenant_id)

        # 1. Check tenant-level override first (admin grants & purchased add-ons)
        tenant_features = tenant.features or {}
        if feature in tenant_features:
            feature_val = tenant_features[feature]

            # H4: Support expiry-aware add-on format: {"enabled": true, "expires_at": "..."}
            if isinstance(feature_val, dict):
                if feature_val.get("enabled"):
                    expires_at = feature_val.get("expires_at")
                    if expires_at:
                        try:
                            expiry = datetime.fromisoformat(expires_at)
                            if datetime.now(timezone.utc) > expiry:
                                # Add-on expired — fall through to plan check
                                pass
                            else:
                                return  # Active add-on
                        except (ValueError, TypeError):
                            return  # Malformed date, treat as enabled
                    else:
                        return  # No expiry, treat as permanent
            elif feature_val:
                return  # Simple boolean True

        # 2. Fall back to plan defaults
        plan_defaults = PLAN_FEATURES.get(tenant.subscription_tier, {})
        feature_status = plan_defaults.get(feature, False)

        if feature_status is True:
            return  # Included in plan

        if feature_status == "addon":
            raise FeatureNotAvailableError(
                message=(
                    f"The {feature.replace('_', ' ')} feature is available as an add-on "
                    f"on the Professional plan. Purchase it in Settings > Subscription, "
                    f"or upgrade to Enterprise where it's included."
                ),
                code="ADDON_NOT_PURCHASED",
            )

        # Not available on this tier
        required_tier = FEATURE_TIER_REQUIREMENTS.get(feature, "a higher")
        raise FeatureNotAvailableError(
            message=(
                f"The {feature.replace('_', ' ')} feature requires "
                f"the {required_tier} plan or higher."
            ),
            code="FEATURE_NOT_AVAILABLE",
        )

    # ========================================================================
    # COST CALCULATION
    # ========================================================================

    async def _count_active_students(self, tenant_id: UUID) -> int:
        """Count active/inactive (enrolled) students for billing purposes."""
        return (
            await self.db.scalar(
                select(func.count(Student.id)).where(
                    Student.tenant_id == tenant_id,
                    Student.status.in_(["active", "inactive"]),
                    Student.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def calculate_upgrade_cost(
        self,
        tenant_id: UUID,
        target_tier: SubscriptionTier,
        billing_period: str,
        addons: list[str] | None = None,
    ) -> dict:
        """
        Calculate the total cost for upgrading to a target tier.

        Returns a detailed breakdown including per-student pricing,
        add-on costs, and totals in both pesewas and GHS.
        """
        student_count = await self._count_active_students(tenant_id)

        # Use at least 1 student for pricing (minimum charge)
        billable_students = max(student_count, 1)

        if billing_period == "year":
            price_map = PRICE_PER_STUDENT_PER_YEAR
        else:
            price_map = PRICE_PER_STUDENT_PER_TERM

        price_per_student = price_map.get(target_tier, 0)
        subtotal = billable_students * price_per_student

        # Add-on costs
        addon_total = 0
        addon_breakdown = []
        if addons:
            for addon in addons:
                addon_price = ADDON_PRICING_PER_TERM.get(addon, 0)
                if billing_period == "year":
                    # 3 terms with 10% annual discount
                    addon_price = int(addon_price * 3 * 0.9)
                addon_total += addon_price
                addon_breakdown.append({"name": addon, "amount": addon_price})

        total = subtotal + addon_total

        return {
            "student_count": student_count,
            "billable_students": billable_students,
            "price_per_student": price_per_student,
            "subtotal": subtotal,
            "addon_total": addon_total,
            "total": total,
            "total_ghs": total / 100,
            "billing_period": billing_period,
            "tier": target_tier.value,
            "breakdown": [
                {
                    "description": (
                        f"{billable_students} students x "
                        f"GHS {price_per_student / 100:.2f}/{billing_period}"
                    ),
                    "amount": subtotal,
                },
                *addon_breakdown,
            ],
        }

    # ========================================================================
    # PAYSTACK PAYMENT INITIATION (H1: uses SubscriptionIntent)
    # ========================================================================

    async def initiate_upgrade(
        self,
        tenant_id: UUID,
        target_tier: SubscriptionTier,
        billing_period: str,
        payer_email: str,
        callback_url: str,
        addons: list[str] | None = None,
    ) -> dict:
        """
        Initiate a Paystack payment for a subscription upgrade.

        Creates a SubscriptionIntent record for webhook validation (H1),
        calculates total based on active student count, then creates
        a Paystack transaction.
        """
        cost = await self.calculate_upgrade_cost(
            tenant_id, target_tier, billing_period, addons
        )

        if cost["total"] <= 0:
            raise SubscriptionError("Cannot process zero-amount payment", "ZERO_AMOUNT")

        # M5: Validate callback URL domain
        self._validate_callback_url(callback_url)

        reference = (
            f"sub_{tenant_id}_{target_tier.value}_{billing_period}_"
            f"{int(datetime.now(timezone.utc).timestamp())}"
        )
        duration_days = YEAR_DURATION_DAYS if billing_period == "year" else TERM_DURATION_DAYS

        # H1: Store intent for webhook validation
        from app.models.subscription_intent import SubscriptionIntent

        intent = SubscriptionIntent(
            tenant_id=tenant_id,
            reference=reference,
            target_tier=target_tier.value,
            amount=cost["total"],
            billing_period=billing_period,
            intent_type="upgrade",
            status="pending",
        )
        self.db.add(intent)
        await self.db.flush()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.PAYSTACK_BASE_URL}/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": payer_email,
                    "amount": cost["total"],
                    "currency": "GHS",
                    "reference": reference,
                    "callback_url": callback_url,
                    "metadata": {
                        "tenant_id": str(tenant_id),
                        "target_tier": target_tier.value,
                        "billing_period": billing_period,
                        "duration_days": duration_days,
                        "student_count": cost["student_count"],
                        "addons": addons or [],
                        "type": "subscription_upgrade",
                    },
                },
            )

            data = response.json()
            if not data.get("status"):
                # Mark intent as failed
                intent.status = "failed"
                await self.db.flush()
                # Log Paystack error internally but return generic message to client
                logger.error(
                    "paystack_upgrade_init_failed",
                    paystack_message=data.get("message"),
                    reference=reference,
                )
                raise SubscriptionError(
                    "Payment initiation failed. Please try again later.",
                    "PAYSTACK_ERROR",
                )

            return {
                "authorization_url": data["data"]["authorization_url"],
                "reference": data["data"]["reference"],
                "access_code": data["data"]["access_code"],
                "cost": cost,
            }

    async def initiate_addon_purchase(
        self,
        tenant_id: UUID,
        addons: list[str],
        billing_period: str,
        payer_email: str,
        callback_url: str,
    ) -> dict:
        """
        Initiate a Paystack payment for add-on purchase (C6: separate from upgrade).

        Does NOT touch subscription dates — only enables features in tenant.features.
        """
        self._validate_callback_url(callback_url)

        # Defense-in-depth: validate addon names even though schema validates too
        for addon in addons:
            if addon not in VALID_ADDONS:
                raise SubscriptionError(f"Invalid add-on: {addon}", "INVALID_ADDON")

        # Calculate add-on cost only (no per-student charges)
        addon_total = 0
        addon_breakdown = []
        for addon in addons:
            addon_price = ADDON_PRICING_PER_TERM.get(addon, 0)
            if billing_period == "year":
                addon_price = int(addon_price * 3 * 0.9)
            addon_total += addon_price
            addon_breakdown.append({"name": addon, "amount": addon_price})

        if addon_total <= 0:
            raise SubscriptionError("No valid add-ons selected", "NO_ADDONS")

        reference = (
            f"addon_{tenant_id}_{'_'.join(addons)}_"
            f"{int(datetime.now(timezone.utc).timestamp())}"
        )

        # H1: Store intent for webhook validation
        from app.models.subscription_intent import SubscriptionIntent

        intent = SubscriptionIntent(
            tenant_id=tenant_id,
            reference=reference,
            target_tier="addon",
            amount=addon_total,
            billing_period=billing_period,
            intent_type="addon_purchase",
            addon_name=",".join(addons),
            status="pending",
        )
        self.db.add(intent)
        await self.db.flush()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.PAYSTACK_BASE_URL}/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": payer_email,
                    "amount": addon_total,
                    "currency": "GHS",
                    "reference": reference,
                    "callback_url": callback_url,
                    "metadata": {
                        "tenant_id": str(tenant_id),
                        "addons": addons,
                        "billing_period": billing_period,
                        "type": "addon_purchase",
                    },
                },
            )

            data = response.json()
            if not data.get("status"):
                intent.status = "failed"
                await self.db.flush()
                # Log Paystack error internally but return generic message to client
                logger.error(
                    "paystack_addon_init_failed",
                    paystack_message=data.get("message"),
                    reference=reference,
                )
                raise SubscriptionError(
                    "Payment initiation failed. Please try again later.",
                    "PAYSTACK_ERROR",
                )

            return {
                "authorization_url": data["data"]["authorization_url"],
                "reference": data["data"]["reference"],
                "access_code": data["data"]["access_code"],
                "cost": {
                    "student_count": 0,
                    "billable_students": 0,
                    "price_per_student": 0,
                    "subtotal": 0,
                    "addon_total": addon_total,
                    "total": addon_total,
                    "total_ghs": addon_total / 100,
                    "billing_period": billing_period,
                    "tier": "addon",
                    "breakdown": addon_breakdown,
                },
            }

    # ========================================================================
    # WEBHOOK HANDLER (H1, H5, H6, C6)
    # ========================================================================

    async def handle_webhook(self, payload_body: bytes, signature: str) -> None:
        """
        Handle Paystack webhook for subscription payments.

        Verifies HMAC-SHA512 signature, validates against stored intent (H1),
        checks idempotency (H5), and upgrades tenant or enables add-ons.
        No explicit db.commit() — caller's dependency handles it (H6).
        """
        # Verify HMAC-SHA512 signature
        webhook_secret = settings.PAYSTACK_WEBHOOK_SECRET or settings.PAYSTACK_SECRET_KEY
        expected = hmac.new(
            webhook_secret.encode(),
            payload_body,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("subscription_webhook_invalid_signature")
            raise SubscriptionError("Invalid webhook signature", "INVALID_SIGNATURE")

        payload = json.loads(payload_body)
        event = payload.get("event")

        if event != "charge.success":
            return  # Only process successful charges

        data = payload.get("data", {})
        metadata = data.get("metadata", {})
        reference = data.get("reference", "")
        payment_type = metadata.get("type")

        if payment_type not in ("subscription_upgrade", "addon_purchase"):
            return  # Not a subscription-related payment

        # H1: Validate against stored intent
        from app.models.subscription_intent import SubscriptionIntent

        intent_result = await self.db.execute(
            select(SubscriptionIntent).where(
                SubscriptionIntent.reference == reference
            )
        )
        intent = intent_result.scalar_one_or_none()

        if not intent:
            logger.warning(
                "subscription_webhook_no_intent",
                reference=reference,
            )
            raise SubscriptionError("No matching intent found", "NO_INTENT")

        # H5: Idempotency — skip if already processed
        if intent.status == "completed":
            logger.info(
                "subscription_webhook_already_processed",
                reference=reference,
            )
            return

        # Validate intent matches metadata
        tenant_id = UUID(metadata["tenant_id"])
        if intent.tenant_id != tenant_id:
            logger.warning(
                "subscription_webhook_tenant_mismatch",
                intent_tenant=str(intent.tenant_id),
                metadata_tenant=str(tenant_id),
            )
            raise SubscriptionError("Intent tenant mismatch", "TENANT_MISMATCH")

        # Validate payment amount matches intent (security: prevent underpayment attacks)
        paid_amount = data.get("amount", 0)  # Paystack sends amount in pesewas
        if intent.amount and paid_amount < intent.amount:
            logger.warning(
                "subscription_webhook_amount_mismatch",
                expected=intent.amount,
                received=paid_amount,
                reference=reference,
            )
            intent.status = "failed"
            await self.db.flush()
            raise SubscriptionError("Payment amount mismatch", "AMOUNT_MISMATCH")

        tenant = await self.db.get(Tenant, tenant_id)
        if not tenant:
            logger.error("subscription_webhook_tenant_not_found", tenant_id=str(tenant_id))
            intent.status = "failed"
            await self.db.flush()
            return

        now = datetime.now(timezone.utc)

        if payment_type == "subscription_upgrade":
            await self._process_upgrade(tenant, intent, metadata, now)
        elif payment_type == "addon_purchase":
            # C6: Separate path — only enable add-ons, don't touch subscription dates
            await self._process_addon_purchase(tenant, intent, metadata, now)

        # Mark intent as completed (H5: prevents reprocessing)
        intent.status = "completed"
        await self.db.flush()

        logger.info(
            "subscription_webhook_processed",
            tenant_id=str(tenant_id),
            reference=reference,
            type=payment_type,
        )

    async def _process_upgrade(
        self,
        tenant: Tenant,
        intent,
        metadata: dict,
        now: datetime,
    ) -> None:
        """Process a subscription upgrade payment."""
        target_tier = SubscriptionTier(metadata["target_tier"])
        billing_period = metadata["billing_period"]
        duration_days = int(metadata["duration_days"])
        addons = metadata.get("addons", [])

        # Upgrade tenant
        tenant.subscription_tier = target_tier
        tenant.status = TenantStatus.ACTIVE
        tenant.subscription_start = now.date()
        tenant.subscription_end = (now + timedelta(days=duration_days)).date()

        # Update limits based on tier (C4: use sentinel for unlimited)
        tenant.max_students = MAX_STUDENTS_BY_TIER.get(target_tier, 100)
        tenant.max_staff = MAX_USERS_BY_TIER.get(target_tier, 10)

        # Enable purchased add-ons in features JSONB (H4: with expiry)
        if addons:
            features = tenant.features or {}
            addon_expires = (now + timedelta(days=duration_days)).isoformat()
            for addon in addons:
                features[addon] = {
                    "enabled": True,
                    "expires_at": addon_expires,
                    "purchased_at": now.isoformat(),
                }
            tenant.features = features

        await self.db.flush()

        logger.info(
            "subscription_upgraded",
            tenant_id=str(tenant.id),
            tier=target_tier.value,
            billing_period=billing_period,
            subscription_end=str(tenant.subscription_end),
            addons=addons,
        )

    async def _process_addon_purchase(
        self,
        tenant: Tenant,
        intent,
        metadata: dict,
        now: datetime,
    ) -> None:
        """Process an add-on purchase (C6: does NOT reset subscription dates)."""
        addons = metadata.get("addons", [])
        billing_period = metadata.get("billing_period", "term")

        duration_days = YEAR_DURATION_DAYS if billing_period == "year" else TERM_DURATION_DAYS
        addon_expires = (now + timedelta(days=duration_days)).isoformat()

        features = tenant.features or {}
        for addon in addons:
            features[addon] = {
                "enabled": True,
                "expires_at": addon_expires,
                "purchased_at": now.isoformat(),
            }
        tenant.features = features

        await self.db.flush()

        logger.info(
            "addon_purchased",
            tenant_id=str(tenant.id),
            addons=addons,
            expires_at=addon_expires,
        )

    # ========================================================================
    # HELPERS
    # ========================================================================

    @staticmethod
    def _validate_callback_url(callback_url: str) -> None:
        """
        Validate callback URL domain (M5).

        Only allows simsplus.io subdomains and localhost in development.
        """
        from urllib.parse import urlparse

        parsed = urlparse(callback_url)
        host = parsed.hostname or ""

        allowed = host.endswith(".simsplus.io") or host == "simsplus.io"

        if settings.is_development:
            allowed = allowed or host in ("localhost", "127.0.0.1")

        if not allowed:
            raise SubscriptionError(
                "Callback URL must be on the simsplus.io domain",
                "INVALID_CALLBACK_URL",
            )

        # Require HTTPS in production
        if not settings.is_development and parsed.scheme != "https":
            raise SubscriptionError(
                "Callback URL must use HTTPS",
                "INVALID_CALLBACK_URL",
            )

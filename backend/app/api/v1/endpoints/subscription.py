"""
SIMS Plus - Subscription Management Endpoints

Provides subscription status, upgrade checkout (Paystack), add-on purchases,
and webhook handling for payment confirmation.

NOTE: Do NOT use `from __future__ import annotations` — breaks 204 responses.
"""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import (
    DatabaseSession,
    UnscopedDatabaseSession,
    ValidatedUser,
    require_permissions,
)
from app.constants.subscription import (
    AVAILABLE_ADDONS_BY_TIER,
    MAX_STUDENTS_BY_TIER,
    MAX_USERS_BY_TIER,
    SMS_LIMIT_BY_TIER,
    UNLIMITED,
)
from app.models.sms import SMSLog
from app.models.student import Student
from app.models.tenant import SubscriptionTier, Tenant
from app.models.user import User
from app.schemas.subscription import (
    CalculateCostRequest,
    CostBreakdownResponse,
    PurchaseAddonRequest,
    SubscriptionStatusResponse,
    UpgradeRequest,
    UpgradeResponse,
)
from app.services.subscription import SubscriptionError, SubscriptionService

logger = structlog.get_logger()

router = APIRouter(prefix="/subscription", tags=["Subscription"])


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    db: DatabaseSession,
    current_user: ValidatedUser,
):
    """
    Get current tenant's subscription status including plan details,
    usage counts, limits, days remaining, and available features.

    No require_permissions — all authenticated users need trial/subscription
    status for the TrialBanner component. Billing-sensitive actions (upgrade,
    addon purchase) are gated by subscription.manage permission.
    """
    tenant_id = UUID(current_user["tenant_id"])
    tenant = await db.get(Tenant, tenant_id)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Count active students (defense-in-depth: filter by tenant_id)
    student_count = (
        await db.scalar(
            select(func.count(Student.id)).where(
                Student.tenant_id == tenant_id,
                Student.status.in_(["active", "inactive"]),
                Student.deleted_at.is_(None),
            )
        )
        or 0
    )

    # Count active user accounts
    user_count = (
        await db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.status.in_(["active", "pending"]),
                User.deleted_at.is_(None),
            )
        )
        or 0
    )

    # Count SMS sent this month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sms_this_month = (
        await db.scalar(
            select(func.count(SMSLog.id)).where(
                SMSLog.tenant_id == tenant_id,
                SMSLog.created_at >= month_start,
                SMSLog.status.in_(["sent", "pending"]),
            )
        )
        or 0
    )

    # Calculate days remaining
    days_remaining = None
    if tenant.status.value == "trial" and tenant.trial_ends_at:
        delta = tenant.trial_ends_at - now
        days_remaining = max(0, delta.days)
    elif tenant.subscription_end:
        sub_dt = datetime.combine(
            tenant.subscription_end, datetime.min.time(), tzinfo=timezone.utc
        )
        delta = sub_dt - now
        days_remaining = max(0, delta.days)

    tier = tenant.subscription_tier
    max_students = MAX_STUDENTS_BY_TIER.get(tier, 100)
    max_users = MAX_USERS_BY_TIER.get(tier, 10)
    sms_limit = SMS_LIMIT_BY_TIER.get(tier, 50)

    return SubscriptionStatusResponse(
        plan=tier.value,
        status=tenant.status.value,
        trial_ends_at=tenant.trial_ends_at,
        subscription_start=tenant.subscription_start,
        subscription_end=tenant.subscription_end,
        days_remaining=days_remaining,
        max_students=max_students,
        current_student_count=student_count,
        max_users=max_users,
        current_user_count=user_count,
        sms_monthly_limit=sms_limit,
        sms_sent_this_month=sms_this_month,
        features=tenant.features or {},
        available_addons=AVAILABLE_ADDONS_BY_TIER.get(tier, []),
    )


@router.post(
    "/calculate-cost",
    response_model=CostBreakdownResponse,
    dependencies=[Depends(require_permissions("subscription.manage"))],
)
async def calculate_upgrade_cost(
    request_body: CalculateCostRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
):
    """
    Calculate the cost of upgrading to a target tier.

    Returns a detailed breakdown including per-student pricing,
    add-on costs, and totals in both pesewas and GHS.

    Requires subscription.manage permission (admin-only).
    """
    tenant_id = UUID(current_user["tenant_id"])
    service = SubscriptionService(db)

    return await service.calculate_upgrade_cost(
        tenant_id=tenant_id,
        target_tier=SubscriptionTier(request_body.target_tier),
        billing_period=request_body.billing_period,
        addons=request_body.addons,
    )


@router.post(
    "/upgrade",
    response_model=UpgradeResponse,
    dependencies=[Depends(require_permissions("subscription.manage"))],
)
async def initiate_upgrade(
    request_body: UpgradeRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
):
    """
    Initiate a subscription upgrade via Paystack.

    Calculates total based on active student count, creates a Paystack
    transaction, and returns the authorization URL to redirect the user.

    Requires subscription.manage permission (admin-only).
    """
    tenant_id = UUID(current_user["tenant_id"])
    service = SubscriptionService(db)

    try:
        return await service.initiate_upgrade(
            tenant_id=tenant_id,
            target_tier=SubscriptionTier(request_body.target_tier),
            billing_period=request_body.billing_period,
            payer_email=current_user["email"],
            callback_url=request_body.callback_url,
            addons=request_body.addons,
        )
    except SubscriptionError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post(
    "/addon",
    response_model=UpgradeResponse,
    dependencies=[Depends(require_permissions("subscription.manage"))],
)
async def purchase_addon(
    request_body: PurchaseAddonRequest,
    db: DatabaseSession,
    current_user: ValidatedUser,
):
    """
    Purchase an add-on for the current plan (Professional tier).

    C6: Uses a separate intent_type='addon_purchase' so webhook
    does NOT reset subscription dates.
    """
    tenant_id = UUID(current_user["tenant_id"])
    tenant = await db.get(Tenant, tenant_id)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.subscription_tier != SubscriptionTier.PROFESSIONAL:
        raise HTTPException(
            status_code=400,
            detail="Add-ons are only available on the Professional plan",
        )

    service = SubscriptionService(db)

    return await service.initiate_addon_purchase(
        tenant_id=tenant_id,
        addons=request_body.addons,
        billing_period=request_body.billing_period,
        payer_email=current_user["email"],
        callback_url=request_body.callback_url,
    )


@router.post("/webhook/paystack", include_in_schema=False)
async def subscription_webhook(
    request: Request,
    db: UnscopedDatabaseSession,
):
    """
    Paystack webhook handler for subscription payments.

    Uses UnscopedDatabaseSession since there's no subdomain context.
    Tenant is identified from Paystack metadata and validated against
    stored SubscriptionIntent (H1).

    H6: No explicit db.commit() — UnscopedDatabaseSession handles it.
    """
    import json as json_mod

    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    service = SubscriptionService(db)

    try:
        await service.handle_webhook(payload, signature)
    except SubscriptionError as e:
        # Signature and validation failures return 400 so monitoring can alert
        if e.code in ("INVALID_SIGNATURE", "NO_INTENT", "TENANT_MISMATCH", "AMOUNT_MISMATCH"):
            raise HTTPException(status_code=400, detail="Validation failed")
        # Other subscription errors return 200 to prevent Paystack retries
        logger.warning("subscription_webhook_error", code=e.code, message=str(e))
        return {"status": "error", "code": e.code}
    except Exception:
        # Unexpected errors return 200 to prevent Paystack retries
        logger.exception("subscription_webhook_unexpected_error")
        return {"status": "error"}

    # Invalidate tenant cache so enforcement picks up new status immediately
    try:
        data = json_mod.loads(payload)
        metadata = data.get("data", {}).get("metadata", {})
        tenant_id_str = metadata.get("tenant_id")

        if tenant_id_str:
            tenant = await db.get(Tenant, UUID(tenant_id_str))
            if tenant:
                redis_client = getattr(request.app.state, "redis", None)
                if redis_client:
                    from app.middleware.tenant import invalidate_tenant_cache

                    await invalidate_tenant_cache(redis_client, tenant.subdomain)
    except Exception:
        # Cache invalidation failure is not critical — TTL will expire
        logger.warning("subscription_cache_invalidation_failed", exc_info=True)

    # Audit log subscription changes
    # AuditLog does NOT have TenantMixin or RLS — it uses a nullable tenant_id
    # column, so we can write to it from an unscoped session safely.
    try:
        data = json_mod.loads(payload)
        metadata = data.get("data", {}).get("metadata", {})
        payment_type = metadata.get("type")
        tenant_id_str = metadata.get("tenant_id")

        if payment_type and tenant_id_str:
            from app.models.audit_log import AuditLog

            audit = AuditLog(
                action=f"subscription_{payment_type}",
                resource_type="tenant",
                resource_id=UUID(tenant_id_str),
                tenant_id=UUID(tenant_id_str),
                details=json_mod.dumps({
                    "reference": data.get("data", {}).get("reference"),
                    "type": payment_type,
                    "target_tier": metadata.get("target_tier"),
                    "addons": metadata.get("addons"),
                }),
            )
            db.add(audit)
            await db.flush()
    except Exception:
        logger.warning("subscription_audit_log_failed", exc_info=True)

    return {"status": "ok"}

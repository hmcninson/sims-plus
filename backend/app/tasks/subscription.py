"""
SIMS Plus - Subscription Background Tasks

Scheduled via Celery Beat to run daily at 08:00 UTC.
Sends warning notifications at 7 days and 1 day before trial expiration.
"""

import structlog
from datetime import datetime, timezone
from sqlalchemy import select, and_

from sqlalchemy import text

from app.db.session import async_session_maker
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole, UserStatus

logger = structlog.get_logger()

# Warning thresholds (days before expiry, key for dedup)
WARNING_THRESHOLDS = [
    (7, "trial_warning_7d"),
    (1, "trial_warning_1d"),
]


async def check_trial_expirations() -> None:
    """
    Daily task: find trial tenants approaching expiration
    and send warning notifications.

    Uses tenant.features JSONB with _internal. prefix (M8) to
    track which warnings have been sent (avoids duplicate sends).

    Schedule: Run daily at 08:00 UTC via Celery Beat.
    """
    now = datetime.now(timezone.utc)

    async with async_session_maker() as db:
        try:
            # Find all active trial tenants with expiration dates
            result = await db.execute(
                select(Tenant).where(
                    and_(
                        Tenant.status == TenantStatus.TRIAL,
                        Tenant.trial_ends_at.is_not(None),
                        Tenant.is_active.is_(True),
                        Tenant.deleted_at.is_(None),
                    )
                )
            )
            tenants = result.scalars().all()

            warnings_sent = 0
            for tenant in tenants:
                days_until_expiry = (tenant.trial_ends_at - now).days

                for threshold_days, warning_key in WARNING_THRESHOLDS:
                    if days_until_expiry <= threshold_days:
                        # Check if this warning was already sent (M8: _internal. prefix)
                        features = tenant.features or {}
                        last_warning = features.get("_internal.last_trial_warning")

                        if last_warning == warning_key:
                            continue  # Already sent this warning level

                        # Set tenant context so RLS allows querying this tenant's users
                        await db.execute(
                            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                            {"tid": str(tenant.id)},
                        )

                        # Find admin user email for this tenant
                        admin_result = await db.execute(
                            select(User).where(
                                User.tenant_id == tenant.id,
                                User.role.in_([
                                    UserRole.SCHOOL_ADMIN.value,
                                    UserRole.CHAIN_ADMIN.value,
                                ]),
                                User.status == UserStatus.ACTIVE,
                                User.deleted_at.is_(None),
                            ).limit(1)
                        )
                        admin = admin_result.scalar_one_or_none()

                        if admin:
                            await _send_trial_warning(
                                tenant, admin, days_until_expiry
                            )

                        # Mark warning as sent (M8: use _internal. prefix)
                        if not tenant.features:
                            tenant.features = {}
                        tenant.features["_internal.last_trial_warning"] = warning_key
                        await db.flush()

                        warnings_sent += 1
                        logger.info(
                            "trial_warning_sent",
                            tenant_id=str(tenant.id),
                            subdomain=tenant.subdomain,
                            days_remaining=days_until_expiry,
                            warning_type=warning_key,
                        )
                        break  # Only send the most urgent warning

            await db.commit()
            logger.info(
                "trial_expiration_check_complete",
                tenants_checked=len(tenants),
                warnings_sent=warnings_sent,
            )
        except Exception:
            await db.rollback()
            logger.exception("trial_expiration_check_failed")
            raise


async def _send_trial_warning(
    tenant: Tenant, admin: User, days_remaining: int
) -> None:
    """
    Send trial expiration warning via email to the tenant's admin user.

    Uses the existing email service infrastructure.
    """
    try:
        from app.services.email import email_service

        subject = (
            f"Your SIMS Plus trial expires in {days_remaining} day"
            f"{'s' if days_remaining != 1 else ''}"
        )
        body = (
            f"Hi {admin.first_name},\n\n"
            f"Your SIMS Plus trial for {tenant.name} "
            f"{'expires tomorrow' if days_remaining <= 1 else f'expires in {days_remaining} days'}.\n\n"
            f"To continue using SIMS Plus without interruption, upgrade your plan at:\n"
            f"https://{tenant.subdomain}.simsplus.io/settings/subscription\n\n"
            f"After your trial expires, you'll have a 7-day read-only grace period "
            f"before access is fully blocked.\n\n"
            f"Best regards,\nThe SIMS Plus Team"
        )

        await email_service.send_email(
            to_email=admin.email,
            subject=subject,
            body=body,
        )
    except Exception:
        # Email failure should not crash the task
        logger.exception(
            "trial_warning_email_failed",
            tenant_id=str(tenant.id),
            admin_email=admin.email,
        )


# ---------------------------------------------------------------------------
# Celery task wrapper
# ---------------------------------------------------------------------------

from app.celery_app import celery_app  # noqa: E402
from app.tasks.utils import run_async  # noqa: E402


@celery_app.task(name="app.tasks.subscription.check_trial_expirations_task")
def check_trial_expirations_task() -> None:
    """
    Celery beat task: check trial expirations and send warning emails.

    This task manages its own DB session (see check_trial_expirations).
    The tenants table is not RLS-scoped, so no tenant context is needed
    for the initial query. Per-tenant context is set inline when querying
    that tenant's users.
    """
    run_async(check_trial_expirations())

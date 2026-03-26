"""
SIMS Plus - Offer Expiry Task

Daily Celery task that expires unanswered admission offers past their
response_deadline.

Runs daily at 00:00 UTC via Celery Beat.
Uses the platform admin superuser engine to iterate tenants, then
sets tenant context per-tenant in isolated sessions for RLS-scoped queries.

CRITICAL: Each tenant is processed in its own session to prevent
cross-tenant context leaking on error (REVIEW FIX C1).
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_platform_admin_session_maker
from app.models.admissions import (
    AdmissionApplicationStatus,
    AdmissionDecision,
    Application,
    ApplicationStatusHistory,
)
from app.models.tenant import Tenant

logger = structlog.get_logger(__name__)


async def _expire_offers_for_tenant(
    session: AsyncSession,
    tenant_id: str,
) -> int:
    """
    Expire unanswered offers for a single tenant.

    Caller is responsible for setting/clearing tenant context and
    committing/rolling back the session.

    Finds applications where:
    - status = 'offered'
    - decision.response_deadline < today
    - offer_responded_at IS NULL (not yet responded)

    Transitions them to EXPIRED status with audit trail.
    Returns the number of expired offers.
    """
    today = datetime.now(UTC).date()

    # Find offered applications with expired deadlines that have no response
    result = await session.execute(
        select(Application, AdmissionDecision)
        .join(AdmissionDecision, AdmissionDecision.application_id == Application.id)
        .filter(
            # Defense-in-depth: filter by tenant_id on both tables
            Application.tenant_id == tenant_id,
            Application.status == AdmissionApplicationStatus.OFFERED.value,
            Application.offer_responded_at.is_(None),
            Application.deleted_at.is_(None),
            AdmissionDecision.tenant_id == tenant_id,
            AdmissionDecision.response_deadline.isnot(None),
            AdmissionDecision.response_deadline < today,
        )
    )
    rows = result.all()

    expired_count = 0

    for application, decision in rows:
        try:
            old_status = application.status
            application.status = AdmissionApplicationStatus.EXPIRED.value

            # Record status history for audit trail
            history = ApplicationStatusHistory(
                tenant_id=tenant_id,
                application_id=application.id,
                from_status=old_status,
                to_status=AdmissionApplicationStatus.EXPIRED.value,
                changed_by=None,  # System action -- no human actor
                reason=(
                    f"Offer expired: response deadline was "
                    f"{decision.response_deadline.strftime('%d/%m/%Y')}"
                ),
            )
            session.add(history)

            # Send notification to applicant (best effort)
            try:
                from app.services.admissions.notification_service import (
                    AdmissionNotificationService,
                )

                notifier = AdmissionNotificationService(session)
                await notifier.notify_status_change(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    new_status="expired",
                    extra_context={
                        "deadline": decision.response_deadline.strftime("%d/%m/%Y"),
                    },
                )
            except Exception:
                logger.exception(
                    "expiry_notification_failed",
                    application_id=str(application.id),
                )

            expired_count += 1
        except Exception:
            logger.exception(
                "offer_expiry_failed",
                application_id=str(application.id),
                tenant_id=tenant_id,
            )

    return expired_count


async def expire_unanswered_offers() -> dict:
    """
    Main task entry point. Iterates all active tenants and expires
    offers past their response deadline.

    CRITICAL: Uses a separate session per tenant to prevent cross-tenant
    context leaking if one tenant's work fails mid-transaction (C1 fix).

    Returns: { tenants_processed: N, offers_expired: N }
    """
    session_maker = get_platform_admin_session_maker()
    tenants_processed = 0
    total_expired = 0

    # Fetch all active tenants in a read-only session (tenants table has no RLS)
    async with session_maker() as session:
        result = await session.execute(
            select(Tenant.id).filter(
                Tenant.status.in_(["active", "trial"]),
                Tenant.deleted_at.is_(None),
            )
        )
        tenant_ids = [row[0] for row in result.all()]

    # Process each tenant in its own isolated session (C1: session-per-tenant)
    for tid in tenant_ids:
        async with session_maker() as per_tenant_session:
            try:
                await per_tenant_session.execute(
                    text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                    {"tid": str(tid)},
                )
                count = await _expire_offers_for_tenant(
                    per_tenant_session, str(tid)
                )
                await per_tenant_session.commit()
                total_expired += count
                tenants_processed += 1
            except Exception:
                await per_tenant_session.rollback()
                logger.exception(
                    "expiry_tenant_failed",
                    tenant_id=str(tid),
                )
            finally:
                # C1: Always clear tenant context even on error
                try:
                    await per_tenant_session.execute(
                        text("SELECT clear_tenant_context()")
                    )
                except Exception:
                    pass  # Connection may already be closed

    summary = {
        "tenants_processed": tenants_processed,
        "offers_expired": total_expired,
    }
    logger.info("offer_expiry_complete", **summary)
    return summary


# ---------------------------------------------------------------------------
# Celery task wrapper
# ---------------------------------------------------------------------------

from app.celery_app import celery_app  # noqa: E402
from app.tasks.utils import run_async  # noqa: E402


@celery_app.task(
    name="app.tasks.offer_expiry.expire_unanswered_offers_task",
)
def expire_unanswered_offers_task() -> dict:
    """
    Celery beat task: expire unanswered admission offers past their
    response deadline.

    Runs daily at 00:00 UTC. Uses superuser engine internally.
    """
    return run_async(expire_unanswered_offers())

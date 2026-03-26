"""
SIMS Plus - Incomplete Application Reminder Task

Daily Celery task that sends SMS/email reminders to applicants with
DRAFT applications on admission periods approaching their close date.

Runs daily at 09:00 UTC via Celery Beat.
Uses the platform admin superuser engine to iterate tenants, then
sets tenant context per-tenant in isolated sessions for RLS-scoped queries.

CRITICAL: Each tenant is processed in its own session to prevent
cross-tenant context leaking on error (REVIEW FIX C1).
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_platform_admin_session_maker
from app.models.admissions import AdmissionApplicationStatus, Application
from app.models.admissions.application import ApplicationGuardian
from app.models.admissions.period import AdmissionPeriod
from app.models.tenant import Tenant

logger = structlog.get_logger(__name__)


async def _send_reminders_for_tenant(
    session: AsyncSession,
    tenant_id: str,
    tenant_subdomain: str,
) -> int:
    """
    Send reminders for a single tenant.

    Caller is responsible for setting/clearing tenant context and
    committing/rolling back the session.

    Finds open admission periods with reminders enabled whose close date
    is within the reminder window, then notifies guardians of DRAFT
    applications to complete and submit before the deadline.

    Returns the number of reminders sent.
    """
    today = datetime.now(UTC).date()

    # Find active periods with reminders enabled and approaching close date
    period_result = await session.execute(
        select(AdmissionPeriod).filter(
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            AdmissionPeriod.tenant_id == tenant_id,
            AdmissionPeriod.status == "open",
            AdmissionPeriod.reminder_enabled.is_(True),
            AdmissionPeriod.reminder_days_before_close.isnot(None),
            AdmissionPeriod.deleted_at.is_(None),
        )
    )
    periods = period_result.scalars().all()

    sent_count = 0

    for period in periods:
        # Calculate the date when reminders should start firing
        reminder_date = period.end_date - timedelta(
            days=period.reminder_days_before_close
        )

        # Only send on or after the trigger date, but before close
        if not (reminder_date <= today <= period.end_date):
            continue

        # Find DRAFT applications for this period that need a nudge
        app_result = await session.execute(
            select(Application).filter(
                Application.tenant_id == tenant_id,
                Application.admission_period_id == period.id,
                Application.status == AdmissionApplicationStatus.DRAFT.value,
                Application.deleted_at.is_(None),
            )
        )
        draft_apps = app_result.scalars().all()

        for application in draft_apps:
            try:
                # Get primary guardian for notification delivery
                guardian_result = await session.execute(
                    select(ApplicationGuardian).filter(
                        ApplicationGuardian.tenant_id == tenant_id,
                        ApplicationGuardian.application_id == application.id,
                        ApplicationGuardian.is_primary.is_(True),
                        ApplicationGuardian.deleted_at.is_(None),
                    )
                )
                guardian = guardian_result.scalar_one_or_none()
                if not guardian:
                    continue

                # Send notification via the admissions notification service
                from app.services.admissions.notification_service import (
                    AdmissionNotificationService,
                )

                notifier = AdmissionNotificationService(session)
                await notifier.notify_status_change(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    new_status="incomplete_reminder",
                    extra_context={
                        "deadline": period.end_date.strftime("%d/%m/%Y"),
                        "days_remaining": (period.end_date - today).days,
                    },
                )
                sent_count += 1
            except Exception:
                logger.exception(
                    "reminder_send_failed",
                    application_id=str(application.id),
                    tenant_id=tenant_id,
                )

    return sent_count


async def send_incomplete_application_reminders() -> dict:
    """
    Main task entry point. Iterates all active tenants and sends
    reminders for incomplete applications approaching deadline.

    CRITICAL: Uses a separate session per tenant to prevent cross-tenant
    context leaking if one tenant's work fails mid-transaction (C1 fix).

    Returns: { tenants_processed: N, reminders_sent: N }
    """
    session_maker = get_platform_admin_session_maker()
    tenants_processed = 0
    total_reminders = 0

    # Fetch all active tenants in a read-only session (tenants table has no RLS)
    async with session_maker() as session:
        result = await session.execute(
            select(Tenant.id, Tenant.subdomain).filter(
                Tenant.status.in_(["active", "trial"]),
                Tenant.deleted_at.is_(None),
            )
        )
        tenants = result.all()

    # Process each tenant in its own isolated session (C1: session-per-tenant)
    for tenant_id, subdomain in tenants:
        async with session_maker() as per_tenant_session:
            try:
                await per_tenant_session.execute(
                    text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                    {"tid": str(tenant_id)},
                )
                count = await _send_reminders_for_tenant(
                    per_tenant_session, str(tenant_id), subdomain
                )
                await per_tenant_session.commit()
                total_reminders += count
                tenants_processed += 1
            except Exception:
                await per_tenant_session.rollback()
                logger.exception(
                    "reminder_tenant_failed",
                    tenant_id=str(tenant_id),
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
        "reminders_sent": total_reminders,
    }
    logger.info("incomplete_reminders_complete", **summary)
    return summary


# ---------------------------------------------------------------------------
# Celery task wrapper
# ---------------------------------------------------------------------------

from app.celery_app import celery_app  # noqa: E402
from app.tasks.utils import run_async  # noqa: E402


@celery_app.task(
    name="app.tasks.admission_reminders.send_incomplete_application_reminders",
)
def send_incomplete_application_reminders_task() -> dict:
    """
    Celery beat task: send reminders for incomplete applications
    approaching their admission period close date.

    Runs daily at 09:00 UTC. Uses superuser engine internally.
    """
    return run_async(send_incomplete_application_reminders())

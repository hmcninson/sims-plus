"""
Automated cleanup of cancelled tenant data after retention period.

After a tenant is cancelled, their data is retained for a configurable number
of days (default 90) before being permanently purged. This allows recovery
if the cancellation was accidental or the customer returns.

The task uses a superuser session (bypasses RLS) because it needs to delete
data across tenant-scoped tables that are normally locked down by RLS policies.

IMPORTANT: dry_run defaults to True — first runs log what would be deleted
without actually deleting anything. Set dry_run=False explicitly for real purges.

Celery beat schedule: daily at 02:00 UTC (defined in app.celery_app).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_platform_admin_session_maker

logger = structlog.get_logger()

# Tenant-scoped tables in reverse FK dependency order.
# Leaf tables (no children referencing them) come first, parent tables last.
# This ordering prevents FK constraint violations during deletion.
_TABLES_DELETION_ORDER = [
    # Multi-Curriculum (Phase 3) — leaf tables
    "predicted_grades",
    "student_credit_accumulations",
    "external_exam_registrations",
    # Multi-Curriculum (Phase 2)
    "subject_curriculum_mappings",
    "grade_equivalencies",
    # Multi-Curriculum (Phase 1)
    "report_card_configs",
    "assessment_components",
    "assessment_structures",
    "curriculum_profiles",
    # User Management & Access Control
    "custom_roles",
    # Subscription (RLS-exempt but has tenant_id — must be cleaned up)
    "subscription_intents",
    # Enrollment Gap Closure Phase 4 — leaf tables first
    "event_registrations",
    "school_events",
    "enrollment_targets",
    # Enrollment Gap Closure Phase 3 — leaf tables first (before applications)
    "enrollment_checklist_items",
    "enrollment_checklists",
    # Enrollment Gap Closure Phase 1 — leaf tables first (before admissions parents)
    "inquiry_follow_ups",
    "inquiry_communications",
    "screening_checklists",
    "interviews",
    "inquiries",
    # Admissions — leaf tables first
    "return_intents",
    "return_intent_campaigns",
    "promotion_rules",
    "class_promotion_entries",
    "class_promotions",
    "admission_decisions",
    "entrance_exam_results",
    "entrance_exam_registrations",
    "entrance_exams",
    "application_notes",
    "application_status_history",
    "application_payments",
    "application_documents",
    "application_guardians",
    "applications",
    "admission_form_configs",
    "admission_periods",
    # Email log (messaging)
    "email_log",
    # User-School junction (chain support)
    "user_schools",
    # Teacher Portal
    "lesson_plans",
    "report_comments",
    # Parent Portal
    "parent_notification_preferences",
    "teacher_notes",
    "announcements",
    # Push Notifications
    "push_subscriptions",
    # Transport — leaf tables first
    "vehicle_maintenance",
    "trip_logs",
    "student_transport",
    "route_stops",
    "routes",
    "drivers",
    "vehicles",
    # Boarding — leaf tables first
    "dining_meals",
    "boarding_incidents",
    "exeats",
    "boarding_roll_call_entries",
    "boarding_roll_call",
    "student_boarding",
    "beds",
    "dormitories",
    "houses",
    # Notifications & SMS
    "sms_log",
    "notifications",
    # Finance — leaf tables first
    "finance_audit_log",
    "credit_notes",
    "scholarship_applications",
    "student_scholarships",
    "payments",
    "invoice_scholarship_items",
    "invoice_items",
    "invoices",
    "fee_items",
    "fee_structures",
    "fee_types",
    "scholarships",
    # Preschool — leaf tables first
    "preschool_reports",
    "daily_activity_logs",
    "progress_observations",
    "student_skill_assessments",
    "preschool_ratings",
    "preschool_rating_scales",
    "developmental_skills",
    "learning_areas",
    # Exams — leaf tables first
    "term_reports",
    "continuous_assessments",
    "score_change_logs",
    "exam_scores",
    "exam_subjects",
    "exams",
    # Attendance
    "staff_attendance",
    "student_attendance",
    # Academic — leaf tables first
    "class_timetables",
    "school_periods",
    "school_holidays",
    "academic_settings",
    "assessment_weights",
    "grades",
    "grading_scales",
    "class_subjects",
    "subjects",
    "class_sections",
    "classes",
    "terms",
    "academic_years",
    # Staff — leaf tables first
    "staff_class_assignments",
    "staff",
    "departments",
    # Student Management Gap Closure Phase 3 (before students — FK dependency)
    "student_documents",
    "previous_schools",
    # Student Management Gap Closure Phase 2 (before status_changes — FK dependency)
    "withdrawal_clearances",
    # Student Management Gap Closure Phase 1 (before students — FK dependency)
    "student_status_changes",
    "student_class_history",
    # Students — leaf tables first
    "student_guardians",
    "guardians",
    "students",
    # Audit (RLS-exempt but has tenant_id — must be cleaned up)
    "audit_logs",
    # Core — users before schools (users.school_id FK)
    "users",
    "schools",
]


async def purge_cancelled_tenants(dry_run: bool = True) -> dict:
    """
    Permanently delete all data for tenants that have been cancelled
    longer than the configured retention period.

    Args:
        dry_run: If True (default), only log what would be deleted without
                 actually deleting. Set to False for real purges.

    Returns:
        Summary dict with counts of tenants processed and rows deleted.
    """
    retention_days = settings.CANCELLED_DATA_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    logger.info(
        "tenant_cleanup_started",
        dry_run=dry_run,
        retention_days=retention_days,
        cutoff=cutoff.isoformat(),
    )

    session_maker = get_platform_admin_session_maker()

    # Find cancelled tenants past the retention period.
    # NOTE: Using updated_at as a proxy for cancellation time because the Tenant
    # model lacks a dedicated cancelled_at column. This is imprecise — any update
    # after cancellation resets the retention clock.
    # TODO: Add cancelled_at column to Tenant via migration, then query on that instead.
    async with session_maker() as db:
        result = await db.execute(
            text(
                "SELECT id, subdomain, name, updated_at "
                "FROM tenants "
                "WHERE status = 'cancelled' "
                "AND updated_at < CAST(:cutoff AS timestamptz) "
                "AND deleted_at IS NULL "
                "ORDER BY updated_at ASC"
            ),
            {"cutoff": cutoff.isoformat()},
        )
        tenants_to_purge = result.fetchall()

    if not tenants_to_purge:
        logger.info("tenant_cleanup_no_tenants_to_purge")
        return {"tenants_processed": 0, "dry_run": dry_run}

    summary = {
        "dry_run": dry_run,
        "retention_days": retention_days,
        "tenants_processed": 0,
        "tenants_failed": 0,
        "details": [],
    }

    for tenant_row in tenants_to_purge:
        tenant_id = tenant_row.id
        subdomain = tenant_row.subdomain
        tenant_name = tenant_row.name

        logger.info(
            "tenant_cleanup_processing",
            tenant_id=str(tenant_id),
            subdomain=subdomain,
            tenant_name=tenant_name,
            # TODO: Use cancelled_at once the column is added to the Tenant model via migration
            last_updated=tenant_row.updated_at.isoformat(),
            dry_run=dry_run,
        )

        try:
            tenant_detail = await _purge_single_tenant(
                session_maker, tenant_id, subdomain, dry_run
            )
            summary["details"].append(tenant_detail)
            summary["tenants_processed"] += 1
        except Exception as exc:
            logger.exception(
                "tenant_cleanup_failed",
                tenant_id=str(tenant_id),
                subdomain=subdomain,
            )
            summary["tenants_failed"] += 1
            summary["details"].append({
                "tenant_id": str(tenant_id),
                "subdomain": subdomain,
                "error": f"{type(exc).__name__}: {exc}",
            })

    logger.info(
        "tenant_cleanup_complete",
        dry_run=dry_run,
        tenants_processed=summary["tenants_processed"],
        tenants_failed=summary["tenants_failed"],
    )

    return summary


async def _purge_single_tenant(
    session_maker,
    tenant_id: UUID,
    subdomain: str,
    dry_run: bool,
) -> dict:
    """
    Delete all data for a single tenant within one transaction.

    If any table deletion fails, the entire transaction is rolled back
    so the tenant is left in a consistent state for retry.
    """
    detail = {
        "tenant_id": str(tenant_id),
        "subdomain": subdomain,
        "rows_deleted": {},
    }

    # TODO: Add S3 object cleanup (delete tenant prefix: {tenant_id}/)

    # Wrap the entire tenant purge in a single transaction
    async with session_maker() as db:
        async with db.begin():
            for table in _TABLES_DELETION_ORDER:
                count = await _delete_tenant_rows(
                    db, table, tenant_id, dry_run
                )
                if count > 0:
                    detail["rows_deleted"][table] = count

            # Finally, hard-delete the tenant row itself
            if dry_run:
                result = await db.execute(
                    text(
                        "SELECT COUNT(*) FROM tenants "
                        "WHERE id = CAST(:tid AS uuid)"
                    ),
                    {"tid": str(tenant_id)},
                )
                tenant_count = result.scalar()
                if tenant_count:
                    detail["rows_deleted"]["tenants"] = tenant_count
                    logger.info(
                        "tenant_cleanup_would_delete_tenant",
                        tenant_id=str(tenant_id),
                        subdomain=subdomain,
                    )
            else:
                result = await db.execute(
                    text(
                        "DELETE FROM tenants "
                        "WHERE id = CAST(:tid AS uuid)"
                    ),
                    {"tid": str(tenant_id)},
                )
                deleted = result.rowcount
                if deleted:
                    detail["rows_deleted"]["tenants"] = deleted
                logger.info(
                    "tenant_cleanup_deleted_tenant",
                    tenant_id=str(tenant_id),
                    subdomain=subdomain,
                )

    # TODO: Invalidate Redis tenant cache after purge

    total_rows = sum(detail["rows_deleted"].values())
    logger.info(
        "tenant_cleanup_tenant_summary",
        tenant_id=str(tenant_id),
        subdomain=subdomain,
        total_rows=total_rows,
        dry_run=dry_run,
    )

    return detail


async def _delete_tenant_rows(
    db: AsyncSession,
    table: str,
    tenant_id: UUID,
    dry_run: bool,
) -> int:
    """
    Delete (or count, if dry_run) all rows for a tenant in a single table.

    Uses raw SQL because this operates across many tables generically.
    Table names come from a hardcoded allowlist, not user input.
    """
    # Defense-in-depth: guard against non-identifier table names even though
    # the list is hardcoded — prevents SQL injection if the list is ever
    # populated from an external source.
    if not table.isidentifier():
        raise ValueError(f"Invalid table name: {table}")

    if dry_run:
        result = await db.execute(
            text(
                f"SELECT COUNT(*) FROM {table} "
                "WHERE tenant_id = CAST(:tid AS uuid)"
            ),
            {"tid": str(tenant_id)},
        )
        count = result.scalar()
        if count:
            logger.info(
                "tenant_cleanup_would_delete",
                table=table,
                tenant_id=str(tenant_id),
                row_count=count,
            )
        return count or 0
    else:
        result = await db.execute(
            text(
                f"DELETE FROM {table} "
                "WHERE tenant_id = CAST(:tid AS uuid)"
            ),
            {"tid": str(tenant_id)},
        )
        deleted = result.rowcount
        if deleted:
            logger.info(
                "tenant_cleanup_deleted",
                table=table,
                tenant_id=str(tenant_id),
                row_count=deleted,
            )
        return deleted


# ---------------------------------------------------------------------------
# Celery task wrapper
# ---------------------------------------------------------------------------

from app.celery_app import celery_app  # noqa: E402
from app.tasks.utils import run_async  # noqa: E402


@celery_app.task(name="app.tasks.tenant_cleanup.purge_cancelled_tenants_task")
def purge_cancelled_tenants_task(dry_run: bool = True) -> dict:
    """
    Celery beat task: purge data for cancelled tenants past retention period.

    The beat schedule calls this with default dry_run=True so scheduled runs
    only log what would be deleted. To actually purge, trigger manually:

        from app.tasks.tenant_cleanup import purge_cancelled_tenants_task
        purge_cancelled_tenants_task.delay(dry_run=False)

    Uses a superuser session internally (no RLS context needed).
    """
    return run_async(purge_cancelled_tenants(dry_run=dry_run))

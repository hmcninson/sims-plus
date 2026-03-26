"""
SIMS Plus - Background Task Utilities

Chain-aware helpers for background tasks that need to process data
across all schools in a tenant. These functions handle the difference
between single-school and chain tenants transparently.

Usage:
    from app.tasks.utils import get_tenant_schools, for_each_school, run_async

    # Get schools to iterate
    schools = await get_tenant_schools(db, tenant_id)
    for school in schools:
        process(school)

    # Or use the higher-level helper
    results = await for_each_school(db, tenant_id, process_callback)

    # Bridge sync Celery tasks to async code
    @celery_app.task
    def my_task():
        run_async(my_async_function())
"""

import asyncio
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.middleware.tenant import set_db_tenant_context
from app.models.school import School, SchoolStatus
from app.models.tenant import Tenant, TenantStatus

logger = structlog.get_logger()


async def get_tenant_schools(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[School]:
    """
    Get all active, non-deleted schools for a tenant.

    Used by background jobs to iterate over schools in chain tenants.
    For single-school tenants, returns a list with one element.
    For chain tenants, returns all active schools ordered by name.

    Args:
        db: Database session (with tenant context already set).
        tenant_id: The tenant to fetch schools for.

    Returns:
        List of active School records. Empty list if none found.
    """
    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
    result = await db.execute(
        select(School)
        .where(School.tenant_id == tenant_id)
        .where(School.is_active.is_(True))
        .where(School.status == SchoolStatus.ACTIVE)
        .where(School.deleted_at.is_(None))
        .order_by(School.name)
    )
    return list(result.scalars().all())


async def get_active_tenants(db: AsyncSession) -> list[Tenant]:
    """
    Get all active, non-deleted tenants for batch processing.

    Used by Celery beat tasks that need to iterate over all tenants
    (e.g., daily attendance reminders for every school).

    This query runs WITHOUT RLS context because the tenants table
    is not tenant-scoped.

    Args:
        db: An unscoped database session (no RLS context).

    Returns:
        List of active Tenant records.
    """
    result = await db.execute(
        select(Tenant)
        .where(Tenant.is_active.is_(True))
        .where(Tenant.status.in_([TenantStatus.ACTIVE, TenantStatus.TRIAL]))
        .where(Tenant.deleted_at.is_(None))
        .order_by(Tenant.name)
    )
    return list(result.scalars().all())


# Type alias for the school-processing callback.
# Accepts (db, tenant_id, school_id) and returns any result.
SchoolCallback = Callable[
    [AsyncSession, UUID, UUID],
    Awaitable[Any],
]


async def for_each_school(
    db: AsyncSession,
    tenant_id: UUID,
    callback: SchoolCallback,
    school_id: Optional[UUID] = None,
) -> list[Any]:
    """
    Execute a callback for each school in a tenant.

    For single-school tenants this runs the callback once.
    For chain tenants this iterates all active schools.
    If school_id is provided, processes only that school (useful when a
    task is triggered for a specific school rather than on a schedule).

    Errors in one school do not stop processing of subsequent schools.
    Each school's result (or error dict) is collected and returned.

    Args:
        db: Database session (with tenant context already set).
        tenant_id: The tenant to process.
        callback: Async function(db, tenant_id, school_id) -> result.
        school_id: Optional specific school to process. If None,
            processes all active schools.

    Returns:
        List of results from each callback invocation. If a callback
        raises, its entry is a dict with "school_id" and "error" keys.
    """
    if school_id:
        # Process a single specific school
        try:
            result = await callback(db, tenant_id, school_id)
            return [result]
        except Exception:
            logger.exception(
                "for_each_school_callback_error",
                tenant_id=str(tenant_id),
                school_id=str(school_id),
            )
            return [{"school_id": str(school_id), "error": "callback failed"}]

    # Process all schools in the tenant
    schools = await get_tenant_schools(db, tenant_id)
    if not schools:
        logger.warning(
            "for_each_school_no_schools",
            tenant_id=str(tenant_id),
        )
        return []

    results: list[Any] = []
    for school in schools:
        try:
            result = await callback(db, tenant_id, school.id)
            results.append(result)
        except Exception:
            logger.exception(
                "for_each_school_callback_error",
                tenant_id=str(tenant_id),
                school_id=str(school.id),
                school_name=school.name,
            )
            results.append({
                "school_id": str(school.id),
                "school_name": school.name,
                "error": "callback failed",
            })

    return results


async def run_for_all_tenants(
    callback: Callable[
        [AsyncSession, UUID],
        Awaitable[Any],
    ],
) -> list[dict]:
    """
    Top-level orchestrator for scheduled tasks: iterates all active
    tenants, creates a properly scoped DB session for each, and calls
    the provided callback.

    Intended to be called from Celery beat tasks. Each tenant gets its
    own session with the correct RLS context set so that all queries
    inside the callback are properly isolated.

    Errors in one tenant do not stop processing of subsequent tenants.

    Args:
        callback: Async function(db, tenant_id) -> result.
            The callback receives a session with tenant RLS context
            already set, so it does not need to call
            set_db_tenant_context() itself.

    Returns:
        List of dicts with tenant_id and either "result" or "error".

    Example (Celery beat task):
        @celery_app.task
        def daily_attendance_reminders():
            import asyncio
            asyncio.run(_daily_attendance_reminders())

        async def _daily_attendance_reminders():
            await run_for_all_tenants(send_attendance_reminders)
    """
    # First, fetch all active tenants using an unscoped session
    # (tenants table has no RLS)
    async with async_session_maker() as unscoped_db:
        tenants = await get_active_tenants(unscoped_db)

    tenant_results: list[dict] = []

    for tenant in tenants:
        try:
            # Each tenant gets a fresh session with its RLS context set
            async with async_session_maker() as db:
                async with db.begin():
                    await set_db_tenant_context(db, tenant.id)
                    result = await callback(db, tenant.id)
                    tenant_results.append({
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.name,
                        "result": result,
                    })
        except Exception:
            logger.exception(
                "run_for_all_tenants_error",
                tenant_id=str(tenant.id),
                tenant_name=tenant.name,
            )
            tenant_results.append({
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.name,
                "error": "tenant processing failed",
            })

    logger.info(
        "run_for_all_tenants_complete",
        total_tenants=len(tenants),
        succeeded=sum(1 for r in tenant_results if "result" in r),
        failed=sum(1 for r in tenant_results if "error" in r),
    )

    return tenant_results


def run_async(coro: Any) -> Any:
    """
    Bridge between synchronous Celery tasks and async application code.

    Celery tasks are synchronous by default. This helper runs an async
    coroutine in a fresh event loop. Each Celery task that needs async
    DB operations should call this instead of asyncio.run() directly,
    so the loop lifecycle is managed consistently.

    Args:
        coro: An awaitable coroutine to execute.

    Returns:
        The coroutine's return value.

    Example:
        @celery_app.task
        def my_celery_task():
            return run_async(_my_async_logic())

        async def _my_async_logic():
            async with async_session_maker() as db:
                ...
    """
    # Create a new event loop for each task invocation. Celery worker
    # threads do not have a running loop, so we cannot use
    # asyncio.get_event_loop().run_until_complete() safely.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

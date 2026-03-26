"""
SIMS Plus - Background Tasks Package

Celery task definitions for scheduled and triggered background jobs.
Tasks are auto-discovered by the Celery app instance in app.celery_app.

Chain-aware utilities (get_tenant_schools, for_each_school,
run_for_all_tenants) ensure tasks process all schools in chain tenants.

Architecture:
    - celery_app lives in app.celery_app (separate module to avoid circular imports)
    - Each task module (notifications, subscription, tenant_cleanup) defines
      synchronous Celery tasks that wrap async business logic via run_async()
    - Async DB operations use async_session_maker directly (not FastAPI DI)
    - Tenant RLS context is set per-tenant with try/finally cleanup
"""

from app.tasks.utils import (
    for_each_school,
    get_active_tenants,
    get_tenant_schools,
    run_async,
    run_for_all_tenants,
)

__all__ = [
    "for_each_school",
    "get_active_tenants",
    "get_tenant_schools",
    "run_async",
    "run_for_all_tenants",
]

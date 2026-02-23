"""
SIMS Plus - Background Tasks Package

Task stubs for scheduled and triggered background jobs. These are designed
to be wired to Celery (or any other task queue) when the infrastructure is
set up. Until then, they can be called directly as async functions for
testing or one-off execution.

Chain-aware utilities (get_tenant_schools, for_each_school,
run_for_all_tenants) ensure tasks process all schools in chain tenants.

TODO: Wire to Celery once celery worker + beat are configured in docker-compose.
      Expected setup:
        - celery_app = Celery("sims_plus", broker=settings.REDIS_URL)
        - @celery_app.task decorator on each function
        - celery beat schedule in celery_config.py
"""

from app.tasks.utils import (
    for_each_school,
    get_active_tenants,
    get_tenant_schools,
    run_for_all_tenants,
)

__all__ = [
    "for_each_school",
    "get_active_tenants",
    "get_tenant_schools",
    "run_for_all_tenants",
]

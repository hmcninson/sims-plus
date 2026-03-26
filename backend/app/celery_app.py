"""
SIMS Plus - Celery Application Instance

Central Celery app used by the worker and beat scheduler. All task modules
under app.tasks are auto-discovered. Tasks that need database access must
create their own async sessions (not FastAPI dependency injection) and
manage tenant RLS context with try/finally.

Usage:
    # Start worker
    celery -A app.celery_app worker --loglevel=info --concurrency=2

    # Start beat scheduler
    celery -A app.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "sims_plus",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
)

celery_app.conf.update(
    # Serialization: JSON only (no pickle for security)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Reliability: track task state transitions, ack after completion
    # so tasks are retried if the worker crashes mid-execution
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result backend: keep results for 1 hour (for monitoring/debugging)
    result_expires=3600,

    # Prevent worker from consuming too much memory on long-running tasks
    worker_max_tasks_per_child=200,

    # Beat schedule: tasks are registered here as they are implemented.
    # Each entry maps a human-readable name to a task + schedule.
    beat_schedule={
        # Trial expiration warnings: daily at 08:00 UTC
        "check-trial-expirations": {
            "task": "app.tasks.subscription.check_trial_expirations_task",
            "schedule": crontab(hour=8, minute=0),
        },
        # Tenant data cleanup: daily at 02:00 UTC (off-peak)
        "purge-cancelled-tenants": {
            "task": "app.tasks.tenant_cleanup.purge_cancelled_tenants_task",
            "schedule": crontab(hour=2, minute=0),
        },
        # Attendance reminders: daily at 11:00 UTC
        "send-attendance-reminders": {
            "task": "app.tasks.notifications.send_attendance_reminders_task",
            "schedule": crontab(hour=11, minute=0),
        },
        # Score deadline reminders: daily at 08:00 UTC
        "send-score-deadline-reminders": {
            "task": "app.tasks.notifications.send_score_deadline_reminders_task",
            "schedule": crontab(hour=8, minute=0),
        },
        # Expire unanswered admission offers: daily at 00:00 UTC
        "expire-unanswered-offers": {
            "task": "app.tasks.offer_expiry.expire_unanswered_offers_task",
            "schedule": crontab(hour=0, minute=0),
        },
        # Incomplete application reminders: daily at 09:00 UTC
        "send-incomplete-app-reminders": {
            "task": "app.tasks.admission_reminders.send_incomplete_application_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
        # Update staff leave status: daily at 00:05 UTC
        # Sets staff on_leave if approved leave starts today,
        # sets active if approved leave ended yesterday
        "update-staff-leave-status": {
            "task": "update_staff_leave_status",
            "schedule": crontab(hour=0, minute=5),
        },
    },
)

# Auto-discover task modules in the app.tasks package.
# Each module must define Celery tasks decorated with @celery_app.task.
celery_app.autodiscover_tasks(["app.tasks"])

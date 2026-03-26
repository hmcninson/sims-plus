"""
SIMS Plus - Leave Management Celery Tasks

Daily task to update staff leave status based on approved leave dates.
"""

import structlog

from app.celery_app import celery_app
from app.tasks.utils import run_async, run_for_all_tenants

logger = structlog.get_logger()


@celery_app.task(name="update_staff_leave_status")
def update_staff_leave_status():
    """
    Daily task (runs at 00:05 UTC) to synchronize staff status with leave dates.

    For each active tenant:
    1. Set staff.status = 'on_leave' for staff whose approved leave starts today
       (and who are currently 'active')
    2. Set staff.status = 'active' for staff whose approved leave ended yesterday
       (and who are currently 'on_leave', with no other active leave covering today)
    """
    return run_async(_update_leave_status_async())


async def _update_leave_status_async():
    """Async implementation — iterates all active tenants."""
    return await run_for_all_tenants(_process_tenant_leave_status)


async def _process_tenant_leave_status(db, tenant_id):
    """
    Process leave status updates for a single tenant.
    Called within a properly scoped DB session (RLS context already set).
    """
    from datetime import date, timedelta
    from uuid import UUID

    from sqlalchemy import select, update, and_, not_
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.leave import LeaveRequest, LeaveRequestStatus
    from app.models.staff import Staff, StaffStatus

    today = date.today()
    yesterday = today - timedelta(days=1)

    # 1. Staff whose approved leave starts today -> set to on_leave
    starting_today = await db.execute(
        select(LeaveRequest.staff_id)
        .where(
            LeaveRequest.tenant_id == tenant_id,
            LeaveRequest.status == LeaveRequestStatus.APPROVED,
            LeaveRequest.start_date == today,
        )
        .distinct()
    )
    starting_staff_ids = [row[0] for row in starting_today.all()]

    if starting_staff_ids:
        await db.execute(
            update(Staff)
            .where(
                Staff.tenant_id == tenant_id,
                Staff.id.in_(starting_staff_ids),
                Staff.status == StaffStatus.ACTIVE,
                Staff.deleted_at.is_(None),
            )
            .values(status=StaffStatus.ON_LEAVE)
        )
        logger.info(
            "leave_status_set_on_leave",
            tenant_id=str(tenant_id),
            count=len(starting_staff_ids),
        )

    # 2. Staff whose approved leave ended yesterday -> set back to active
    #    BUT only if they don't have another approved leave covering today
    ended_yesterday = await db.execute(
        select(LeaveRequest.staff_id)
        .where(
            LeaveRequest.tenant_id == tenant_id,
            LeaveRequest.status == LeaveRequestStatus.APPROVED,
            LeaveRequest.end_date == yesterday,
        )
        .distinct()
    )
    ended_staff_ids = [row[0] for row in ended_yesterday.all()]

    if ended_staff_ids:
        # Exclude staff who have another approved leave covering today
        still_on_leave = await db.execute(
            select(LeaveRequest.staff_id)
            .where(
                LeaveRequest.tenant_id == tenant_id,
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
            )
            .distinct()
        )
        still_on_leave_ids = {row[0] for row in still_on_leave.all()}

        # Only reactivate staff who are NOT still on another leave
        reactivate_ids = [
            sid for sid in ended_staff_ids if sid not in still_on_leave_ids
        ]

        if reactivate_ids:
            await db.execute(
                update(Staff)
                .where(
                    Staff.tenant_id == tenant_id,
                    Staff.id.in_(reactivate_ids),
                    Staff.status == StaffStatus.ON_LEAVE,
                    Staff.deleted_at.is_(None),
                )
                .values(status=StaffStatus.ACTIVE)
            )
            logger.info(
                "leave_status_set_active",
                tenant_id=str(tenant_id),
                count=len(reactivate_ids),
            )

    return {
        "started_leave": len(starting_staff_ids),
        "ended_leave": len(ended_staff_ids),
    }

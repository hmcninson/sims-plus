"""
SIMS Plus - Parent Portal Attendance Endpoints

Endpoints for parents to view their children's attendance data:
monthly summaries with daily breakdowns and multi-month trend charts.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    AttendanceSummary,
    AttendanceTrend,
)
from app.services.parent import (
    ParentAttendanceService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/children/{student_id}/attendance",
    response_model=AttendanceSummary,
    summary="Get child monthly attendance",
    dependencies=[Depends(require_permissions("parent.attendance.read"))],
)
async def get_child_attendance(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    month: str = Query(
        ...,
        description="Month in YYYY-MM format (e.g., 2026-02)",
        pattern=r"^\d{4}-\d{2}$",
    ),
) -> AttendanceSummary:
    """
    Get monthly attendance summary with daily breakdown for a child.

    Returns: total school days, present/absent/late/excused counts,
    attendance rate, and per-day status records.
    """
    user_id = _get_user_id(user)
    service = ParentAttendanceService(db)

    try:
        result = await service.get_child_attendance(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
            month=month,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return AttendanceSummary(**result)


@router.get(
    "/children/{student_id}/attendance/trend",
    response_model=list[AttendanceTrend],
    summary="Get child attendance trend",
    dependencies=[Depends(require_permissions("parent.attendance.read"))],
)
async def get_child_attendance_trend(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    months: int = Query(
        6,
        ge=1,
        le=12,
        description="Number of months to look back (default 6, max 12)",
    ),
) -> list[AttendanceTrend]:
    """
    Get monthly attendance rate trend for charting.

    Returns up to N months of data going backwards from the current date,
    with attendance rate, present count, and total school days per month.
    """
    user_id = _get_user_id(user)
    service = ParentAttendanceService(db)

    try:
        results = await service.get_child_attendance_trend(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
            months=months,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return [AttendanceTrend(**item) for item in results]

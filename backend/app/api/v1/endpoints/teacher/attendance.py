"""
SIMS Plus - Teacher Portal Attendance Endpoints

Attendance summary view for teachers. Teachers can see attendance
statistics for their assigned classes. Actual attendance marking is
handled by the existing attendance module.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import (
    ClassAttendanceSummary,
    StudentAttendanceSummary,
)
from app.services.teacher import (
    TeacherAttendanceService,
    TeacherContextService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/attendance/classes/{class_id}/summary",
    response_model=ClassAttendanceSummary,
    summary="Get class attendance summary",
    dependencies=[Depends(require_permissions("teacher.attendance.read"))],
)
async def get_class_attendance_summary(
    class_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    section_id: UUID | None = Query(None, description="Optional section filter"),
    date_from: date | None = Query(None, description="Start date for summary"),
    date_to: date | None = Query(None, description="End date for summary"),
) -> ClassAttendanceSummary:
    """
    Get attendance summary for a class the teacher is assigned to.

    Returns per-student attendance counts (present, absent, late) and
    overall class attendance percentage for the given date range.
    Defaults to the current month if no date range specified.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)

        # Verify teacher has access to this class
        await context.verify_class_access(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            section_id=section_id,
        )

        attendance_service = TeacherAttendanceService(db)
        summary = await attendance_service.get_class_attendance_summary(
            tenant_id=tenant.tenant_id,
            class_id=class_id,
            section_id=section_id,
            date_from=date_from,
            date_to=date_to,
        )

        return ClassAttendanceSummary(
            class_id=summary["class_id"],
            class_name=summary["class_name"],
            section_id=summary["section_id"],
            section_name=summary["section_name"],
            total_students=summary["total_students"],
            present_today=summary["present_today"],
            absent_today=summary["absent_today"],
            late_today=summary["late_today"],
            attendance_percentage=summary["attendance_percentage"],
            students=[
                StudentAttendanceSummary(**s) for s in summary["students"]
            ],
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)

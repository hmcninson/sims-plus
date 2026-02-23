"""
SIMS Plus - Teacher Portal Schedule Endpoints

Today's schedule and weekly timetable view for teachers.
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import DaySchedule, ScheduleEntry, WeekSchedule
from app.services.teacher import (
    TeacherContextService,
    TeacherScheduleService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/schedule/today",
    response_model=list[ScheduleEntry],
    summary="Get today's schedule",
    dependencies=[Depends(require_permissions("teacher.schedule.read"))],
)
async def get_today_schedule(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ScheduleEntry]:
    """
    Get today's timetable entries for the authenticated teacher.

    Returns a list of schedule entries sorted by period number.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)

        term_id = None
        try:
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id
        except TeacherServiceError:
            pass

        schedule_service = TeacherScheduleService(db)
        entries = await schedule_service.get_today_schedule(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year.id,
            term_id=term_id,
        )
        return [ScheduleEntry(**e) for e in entries]

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)


@router.get(
    "/schedule/week",
    response_model=WeekSchedule,
    summary="Get weekly schedule",
    dependencies=[Depends(require_permissions("teacher.schedule.read"))],
)
async def get_week_schedule(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> WeekSchedule:
    """
    Get the full weekly timetable for the authenticated teacher.

    Returns schedule grouped by day of the week.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)

        term_id = None
        try:
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id
        except TeacherServiceError:
            pass

        schedule_service = TeacherScheduleService(db)
        days = await schedule_service.get_week_schedule(
            staff_id=staff.id,
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year.id,
            term_id=term_id,
        )
        return WeekSchedule(
            days=[DaySchedule(**d) for d in days]
        )

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)

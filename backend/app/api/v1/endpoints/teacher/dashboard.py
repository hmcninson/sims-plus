"""
SIMS Plus - Teacher Portal Dashboard Endpoint

Aggregates teacher dashboard data: classes, subjects, today's schedule,
and pending tasks into a single response.
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import TeacherDashboard
from app.services.teacher import (
    TeacherContextService,
    TeacherDashboardService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=TeacherDashboard,
    summary="Get teacher dashboard",
    dependencies=[Depends(require_permissions("teacher.dashboard.read"))],
)
async def get_teacher_dashboard(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> TeacherDashboard:
    """
    Get the teacher dashboard aggregating data from multiple services.

    Returns:
    - Teacher profile summary
    - Class assignments with student counts
    - Subject assignments with class counts
    - Today's timetable schedule
    - Pending tasks (score entry, report comments, lesson plans)
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        staff = await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)

        # Try to get current term (optional for dashboard)
        term_id = None
        try:
            term = await context.get_current_term(tenant.tenant_id, academic_year.id)
            term_id = term.id
        except TeacherServiceError:
            pass

        dashboard_service = TeacherDashboardService(db)
        result = await dashboard_service.get_dashboard(
            staff=staff,
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year.id,
            term_id=term_id,
        )
        return TeacherDashboard(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)

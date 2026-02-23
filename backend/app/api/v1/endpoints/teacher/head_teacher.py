"""
SIMS Plus - Teacher Portal Head Teacher Endpoints

Performance metrics and oversight for head teachers / school admins.
Provides an aggregate view of all teaching staff performance.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import TeacherPerformanceSummary
from app.services.teacher import (
    TeacherContextService,
    TeacherPerformanceService,
    TeacherServiceError,
)

from ._helpers import _get_user_id, _handle_teacher_error

router = APIRouter()


@router.get(
    "/head-teacher/performance",
    response_model=TeacherPerformanceSummary,
    summary="Get teacher performance summary",
    dependencies=[Depends(require_permissions("teacher.performance.read"))],
)
async def get_teacher_performance(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(None, description="Term ID (defaults to current)"),
) -> TeacherPerformanceSummary:
    """
    Get performance metrics for all teaching staff.

    Returns per-teacher metrics including:
    - Lesson plan creation and completion rates
    - Score entry progress
    - Teacher note activity
    - Report comment sign-off rates

    Also includes overall school-wide completion rates.
    Requires school admin / head teacher permissions.
    """
    user_id = _get_user_id(user)

    try:
        context = TeacherContextService(db)
        # Verify the user is a teacher (even if head teacher, should have staff record)
        await context.get_staff_for_user(user_id, tenant.tenant_id)
        academic_year = await context.get_current_academic_year(tenant.tenant_id)

        if not term_id:
            try:
                term = await context.get_current_term(tenant.tenant_id, academic_year.id)
                term_id = term.id
            except TeacherServiceError:
                pass

        perf_service = TeacherPerformanceService(db)
        result = await perf_service.get_performance_summary(
            tenant_id=tenant.tenant_id,
            academic_year_id=academic_year.id,
            term_id=term_id,
        )
        return TeacherPerformanceSummary(**result)

    except TeacherServiceError as e:
        raise _handle_teacher_error(e)

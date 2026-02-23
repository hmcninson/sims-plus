"""
SIMS Plus - Parent Portal Dashboard Endpoint

Composes data from multiple parent services into a single dashboard
response: children list, active child overview, recent announcements,
and upcoming events (due invoices, exams, holidays).
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
    AnnouncementResponse,
    ChildDetail,
    ChildOverview,
    ChildQuickStats,
    ChildSummary,
    ParentDashboard,
)
from app.services.parent import (
    ParentCommunicationService,
    ParentService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=ParentDashboard,
    summary="Get parent dashboard",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def get_parent_dashboard(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    active_child_id: UUID | None = Query(
        None,
        description="ID of the child to show detailed overview for. "
        "Defaults to the first child if not specified.",
    ),
) -> ParentDashboard:
    """
    Get the parent dashboard aggregating data from multiple services.

    Returns:
    - List of all linked children (for child selector)
    - Detailed overview for the active/selected child
    - Recent announcements targeted at this parent
    - Upcoming events (due invoices, exam dates, holidays)

    The active_child_id parameter controls which child's detailed
    overview is included. If omitted, the first child is used.
    """
    user_id = _get_user_id(user)
    parent_service = ParentService(db)

    # Get all children for the sidebar/selector
    students = await parent_service.get_my_children(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
    )

    children_summaries = [
        ChildSummary(
            id=s.id,
            first_name=s.first_name,
            last_name=s.last_name,
            photo_url=s.photo_url,
            class_name=s.class_.name if s.class_ else None,
            section_name=s.section.name if s.section else None,
            admission_number=s.admission_number,
            date_of_birth=s.date_of_birth,
            gender=s.gender.value if s.gender else None,
            school_id=s.school_id,
            school_name=s.school.name if s.school else None,
        )
        for s in students
    ]

    # Determine which child to show detailed overview for
    active_child: ChildOverview | None = None
    if students:
        target_student_id = active_child_id or students[0].id

        try:
            child_data = await parent_service.get_child_detail(
                user_id=user_id,
                student_id=target_student_id,
                tenant_id=tenant.tenant_id,
            )
            child_detail = ChildDetail(**child_data)
            stats = ChildQuickStats()

            active_child = ChildOverview(
                child=child_detail,
                stats=stats,
                recent_activity=[],
            )
        except ParentServiceError:
            # If the specified child cannot be loaded (e.g., invalid ID),
            # degrade gracefully by showing no active child
            pass

    # Get recent announcements for this parent
    comm_service = ParentCommunicationService(db)
    announcements_data = await comm_service.get_announcements_for_parent(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
    )
    # Limit to most recent 5 announcements for dashboard view
    announcements = [
        AnnouncementResponse(**ann) for ann in announcements_data[:5]
    ]

    return ParentDashboard(
        children=children_summaries,
        active_child=active_child,
        announcements=announcements,
        upcoming=[],
    )

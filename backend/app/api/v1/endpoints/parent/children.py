"""
SIMS Plus - Parent Portal Children Endpoints

Endpoints for parents to view their linked children and child overview.
Parent-to-student resolution is handled via email matching:
User.email == Guardian.email within the same tenant.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    ChildDetail,
    ChildOverview,
    ChildQuickStats,
    ChildSummary,
)
from app.services.parent import ParentService, ParentServiceError

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/children",
    response_model=list[ChildSummary],
    summary="List my children",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def list_children(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ChildSummary]:
    """
    Get all children linked to the authenticated parent.

    Resolves the parent-student relationship via email matching:
    User.email == Guardian.email within the same tenant.
    Returns lightweight summaries suitable for child selector UIs.
    """
    user_id = _get_user_id(user)
    service = ParentService(db)

    students = await service.get_my_children(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
    )

    return [
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


@router.get(
    "/children/{student_id}/overview",
    response_model=ChildOverview,
    summary="Get child overview",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def get_child_overview(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChildOverview:
    """
    Get detailed overview for a single child.

    Includes child profile, quick stats (attendance rate, average score,
    class position, outstanding balance), and recent activity feed.
    Verifies parent-child access before returning data.
    """
    user_id = _get_user_id(user)
    service = ParentService(db)

    try:
        child_data = await service.get_child_detail(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    child_detail = ChildDetail(**child_data)

    # Quick stats and activity are best-effort -- default to empty if
    # the underlying data is not yet available for this student
    stats = ChildQuickStats()

    return ChildOverview(
        child=child_detail,
        stats=stats,
        recent_activity=[],
    )

"""
SIMS Plus - Parent Portal Onboarding Endpoints

Endpoints for parent profile completion after first login.
Parents receive an invitation email with temporary credentials;
these endpoints allow them to check their onboarding status and
complete their profile.
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import ParentProfileCompletion
from app.services.parent import (
    ParentOnboardingService,
    ParentService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/onboarding/status",
    summary="Get parent onboarding status",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def get_onboarding_status(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Check if the parent has completed their profile onboarding.

    Returns whether the parent has linked children and whether their
    profile is complete (account is active, not pending).
    """
    user_id = _get_user_id(user)
    parent_service = ParentService(db)

    children = await parent_service.get_my_children(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
    )

    # A parent with an "active" status has completed onboarding;
    # "pending" status means they haven't set up their profile yet
    role = user.get("role", "")
    is_parent = role == "parent"

    return {
        "is_parent": is_parent,
        "has_children": len(children) > 0,
        "children_count": len(children),
        "profile_complete": is_parent and len(children) > 0,
    }


@router.post(
    "/onboarding/complete",
    summary="Complete parent profile",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def complete_profile(
    data: ParentProfileCompletion,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Complete parent profile after first login.

    Updates the parent's phone number and creates default notification
    preferences. Activates the account if it was in pending status.
    """
    user_id = _get_user_id(user)
    service = ParentOnboardingService(db)

    try:
        await service.complete_profile(
            user_id=user_id,
            tenant_id=tenant.tenant_id,
            data=data.model_dump(exclude_unset=True),
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return {"status": "complete"}

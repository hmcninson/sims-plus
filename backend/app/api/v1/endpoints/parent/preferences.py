"""
SIMS Plus - Parent Portal Notification Preferences Endpoints

Endpoints for parents to view and update their notification channel
and category preferences. Controls which notifications are sent
via email, SMS, and push, and for which categories (attendance,
grades, finance, announcements, etc.).
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.services.parent import (
    NotificationPreferencesService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/notification-preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def get_notification_preferences(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> NotificationPreferencesResponse:
    """
    Get current notification preferences for the authenticated parent.

    Creates default preferences on first access if none exist.
    """
    user_id = _get_user_id(user)
    service = NotificationPreferencesService(db)

    prefs = await service.get_preferences(
        user_id=user_id,
        tenant_id=tenant.tenant_id,
    )

    return NotificationPreferencesResponse.model_validate(prefs)


@router.patch(
    "/notification-preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
    dependencies=[Depends(require_permissions("parent.children.read"))],
)
async def update_notification_preferences(
    data: NotificationPreferencesUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> NotificationPreferencesResponse:
    """
    Update notification preferences using PATCH semantics.

    Only fields present in the request body are updated; absent fields
    are left unchanged. Quiet hours must be set together (both start
    and end) or both cleared to null.
    """
    user_id = _get_user_id(user)
    service = NotificationPreferencesService(db)

    try:
        prefs = await service.update_preferences(
            user_id=user_id,
            tenant_id=tenant.tenant_id,
            data=data.model_dump(exclude_unset=True),
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return NotificationPreferencesResponse.model_validate(prefs)

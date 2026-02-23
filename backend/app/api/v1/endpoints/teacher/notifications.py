"""
SIMS Plus - Teacher Portal Notification Endpoints

Provides teacher-specific notification views. Under the hood, these wrap
the existing NotificationService to scope queries to the teacher's user_id.
The frontend expects page-based pagination with unread_count in the response.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.teacher import (
    TeacherNotificationItem,
    TeacherNotificationListResponse,
)
from app.services.notification import NotificationService

from ._helpers import _get_user_id

router = APIRouter()


@router.get(
    "/notifications",
    response_model=TeacherNotificationListResponse,
    summary="List teacher notifications",
    dependencies=[Depends(require_permissions("teacher.notifications.read"))],
)
async def list_teacher_notifications(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> TeacherNotificationListResponse:
    """
    List notifications for the current teacher, newest first.

    Returns paginated notifications with unread count. Uses the shared
    NotificationService under the hood -- the teacher endpoints are a
    thin view over the same notification table.
    """
    user_id = _get_user_id(user)
    service = NotificationService(db)

    result = await service.list_for_user(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )

    unread_count = await service.get_unread_count(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
    )

    return TeacherNotificationListResponse(
        items=[
            TeacherNotificationItem(
                id=n.id,
                title=n.title,
                message=n.message,
                type=n.type.value,
                category=n.category.value,
                is_read=n.is_read,
                created_at=n.created_at,
                link=None,
            )
            for n in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
        unread_count=unread_count,
    )


@router.patch(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a notification as read",
    dependencies=[Depends(require_permissions("teacher.notifications.read"))],
)
async def mark_teacher_notification_read(
    notification_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Mark a single notification as read for the current teacher.

    Returns 404 if the notification does not exist or does not belong
    to the current user within their tenant.
    """
    user_id = _get_user_id(user)
    service = NotificationService(db)

    notification = await service.mark_read(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
        notification_id=notification_id,
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )


@router.post(
    "/notifications/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all notifications as read",
    dependencies=[Depends(require_permissions("teacher.notifications.read"))],
)
async def mark_all_teacher_notifications_read(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Mark all of the current teacher's unread notifications as read.

    This is an idempotent operation -- calling it when all notifications
    are already read is a no-op.
    """
    user_id = _get_user_id(user)
    service = NotificationService(db)

    await service.mark_all_read(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
    )

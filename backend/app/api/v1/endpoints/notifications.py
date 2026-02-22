"""
SIMS Plus - Notification Endpoints

API endpoints for managing in-app user notifications.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.models.notification import NotificationCategory
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification import NotificationService

import structlog

logger = structlog.get_logger()

router = APIRouter()


# =========================
# Notification Endpoints
# =========================


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
)
async def list_notifications(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    category: Optional[NotificationCategory] = Query(None, description="Filter by category"),
) -> NotificationListResponse:
    """
    List the current user's notifications with pagination and filtering.

    No special permission required -- users can only see their own notifications.
    """
    service = NotificationService(db)

    result = await service.list_for_user(
        tenant_id=tenant.tenant_id,
        user_id=UUID(user["user_id"]),
        page=page,
        page_size=page_size,
        is_read=is_read,
        category=category,
    )

    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                user_id=n.user_id,
                title=n.title,
                message=n.message,
                type=n.type,
                category=n.category,
                reference_id=n.reference_id,
                reference_type=n.reference_type,
                is_read=n.is_read,
                read_at=n.read_at,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
)
async def get_unread_count(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> UnreadCountResponse:
    """
    Get the count of unread notifications for the current user.

    No special permission required -- users can only see their own count.
    """
    service = NotificationService(db)

    count = await service.get_unread_count(
        tenant_id=tenant.tenant_id,
        user_id=UUID(user["user_id"]),
    )

    return UnreadCountResponse(count=count)


@router.put(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark notification as read",
)
async def mark_notification_read(
    notification_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Mark a single notification as read.

    No special permission required -- users can only mark their own notifications.
    """
    service = NotificationService(db)

    notification = await service.mark_read(
        tenant_id=tenant.tenant_id,
        user_id=UUID(user["user_id"]),
        notification_id=notification_id,
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )


@router.put(
    "/mark-all-read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all notifications as read",
)
async def mark_all_notifications_read(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Mark all of the current user's unread notifications as read.

    No special permission required -- users can only mark their own notifications.
    """
    service = NotificationService(db)

    await service.mark_all_read(
        tenant_id=tenant.tenant_id,
        user_id=UUID(user["user_id"]),
    )


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
)
async def delete_notification(
    notification_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Delete a single notification (hard delete).

    No special permission required -- users can only delete their own notifications.
    """
    service = NotificationService(db)

    deleted = await service.delete_notification(
        tenant_id=tenant.tenant_id,
        user_id=UUID(user["user_id"]),
        notification_id=notification_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

"""
SIMS Plus - Notification Schemas

Pydantic schemas for the notification system.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationCategory, NotificationType


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class NotificationResponse(BaseSchema):
    """Single notification response."""

    id: UUID
    user_id: UUID
    title: str
    message: str
    type: NotificationType
    category: NotificationCategory
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseSchema):
    """Paginated notification list response."""

    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class NotificationCreate(BaseModel):
    """Internal schema for creating a notification (not exposed via API)."""

    tenant_id: UUID
    user_id: UUID
    title: str = Field(..., max_length=255)
    message: str
    type: NotificationType = NotificationType.INFO
    category: NotificationCategory = NotificationCategory.GENERAL
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = Field(None, max_length=50)


class NotificationMarkRead(BaseSchema):
    """Mark a single notification as read."""

    notification_id: UUID


class NotificationBulkMarkRead(BaseSchema):
    """Mark multiple notifications as read."""

    notification_ids: list[UUID]


class UnreadCountResponse(BaseSchema):
    """Unread notification count response."""

    count: int

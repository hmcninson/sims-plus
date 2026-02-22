"""
SIMS Plus - Notification Service

Manages in-app notifications for users.
"""

import math
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationCategory, NotificationType

logger = structlog.get_logger()


class NotificationError(Exception):
    """Notification operation failed."""

    def __init__(self, message: str, code: str = "notification_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotificationService:
    """Service for managing in-app notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: UUID,
        user_id: UUID,
        title: str,
        message: str,
        type: NotificationType = NotificationType.INFO,
        category: NotificationCategory = NotificationCategory.GENERAL,
        reference_id: Optional[UUID] = None,
        reference_type: Optional[str] = None,
    ) -> Notification:
        """Create a new notification for a user."""
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            category=category,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        logger.info(
            "notification_created",
            notification_id=str(notification.id),
            user_id=str(user_id),
            category=category.value,
        )
        return notification

    async def list_for_user(
        self,
        tenant_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        is_read: Optional[bool] = None,
        category: Optional[NotificationCategory] = None,
    ) -> dict:
        """List notifications for a user with pagination and filtering."""
        # Defense-in-depth: always scope by tenant_id
        stmt = select(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )
        count_stmt = select(func.count()).select_from(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )

        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
            count_stmt = count_stmt.where(Notification.is_read == is_read)

        if category is not None:
            stmt = stmt.where(Notification.category == category)
            count_stmt = count_stmt.where(Notification.category == category)

        # Get total count
        total = (await self.db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        # Get paginated results ordered by newest first
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def get_unread_count(self, tenant_id: UUID, user_id: UUID) -> int:
        """Get the count of unread notifications for a user."""
        stmt = select(func.count()).select_from(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712 — SQLAlchemy requires == for column comparison
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def mark_read(
        self, tenant_id: UUID, user_id: UUID, notification_id: UUID
    ) -> Optional[Notification]:
        """Mark a single notification as read."""
        # Defense-in-depth: scope by tenant_id and user_id to prevent cross-user access
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()

        if notification is None:
            return None

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await self.db.flush()
            await self.db.refresh(notification)

        return notification

    async def mark_all_read(self, tenant_id: UUID, user_id: UUID) -> int:
        """Mark all unread notifications as read. Returns count updated."""
        stmt = (
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=datetime.now(UTC))
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    async def delete_notification(
        self, tenant_id: UUID, user_id: UUID, notification_id: UUID
    ) -> bool:
        """
        Delete a notification (hard delete).

        Notifications are ephemeral UI elements, so hard delete is appropriate.
        Returns True if deleted.
        """
        stmt = delete(Notification).where(
            Notification.id == notification_id,
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

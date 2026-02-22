"""
SIMS Plus - Notification Model

In-app notification system for user alerts.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin


class NotificationType(str, Enum):
    """Type/severity of notification."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SYSTEM = "system"


class NotificationCategory(str, Enum):
    """Category of notification for filtering."""
    ACADEMIC = "academic"
    FINANCE = "finance"
    ATTENDANCE = "attendance"
    EXAM = "exam"
    GENERAL = "general"
    ADMIN = "admin"


class Notification(Base, TenantMixin):
    """In-app notification for users."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        SQLEnum(
            NotificationType,
            name="notificationtype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=NotificationType.INFO,
    )
    category: Mapped[NotificationCategory] = mapped_column(
        SQLEnum(
            NotificationCategory,
            name="notificationcategory",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=NotificationCategory.GENERAL,
    )
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reference_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="raise")

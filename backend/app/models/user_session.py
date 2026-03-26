"""
SIMS Plus - User Session Model

Tracks active user sessions for session management and device visibility.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class UserSession(Base, TenantMixin):
    """
    Tracks active login sessions tied to refresh tokens.

    Each session is identified by the refresh token's JTI (JWT ID).
    Users can view and terminate sessions from other devices.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # JWT ID of the refresh token — links session to a specific token
    jti: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Parsed user-agent string (e.g., "Chrome on Windows")
    device_info: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Client IP address (supports IPv6)
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<UserSession(user_id='{self.user_id}', jti='{self.jti[:8]}...', active={self.is_active})>"

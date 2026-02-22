"""
SIMS Plus - Push Subscription Model

Stores Web Push API subscriptions for browser-based push notifications.
Each user can have multiple subscriptions (one per browser/device).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


class PushSubscription(Base, TenantMixin):
    """
    Web Push subscription for a user's browser.

    A user may have multiple active subscriptions across devices.
    Keys (p256dh, auth) are part of the Web Push protocol and may rotate
    when the browser refreshes the subscription.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The push service endpoint URL provided by the browser
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    # ECDH public key for encryption (Web Push protocol)
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Authentication secret for encryption (Web Push protocol)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional browser User-Agent for debugging stale subscriptions
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="raise")

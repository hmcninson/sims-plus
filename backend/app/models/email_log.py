"""
SIMS Plus - Email Log Model

Tracks outbound email messages sent via the communication system.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class EmailStatus(str, Enum):
    """Status of an outbound email message."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class EmailLog(Base, TenantMixin):
    """
    Log of outbound email messages.

    Every email sent through the communication system is recorded here
    for audit trail and delivery tracking.
    """

    __tablename__ = "email_log"

    school_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="School that triggered the email (nullable for tenant-wide messages)",
    )
    recipient_email: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    recipient_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EmailStatus] = mapped_column(
        SQLEnum(
            EmailStatus,
            name="emailstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EmailStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who initiated the email send",
    )

    def __repr__(self) -> str:
        return f"<EmailLog(recipient='{self.recipient_email}', status='{self.status}')>"

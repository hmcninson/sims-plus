"""
SIMS Plus - SMS Log Model

Tracks outbound SMS messages sent via providers.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class SMSProvider(str, Enum):
    """Supported SMS gateway providers."""
    HUBTEL = "hubtel"
    ARKESEL = "arkesel"
    TWILIO = "twilio"


class SMSStatus(str, Enum):
    """Status of an SMS message."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class SMSLog(Base, TenantMixin):
    """Log of outbound SMS messages."""

    __tablename__ = "sms_log"

    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[SMSProvider] = mapped_column(
        SQLEnum(
            SMSProvider,
            name="smsprovider",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SMSProvider.HUBTEL,
    )
    status: Mapped[SMSStatus] = mapped_column(
        SQLEnum(
            SMSStatus,
            name="smsstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SMSStatus.PENDING,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

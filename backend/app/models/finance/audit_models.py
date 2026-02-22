"""
SIMS Plus - Finance Audit Log Models

Models for immutable finance audit trail.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User


# =========================
# Enums
# =========================


class FinanceAuditAction(str, Enum):
    """Types of actions that can be audited."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VOID = "void"
    ISSUE = "issue"
    CANCEL = "cancel"
    AWARD = "award"
    REVOKE = "revoke"
    PAYMENT = "payment"
    REFUND = "refund"


# =========================
# Finance Audit Log Model
# =========================


class FinanceAuditLog(Base, TenantMixin):
    """
    Finance Audit Log model.

    Records all changes to financial entities for audit trail.
    This is an append-only log that should never be modified or deleted.
    """

    __tablename__ = "finance_audit_log"

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of entity: invoice, payment, scholarship, fee_structure, etc.",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of the entity being audited",
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Action type: create, update, delete, void, issue, cancel, award, revoke",
    )
    field_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Field that was changed (for updates)",
    )
    old_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Previous value (JSON string for complex values)",
    )
    new_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="New value (JSON string for complex values)",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for the change (e.g., void reason, cancel reason)",
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional metadata about the change",
    )
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of the user",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Browser/client user agent",
    )

    # Relationships
    performed_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[performed_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<FinanceAuditLog(entity_type='{self.entity_type}', entity_id='{self.entity_id}', action='{self.action}')>"

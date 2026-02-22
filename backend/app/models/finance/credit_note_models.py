"""
SIMS Plus - Finance Credit Note Models

Models for credit notes issued to students.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User

    from .invoice_models import Invoice


# =========================
# Enums
# =========================


class CreditNoteStatus(str, Enum):
    """Status of a credit note."""

    DRAFT = "draft"
    ISSUED = "issued"
    APPLIED = "applied"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class CreditNoteType(str, Enum):
    """Type/reason for credit note."""

    OVERPAYMENT = "overpayment"
    FEE_REDUCTION = "fee_reduction"
    ERROR_CORRECTION = "error_correction"
    SCHOLARSHIP_ADJUSTMENT = "scholarship_adjustment"
    OTHER = "other"


# =========================
# Credit Note Model
# =========================


class CreditNote(Base, TenantMixin, SoftDeleteMixin):
    """
    Credit Note model.

    Represents a credit issued to a student for overpayments, fee reductions,
    error corrections, or refunds. Can be applied to future invoices or refunded.
    """

    __tablename__ = "credit_notes"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    credit_note_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Unique credit note number (e.g., CN-2026-00001)",
    )
    credit_note_type: Mapped[CreditNoteType] = mapped_column(
        SQLEnum(
            CreditNoteType,
            name="creditnotetype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    original_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="Invoice this credit note is issued against (optional)",
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Credit amount",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="GHS",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for issuing the credit note",
    )
    status: Mapped[CreditNoteStatus] = mapped_column(
        SQLEnum(
            CreditNoteStatus,
            name="creditnotestatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=CreditNoteStatus.DRAFT,
        nullable=False,
    )

    # Issuance info
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Application info (when applied to another invoice)
    applied_to_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="Invoice this credit was applied to",
    )
    applied_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Refund info
    refund_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="How the refund was made: cash, momo, bank_transfer, etc.",
    )
    refund_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    refunded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Cancellation info
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    original_invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        foreign_keys=[original_invoice_id],
        lazy="raise",
    )
    applied_to_invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        foreign_keys=[applied_to_invoice_id],
        lazy="raise",
    )
    issued_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[issued_by],
        lazy="raise",
    )
    applied_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[applied_by],
        lazy="raise",
    )
    refunded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[refunded_by],
        lazy="raise",
    )
    cancelled_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[cancelled_by],
        lazy="raise",
    )

    @property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining credit amount after application."""
        if self.applied_amount:
            return self.amount - self.applied_amount
        return self.amount

    def __repr__(self) -> str:
        return f"<CreditNote(number='{self.credit_note_number}', amount={self.amount}, status='{self.status}')>"

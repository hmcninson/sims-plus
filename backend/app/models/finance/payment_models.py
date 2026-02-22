"""
SIMS Plus - Finance Payment Models

Models for payment recording and tracking.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User

    from .invoice_models import Invoice


# =========================
# Enums
# =========================


class PaymentMethod(str, Enum):
    """Payment methods."""

    CASH = "cash"
    MOMO_MTN = "momo_mtn"
    MOMO_VODAFONE = "momo_vodafone"
    MOMO_AIRTELTIGO = "momo_airteltigo"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    CARD = "card"
    OTHER = "other"


class PaymentStatus(str, Enum):
    """Status of a payment."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


# =========================
# Payment Model
# =========================


class Payment(Base, TenantMixin):
    """
    Payment model.

    Records a payment made towards an invoice or student account.
    """

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "receipt_number", name="uq_receipt_number"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    receipt_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Auto-generated receipt number",
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="GHS",
        nullable=False,
    )

    # Payment method details
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(
            PaymentMethod,
            name="paymentmethod",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    momo_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Mobile money phone number",
    )
    momo_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Mobile money transaction ID",
    )
    momo_provider: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="MTN, Vodafone, AirtelTigo",
    )
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    bank_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    cheque_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Payer info
    payer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    payer_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    payer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Status
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(
            PaymentStatus,
            name="paymentstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=PaymentStatus.COMPLETED,
        nullable=False,
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Void info
    is_voided: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    voided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    void_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Audit
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="payments",
        foreign_keys=[invoice_id],
        lazy="raise",
    )
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    voided_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[voided_by],
        lazy="raise",
    )
    recorded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recorded_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Payment(receipt='{self.receipt_number}', amount={self.amount}, status='{self.status}')>"

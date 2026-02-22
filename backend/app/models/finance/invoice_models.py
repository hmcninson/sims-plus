"""
SIMS Plus - Finance Invoice Models

Models for invoices, invoice items, and invoice scholarship items.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Term
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User

    from .fee_models import FeeItem, FeeStructure
    from .payment_models import Payment
    from .scholarship_models import Scholarship, StudentScholarship


# =========================
# Enums
# =========================


class InvoiceStatus(str, Enum):
    """Status of an invoice."""

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    WRITE_OFF = "write_off"


# Invoice Status State Machine - Valid transitions
# DRAFT -> ISSUED -> PARTIAL -> PAID
#            |        |
#         CANCELLED  OVERDUE -> PARTIAL -> PAID
#                       |
#                    WRITE_OFF
INVOICE_STATUS_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED},
    InvoiceStatus.ISSUED: {InvoiceStatus.PARTIAL, InvoiceStatus.PAID, InvoiceStatus.OVERDUE, InvoiceStatus.CANCELLED},
    InvoiceStatus.PARTIAL: {InvoiceStatus.PAID, InvoiceStatus.OVERDUE},
    InvoiceStatus.PAID: set(),  # Terminal state - no transitions allowed
    InvoiceStatus.OVERDUE: {InvoiceStatus.PARTIAL, InvoiceStatus.PAID, InvoiceStatus.WRITE_OFF},
    InvoiceStatus.CANCELLED: set(),  # Terminal state - no transitions allowed
    InvoiceStatus.WRITE_OFF: set(),  # Terminal state - no transitions allowed
}


def is_valid_invoice_transition(from_status: InvoiceStatus, to_status: InvoiceStatus) -> bool:
    """Check if a status transition is valid according to the state machine."""
    if from_status == to_status:
        return True  # No change is always valid
    valid_transitions = INVOICE_STATUS_TRANSITIONS.get(from_status, set())
    return to_status in valid_transitions


def get_valid_next_statuses(current_status: InvoiceStatus) -> list[InvoiceStatus]:
    """Get the list of valid next statuses for a given current status."""
    return list(INVOICE_STATUS_TRANSITIONS.get(current_status, set()))


# =========================
# Invoice Model
# =========================


class Invoice(Base, TenantMixin, SoftDeleteMixin):
    """
    Invoice model.

    Represents a bill sent to a student/guardian for fees.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoice_number"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Auto-generated invoice number",
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    fee_structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fee_structures.id", ondelete="SET NULL"),
        nullable=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    scholarship_discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Scholarship-based discount",
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Cached balance (total_amount - amount_paid)",
    )

    # Status and dates
    status: Mapped[InvoiceStatus] = mapped_column(
        SQLEnum(
            InvoiceStatus,
            name="invoicestatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=InvoiceStatus.DRAFT,
        nullable=False,
    )
    issue_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="GHS",
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Audit
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    # Adjustment tracking (for debit/credit adjustments)
    adjustment_for_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="If this is an adjustment invoice, reference to the original invoice",
    )
    adjustment_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Type of adjustment: scholarship_revoked, scholarship_reinstated, fee_correction, etc.",
    )
    adjustment_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for the adjustment",
    )

    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use selectinload()/joinedload() explicitly in queries that need these.
    school: Mapped["School"] = relationship("School", lazy="raise")
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    fee_structure: Mapped["FeeStructure"] = relationship("FeeStructure", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    term: Mapped["Term"] = relationship("Term", lazy="raise")
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
        foreign_keys="Payment.invoice_id",
        lazy="raise",
    )
    scholarship_items: Mapped[list["InvoiceScholarshipItem"]] = relationship(
        "InvoiceScholarshipItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    adjustment_for_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice",
        foreign_keys=[adjustment_for_invoice_id],
        remote_side="Invoice.id",
        lazy="raise",
    )

    def update_balance(self) -> None:
        """Update the cached balance value."""
        self.balance = self.total_amount - self.amount_paid

    def __repr__(self) -> str:
        return f"<Invoice(number='{self.invoice_number}', status='{self.status}', balance={self.balance})>"


# =========================
# Invoice Item Model
# =========================


class InvoiceItem(Base, TenantMixin):
    """
    Invoice Item model.

    Individual line item on an invoice.
    """

    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    fee_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fee_items.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to fee item if applicable",
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="items",
        lazy="raise",
    )
    fee_item: Mapped["FeeItem"] = relationship("FeeItem", lazy="raise")

    def __repr__(self) -> str:
        return f"<InvoiceItem(description='{self.description}', amount={self.amount})>"


# =========================
# Invoice Scholarship Item Model
# =========================


class InvoiceScholarshipItem(Base, TenantMixin):
    """
    Invoice Scholarship Item model.

    Tracks scholarship discounts applied to invoices with full audit trail.
    This provides traceability for which scholarships provided discounts.
    """

    __tablename__ = "invoice_scholarship_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_scholarship_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_scholarships.id", ondelete="SET NULL"),
        nullable=True,
        comment="Link to the student scholarship that provided this discount",
    )
    scholarship_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scholarships.id", ondelete="SET NULL"),
        nullable=True,
        comment="Direct link to scholarship for historical reference",
    )

    # Snapshot of scholarship details at time of application
    scholarship_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Scholarship name at time of application (for historical record)",
    )
    scholarship_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Scholarship code at time of application",
    )
    coverage_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="percentage or fixed_amount",
    )
    coverage_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="The coverage value used (percentage or amount)",
    )
    calculated_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="The actual discount amount applied to the invoice",
    )
    applicable_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="The subtotal this scholarship was applied to",
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="scholarship_items",
        lazy="raise",
    )
    student_scholarship: Mapped["StudentScholarship | None"] = relationship(
        "StudentScholarship",
        lazy="raise",
    )
    scholarship: Mapped["Scholarship | None"] = relationship(
        "Scholarship",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<InvoiceScholarshipItem(invoice_id='{self.invoice_id}', scholarship='{self.scholarship_name}', amount={self.calculated_amount})>"

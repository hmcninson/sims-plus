"""
SIMS Plus - Finance Models

Models for financial management: Fee Structures, Invoices, Payments, Scholarships.
"""

import uuid
from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Term, Class
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User


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
# DRAFT → ISSUED → PARTIAL → PAID
#            ↓        ↓
#         CANCELLED  OVERDUE → PARTIAL → PAID
#                       ↓
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


class ScholarshipType(str, Enum):
    """Type of scholarship."""

    FULL = "full"
    PARTIAL = "partial"
    MERIT = "merit"
    NEED_BASED = "need_based"
    ATHLETIC = "athletic"
    SPECIAL = "special"


class CoverageType(str, Enum):
    """How scholarship coverage is calculated."""

    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


class ScholarshipStatus(str, Enum):
    """Status of a student's scholarship."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApplicationStatus(str, Enum):
    """Status of a scholarship application."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


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


class RenewalType(str, Enum):
    """Scholarship renewal types."""

    ONE_TIME = "one_time"
    ANNUAL = "annual"
    UNTIL_GRADUATION = "until_graduation"


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


class FeeTypeCategory(str, Enum):
    """Categories for fee types."""

    TUITION = "tuition"
    EXAMINATION = "examination"
    FACILITIES = "facilities"
    ACTIVITIES = "activities"
    OTHER = "other"


# =========================
# Fee Type Model
# =========================


class FeeType(Base, TenantMixin):
    """
    Fee Type model.

    Defines reusable fee type names (e.g., Tuition, Examination, PTA).
    """

    __tablename__ = "fee_types"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Fee type name, e.g., Tuition, Examination, PTA",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Category: tuition, examination, facilities, activities, other",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="joined")


# =========================
# Fee Structure Model
# =========================


class FeeStructure(Base, TenantMixin, SoftDeleteMixin):
    """
    Fee Structure model.

    Defines a fee template that can be applied to classes/levels.
    """

    __tablename__ = "fee_structures"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Fee structure name, e.g., Term 1 Fees 2025/2026",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional: applies to specific class",
    )
    level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Optional: applies to class level (jhs_1, shs_2, etc.)",
    )
    level_category: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Level category: preschool, primary, jhs, shs",
    )
    student_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="all",
        server_default="all",
        comment="Student type: all, boarding, day",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="joined")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="joined")
    term: Mapped["Term"] = relationship("Term", lazy="joined")
    class_: Mapped["Class"] = relationship("Class", lazy="joined")
    items: Mapped[list["FeeItem"]] = relationship(
        "FeeItem",
        back_populates="fee_structure",
        cascade="all, delete-orphan",
        order_by="FeeItem.sequence",
    )

    def __repr__(self) -> str:
        return f"<FeeStructure(name='{self.name}', is_active={self.is_active})>"

    @property
    def total_amount(self) -> Decimal:
        """Calculate total of all mandatory fee items."""
        return sum(item.amount for item in self.items if not item.is_optional)


# =========================
# Fee Item Model
# =========================


class FeeItem(Base, TenantMixin):
    """
    Fee Item model.

    Individual line item within a fee structure.
    """

    __tablename__ = "fee_items"

    fee_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fee_structures.id", ondelete="CASCADE"),
        nullable=False,
    )
    fee_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fee_types.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to fee type for consistent naming",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Fee item name, e.g., Tuition, Examination Fee",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    is_optional: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Display order",
    )

    # Relationships
    fee_type: Mapped["FeeType"] = relationship("FeeType", lazy="joined")
    fee_structure: Mapped["FeeStructure"] = relationship(
        "FeeStructure",
        back_populates="items",
    )

    def __repr__(self) -> str:
        return f"<FeeItem(name='{self.name}', amount={self.amount})>"


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
    school: Mapped["School"] = relationship("School", lazy="joined")
    student: Mapped["Student"] = relationship("Student", lazy="joined")
    fee_structure: Mapped["FeeStructure"] = relationship("FeeStructure", lazy="joined")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="joined")
    term: Mapped["Term"] = relationship("Term", lazy="joined")
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
        foreign_keys="Payment.invoice_id",
    )
    scholarship_items: Mapped[list["InvoiceScholarshipItem"]] = relationship(
        "InvoiceScholarshipItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    adjustment_for_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice",
        foreign_keys=[adjustment_for_invoice_id],
        remote_side="Invoice.id",
        lazy="joined",
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
    )
    fee_item: Mapped["FeeItem"] = relationship("FeeItem", lazy="joined")

    def __repr__(self) -> str:
        return f"<InvoiceItem(description='{self.description}', amount={self.amount})>"


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
    school: Mapped["School"] = relationship("School", lazy="joined")
    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="payments",
        foreign_keys=[invoice_id],
    )
    student: Mapped["Student"] = relationship("Student", lazy="joined")
    voided_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[voided_by],
        lazy="joined",
    )
    recorded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recorded_by],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Payment(receipt='{self.receipt_number}', amount={self.amount}, status='{self.status}')>"


# =========================
# Scholarship Model
# =========================


class Scholarship(Base, TenantMixin, SoftDeleteMixin):
    """
    Scholarship model.

    Defines a scholarship program that can be awarded to students.
    """

    __tablename__ = "scholarships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_scholarship_code"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Scholarship name, e.g., Academic Excellence Award",
    )
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Unique code, e.g., AEA-2026",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    scholarship_type: Mapped[ScholarshipType] = mapped_column(
        SQLEnum(
            ScholarshipType,
            name="scholarshiptype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    coverage_type: Mapped[CoverageType] = mapped_column(
        SQLEnum(
            CoverageType,
            name="coveragetype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    coverage_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Percentage (0-100) or fixed GHS amount",
    )
    applicable_fees: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Which fee items it covers: ["tuition", "all"] or specific IDs',
    )
    max_recipients: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Optional: limit number of awards",
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
    )
    eligibility_criteria: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='{"min_gpa": 3.5, "max_income": 5000}',
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Audit
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="joined")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="joined")
    recipients: Mapped[list["StudentScholarship"]] = relationship(
        "StudentScholarship",
        back_populates="scholarship",
        cascade="all, delete-orphan",
    )

    @property
    def recipients_count(self) -> int:
        """Count of active recipients."""
        return len([r for r in self.recipients if r.status == ScholarshipStatus.ACTIVE])

    def __repr__(self) -> str:
        return f"<Scholarship(name='{self.name}', type='{self.scholarship_type}', coverage={self.coverage_value})>"


# =========================
# Student Scholarship Model
# =========================


class StudentScholarship(Base, TenantMixin):
    """
    Student Scholarship model.

    Records a scholarship awarded to a student.
    """

    __tablename__ = "student_scholarships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scholarship_id",
            "student_id",
            "academic_year_id",
            name="uq_student_scholarship_unique",
        ),
    )

    scholarship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scholarships.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    awarded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[ScholarshipStatus] = mapped_column(
        SQLEnum(
            ScholarshipStatus,
            name="scholarshipstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ScholarshipStatus.ACTIVE,
        nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="NULL = until end of academic year",
    )
    coverage_override: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Override default coverage if needed",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Enhanced award settings (Phase 1 improvements)
    justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Required justification/reason for awarding the scholarship",
    )
    renewal_type: Mapped[str] = mapped_column(
        String(20),
        default="one_time",
        nullable=False,
        comment="Renewal type: one_time, annual, until_graduation",
    )
    is_provisional: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is a provisional/conditional award",
    )
    provisional_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions that must be met for provisional awards",
    )

    # Revocation info
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoke_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Reinstatement tracking
    reinstated_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_scholarships.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to previously revoked scholarship if this is a reinstatement",
    )

    # Relationships
    scholarship: Mapped["Scholarship"] = relationship(
        "Scholarship",
        back_populates="recipients",
    )
    student: Mapped["Student"] = relationship("Student", lazy="joined")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="joined")
    awarded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[awarded_by],
        lazy="joined",
    )
    revoked_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[revoked_by],
        lazy="joined",
    )
    reinstated_from_record: Mapped["StudentScholarship | None"] = relationship(
        "StudentScholarship",
        foreign_keys=[reinstated_from],
        remote_side="StudentScholarship.id",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<StudentScholarship(student_id='{self.student_id}', scholarship_id='{self.scholarship_id}', status='{self.status}')>"


# =========================
# Scholarship Application Model
# =========================


class ScholarshipApplication(Base, TenantMixin):
    """
    Scholarship Application model.

    Records a student's application for a scholarship.
    """

    __tablename__ = "scholarship_applications"

    scholarship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scholarships.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(
            ApplicationStatus,
            name="applicationstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ApplicationStatus.PENDING,
        nullable=False,
    )
    supporting_documents: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="[{name, url, type}]",
    )
    application_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Review info
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    scholarship: Mapped["Scholarship"] = relationship("Scholarship", lazy="joined")
    student: Mapped["Student"] = relationship("Student", lazy="joined")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="joined")
    reviewer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reviewer_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<ScholarshipApplication(student_id='{self.student_id}', scholarship_id='{self.scholarship_id}', status='{self.status}')>"


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
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<FinanceAuditLog(entity_type='{self.entity_type}', entity_id='{self.entity_id}', action='{self.action}')>"


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
    school: Mapped["School"] = relationship("School", lazy="joined")
    student: Mapped["Student"] = relationship("Student", lazy="joined")
    original_invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        foreign_keys=[original_invoice_id],
        lazy="joined",
    )
    applied_to_invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        foreign_keys=[applied_to_invoice_id],
        lazy="joined",
    )
    issued_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[issued_by],
        lazy="joined",
    )
    applied_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[applied_by],
        lazy="joined",
    )
    refunded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[refunded_by],
        lazy="joined",
    )
    cancelled_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[cancelled_by],
        lazy="joined",
    )

    @property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining credit amount after application."""
        if self.applied_amount:
            return self.amount - self.applied_amount
        return self.amount

    def __repr__(self) -> str:
        return f"<CreditNote(number='{self.credit_note_number}', amount={self.amount}, status='{self.status}')>"


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
    )
    student_scholarship: Mapped["StudentScholarship | None"] = relationship(
        "StudentScholarship",
        lazy="joined",
    )
    scholarship: Mapped["Scholarship | None"] = relationship(
        "Scholarship",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<InvoiceScholarshipItem(invoice_id='{self.invoice_id}', scholarship='{self.scholarship_name}', amount={self.calculated_amount})>"

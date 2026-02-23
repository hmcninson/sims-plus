"""
SIMS Plus - Finance Fee Models

Models for fee types, fee structures, and fee items.
"""

import uuid
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, Term
    from app.models.school import School


# =========================
# Enums
# =========================


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
    school: Mapped["School"] = relationship("School", lazy="raise")


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
    school: Mapped["School"] = relationship("School", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    term: Mapped["Term"] = relationship("Term", lazy="raise")
    class_: Mapped["Class"] = relationship("Class", lazy="raise")
    items: Mapped[list["FeeItem"]] = relationship(
        "FeeItem",
        back_populates="fee_structure",
        cascade="all, delete-orphan",
        order_by="FeeItem.sequence",
        lazy="raise",
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

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

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
    fee_type: Mapped["FeeType"] = relationship("FeeType", lazy="raise")
    fee_structure: Mapped["FeeStructure"] = relationship(
        "FeeStructure",
        back_populates="items",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<FeeItem(name='{self.name}', amount={self.amount})>"

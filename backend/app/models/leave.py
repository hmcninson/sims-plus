"""
SIMS Plus - Leave Management Models

Database models for leave types, balances, and requests.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.staff import Staff
    from app.models.user import User


class LeaveRequestStatus(str, Enum):
    """Leave request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveType(Base, TenantMixin, SoftDeleteMixin):
    """
    Leave type model.

    Defines categories of leave available within a tenant/school
    (e.g., Annual, Sick, Maternity, Paternity).
    """
    __tablename__ = "leave_types"
    __table_args__ = (
        # Soft-delete aware uniqueness handled by partial unique index in migration
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_days_per_year: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False,
    )
    max_carryover_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), server_default="0", nullable=False,
    )
    is_paid: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    color: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True,
        comment="Hex color for calendar display (e.g., #FF5733)",
    )

    # Relationships
    balances: Mapped[list["LeaveBalance"]] = relationship(
        "LeaveBalance",
        back_populates="leave_type",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest",
        back_populates="leave_type",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class LeaveBalance(Base, TenantMixin):
    """
    Leave balance model.

    Tracks each staff member's leave entitlement and usage per leave type
    per academic year. No SoftDeleteMixin -- balances are recalculated,
    not soft-deleted.
    """
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "staff_id", "leave_type_id", "academic_year_id",
            name="uq_leave_balance_staff_type_year",
        ),
        {"extend_existing": True},
    )

    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    leave_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    entitled_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False,
    )
    used_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), server_default="0", nullable=False,
    )
    pending_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), server_default="0", nullable=False,
    )
    carried_over: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), server_default="0", nullable=False,
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="raise",
    )
    leave_type: Mapped["LeaveType"] = relationship(
        "LeaveType",
        back_populates="balances",
        lazy="raise",
    )


class LeaveRequest(Base, TenantMixin):
    """
    Leave request model.

    Represents a staff member's request for leave. Tracks the approval
    workflow (pending -> approved/rejected/cancelled).
    No SoftDeleteMixin -- requests are permanent records for audit.
    """
    __tablename__ = "leave_requests"
    __table_args__ = {"extend_existing": True}

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    leave_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_requested: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveRequestStatus] = mapped_column(
        SQLEnum(
            LeaveRequestStatus,
            name="leaverequeststatus",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default="pending",
        nullable=False,
    )
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_key: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="S3 key for supporting document",
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="raise",
    )
    leave_type: Mapped["LeaveType"] = relationship(
        "LeaveType",
        back_populates="requests",
        lazy="raise",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="raise",
        foreign_keys=[reviewed_by],
    )

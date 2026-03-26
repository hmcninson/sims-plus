"""
SIMS Plus - Return Intent Models

ReturnIntentCampaign: Optional survey for boarding/private schools.
ReturnIntent: Per-student intent-to-return response.

This is NOT a gate -- purely informational. In Ghana, students are
automatically promoted. This feature helps schools (especially boarding
schools) plan capacity by surveying parents about return intentions.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.school import School
    from app.models.student import Student
    from app.models.tenant import User


class ReturnIntentCampaign(Base, TenantMixin, SoftDeleteMixin):
    """
    Return Intent Campaign model.

    Optional survey sent to parents/guardians asking whether their
    child plans to return for the next academic year. Does NOT block
    promotion or enrollment -- results are advisory only.
    """

    __tablename__ = "return_intent_campaigns"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        comment="Target academic year",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., '2026/2027 Return Intent Survey'",
    )
    target_classes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of class UUIDs to target",
    )
    message_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="SMS/email template with placeholders",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
        comment="draft, sent, completed",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Response deadline",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    intents: Mapped[list["ReturnIntent"]] = relationship(
        back_populates="campaign",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class ReturnIntent(Base, TenantMixin, SoftDeleteMixin):
    """
    Return Intent model.

    Tracks individual student/parent response to a return intent survey.
    Values: pending, returning, not_returning, undecided.
    """

    __tablename__ = "return_intents"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("return_intent_campaigns.id", ondelete="CASCADE"),
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
    intent: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="pending, returning, not_returning, undecided",
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    responded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent user who responded",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Reason if not returning",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Re-enrollment confirmation fields (Enrollment Gap Closure Phase 4)
    re_enrollment_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
        comment="True when admin confirms this returning student is re-enrolled",
    )
    re_enrollment_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    outstanding_fees_checked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
        comment="True when outstanding fees were checked during confirmation",
    )
    outstanding_fee_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Snapshot of outstanding fee balance at confirmation time",
    )

    # Relationships
    campaign: Mapped["ReturnIntentCampaign"] = relationship(
        back_populates="intents",
        lazy="raise",
    )
    student: Mapped["Student"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    responded_by_user: Mapped["User | None"] = relationship(lazy="raise")

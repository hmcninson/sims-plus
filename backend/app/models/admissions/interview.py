"""
SIMS Plus - Interview & Screening Models (Enrollment Gap Closure Phase 1)

Interview: Interview scheduling and scoring for selective admissions.
ScreeningChecklist: Per-application screening items for document/academic/medical verification.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.admissions.enums import InterviewStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.admissions.application import Application
    from app.models.school import School
    from app.models.tenant import User


class Interview(Base, TenantMixin, SoftDeleteMixin):
    """
    Interview model.

    Records interview scheduling, scoring criteria, and feedback
    for selective admissions processes. One active interview per
    application (enforced by partial unique index).
    """

    __tablename__ = "interviews"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    interviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff conducting the interview (nullable to preserve history)",
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
        comment="Interview duration in minutes (10-180)",
    )
    venue: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Room/location for the interview",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InterviewStatus.SCHEDULED.value,
        server_default="scheduled",
        comment="Interview lifecycle status (InterviewStatus enum value)",
    )
    scoring_criteria: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment='Breakdown by criterion: {"criterion": {"score": N, "max": N}}',
    )
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Overall interview score",
    )
    max_score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Maximum possible score",
    )
    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Written feedback from interviewer",
    )

    # Relationships
    school: Mapped["School"] = sa_relationship(lazy="raise")
    application: Mapped["Application"] = sa_relationship(lazy="raise", overlaps="interview")
    interviewer: Mapped["User | None"] = sa_relationship(lazy="raise")


class ScreeningChecklist(Base, TenantMixin, SoftDeleteMixin):
    """
    Screening Checklist model.

    Per-application screening items that track document verification,
    academic record evaluation, medical checks, etc.
    """

    __tablename__ = "screening_checklists"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment='e.g., "Birth certificate verified"',
    )
    item_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="documents, academic, medical, other",
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff who verified this item",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes",
    )

    # Relationships
    application: Mapped["Application"] = sa_relationship(lazy="raise", overlaps="screening_items")
    completed_by_user: Mapped["User | None"] = sa_relationship(lazy="raise")

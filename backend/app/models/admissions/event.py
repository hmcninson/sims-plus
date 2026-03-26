"""
SIMS Plus - School Event & Event Registration Models

Tours, open days, and orientation events for prospective families.

Tables:
  - school_events: Events with capacity tracking
  - event_registrations: Registrations for events (hard delete, no SoftDeleteMixin)
"""

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.tenant import User


class SchoolEvent(Base, TenantMixin, SoftDeleteMixin):
    """
    School Event model.

    Represents tours, open days, and orientations for prospective families.
    Tracks capacity and registration counts. The guide_id field optionally
    associates a staff member (tour guide / event lead).
    """

    __tablename__ = "school_events"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="EventType enum value: open_day, tour, orientation",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Event display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    event_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    end_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    venue: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Max registrants (null = unlimited)",
    )
    registered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Maintained via service-level increment/decrement",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="upcoming",
        server_default="upcoming",
        comment="EventStatus enum value: upcoming, completed, cancelled",
    )
    guide_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Tour guide / event lead",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    guide: Mapped["User | None"] = relationship(lazy="raise")
    registrations: Mapped[list["EventRegistration"]] = relationship(
        back_populates="event",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class EventRegistration(Base, TenantMixin):
    """
    Event Registration model.

    Registrations for school events. NO SoftDeleteMixin -- cancelled
    registrations are hard-deleted so that registered_count stays accurate
    without soft-delete bookkeeping.

    Unique constraint on (tenant_id, event_id, registrant_phone) prevents
    duplicate registrations from the same phone number for the same event.
    """

    __tablename__ = "event_registrations"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    registrant_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Parent/guardian name",
    )
    registrant_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    registrant_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    student_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Prospective student name",
    )
    attended: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
        comment="Marked by staff post-event",
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    event: Mapped["SchoolEvent"] = relationship(
        back_populates="registrations",
        lazy="raise",
    )

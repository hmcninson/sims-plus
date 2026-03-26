"""
SIMS Plus - Inquiry Models (Enrollment Gap Closure Phase 1)

Inquiry: Pre-application lead tracking for prospective students.
InquiryCommunication: Append-only communication log per inquiry.
InquiryFollowUp: Scheduled follow-up tasks assigned to staff.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.admissions.enums import InquirySource, InquiryStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.admissions.application import Application
    from app.models.school import School
    from app.models.tenant import User


class Inquiry(Base, TenantMixin, SoftDeleteMixin):
    """
    Inquiry model -- pre-application lead tracking.

    Captures prospective student and guardian information before a formal
    application is submitted. Tracks lead source, status progression,
    and staff assignment for follow-up.
    """

    __tablename__ = "inquiries"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="How the inquiry reached the school (InquirySource enum value)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InquiryStatus.NEW.value,
        server_default="new",
        comment="Lead progression status (InquiryStatus enum value)",
    )

    # Prospective student info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="male or female",
    )
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Desired class level",
    )

    # Guardian info
    guardian_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Primary guardian full name",
    )
    guardian_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Primary guardian phone",
    )
    guardian_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary guardian email",
    )

    # Staff assignment & tracking
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member managing this lead",
    )
    referred_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Free text referral source detail",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Conversion tracking
    converted_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        comment="Links to the application created from this inquiry",
    )

    # Relationships
    school: Mapped["School"] = sa_relationship(lazy="raise")
    target_class: Mapped["Class | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[target_class_id],
    )
    assigned_user: Mapped["User | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[assigned_to],
    )
    converted_application: Mapped["Application | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[converted_application_id],
    )
    communications: Mapped[list["InquiryCommunication"]] = sa_relationship(
        back_populates="inquiry",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    follow_ups: Mapped[list["InquiryFollowUp"]] = sa_relationship(
        back_populates="inquiry",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class InquiryCommunication(Base, TenantMixin):
    """
    Inquiry Communication model.

    Append-only log of all communications related to an inquiry.
    No SoftDeleteMixin -- audit records are never deleted.
    """

    __tablename__ = "inquiry_communications"

    inquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inquiries.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="sms, email, phone, in_person",
    )
    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="inbound or outbound",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Summary of the communication",
    )
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff who logged the communication",
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="When the communication occurred",
    )

    # Relationships
    inquiry: Mapped["Inquiry"] = sa_relationship(
        back_populates="communications",
        lazy="raise",
    )
    sent_by_user: Mapped["User | None"] = sa_relationship(lazy="raise")


class InquiryFollowUp(Base, TenantMixin, SoftDeleteMixin):
    """
    Inquiry Follow-Up model.

    Scheduled follow-up tasks assigned to staff members.
    Uses RESTRICT on assigned_to FK to force reassignment before user deletion.
    """

    __tablename__ = "inquiry_follow_ups"

    inquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inquiries.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Staff responsible -- RESTRICT forces reassignment before user deletion",
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="medium",
        server_default="medium",
        comment="low, medium, high",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When completed (null = pending)",
    )

    # Relationships
    inquiry: Mapped["Inquiry"] = sa_relationship(
        back_populates="follow_ups",
        lazy="raise",
    )
    assigned_user: Mapped["User"] = sa_relationship(lazy="raise")

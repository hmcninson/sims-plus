"""
SIMS Plus - Parent Portal Models

Models for the parent portal: announcements, teacher notes,
and parent notification preferences.
"""

import uuid
from datetime import datetime, time
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    Time,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.boarding.models import House
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User


# =========================
# Enums
# =========================


class AnnouncementTarget(str, Enum):
    """Target audience for an announcement."""

    ALL_PARENTS = "all_parents"
    SPECIFIC_CLASS = "specific_class"
    SPECIFIC_HOUSE = "specific_house"
    BOARDING_PARENTS = "boarding_parents"
    TRANSPORT_PARENTS = "transport_parents"


class AnnouncementPriority(str, Enum):
    """Priority level for an announcement."""

    NORMAL = "normal"
    IMPORTANT = "important"
    URGENT = "urgent"


class NoteType(str, Enum):
    """Type of teacher note about a student."""

    POSITIVE = "positive"
    CONCERN = "concern"
    INFORMATION = "information"
    ACTION_REQUIRED = "action_required"


# =========================
# Announcement Model
# =========================


class Announcement(Base, TenantMixin, SoftDeleteMixin):
    """
    Announcement model.

    School-wide or targeted announcements visible to parents
    via the parent portal. Supports targeting by class, house,
    or parent category (boarding, transport).
    """

    __tablename__ = "announcements"
    __table_args__ = (
        {"extend_existing": True},
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_audience: Mapped[AnnouncementTarget] = mapped_column(
        SQLEnum(
            AnnouncementTarget,
            name="announcementtarget",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AnnouncementTarget.ALL_PARENTS,
    )
    target_class_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Required when target_audience is specific_class",
    )
    target_house_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("houses.id", ondelete="SET NULL"),
        nullable=True,
        comment="Required when target_audience is specific_house",
    )
    priority: Mapped[AnnouncementPriority] = mapped_column(
        SQLEnum(
            AnnouncementPriority,
            name="announcementpriority",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AnnouncementPriority.NORMAL,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL means draft; set to publish the announcement",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Announcement stops displaying after this time",
    )
    attachment_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    author: Mapped[Optional["User"]] = relationship("User", lazy="raise")
    target_class: Mapped[Optional["Class"]] = relationship("Class", lazy="raise")
    target_house: Mapped[Optional["House"]] = relationship("House", lazy="raise")


# =========================
# Teacher Note Model
# =========================


class TeacherNote(Base, TenantMixin, SoftDeleteMixin):
    """
    Teacher note model.

    Notes from teachers about individual students, visible to parents
    through the parent portal. Supports acknowledgement tracking.
    """

    __tablename__ = "teacher_notes"
    __table_args__ = (
        {"extend_existing": True},
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL means general note not tied to a subject",
    )
    note_type: Mapped[NoteType] = mapped_column(
        SQLEnum(
            NoteType,
            name="notetype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_visible_to_parent: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    parent_acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    parent_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    teacher: Mapped["User"] = relationship("User", lazy="raise")


# =========================
# Parent Notification Preferences Model
# =========================


class ParentNotificationPreference(Base, TenantMixin):
    """
    Parent notification preferences model.

    Per-user notification channel and category preferences for parents.
    Controls which notifications a parent receives and through which channels.
    No SoftDeleteMixin -- preferences are hard-deleted with the user.
    """

    __tablename__ = "parent_notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id",
            name="uq_parent_notification_preferences_tenant_user",
        ),
        {"extend_existing": True},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    push_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )

    # Category preferences
    notify_attendance: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    notify_grades: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    notify_finance: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    notify_announcements: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    notify_transport: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    notify_boarding: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )

    # Quiet hours
    quiet_hours_start: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Start of quiet hours (no notifications sent)",
    )
    quiet_hours_end: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="End of quiet hours",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="raise")

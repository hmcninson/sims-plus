"""
SIMS Plus - Academic Timetable and Calendar Models

Models for school periods, class timetables, and school holidays.
"""

import uuid
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.staff import Staff

    from .class_models import Class, ClassSection
    from .subject_models import Subject
    from .year_models import AcademicYear, Term


# =========================
# Enums
# =========================


class DayOfWeek(int, Enum):
    """Day of the week (0=Monday, 6=Sunday)."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


# =========================
# School Period
# =========================


class SchoolPeriod(Base, TenantMixin):
    """
    School Period Template model.

    Defines the period structure for a school (e.g., Period 1: 08:00-08:45).
    Schools can customize their own period timings.

    Period hierarchy:
    1. Section-specific periods (most specific) - class_id + section_id set
    2. Class-specific periods - class_id set, section_id NULL
    3. School-wide periods (default) - class_id NULL, section_id NULL
    """

    __tablename__ = "school_periods"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "class_id",
            "section_id",
            "period_number",
            name="uq_school_period",
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional: Link to specific class (NULL = school-wide)
    class_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,
        comment="If set, periods apply only to this class. NULL = school-wide.",
    )
    # Optional: Link to specific section (requires class_id)
    section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("class_sections.id", ondelete="CASCADE"),
        nullable=True,
        comment="If set, periods apply only to this section. NULL = class-wide or school-wide.",
    )
    period_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Period number (1, 2, 3...)",
    )
    name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Period name (e.g., 'Morning Assembly', 'Break')",
    )
    start_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Start time in HH:MM format",
    )
    end_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="End time in HH:MM format",
    )
    is_break: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether this is a break period (not for teaching)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Relationships
    class_: Mapped["Class | None"] = relationship(
        "Class",
        foreign_keys=[class_id],
        lazy="raise",
    )
    section: Mapped["ClassSection | None"] = relationship(
        "ClassSection",
        foreign_keys=[section_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<SchoolPeriod(period={self.period_number}, time={self.start_time}-{self.end_time}, class={self.class_id})>"


# =========================
# School Holiday
# =========================


class SchoolHoliday(Base, TenantMixin):
    """
    School Holiday/Event model.

    Defines holidays and special events when normal timetable doesn't apply.
    """

    __tablename__ = "school_holidays"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            name="uq_school_holiday_date",
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Holiday date",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Holiday name (e.g., 'Independence Day', 'Mid-term Break')",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    holiday_type: Mapped[str] = mapped_column(
        String(20),
        default="holiday",
        comment="Type: holiday, exam, event, vacation",
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=True,
        comment="Associated academic year (null for recurring holidays)",
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether this holiday recurs every year",
    )

    def __repr__(self) -> str:
        return f"<SchoolHoliday(date={self.date}, name='{self.name}')>"


# =========================
# Class Timetable
# =========================


class ClassTimetable(Base, TenantMixin):
    """
    Class Timetable model.

    Represents a weekly schedule entry for a class/section.
    Each entry defines a period with subject, teacher, and timing.
    Term is optional - if not specified, timetable applies to entire academic year.
    """

    __tablename__ = "class_timetables"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "class_id",
            "section_id",
            "academic_year_id",
            "term_id",
            "day_of_week",
            "period_number",
            name="uq_timetable_period",
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="CASCADE"),
        nullable=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=True,
        comment="Optional: if set, timetable applies only to this term",
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Schedule details
    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Day of week (0=Monday, 6=Sunday)",
    )
    period_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Period number within the day (1, 2, 3...)",
    )
    start_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Start time in HH:MM format",
    )
    end_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="End time in HH:MM format",
    )

    # Venue/Room
    room: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Room or venue for the class",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether this timetable entry is active",
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )

    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use selectinload()/joinedload() explicitly in queries that need these.
    class_: Mapped["Class"] = relationship("Class", lazy="raise")
    section: Mapped["ClassSection | None"] = relationship("ClassSection", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    term: Mapped["Term | None"] = relationship("Term", lazy="raise")
    subject: Mapped["Subject | None"] = relationship("Subject", lazy="raise")
    teacher: Mapped["Staff | None"] = relationship("Staff", lazy="raise")

    def __repr__(self) -> str:
        return f"<ClassTimetable(class_id={self.class_id}, term_id={self.term_id}, day={self.day_of_week}, period={self.period_number})>"

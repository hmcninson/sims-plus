"""
SIMS Plus - Attendance Models

Database models for student and staff attendance tracking.
"""

from datetime import date, time
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    String,
    Text,
    Time,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.staff import Staff
    from app.models.academic import Term, ClassSection


class AttendanceStatus(str, Enum):
    """Attendance status options."""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    SICK = "sick"


class StudentAttendance(Base, TenantMixin):
    """
    Student Attendance model.

    Records daily attendance for students.
    """
    __tablename__ = "student_attendance"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "student_id", "date",
            name="uq_student_attendance_date"
        ),
        {"extend_existing": True},
    )

    # Foreign keys
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[UUID] = mapped_column(
        ForeignKey("class_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Class section at time of attendance",
    )
    term_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Academic term for this attendance",
    )

    # Attendance details
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of attendance",
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(AttendanceStatus, name="attendancestatus", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AttendanceStatus.PRESENT,
    )
    check_in_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Time student checked in",
    )
    check_out_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Time student checked out (for day students)",
    )

    # Additional info
    remarks: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes/remarks for this attendance record",
    )
    excuse_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for absence/excuse (if applicable)",
    )

    # Who marked the attendance
    marked_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who marked this attendance",
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        lazy="selectin",
    )
    section: Mapped["ClassSection"] = relationship(
        "ClassSection",
        lazy="selectin",
    )
    term: Mapped[Optional["Term"]] = relationship(
        "Term",
        lazy="selectin",
    )


class StaffAttendance(Base, TenantMixin):
    """
    Staff Attendance model.

    Records daily attendance for staff members.
    """
    __tablename__ = "staff_attendance"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "staff_id", "date",
            name="uq_staff_attendance_date"
        ),
        {"extend_existing": True},
    )

    # Foreign keys
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Academic term for this attendance",
    )

    # Attendance details
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of attendance",
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(AttendanceStatus, name="attendancestatus", create_constraint=False),
        nullable=False,
        default=AttendanceStatus.PRESENT,
    )
    check_in_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Time staff checked in",
    )
    check_out_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Time staff checked out",
    )

    # Additional info
    remarks: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes/remarks for this attendance record",
    )
    excuse_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for absence/excuse (if applicable)",
    )

    # Who marked the attendance
    marked_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who marked this attendance",
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="selectin",
    )
    term: Mapped[Optional["Term"]] = relationship(
        "Term",
        lazy="selectin",
    )

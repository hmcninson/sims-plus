"""
SIMS Plus - Staff Model

Database models for staff management (teachers and non-teaching staff).
"""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    String,
    Text,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin
from app.models.student import Gender

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.models.academic import ClassSection


class StaffType(str, Enum):
    """Staff employment type."""
    TEACHING = "teaching"
    NON_TEACHING = "non_teaching"
    ADMINISTRATIVE = "administrative"


class StaffStatus(str, Enum):
    """Staff employment status."""
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    RETIRED = "retired"


class Staff(Base, TenantMixin, SoftDeleteMixin):
    """
    Staff model.

    Represents teaching and non-teaching staff members.
    """
    __tablename__ = "staff"
    __table_args__ = (
        UniqueConstraint("staff_id", "tenant_id", name="uq_staff_staff_id_tenant"),
        UniqueConstraint("email", "tenant_id", name="uq_staff_email_tenant"),
        {"extend_existing": True},
    )

    # System ID
    staff_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="System-generated unique staff ID (e.g., STF-2026-001)",
    )

    # Basic Information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender] = mapped_column(
        SQLEnum(Gender, name="gender", create_constraint=False),
        nullable=False,
    )

    # Contact Information
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_secondary: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Emergency Contact
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    emergency_contact_relationship: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Ghana-specific IDs
    ghana_card_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ssnit_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    teacher_license_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="GES Teacher License Number (for certified teachers)",
    )

    # Employment Information
    staff_type: Mapped[StaffType] = mapped_column(
        SQLEnum(StaffType, name="stafftype", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StaffType.TEACHING,
    )
    status: Mapped[StaffStatus] = mapped_column(
        SQLEnum(StaffStatus, name="staffstatus", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StaffStatus.ACTIVE,
    )
    job_title: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employment_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Qualifications (stored as JSON array)
    # Example: [{"degree": "B.Ed", "institution": "UCC", "year": 2015}, ...]
    qualifications: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    # Banking Information (for payroll)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Photo
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign Keys
    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        comment="Link to User for system login access",
    )

    # Relationships
    school: Mapped[Optional["School"]] = relationship(
        "School",
        back_populates="staff_members",
        lazy="selectin",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="staff_profile",
        lazy="selectin",
    )
    class_assignments: Mapped[list["StaffClassAssignment"]] = relationship(
        "StaffClassAssignment",
        back_populates="staff",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def full_name(self) -> str:
        """Get the staff member's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def is_teaching_staff(self) -> bool:
        """Check if staff is a teaching staff member."""
        return self.staff_type == StaffType.TEACHING


class StaffClassAssignment(Base, TenantMixin):
    """
    Staff-Class assignment table.

    Links teaching staff to class sections they teach.
    """
    __tablename__ = "staff_class_assignments"
    __table_args__ = (
        UniqueConstraint(
            "staff_id", "section_id", "tenant_id",
            name="uq_staff_class_assignment_tenant"
        ),
        {"extend_existing": True},
    )

    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[UUID] = mapped_column(
        ForeignKey("class_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_class_teacher: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether this staff is the class teacher for this section",
    )
    subject_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"),
        nullable=True,
        comment="Subject taught in this section (if applicable)",
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        back_populates="class_assignments",
        lazy="selectin",
    )
    section: Mapped["ClassSection"] = relationship(
        "ClassSection",
        back_populates="staff_assignments",
        lazy="selectin",
    )

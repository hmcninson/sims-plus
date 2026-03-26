"""
SIMS Plus - Staff Model

Database models for staff management (teachers and non-teaching staff).
"""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin
from app.models.student import Gender

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User
    from app.models.academic import ClassSection


class Department(Base, TenantMixin, SoftDeleteMixin):
    """
    Department model.

    Represents organizational departments within a school.
    """
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("name", "tenant_id", "deleted_at", name="uq_department_name_tenant"),
        {"extend_existing": True},
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    head_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        comment="Department head (staff member)",
    )

    # Relationships
    staff_members: Mapped[list["Staff"]] = relationship(
        "Staff",
        back_populates="department_rel",
        foreign_keys="Staff.department_id",
        lazy="raise",
    )


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


class EmploymentType(str, Enum):
    """Employment type (full-time, part-time, etc.)."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERN = "intern"


class StaffDocumentType(str, Enum):
    """Types of staff documents."""
    CONTRACT = "contract"
    CERTIFICATE = "certificate"
    CV_RESUME = "cv_resume"
    ID_DOCUMENT = "id_document"
    REFERENCE_LETTER = "reference_letter"
    DISCIPLINARY = "disciplinary"
    TRAINING = "training"
    MEDICAL = "medical"
    OTHER = "other"


class EmploymentEventType(str, Enum):
    """Types of employment history events."""
    HIRED = "hired"
    PROMOTED = "promoted"
    DEMOTED = "demoted"
    TRANSFERRED = "transferred"
    TITLE_CHANGED = "title_changed"
    DEPARTMENT_CHANGED = "department_changed"
    STATUS_CHANGED = "status_changed"
    SALARY_CHANGED = "salary_changed"
    CONTRACT_RENEWED = "contract_renewed"


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
    previous_staff_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="ID from previous/external system (for reference during migration)",
    )

    # Basic Information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender] = mapped_column(
        SQLEnum(Gender, name="gender", create_constraint=False, values_callable=lambda x: [e.value for e in x]),
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
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Legacy department name field")
    department_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to department",
    )
    employment_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(
        SQLEnum(EmploymentType, name="employmenttype", create_constraint=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    # HR-specific fields
    tin_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ges_staff_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

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
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use selectinload()/joinedload() explicitly in queries that need these.
    school: Mapped[Optional["School"]] = relationship(
        "School",
        back_populates="staff_members",
        lazy="raise",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="staff_profile",
        lazy="raise",
    )
    department_rel: Mapped[Optional["Department"]] = relationship(
        "Department",
        back_populates="staff_members",
        foreign_keys=[department_id],
        lazy="raise",
    )
    class_assignments: Mapped[list["StaffClassAssignment"]] = relationship(
        "StaffClassAssignment",
        back_populates="staff",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    documents: Mapped[list["StaffDocument"]] = relationship(
        "StaffDocument",
        back_populates="staff",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    employment_history: Mapped[list["StaffEmploymentHistory"]] = relationship(
        "StaffEmploymentHistory",
        back_populates="staff",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="desc(StaffEmploymentHistory.effective_date)",
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

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        lazy="raise",
    )
    section: Mapped["ClassSection"] = relationship(
        "ClassSection",
        back_populates="staff_assignments",
        lazy="raise",
    )


class StaffDocument(Base, TenantMixin, SoftDeleteMixin):
    """
    Staff document model.

    Stores references to uploaded staff documents (contracts, certificates,
    CVs, ID documents, etc.) with S3 file keys.
    """
    __tablename__ = "staff_documents"
    __table_args__ = {"extend_existing": True}

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[StaffDocumentType] = mapped_column(
        SQLEnum(StaffDocumentType, name="staffdocumenttype", create_constraint=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        back_populates="documents",
        lazy="raise",
    )


class StaffEmploymentHistory(Base, TenantMixin):
    """
    Staff employment history model.

    Tracks employment events: promotions, transfers, department changes,
    title changes, status changes, salary changes, etc.
    NO SoftDeleteMixin — history records are permanent.
    """
    __tablename__ = "staff_employment_history"
    __table_args__ = {"extend_existing": True}

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[EmploymentEventType] = mapped_column(
        SQLEnum(EmploymentEventType, name="employmenteventtype", create_constraint=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_department_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    new_department_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    new_job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        back_populates="employment_history",
        lazy="raise",
    )

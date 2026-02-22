"""
SIMS Plus - Student and Guardian Models

Database models for student management.
"""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from decimal import Decimal
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.academic import Class, ClassSection
    from app.models.school import School


class Gender(str, Enum):
    """Gender options."""
    MALE = "male"
    FEMALE = "female"


class StudentStatus(str, Enum):
    """Student enrollment status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    GRADUATED = "graduated"
    TRANSFERRED = "transferred"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"


class GuardianRelationship(str, Enum):
    """Guardian relationship to student."""
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    UNCLE = "uncle"
    AUNT = "aunt"
    SIBLING = "sibling"
    OTHER = "other"


class Student(Base, TenantMixin, SoftDeleteMixin):
    """
    Student model.

    Represents a student enrolled in a school.
    """
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("student_id", "tenant_id", name="uq_students_student_id_tenant"),
        {"extend_existing": True},
    )

    # Basic Information
    student_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="System-generated unique student ID (e.g., STU-2026-001)",
    )
    previous_student_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Student ID from previous/external system (for migration reference)",
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[Gender] = mapped_column(
        SQLEnum(Gender, name="gender", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Contact Information
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Ghana-specific IDs
    ghana_card_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nhis_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Academic Information
    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    class_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
    )
    section_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    admission_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    admission_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    status: Mapped[StudentStatus] = mapped_column(
        SQLEnum(StudentStatus, name="studentstatus", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StudentStatus.ACTIVE,
    )

    # Boarding Information
    is_boarder: Mapped[bool] = mapped_column(Boolean, default=False)

    # Medical Information
    blood_group: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    medical_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Photo
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Finance
    credit_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Available credit balance from credit notes",
    )

    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use selectinload()/joinedload() explicitly in queries that need these.
    school: Mapped[Optional["School"]] = relationship(
        "School",
        back_populates="students",
        lazy="raise",
    )
    class_: Mapped[Optional["Class"]] = relationship(
        "Class",
        back_populates="students",
        lazy="raise",
    )
    section: Mapped[Optional["ClassSection"]] = relationship(
        "ClassSection",
        back_populates="students",
        lazy="raise",
    )
    guardians: Mapped[list["StudentGuardian"]] = relationship(
        "StudentGuardian",
        back_populates="student_rel",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        """Calculate the student's age."""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def primary_guardian(self) -> Optional["StudentGuardian"]:
        """Get the primary guardian."""
        for guardian in self.guardians:
            if guardian.is_primary:
                return guardian
        return self.guardians[0] if self.guardians else None


class Guardian(Base, TenantMixin, SoftDeleteMixin):
    """
    Guardian model.

    Represents a parent or guardian who can have multiple students.
    """
    __tablename__ = "guardians"
    __table_args__ = (
        UniqueConstraint("email", "tenant_id", name="uq_guardians_email_tenant"),
        {"extend_existing": True},
    )

    # Basic Information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Contact Information (phone is required)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_secondary: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Work Information
    occupation: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    workplace: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    work_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Ghana-specific
    ghana_card_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Photo
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    students: Mapped[list["StudentGuardian"]] = relationship(
        "StudentGuardian",
        back_populates="guardian_rel",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @property
    def full_name(self) -> str:
        """Get the guardian's full name."""
        return f"{self.first_name} {self.last_name}"


class StudentGuardian(Base, TenantMixin):
    """
    Student-Guardian association table.

    Links students to their guardians with relationship details.
    """
    __tablename__ = "student_guardians"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "guardian_id", "tenant_id",
            name="uq_student_guardian_tenant"
        ),
        {"extend_existing": True},
    )

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    guardian_id: Mapped[UUID] = mapped_column(
        ForeignKey("guardians.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[GuardianRelationship] = mapped_column(
        "relationship",
        SQLEnum(GuardianRelationship, name="guardianrelationship", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_emergency_contact: Mapped[bool] = mapped_column(Boolean, default=True)
    can_pickup: Mapped[bool] = mapped_column(Boolean, default=True)

    # ORM Relationships
    student_rel: Mapped["Student"] = relationship(
        "Student",
        back_populates="guardians",
        lazy="raise",
    )
    guardian_rel: Mapped["Guardian"] = relationship(
        "Guardian",
        back_populates="students",
        lazy="raise",
    )

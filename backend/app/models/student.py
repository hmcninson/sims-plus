"""
SIMS Plus - Student and Guardian Models

Database models for student management.
"""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, ClassSection
    from app.models.curriculum import CurriculumProfile
    from app.models.school import School
    from app.models.user import User


class StudentDocumentType(str, Enum):
    """Type of document uploaded for a student."""
    BIRTH_CERTIFICATE = "birth_certificate"
    MEDICAL_RECORD = "medical_record"
    TRANSFER_LETTER = "transfer_letter"
    REPORT_CARD = "report_card"
    ID_CARD = "id_card"
    LEAVING_CERTIFICATE = "leaving_certificate"
    PHOTO = "photo"
    OTHER = "other"


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

    # Preschool-specific fields
    enrollment_session: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Preschool session type: half_day_morning, half_day_afternoon, full_day, extended",
    )
    dietary_requirements: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured dietary/allergy data for preschool students",
    )

    # Finance
    credit_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Available credit balance from credit notes",
    )

    # Curriculum tracking
    curriculum_profile_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
        nullable=True,
        comment="Student's current curriculum (inherited from class if NULL)",
    )
    previous_curriculum_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="For transfer students -- records origin curriculum type",
    )

    # Profile extensions (Phase 3)
    birth_certificate_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
    )
    structured_medical: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="Structured medical data (conditions, allergies, vaccinations, etc.)",
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
    curriculum_profile: Mapped[Optional["CurriculumProfile"]] = relationship(
        "CurriculumProfile",
        lazy="raise",
    )
    class_history: Mapped[list["StudentClassHistory"]] = relationship(
        "StudentClassHistory",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    status_changes: Mapped[list["StudentStatusChange"]] = relationship(
        "StudentStatusChange",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    documents: Mapped[list["StudentDocument"]] = relationship(
        "StudentDocument",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    previous_schools: Mapped[list["PreviousSchool"]] = relationship(
        "PreviousSchool",
        back_populates="student",
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

    # School (nullable for chain support; guardians may be shared across schools)
    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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


class StudentClassHistory(Base, TenantMixin):
    """
    Immutable audit record of student class/section assignments.

    Tracks every class a student has been enrolled in, including
    the academic year, enrolled/left dates, and reason for leaving.
    No SoftDeleteMixin — this is an append-only audit table.
    """
    __tablename__ = "student_class_history"
    __table_args__ = {"extend_existing": True}

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    enrolled_date: Mapped[date] = mapped_column(Date, nullable=False)
    left_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="class_history",
        lazy="raise",
    )
    school: Mapped["School"] = relationship(
        "School",
        lazy="raise",
    )
    class_: Mapped["Class"] = relationship(
        "Class",
        lazy="raise",
    )
    section: Mapped[Optional["ClassSection"]] = relationship(
        "ClassSection",
        lazy="raise",
    )
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        lazy="raise",
    )


class StudentStatusChange(Base, TenantMixin):
    """
    Immutable audit record of student enrollment status transitions.

    Tracks every status change (e.g., active -> suspended, active -> withdrawn).
    No SoftDeleteMixin — this is an append-only audit table (INSERT only).
    """
    __tablename__ = "student_status_changes"
    __table_args__ = {"extend_existing": True}

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Previous status (NULL for initial enrollment)",
    )
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed the status change (nullable for user deletion)",
    )
    # Python attr is change_metadata to avoid shadowing SQLAlchemy Base.metadata.
    # DB column remains "metadata".
    change_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True,
    )

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="status_changes",
        lazy="raise",
    )
    school: Mapped["School"] = relationship(
        "School",
        lazy="raise",
    )
    performed_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="raise",
        foreign_keys=[performed_by],
    )


class WithdrawalClearance(Base, TenantMixin):
    """Clearance checklist for student withdrawal or external transfer."""
    __tablename__ = "withdrawal_clearances"
    __table_args__ = (
        CheckConstraint("type IN ('withdrawal', 'transfer')", name="ck_wc_type"),
        {"extend_existing": True},
    )

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    status_change_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("student_status_changes.id", ondelete="CASCADE"),
        nullable=True,
        comment="Set when withdrawal/transfer is completed",
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="withdrawal or transfer",
    )
    library_cleared: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false"), nullable=False,
    )
    finance_cleared: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false"), nullable=False,
    )
    property_cleared: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false"), nullable=False,
    )
    boarding_cleared: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True,
        comment="NULL if student is not a boarder",
    )
    outstanding_fees: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True,
    )
    fee_override: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false"), nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_complete: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false"), nullable=False,
    )
    cleared_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cleared_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        lazy="raise",
    )
    school: Mapped["School"] = relationship(
        "School",
        lazy="raise",
    )
    status_change: Mapped[Optional["StudentStatusChange"]] = relationship(
        "StudentStatusChange",
        lazy="raise",
    )
    cleared_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="raise",
        foreign_keys=[cleared_by],
    )


class StudentDocument(Base, TenantMixin, SoftDeleteMixin):
    """
    Uploaded document associated with a student.

    Supports birth certificates, medical records, transfer letters,
    report cards, ID cards, leaving certificates, photos, and other documents.
    Uses SoftDeleteMixin for soft deletes (deleted_at column).
    """
    __tablename__ = "student_documents"
    __table_args__ = {"extend_existing": True}

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[StudentDocumentType] = mapped_column(
        SQLEnum(
            StudentDocumentType,
            name="studentdocumenttype",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="S3 object key for the uploaded document",
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="File size in bytes",
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who uploaded the document (nullable for user deletion)",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="documents",
        lazy="raise",
    )
    school: Mapped["School"] = relationship(
        "School",
        lazy="raise",
    )
    uploaded_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        lazy="raise",
        foreign_keys=[uploaded_by],
    )


class PreviousSchool(Base, TenantMixin):
    """
    Academic history at a prior institution.

    Records details about schools a student previously attended,
    including the school name, last class, years attended, and
    transfer reason. No SoftDeleteMixin — records are hard-deleted.
    """
    __tablename__ = "previous_schools"
    __table_args__ = {"extend_existing": True}

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        comment="Current school (for chain filtering)",
    )
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    years_attended: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transfer_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    leaving_certificate_ref: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="previous_schools",
        lazy="raise",
    )
    school: Mapped["School"] = relationship(
        "School",
        lazy="raise",
    )

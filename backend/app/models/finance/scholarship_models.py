"""
SIMS Plus - Finance Scholarship Models

Models for scholarships, student scholarship awards, and scholarship applications.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
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
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User


# =========================
# Enums
# =========================


class ScholarshipType(str, Enum):
    """Type of scholarship."""

    FULL = "full"
    PARTIAL = "partial"
    MERIT = "merit"
    NEED_BASED = "need_based"
    ATHLETIC = "athletic"
    SPECIAL = "special"


class CoverageType(str, Enum):
    """How scholarship coverage is calculated."""

    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


class ScholarshipStatus(str, Enum):
    """Status of a student's scholarship."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApplicationStatus(str, Enum):
    """Status of a scholarship application."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RenewalType(str, Enum):
    """Scholarship renewal types."""

    ONE_TIME = "one_time"
    ANNUAL = "annual"
    UNTIL_GRADUATION = "until_graduation"


# =========================
# Scholarship Model
# =========================


class Scholarship(Base, TenantMixin, SoftDeleteMixin):
    """
    Scholarship model.

    Defines a scholarship program that can be awarded to students.
    """

    __tablename__ = "scholarships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_scholarship_code"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Scholarship name, e.g., Academic Excellence Award",
    )
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Unique code, e.g., AEA-2026",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    scholarship_type: Mapped[ScholarshipType] = mapped_column(
        SQLEnum(
            ScholarshipType,
            name="scholarshiptype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    coverage_type: Mapped[CoverageType] = mapped_column(
        SQLEnum(
            CoverageType,
            name="coveragetype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    coverage_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Percentage (0-100) or fixed GHS amount",
    )
    applicable_fees: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Which fee items it covers: ["tuition", "all"] or specific IDs',
    )
    max_recipients: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Optional: limit number of awards",
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
    )
    eligibility_criteria: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='{"min_gpa": 3.5, "max_income": 5000}',
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Audit
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    recipients: Mapped[list["StudentScholarship"]] = relationship(
        "StudentScholarship",
        back_populates="scholarship",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @property
    def recipients_count(self) -> int:
        """Count of active recipients."""
        return len([r for r in self.recipients if r.status == ScholarshipStatus.ACTIVE])

    def __repr__(self) -> str:
        return f"<Scholarship(name='{self.name}', type='{self.scholarship_type}', coverage={self.coverage_value})>"


# =========================
# Student Scholarship Model
# =========================


class StudentScholarship(Base, TenantMixin):
    """
    Student Scholarship model.

    Records a scholarship awarded to a student.
    """

    __tablename__ = "student_scholarships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scholarship_id",
            "student_id",
            "academic_year_id",
            name="uq_student_scholarship_unique",
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scholarship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scholarships.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    awarded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[ScholarshipStatus] = mapped_column(
        SQLEnum(
            ScholarshipStatus,
            name="scholarshipstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ScholarshipStatus.ACTIVE,
        nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="NULL = until end of academic year",
    )
    coverage_override: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Override default coverage if needed",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Enhanced award settings (Phase 1 improvements)
    justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Required justification/reason for awarding the scholarship",
    )
    renewal_type: Mapped[str] = mapped_column(
        String(20),
        default="one_time",
        nullable=False,
        comment="Renewal type: one_time, annual, until_graduation",
    )
    is_provisional: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is a provisional/conditional award",
    )
    provisional_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditions that must be met for provisional awards",
    )

    # Revocation info
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoke_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Reinstatement tracking
    reinstated_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_scholarships.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to previously revoked scholarship if this is a reinstatement",
    )

    # Relationships
    scholarship: Mapped["Scholarship"] = relationship(
        "Scholarship",
        back_populates="recipients",
        lazy="raise",
    )
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    awarded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[awarded_by],
        lazy="raise",
    )
    revoked_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[revoked_by],
        lazy="raise",
    )
    reinstated_from_record: Mapped["StudentScholarship | None"] = relationship(
        "StudentScholarship",
        foreign_keys=[reinstated_from],
        remote_side="StudentScholarship.id",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<StudentScholarship(student_id='{self.student_id}', scholarship_id='{self.scholarship_id}', status='{self.status}')>"


# =========================
# Scholarship Application Model
# =========================


class ScholarshipApplication(Base, TenantMixin):
    """
    Scholarship Application model.

    Records a student's application for a scholarship.
    """

    __tablename__ = "scholarship_applications"

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scholarship_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scholarships.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(
            ApplicationStatus,
            name="applicationstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ApplicationStatus.PENDING,
        nullable=False,
    )
    supporting_documents: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="[{name, url, type}]",
    )
    application_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Review info
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    scholarship: Mapped["Scholarship"] = relationship("Scholarship", lazy="raise")
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    reviewer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reviewer_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ScholarshipApplication(student_id='{self.student_id}', scholarship_id='{self.scholarship_id}', status='{self.status}')>"

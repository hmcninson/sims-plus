"""
SIMS Plus - Academic Subject and Grading Models

Models for subjects, grading scales, grades, assessment weights, and academic settings.
"""

import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin


# =========================
# Enums
# =========================


class SubjectCategory(str, Enum):
    """Category of subjects."""

    CORE = "core"  # Compulsory for all
    ELECTIVE = "elective"  # Optional
    VOCATIONAL = "vocational"  # Technical/vocational
    EXTRA = "extra"  # Extra-curricular


class GradingScaleType(str, Enum):
    """Type of grading scale."""

    WAEC = "waec"  # WAEC standard (A1-F9)
    GPA = "gpa"  # GPA scale (4.0)
    PERCENTAGE = "percentage"  # Percentage-based
    CUSTOM = "custom"  # Custom scale


# =========================
# Subject
# =========================


class Subject(Base, TenantMixin, SoftDeleteMixin):
    """
    Subject model.

    A subject taught in the school (e.g., Mathematics, English).
    """

    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_subject_code"),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Subject name",
    )
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Subject code, e.g., MATH, ENG",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Category
    category: Mapped[SubjectCategory] = mapped_column(
        SQLEnum(
            SubjectCategory,
            name="subjectcategory",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=SubjectCategory.CORE,
        nullable=False,
    )

    # Applicable class levels (which class levels can use this subject)
    # e.g., ["primary", "jhs"] for Math, ["preschool"] for preschool-only subjects
    # None or empty means applicable to all levels
    applicable_levels: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="List of class levels this subject applies to (null = all levels)",
    )

    # Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    class_subjects: Mapped[list["ClassSubject"]] = relationship(
        "ClassSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Subject(name='{self.name}', code='{self.code}')>"


# =========================
# Grading Scale
# =========================


class GradingScale(Base, TenantMixin, SoftDeleteMixin):
    """
    Grading Scale model.

    Defines the grading system used by the school.
    """

    __tablename__ = "grading_scales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_grading_scale_name"),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Scale name, e.g., WAEC Standard",
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    scale_type: Mapped[GradingScaleType] = mapped_column(
        SQLEnum(
            GradingScaleType,
            name="gradingscaletype",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=GradingScaleType.WAEC,
        nullable=False,
    )

    # Is this the default scale for the tenant?
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    # Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    grades: Mapped[list["Grade"]] = relationship(
        "Grade",
        back_populates="grading_scale",
        cascade="all, delete-orphan",
        order_by="Grade.min_score.desc()",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<GradingScale(name='{self.name}', type='{self.scale_type}')>"


class Grade(Base, TenantMixin):
    """
    Grade model.

    Individual grade within a grading scale (e.g., A1, B2, C4).
    """

    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "grading_scale_id", "grade", name="uq_grade"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    grading_scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Grade Info
    grade: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Grade symbol, e.g., A1, B2",
    )
    min_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Minimum score for this grade",
    )
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Maximum score for this grade",
    )
    grade_point: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Grade point value (for GPA)",
    )
    remark: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Grade remark, e.g., Excellent, Good",
    )

    # Relationships
    grading_scale: Mapped["GradingScale"] = relationship(
        "GradingScale",
        back_populates="grades",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Grade(grade='{self.grade}', range={self.min_score}-{self.max_score})>"


# =========================
# Assessment Weight Configuration
# =========================


class AssessmentWeight(Base, TenantMixin):
    """
    Assessment weight configuration.

    Defines how different assessments contribute to final grades.
    """

    __tablename__ = "assessment_weights"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "academic_year_id", name="uq_assessment_weight"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
        comment="Specific to an academic year, or null for default",
    )

    # Individual component weights (for detailed breakdown, must sum to 100)
    class_work_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=20,
        comment="Class work percentage",
    )
    homework_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=10,
        comment="Homework percentage",
    )
    midterm_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=20,
        comment="Mid-term exam percentage",
    )
    end_term_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=50,
        comment="End of term exam percentage",
    )

    # Report card weights (Ghana's system: CA vs Exams split)
    # These control how Class Score and Exams Score are displayed on report cards
    ca_total_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=50,
        comment="Total weight for all Continuous Assessment components on report card (default 50%)",
    )
    exam_total_weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=50,
        comment="Total weight for End of Term Exam on report card (default 50%)",
    )

    def __repr__(self) -> str:
        return f"<AssessmentWeight(cw={self.class_work_weight}, hw={self.homework_weight}, mid={self.midterm_weight}, end={self.end_term_weight}, ca_total={self.ca_total_weight}, exam_total={self.exam_total_weight})>"


# =========================
# Academic Settings
# =========================


class AcademicSettings(Base, TenantMixin):
    """
    Academic settings for a tenant.

    Stores various boolean flags that control academic behavior.
    One record per tenant.
    """

    __tablename__ = "academic_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_academic_settings_tenant"),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Auto-promote passing students at end of academic year
    auto_promote_students: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Automatically promote passing students at end of academic year",
    )

    # Allow teachers to amend grades after submission (with approval)
    allow_grade_amendments: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Allow teachers to amend grades after submission",
    )

    # Display class position/ranking on student report cards
    show_position_on_report_cards: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Display class position/ranking on report cards",
    )

    # Students must have attendance records before exam scores can be entered
    require_attendance_for_exams: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Require attendance records before exam score entry",
    )

    # Track class work, assignments, and tests throughout the term
    enable_continuous_assessment: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Enable continuous assessment tracking",
    )

    def __repr__(self) -> str:
        return f"<AcademicSettings(tenant_id={self.tenant_id})>"


# Import ClassSubject here so it can be referenced by Subject.class_subjects relationship.
# This avoids circular imports since class_models.py imports Subject from here via TYPE_CHECKING.
from .class_models import ClassSubject  # noqa: E402, F401

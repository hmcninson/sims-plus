"""
SIMS Plus - Academic Models

Models for academic structure: Academic Years, Terms, Classes, Sections, Subjects, Grading.
"""

import uuid
from enum import Enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
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
    from app.models.student import Student


# =========================
# Enums
# =========================


class AcademicYearStatus(str, Enum):
    """Status of an academic year."""

    PLANNING = "planning"  # Being set up
    ACTIVE = "active"  # Currently running
    COMPLETED = "completed"  # Finished


class TermStatus(str, Enum):
    """Status of a term/semester."""

    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"


class ClassLevel(str, Enum):
    """Class level/grade."""

    # Category levels (simplified)
    PRESCHOOL = "preschool"
    PRIMARY = "primary"
    JHS = "jhs"
    SHS = "shs"

    # Specific grade levels (for backward compatibility)
    NURSERY_1 = "nursery_1"
    NURSERY_2 = "nursery_2"
    KG_1 = "kg_1"
    KG_2 = "kg_2"
    PRIMARY_1 = "primary_1"
    PRIMARY_2 = "primary_2"
    PRIMARY_3 = "primary_3"
    PRIMARY_4 = "primary_4"
    PRIMARY_5 = "primary_5"
    PRIMARY_6 = "primary_6"
    JHS_1 = "jhs_1"
    JHS_2 = "jhs_2"
    JHS_3 = "jhs_3"
    SHS_1 = "shs_1"
    SHS_2 = "shs_2"
    SHS_3 = "shs_3"


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
# Academic Year
# =========================


class AcademicYear(Base, TenantMixin, SoftDeleteMixin):
    """
    Academic year model.

    Represents a school year (e.g., 2025/2026).
    """

    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_academic_year_name"),
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Year name, e.g., 2025/2026",
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Dates
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Academic year start date",
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Academic year end date",
    )

    # Status
    status: Mapped[AcademicYearStatus] = mapped_column(
        SQLEnum(
            AcademicYearStatus,
            name="academicyearstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AcademicYearStatus.PLANNING,
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Is this the current academic year?",
    )

    # Relationships
    terms: Mapped[list["Term"]] = relationship(
        "Term",
        back_populates="academic_year",
        cascade="all, delete-orphan",
        order_by="Term.start_date",
    )

    def __repr__(self) -> str:
        return f"<AcademicYear(name='{self.name}', status='{self.status}')>"


# =========================
# Term / Semester
# =========================


class Term(Base, TenantMixin, SoftDeleteMixin):
    """
    Term/Semester model.

    A period within an academic year (e.g., First Term, Second Term).
    """

    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "academic_year_id", "name", name="uq_term_name"
        ),
    )

    # Relationship to Academic Year
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Term name, e.g., First Term",
    )
    short_name: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Short name, e.g., Term 1",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Order of term within year (1, 2, 3)",
    )

    # Dates
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Status
    status: Mapped[TermStatus] = mapped_column(
        SQLEnum(
            TermStatus,
            name="termstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TermStatus.UPCOMING,
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Is this the current term?",
    )

    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        back_populates="terms",
    )

    def __repr__(self) -> str:
        return f"<Term(name='{self.name}', status='{self.status}')>"


# =========================
# Class (Grade Level)
# =========================


class Class(Base, TenantMixin, SoftDeleteMixin):
    """
    Class model.

    Represents a grade level (e.g., JHS 1, SHS 2).
    Each class can have multiple sections (e.g., JHS 1A, JHS 1B).
    """

    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_class_name"),
    )

    # School (optional, for multi-school tenants)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Class name, e.g., JHS 1, Form 1",
    )
    short_name: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Short name, e.g., J1, F1",
    )
    level: Mapped[ClassLevel | None] = mapped_column(
        SQLEnum(
            ClassLevel,
            name="classlevel",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
        comment="Standard level mapping",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Order for display",
    )

    # Capacity
    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum students",
    )

    # Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    sections: Mapped[list["ClassSection"]] = relationship(
        "ClassSection",
        back_populates="class_",
        cascade="all, delete-orphan",
        order_by="ClassSection.name",
        primaryjoin="and_(Class.id == foreign(ClassSection.class_id), ClassSection.deleted_at.is_(None))",
    )
    subjects: Mapped[list["ClassSubject"]] = relationship(
        "ClassSubject",
        back_populates="class_",
        cascade="all, delete-orphan",
    )
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="class_",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Class(name='{self.name}')>"


# =========================
# Class Section
# =========================


class ClassSection(Base, TenantMixin, SoftDeleteMixin):
    """
    Class Section model.

    A division of a class (e.g., JHS 1A, JHS 1B).
    """

    __tablename__ = "class_sections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "name", name="uq_section_name"
        ),
    )

    # Relationship to Class
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Section name, e.g., A, B, Science, Arts",
    )

    # Capacity
    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum students in section",
    )

    # Class Teacher (optional, will link to Staff later)
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Assigned class teacher",
    )

    # Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    class_: Mapped["Class"] = relationship(
        "Class",
        back_populates="sections",
    )
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="section",
        lazy="selectin",
    )

    @property
    def full_name(self) -> str:
        """Get full section name (e.g., JHS 1A)."""
        return f"{self.class_.name} {self.name}"

    def __repr__(self) -> str:
        return f"<ClassSection(name='{self.name}')>"


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

    # Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    class_subjects: Mapped[list["ClassSubject"]] = relationship(
        "ClassSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Subject(name='{self.name}', code='{self.code}')>"


# =========================
# Class Subject (M2M)
# =========================


class ClassSubject(Base, TenantMixin):
    """
    Class-Subject association.

    Links subjects to classes with additional metadata.
    """

    __tablename__ = "class_subjects"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "subject_id", name="uq_class_subject"
        ),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional: periods per week
    periods_per_week: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of periods per week",
    )

    # Is this subject compulsory for this class?
    is_compulsory: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Relationships
    class_: Mapped["Class"] = relationship(
        "Class",
        back_populates="subjects",
    )
    subject: Mapped["Subject"] = relationship(
        "Subject",
        back_populates="class_subjects",
    )


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

    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
        comment="Specific to an academic year, or null for default",
    )

    # Weights (must sum to 100)
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

    def __repr__(self) -> str:
        return f"<AssessmentWeight(cw={self.class_work_weight}, hw={self.homework_weight}, mid={self.midterm_weight}, end={self.end_term_weight})>"


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

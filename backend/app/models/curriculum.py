"""
SIMS Plus - Multi-Curriculum Models

Models for curriculum profiles, assessment structures, components,
and report card configurations. These form the foundation of multi-curriculum
support, allowing schools to operate under different educational frameworks
(GES, Cambridge, Edexcel, American, IB, French, Montessori, Custom).
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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, GradingScale, Grade, Subject, Term
    from app.models.school import School
    from app.models.student import Student
    from app.models.user import User


# =========================
# Enums
# =========================


class CurriculumType(str, Enum):
    """Supported curriculum frameworks."""

    GES = "ges"                  # Ghana Education Service
    CAMBRIDGE = "cambridge"      # Cambridge International (IGCSE, A-Level)
    EDEXCEL = "edexcel"          # Pearson Edexcel (IGCSE, A-Level)
    AMERICAN = "american"        # US Common Core / AP
    IB = "ib"                    # International Baccalaureate (MYP, DP)
    FRENCH = "french"            # French Baccalaureate
    MONTESSORI = "montessori"    # Montessori (narrative-based)
    CUSTOM = "custom"            # School-defined custom curriculum


class AssessmentComponentType(str, Enum):
    """Types of assessment components across all curricula."""

    # Universal
    CONTINUOUS_ASSESSMENT = "continuous_assessment"
    EXAM = "exam"
    # GES-specific
    CLASS_WORK = "class_work"
    HOMEWORK = "homework"
    MIDTERM = "midterm"
    END_TERM = "end_term"
    # Cambridge/Edexcel
    COURSEWORK = "coursework"
    CONTROLLED_ASSESSMENT = "controlled_assessment"
    EXTERNAL_EXAM = "external_exam"
    PRACTICAL = "practical"
    ORAL = "oral"
    # IB
    INTERNAL_ASSESSMENT = "internal_assessment"
    EXTERNAL_ASSESSMENT = "external_assessment"
    EXTENDED_ESSAY = "extended_essay"
    TOK = "tok"                          # Theory of Knowledge
    CAS = "cas"                          # Creativity, Activity, Service
    # American
    QUIZ = "quiz"
    TEST = "test"
    PROJECT = "project"
    PARTICIPATION = "participation"
    FINAL = "final"
    # French
    CONTROLE_CONTINU = "controle_continu"
    EPREUVE = "epreuve"
    # Montessori
    OBSERVATION = "observation"
    NARRATIVE = "narrative"
    PORTFOLIO = "portfolio"


class ScoreDisplayMode(str, Enum):
    """How scores are displayed on reports."""

    PERCENTAGE = "percentage"              # 85%
    GRADE_ONLY = "grade_only"              # A*
    GRADE_AND_SCORE = "grade_and_score"    # A* (92%)
    LEVEL = "level"                        # Level 7 (IB)
    GPA = "gpa"                            # 3.85
    NARRATIVE = "narrative"                # Qualitative description only
    MENTION = "mention"                    # Tres Bien (French)


class AcademicCalendarType(str, Enum):
    """Academic calendar structure."""

    TERMS = "terms"            # 3 terms per year (GES, Cambridge)
    SEMESTERS = "semesters"    # 2 semesters per year (American, French)
    QUARTERS = "quarters"      # 4 quarters per year


# =========================
# CurriculumProfile
# =========================


class CurriculumProfile(Base, TenantMixin, SoftDeleteMixin):
    """
    Central curriculum configuration entity.

    Bundles a grading scale, assessment structure, and report card
    preferences for a specific curriculum framework.
    """

    __tablename__ = "curriculum_profiles"
    __table_args__ = (
        # Partial unique index -- allows re-creating a profile with the same
        # name after the original is soft-deleted (deleted_at IS NOT NULL).
        Index(
            "uq_curriculum_profile_name",
            "tenant_id", "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Profile name, e.g., 'Cambridge IGCSE', 'GES Standard'",
    )
    curriculum_type: Mapped[CurriculumType] = mapped_column(
        SQLEnum(
            CurriculumType,
            name="curriculumtype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Linked Grading Scale
    grading_scale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="SET NULL"),
        nullable=True,
        comment="Default grading scale for this curriculum",
    )

    # Calendar Configuration
    academic_calendar_type: Mapped[AcademicCalendarType] = mapped_column(
        SQLEnum(
            AcademicCalendarType,
            name="academiccalendartype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AcademicCalendarType.TERMS,
    )
    periods_per_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Number of terms/semesters per academic year",
    )

    # Display Configuration
    score_display_mode: Mapped[ScoreDisplayMode] = mapped_column(
        SQLEnum(
            ScoreDisplayMode,
            name="scoredisplaymode",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ScoreDisplayMode.GRADE_AND_SCORE,
    )
    show_position: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Show class position/ranking on reports",
    )
    show_class_average: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Feature Flags
    use_gpa: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Calculate and display GPA (American, IB)",
    )
    use_credits: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Track credit/unit accumulation (American)",
    )
    use_criterion_grading: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Use criterion-referenced grading (IB MYP)",
    )

    # Curriculum-Specific Configuration (JSONB)
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Curriculum-specific settings (see docs for schema per type)",
    )

    # Status
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Default profile for this school",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    school: Mapped["School | None"] = relationship(
        "School",
        foreign_keys=[school_id],
        lazy="raise",
    )
    grading_scale: Mapped["GradingScale | None"] = relationship(
        "GradingScale",
        foreign_keys=[grading_scale_id],
        lazy="raise",
    )
    assessment_structures: Mapped[list["AssessmentStructure"]] = relationship(
        "AssessmentStructure",
        back_populates="curriculum_profile",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    report_config: Mapped[list["ReportCardConfig"]] = relationship(
        "ReportCardConfig",
        back_populates="curriculum_profile",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<CurriculumProfile(name='{self.name}', type='{self.curriculum_type}')>"


# =========================
# AssessmentStructure
# =========================


class AssessmentStructure(Base, TenantMixin, SoftDeleteMixin):
    """
    Flexible assessment weight system for a curriculum profile.

    Replaces the rigid 4-column AssessmentWeight model with an
    N-component system. Each structure contains multiple components
    whose weights must sum to 100.
    """

    __tablename__ = "assessment_structures"
    __table_args__ = (
        # COALESCE-based unique: one structure per profile per year
        # (NULL academic_year_id = default structure for the profile)
        # Partial index excludes soft-deleted rows so a replacement can be created
        Index(
            "uq_assessment_structure",
            "tenant_id", "curriculum_profile_id",
            text("COALESCE(academic_year_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
        comment="Year-specific override; NULL = default structure",
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., 'IGCSE Assessment Structure'",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    curriculum_profile: Mapped["CurriculumProfile"] = relationship(
        "CurriculumProfile",
        back_populates="assessment_structures",
        lazy="raise",
    )
    academic_year: Mapped["AcademicYear | None"] = relationship(
        "AcademicYear",
        lazy="raise",
    )
    components: Mapped[list["AssessmentComponent"]] = relationship(
        "AssessmentComponent",
        back_populates="assessment_structure",
        cascade="all, delete-orphan",
        order_by="AssessmentComponent.sequence",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<AssessmentStructure(name='{self.name}')>"


# =========================
# AssessmentComponent
# =========================


class AssessmentComponent(Base, TenantMixin):
    """
    Individual assessment weight component within a structure.

    Each component has a type, weight (percentage), and flags
    indicating whether it maps to the legacy CA/Exam report columns.

    Uses hard delete (no SoftDeleteMixin) -- components are managed
    as part of their parent structure.
    """

    __tablename__ = "assessment_components"

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    assessment_structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_structures.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Component Definition
    component_type: Mapped[AssessmentComponentType] = mapped_column(
        SQLEnum(
            AssessmentComponentType,
            name="assessmentcomponenttype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name, e.g., 'Coursework'",
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Percentage weight (all components in structure must sum to 100)",
    )
    max_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Optional fixed max score for this component",
    )

    # Flags
    is_external: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Externally assessed (Cambridge papers, WAEC exam)",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order within structure",
    )
    maps_to_ca: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Maps to 'Class Score' column on legacy GES report cards",
    )
    maps_to_exam: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Maps to 'Exams Score' column on legacy GES report cards",
    )

    # Curriculum-Specific Config
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Component-specific config (e.g., IB criterion definitions)",
    )

    # Relationships
    assessment_structure: Mapped["AssessmentStructure"] = relationship(
        "AssessmentStructure",
        back_populates="components",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<AssessmentComponent(name='{self.name}', weight={self.weight})>"


# =========================
# ReportCardConfig
# =========================


class ReportCardConfig(Base, TenantMixin, SoftDeleteMixin):
    """
    Curriculum-specific report card display configuration.

    Controls which sections and columns appear on the report card
    for a given curriculum profile.
    """

    __tablename__ = "report_card_configs"
    __table_args__ = (
        # Partial unique index -- allows re-creating a config with the same
        # template_key after the original is soft-deleted (deleted_at IS NOT NULL).
        Index(
            "uq_report_card_config",
            "tenant_id", "curriculum_profile_id", "template_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # School (nullable for chain support)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Template
    template_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="default",
        comment="Template identifier for HTML template selection",
    )

    # Visibility Flags
    show_position: Mapped[bool] = mapped_column(Boolean, default=True)
    show_class_average: Mapped[bool] = mapped_column(Boolean, default=True)
    show_subject_position: Mapped[bool] = mapped_column(Boolean, default=True)
    show_effort_grade: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Cambridge-style effort grades (1-5 or A-E)",
    )
    show_predicted_grades: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Show predicted grades (Cambridge/IB for university apps)",
    )
    show_gpa: Mapped[bool] = mapped_column(Boolean, default=False)
    show_credits: Mapped[bool] = mapped_column(Boolean, default=False)
    show_honor_roll: Mapped[bool] = mapped_column(Boolean, default=False)
    show_learner_profile: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="IB Learner Profile traits assessment",
    )
    show_atl_skills: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="IB Approaches to Learning skills",
    )

    # Custom Content
    custom_columns: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional custom columns for the report card",
    )
    header_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Custom header text for the report",
    )
    footer_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Custom footer text for the report",
    )

    # Relationships
    curriculum_profile: Mapped["CurriculumProfile"] = relationship(
        "CurriculumProfile",
        back_populates="report_config",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ReportCardConfig(profile_id={self.curriculum_profile_id}, template='{self.template_key}')>"


# =========================
# GradeEquivalency
# =========================


class GradeEquivalency(Base, TenantMixin):
    """
    Cross-curriculum grade mapping.

    Maps a grade from one scale to an equivalent grade in another scale.
    e.g., WAEC A1 -> Cambridge A*, IB 7 -> American A+
    """

    __tablename__ = "grade_equivalencies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_grade_id", "target_grading_scale_id",
            name="uq_grade_equivalency",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_grading_scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_grading_scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_grade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    source_grading_scale: Mapped["GradingScale"] = relationship(
        "GradingScale",
        foreign_keys=[source_grading_scale_id],
        lazy="raise",
    )
    target_grading_scale: Mapped["GradingScale"] = relationship(
        "GradingScale",
        foreign_keys=[target_grading_scale_id],
        lazy="raise",
    )
    source_grade: Mapped["Grade"] = relationship(
        "Grade",
        foreign_keys=[source_grade_id],
        lazy="raise",
    )
    target_grade: Mapped["Grade"] = relationship(
        "Grade",
        foreign_keys=[target_grade_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<GradeEquivalency(source_grade_id={self.source_grade_id}, target_grade_id={self.target_grade_id})>"


# =========================
# SubjectCurriculumMapping
# =========================


class SubjectCurriculumMapping(Base, TenantMixin):
    """
    Maps an internal subject to its curriculum-specific code, name, and metadata.

    e.g., Subject "Mathematics" -> Cambridge code "0580", level "Extended",
    credits 1.0 for American system.
    """

    __tablename__ = "subject_curriculum_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "subject_id", "curriculum_profile_id",
            name="uq_subject_curriculum_mapping",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="External subject code, e.g., '0580' for IGCSE Mathematics",
    )
    external_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="Official curriculum subject name",
    )
    level: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="e.g., 'Higher', 'Standard', 'Extended', 'Core', 'AP', 'Honors'",
    )
    credits: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True,
        comment="Credit value (American system)",
    )
    coefficient: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True,
        comment="Coefficient (French system)",
    )
    is_hl: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="IB Higher Level flag",
    )
    grading_scale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="SET NULL"),
        nullable=True,
        comment="Subject-specific grading scale override",
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Subject-specific curriculum config",
    )

    # Relationships
    subject: Mapped["Subject"] = relationship(
        "Subject",
        lazy="raise",
    )
    curriculum_profile: Mapped["CurriculumProfile"] = relationship(
        "CurriculumProfile",
        lazy="raise",
    )
    grading_scale: Mapped["GradingScale | None"] = relationship(
        "GradingScale",
        foreign_keys=[grading_scale_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<SubjectCurriculumMapping(subject_id={self.subject_id}, profile_id={self.curriculum_profile_id})>"


# =========================
# ExternalExamBoard Enum
# =========================


class ExternalExamBoard(str, Enum):
    """External examination boards."""

    WAEC = "waec"
    CAMBRIDGE_INTERNATIONAL = "cambridge_international"
    EDEXCEL = "edexcel"
    COLLEGE_BOARD = "college_board"  # SAT/AP
    IBO = "ibo"                      # IB Organization
    OTHER = "other"


# =========================
# ExternalExamRegistration
# =========================


class ExternalExamRegistration(Base, TenantMixin, SoftDeleteMixin):
    """
    External examination registration and results tracking.

    Tracks student registrations for external exams (WAEC, Cambridge, IB, etc.)
    and stores imported results.
    """

    __tablename__ = "external_exam_registrations"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    exam_board: Mapped[ExternalExamBoard] = mapped_column(
        SQLEnum(
            ExternalExamBoard,
            name="externalexamboard",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    exam_session: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="e.g., 'May 2026', 'Nov 2026'",
    )
    candidate_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    center_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    registration_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending, registered, confirmed",
    )
    subjects: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        comment="Array of {subject_code, subject_name, level, paper_numbers}",
    )
    results: Mapped[list | None] = mapped_column(
        JSONB, nullable=True,
        comment="Array of {subject_code, grade, score, date_received}",
    )
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    results_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")

    def __repr__(self) -> str:
        return f"<ExternalExamRegistration(student_id={self.student_id}, board='{self.exam_board}', session='{self.exam_session}')>"


# =========================
# StudentCreditAccumulation
# =========================


class StudentCreditAccumulation(Base, TenantMixin):
    """
    Credit/unit tracking for American and IB curricula.

    Records credits attempted and earned per subject per term,
    with grade points for GPA calculation.
    Uses hard delete (no SoftDeleteMixin) — recalculated from term reports.
    """

    __tablename__ = "student_credit_accumulations"
    __table_args__ = (
        Index(
            "uq_student_credit",
            "tenant_id", "student_id", "subject_id", "academic_year_id",
            text("COALESCE(term_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    curriculum_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    credits_attempted: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), nullable=False,
    )
    credits_earned: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), nullable=False,
    )
    grade_points: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
        comment="For GPA calculation",
    )
    weighted_grade_points: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
        comment="For weighted GPA",
    )
    is_ap: Mapped[bool] = mapped_column(Boolean, default=False)
    is_honors: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    curriculum_profile: Mapped["CurriculumProfile"] = relationship("CurriculumProfile", lazy="raise")
    subject: Mapped["Subject"] = relationship("Subject", lazy="raise")

    def __repr__(self) -> str:
        return f"<StudentCreditAccumulation(student_id={self.student_id}, subject_id={self.subject_id})>"


# =========================
# PredictedGrade
# =========================


class PredictedGrade(Base, TenantMixin, SoftDeleteMixin):
    """
    Predicted and target grades for university applications.

    Used by Cambridge and IB schools to track teacher-predicted
    grades and student target grades.
    """

    __tablename__ = "predicted_grades"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    predicted_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    target_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    predicted_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    predicted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    predicted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    subject: Mapped["Subject"] = relationship("Subject", lazy="raise")
    predictor: Mapped["User | None"] = relationship("User", lazy="raise")

    def __repr__(self) -> str:
        return f"<PredictedGrade(student_id={self.student_id}, subject_id={self.subject_id}, grade='{self.predicted_grade}')>"

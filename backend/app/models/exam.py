"""
SIMS Plus - Examination Models

Models for examination management: Exams, Scores, Continuous Assessment, Term Reports.
"""

import uuid
from enum import Enum
from datetime import date, datetime, time
from decimal import Decimal
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
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Term, Class, ClassSection, Subject, GradingScale
    from app.models.student import Student
    from app.models.user import User


# =========================
# Enums
# =========================


class ExamType(str, Enum):
    """Type of examination."""

    QUIZ = "quiz"
    MIDTERM = "midterm"
    END_TERM = "end_term"
    MOCK = "mock"
    PRACTICAL = "practical"
    PROJECT = "project"


class ExamStatus(str, Enum):
    """Status of an examination."""

    DRAFT = "draft"  # Being set up
    SCHEDULED = "scheduled"  # Ready to start
    ONGOING = "ongoing"  # In progress
    COMPLETED = "completed"  # All scores entered
    RESULTS_PUBLISHED = "results_published"  # Results visible
    CANCELLED = "cancelled"  # Cancelled


class ExamSubjectStatus(str, Enum):
    """Status of exam subject scores."""

    PENDING = "pending"  # No scores entered
    SCORES_ENTERED = "scores_entered"  # Some scores entered
    SUBMITTED = "submitted"  # All scores submitted (locked)
    PUBLISHED = "published"  # Results visible


class AssessmentType(str, Enum):
    """Type of continuous assessment."""

    CLASS_WORK = "class_work"
    HOMEWORK = "homework"
    TEST = "test"
    PROJECT = "project"
    ASSIGNMENT = "assignment"


# =========================
# Exam Model
# =========================


class Exam(Base, TenantMixin, SoftDeleteMixin):
    """
    Examination model.

    Represents an exam event (e.g., "First Term Mid-Term Examination 2025").
    """

    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "academic_year_id", "term_id", "name",
            name="uq_exam_name_per_term"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships to Academic Context
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Basic Info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Exam name, e.g., Mid-Term Examination",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    exam_type: Mapped[ExamType] = mapped_column(
        SQLEnum(
            ExamType,
            name="examtype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # Dates
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Exam start date",
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Exam end date",
    )

    # Status
    status: Mapped[ExamStatus] = mapped_column(
        SQLEnum(
            ExamStatus,
            name="examstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ExamStatus.DRAFT,
        nullable=False,
    )

    # Audit
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use selectinload()/joinedload() explicitly in queries that need these.
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        lazy="raise",
    )
    term: Mapped["Term"] = relationship(
        "Term",
        lazy="raise",
    )
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="raise",
    )
    subjects: Mapped[list["ExamSubject"]] = relationship(
        "ExamSubject",
        back_populates="exam",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Exam(name='{self.name}', type='{self.exam_type}', status='{self.status}')>"


# =========================
# Exam Subject Model
# =========================


class ExamSubject(Base, TenantMixin):
    """
    Exam-Subject-Class-Section mapping.

    Links an exam to a subject for a specific class/section, with scheduling details.
    Section is optional - if not specified, applies to the whole class.
    """

    __tablename__ = "exam_subjects"
    __table_args__ = (
        # Unique constraint uses COALESCE to handle NULL section_id
        # This ensures uniqueness per exam+subject+class+section
        Index(
            "uq_exam_subject_class_section",
            "tenant_id", "exam_id", "subject_id", "class_id",
            text("COALESCE(section_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
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
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="CASCADE"),
        nullable=True,
        comment="Optional section - if NULL, applies to whole class",
    )
    grading_scale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grading_scales.id", ondelete="SET NULL"),
        nullable=True,
        comment="Grading scale for auto grade calculation",
    )

    # Scoring Configuration
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("100.00"),
        nullable=False,
        comment="Maximum possible score",
    )
    pass_mark: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("50.00"),
        nullable=False,
        comment="Minimum passing score",
    )

    # Scheduling (optional)
    exam_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    exam_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Exam duration in minutes",
    )
    venue: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Status
    status: Mapped[ExamSubjectStatus] = mapped_column(
        SQLEnum(
            ExamSubjectStatus,
            name="examsubjectstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ExamSubjectStatus.PENDING,
        nullable=False,
    )

    # Relationships
    exam: Mapped["Exam"] = relationship(
        "Exam",
        back_populates="subjects",
        lazy="raise",
    )
    subject: Mapped["Subject"] = relationship(
        "Subject",
        lazy="raise",
    )
    class_: Mapped["Class"] = relationship(
        "Class",
        lazy="raise",
    )
    section: Mapped["ClassSection"] = relationship(
        "ClassSection",
        lazy="raise",
    )
    grading_scale: Mapped["GradingScale"] = relationship(
        "GradingScale",
        lazy="raise",
    )
    scores: Mapped[list["ExamScore"]] = relationship(
        "ExamScore",
        back_populates="exam_subject",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ExamSubject(exam_id='{self.exam_id}', subject_id='{self.subject_id}', class_id='{self.class_id}', section_id='{self.section_id}')>"


# =========================
# Exam Score Model
# =========================


class ExamScore(Base, TenantMixin, SoftDeleteMixin):
    """
    Student exam score.

    Records individual student score for an exam subject.
    """

    __tablename__ = "exam_scores"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "exam_subject_id", "student_id",
            name="uq_exam_score_student"
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
    exam_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exam_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Score Data
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Raw score obtained",
    )
    is_absent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Student was absent for exam",
    )

    # Calculated Grade (auto-filled)
    grade: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="Calculated grade (A1, B2, etc.)",
    )
    grade_point: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Grade point for GPA calculation",
    )
    grade_remark: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Grade remark (Excellent, Good, etc.)",
    )
    effort_grade: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        comment="Effort grade (Cambridge: 1-5 or A-E)",
    )

    # Teacher Remark (for report card)
    teacher_remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Per-subject teacher remark for report card",
    )

    # Audit
    entered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    entered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    exam_subject: Mapped["ExamSubject"] = relationship(
        "ExamSubject",
        back_populates="scores",
        lazy="raise",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        lazy="raise",
    )
    entered_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[entered_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ExamScore(student_id='{self.student_id}', score={self.score}, grade='{self.grade}')>"


# =========================
# Score Change Log Model (Audit Trail)
# =========================


class ScoreChangeLog(Base, TenantMixin):
    """
    Audit trail for exam score changes.

    Records all changes to exam scores for accountability and dispute resolution.
    """

    __tablename__ = "score_change_logs"

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Reference to the score
    exam_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exam_scores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # What changed
    old_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Previous score value",
    )
    new_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="New score value",
    )
    old_is_absent: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Previous absent status",
    )
    new_is_absent: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="New absent status",
    )

    # Change metadata
    change_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type of change: created, updated, deleted",
    )
    change_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional reason for the change",
    )

    # Who made the change
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # IP address for security tracking
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of the user making the change",
    )

    # Relationships
    exam_score: Mapped["ExamScore"] = relationship(
        "ExamScore",
        foreign_keys=[exam_score_id],
        lazy="raise",
    )
    changed_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[changed_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ScoreChangeLog(score_id='{self.exam_score_id}', type='{self.change_type}', at='{self.changed_at}')>"


# =========================
# Continuous Assessment Model
# =========================


class ContinuousAssessment(Base, TenantMixin, SoftDeleteMixin):
    """
    Continuous Assessment entry.

    Records individual assessments (class work, homework, tests) throughout the term.
    """

    __tablename__ = "continuous_assessments"

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Academic Context
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
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
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Assessment Info
    assessment_type: Mapped[AssessmentType] = mapped_column(
        SQLEnum(
            AssessmentType,
            name="assessmenttype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Assessment title, e.g., Week 3 Class Test",
    )
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("10.00"),
        nullable=False,
    )
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    assessment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Audit
    entered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    term: Mapped["Term"] = relationship("Term", lazy="raise")
    class_: Mapped["Class"] = relationship("Class", lazy="raise")
    subject: Mapped["Subject"] = relationship("Subject", lazy="raise")
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    entered_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[entered_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ContinuousAssessment(type='{self.assessment_type}', title='{self.title}', score={self.score})>"


# =========================
# Term Report Model (Report Card Data)
# =========================


class TermReport(Base, TenantMixin, SoftDeleteMixin):
    """
    Term Report (Report Card Data).

    Aggregated student performance data for a term, used for report card generation.
    """

    __tablename__ = "term_reports"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "term_id", "student_id",
            name="uq_term_report_student"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Academic Context
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Aggregate Scores
    total_score: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 2),
        nullable=True,
        comment="Sum of weighted subject scores",
    )
    average_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Average score across subjects",
    )
    subjects_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of subjects taken",
    )

    # Rankings
    class_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Position in class (all sections)",
    )
    section_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Position in section",
    )
    class_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total students in class",
    )
    section_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total students in section",
    )

    # Attendance Summary
    attendance_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    days_present: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    days_absent: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    total_school_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Conduct & Remarks
    conduct_grade: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Conduct grade (e.g., Excellent, Very Good, Good, Satisfactory, Needs Improvement)",
    )
    interest: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Student interests/activities",
    )
    class_teacher_remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Class teacher's general remark",
    )
    headmaster_remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Headmaster's remark",
    )

    # Curriculum-specific fields (Phase 2)
    curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
        nullable=True,
        comment="Curriculum profile used to generate this report",
    )
    gpa: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True, comment="Term GPA (American, IB)",
    )
    weighted_gpa: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True, comment="Weighted GPA",
    )
    cumulative_gpa: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True, comment="Cumulative GPA across terms",
    )
    total_credits_earned: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 1), nullable=True, comment="Credits earned this term",
    )
    cumulative_credits: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 1), nullable=True, comment="Total credits to date",
    )
    honor_roll: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="Honor roll status",
    )
    ib_total_points: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="IB total points (out of 45)",
    )
    french_mention: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="French mention category",
    )
    extra_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Curriculum-specific report data",
    )

    # Publishing
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Is report visible to parents?",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    term: Mapped["Term"] = relationship("Term", lazy="raise")
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    class_: Mapped["Class"] = relationship("Class", lazy="raise")
    section: Mapped["ClassSection"] = relationship("ClassSection", lazy="raise")

    def __repr__(self) -> str:
        return f"<TermReport(student_id='{self.student_id}', term_id='{self.term_id}', position={self.class_position})>"

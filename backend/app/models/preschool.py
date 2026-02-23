"""
SIMS Plus - Preschool Models

Models for preschool-specific functionality:
- Learning Areas (replaces subjects)
- Developmental Skills/Milestones
- Rating Scales
- Skill Assessments
- Progress Observations
- Daily Activity Logs
- Preschool Reports
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, Term
    from app.models.student import Student
    from app.models.user import User


# =========================
# Enums
# =========================


class ObservationType(str, Enum):
    """Type of progress observation."""

    ANECDOTE = "anecdote"
    MILESTONE = "milestone"
    PHOTO = "photo"
    VIDEO = "video"
    INCIDENT = "incident"


class MoodType(str, Enum):
    """Mood options for daily logs."""

    HAPPY = "happy"
    EXCITED = "excited"
    CALM = "calm"
    TIRED = "tired"
    UPSET = "upset"
    SICK = "sick"


class MealAmount(str, Enum):
    """How much of a meal was consumed."""

    NONE = "none"
    LITTLE = "little"
    SOME = "some"
    MOST = "most"
    ALL = "all"


class NapQuality(str, Enum):
    """Quality of nap/rest."""

    GOOD = "good"
    RESTLESS = "restless"
    DIDNT_SLEEP = "didnt_sleep"


# =========================
# Learning Area
# =========================


class LearningArea(Base, TenantMixin, SoftDeleteMixin):
    """
    Developmental/Learning areas for preschool assessment.

    Examples:
    - Social-Emotional Development
    - Language & Literacy
    - Mathematical Thinking / Numeracy
    - Scientific Exploration
    - Physical Development - Gross Motor
    - Physical Development - Fine Motor
    - Creative Arts & Expression
    - Personal Hygiene & Self-Care
    """

    __tablename__ = "learning_areas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_learning_area_code"),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Learning area name, e.g., Social-Emotional Development",
    )
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Short code, e.g., SED",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the learning area",
    )
    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon identifier for UI",
    )
    color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        comment="Hex color for visual representation, e.g., #22c55e",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Order for display in UI",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Relationships
    skills: Mapped[list["DevelopmentalSkill"]] = relationship(
        "DevelopmentalSkill",
        back_populates="learning_area",
        cascade="all, delete-orphan",
        order_by="DevelopmentalSkill.display_order",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<LearningArea(name='{self.name}', code='{self.code}')>"


# =========================
# Developmental Skill
# =========================


class DevelopmentalSkill(Base, TenantMixin, SoftDeleteMixin):
    """
    Specific skills/milestones within a learning area.

    Example: Under "Language & Literacy" -> "Recognizes own name in print"
    """

    __tablename__ = "developmental_skills"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "learning_area_id", "name", name="uq_skill_name"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    learning_area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_areas.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Skill name, e.g., Recognizes own name in print",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description or criteria",
    )
    age_range_months_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum age in months (e.g., 36 for 3 years)",
    )
    age_range_months_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum age in months (e.g., 48 for 4 years)",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Order within learning area",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # Which class levels this skill applies to (e.g., ["nursery_1", "nursery_2"])
    applicable_levels: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of class levels this skill applies to",
    )

    # Relationships
    learning_area: Mapped["LearningArea"] = relationship(
        "LearningArea",
        back_populates="skills",
        lazy="raise",
    )
    assessments: Mapped[list["StudentSkillAssessment"]] = relationship(
        "StudentSkillAssessment",
        back_populates="skill",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<DevelopmentalSkill(name='{self.name}')>"


# =========================
# Preschool Rating Scale
# =========================


class PreschoolRatingScale(Base, TenantMixin, SoftDeleteMixin):
    """
    Rating scales for preschool assessments.

    Example: 4-point scale (Emerging, Developing, Proficient, Advanced)
    """

    __tablename__ = "preschool_rating_scales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_rating_scale_name"),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Scale name, e.g., 4-Point Developmental Scale",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Is this the default scale for this tenant?",
    )

    # Relationships
    ratings: Mapped[list["PreschoolRating"]] = relationship(
        "PreschoolRating",
        back_populates="scale",
        cascade="all, delete-orphan",
        order_by="PreschoolRating.numeric_value",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PreschoolRatingScale(name='{self.name}')>"


# =========================
# Preschool Rating
# =========================


class PreschoolRating(Base, TenantMixin, SoftDeleteMixin):
    """
    Individual ratings within a scale.

    Tenant-scoped and soft-deletable for proper multi-tenant isolation.

    Example ratings:
    - Not Yet Observed (NYO, 0)
    - Emerging (E, 1)
    - Developing (D, 2)
    - Proficient (P, 3)
    - Advanced (A, 4)
    """

    __tablename__ = "preschool_ratings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scale_id", "short_code", name="uq_rating_code"),
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("preschool_rating_scales.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Rating name, e.g., Proficient",
    )
    short_code: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Short code, e.g., P or 3",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description, e.g., Child consistently demonstrates this skill",
    )
    numeric_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Numeric value for calculations/sorting",
    )
    color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        comment="Hex color, e.g., #22c55e (green)",
    )
    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon identifier or emoji",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # Relationships
    scale: Mapped["PreschoolRatingScale"] = relationship(
        "PreschoolRatingScale",
        back_populates="ratings",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PreschoolRating(name='{self.name}', code='{self.short_code}')>"


# =========================
# Student Skill Assessment
# =========================


class StudentSkillAssessment(Base, TenantMixin):
    """
    Records a student's progress on a specific developmental skill.
    """

    __tablename__ = "student_skill_assessments"
    __table_args__ = (
        # One assessment per student per skill per term
        UniqueConstraint(
            "tenant_id", "student_id", "skill_id", "term_id",
            name="uq_student_skill_term"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
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
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("developmental_skills.id", ondelete="CASCADE"),
        nullable=False,
    )
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
    rating_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("preschool_ratings.id", ondelete="SET NULL"),
        nullable=True,
    )

    observation_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Teacher's observation notes",
    )
    evidence_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to photo/video evidence (optional)",
    )

    assessed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    skill: Mapped["DevelopmentalSkill"] = relationship(
        "DevelopmentalSkill",
        back_populates="assessments",
        lazy="raise",
    )
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        foreign_keys=[academic_year_id],
        lazy="raise",
    )
    term: Mapped["Term"] = relationship(
        "Term",
        foreign_keys=[term_id],
        lazy="raise",
    )
    rating: Mapped["PreschoolRating | None"] = relationship(
        "PreschoolRating",
        foreign_keys=[rating_id],
        lazy="raise",
    )
    assessed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assessed_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<StudentSkillAssessment(student_id='{self.student_id}', skill_id='{self.skill_id}')>"


# =========================
# Progress Observation
# =========================


class ProgressObservation(Base, TenantMixin, SoftDeleteMixin):
    """
    General observations about a student's progress.

    Can be daily anecdotes, photos, milestone achievements, or incidents.
    """

    __tablename__ = "progress_observations"

    # School (nullable for chain support; backfilled for existing data)
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
    learning_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_areas.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional: link to a specific learning area",
    )

    observation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ObservationType.ANECDOTE.value,
        comment="Type: anecdote, milestone, photo, video, incident",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    observation_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Media attachments as JSONB: [{url, type, thumbnail}]
    attachments: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Visibility controls
    share_with_parents: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Should this be visible to parents?",
    )
    is_highlight: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Featured on student profile?",
    )

    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    learning_area: Mapped["LearningArea | None"] = relationship(
        "LearningArea",
        foreign_keys=[learning_area_id],
        lazy="raise",
    )
    recorded_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[recorded_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ProgressObservation(title='{self.title}', type='{self.observation_type}')>"


# =========================
# Daily Activity Log
# =========================


class DailyActivityLog(Base, TenantMixin, SoftDeleteMixin):
    """
    Daily log for preschool - tracks meals, naps, mood, activities.

    This is a highly requested feature by preschool parents.
    """

    __tablename__ = "daily_activity_logs"
    __table_args__ = (
        # One log per student per day
        UniqueConstraint(
            "tenant_id", "student_id", "log_date",
            name="uq_student_daily_log"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
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
    log_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Arrival/Departure
    arrival_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    arrival_mood: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="happy, tired, upset, excited, calm, sick",
    )
    departure_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    departure_mood: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Meals as JSONB for flexibility
    # Example: [
    #   {"type": "breakfast", "time": "08:30", "amount": "all", "notes": "Enjoyed porridge"},
    #   {"type": "snack", "time": "10:30", "amount": "some"},
    #   {"type": "lunch", "time": "12:30", "amount": "most", "notes": "Didn't eat vegetables"}
    # ]
    meals: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Nap/Rest
    nap_start: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    nap_end: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    nap_quality: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="good, restless, didnt_sleep",
    )

    # Bathroom tracking (for younger children)
    diaper_changes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    potty_successes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    accidents: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Activities participated in as JSONB
    # Example: ["outdoor_play", "art", "music", "story_time"]
    activities: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # General notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    highlights: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Special moments to share with parents",
    )

    logged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    logged_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[logged_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<DailyActivityLog(student_id='{self.student_id}', date='{self.log_date}')>"


# =========================
# Preschool Report
# =========================


class PreschoolReport(Base, TenantMixin, SoftDeleteMixin):
    """
    Term report for preschool students.

    Different structure from traditional report cards - focuses on
    developmental progress narratives rather than scores and rankings.
    """

    __tablename__ = "preschool_reports"
    __table_args__ = (
        # One report per student per term
        UniqueConstraint(
            "tenant_id", "student_id", "term_id",
            name="uq_preschool_report"
        ),
    )

    # School (nullable for chain support; backfilled for existing data)
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

    # Attendance summary
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

    # Overall assessment by learning area (computed from skill assessments)
    # Example: {
    #   "social_emotional": {"rating": "proficient", "summary": "..."},
    #   "language_literacy": {"rating": "developing", "summary": "..."},
    # }
    learning_area_summaries: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Narrative sections
    overall_progress: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="General progress narrative",
    )
    strengths: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What the child excels at",
    )
    areas_for_growth: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Areas needing development",
    )
    teacher_recommendations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Suggestions for parents",
    )

    # Special achievements/highlights as JSONB
    # Example: ["Learned to tie shoes", "Made first friend"]
    highlights: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Goals for next term as JSONB
    next_term_goals: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Teacher remarks
    class_teacher_remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    head_teacher_remark: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        foreign_keys=[academic_year_id],
        lazy="raise",
    )
    term: Mapped["Term"] = relationship(
        "Term",
        foreign_keys=[term_id],
        lazy="raise",
    )
    class_: Mapped["Class"] = relationship(
        "Class",
        foreign_keys=[class_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PreschoolReport(student_id='{self.student_id}', term_id='{self.term_id}')>"

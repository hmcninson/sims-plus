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
    from app.models.student import Guardian, Student
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


class PreschoolSessionType(str, Enum):
    """Enrollment session types for preschool students."""

    HALF_DAY_MORNING = "half_day_morning"
    HALF_DAY_AFTERNOON = "half_day_afternoon"
    FULL_DAY = "full_day"
    EXTENDED = "extended"


class PreschoolIncidentType(str, Enum):
    """Types of preschool incidents/accidents."""

    ACCIDENT = "accident"              # Physical injury (fall, bump, scrape)
    ILLNESS = "illness"                # Fell sick at school
    BEHAVIORAL = "behavioral"          # Behavioral issue
    ALLERGIC_REACTION = "allergic_reaction"  # Allergy-related
    OTHER = "other"


class PreschoolIncidentSeverity(str, Enum):
    """Severity levels for preschool incidents."""

    MINOR = "minor"        # Scraped knee, small bump — no parent call needed
    MODERATE = "moderate"  # Needs first aid, parent should be notified
    SERIOUS = "serious"    # Medical attention required, parent MUST be notified


class PreschoolIncidentStatus(str, Enum):
    """Workflow status for preschool incidents."""

    REPORTED = "reported"
    REVIEWED = "reviewed"
    PARENT_NOTIFIED = "parent_notified"
    RESOLVED = "resolved"


# ---------------------------------------------------------------
# Incident Status Machine — Valid Transitions
# ---------------------------------------------------------------

VALID_INCIDENT_TRANSITIONS: dict[PreschoolIncidentStatus, list[PreschoolIncidentStatus]] = {
    PreschoolIncidentStatus.REPORTED: [
        PreschoolIncidentStatus.REVIEWED,
        PreschoolIncidentStatus.PARENT_NOTIFIED,  # Skip review for urgent cases
    ],
    PreschoolIncidentStatus.REVIEWED: [
        PreschoolIncidentStatus.PARENT_NOTIFIED,
        PreschoolIncidentStatus.RESOLVED,          # Only minor incidents can skip parent notification
    ],
    PreschoolIncidentStatus.PARENT_NOTIFIED: [
        PreschoolIncidentStatus.RESOLVED,
    ],
    PreschoolIncidentStatus.RESOLVED: [],  # Terminal
}

# CHILD SAFETY: Severity-based resolution rules (enforced in service layer)
# - "minor": Can be resolved from REVIEWED without parent notification
# - "moderate"/"serious": MUST go through PARENT_NOTIFIED before RESOLVED
# The service layer's resolve_incident() enforces this gate.


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
        # One report per student per term per report type
        UniqueConstraint(
            "tenant_id", "student_id", "term_id", "report_type",
            name="uq_preschool_report_v2",
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

    # Phase 2 additions
    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="term",
        server_default="term",
        comment="Report type: term, interim, progress_update",
    )
    photo_urls: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Student photos for report: [{url, caption}]",
    )
    chart_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Pre-computed chart data for PDF: {labels: [...], values: [...]}",
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


# =========================
# Preschool Incident
# =========================


class PreschoolIncident(Base, TenantMixin, SoftDeleteMixin):
    """
    Preschool incident/accident report.

    Tracks incidents from initial report through review, parent notification,
    and resolution. "Serious" severity auto-triggers parent notification.

    Workflow: reported -> reviewed -> parent_notified -> resolved
    """

    __tablename__ = "preschool_incidents"

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
    incident_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="accident, illness, behavioral, allergic_reaction, other",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="minor, moderate, serious",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PreschoolIncidentStatus.REPORTED.value,
        comment="reported, reviewed, parent_notified, resolved",
    )
    incident_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    incident_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Where the incident occurred (e.g., playground, classroom)",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of what happened",
    )
    action_taken: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What was done immediately after the incident",
    )
    first_aid_given: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether first aid was administered",
    )
    medical_attention_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether professional medical attention is needed",
    )
    parent_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    parent_notified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    witnesses: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='List of witness names, e.g., ["Ms. Adjei", "Mr. Mensah"]',
    )
    attachments: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Photos: [{url, type, thumbnail, filename}]',
    )
    follow_up_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Follow-up observations after initial incident",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    reported_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reported_by],
        lazy="raise",
    )
    parent_notified_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[parent_notified_by],
        lazy="raise",
    )
    resolved_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[resolved_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PreschoolIncident(student_id='{self.student_id}', type='{self.incident_type}', severity='{self.severity}')>"


# =========================
# Authorized Pickup
# =========================


class AuthorizedPickup(Base, TenantMixin, SoftDeleteMixin):
    """
    Non-guardian persons authorized to pick up a student.

    Guardians with can_pickup=True on StudentGuardian are implicitly authorized.
    This table tracks ADDITIONAL authorized persons (nannies, family friends, etc.)
    who are not registered guardians.
    """

    __tablename__ = "authorized_pickups"
    # NOTE: Unique constraint is a PARTIAL index (WHERE deleted_at IS NULL)
    # created in the migration, NOT via UniqueConstraint, to allow
    # re-adding soft-deleted phone numbers.

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
    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Contact phone number",
    )
    relationship_to_student: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g., uncle, family friend, nanny, driver",
    )
    photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 presigned URL for photo identification",
    )
    id_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 presigned URL for ID document scan",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Can be deactivated without deletion for audit trail",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Any special notes (e.g., only on Fridays)",
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
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
    added_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[added_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<AuthorizedPickup(name='{self.full_name}', student_id='{self.student_id}')>"


# =========================
# Pickup Log
# =========================


class PickupLog(Base, TenantMixin):
    """
    Record of each pickup event.

    Tracks who picked up which student, when, and who (teacher/admin) verified it.
    Does NOT use SoftDeleteMixin -- pickup records are immutable audit entries.
    """

    __tablename__ = "pickup_logs"

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
    pickup_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    pickup_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    picked_up_by_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'guardian' or 'authorized_person'",
    )
    picked_up_by_guardian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardians.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when picked_up_by_type = 'guardian'",
    )
    picked_up_by_authorized_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authorized_pickups.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when picked_up_by_type = 'authorized_person'",
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Teacher/admin who verified the pickup",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    guardian: Mapped["Guardian | None"] = relationship(
        "Guardian",
        foreign_keys=[picked_up_by_guardian_id],
        lazy="raise",
    )
    authorized_pickup: Mapped["AuthorizedPickup | None"] = relationship(
        "AuthorizedPickup",
        foreign_keys=[picked_up_by_authorized_id],
        lazy="raise",
    )
    verified_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[verified_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PickupLog(student_id='{self.student_id}', date='{self.pickup_date}')>"


# =========================
# Learning Story (Phase 2)
# =========================


class LearningStory(Base, TenantMixin, SoftDeleteMixin):
    """
    Portfolio entry / learning story (Reggio Emilia approach).

    A curated narrative that links multiple observations, spans multiple
    learning areas, and includes rich media. Think of it as a teacher's
    crafted story about a child's learning journey on a particular topic.

    Different from ProgressObservation: observations are point-in-time notes,
    learning stories are curated narratives that aggregate observations.
    """

    __tablename__ = "learning_stories"

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
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
        comment="Term this story relates to (optional)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Story title, e.g., 'Building a Castle Together'",
    )
    narrative: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The teacher's narrative describing the learning experience",
    )
    learning_area_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UUIDs of related learning areas",
    )
    skill_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UUIDs of related developmental skills demonstrated",
    )
    observation_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="UUIDs of linked progress observations",
    )
    attachments: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Photos/videos: [{url, type, thumbnail, filename, caption}]",
    )
    is_shared_with_parents: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Visible to parents in parent portal",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
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
    term: Mapped["Term | None"] = relationship(
        "Term",
        foreign_keys=[term_id],
        lazy="raise",
    )
    created_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<LearningStory(title='{self.title}', student_id='{self.student_id}')>"


# =========================
# Extended Care Session (Phase 2)
# =========================


class ExtendedCareSession(Base, TenantMixin):
    """
    Tracks before-school or after-school extended care sessions.

    Used for billing calculation: total hours x configured hourly rate.
    Does NOT use SoftDeleteMixin -- sessions are immutable billing records.
    """

    __tablename__ = "extended_care_sessions"

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
    session_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    session_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'before_care' or 'after_care'",
    )
    check_in_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    check_out_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="NULL until student is checked out",
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculated on check-out: (check_out - check_in) in minutes",
    )
    checked_in_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    checked_out_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ExtendedCareSession(student_id='{self.student_id}', date='{self.session_date}')>"


# =========================
# Class Caregiver Ratio (Phase 2)
# =========================


class ClassCaregiverRatio(Base, TenantMixin):
    """
    Configurable caregiver-to-child ratio per class per academic year.

    Used for compliance tracking -- Ghana ECCD standards require specific ratios
    (e.g., 1:10 for Nursery, 1:15 for KG).
    """

    __tablename__ = "class_caregiver_ratios"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "academic_year_id",
            name="uq_class_caregiver_ratio",
        ),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    max_children_per_caregiver: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum children per caregiver (e.g., 10)",
    )
    current_caregiver_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of caregivers/teachers assigned",
    )

    # Relationships
    class_: Mapped["Class"] = relationship(
        "Class",
        foreign_keys=[class_id],
        lazy="raise",
    )
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear",
        foreign_keys=[academic_year_id],
        lazy="raise",
    )

    @property
    def max_capacity(self) -> int:
        """Maximum student capacity based on ratio."""
        return self.max_children_per_caregiver * self.current_caregiver_count

    @property
    def is_compliant(self) -> bool:
        """Check if current enrollment is within ratio limits."""
        # This is computed at query time, not stored
        return True  # Actual check done in service layer

    def __repr__(self) -> str:
        return f"<ClassCaregiverRatio(class_id='{self.class_id}', ratio=1:{self.max_children_per_caregiver})>"


# =========================
# Preschool Supply (Phase 3)
# =========================


class PreschoolSupply(Base, TenantMixin, SoftDeleteMixin):
    """
    Per-student supply inventory item.

    Tracks parent-provided supplies (diapers, wipes, change of clothes).
    Teachers decrement on use; low-stock alerts notify parents.
    """

    __tablename__ = "preschool_supplies"

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
    item_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Supply item name (e.g., Diapers, Wipes, Spare Clothes)",
    )
    quantity_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Alert parent when quantity falls to this level",
    )
    last_restocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="e.g., brand preference, size information",
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_remaining <= self.low_stock_threshold

    def __repr__(self) -> str:
        return f"<PreschoolSupply(item='{self.item_name}', qty={self.quantity_remaining})>"

"""
SIMS Plus - Teacher Portal Models

Models for the teacher portal: report comments and lesson plans.
ReportComment stores per-student term-end comments from class teacher and head teacher.
LessonPlan tracks teacher lesson planning with topic, objectives, and status.
"""

import uuid
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, Subject, Term
    from app.models.staff import Staff
    from app.models.student import Student


# =========================
# Enums
# =========================


class LessonPlanStatus(str, Enum):
    """Status of a lesson plan."""

    PLANNED = "planned"
    TAUGHT = "taught"
    CANCELLED = "cancelled"


# =========================
# Report Comment Model
# =========================


class ReportComment(Base, TenantMixin, SoftDeleteMixin):
    """
    Report comment model.

    Stores class teacher and head teacher comments for a student's term report card.
    Each student gets one record per term. Both class teacher and head teacher can
    write their respective comments and sign off independently.
    """

    __tablename__ = "report_comments"
    # NOTE: Partial unique index (WHERE deleted_at IS NULL) is managed by migration
    # (uq_report_comment_student_term). Not declared here to avoid Alembic autogenerate
    # drift between the non-partial ORM constraint and the partial migration index.
    __table_args__ = (
        {"extend_existing": True},
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
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Comments
    class_teacher_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    head_teacher_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Who wrote each comment (for audit trail)
    class_teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member who wrote the class teacher comment",
    )
    head_teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member who wrote the head teacher comment",
    )

    # Sign-off flags
    class_teacher_signed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    head_teacher_signed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    term: Mapped["Term"] = relationship("Term", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    class_teacher: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        foreign_keys=[class_teacher_id],
        lazy="raise",
    )
    head_teacher: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        foreign_keys=[head_teacher_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<ReportComment(student_id={self.student_id}, term_id={self.term_id})>"


# =========================
# Lesson Plan Model
# =========================


class LessonPlan(Base, TenantMixin, SoftDeleteMixin):
    """
    Lesson plan model.

    Teachers create lesson plans for their classes specifying topic,
    objectives, resources, and activities. Plans are tied to a specific
    class, subject, and date, and can be marked as taught or cancelled.
    """

    __tablename__ = "lesson_plans"
    # NOTE: Partial unique index (WHERE deleted_at IS NULL) is managed by migration
    # (uq_lesson_plan_teacher_class_subject_date_period). Not declared here to avoid
    # Alembic autogenerate drift between the non-partial ORM constraint and the
    # partial migration index.
    __table_args__ = (
        {"extend_existing": True},
    )

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
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
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    period: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Period number within the day",
    )
    topic: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    objectives: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    resources: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    activities: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[LessonPlanStatus] = mapped_column(
        SQLEnum(
            LessonPlanStatus,
            name="lessonplanstatus",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=LessonPlanStatus.PLANNED,
    )

    # Relationships
    teacher: Mapped["Staff"] = relationship("Staff", lazy="raise")
    class_: Mapped["Class"] = relationship("Class", lazy="raise")
    subject: Mapped["Subject"] = relationship("Subject", lazy="raise")

    def __repr__(self) -> str:
        return f"<LessonPlan(teacher_id={self.teacher_id}, class_id={self.class_id}, date={self.date}, topic='{self.topic}')>"

"""
SIMS Plus - Entrance Exam Models

EntranceExam: Exam session definitions.
EntranceExamRegistration: Applicant-to-exam assignments.
EntranceExamResult: Exam scores per applicant.
"""

import uuid
from datetime import date, time
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
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import EntranceExamStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.admissions.application import Application
    from app.models.admissions.period import AdmissionPeriod
    from app.models.school import School
    from app.models.tenant import User


class EntranceExam(Base, TenantMixin, SoftDeleteMixin):
    """
    Entrance Exam model.

    Represents an exam session with date, venue, and capacity.
    """

    __tablename__ = "entrance_exams"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    admission_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admission_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., 'Entrance Exam -- Batch 1'",
    )
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    venue: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum number of candidates",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EntranceExamStatus.SCHEDULED.value,
        server_default="scheduled",
        comment="scheduled, in_progress, completed, cancelled",
    )
    instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Instructions sent to candidates",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    admission_period: Mapped["AdmissionPeriod"] = relationship(
        back_populates="entrance_exams",
        lazy="raise",
    )
    registrations: Mapped[list["EntranceExamRegistration"]] = relationship(
        back_populates="entrance_exam",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    results: Mapped[list["EntranceExamResult"]] = relationship(
        back_populates="entrance_exam",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class EntranceExamRegistration(Base, TenantMixin, SoftDeleteMixin):
    """
    Entrance Exam Registration model.

    Links an applicant to an exam session with optional seat assignment.
    """

    __tablename__ = "entrance_exam_registrations"

    entrance_exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entrance_exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    seat_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    attended: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Relationships
    entrance_exam: Mapped["EntranceExam"] = relationship(
        back_populates="registrations",
        lazy="raise",
    )
    application: Mapped["Application"] = relationship(
        back_populates="exam_registrations",
        lazy="raise",
    )


class EntranceExamResult(Base, TenantMixin, SoftDeleteMixin):
    """
    Entrance Exam Result model.

    Stores scores for each applicant per exam session.
    """

    __tablename__ = "entrance_exam_results"

    entrance_exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entrance_exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )
    grade: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Optional letter grade",
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    subject_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        comment="Per-subject scoring. NULL = aggregate score only",
    )
    weight: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2),
        nullable=True,
        default=Decimal("1.0"),
        server_default="1.0",
        comment="Subject weight for composite score calculation",
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    entrance_exam: Mapped["EntranceExam"] = relationship(
        back_populates="results",
        lazy="raise",
    )
    application: Mapped["Application"] = relationship(
        back_populates="exam_results",
        lazy="raise",
    )
    scored_by_user: Mapped["User | None"] = relationship(lazy="raise")

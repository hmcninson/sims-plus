"""
SIMS Plus - Class Promotion Models

ClassPromotion: Batch promotion operation record (end-of-year).
ClassPromotionEntry: Per-student promotion decision.
PromotionRule: Configurable criteria for auto-populating promotion batch entries.

This is the primary tool for Ghanaian academic year transitions.
Students are automatically promoted to the next class unless marked
for repeat, graduation, or withdrawal.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import PromotionAction, PromotionBatchStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, ClassSection
    from app.models.school import School
    from app.models.student import Student
    from app.models.tenant import User


class ClassPromotion(Base, TenantMixin, SoftDeleteMixin):
    """
    Class Promotion batch model.

    Represents a single end-of-year promotion operation.
    Admin creates a batch, previews entries (each student gets a default
    action), adjusts as needed, then executes the batch.
    """

    __tablename__ = "class_promotions"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        comment="Current (ending) academic year",
    )
    target_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        comment="Next (incoming) academic year",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., '2025/2026 -> 2026/2027 Promotion'",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PromotionBatchStatus.DRAFT.value,
        server_default="draft",
        comment="draft, preview, in_progress, completed, failed",
    )
    total_students: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    promoted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    repeated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    graduated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    withdrawn_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    executed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who executed the promotion",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    source_academic_year: Mapped["AcademicYear"] = relationship(
        foreign_keys=[source_academic_year_id], lazy="raise",
    )
    target_academic_year: Mapped["AcademicYear"] = relationship(
        foreign_keys=[target_academic_year_id], lazy="raise",
    )
    executed_by_user: Mapped["User | None"] = relationship(lazy="raise")
    entries: Mapped[list["ClassPromotionEntry"]] = relationship(
        back_populates="promotion",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class ClassPromotionEntry(Base, TenantMixin, SoftDeleteMixin):
    """
    Per-student promotion decision within a batch.

    Default action is 'promote'. Admin can override to repeat, graduate,
    or withdraw individual students before executing the batch.
    """

    __tablename__ = "class_promotion_entries"

    promotion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_promotions.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Student's current class",
    )
    source_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
        comment="Student's current section",
    )
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Next class (null for graduated/withdrawn)",
    )
    target_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
        comment="Assigned section in new class",
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PromotionAction.PROMOTE.value,
        server_default="promote",
        comment="promote, repeat, graduate, withdraw",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Reason for repeat/withdraw",
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Whether this entry has been executed",
    )

    # Relationships
    promotion: Mapped["ClassPromotion"] = relationship(
        back_populates="entries", lazy="raise",
    )
    student: Mapped["Student"] = relationship(lazy="raise")
    source_class: Mapped["Class"] = relationship(
        foreign_keys=[source_class_id], lazy="raise",
    )
    source_section: Mapped["ClassSection | None"] = relationship(
        foreign_keys=[source_section_id], lazy="raise",
    )
    target_class: Mapped["Class | None"] = relationship(
        foreign_keys=[target_class_id], lazy="raise",
    )
    target_section: Mapped["ClassSection | None"] = relationship(
        foreign_keys=[target_section_id], lazy="raise",
    )


class PromotionRule(Base, TenantMixin, SoftDeleteMixin):
    """
    Configurable criteria for auto-populating promotion batch entries.

    A rule defines minimum thresholds (average score, attendance, core subject
    passes) that a student must meet to be auto-promoted.  When class_id is
    NULL the rule is the school-wide default; a non-NULL class_id targets a
    specific class and takes precedence.
    """

    __tablename__ = "promotion_rules"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL = school-wide default rule",
    )
    min_average: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    min_attendance_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    core_subject_pass_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )
    pass_mark: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, default=Decimal("50.00"),
    )
    auto_apply: Mapped[bool] = mapped_column(
        Boolean, default=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    class_: Mapped[Optional["Class"]] = relationship("Class", lazy="raise")

"""
SIMS Plus - Academic Class Models

Models for classes, class sections, and class-subject associations.
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.curriculum import CurriculumProfile
    from app.models.staff import Staff, StaffClassAssignment
    from app.models.student import Student

    from .subject_models import Subject


# =========================
# Enums
# =========================


class ClassLevel(str, Enum):
    """Class level/grade."""

    # Category levels (simplified)
    PRESCHOOL = "preschool"
    PRIMARY = "primary"
    JHS = "jhs"
    SHS = "shs"

    # Specific grade levels (for backward compatibility)
    CRECHE = "creche"
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

    # Curriculum (overrides school default for dual-track)
    curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
        nullable=True,
        comment="Class-level curriculum override (for dual-track schools)",
    )

    # Relationships
    curriculum_profile: Mapped["CurriculumProfile | None"] = relationship(
        "CurriculumProfile",
        lazy="raise",
    )
    sections: Mapped[list["ClassSection"]] = relationship(
        "ClassSection",
        back_populates="class_",
        cascade="all, delete-orphan",
        order_by="ClassSection.name",
        primaryjoin="and_(Class.id == foreign(ClassSection.class_id), ClassSection.deleted_at.is_(None))",
        lazy="raise",
    )
    subjects: Mapped[list["ClassSubject"]] = relationship(
        "ClassSubject",
        back_populates="class_",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="class_",
        lazy="raise",
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

    # School (nullable for chain support; backfilled for existing data)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        lazy="raise",
    )
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="section",
        lazy="raise",
    )
    staff_assignments: Mapped[list["StaffClassAssignment"]] = relationship(
        "StaffClassAssignment",
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @property
    def full_name(self) -> str:
        """Get full section name (e.g., JHS 1A)."""
        return f"{self.class_.name} {self.name}"

    def __repr__(self) -> str:
        return f"<ClassSection(name='{self.name}')>"


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

    # School (nullable for chain support; backfilled for existing data)
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

    # Assigned teacher for this class-subject combination
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Assigned teacher for this class-subject combination",
    )

    # Relationships
    class_: Mapped["Class"] = relationship(
        "Class",
        back_populates="subjects",
        lazy="raise",
    )
    subject: Mapped["Subject"] = relationship(
        "Subject",
        back_populates="class_subjects",
        lazy="raise",
    )
    teacher: Mapped["Staff | None"] = relationship(
        "Staff",
        lazy="raise",
    )

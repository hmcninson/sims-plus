"""
SIMS Plus - Academic Year and Term Models

Models for academic year and term/semester management.
"""

import uuid
from datetime import date
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin


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
    # lazy="raise" prevents accidental lazy loading in async context.
    terms: Mapped[list["Term"]] = relationship(
        "Term",
        back_populates="academic_year",
        cascade="all, delete-orphan",
        order_by="Term.start_date",
        lazy="raise",
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
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Term(name='{self.name}', status='{self.status}')>"

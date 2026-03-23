"""
SIMS Plus - School Model

School entity within a tenant.
"""

import uuid
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.curriculum import CurriculumProfile
    from app.models.student import Student
    from app.models.staff import Staff


class SchoolType(str, Enum):
    """Type of school."""

    PRESCHOOL = "preschool"  # Preschool only
    PRIMARY = "primary"  # Primary School
    PRESCHOOL_PRIMARY = "preschool_primary"  # Preschool + Primary
    JHS = "jhs"  # Junior High School
    SHS = "shs"  # Senior High School
    BASIC = "basic"  # Primary + JHS combined
    BASIC_PRESCHOOL = "basic_preschool"  # Preschool to JHS
    BASIC_SHS = "basic_shs"  # Preschool to SHS (full K-12)
    INTERNATIONAL = "international"
    TECHNICAL = "technical"


class SchoolStatus(str, Enum):
    """School status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class SchoolCategory(str, Enum):
    """Ownership/governance type of the school."""

    PUBLIC = "public"
    PRIVATE = "private"
    INTERNATIONAL = "international"
    FAITH_BASED = "faith_based"


class BoardingType(str, Enum):
    """Residential accommodation type."""

    DAY_ONLY = "day_only"
    BOARDING_ONLY = "boarding_only"
    MIXED = "mixed"  # Both day and boarding students


class CalendarType(str, Enum):
    """Academic calendar structure for the school."""

    TERM = "term"          # 3 terms per year (GES standard)
    SEMESTER = "semester"  # 2 semesters per year
    QUARTER = "quarter"    # 4 quarters per year


class School(Base, TenantMixin, SoftDeleteMixin):
    """
    School model - represents an individual school within a tenant.

    A tenant can have one school (single_school type) or multiple
    schools (school_chain type).
    """

    __tablename__ = "schools"

    # Basic Information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Official school name",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="URL-friendly identifier",
    )
    code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="School code (e.g., GES code)",
    )
    school_type: Mapped[SchoolType] = mapped_column(
        SQLEnum(
            SchoolType,
            name="schooltype",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=SchoolType.BASIC,
        nullable=False,
    )
    status: Mapped[SchoolStatus] = mapped_column(
        SQLEnum(
            SchoolStatus,
            name="schoolstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=SchoolStatus.ACTIVE,
        nullable=False,
    )

    # Contact Information
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Address
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Ghana region",
    )
    gps_address: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Ghana GPS address",
    )

    # Branding (overrides tenant branding)
    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="School logo URL",
    )
    primary_color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        comment="Primary brand color (hex)",
    )
    motto: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="School motto",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="School description/about",
    )
    year_established: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Year the school was established",
    )

    # Academic Settings
    uses_boarding: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Has boarding facilities",
    )
    # School classification
    category: Mapped[SchoolCategory | None] = mapped_column(
        SQLEnum(
            SchoolCategory,
            name="schoolcategory",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
        comment="Ownership: public, private, international, faith_based",
    )
    boarding_type: Mapped[BoardingType | None] = mapped_column(
        SQLEnum(
            BoardingType,
            name="boardingtype",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
        comment="Residential: day_only, boarding_only, mixed",
    )

    uses_transport: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Provides transport services",
    )
    student_id_prefix: Mapped[str] = mapped_column(
        String(10),
        default="STU",
        nullable=False,
        comment="Prefix for auto-generated student IDs (e.g., STU, ADM)",
    )
    staff_id_prefix: Mapped[str] = mapped_column(
        String(10),
        default="STF",
        nullable=False,
        comment="Prefix for auto-generated staff IDs (e.g., STF, EMP)",
    )

    # Preschool Settings
    preschool_settings: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Preschool configuration settings (enabled, tracking options, etc.)",
    )

    # Communication Settings (SMS, email, notification preferences)
    communication_settings: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Communication settings (SMS, email, notification preferences)",
    )

    # Curriculum
    curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_profiles.id", ondelete="SET NULL"),
        nullable=True,
        comment="School's default curriculum profile",
    )
    curriculum_settings: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="School-level curriculum overrides",
    )

    # Active flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # GES Registration
    ges_registration_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Ghana Education Service registration number",
    )

    # Setup Wizard Tracking
    setup_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="Whether the school has completed the setup wizard",
    )
    setup_wizard_step: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="Last completed wizard step (0 = not started)",
    )

    # Calendar Configuration
    calendar_type: Mapped[CalendarType] = mapped_column(
        SQLEnum(
            CalendarType,
            name="calendartype",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=CalendarType.TERM,
        server_default="term",
        nullable=False,
        comment="Academic calendar type: term, semester, or quarter",
    )

    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use joinedload() or selectinload() explicitly in queries that need these.
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="school",
        lazy="raise",
    )
    staff_members: Mapped[list["Staff"]] = relationship(
        "Staff",
        back_populates="school",
        lazy="raise",
    )
    curriculum_profile: Mapped["CurriculumProfile | None"] = relationship(
        "CurriculumProfile",
        foreign_keys=[curriculum_profile_id],
        lazy="raise",
    )

    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.address, self.city, self.region]
        return ", ".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<School(name='{self.name}', type='{self.school_type}')>"

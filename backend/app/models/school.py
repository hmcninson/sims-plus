"""
SIMS Plus - School Model

School entity within a tenant.
"""

import uuid
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin


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

    # Academic Settings
    uses_boarding: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Has boarding facilities",
    )
    uses_transport: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Provides transport services",
    )

    # Active flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships (will be added)
    # users = relationship("User", back_populates="school")
    # students = relationship("Student", back_populates="school")
    # classes = relationship("Class", back_populates="school")

    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.address, self.city, self.region]
        return ", ".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<School(name='{self.name}', type='{self.school_type}')>"

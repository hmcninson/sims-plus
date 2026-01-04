"""
SIMS Plus - Tenant Model

Multi-tenant root entity representing a school or school chain.
"""

import uuid
from datetime import date
from enum import Enum

from sqlalchemy import Boolean, Date, Enum as SQLEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin


class TenantType(str, Enum):
    """Type of tenant."""

    SINGLE_SCHOOL = "single_school"
    SCHOOL_CHAIN = "school_chain"


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""

    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Tenant(Base, SoftDeleteMixin):
    """
    Tenant model - represents a school or school chain.

    This is the root entity for multi-tenancy.
    All school data is isolated by tenant_id.
    """

    __tablename__ = "tenants"

    # Basic Information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organization/School chain name",
    )
    subdomain: Mapped[str] = mapped_column(
        String(63),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique subdomain for tenant (e.g., presec, achimota)",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-friendly identifier",
    )
    tenant_type: Mapped[TenantType] = mapped_column(
        SQLEnum(TenantType),
        default=TenantType.SINGLE_SCHOOL,
        nullable=False,
    )

    # Subscription
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier),
        default=SubscriptionTier.TRIAL,
        nullable=False,
    )
    subscription_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscription_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_students: Mapped[int] = mapped_column(default=100, comment="Max students allowed")

    # Contact
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON settings for tenant customization",
    )

    # Branding
    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to tenant logo",
    )
    primary_color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        default="#1B4F72",
        comment="Primary brand color (hex)",
    )

    # Relationships (will be added)
    # schools = relationship("School", back_populates="tenant")
    # users = relationship("User", back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant(name='{self.name}', slug='{self.slug}')>"

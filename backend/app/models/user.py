"""
SIMS Plus - User Model

System users with authentication and authorization.
"""

import uuid
from datetime import datetime
from enum import Enum

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.staff import Staff


class UserRole(str, Enum):
    """User roles for RBAC."""

    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    PARENT = "parent"
    STUDENT = "student"
    APPLICANT = "applicant"


class UserStatus(str, Enum):
    """User account status."""

    PENDING = "pending"  # Email not verified
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class User(Base, TenantMixin, SoftDeleteMixin):
    """
    User model - all system users.

    Supports authentication and role-based access control.
    """

    __tablename__ = "users"

    __table_args__ = (
        sa.Index(
            "uq_users_tenant_email",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )

    # Basic Information
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Role & Status
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name="userrole",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserRole.TEACHER,
        nullable=False,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(
            UserStatus,
            name="userstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserStatus.PENDING,
        nullable=False,
    )

    # School association (for school-level users)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id"),
        nullable=True,
        index=True,
    )

    # Email verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Login tracking
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Profile
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Accra")

    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use joinedload() explicitly in queries that need the staff profile.
    staff_profile: Mapped["Staff | None"] = relationship(
        "Staff",
        back_populates="user",
        uselist=False,
        lazy="raise",
    )

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        """Check if user is active."""
        return self.status == UserStatus.ACTIVE

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role in [
            UserRole.PLATFORM_ADMIN,
            UserRole.CHAIN_ADMIN,
            UserRole.SCHOOL_ADMIN,
        ]

    def __repr__(self) -> str:
        return f"<User(email='{self.email}', role='{self.role}')>"

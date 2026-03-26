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
    from app.models.custom_role import CustomRole
    from app.models.staff import Staff


class UserRole(str, Enum):
    """User roles for RBAC."""

    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    HR_OFFICER = "hr_officer"
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    TRANSPORT_OFFICER = "transport_officer"
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

    # Phone verification
    phone_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # MFA
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_backup_codes_hash: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # JSON-encoded list of Argon2id-hashed backup codes.
    # Each code is 8 characters, alphanumeric (XXXX-XXXX format).
    # Codes are burned (removed from list) on use.

    mfa_setup_pending_secret: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Temporary encrypted TOTP secret during setup flow. Uses Text (not
    # String(255)) because the Fernet-encrypted payload including backup
    # code hashes can exceed 255 chars. Cleared after verification.

    # Login tracking
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Session timeout: updated by heartbeat endpoint, checked on token refresh
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Custom role override — if set, permissions come from this custom role
    # instead of the static ROLE_PERMISSIONS lookup for user.role
    custom_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="If set, user's permissions come from this custom role instead of ROLE_PERMISSIONS",
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
    custom_role: Mapped["CustomRole | None"] = relationship(
        "CustomRole",
        back_populates="users",
        foreign_keys="[User.custom_role_id]",
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

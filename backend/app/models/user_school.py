"""
SIMS Plus - UserSchool Junction Model

Maps users to schools within a chain tenant, supporting multi-school access.
Single-school tenants get one user_schools row per user (auto-created during
migration backfill and onboarding).

SECURITY:
- RLS enabled: tenant_id = get_current_tenant_id()
- Defense-in-depth: all service queries explicitly filter by tenant_id.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from typing import TYPE_CHECKING

from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User


class UserSchool(Base, TenantMixin):
    """
    User-School junction table for multi-school access.

    Each row grants a user access to a specific school with a role.
    Chain admins may have rows for every school; a teacher typically has one.
    """

    __tablename__ = "user_schools"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", "school_id",
            name="uq_user_school_tenant",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Role at this specific school (may differ from user.role for chain admins)
    role_at_school: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="User's role at this specific school (e.g., school_admin, teacher)",
    )

    # Whether this is the user's primary (default) school
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Primary school shown on login; only one per user per tenant",
    )

    # Soft-disable without deleting the association
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the user currently has access to this school",
    )

    # Relationships -- lazy="raise" to prevent N+1 queries in async context
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="raise",
    )
    school: Mapped["School"] = relationship(
        "School",
        foreign_keys=[school_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<UserSchool(user_id='{self.user_id}', "
            f"school_id='{self.school_id}', "
            f"role='{self.role_at_school}')>"
        )

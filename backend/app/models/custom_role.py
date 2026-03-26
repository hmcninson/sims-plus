"""
SIMS Plus - Custom Role Model

Tenant-scoped custom roles with configurable permissions.
Extends the existing RBAC system — a custom role always has a `base_role`
(one of the predefined UserRole values) that acts as its permission ceiling.
"""

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin
from app.models.user import UserRole


class CustomRole(Base, TenantMixin, SoftDeleteMixin):
    """
    Tenant-scoped custom role with configurable permissions.

    Permissions are stored as a JSONB array of permission strings
    (same format as ROLE_PERMISSIONS in auth.py).

    Each custom role has a base_role that defines its permission ceiling —
    the custom role's permissions must be a subset of the base_role's
    permissions. This is enforced at the service layer during creation
    and updates.
    """

    __tablename__ = "custom_roles"

    # NOTE: Partial unique index (WHERE deleted_at IS NULL) is created in the
    # migration, not via __table_args__. This allows soft-deleted role slugs
    # to be reused.

    # id, created_at, updated_at inherited from Base — do not redefine

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name (e.g., 'Head of Department')",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="URL-safe identifier (e.g., 'head-of-department')",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the role's purpose",
    )

    # Permission ceiling — custom role's permissions must be a subset of this role's
    base_role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name="userrole",
            create_type=False,  # Reuse existing enum type, do not CREATE
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        comment="Parent role — defines the permission ceiling",
    )

    # Stored as a JSONB array of permission strings (e.g., ["students.read", "attendance.mark"])
    permissions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Array of permission strings",
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="If True, cannot be modified or deleted (reserved for system-created roles)",
    )

    # Who created this role — SET NULL if the admin is deleted
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships — lazy="raise" prevents accidental lazy loading in async context
    users: Mapped[list] = relationship(
        "User",
        back_populates="custom_role",
        foreign_keys="[User.custom_role_id]",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<CustomRole(name='{self.name}', base_role='{self.base_role}')>"

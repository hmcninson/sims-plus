"""
Platform audit log model.

Records all platform admin actions: login, tenant CRUD, impersonation.
This table has NO tenant_id and NO RLS — it is a global audit table.
Access is controlled at the API layer via PlatformAdminUser dependency.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class PlatformAuditLog(Base):
    """
    Immutable audit trail for platform admin operations.

    NOT tenant-scoped (no TenantMixin). This is intentional —
    platform operations span multiple tenants.
    """

    __tablename__ = "platform_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
        comment="Platform admin user who performed the action",
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Action type: login, tenant_create, tenant_suspend, impersonate, etc.",
    )
    target_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="Tenant affected by the action (NULL for non-tenant actions like login)",
    )
    target_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Entity type affected: tenant, user, school (NULL for login/analytics)",
    )
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="Entity ID affected (NULL for login/analytics)",
    )
    details: Mapped[dict | None] = mapped_column(
        JSONB(), nullable=True,
        comment="Additional context (e.g., changes made, reason for suspension)",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
        comment="Client IP address (IPv4 or IPv6)",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text(), nullable=True,
        comment="Client user-agent string",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    # Suppress Base.updated_at — audit log entries are immutable
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

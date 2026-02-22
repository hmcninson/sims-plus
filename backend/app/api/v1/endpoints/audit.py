"""
SIMS Plus - Audit Log Endpoints

API endpoints for viewing the security audit trail.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.models.audit_log import AuditLog

import structlog

logger = structlog.get_logger()

router = APIRouter()


# =========================
# Response Schemas
# =========================
# Defined locally because audit logs are a simple read-only endpoint
# that doesn't warrant a full separate schema file.


class AuditLogResponse(BaseModel):
    """Single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[str] = None
    created_at: str


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =========================
# Endpoints
# =========================


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List audit logs",
    dependencies=[Depends(require_permissions("audit.read"))],
)
async def list_audit_logs(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    action: Optional[str] = Query(None, description="Filter by action type (e.g. auth.login.success)"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    date_from: Optional[date] = Query(None, description="Start date (inclusive)"),
    date_to: Optional[date] = Query(None, description="End date (inclusive)"),
) -> AuditLogListResponse:
    """
    List audit log entries for the current tenant.

    Requires `audit.read` permission. Only school/platform admins typically
    have this. Results are ordered by most recent first.

    The audit_logs table does not use RLS, so we filter by tenant_id
    explicitly to ensure tenant isolation.
    """
    # Defense-in-depth: filter by tenant_id since audit_logs has no RLS
    query = select(AuditLog).where(AuditLog.tenant_id == tenant.tenant_id)
    count_query = select(func.count()).select_from(AuditLog).where(
        AuditLog.tenant_id == tenant.tenant_id
    )

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)

    if date_from:
        query = query.where(func.date(AuditLog.created_at) >= date_from)
        count_query = count_query.where(func.date(AuditLog.created_at) >= date_from)

    if date_to:
        query = query.where(func.date(AuditLog.created_at) <= date_to)
        count_query = count_query.where(func.date(AuditLog.created_at) <= date_to)

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Paginate, ordered by newest first
    offset = (page - 1) * page_size
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    logs = list(result.scalars().all())

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                tenant_id=log.tenant_id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                details=log.details,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

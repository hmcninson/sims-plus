"""
SIMS Plus - Payroll Audit Service

Append-only audit trail for all payroll mutations. The payroll_audit_log
table is INSERT-only for sims_app_user (no UPDATE/DELETE allowed at DB level).
"""

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import PayrollAuditLog

logger = structlog.get_logger()


class PayrollAuditService:
    """Service for payroll audit logging and retrieval."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def log_event(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        performed_by: UUID,
        school_id: Optional[UUID] = None,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PayrollAuditLog:
        """
        Insert a payroll audit log entry.

        This is append-only: the DB GRANT prevents UPDATE/DELETE on this table
        for sims_app_user, ensuring the audit trail cannot be tampered with.
        """
        entry = PayrollAuditLog(
            tenant_id=tenant_id,
            school_id=school_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            audit_metadata=metadata,
            performed_by=performed_by,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        logger.info(
            "payroll_audit_logged",
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            performed_by=str(performed_by),
            tenant_id=str(tenant_id),
        )
        return entry

    async def list_audit_log(
        self,
        tenant_id: UUID,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PayrollAuditLog]:
        """Query payroll audit log with optional filters."""
        query = (
            select(PayrollAuditLog)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollAuditLog.tenant_id == tenant_id)
            .order_by(PayrollAuditLog.performed_at.desc())
        )

        if entity_type:
            query = query.where(PayrollAuditLog.entity_type == entity_type)
        if entity_id:
            query = query.where(PayrollAuditLog.entity_id == entity_id)
        if date_from:
            query = query.where(
                PayrollAuditLog.performed_at >= datetime.combine(
                    date_from, datetime.min.time(), tzinfo=timezone.utc
                )
            )
        if date_to:
            query = query.where(
                PayrollAuditLog.performed_at <= datetime.combine(
                    date_to, datetime.max.time(), tzinfo=timezone.utc
                )
            )

        query = query.limit(min(limit, 200)).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

"""
SIMS Plus - Finance Audit Service

Business logic for logging financial audit trail entries.
"""

from datetime import datetime, UTC, date
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.finance import FinanceAuditLog, FinanceAuditAction


class FinanceAuditService:
    """
    Service for logging financial audit trail entries.

    This service records all changes to financial entities (invoices, payments,
    scholarships, etc.) for compliance and auditing purposes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        performed_by: UUID,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FinanceAuditLog:
        """
        Log an audit trail entry for a financial action.

        Args:
            tenant_id: The tenant ID
            entity_type: Type of entity (invoice, payment, scholarship, etc.)
            entity_id: ID of the entity being audited
            action: Action type (create, update, delete, void, issue, cancel, award, revoke)
            performed_by: User ID who performed the action
            field_name: Field that was changed (for updates)
            old_value: Previous value (JSON string for complex values)
            new_value: New value (JSON string for complex values)
            reason: Reason for the change
            metadata: Additional metadata about the change
            ip_address: IP address of the user
            user_agent: Browser/client user agent
        """
        audit_log = FinanceAuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            metadata_json=metadata,
            performed_by=performed_by,
            performed_at=datetime.now(UTC),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(audit_log)
        await self.db.flush()  # Don't commit - let the caller manage the transaction
        return audit_log

    async def log_create(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        performed_by: UUID,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log entity creation."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=FinanceAuditAction.CREATE.value,
            performed_by=performed_by,
            metadata=metadata,
            ip_address=ip_address,
        )

    async def log_update(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        performed_by: UUID,
        field_name: str,
        old_value: str,
        new_value: str,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log entity field update."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=FinanceAuditAction.UPDATE.value,
            performed_by=performed_by,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )

    async def log_void(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        performed_by: UUID,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log entity void action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=FinanceAuditAction.VOID.value,
            performed_by=performed_by,
            reason=reason,
            ip_address=ip_address,
        )

    async def log_scholarship_award(
        self,
        tenant_id: UUID,
        student_scholarship_id: UUID,
        performed_by: UUID,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log scholarship award."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type="student_scholarship",
            entity_id=student_scholarship_id,
            action=FinanceAuditAction.AWARD.value,
            performed_by=performed_by,
            metadata=metadata,
            ip_address=ip_address,
        )

    async def log_scholarship_revoke(
        self,
        tenant_id: UUID,
        student_scholarship_id: UUID,
        performed_by: UUID,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log scholarship revocation."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type="student_scholarship",
            entity_id=student_scholarship_id,
            action=FinanceAuditAction.REVOKE.value,
            performed_by=performed_by,
            reason=reason,
            ip_address=ip_address,
        )

    async def get_entity_audit_log(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[FinanceAuditLog], int]:
        """Get audit log entries for a specific entity."""
        query = select(FinanceAuditLog).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                FinanceAuditLog.tenant_id == tenant_id,
                FinanceAuditLog.entity_type == entity_type,
                FinanceAuditLog.entity_id == entity_id,
            )
        )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(FinanceAuditLog.performed_by_user),
        ).order_by(desc(FinanceAuditLog.performed_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def get_tenant_audit_log(
        self,
        tenant_id: UUID,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        performed_by: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[FinanceAuditLog], int]:
        """Get audit log entries for a tenant with optional filters."""
        query = select(FinanceAuditLog).where(
            FinanceAuditLog.tenant_id == tenant_id
        )

        if entity_type:
            query = query.where(FinanceAuditLog.entity_type == entity_type)
        if action:
            query = query.where(FinanceAuditLog.action == action)
        if performed_by:
            query = query.where(FinanceAuditLog.performed_by == performed_by)
        if start_date:
            query = query.where(func.date(FinanceAuditLog.performed_at) >= start_date)
        if end_date:
            query = query.where(func.date(FinanceAuditLog.performed_at) <= end_date)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(FinanceAuditLog.performed_by_user),
        ).order_by(desc(FinanceAuditLog.performed_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

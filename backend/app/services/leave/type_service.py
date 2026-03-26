"""
SIMS Plus - Leave Type Service

CRUD operations for leave types (annual, sick, maternity, etc.).
"""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave import LeaveType

logger = structlog.get_logger()


class LeaveTypeService:
    """Service for managing leave types."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def create(
        self,
        tenant_id: UUID,
        data: dict,
        school_id: Optional[UUID] = None,
    ) -> LeaveType:
        """Create a new leave type. Code must be unique per tenant."""
        # Check unique code within tenant (soft-delete aware)
        existing = await self.db.execute(
            select(LeaveType).where(
                LeaveType.tenant_id == tenant_id,
                LeaveType.code == data["code"].upper(),
                LeaveType.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise self.Error(
                f"Leave type with code '{data['code']}' already exists",
                409,
            )

        leave_type = LeaveType(
            tenant_id=tenant_id,
            school_id=school_id,
            name=data["name"],
            code=data["code"].upper(),
            description=data.get("description"),
            default_days_per_year=data["default_days_per_year"],
            max_carryover_days=data.get("max_carryover_days", 0),
            is_paid=data.get("is_paid", True),
            requires_approval=data.get("requires_approval", True),
            color=data.get("color"),
        )
        self.db.add(leave_type)
        await self.db.flush()
        await self.db.refresh(leave_type)

        logger.info(
            "leave_type_created",
            leave_type_id=str(leave_type.id),
            code=leave_type.code,
            tenant_id=str(tenant_id),
        )
        return leave_type

    async def list(
        self,
        tenant_id: UUID,
        active_only: bool = True,
    ) -> list[LeaveType]:
        """List leave types for a tenant."""
        query = select(LeaveType).where(
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            LeaveType.tenant_id == tenant_id,
            LeaveType.deleted_at.is_(None),
        ).order_by(LeaveType.name)

        if active_only:
            query = query.where(LeaveType.is_active.is_(True))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, tenant_id: UUID, type_id: UUID) -> LeaveType:
        """Get a single leave type by ID."""
        result = await self.db.execute(
            select(LeaveType).where(
                LeaveType.id == type_id,
                LeaveType.tenant_id == tenant_id,
                LeaveType.deleted_at.is_(None),
            )
        )
        leave_type = result.scalar_one_or_none()
        if not leave_type:
            raise self.Error("Leave type not found", 404)
        return leave_type

    async def update(
        self,
        tenant_id: UUID,
        type_id: UUID,
        data: dict,
    ) -> LeaveType:
        """Update a leave type."""
        leave_type = await self.get(tenant_id, type_id)

        for key, value in data.items():
            if value is not None and hasattr(leave_type, key):
                setattr(leave_type, key, value)

        await self.db.flush()
        await self.db.refresh(leave_type)

        logger.info(
            "leave_type_updated",
            leave_type_id=str(type_id),
            tenant_id=str(tenant_id),
        )
        return leave_type

    async def delete(self, tenant_id: UUID, type_id: UUID) -> None:
        """Soft delete a leave type."""
        from datetime import datetime, UTC

        leave_type = await self.get(tenant_id, type_id)

        # Prevent deletion if active balances reference this type
        from app.models.leave import LeaveBalance
        from sqlalchemy import func

        balance_count_result = await self.db.execute(
            select(func.count(LeaveBalance.id)).where(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.leave_type_id == type_id,
            )
        )
        balance_count = balance_count_result.scalar() or 0
        if balance_count > 0:
            raise self.Error(
                "Cannot delete leave type with existing balances. "
                "Deactivate it instead.",
                409,
            )

        leave_type.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "leave_type_deleted",
            leave_type_id=str(type_id),
            tenant_id=str(tenant_id),
        )

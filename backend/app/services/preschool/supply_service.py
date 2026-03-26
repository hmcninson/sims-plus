"""
SIMS Plus - Preschool Supply Service

Business logic for per-student supply inventory tracking:
adding, listing, using (decrementing), restocking, and metadata updates.
Low-stock notifications dispatched to parents when quantity drops to/below threshold.
"""

import structlog
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preschool import PreschoolSupply
from app.models.student import Student
from app.schemas.preschool.supply import (
    PreschoolSupplyCreate,
    PreschoolSupplyUpdate,
)
from app.services.preschool._shared import PreschoolServiceError

logger = structlog.get_logger(__name__)


class PreschoolSupplyService:
    """Service for managing per-student supply inventory."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_supply(
        self,
        tenant_id: UUID,
        student_id: UUID,
        data: PreschoolSupplyCreate,
        school_id: UUID | None = None,
    ) -> PreschoolSupply:
        """Add a supply item for a student.

        Validates that the student belongs to the tenant before creating.
        """
        # Defense-in-depth: verify student belongs to tenant
        await self._validate_student(tenant_id, student_id)

        supply = PreschoolSupply(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_id,
            item_name=data.item_name,
            quantity_remaining=data.quantity_remaining,
            low_stock_threshold=data.low_stock_threshold,
            notes=data.notes,
        )
        self.db.add(supply)
        await self.db.flush()
        await self.db.refresh(supply)
        return supply

    async def list_supplies(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> Sequence[PreschoolSupply]:
        """List all active (non-deleted) supply items for a student."""
        result = await self.db.execute(
            select(PreschoolSupply).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    PreschoolSupply.tenant_id == tenant_id,
                    PreschoolSupply.student_id == student_id,
                    PreschoolSupply.deleted_at.is_(None),
                )
            ).order_by(PreschoolSupply.item_name)
        )
        return result.scalars().all()

    async def update_supply(
        self,
        tenant_id: UUID,
        supply_id: UUID,
        data: PreschoolSupplyUpdate,
    ) -> PreschoolSupply:
        """Update supply metadata (name, threshold, notes)."""
        supply = await self._get_supply(tenant_id, supply_id)

        if data.item_name is not None:
            supply.item_name = data.item_name
        if data.low_stock_threshold is not None:
            supply.low_stock_threshold = data.low_stock_threshold
        if data.notes is not None:
            supply.notes = data.notes

        await self.db.flush()
        await self.db.refresh(supply)
        return supply

    async def use_supply(
        self,
        tenant_id: UUID,
        supply_id: UUID,
        quantity: int = 1,
    ) -> PreschoolSupply:
        """Decrement supply quantity.

        Raises error if quantity_remaining would go below 0.
        If quantity drops to/below low_stock_threshold, attempts to
        notify parents via NotificationDispatcher (best-effort).
        """
        supply = await self._get_supply(tenant_id, supply_id)

        new_qty = supply.quantity_remaining - quantity
        if new_qty < 0:
            raise PreschoolServiceError(
                f"Insufficient stock: {supply.quantity_remaining} remaining, "
                f"cannot use {quantity}",
                code="insufficient_stock",
            )

        # Track whether we crossed the low-stock threshold with this use
        was_above_threshold = supply.quantity_remaining > supply.low_stock_threshold
        supply.quantity_remaining = new_qty

        await self.db.flush()
        await self.db.refresh(supply)

        # Trigger low-stock notification if we just crossed the threshold
        if was_above_threshold and supply.is_low_stock:
            await self._notify_low_stock(supply)

        return supply

    async def restock_supply(
        self,
        tenant_id: UUID,
        supply_id: UUID,
        quantity: int,
    ) -> PreschoolSupply:
        """Increment supply quantity and record restock timestamp."""
        supply = await self._get_supply(tenant_id, supply_id)

        supply.quantity_remaining += quantity
        supply.last_restocked_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(supply)
        return supply

    # =========================
    # Private Helpers
    # =========================

    async def _get_supply(self, tenant_id: UUID, supply_id: UUID) -> PreschoolSupply:
        """Fetch a supply item, verifying tenant ownership and soft-delete status."""
        result = await self.db.execute(
            select(PreschoolSupply).where(
                and_(
                    PreschoolSupply.id == supply_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    PreschoolSupply.tenant_id == tenant_id,
                    PreschoolSupply.deleted_at.is_(None),
                )
            )
        )
        supply = result.scalar_one_or_none()
        if not supply:
            raise PreschoolServiceError("Supply item not found", code="not_found")
        return supply

    async def _validate_student(self, tenant_id: UUID, student_id: UUID) -> Student:
        """Validate student exists and belongs to tenant."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", code="not_found")
        return student

    async def _notify_low_stock(self, supply: PreschoolSupply) -> None:
        """Best-effort low-stock notification to parents.

        Uses NotificationDispatcher if available. Failures are logged
        but never propagated — supply operations must not fail due to
        notification errors.
        """
        try:
            # Lazy import to avoid circular dependency
            from app.services.notification_dispatcher import NotificationDispatcher

            dispatcher = NotificationDispatcher(self.db)
            message = (
                f"Low supply alert: {supply.item_name} for your child "
                f"is running low ({supply.quantity_remaining} remaining). "
                f"Please send more to school."
            )
            await dispatcher.notify_student_guardians(
                tenant_id=supply.tenant_id,
                student_id=supply.student_id,
                title="Low Supply Alert",
                message=message,
                channels=["in_app", "sms"],
            )
        except Exception:
            # Best-effort: log and continue — supply ops must not fail on notification errors
            logger.warning(
                "Failed to send low-stock notification",
                supply_id=str(supply.id),
                item_name=supply.item_name,
                exc_info=True,
            )

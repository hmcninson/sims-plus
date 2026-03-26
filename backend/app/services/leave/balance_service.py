"""
SIMS Plus - Leave Balance Service

Manages leave balances: initialization, adjustment, and querying.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear
from app.models.leave import LeaveBalance, LeaveType
from app.models.staff import Staff, StaffStatus

logger = structlog.get_logger()


class LeaveBalanceService:
    """Service for managing leave balances."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def get_staff_balances(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> list[dict]:
        """
        Fetch all balances for a staff member, optionally filtered by year.
        Returns dicts with computed remaining_days.
        """
        query = (
            select(LeaveBalance)
            .options(selectinload(LeaveBalance.leave_type))
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.staff_id == staff_id,
            )
        )
        if academic_year_id:
            query = query.where(LeaveBalance.academic_year_id == academic_year_id)

        result = await self.db.execute(query)
        balances = result.scalars().all()

        # Load staff name once
        staff_result = await self.db.execute(
            select(Staff.first_name, Staff.last_name).where(
                Staff.id == staff_id,
                Staff.tenant_id == tenant_id,
            )
        )
        staff_row = staff_result.one_or_none()
        staff_name = f"{staff_row[0]} {staff_row[1]}" if staff_row else None

        return [
            self._balance_to_dict(b, staff_name=staff_name)
            for b in balances
        ]

    async def get_all_balances(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        leave_type_id: Optional[UUID] = None,
    ) -> list[dict]:
        """All staff balances for a year, with staff and leave type names."""
        query = (
            select(LeaveBalance)
            .options(
                selectinload(LeaveBalance.leave_type),
                selectinload(LeaveBalance.staff),
            )
            .where(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.academic_year_id == academic_year_id,
            )
        )
        if leave_type_id:
            query = query.where(LeaveBalance.leave_type_id == leave_type_id)

        result = await self.db.execute(query)
        balances = result.scalars().all()

        return [
            self._balance_to_dict(
                b,
                staff_name=f"{b.staff.first_name} {b.staff.last_name}" if b.staff else None,
            )
            for b in balances
        ]

    async def adjust(
        self,
        tenant_id: UUID,
        balance_id: UUID,
        data: dict,
    ) -> dict:
        """
        Admin override of entitled_days or carried_over.
        Requires a reason for audit trail.
        """
        result = await self.db.execute(
            select(LeaveBalance)
            .options(
                selectinload(LeaveBalance.leave_type),
                selectinload(LeaveBalance.staff),
            )
            .where(
                LeaveBalance.id == balance_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                LeaveBalance.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        balance = result.scalar_one_or_none()
        if not balance:
            raise self.Error("Leave balance not found", 404)

        old_entitled = balance.entitled_days
        old_carried = balance.carried_over

        if data.get("entitled_days") is not None:
            balance.entitled_days = data["entitled_days"]
        if data.get("carried_over") is not None:
            balance.carried_over = data["carried_over"]

        await self.db.flush()
        await self.db.refresh(balance)

        logger.info(
            "leave_balance_adjusted",
            balance_id=str(balance_id),
            tenant_id=str(tenant_id),
            staff_id=str(balance.staff_id),
            old_entitled=str(old_entitled),
            new_entitled=str(balance.entitled_days),
            old_carried=str(old_carried),
            new_carried=str(balance.carried_over),
            reason=data.get("reason", ""),
        )

        staff_name = (
            f"{balance.staff.first_name} {balance.staff.last_name}"
            if balance.staff
            else None
        )
        return self._balance_to_dict(balance, staff_name=staff_name)

    async def initialize_for_year(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        carry_over: bool = False,
    ) -> dict:
        """
        Bulk initialize balances for all active staff for a new academic year.
        If carry_over=True, calculate remaining from previous year
        (capped by max_carryover_days).

        Returns: {"created": int, "message": str}
        """
        # Validate academic year exists for this tenant
        year_result = await self.db.execute(
            select(AcademicYear).where(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        year = year_result.scalar_one_or_none()
        if not year:
            raise self.Error("Academic year not found", 404)

        # Fetch all active staff
        staff_result = await self.db.execute(
            select(Staff.id).where(
                Staff.tenant_id == tenant_id,
                Staff.status.in_([StaffStatus.ACTIVE, StaffStatus.ON_LEAVE]),
                Staff.deleted_at.is_(None),
            )
        )
        staff_ids = [row[0] for row in staff_result.all()]
        if not staff_ids:
            return {"created": 0, "message": "No active staff found"}

        # Fetch all active leave types
        types_result = await self.db.execute(
            select(LeaveType).where(
                LeaveType.tenant_id == tenant_id,
                LeaveType.is_active.is_(True),
                LeaveType.deleted_at.is_(None),
            )
        )
        leave_types = list(types_result.scalars().all())
        if not leave_types:
            return {"created": 0, "message": "No active leave types found"}

        # Find previous year for carryover calculation
        previous_year_balances: dict[tuple[UUID, UUID], LeaveBalance] = {}
        if carry_over:
            # Get the most recent academic year before this one
            prev_year_result = await self.db.execute(
                select(AcademicYear.id)
                .where(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.start_date < year.start_date,
                    AcademicYear.deleted_at.is_(None),
                )
                .order_by(AcademicYear.start_date.desc())
                .limit(1)
            )
            prev_year_id = prev_year_result.scalar_one_or_none()

            if prev_year_id:
                prev_balances_result = await self.db.execute(
                    select(LeaveBalance).where(
                        LeaveBalance.tenant_id == tenant_id,
                        LeaveBalance.academic_year_id == prev_year_id,
                    )
                )
                for b in prev_balances_result.scalars().all():
                    previous_year_balances[(b.staff_id, b.leave_type_id)] = b

        # Check existing balances to avoid duplicates
        existing_result = await self.db.execute(
            select(LeaveBalance.staff_id, LeaveBalance.leave_type_id).where(
                LeaveBalance.tenant_id == tenant_id,
                LeaveBalance.academic_year_id == academic_year_id,
            )
        )
        existing_pairs = {(row[0], row[1]) for row in existing_result.all()}

        # Create balances
        created_count = 0
        for staff_id in staff_ids:
            for lt in leave_types:
                if (staff_id, lt.id) in existing_pairs:
                    continue  # Already initialized

                carried = Decimal("0")
                if carry_over and (staff_id, lt.id) in previous_year_balances:
                    prev = previous_year_balances[(staff_id, lt.id)]
                    remaining = (
                        prev.entitled_days + prev.carried_over
                        - prev.used_days - prev.pending_days
                    )
                    # Cap carryover at max_carryover_days
                    carried = min(max(remaining, Decimal("0")), lt.max_carryover_days)

                balance = LeaveBalance(
                    tenant_id=tenant_id,
                    staff_id=staff_id,
                    leave_type_id=lt.id,
                    academic_year_id=academic_year_id,
                    entitled_days=lt.default_days_per_year,
                    carried_over=carried,
                )
                self.db.add(balance)
                created_count += 1

        await self.db.flush()

        logger.info(
            "leave_balances_initialized",
            tenant_id=str(tenant_id),
            academic_year_id=str(academic_year_id),
            created=created_count,
            staff_count=len(staff_ids),
            type_count=len(leave_types),
            carry_over=carry_over,
        )

        return {
            "created": created_count,
            "message": (
                f"Initialized {created_count} leave balances "
                f"for {len(staff_ids)} staff across {len(leave_types)} leave types"
            ),
        }

    @staticmethod
    def _balance_to_dict(
        balance: LeaveBalance,
        staff_name: Optional[str] = None,
    ) -> dict:
        """Convert a balance to a dict with computed remaining_days."""
        remaining = (
            balance.entitled_days + balance.carried_over
            - balance.used_days - balance.pending_days
        )
        return {
            "id": balance.id,
            "staff_id": balance.staff_id,
            "staff_name": staff_name,
            "leave_type_id": balance.leave_type_id,
            "leave_type_name": balance.leave_type.name if balance.leave_type else None,
            "academic_year_id": balance.academic_year_id,
            "entitled_days": balance.entitled_days,
            "used_days": balance.used_days,
            "pending_days": balance.pending_days,
            "carried_over": balance.carried_over,
            "remaining_days": remaining,
        }

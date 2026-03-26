"""
SIMS Plus - Salary Service

Manages staff salary configurations: create/update configs with allowances
and deductions, bulk salary grade assignment, and salary history.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payroll import (
    AllowanceType,
    DeductionType,
    SalaryGrade,
    StaffAllowance,
    StaffDeduction,
    StaffSalaryConfig,
)
from app.models.staff import Staff

logger = structlog.get_logger()


class SalaryService:
    """Service for managing staff salary configurations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def get_staff_salary(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> Optional[StaffSalaryConfig]:
        """
        Get the current active salary config for a staff member,
        with nested allowances and deductions eagerly loaded.
        """
        # Verify staff exists and belongs to tenant
        await self._verify_staff(tenant_id, staff_id)

        result = await self.db.execute(
            select(StaffSalaryConfig)
            .options(
                selectinload(StaffSalaryConfig.allowances).selectinload(
                    StaffAllowance.allowance_type
                ),
                selectinload(StaffSalaryConfig.deductions).selectinload(
                    StaffDeduction.deduction_type
                ),
                selectinload(StaffSalaryConfig.salary_grade),
            )
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(StaffSalaryConfig.tenant_id == tenant_id)
            .where(StaffSalaryConfig.staff_id == staff_id)
            .where(StaffSalaryConfig.is_active.is_(True))
            .where(StaffSalaryConfig.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def create_or_update_salary(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        data: dict,
        performed_by: Optional[UUID] = None,
    ) -> StaffSalaryConfig:
        """
        Create a new salary config for a staff member. If an active config
        already exists, deactivate it and set its end_date to the day before
        the new config's effective_date.
        """
        await self._verify_staff(tenant_id, staff_id)

        # Validate salary grade if provided
        salary_grade = None
        if data.get("salary_grade_id"):
            salary_grade = await self._get_salary_grade(
                tenant_id, data["salary_grade_id"]
            )

        # Validate allowance type IDs
        allowances_data = data.get("allowances", [])
        for a in allowances_data:
            await self._verify_allowance_type(tenant_id, a["allowance_type_id"])

        # Validate deduction type IDs
        deductions_data = data.get("deductions", [])
        for d in deductions_data:
            await self._verify_deduction_type(tenant_id, d["deduction_type_id"])

        # Deactivate the current active config (history preservation)
        await self._deactivate_current_config(
            tenant_id, staff_id, data["effective_date"]
        )

        # Create new config
        config = StaffSalaryConfig(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            staff_id=staff_id,
            salary_grade_id=data.get("salary_grade_id"),
            basic_salary=data["basic_salary"],
            effective_date=data["effective_date"],
            payment_method=data.get("payment_method", "bank_transfer"),
            bank_name=data.get("bank_name"),
            bank_branch=data.get("bank_branch"),
            account_number=data.get("account_number"),
            mobile_money_number=data.get("mobile_money_number"),
            mobile_money_provider=data.get("mobile_money_provider"),
            tin_number=data.get("tin_number"),
            ssnit_number=data.get("ssnit_number"),
            notes=data.get("notes"),
            is_active=True,
        )
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)

        # Add allowances
        for a_data in allowances_data:
            allowance = StaffAllowance(
                tenant_id=tenant_id,
                staff_salary_config_id=config.id,
                allowance_type_id=a_data["allowance_type_id"],
                amount=a_data["amount"],
                calculation_method=a_data.get("calculation_method"),
            )
            self.db.add(allowance)

        # Add deductions
        for d_data in deductions_data:
            deduction = StaffDeduction(
                tenant_id=tenant_id,
                staff_salary_config_id=config.id,
                deduction_type_id=d_data["deduction_type_id"],
                amount=d_data["amount"],
                calculation_method=d_data.get("calculation_method"),
            )
            self.db.add(deduction)

        await self.db.flush()

        # Reload with relationships for response
        result = await self.db.execute(
            select(StaffSalaryConfig)
            .options(
                selectinload(StaffSalaryConfig.allowances).selectinload(
                    StaffAllowance.allowance_type
                ),
                selectinload(StaffSalaryConfig.deductions).selectinload(
                    StaffDeduction.deduction_type
                ),
                selectinload(StaffSalaryConfig.salary_grade),
            )
            .where(StaffSalaryConfig.id == config.id)
            .where(StaffSalaryConfig.tenant_id == tenant_id)
        )
        config = result.scalar_one()

        logger.info(
            "staff_salary_created",
            config_id=str(config.id),
            staff_id=str(staff_id),
            basic_salary=str(config.basic_salary),
            tenant_id=str(tenant_id),
        )
        return config

    async def bulk_assign_salary_grade(
        self,
        tenant_id: UUID,
        staff_ids: list[UUID],
        salary_grade_id: UUID,
        effective_date,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Bulk assign a salary grade to multiple staff members.

        Creates new salary configs using the grade's basic_salary.
        Deactivates existing active configs for each staff member.
        """
        # Verify salary grade exists
        grade = await self._get_salary_grade(tenant_id, salary_grade_id)

        assigned = 0
        skipped = 0
        errors: list[str] = []

        for sid in staff_ids:
            try:
                # Verify staff exists
                staff = await self._verify_staff(tenant_id, sid)

                # Deactivate current config
                await self._deactivate_current_config(
                    tenant_id, sid, effective_date
                )

                # Create new config from grade
                config = StaffSalaryConfig(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    staff_id=sid,
                    salary_grade_id=salary_grade_id,
                    basic_salary=grade.basic_salary,
                    effective_date=effective_date,
                    is_active=True,
                )
                self.db.add(config)
                assigned += 1
            except self.Error as e:
                skipped += 1
                errors.append(f"Staff {sid}: {e.message}")
            except Exception as e:
                skipped += 1
                errors.append(f"Staff {sid}: unexpected error")
                logger.warning(
                    "bulk_salary_assign_error",
                    staff_id=str(sid),
                    error=str(e),
                )

        await self.db.flush()

        logger.info(
            "bulk_salary_grade_assigned",
            grade_id=str(salary_grade_id),
            assigned=assigned,
            skipped=skipped,
            tenant_id=str(tenant_id),
        )

        return {
            "assigned_count": assigned,
            "skipped_count": skipped,
            "errors": errors,
        }

    async def get_salary_history(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> list[StaffSalaryConfig]:
        """Get all salary configs for a staff member, ordered by effective_date descending."""
        await self._verify_staff(tenant_id, staff_id)

        result = await self.db.execute(
            select(StaffSalaryConfig)
            .options(
                selectinload(StaffSalaryConfig.allowances).selectinload(
                    StaffAllowance.allowance_type
                ),
                selectinload(StaffSalaryConfig.deductions).selectinload(
                    StaffDeduction.deduction_type
                ),
                selectinload(StaffSalaryConfig.salary_grade),
            )
            .where(StaffSalaryConfig.tenant_id == tenant_id)
            .where(StaffSalaryConfig.staff_id == staff_id)
            .where(StaffSalaryConfig.deleted_at.is_(None))
            .order_by(StaffSalaryConfig.effective_date.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _verify_staff(self, tenant_id: UUID, staff_id: UUID) -> Staff:
        """Verify staff exists and belongs to tenant."""
        result = await self.db.execute(
            select(Staff)
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.id == staff_id)
            .where(Staff.deleted_at.is_(None))
        )
        staff = result.scalar_one_or_none()
        if not staff:
            raise self.Error("Staff member not found", 404)
        return staff

    async def _get_salary_grade(
        self, tenant_id: UUID, grade_id: UUID
    ) -> SalaryGrade:
        result = await self.db.execute(
            select(SalaryGrade)
            .where(SalaryGrade.tenant_id == tenant_id)
            .where(SalaryGrade.id == grade_id)
            .where(SalaryGrade.deleted_at.is_(None))
            .where(SalaryGrade.is_active.is_(True))
        )
        grade = result.scalar_one_or_none()
        if not grade:
            raise self.Error("Salary grade not found or inactive", 404)
        return grade

    async def _verify_allowance_type(
        self, tenant_id: UUID, allowance_type_id: UUID
    ) -> None:
        result = await self.db.execute(
            select(AllowanceType)
            .where(AllowanceType.tenant_id == tenant_id)
            .where(AllowanceType.id == allowance_type_id)
            .where(AllowanceType.deleted_at.is_(None))
            .where(AllowanceType.is_active.is_(True))
        )
        if not result.scalar_one_or_none():
            raise self.Error(
                f"Allowance type {allowance_type_id} not found or inactive", 404
            )

    async def _verify_deduction_type(
        self, tenant_id: UUID, deduction_type_id: UUID
    ) -> None:
        result = await self.db.execute(
            select(DeductionType)
            .where(DeductionType.tenant_id == tenant_id)
            .where(DeductionType.id == deduction_type_id)
            .where(DeductionType.deleted_at.is_(None))
            .where(DeductionType.is_active.is_(True))
        )
        if not result.scalar_one_or_none():
            raise self.Error(
                f"Deduction type {deduction_type_id} not found or inactive", 404
            )

    async def _deactivate_current_config(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        new_effective_date,
    ) -> None:
        """Deactivate the current active salary config for a staff member."""
        from datetime import timedelta

        result = await self.db.execute(
            select(StaffSalaryConfig)
            .where(StaffSalaryConfig.tenant_id == tenant_id)
            .where(StaffSalaryConfig.staff_id == staff_id)
            .where(StaffSalaryConfig.is_active.is_(True))
            .where(StaffSalaryConfig.deleted_at.is_(None))
        )
        current = result.scalar_one_or_none()
        if current:
            # Set end_date to the day before the new config's effective_date
            current.is_active = False
            current.end_date = new_effective_date - timedelta(days=1)
            await self.db.flush()

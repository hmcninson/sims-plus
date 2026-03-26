"""
SIMS Plus - Payroll Configuration Service

CRUD for salary grades, allowance types, deduction types, tax brackets,
and bank file configs. All operations are tenant-scoped with defense-in-depth.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import (
    AllowanceType,
    BankFileConfig,
    DeductionType,
    SalaryGrade,
    TaxBracket,
)

logger = structlog.get_logger()

# GRA 2024 monthly PAYE tax brackets (seed data)
GHANA_TAX_BRACKETS_2024 = [
    {"band": 1, "lower": "0.00", "upper": "490.00", "rate": "0.0000", "cumulative": "0.00"},
    {"band": 2, "lower": "490.00", "upper": "600.00", "rate": "0.0500", "cumulative": "0.00"},
    {"band": 3, "lower": "600.00", "upper": "730.00", "rate": "0.1000", "cumulative": "5.50"},
    {"band": 4, "lower": "730.00", "upper": "3896.67", "rate": "0.1750", "cumulative": "18.50"},
    {"band": 5, "lower": "3896.67", "upper": "19896.67", "rate": "0.2500", "cumulative": "572.67"},
    {"band": 6, "lower": "19896.67", "upper": "50290.00", "rate": "0.3000", "cumulative": "4572.67"},
    {"band": 7, "lower": "50290.00", "upper": None, "rate": "0.3500", "cumulative": "13690.67"},
]


# Re-export for backward compatibility; canonical implementation is in calculation_service
from app.services.payroll.calculation_service import validate_bracket_contiguity  # noqa: F401


class PayrollConfigService:
    """Service for payroll configuration: salary grades, types, brackets, bank configs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    # ======================================================================
    # Salary Grades
    # ======================================================================

    async def list_salary_grades(
        self,
        tenant_id: UUID,
        active_only: bool = True,
    ) -> list[SalaryGrade]:
        """List salary grades for a tenant."""
        query = (
            select(SalaryGrade)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(SalaryGrade.tenant_id == tenant_id)
            .where(SalaryGrade.deleted_at.is_(None))
            .order_by(SalaryGrade.name)
        )
        if active_only:
            query = query.where(SalaryGrade.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_salary_grade(
        self,
        tenant_id: UUID,
        data: dict,
    ) -> SalaryGrade:
        """Create a new salary grade. Code must be unique per tenant (soft-delete aware)."""
        if data.get("code"):
            await self._check_salary_grade_code_unique(
                tenant_id, data["code"], exclude_id=None
            )

        grade = SalaryGrade(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            name=data["name"],
            code=data.get("code"),
            basic_salary=data["basic_salary"],
            min_salary=data.get("min_salary"),
            max_salary=data.get("max_salary"),
            description=data.get("description"),
            is_active=data.get("is_active", True),
        )
        self.db.add(grade)
        await self.db.flush()
        await self.db.refresh(grade)

        logger.info(
            "salary_grade_created",
            grade_id=str(grade.id),
            name=grade.name,
            tenant_id=str(tenant_id),
        )
        return grade

    async def update_salary_grade(
        self,
        tenant_id: UUID,
        grade_id: UUID,
        data: dict,
    ) -> SalaryGrade:
        """Update a salary grade."""
        grade = await self._get_salary_grade(tenant_id, grade_id)

        if "code" in data and data["code"] is not None:
            await self._check_salary_grade_code_unique(
                tenant_id, data["code"], exclude_id=grade_id
            )

        # exclude_unset=True at the endpoint layer filters out fields the user didn't send,
        # so we can safely set fields to None here (e.g. clearing description)
        for field, value in data.items():
            if hasattr(grade, field):
                setattr(grade, field, value)

        await self.db.flush()
        await self.db.refresh(grade)

        logger.info(
            "salary_grade_updated",
            grade_id=str(grade_id),
            tenant_id=str(tenant_id),
        )
        return grade

    async def delete_salary_grade(
        self,
        tenant_id: UUID,
        grade_id: UUID,
    ) -> None:
        """Soft-delete a salary grade."""
        grade = await self._get_salary_grade(tenant_id, grade_id)
        grade.deleted_at = datetime.now(timezone.utc)
        grade.is_active = False
        await self.db.flush()

        logger.info(
            "salary_grade_deleted",
            grade_id=str(grade_id),
            tenant_id=str(tenant_id),
        )

    async def _get_salary_grade(
        self, tenant_id: UUID, grade_id: UUID
    ) -> SalaryGrade:
        result = await self.db.execute(
            select(SalaryGrade)
            .where(SalaryGrade.tenant_id == tenant_id)
            .where(SalaryGrade.id == grade_id)
            .where(SalaryGrade.deleted_at.is_(None))
        )
        grade = result.scalar_one_or_none()
        if not grade:
            raise self.Error("Salary grade not found", 404)
        return grade

    async def _check_salary_grade_code_unique(
        self,
        tenant_id: UUID,
        code: str,
        exclude_id: Optional[UUID],
    ) -> None:
        """Partial unique constraint check: code must be unique among non-deleted records."""
        query = (
            select(SalaryGrade)
            .where(SalaryGrade.tenant_id == tenant_id)
            .where(SalaryGrade.code == code)
            .where(SalaryGrade.deleted_at.is_(None))
        )
        if exclude_id:
            query = query.where(SalaryGrade.id != exclude_id)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise self.Error(
                f"Salary grade with code '{code}' already exists", 409
            )

    # ======================================================================
    # Allowance Types
    # ======================================================================

    async def list_allowance_types(
        self,
        tenant_id: UUID,
        active_only: bool = True,
    ) -> list[AllowanceType]:
        query = (
            select(AllowanceType)
            .where(AllowanceType.tenant_id == tenant_id)
            .where(AllowanceType.deleted_at.is_(None))
            .order_by(AllowanceType.name)
        )
        if active_only:
            query = query.where(AllowanceType.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_allowance_type(
        self,
        tenant_id: UUID,
        data: dict,
    ) -> AllowanceType:
        await self._check_allowance_code_unique(tenant_id, data["code"], exclude_id=None)

        allowance = AllowanceType(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            name=data["name"],
            code=data["code"],
            calculation_method=data["calculation_method"],
            default_amount=data["default_amount"],
            is_taxable=data.get("is_taxable", True),
            is_active=data.get("is_active", True),
            description=data.get("description"),
        )
        self.db.add(allowance)
        await self.db.flush()
        await self.db.refresh(allowance)

        logger.info(
            "allowance_type_created",
            allowance_id=str(allowance.id),
            code=allowance.code,
            tenant_id=str(tenant_id),
        )
        return allowance

    async def update_allowance_type(
        self,
        tenant_id: UUID,
        allowance_id: UUID,
        data: dict,
    ) -> AllowanceType:
        allowance = await self._get_allowance_type(tenant_id, allowance_id)

        if "code" in data and data["code"] is not None:
            await self._check_allowance_code_unique(
                tenant_id, data["code"], exclude_id=allowance_id
            )

        # exclude_unset=True at the endpoint layer filters out fields the user didn't send,
        # so we can safely set fields to None here (e.g. clearing description)
        for field, value in data.items():
            if hasattr(allowance, field):
                setattr(allowance, field, value)

        await self.db.flush()
        await self.db.refresh(allowance)

        logger.info(
            "allowance_type_updated",
            allowance_id=str(allowance_id),
            tenant_id=str(tenant_id),
        )
        return allowance

    async def delete_allowance_type(
        self,
        tenant_id: UUID,
        allowance_id: UUID,
    ) -> None:
        allowance = await self._get_allowance_type(tenant_id, allowance_id)
        allowance.deleted_at = datetime.now(timezone.utc)
        allowance.is_active = False
        await self.db.flush()

        logger.info(
            "allowance_type_deleted",
            allowance_id=str(allowance_id),
            tenant_id=str(tenant_id),
        )

    async def _get_allowance_type(
        self, tenant_id: UUID, allowance_id: UUID
    ) -> AllowanceType:
        result = await self.db.execute(
            select(AllowanceType)
            .where(AllowanceType.tenant_id == tenant_id)
            .where(AllowanceType.id == allowance_id)
            .where(AllowanceType.deleted_at.is_(None))
        )
        allowance = result.scalar_one_or_none()
        if not allowance:
            raise self.Error("Allowance type not found", 404)
        return allowance

    async def _check_allowance_code_unique(
        self,
        tenant_id: UUID,
        code: str,
        exclude_id: Optional[UUID],
    ) -> None:
        query = (
            select(AllowanceType)
            .where(AllowanceType.tenant_id == tenant_id)
            .where(AllowanceType.code == code)
            .where(AllowanceType.deleted_at.is_(None))
        )
        if exclude_id:
            query = query.where(AllowanceType.id != exclude_id)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise self.Error(
                f"Allowance type with code '{code}' already exists", 409
            )

    # ======================================================================
    # Deduction Types
    # ======================================================================

    async def list_deduction_types(
        self,
        tenant_id: UUID,
        active_only: bool = True,
    ) -> list[DeductionType]:
        query = (
            select(DeductionType)
            .where(DeductionType.tenant_id == tenant_id)
            .where(DeductionType.deleted_at.is_(None))
            .order_by(DeductionType.name)
        )
        if active_only:
            query = query.where(DeductionType.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_deduction_type(
        self,
        tenant_id: UUID,
        data: dict,
    ) -> DeductionType:
        await self._check_deduction_code_unique(tenant_id, data["code"], exclude_id=None)

        deduction = DeductionType(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            name=data["name"],
            code=data["code"],
            calculation_method=data["calculation_method"],
            default_amount=data["default_amount"],
            is_statutory=data.get("is_statutory", False),
            is_employer_portion=data.get("is_employer_portion", False),
            deduction_category=data["deduction_category"],
            is_active=data.get("is_active", True),
            description=data.get("description"),
        )
        self.db.add(deduction)
        await self.db.flush()
        await self.db.refresh(deduction)

        logger.info(
            "deduction_type_created",
            deduction_id=str(deduction.id),
            code=deduction.code,
            tenant_id=str(tenant_id),
        )
        return deduction

    async def update_deduction_type(
        self,
        tenant_id: UUID,
        deduction_id: UUID,
        data: dict,
    ) -> DeductionType:
        deduction = await self._get_deduction_type(tenant_id, deduction_id)

        if "code" in data and data["code"] is not None:
            await self._check_deduction_code_unique(
                tenant_id, data["code"], exclude_id=deduction_id
            )

        # exclude_unset=True at the endpoint layer filters out fields the user didn't send,
        # so we can safely set fields to None here (e.g. clearing description)
        for field, value in data.items():
            if hasattr(deduction, field):
                setattr(deduction, field, value)

        await self.db.flush()
        await self.db.refresh(deduction)

        logger.info(
            "deduction_type_updated",
            deduction_id=str(deduction_id),
            tenant_id=str(tenant_id),
        )
        return deduction

    async def delete_deduction_type(
        self,
        tenant_id: UUID,
        deduction_id: UUID,
    ) -> None:
        deduction = await self._get_deduction_type(tenant_id, deduction_id)
        deduction.deleted_at = datetime.now(timezone.utc)
        deduction.is_active = False
        await self.db.flush()

        logger.info(
            "deduction_type_deleted",
            deduction_id=str(deduction_id),
            tenant_id=str(tenant_id),
        )

    async def _get_deduction_type(
        self, tenant_id: UUID, deduction_id: UUID
    ) -> DeductionType:
        result = await self.db.execute(
            select(DeductionType)
            .where(DeductionType.tenant_id == tenant_id)
            .where(DeductionType.id == deduction_id)
            .where(DeductionType.deleted_at.is_(None))
        )
        deduction = result.scalar_one_or_none()
        if not deduction:
            raise self.Error("Deduction type not found", 404)
        return deduction

    async def _check_deduction_code_unique(
        self,
        tenant_id: UUID,
        code: str,
        exclude_id: Optional[UUID],
    ) -> None:
        query = (
            select(DeductionType)
            .where(DeductionType.tenant_id == tenant_id)
            .where(DeductionType.code == code)
            .where(DeductionType.deleted_at.is_(None))
        )
        if exclude_id:
            query = query.where(DeductionType.id != exclude_id)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise self.Error(
                f"Deduction type with code '{code}' already exists", 409
            )

    # ======================================================================
    # Tax Brackets
    # ======================================================================

    async def list_tax_brackets(
        self,
        tenant_id: UUID,
        effective_year: Optional[int] = None,
    ) -> list[TaxBracket]:
        """List tax brackets for a tenant, optionally filtered by year."""
        query = (
            select(TaxBracket)
            .where(TaxBracket.tenant_id == tenant_id)
            .order_by(TaxBracket.effective_year.desc(), TaxBracket.band_number)
        )
        if effective_year is not None:
            query = query.where(TaxBracket.effective_year == effective_year)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def seed_tax_brackets(
        self,
        tenant_id: UUID,
        effective_year: int = 2024,
        school_id: Optional[UUID] = None,
    ) -> int:
        """
        Idempotent seed of GRA tax brackets for a given year.

        If brackets already exist for the year + tenant, returns 0 (no-op).
        Validates contiguity of seed data before inserting.
        """
        # Check if brackets already exist for this year
        existing = await self.db.execute(
            select(TaxBracket)
            .where(TaxBracket.tenant_id == tenant_id)
            .where(TaxBracket.effective_year == effective_year)
        )
        if existing.scalars().first():
            return 0  # Already seeded — idempotent

        # Validate contiguity of seed data
        seed_brackets = [
            {
                "band_number": b["band"],
                "lower_limit": b["lower"],
                "upper_limit": b["upper"],
            }
            for b in GHANA_TAX_BRACKETS_2024
        ]
        validate_bracket_contiguity(seed_brackets)

        count = 0
        for bracket_data in GHANA_TAX_BRACKETS_2024:
            bracket = TaxBracket(
                tenant_id=tenant_id,
                school_id=school_id,
                effective_year=effective_year,
                band_number=bracket_data["band"],
                lower_limit=Decimal(bracket_data["lower"]),
                upper_limit=(
                    Decimal(bracket_data["upper"])
                    if bracket_data["upper"] is not None
                    else None
                ),
                rate=Decimal(bracket_data["rate"]),
                cumulative_tax=Decimal(bracket_data["cumulative"]),
            )
            self.db.add(bracket)
            count += 1

        await self.db.flush()

        logger.info(
            "tax_brackets_seeded",
            count=count,
            effective_year=effective_year,
            tenant_id=str(tenant_id),
        )
        return count

    async def update_tax_bracket(
        self,
        tenant_id: UUID,
        bracket_id: UUID,
        data: dict,
    ) -> TaxBracket:
        """
        Update a single tax bracket. After updating, validates contiguity
        of the entire year's brackets to prevent calculation errors.
        """
        result = await self.db.execute(
            select(TaxBracket)
            .where(TaxBracket.tenant_id == tenant_id)
            .where(TaxBracket.id == bracket_id)
        )
        bracket = result.scalar_one_or_none()
        if not bracket:
            raise self.Error("Tax bracket not found", 404)

        for field, value in data.items():
            if value is not None and hasattr(bracket, field):
                setattr(bracket, field, value)

        await self.db.flush()
        await self.db.refresh(bracket)

        # Validate contiguity after update to prevent gaps in tax table
        all_brackets = await self.list_tax_brackets(
            tenant_id, effective_year=bracket.effective_year
        )
        bracket_dicts = [
            {
                "band_number": b.band_number,
                "lower_limit": b.lower_limit,
                "upper_limit": b.upper_limit,
            }
            for b in all_brackets
        ]
        try:
            validate_bracket_contiguity(bracket_dicts)
        except ValueError as e:
            raise self.Error(str(e), 422)

        logger.info(
            "tax_bracket_updated",
            bracket_id=str(bracket_id),
            tenant_id=str(tenant_id),
        )
        return bracket

    # ======================================================================
    # Bank File Configs
    # ======================================================================

    async def list_bank_file_configs(
        self,
        tenant_id: UUID,
    ) -> list[BankFileConfig]:
        result = await self.db.execute(
            select(BankFileConfig)
            .where(BankFileConfig.tenant_id == tenant_id)
            .where(BankFileConfig.deleted_at.is_(None))
            .order_by(BankFileConfig.bank_name)
        )
        return list(result.scalars().all())

    async def create_bank_file_config(
        self,
        tenant_id: UUID,
        data: dict,
    ) -> BankFileConfig:
        """Create a bank file config. Bank name must be unique per tenant."""
        await self._check_bank_name_unique(
            tenant_id, data["bank_name"], exclude_id=None
        )

        config = BankFileConfig(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            bank_name=data["bank_name"],
            file_format=data.get("file_format", "csv"),
            delimiter=data.get("delimiter", ","),
            column_mapping=[
                cm if isinstance(cm, dict) else cm.model_dump()
                for cm in data["column_mapping"]
            ],
            header_template=data.get("header_template"),
            footer_template=data.get("footer_template"),
            include_header_row=data.get("include_header_row", True),
            date_format=data.get("date_format", "YYYY-MM-DD"),
            amount_format=data.get("amount_format", "decimal"),
            encoding=data.get("encoding", "utf-8"),
            is_default=data.get("is_default", False),
        )
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)

        logger.info(
            "bank_file_config_created",
            config_id=str(config.id),
            bank_name=config.bank_name,
            tenant_id=str(tenant_id),
        )
        return config

    async def update_bank_file_config(
        self,
        tenant_id: UUID,
        config_id: UUID,
        data: dict,
    ) -> BankFileConfig:
        config = await self._get_bank_file_config(tenant_id, config_id)

        if "bank_name" in data and data["bank_name"] is not None:
            await self._check_bank_name_unique(
                tenant_id, data["bank_name"], exclude_id=config_id
            )

        # exclude_unset=True at the endpoint layer filters out fields the user didn't send,
        # so we can safely set fields to None here (e.g. clearing header_template)
        for field, value in data.items():
            if hasattr(config, field):
                if field == "column_mapping" and value is not None:
                    # Ensure column_mapping entries are dicts
                    config.column_mapping = [
                        cm if isinstance(cm, dict) else cm.model_dump()
                        for cm in value
                    ]
                else:
                    setattr(config, field, value)

        await self.db.flush()
        await self.db.refresh(config)

        logger.info(
            "bank_file_config_updated",
            config_id=str(config_id),
            tenant_id=str(tenant_id),
        )
        return config

    async def delete_bank_file_config(
        self,
        tenant_id: UUID,
        config_id: UUID,
    ) -> None:
        config = await self._get_bank_file_config(tenant_id, config_id)
        config.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "bank_file_config_deleted",
            config_id=str(config_id),
            tenant_id=str(tenant_id),
        )

    async def _get_bank_file_config(
        self, tenant_id: UUID, config_id: UUID
    ) -> BankFileConfig:
        result = await self.db.execute(
            select(BankFileConfig)
            .where(BankFileConfig.tenant_id == tenant_id)
            .where(BankFileConfig.id == config_id)
            .where(BankFileConfig.deleted_at.is_(None))
        )
        config = result.scalar_one_or_none()
        if not config:
            raise self.Error("Bank file config not found", 404)
        return config

    async def _check_bank_name_unique(
        self,
        tenant_id: UUID,
        bank_name: str,
        exclude_id: Optional[UUID],
    ) -> None:
        query = (
            select(BankFileConfig)
            .where(BankFileConfig.tenant_id == tenant_id)
            .where(BankFileConfig.bank_name == bank_name)
            .where(BankFileConfig.deleted_at.is_(None))
        )
        if exclude_id:
            query = query.where(BankFileConfig.id != exclude_id)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise self.Error(
                f"Bank file config for '{bank_name}' already exists", 409
            )

"""
SIMS Plus - Payroll Models

Database models for the payroll module: salary grades, allowance/deduction types,
tax brackets, staff salary configs, payroll runs, payroll items, approvals,
bank file configs, and payroll audit log.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.staff import Staff
    from app.models.user import User
    from app.models.school import School
    from app.models.loan import LoanInstallment


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PayrollRunStatus(str, Enum):
    """Payroll run lifecycle status."""
    DRAFT = "draft"
    PROCESSING = "processing"
    CALCULATED = "calculated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class PayrollRunType(str, Enum):
    """Type of payroll run."""
    REGULAR = "regular"
    SUPPLEMENTARY = "supplementary"
    BONUS = "bonus"
    ARREARS = "arrears"


class CalculationMethod(str, Enum):
    """How an allowance or deduction amount is calculated."""
    FIXED = "fixed"
    PERCENTAGE_BASIC = "percentage_basic"
    PERCENTAGE_GROSS = "percentage_gross"


class PayrollPaymentMethod(str, Enum):
    """Payment method for salary disbursement."""
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    MOBILE_MONEY = "mobile_money"


class DeductionCategory(str, Enum):
    """Category of deduction."""
    STATUTORY = "statutory"
    VOLUNTARY = "voluntary"
    LOAN = "loan"
    UNION = "union"
    OTHER = "other"


class PayrollApprovalAction(str, Enum):
    """Action taken during payroll approval."""
    APPROVE = "approve"
    REJECT = "reject"
    RETURN_FOR_REVIEW = "return_for_review"


# ---------------------------------------------------------------------------
# 1. SalaryGrade
# ---------------------------------------------------------------------------

class SalaryGrade(Base, TenantMixin, SoftDeleteMixin):
    """
    Salary grade model.

    Defines pay scales with a base salary amount and optional min/max range.
    """
    __tablename__ = "salary_grades"
    __table_args__ = (
        # Partial unique index on (tenant_id, code) WHERE deleted_at IS NULL
        # is created in migration — not expressible as a SQLAlchemy constraint.
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    max_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )

    # Relationships
    salary_configs: Mapped[list["StaffSalaryConfig"]] = relationship(
        "StaffSalaryConfig",
        back_populates="salary_grade",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 2. AllowanceType
# ---------------------------------------------------------------------------

class AllowanceType(Base, TenantMixin, SoftDeleteMixin):
    """
    Allowance type model.

    Defines categories of allowances (e.g., Housing, Responsibility, Transport)
    with a default calculation method and amount.
    """
    __tablename__ = "allowance_types"
    __table_args__ = (
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_method: Mapped[CalculationMethod] = mapped_column(
        SQLEnum(
            CalculationMethod,
            name="calculationmethod",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    default_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_taxable: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    staff_allowances: Mapped[list["StaffAllowance"]] = relationship(
        "StaffAllowance",
        back_populates="allowance_type",
        lazy="raise",
    )
    payroll_item_earnings: Mapped[list["PayrollItemEarning"]] = relationship(
        "PayrollItemEarning",
        back_populates="allowance_type",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 3. DeductionType
# ---------------------------------------------------------------------------

class DeductionType(Base, TenantMixin, SoftDeleteMixin):
    """
    Deduction type model.

    Defines categories of deductions (SSNIT Employee, Staff Welfare, Loan, etc.)
    with statutory/employer flags and calculation method.
    """
    __tablename__ = "deduction_types"
    __table_args__ = (
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_method: Mapped[CalculationMethod] = mapped_column(
        SQLEnum(
            CalculationMethod,
            name="calculationmethod",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    default_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_statutory: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    is_employer_portion: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    deduction_category: Mapped[DeductionCategory] = mapped_column(
        SQLEnum(
            DeductionCategory,
            name="deductioncategory",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    staff_deductions: Mapped[list["StaffDeduction"]] = relationship(
        "StaffDeduction",
        back_populates="deduction_type",
        lazy="raise",
    )
    payroll_item_deductions: Mapped[list["PayrollItemDeduction"]] = relationship(
        "PayrollItemDeduction",
        back_populates="deduction_type",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 4. TaxBracket
# ---------------------------------------------------------------------------

class TaxBracket(Base, TenantMixin):
    """
    Tax bracket model.

    Represents one band in the PAYE graduated tax table (e.g., GRA 2024 rates).
    No SoftDeleteMixin — brackets are replaced per effective_year, not soft-deleted.
    """
    __tablename__ = "tax_brackets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "effective_year", "band_number",
            name="uq_tax_bracket_year_band",
        ),
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    effective_year: Mapped[int] = mapped_column(Integer, nullable=False)
    band_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    upper_limit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True,
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    cumulative_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )


# ---------------------------------------------------------------------------
# 5. StaffSalaryConfig
# ---------------------------------------------------------------------------

class StaffSalaryConfig(Base, TenantMixin, SoftDeleteMixin):
    """
    Staff salary configuration model.

    Stores the active salary configuration for a staff member: basic salary,
    payment method, bank details, and links to an optional salary grade.
    """
    __tablename__ = "staff_salary_configs"
    __table_args__ = (
        # Partial unique and partial active indexes created in migration.
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    salary_grade_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("salary_grades.id", ondelete="SET NULL"),
        nullable=True,
    )
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_method: Mapped[Optional[PayrollPaymentMethod]] = mapped_column(
        SQLEnum(
            PayrollPaymentMethod,
            name="payrollpaymentmethod",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default="bank_transfer",
        nullable=True,
    )
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mobile_money_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mobile_money_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tin_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ssnit_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="raise",
    )
    salary_grade: Mapped[Optional["SalaryGrade"]] = relationship(
        "SalaryGrade",
        back_populates="salary_configs",
        lazy="raise",
    )
    allowances: Mapped[list["StaffAllowance"]] = relationship(
        "StaffAllowance",
        back_populates="salary_config",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    deductions: Mapped[list["StaffDeduction"]] = relationship(
        "StaffDeduction",
        back_populates="salary_config",
        cascade="all, delete-orphan",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 6. StaffAllowance
# ---------------------------------------------------------------------------

class StaffAllowance(Base, TenantMixin):
    """
    Staff allowance assignment.

    Links a staff salary config to an allowance type with a specific amount.
    No SoftDeleteMixin — junction-like, use hard delete.
    """
    __tablename__ = "staff_allowances"
    __table_args__ = (
        UniqueConstraint(
            "staff_salary_config_id", "allowance_type_id",
            name="uq_staff_allowance_config_type",
        ),
        {"extend_existing": True},
    )

    staff_salary_config_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_salary_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    allowance_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("allowance_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    calculation_method: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Override allowance type default calculation method",
    )

    # Relationships
    salary_config: Mapped["StaffSalaryConfig"] = relationship(
        "StaffSalaryConfig",
        back_populates="allowances",
        lazy="raise",
    )
    allowance_type: Mapped["AllowanceType"] = relationship(
        "AllowanceType",
        back_populates="staff_allowances",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 7. StaffDeduction
# ---------------------------------------------------------------------------

class StaffDeduction(Base, TenantMixin):
    """
    Staff deduction assignment.

    Links a staff salary config to a deduction type with a specific amount.
    No SoftDeleteMixin — junction-like, use hard delete.
    """
    __tablename__ = "staff_deductions"
    __table_args__ = (
        UniqueConstraint(
            "staff_salary_config_id", "deduction_type_id",
            name="uq_staff_deduction_config_type",
        ),
        {"extend_existing": True},
    )

    staff_salary_config_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_salary_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    deduction_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("deduction_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    calculation_method: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Override deduction type default calculation method",
    )

    # Relationships
    salary_config: Mapped["StaffSalaryConfig"] = relationship(
        "StaffSalaryConfig",
        back_populates="deductions",
        lazy="raise",
    )
    deduction_type: Mapped["DeductionType"] = relationship(
        "DeductionType",
        back_populates="staff_deductions",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 8. PayrollRun
# ---------------------------------------------------------------------------

class PayrollRun(Base, TenantMixin, SoftDeleteMixin):
    """
    Payroll run model.

    Represents a single payroll processing cycle for a given month/year.
    Tracks aggregate totals and lifecycle status.
    """
    __tablename__ = "payroll_runs"
    __table_args__ = (
        # COALESCE unique index created in migration.
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    run_number: Mapped[int] = mapped_column(
        Integer, server_default="1", nullable=False,
    )
    status: Mapped[PayrollRunStatus] = mapped_column(
        SQLEnum(
            PayrollRunStatus,
            name="payrollrunstatus",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    run_type: Mapped[PayrollRunType] = mapped_column(
        SQLEnum(
            PayrollRunType,
            name="payrollruntype",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default="regular",
        nullable=False,
    )

    # Aggregate totals
    total_basic: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_allowances: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_gross: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_paye: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_ssnit_ee: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_ssnit_er: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_tier2_er: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_tier3: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_other_deductions: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_net: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    total_employer_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default="0", nullable=False,
    )
    staff_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3), server_default="GHS", nullable=False,
    )

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    bank_file_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
    )
    bank_file_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    items: Mapped[list["PayrollItem"]] = relationship(
        "PayrollItem",
        back_populates="payroll_run",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    approvals: Mapped[list["PayrollApproval"]] = relationship(
        "PayrollApproval",
        back_populates="payroll_run",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    processor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[processed_by],
        lazy="raise",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 9. PayrollItem
# ---------------------------------------------------------------------------

class PayrollItem(Base, TenantMixin):
    """
    Payroll item model.

    Stores the calculated payroll details for one staff member in a payroll run.
    All staff/bank details are denormalized (snapshot) for auditability.
    No SoftDeleteMixin — items are deleted and recalculated when a run is reprocessed.
    """
    __tablename__ = "payroll_items"
    __table_args__ = (
        UniqueConstraint(
            "payroll_run_id", "staff_id",
            name="uq_payroll_item_run_staff",
        ),
        {"extend_existing": True},
    )

    payroll_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Snapshot fields (denormalized for audit)
    staff_name: Mapped[str] = mapped_column(String(300), nullable=False)
    staff_code: Mapped[str] = mapped_column(String(50), nullable=False)
    department_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    salary_grade_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Calculated fields
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_allowances: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    gross_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    taxable_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paye_tax: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    ssnit_employee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    ssnit_employer: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    tier2_employer: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    tier3_employee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    total_deductions: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False,
    )
    net_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Payment snapshot
    payment_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mobile_money_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ssnit_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tin_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Relationships
    payroll_run: Mapped["PayrollRun"] = relationship(
        "PayrollRun",
        back_populates="items",
        lazy="raise",
    )
    staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="raise",
    )
    earnings: Mapped[list["PayrollItemEarning"]] = relationship(
        "PayrollItemEarning",
        back_populates="payroll_item",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    deductions: Mapped[list["PayrollItemDeduction"]] = relationship(
        "PayrollItemDeduction",
        back_populates="payroll_item",
        cascade="all, delete-orphan",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 10. PayrollItemEarning
# ---------------------------------------------------------------------------

class PayrollItemEarning(Base, TenantMixin):
    """
    Payroll item earning line.

    Stores one allowance/earning entry for a payroll item (snapshot).
    No SoftDeleteMixin — junction-like, cascades from payroll_items.
    """
    __tablename__ = "payroll_item_earnings"
    __table_args__ = {"extend_existing": True}

    payroll_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("payroll_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    allowance_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("allowance_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_taxable: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )

    # Relationships
    payroll_item: Mapped["PayrollItem"] = relationship(
        "PayrollItem",
        back_populates="earnings",
        lazy="raise",
    )
    allowance_type: Mapped[Optional["AllowanceType"]] = relationship(
        "AllowanceType",
        back_populates="payroll_item_earnings",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 11. PayrollItemDeduction
# ---------------------------------------------------------------------------

class PayrollItemDeduction(Base, TenantMixin):
    """
    Payroll item deduction line.

    Stores one deduction entry for a payroll item (snapshot).
    No SoftDeleteMixin — junction-like, cascades from payroll_items.
    """
    __tablename__ = "payroll_item_deductions"
    __table_args__ = {"extend_existing": True}

    payroll_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("payroll_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    deduction_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("deduction_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_statutory: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    is_employer_portion: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    deduction_category: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True,
    )

    # FK to loan installment (added Phase 5 — Loan Management)
    loan_installment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("loan_installments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    payroll_item: Mapped["PayrollItem"] = relationship(
        "PayrollItem",
        back_populates="deductions",
        lazy="raise",
    )
    deduction_type: Mapped[Optional["DeductionType"]] = relationship(
        "DeductionType",
        back_populates="payroll_item_deductions",
        lazy="raise",
    )
    loan_installment: Mapped[Optional["LoanInstallment"]] = relationship(
        "LoanInstallment",
        foreign_keys=[loan_installment_id],
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 12. PayrollApproval
# ---------------------------------------------------------------------------

class PayrollApproval(Base, TenantMixin):
    """
    Payroll approval record.

    Tracks each approval/rejection action on a payroll run.
    No SoftDeleteMixin — permanent audit records.
    No updated_at override — Base provides it, but this is write-once.
    """
    __tablename__ = "payroll_approvals"
    __table_args__ = {"extend_existing": True}

    payroll_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    approver_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[PayrollApprovalAction] = mapped_column(
        SQLEnum(
            PayrollApprovalAction,
            name="payrollapprovalaction",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    payroll_run: Mapped["PayrollRun"] = relationship(
        "PayrollRun",
        back_populates="approvals",
        lazy="raise",
    )
    approver: Mapped["User"] = relationship(
        "User",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 13. BankFileConfig
# ---------------------------------------------------------------------------

class BankFileConfig(Base, TenantMixin, SoftDeleteMixin):
    """
    Bank file configuration model.

    Stores the column mapping and format settings for generating bank
    payment files (CSV, pipe-delimited, etc.) for each bank.
    """
    __tablename__ = "bank_file_configs"
    __table_args__ = (
        # Partial unique index on (tenant_id, bank_name) WHERE deleted_at IS NULL
        # is created in migration.
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    file_format: Mapped[str] = mapped_column(
        String(20), server_default="csv", nullable=False,
    )
    delimiter: Mapped[Optional[str]] = mapped_column(
        String(5), server_default=",", nullable=True,
    )
    column_mapping: Mapped[list] = mapped_column(JSONB, nullable=False)
    header_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    footer_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    include_header_row: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )
    date_format: Mapped[Optional[str]] = mapped_column(
        String(20), server_default="YYYY-MM-DD", nullable=True,
    )
    amount_format: Mapped[Optional[str]] = mapped_column(
        String(20), server_default="decimal", nullable=True,
    )
    encoding: Mapped[Optional[str]] = mapped_column(
        String(20), server_default="utf-8", nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )


# ---------------------------------------------------------------------------
# 14. PayrollAuditLog
# ---------------------------------------------------------------------------

class PayrollAuditLog(Base, TenantMixin):
    """
    Payroll audit log model.

    Append-only audit trail for all payroll mutations. The database GRANT
    restricts sims_app_user to SELECT + INSERT only (no UPDATE, no DELETE).

    IMPORTANT: The `metadata` column is a reserved name in SQLAlchemy's
    Declarative API. The Python attribute is named `audit_metadata` but maps
    to the DB column `metadata` via the explicit column name parameter.
    """
    __tablename__ = "payroll_audit_log"
    __table_args__ = {"extend_existing": True}

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # CRITICAL: Python attr `audit_metadata` maps to DB column `metadata`
    # to avoid collision with SQLAlchemy's Declarative `metadata` attribute.
    audit_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True,
    )

    performed_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    performer: Mapped["User"] = relationship(
        "User",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# Loan Enums
# ---------------------------------------------------------------------------

class LoanStatus(str, Enum):
    """Loan lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    COMPLETED = "completed"
    WRITTEN_OFF = "written_off"
    RESTRUCTURED = "restructured"
    REJECTED = "rejected"


class InterestMethod(str, Enum):
    """Interest calculation method."""
    FLAT = "flat"
    REDUCING_BALANCE = "reducing_balance"


# Valid state machine transitions for loans
LOAN_VALID_TRANSITIONS: dict[LoanStatus, set[LoanStatus]] = {
    LoanStatus.DRAFT: {LoanStatus.PENDING_APPROVAL},
    LoanStatus.PENDING_APPROVAL: {LoanStatus.APPROVED, LoanStatus.REJECTED},
    LoanStatus.REJECTED: {LoanStatus.DRAFT},
    LoanStatus.APPROVED: {LoanStatus.ACTIVE},
    LoanStatus.ACTIVE: {LoanStatus.COMPLETED, LoanStatus.WRITTEN_OFF, LoanStatus.RESTRUCTURED},
}


# ---------------------------------------------------------------------------
# 15. LoanType
# ---------------------------------------------------------------------------

class LoanType(Base, TenantMixin, SoftDeleteMixin):
    """
    Loan type configuration.

    Defines school-specific loan categories (salary advance, welfare, equipment)
    with default terms, limits, and eligibility rules.
    """
    __tablename__ = "loan_types"
    __table_args__ = (
        # Partial unique on (tenant_id, code) WHERE deleted_at IS NULL
        # created in migration — not expressible as a SQLAlchemy constraint.
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_interest_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), server_default="0.00", nullable=False,
    )
    default_interest_method: Mapped[InterestMethod] = mapped_column(
        SQLEnum(
            InterestMethod,
            name="interestmethod",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default="flat",
        nullable=False,
    )
    max_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True,
    )
    max_tenure_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
    )
    max_active_loans: Mapped[int] = mapped_column(
        Integer, server_default="1", nullable=False,
    )
    requires_guarantor: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    min_service_months: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False,
    )
    max_deduction_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), server_default="50.00", nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False,
    )

    # Relationships
    loans: Mapped[list["StaffLoan"]] = relationship(
        "StaffLoan",
        back_populates="loan_type",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 16. StaffLoan
# ---------------------------------------------------------------------------

class StaffLoan(Base, TenantMixin, SoftDeleteMixin):
    """
    Staff loan entity.

    Tracks the full loan lifecycle from draft through completion, including
    principal/interest calculations, payment tracking, and balance management.
    """
    __tablename__ = "staff_loans"
    __table_args__ = (
        UniqueConstraint(
            "loan_number", "tenant_id",
            name="uq_staff_loans_number_tenant",
        ),
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    loan_number: Mapped[str] = mapped_column(String(30), nullable=False)
    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    loan_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("loan_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[LoanStatus] = mapped_column(
        SQLEnum(
            LoanStatus,
            name="loanstatus",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default="draft",
        nullable=False,
    )
    principal_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    interest_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), server_default="0.00", nullable=False,
    )
    interest_method: Mapped[InterestMethod] = mapped_column(
        SQLEnum(
            InterestMethod,
            name="interestmethod",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default="flat",
        nullable=False,
    )
    total_interest: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0.00", nullable=False,
    )
    total_repayable: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_installment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    total_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0.00", nullable=False,
    )
    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    installments_paid: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False,
    )
    installments_remaining: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )

    # Dates
    application_date: Mapped[date] = mapped_column(
        Date, server_default=text("CURRENT_DATE"), nullable=False,
    )
    approval_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    disbursement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    first_deduction_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Actors
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the loan (for self-approval prevention)",
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    disbursed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Restructuring
    restructured_from_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("staff_loans.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Write-off
    write_off_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    write_off_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    written_off_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="raise",
    )
    loan_type: Mapped["LoanType"] = relationship(
        "LoanType",
        back_populates="loans",
        lazy="raise",
    )
    installments: Mapped[list["LoanInstallment"]] = relationship(
        "LoanInstallment",
        back_populates="loan",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    guarantors: Mapped[list["LoanGuarantor"]] = relationship(
        "LoanGuarantor",
        back_populates="loan",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    payments: Mapped[list["LoanPayment"]] = relationship(
        "LoanPayment",
        back_populates="loan",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="raise",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="raise",
    )
    disburser: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[disbursed_by],
        lazy="raise",
    )
    write_off_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[written_off_by],
        lazy="raise",
    )
    restructured_from: Mapped[Optional["StaffLoan"]] = relationship(
        "StaffLoan",
        remote_side="StaffLoan.id",
        foreign_keys=[restructured_from_id],
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 17. LoanInstallment
# ---------------------------------------------------------------------------

class LoanInstallment(Base, TenantMixin):
    """
    Scheduled loan installment.

    Pre-generated at disbursement. One row per monthly payment.
    No SoftDeleteMixin — installments are historical records, never soft-deleted.
    """
    __tablename__ = "loan_installments"
    __table_args__ = (
        UniqueConstraint(
            "loan_id", "installment_number",
            name="uq_loan_installment_number",
        ),
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    loan_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_loans.id", ondelete="CASCADE"),
        nullable=False,
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    principal_component: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    interest_component: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    installment_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
    )
    is_paid: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    paid_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paid_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True,
    )
    payroll_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    payroll_item_deduction_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("payroll_item_deductions.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    loan: Mapped["StaffLoan"] = relationship(
        "StaffLoan",
        back_populates="installments",
        lazy="raise",
    )
    payroll_run: Mapped[Optional["PayrollRun"]] = relationship(
        "PayrollRun",
        lazy="raise",
    )
    payroll_item_deduction: Mapped[Optional["PayrollItemDeduction"]] = relationship(
        "PayrollItemDeduction",
        foreign_keys=[payroll_item_deduction_id],
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 18. LoanGuarantor
# ---------------------------------------------------------------------------

class LoanGuarantor(Base, TenantMixin):
    """
    Loan guarantor record.

    Tracks which staff member guarantees a loan and whether they have
    given consent. No SoftDeleteMixin — use hard delete for draft loans.
    """
    __tablename__ = "loan_guarantors"
    __table_args__ = (
        UniqueConstraint(
            "loan_id", "guarantor_staff_id",
            name="uq_loan_guarantor_staff",
        ),
        {"extend_existing": True},
    )

    loan_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_loans.id", ondelete="CASCADE"),
        nullable=False,
    )
    guarantor_staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_desc: Mapped[Optional[str]] = mapped_column(
        "relationship", String(50), nullable=True,
    )
    guaranteed_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True,
    )
    consent_given: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    consent_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    loan: Mapped["StaffLoan"] = relationship(
        "StaffLoan",
        back_populates="guarantors",
        lazy="raise",
    )
    guarantor_staff: Mapped["Staff"] = relationship(
        "Staff",
        lazy="raise",
    )


# ---------------------------------------------------------------------------
# 19. LoanPayment
# ---------------------------------------------------------------------------

class LoanPayment(Base, TenantMixin):
    """
    Loan payment record.

    Records ALL payments — both payroll deductions and out-of-band payments
    (early repayments, lump-sum settlements). No SoftDeleteMixin — payments
    are permanent audit records.
    """
    __tablename__ = "loan_payments"
    __table_args__ = (
        UniqueConstraint(
            "payment_number", "tenant_id",
            name="uq_loan_payment_number_tenant",
        ),
        {"extend_existing": True},
    )

    school_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    loan_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_loans.id", ondelete="CASCADE"),
        nullable=False,
    )
    payment_number: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    installments_covered: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
    )
    is_early_repayment: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    recorded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    loan: Mapped["StaffLoan"] = relationship(
        "StaffLoan",
        back_populates="payments",
        lazy="raise",
    )
    recorder: Mapped["User"] = relationship(
        "User",
        lazy="raise",
    )

"""
SIMS Plus - Payroll Schemas

Pydantic v2 schemas for payroll configuration, salary management,
and audit log responses (Phase 4A).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Salary Grades
# ---------------------------------------------------------------------------


class SalaryGradeCreate(BaseModel):
    """Create a salary grade (pay scale)."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    basic_salary: Decimal = Field(..., ge=0)
    min_salary: Optional[Decimal] = Field(None, ge=0)
    max_salary: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    is_active: bool = True
    school_id: Optional[UUID] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_salary_range(self) -> "SalaryGradeCreate":
        if self.min_salary is not None and self.max_salary is not None:
            if self.min_salary > self.max_salary:
                raise ValueError("min_salary cannot exceed max_salary")
        if self.min_salary is not None and self.basic_salary < self.min_salary:
            raise ValueError("basic_salary cannot be below min_salary")
        if self.max_salary is not None and self.basic_salary > self.max_salary:
            raise ValueError("basic_salary cannot exceed max_salary")
        return self


class SalaryGradeUpdate(BaseModel):
    """Update a salary grade."""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    basic_salary: Optional[Decimal] = Field(None, ge=0)
    min_salary: Optional[Decimal] = Field(None, ge=0)
    max_salary: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class SalaryGradeResponse(BaseModel):
    """Salary grade response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    name: str
    code: Optional[str] = None
    basic_salary: Decimal
    min_salary: Optional[Decimal] = None
    max_salary: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Allowance Types
# ---------------------------------------------------------------------------


class AllowanceTypeCreate(BaseModel):
    """Create an allowance type."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    calculation_method: str = Field(
        ..., pattern="^(fixed|percentage_basic|percentage_gross)$"
    )
    default_amount: Decimal = Field(..., ge=0)
    is_taxable: bool = True
    is_active: bool = True
    description: Optional[str] = None
    school_id: Optional[UUID] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class AllowanceTypeUpdate(BaseModel):
    """Update an allowance type."""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    calculation_method: Optional[str] = Field(
        None, pattern="^(fixed|percentage_basic|percentage_gross)$"
    )
    default_amount: Optional[Decimal] = Field(None, ge=0)
    is_taxable: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class AllowanceTypeResponse(BaseModel):
    """Allowance type response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    name: str
    code: str
    calculation_method: str
    default_amount: Decimal
    is_taxable: bool
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Deduction Types
# ---------------------------------------------------------------------------


class DeductionTypeCreate(BaseModel):
    """Create a deduction type."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    calculation_method: str = Field(
        ..., pattern="^(fixed|percentage_basic|percentage_gross)$"
    )
    default_amount: Decimal = Field(..., ge=0)
    is_statutory: bool = False
    is_employer_portion: bool = False
    deduction_category: str = Field(
        ..., pattern="^(statutory|voluntary|loan|union|other)$"
    )
    is_active: bool = True
    description: Optional[str] = None
    school_id: Optional[UUID] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class DeductionTypeUpdate(BaseModel):
    """Update a deduction type."""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    calculation_method: Optional[str] = Field(
        None, pattern="^(fixed|percentage_basic|percentage_gross)$"
    )
    default_amount: Optional[Decimal] = Field(None, ge=0)
    is_statutory: Optional[bool] = None
    is_employer_portion: Optional[bool] = None
    deduction_category: Optional[str] = Field(
        None, pattern="^(statutory|voluntary|loan|union|other)$"
    )
    is_active: Optional[bool] = None
    description: Optional[str] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class DeductionTypeResponse(BaseModel):
    """Deduction type response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    name: str
    code: str
    calculation_method: str
    default_amount: Decimal
    is_statutory: bool
    is_employer_portion: bool
    deduction_category: str
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Tax Brackets
# ---------------------------------------------------------------------------


class TaxBracketCreate(BaseModel):
    """Create a tax bracket (for manual creation)."""

    model_config = ConfigDict(from_attributes=True)

    effective_year: int = Field(..., ge=2020, le=2100)
    band_number: int = Field(..., ge=1)
    lower_limit: Decimal = Field(..., ge=0)
    upper_limit: Optional[Decimal] = Field(None, ge=0)
    rate: Decimal = Field(..., ge=0, le=1)
    cumulative_tax: Decimal = Field(..., ge=0)
    school_id: Optional[UUID] = None


class TaxBracketUpdate(BaseModel):
    """Update a single tax bracket."""

    model_config = ConfigDict(from_attributes=True)

    lower_limit: Optional[Decimal] = Field(None, ge=0)
    upper_limit: Optional[Decimal] = Field(None, ge=0)
    rate: Optional[Decimal] = Field(None, ge=0, le=1)
    cumulative_tax: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None


class TaxBracketResponse(BaseModel):
    """Tax bracket response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    effective_year: int
    band_number: int
    lower_limit: Decimal
    upper_limit: Optional[Decimal] = None
    rate: Decimal
    cumulative_tax: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TaxBracketSeedRequest(BaseModel):
    """Seed tax brackets for a year."""

    effective_year: int = Field(2024, ge=2020, le=2100)
    school_id: Optional[UUID] = None


class TaxBracketSeedResponse(BaseModel):
    """Response from seeding tax brackets."""

    brackets_created: int
    effective_year: int
    message: str


# ---------------------------------------------------------------------------
# Staff Allowance / Deduction (nested in salary config)
# ---------------------------------------------------------------------------


class StaffAllowanceCreate(BaseModel):
    """Allowance assignment for a staff salary config."""

    model_config = ConfigDict(from_attributes=True)

    allowance_type_id: UUID
    amount: Decimal = Field(..., ge=0)
    calculation_method: Optional[str] = Field(
        None, pattern="^(fixed|percentage_basic|percentage_gross)$"
    )


class StaffAllowanceResponse(BaseModel):
    """Staff allowance response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    allowance_type_id: UUID
    amount: Decimal
    calculation_method: Optional[str] = None
    # Denormalized from allowance type for convenience
    allowance_type_name: Optional[str] = None
    allowance_type_code: Optional[str] = None


class StaffDeductionCreate(BaseModel):
    """Deduction assignment for a staff salary config."""

    model_config = ConfigDict(from_attributes=True)

    deduction_type_id: UUID
    amount: Decimal = Field(..., ge=0)
    calculation_method: Optional[str] = Field(
        None, pattern="^(fixed|percentage_basic|percentage_gross)$"
    )


class StaffDeductionResponse(BaseModel):
    """Staff deduction response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deduction_type_id: UUID
    amount: Decimal
    calculation_method: Optional[str] = None
    # Denormalized from deduction type for convenience
    deduction_type_name: Optional[str] = None
    deduction_type_code: Optional[str] = None


# ---------------------------------------------------------------------------
# Staff Salary Config
# ---------------------------------------------------------------------------


class StaffSalaryConfigCreate(BaseModel):
    """Create or update a staff salary configuration."""

    model_config = ConfigDict(from_attributes=True)

    salary_grade_id: Optional[UUID] = None
    basic_salary: Decimal = Field(..., ge=0)
    effective_date: date
    payment_method: Optional[str] = Field(
        "bank_transfer",
        pattern="^(bank_transfer|cash|mobile_money)$",
    )
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=50)
    mobile_money_number: Optional[str] = Field(None, max_length=20)
    mobile_money_provider: Optional[str] = Field(None, max_length=20)
    tin_number: Optional[str] = Field(None, max_length=20)
    ssnit_number: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    school_id: Optional[UUID] = None

    # Nested allowances and deductions
    allowances: list[StaffAllowanceCreate] = Field(default_factory=list)
    deductions: list[StaffDeductionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payment_details(self) -> "StaffSalaryConfigCreate":
        """Bank details required for bank_transfer, mobile details for mobile_money."""
        if self.payment_method == "bank_transfer":
            if not self.bank_name or not self.account_number:
                raise ValueError(
                    "bank_name and account_number are required for bank_transfer"
                )
        if self.payment_method == "mobile_money":
            if not self.mobile_money_number or not self.mobile_money_provider:
                raise ValueError(
                    "mobile_money_number and mobile_money_provider are required for mobile_money"
                )
        return self


class StaffSalaryConfigUpdate(BaseModel):
    """Update a staff salary configuration (creates new config, deactivates old)."""

    model_config = ConfigDict(from_attributes=True)

    salary_grade_id: Optional[UUID] = None
    basic_salary: Optional[Decimal] = Field(None, ge=0)
    effective_date: Optional[date] = None
    payment_method: Optional[str] = Field(
        None, pattern="^(bank_transfer|cash|mobile_money)$"
    )
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=50)
    mobile_money_number: Optional[str] = Field(None, max_length=20)
    mobile_money_provider: Optional[str] = Field(None, max_length=20)
    tin_number: Optional[str] = Field(None, max_length=20)
    ssnit_number: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None

    # Nested allowances and deductions (replaces all existing)
    allowances: Optional[list[StaffAllowanceCreate]] = None
    deductions: Optional[list[StaffDeductionCreate]] = None


def _mask_account_number(account_number: Optional[str]) -> Optional[str]:
    """Mask account number, showing only last 4 digits: ****5678."""
    if not account_number:
        return None
    if len(account_number) <= 4:
        return "****"
    return "****" + account_number[-4:]


class StaffSalaryConfigResponse(BaseModel):
    """Staff salary configuration response with masked sensitive data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    staff_id: UUID
    salary_grade_id: Optional[UUID] = None
    basic_salary: Decimal
    effective_date: date
    end_date: Optional[date] = None
    payment_method: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    account_number: Optional[str] = None
    mobile_money_number: Optional[str] = None
    mobile_money_provider: Optional[str] = None
    tin_number: Optional[str] = None
    ssnit_number: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Nested
    allowances: list[StaffAllowanceResponse] = Field(default_factory=list)
    deductions: list[StaffDeductionResponse] = Field(default_factory=list)

    # Denormalized salary grade info
    salary_grade_name: Optional[str] = None

    @field_validator("account_number", mode="before")
    @classmethod
    def mask_account(cls, v: Optional[str]) -> Optional[str]:
        """Mask account number in API responses for security."""
        return _mask_account_number(v)


# ---------------------------------------------------------------------------
# Bulk Salary Assignment
# ---------------------------------------------------------------------------


class BulkSalaryAssignRequest(BaseModel):
    """Bulk assign a salary grade to multiple staff members."""

    staff_ids: list[UUID] = Field(..., min_length=1, max_length=200)
    salary_grade_id: UUID
    effective_date: date
    school_id: Optional[UUID] = None


class BulkSalaryAssignResponse(BaseModel):
    """Response from bulk salary assignment."""

    assigned_count: int
    skipped_count: int
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bank File Configs
# ---------------------------------------------------------------------------

# Whitelist of allowed source fields for bank file column_mapping
ALLOWED_COLUMN_SOURCES = {
    "staff_name",
    "staff_code",
    "account_number",
    "bank_name",
    "bank_branch",
    "net_salary",
    "basic_salary",
    "gross_salary",
    "ssnit_number",
    "tin_number",
    "mobile_money_number",
    "department_name",
    "salary_grade_name",
    "payment_method",
    "template",  # special: uses the 'template' key for dynamic values
}


class ColumnMappingEntry(BaseModel):
    """One column in a bank file column_mapping."""

    header: str = Field(..., min_length=1, max_length=100)
    source: str = Field(..., min_length=1, max_length=50)
    format: Optional[str] = None
    template: Optional[str] = None
    width: Optional[int] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in ALLOWED_COLUMN_SOURCES:
            raise ValueError(
                f"Invalid source '{v}'. Allowed: {sorted(ALLOWED_COLUMN_SOURCES)}"
            )
        return v


class BankFileConfigCreate(BaseModel):
    """Create a bank file configuration."""

    model_config = ConfigDict(from_attributes=True)

    bank_name: str = Field(..., min_length=1, max_length=100)
    file_format: str = Field("csv", pattern="^(csv|tsv|pipe|fixed_width)$")
    delimiter: Optional[str] = Field(",", max_length=5)
    column_mapping: list[ColumnMappingEntry] = Field(..., min_length=1)
    header_template: Optional[str] = None
    footer_template: Optional[str] = None
    include_header_row: bool = True
    date_format: Optional[str] = Field("YYYY-MM-DD", max_length=20)
    amount_format: Optional[str] = Field("decimal", max_length=20)
    encoding: Optional[str] = Field("utf-8", max_length=20)
    is_default: bool = False
    school_id: Optional[UUID] = None

    @field_validator("bank_name")
    @classmethod
    def strip_bank_name(cls, v: str) -> str:
        return v.strip()


class BankFileConfigUpdate(BaseModel):
    """Update a bank file configuration."""

    model_config = ConfigDict(from_attributes=True)

    bank_name: Optional[str] = Field(None, min_length=1, max_length=100)
    file_format: Optional[str] = Field(None, pattern="^(csv|tsv|pipe|fixed_width)$")
    delimiter: Optional[str] = Field(None, max_length=5)
    column_mapping: Optional[list[ColumnMappingEntry]] = None
    header_template: Optional[str] = None
    footer_template: Optional[str] = None
    include_header_row: Optional[bool] = None
    date_format: Optional[str] = Field(None, max_length=20)
    amount_format: Optional[str] = Field(None, max_length=20)
    encoding: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = None

    @field_validator("bank_name")
    @classmethod
    def strip_bank_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class BankFileConfigResponse(BaseModel):
    """Bank file configuration response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    bank_name: str
    file_format: str
    delimiter: Optional[str] = None
    column_mapping: list[dict]
    header_template: Optional[str] = None
    footer_template: Optional[str] = None
    include_header_row: bool
    date_format: Optional[str] = None
    amount_format: Optional[str] = None
    encoding: Optional[str] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Payroll Audit Log
# ---------------------------------------------------------------------------


class PayrollAuditLogResponse(BaseModel):
    """Payroll audit log entry response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    entity_type: str
    entity_id: UUID
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    audit_metadata: Optional[dict] = None
    performed_by: UUID
    performed_at: datetime
    ip_address: Optional[str] = None


# ---------------------------------------------------------------------------
# Payroll Runs (Phase 4B)
# ---------------------------------------------------------------------------


class PayrollRunCreate(BaseModel):
    """Create a payroll run (draft)."""

    model_config = ConfigDict(from_attributes=True)

    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2100)
    run_type: str = Field(
        "regular",
        pattern="^(regular|supplementary|bonus|arrears)$",
    )
    school_id: Optional[UUID] = None
    notes: Optional[str] = None


class PayrollRunResponse(BaseModel):
    """Payroll run response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    month: int
    year: int
    run_number: int
    status: str
    run_type: str
    total_basic: Decimal
    total_allowances: Decimal
    total_gross: Decimal
    total_paye: Decimal
    total_ssnit_ee: Decimal
    total_ssnit_er: Decimal
    total_tier2_er: Decimal
    total_tier3: Decimal
    total_other_deductions: Decimal
    total_net: Decimal
    total_employer_cost: Decimal
    staff_count: int
    currency: str
    notes: Optional[str] = None
    processed_by: Optional[UUID] = None
    processed_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else v

    @field_validator("run_type", mode="before")
    @classmethod
    def coerce_run_type(cls, v):
        return v.value if hasattr(v, "value") else v


class PayrollRunSummary(BaseModel):
    """Payroll run summary statistics."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    month: int
    year: int
    run_number: int
    run_type: str
    status: str
    currency: str = "GHS"
    staff_count: int
    total_basic: Decimal
    total_allowances: Decimal
    total_gross: Decimal
    total_paye: Decimal
    total_ssnit_ee: Decimal
    total_ssnit_er: Decimal
    total_tier2_er: Decimal
    total_tier3: Decimal
    total_deductions: Decimal
    total_net: Decimal
    total_employer_cost: Decimal
    processed_by: Optional[UUID] = None
    processed_at: Optional[datetime] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Payroll Item Earnings / Deductions (Phase 4B)
# ---------------------------------------------------------------------------


class PayrollItemEarningResponse(BaseModel):
    """Payroll item earning line response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    allowance_type_id: Optional[UUID] = None
    name: str
    amount: Decimal
    is_taxable: bool


class PayrollItemDeductionResponse(BaseModel):
    """Payroll item deduction line response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deduction_type_id: Optional[UUID] = None
    name: str
    amount: Decimal
    is_statutory: bool
    is_employer_portion: bool
    deduction_category: Optional[str] = None


class PayrollItemResponse(BaseModel):
    """Payroll item response with masked account number."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    payroll_run_id: UUID
    staff_id: UUID
    staff_name: str
    staff_code: str
    department_name: Optional[str] = None
    salary_grade_name: Optional[str] = None
    basic_salary: Decimal
    total_allowances: Decimal
    gross_salary: Decimal
    taxable_income: Decimal
    paye_tax: Decimal
    ssnit_employee: Decimal
    ssnit_employer: Decimal
    tier2_employer: Decimal
    tier3_employee: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    payment_method: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    account_number: Optional[str] = None
    mobile_money_number: Optional[str] = None
    ssnit_number: Optional[str] = None
    tin_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("account_number", mode="before")
    @classmethod
    def mask_account(cls, v: Optional[str]) -> Optional[str]:
        """Mask account number in API responses for security."""
        return _mask_account_number(v)


class PayrollItemListResponse(BaseModel):
    """Payroll item response for list endpoints — excludes PII (TIN, SSNIT, bank details)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_name: str
    staff_code: str
    department_name: Optional[str] = None
    salary_grade_name: Optional[str] = None
    basic_salary: Decimal
    total_allowances: Decimal
    gross_salary: Decimal
    paye_tax: Decimal
    ssnit_employee: Decimal
    ssnit_employer: Decimal
    tier2_employer: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    payment_method: Optional[str] = None


class PayrollItemDetailResponse(PayrollItemResponse):
    """Payroll item detail with earnings and deductions."""

    earnings: list[PayrollItemEarningResponse] = Field(default_factory=list)
    deductions: list[PayrollItemDeductionResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Manual Adjustment (Phase 4B)
# ---------------------------------------------------------------------------


class ManualAdjustmentRequest(BaseModel):
    """Manual adjustment to a payroll item."""

    basic_salary: Optional[Decimal] = Field(None, ge=0)
    total_allowances: Optional[Decimal] = Field(None, ge=0)
    gross_salary: Optional[Decimal] = Field(None, ge=0)
    paye_tax: Optional[Decimal] = Field(None, ge=0)
    ssnit_employee: Optional[Decimal] = Field(None, ge=0)
    tier3_employee: Optional[Decimal] = Field(None, ge=0)
    total_deductions: Optional[Decimal] = Field(None, ge=0)
    net_salary: Optional[Decimal] = None
    notes: Optional[str] = None


class CalculationTriggerResponse(BaseModel):
    """Response from triggering a payroll calculation."""

    task_id: str
    message: str


# ---------------------------------------------------------------------------
# Payroll Approval (Phase 4B)
# ---------------------------------------------------------------------------


class PayrollApprovalRequest(BaseModel):
    """Request to approve or reject a payroll run."""

    comments: Optional[str] = None


class PayrollRejectRequest(BaseModel):
    """Request to reject a payroll run."""

    reason: Optional[str] = None


class PayrollApprovalResponse(BaseModel):
    """Payroll approval record response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payroll_run_id: UUID
    approver_id: UUID
    action: str
    comments: Optional[str] = None
    created_at: datetime

    @field_validator("action", mode="before")
    @classmethod
    def coerce_action(cls, v):
        return v.value if hasattr(v, "value") else v


# ---------------------------------------------------------------------------
# Phase 4C: Payslip, Bank File, Report Schemas
# ---------------------------------------------------------------------------


class PayslipResponse(BaseModel):
    """Response from individual payslip generation."""

    download_url: str
    staff_name: str
    staff_code: str
    month: int
    year: int
    expires_in_seconds: int = 300


class BulkPayslipRequest(BaseModel):
    """Request to trigger bulk payslip generation."""

    # No body fields required; run_id comes from URL path
    pass


class BulkPayslipResponse(BaseModel):
    """Response from bulk payslip generation trigger."""

    task_id: str
    message: str
    staff_count: int


class BankFileResponse(BaseModel):
    """Response from bank file generation."""

    download_url: str
    bank_name: str
    file_format: str
    record_count: int
    total_amount: Decimal
    expires_in_seconds: int = 300


class MonthlySummaryResponse(BaseModel):
    """Monthly payroll summary report."""

    model_config = ConfigDict(from_attributes=True)

    month: int
    year: int
    currency: str = "GHS"
    staff_count: int
    total_basic: Decimal
    total_allowances: Decimal
    total_gross: Decimal
    total_paye: Decimal
    total_ssnit_ee: Decimal
    total_ssnit_er: Decimal
    total_tier2_er: Decimal
    total_tier3: Decimal
    total_other_deductions: Decimal
    total_net: Decimal
    total_employer_cost: Decimal
    by_department: list[dict] = Field(default_factory=list)
    by_payment_method: list[dict] = Field(default_factory=list)


class SSNITReturnItem(BaseModel):
    """Single staff entry in SSNIT returns report."""

    staff_name: str
    staff_code: str
    ssnit_number: Optional[str] = None
    basic_salary: Decimal
    employee_contribution: Decimal
    employer_contribution: Decimal
    tier2_contribution: Decimal
    total_contribution: Decimal


class SSNITReturnResponse(BaseModel):
    """SSNIT returns report."""

    month: int
    year: int
    currency: str = "GHS"
    total_employee: Decimal
    total_employer: Decimal
    total_tier2: Decimal
    grand_total: Decimal
    staff_count: int
    items: list[SSNITReturnItem] = Field(default_factory=list)


class PAYEReturnItem(BaseModel):
    """Single staff entry in PAYE returns report."""

    staff_name: str
    staff_code: str
    tin_number: Optional[str] = None
    gross_salary: Decimal
    taxable_income: Decimal
    paye_tax: Decimal


class PAYEReturnResponse(BaseModel):
    """PAYE tax returns report."""

    month: int
    year: int
    currency: str = "GHS"
    total_taxable: Decimal
    total_paye: Decimal
    staff_count: int
    items: list[PAYEReturnItem] = Field(default_factory=list)


class DepartmentSummaryItem(BaseModel):
    """Single department in payroll cost summary."""

    department_name: str
    staff_count: int
    total_basic: Decimal
    total_gross: Decimal
    total_net: Decimal
    total_employer_cost: Decimal


class DepartmentSummaryResponse(BaseModel):
    """Department-level payroll cost summary."""

    month: int
    year: int
    currency: str = "GHS"
    departments: list[DepartmentSummaryItem] = Field(default_factory=list)


class YearToDateMonthEntry(BaseModel):
    """Single month in YTD breakdown."""

    month: int
    month_name: str
    gross_salary: Decimal
    paye_tax: Decimal
    ssnit_employee: Decimal
    net_salary: Decimal


class YearToDateResponse(BaseModel):
    """Staff year-to-date payroll summary."""

    staff_id: UUID
    staff_name: str
    year: int
    currency: str = "GHS"
    months: list[YearToDateMonthEntry] = Field(default_factory=list)
    total_gross: Decimal
    total_paye: Decimal
    total_ssnit: Decimal
    total_net: Decimal


class AuditLogListResponse(BaseModel):
    """Paginated audit log response."""

    items: list[PayrollAuditLogResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int

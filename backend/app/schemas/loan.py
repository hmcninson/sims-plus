"""
SIMS Plus - Loan Management Schemas

Pydantic v2 schemas for staff loan management: loan types, loan lifecycle,
installments, payments, guarantors, portfolio analytics, and aging reports.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Loan Types
# ---------------------------------------------------------------------------


class LoanTypeCreate(BaseModel):
    """Create a loan type configuration."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20, pattern=r"^[A-Z0-9_]+$")
    description: Optional[str] = None
    default_interest_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    default_interest_method: str = Field(
        default="flat", pattern="^(flat|reducing_balance)$"
    )
    max_amount: Optional[Decimal] = Field(default=None, gt=0)
    max_tenure_months: Optional[int] = Field(default=None, gt=0, le=60)
    max_active_loans: int = Field(default=1, ge=1, le=10)
    requires_guarantor: bool = False
    min_service_months: int = Field(default=0, ge=0)
    max_deduction_pct: Decimal = Field(default=Decimal("50.00"), ge=10, le=100)
    school_id: Optional[UUID] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class LoanTypeUpdate(BaseModel):
    """Update a loan type."""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20, pattern=r"^[A-Z0-9_]+$")
    description: Optional[str] = None
    default_interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    default_interest_method: Optional[str] = Field(
        None, pattern="^(flat|reducing_balance)$"
    )
    max_amount: Optional[Decimal] = Field(None, gt=0)
    max_tenure_months: Optional[int] = Field(None, gt=0, le=60)
    max_active_loans: Optional[int] = Field(None, ge=1, le=10)
    requires_guarantor: Optional[bool] = None
    min_service_months: Optional[int] = Field(None, ge=0)
    max_deduction_pct: Optional[Decimal] = Field(None, ge=10, le=100)
    is_active: Optional[bool] = None

    @field_validator("name", "code")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class LoanTypeResponse(BaseModel):
    """Loan type response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    name: str
    code: str
    description: Optional[str] = None
    default_interest_rate: Decimal
    default_interest_method: str
    max_amount: Optional[Decimal] = None
    max_tenure_months: Optional[int] = None
    max_active_loans: int
    requires_guarantor: bool
    min_service_months: int
    max_deduction_pct: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("default_interest_method", mode="before")
    @classmethod
    def coerce_interest_method(cls, v):
        return v.value if hasattr(v, "value") else v


# ---------------------------------------------------------------------------
# Loan Guarantors
# ---------------------------------------------------------------------------


class LoanGuarantorCreate(BaseModel):
    """Add a guarantor to a loan."""

    guarantor_staff_id: UUID
    relationship: Optional[str] = Field(None, max_length=50)
    guaranteed_amount: Optional[Decimal] = Field(None, gt=0)
    notes: Optional[str] = None


class LoanGuarantorResponse(BaseModel):
    """Loan guarantor response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_id: UUID
    guarantor_staff_id: UUID
    guarantor_staff_name: Optional[str] = None
    relationship: Optional[str] = None
    guaranteed_amount: Optional[Decimal] = None
    consent_given: bool
    consent_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime

    @field_validator("relationship", mode="before")
    @classmethod
    def extract_relationship(cls, v):
        """Handle the mapped column name 'relationship_desc' -> 'relationship'."""
        return v


class LoanGuarantorConsentRequest(BaseModel):
    """Record guarantor consent."""

    consent_given: bool = True
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Loan Installments
# ---------------------------------------------------------------------------


class LoanInstallmentResponse(BaseModel):
    """Loan installment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_id: UUID
    installment_number: int
    due_date: date
    principal_component: Decimal
    interest_component: Decimal
    installment_amount: Decimal
    opening_balance: Decimal
    closing_balance: Decimal
    is_paid: bool
    paid_date: Optional[date] = None
    paid_amount: Optional[Decimal] = None
    payroll_run_id: Optional[UUID] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Loan Payments
# ---------------------------------------------------------------------------


class LoanPaymentResponse(BaseModel):
    """Loan payment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_id: UUID
    payment_number: str
    amount: Decimal
    payment_date: date
    payment_method: str
    reference: Optional[str] = None
    installments_covered: Optional[list] = None
    is_early_repayment: bool
    recorded_by: UUID
    notes: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Loan Create / Update / Response
# ---------------------------------------------------------------------------


class LoanCreate(BaseModel):
    """Create a staff loan (draft)."""

    model_config = ConfigDict(from_attributes=True)

    staff_id: UUID
    loan_type_id: UUID
    principal_amount: Decimal = Field(..., gt=0, le=Decimal("999999.99"))
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    interest_method: Optional[str] = Field(
        None, pattern="^(flat|reducing_balance)$"
    )
    tenure_months: int = Field(..., gt=0, le=60)
    first_deduction_date: date
    purpose: Optional[str] = Field(None, max_length=500)
    guarantor_staff_ids: list[UUID] = Field(default_factory=list)
    school_id: Optional[UUID] = None

    @field_validator("first_deduction_date")
    @classmethod
    def validate_first_deduction_date(cls, v: date) -> date:
        """First deduction date must be the 1st of a month."""
        if v.day != 1:
            raise ValueError("First deduction date must be the 1st of the month")
        return v


class LoanUpdate(BaseModel):
    """Update a draft loan."""

    model_config = ConfigDict(from_attributes=True)

    principal_amount: Optional[Decimal] = Field(None, gt=0, le=Decimal("999999.99"))
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    interest_method: Optional[str] = Field(
        None, pattern="^(flat|reducing_balance)$"
    )
    tenure_months: Optional[int] = Field(None, gt=0, le=60)
    first_deduction_date: Optional[date] = None
    purpose: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    @field_validator("first_deduction_date")
    @classmethod
    def validate_first_deduction_date(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v.day != 1:
            raise ValueError("First deduction date must be the 1st of the month")
        return v


class LoanResponse(BaseModel):
    """Full loan detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    school_id: Optional[UUID] = None
    loan_number: str
    staff_id: UUID
    staff_name: Optional[str] = None
    loan_type: Optional[LoanTypeResponse] = None
    status: str
    principal_amount: Decimal
    interest_rate: Decimal
    interest_method: str
    total_interest: Decimal
    total_repayable: Decimal
    tenure_months: int
    monthly_installment: Decimal
    total_paid: Decimal
    outstanding_balance: Decimal
    installments_paid: int
    installments_remaining: int
    application_date: date
    approval_date: Optional[date] = None
    disbursement_date: Optional[date] = None
    first_deduction_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    actual_completion_date: Optional[date] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    guarantors: list[LoanGuarantorResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else v

    @field_validator("interest_method", mode="before")
    @classmethod
    def coerce_interest_method(cls, v):
        return v.value if hasattr(v, "value") else v


class LoanListItem(BaseModel):
    """Loan summary for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_number: str
    staff_id: UUID
    staff_name: Optional[str] = None
    loan_type_name: Optional[str] = None
    status: str
    principal_amount: Decimal
    total_repayable: Decimal
    total_paid: Decimal
    outstanding_balance: Decimal
    tenure_months: int
    installments_paid: int
    installments_remaining: int
    application_date: date
    first_deduction_date: Optional[date] = None

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else v


class LoanListResponse(BaseModel):
    """Paginated loan list."""

    items: list[LoanListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Loan Operations
# ---------------------------------------------------------------------------


class EarlyRepaymentRequest(BaseModel):
    """Record an early/lump-sum payment."""

    amount: Decimal = Field(..., gt=0)
    payment_date: date
    payment_method: str = Field(
        ..., pattern="^(cash|bank_transfer|mobile_money)$"
    )
    reference: Optional[str] = Field(None, max_length=100)
    is_full_settlement: bool = False
    notes: Optional[str] = None


class LoanRestructureRequest(BaseModel):
    """Restructure a loan with new terms."""

    new_interest_rate: Decimal = Field(..., ge=0, le=100)
    new_interest_method: str = Field(
        ..., pattern="^(flat|reducing_balance)$"
    )
    new_tenure_months: int = Field(..., gt=0, le=60)
    new_first_deduction_date: date
    reason: str = Field(..., min_length=10, max_length=500)

    @field_validator("new_first_deduction_date")
    @classmethod
    def validate_date(cls, v: date) -> date:
        if v.day != 1:
            raise ValueError("First deduction date must be the 1st of the month")
        return v


class LoanWriteOffRequest(BaseModel):
    """Write off remaining loan balance."""

    reason: str = Field(..., min_length=10, max_length=500)


class LoanRejectRequest(BaseModel):
    """Reject a loan with reason."""

    reason: str = Field(..., min_length=5, max_length=500)


class LoanEligibilityResponse(BaseModel):
    """Loan eligibility check result."""

    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    max_eligible_amount: Optional[Decimal] = None
    max_eligible_tenure: Optional[int] = None


# ---------------------------------------------------------------------------
# Portfolio Analytics
# ---------------------------------------------------------------------------


class LoanTypeBreakdown(BaseModel):
    """Breakdown of loans by type for portfolio view."""

    loan_type_id: UUID
    loan_type_name: str
    count: int
    total_principal: Decimal
    total_outstanding: Decimal


class LoanPortfolioResponse(BaseModel):
    """Loan portfolio summary."""

    total_loans: int
    active_loans: int
    total_disbursed: Decimal
    total_outstanding: Decimal
    total_collected: Decimal
    total_written_off: Decimal
    average_loan_amount: Decimal
    by_type: list[LoanTypeBreakdown] = Field(default_factory=list)
    by_status: dict[str, int] = Field(default_factory=dict)
    overdue_count: int
    overdue_amount: Decimal


# ---------------------------------------------------------------------------
# Aging Report
# ---------------------------------------------------------------------------


class LoanAgingBucket(BaseModel):
    """One bucket in the aging report."""

    bucket: str  # "current", "30_days", "60_days", "90_days", "120_plus"
    count: int
    total_amount: Decimal
    loans: list[dict] = Field(default_factory=list)


class LoanAgingResponse(BaseModel):
    """Loan aging report with 30/60/90/120+ day buckets."""

    total_overdue: Decimal
    total_overdue_count: int
    buckets: list[LoanAgingBucket] = Field(default_factory=list)

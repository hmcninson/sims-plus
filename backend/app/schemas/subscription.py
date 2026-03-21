"""
SIMS Plus - Subscription Schemas

Pydantic v2 schemas for subscription management endpoints.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubscriptionStatusResponse(BaseModel):
    """Response for GET /subscription/status."""

    model_config = ConfigDict(from_attributes=True)

    plan: str
    status: str
    trial_ends_at: datetime | None = None
    subscription_start: date | None = None
    subscription_end: date | None = None
    days_remaining: int | None = None
    # Student limits
    max_students: int
    current_student_count: int
    # User account limits
    max_users: int
    current_user_count: int
    # SMS limits
    sms_monthly_limit: int
    sms_sent_this_month: int
    # Features
    features: dict[str, Any] = Field(default_factory=dict)
    available_addons: list[str] = Field(default_factory=list)


class CalculateCostRequest(BaseModel):
    """Request body for POST /subscription/calculate-cost."""

    target_tier: str
    billing_period: str
    addons: list[str] | None = None

    @field_validator("target_tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        if v not in ("starter", "professional", "enterprise"):
            raise ValueError("Target tier must be: starter, professional, or enterprise")
        return v

    @field_validator("billing_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in ("term", "year"):
            raise ValueError("Billing period must be: term or year")
        return v

    @field_validator("addons")
    @classmethod
    def validate_addons(cls, v: list[str] | None) -> list[str] | None:
        valid = ["boarding", "transport", "preschool", "hr_payroll"]
        if v:
            for a in v:
                if a not in valid:
                    raise ValueError(f"Invalid add-on '{a}'. Valid: {valid}")
        return v


class CostBreakdownItem(BaseModel):
    """Single line item in a cost breakdown."""

    description: str | None = None
    name: str | None = None
    amount: int


class CostBreakdownResponse(BaseModel):
    """Response for cost calculation."""

    student_count: int
    billable_students: int
    price_per_student: int
    subtotal: int
    addon_total: int
    total: int
    total_ghs: float
    billing_period: str
    tier: str
    breakdown: list[dict[str, Any]]


class UpgradeRequest(BaseModel):
    """Request body for POST /subscription/upgrade."""

    target_tier: str
    billing_period: str
    callback_url: str = Field(..., max_length=500)
    addons: list[str] | None = None

    @field_validator("target_tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        if v not in ("starter", "professional", "enterprise"):
            raise ValueError("Target tier must be: starter, professional, or enterprise")
        return v

    @field_validator("billing_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in ("term", "year"):
            raise ValueError("Billing period must be: term or year")
        return v

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url_format(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("Callback URL must use HTTP or HTTPS scheme")
        return v


class UpgradeResponse(BaseModel):
    """Response for upgrade/addon initiation."""

    authorization_url: str
    reference: str
    access_code: str
    cost: CostBreakdownResponse


class PurchaseAddonRequest(BaseModel):
    """Request body for POST /subscription/addon."""

    addons: list[str]
    billing_period: str
    callback_url: str = Field(..., max_length=500)

    @field_validator("addons")
    @classmethod
    def validate_addons(cls, v: list[str]) -> list[str]:
        valid = ["boarding", "transport", "preschool", "hr_payroll"]
        if not v:
            raise ValueError("At least one add-on is required")
        for a in v:
            if a not in valid:
                raise ValueError(f"Invalid add-on '{a}'. Valid: {valid}")
        return v

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url_format(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("Callback URL must use HTTP or HTTPS scheme")
        return v

    @field_validator("billing_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in ("term", "year"):
            raise ValueError("Billing period must be: term or year")
        return v

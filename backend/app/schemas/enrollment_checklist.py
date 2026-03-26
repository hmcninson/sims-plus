"""
SIMS Plus - Enrollment Checklist Schemas

Pydantic schemas for enrollment checklist, deposit, boarding status,
confirmation letter, and welcome pack endpoints.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# --- Enums for schema validation ---


class ChecklistItemTypeEnum(str, Enum):
    """Categories for enrollment checklist items."""

    DOCUMENT = "document"
    PAYMENT = "payment"
    FORM = "form"
    BOARDING = "boarding"
    MEDICAL = "medical"


class BoardingStatusEnum(str, Enum):
    """Residential status for enrolled students."""

    BOARDING = "boarding"
    DAY = "day"


# --- Checklist Item Schemas ---


class ChecklistItemResponse(BaseSchema):
    """Single checklist item detail."""

    id: UUID
    checklist_id: UUID
    item_type: str
    item_name: str
    description: str | None = None
    is_required: bool
    is_completed: bool
    completed_at: datetime | None = None
    completed_by: UUID | None = None
    notes: str | None = None
    # REVIEW FIX E4: item_metadata not metadata (avoids SQLAlchemy collision)
    item_metadata: dict[str, Any] | None = None
    created_at: datetime


class ChecklistItemComplete(BaseSchema):
    """Mark a checklist item as completed."""

    notes: str | None = Field(None, max_length=1000)
    item_metadata: dict[str, Any] | None = None


# --- Checklist Schemas ---


class ChecklistResponse(BaseSchema):
    """Full enrollment checklist with items and computed progress fields."""

    id: UUID
    school_id: UUID
    application_id: UUID
    checklist_type: str
    completed_at: datetime | None = None
    completed_by: UUID | None = None
    total_items: int = 0
    completed_items: int = 0
    required_items: int = 0
    required_completed: int = 0
    progress_pct: float = 0.0
    items: list[ChecklistItemResponse] = []
    created_at: datetime
    updated_at: datetime


# --- Enrollment Deposit Schemas ---


class EnrollmentDepositRecord(BaseSchema):
    """Record an enrollment deposit payment (manual entry by admin)."""

    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    reference: str = Field(..., min_length=1, max_length=255)


class EnrollmentDepositResponse(BaseSchema):
    """Deposit recording result."""

    application_id: UUID
    enrollment_deposit_paid: bool
    enrollment_deposit_amount: Decimal | None = None
    enrollment_deposit_reference: str | None = None


# --- Boarding Status Schemas ---


class BoardingStatusAssign(BaseSchema):
    """Assign boarding or day status to an application."""

    boarding_status: BoardingStatusEnum


class BoardingStatusResponse(BaseSchema):
    """Boarding status assignment result."""

    application_id: UUID
    boarding_status: str
    boarding_items_added: int = 0


# --- Confirmation & Welcome Pack ---


class ConfirmationLetterResponse(BaseSchema):
    """Generated enrollment confirmation letter."""

    application_id: UUID
    confirmation_url: str
    applicant_name: str


class WelcomePackResponse(BaseSchema):
    """Welcome pack send result."""

    application_id: UUID
    welcome_pack_sent: bool
    channels: list[str]  # ["email", "sms"]

"""
SIMS Plus - Leave Management Schemas

Pydantic schemas for leave types, balances, and requests.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Leave Type Schemas
# =========================


class LeaveTypeCreate(BaseSchema):
    """Create a leave type."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    default_days_per_year: Decimal = Field(..., ge=0)
    max_carryover_days: Decimal = Field(default=Decimal("0"), ge=0)
    is_paid: bool = True
    requires_approval: bool = True
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class LeaveTypeUpdate(BaseSchema):
    """Update a leave type."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    default_days_per_year: Optional[Decimal] = Field(None, ge=0)
    max_carryover_days: Optional[Decimal] = Field(None, ge=0)
    is_paid: Optional[bool] = None
    requires_approval: Optional[bool] = None
    is_active: Optional[bool] = None
    color: Optional[str] = None


class LeaveTypeResponse(BaseSchema):
    """Leave type response."""

    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    default_days_per_year: Decimal
    max_carryover_days: Decimal
    is_paid: bool
    requires_approval: bool
    is_active: bool
    color: Optional[str] = None
    created_at: datetime


# =========================
# Leave Balance Schemas
# =========================


class LeaveBalanceResponse(BaseSchema):
    """Leave balance response with computed remaining_days."""

    id: UUID
    staff_id: UUID
    staff_name: Optional[str] = None
    leave_type_id: UUID
    leave_type_name: Optional[str] = None
    academic_year_id: UUID
    entitled_days: Decimal
    used_days: Decimal
    pending_days: Decimal
    carried_over: Decimal
    remaining_days: Decimal  # computed: entitled + carried_over - used - pending


class LeaveBalanceAdjust(BaseSchema):
    """Adjust a leave balance (admin override)."""

    entitled_days: Optional[Decimal] = None
    carried_over: Optional[Decimal] = None
    reason: str = Field(..., min_length=3, max_length=500)


class LeaveBalanceInitialize(BaseSchema):
    """Bulk initialize leave balances for an academic year."""

    academic_year_id: UUID
    carry_over_from_previous: bool = False


# =========================
# Leave Request Schemas
# =========================


class LeaveRequestCreate(BaseSchema):
    """Submit a leave request. days_requested is calculated server-side."""

    leave_type_id: UUID
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=5, max_length=2000)


class LeaveRequestUpdate(BaseSchema):
    """Update a pending leave request (before approval)."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason: Optional[str] = Field(None, min_length=5, max_length=2000)


class LeaveRequestResponse(BaseSchema):
    """Leave request response."""

    id: UUID
    staff_id: UUID
    staff_name: Optional[str] = None
    leave_type_id: UUID
    leave_type_name: Optional[str] = None
    leave_type_color: Optional[str] = None
    start_date: date
    end_date: date
    days_requested: Decimal
    reason: str
    status: str
    reviewed_by: Optional[UUID] = None
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime


class LeaveApprovalRequest(BaseSchema):
    """Approve or reject a leave request."""

    notes: Optional[str] = Field(None, max_length=1000)


class LeaveCalendarEntry(BaseSchema):
    """Leave calendar entry for calendar view."""

    staff_id: UUID
    staff_name: str
    leave_type_name: str
    leave_type_color: Optional[str] = None
    start_date: date
    end_date: date
    days: Decimal
    status: str

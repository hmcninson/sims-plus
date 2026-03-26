"""
SIMS Plus - Preschool Extended Care Schemas

Pydantic schemas for extended care sessions, billing summaries,
and caregiver ratio management.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated
from uuid import UUID as StdUUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.preschool.core import BaseSchema

# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Extended Care Schemas
# =========================


class ExtendedCareCheckInRequest(BaseSchema):
    """Schema for checking a student into extended care."""

    student_id: UUID
    session_type: Annotated[str, Field(pattern=r"^(before_care|after_care)$")]
    notes: Annotated[str | None, Field(max_length=2000)] = None


class ExtendedCareCheckOutRequest(BaseSchema):
    """Schema for checking a student out of extended care."""

    notes: Annotated[str | None, Field(max_length=2000)] = None


class ExtendedCareSessionResponse(BaseSchema):
    """Schema for extended care session response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    student_id: UUID
    session_date: date
    session_type: str
    check_in_time: time
    check_out_time: time | None = None
    duration_minutes: int | None = None
    checked_in_by: UUID | None = None
    checked_out_by: UUID | None = None
    notes: str | None = None
    created_at: datetime


class ExtendedCareBillingSummary(BaseSchema):
    """Billing summary for extended care per student."""

    student_id: UUID
    student_name: str
    total_sessions: int
    total_minutes: int
    total_hours: Decimal
    rate_per_hour: Decimal | None = None
    flat_rate: Decimal | None = None
    estimated_charge: Decimal


# =========================
# Caregiver Ratio Schemas
# =========================


class CaregiverRatioSet(BaseSchema):
    """Schema for setting caregiver ratio."""

    max_children_per_caregiver: Annotated[int, Field(ge=1, le=50)]
    current_caregiver_count: Annotated[int, Field(ge=0, le=100)]


class CaregiverRatioResponse(BaseSchema):
    """Schema for caregiver ratio response with compliance info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    class_id: UUID
    academic_year_id: UUID
    max_children_per_caregiver: int
    current_caregiver_count: int
    max_capacity: int
    current_enrollment: int
    is_compliant: bool

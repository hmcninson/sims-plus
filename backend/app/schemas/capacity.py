"""
SIMS Plus - Capacity Planning Schemas

Pydantic schemas for enrollment target and capacity dashboard endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Enrollment Target Schemas ---


class EnrollmentTargetCreate(BaseSchema):
    """Set enrollment target for a class/year (upsert semantics)."""

    academic_year_id: UUID
    class_id: UUID
    target_count: int = Field(..., ge=0)
    boarding_target: int | None = Field(None, ge=0)
    day_target: int | None = Field(None, ge=0)


class EnrollmentTargetResponse(BaseSchema):
    """Full enrollment target response."""

    id: UUID
    school_id: UUID
    academic_year_id: UUID
    class_id: UUID
    class_name: str | None = None
    target_count: int
    boarding_target: int | None
    day_target: int | None
    created_at: datetime
    updated_at: datetime


class EnrollmentTargetListResponse(BaseSchema):
    """List of targets for a year."""

    items: list[EnrollmentTargetResponse]
    academic_year_id: UUID


# --- Capacity Dashboard Schemas ---


class ClassCapacityRow(BaseSchema):
    """Per-class capacity breakdown in the dashboard."""

    class_id: UUID
    class_name: str
    capacity: int | None  # From Class model (physical capacity)
    target: int | None  # From EnrollmentTarget
    boarding_target: int | None
    day_target: int | None
    current_enrolled: int  # Count of active students
    applications_in_pipeline: int  # Non-terminal applications
    utilization_pct: float  # current_enrolled / capacity * 100


class CapacityDashboardResponse(BaseSchema):
    """Full capacity dashboard for a school/year."""

    academic_year_id: UUID
    school_id: UUID
    total_capacity: int | None
    total_target: int | None
    total_enrolled: int
    total_pipeline: int
    classes: list[ClassCapacityRow]


# --- Capacity Check Schema ---


class CapacityCheckResponse(BaseSchema):
    """Quick capacity check for a single class."""

    class_id: UUID
    class_name: str | None = None
    capacity: int | None
    current_enrolled: int
    remaining: int | None  # None if capacity is unlimited
    is_full: bool

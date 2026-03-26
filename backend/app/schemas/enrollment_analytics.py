"""
SIMS Plus - Admissions Analytics Schemas

Pydantic schemas for enrollment funnel, trends, and analytics endpoints.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Funnel ---


class FunnelStageResponse(BaseSchema):
    """Single stage in the admissions funnel."""

    stage: str
    count: int
    conversion_rate: float | None  # Percentage of previous stage


class FunnelResponse(BaseSchema):
    """Full admissions funnel from inquiry to enrollment."""

    school_id: UUID
    period_id: UUID | None
    stages: list[FunnelStageResponse]


# --- Trends ---


class YearClassCount(BaseSchema):
    """Enrollment count for a single class in a year."""

    class_id: UUID
    class_name: str
    count: int


class YearTrendRow(BaseSchema):
    """One academic year's enrollment data."""

    academic_year_id: UUID
    academic_year_name: str
    total_enrolled: int
    by_class: list[YearClassCount]


class TrendsResponse(BaseSchema):
    """Year-over-year enrollment trends."""

    school_id: UUID
    years: list[YearTrendRow]


# --- Lead Source Effectiveness ---


class SourceEffectivenessRow(BaseSchema):
    """Conversion metrics for a single lead source."""

    source: str
    inquiry_count: int
    application_count: int
    enrollment_count: int
    inquiry_to_application_rate: float
    inquiry_to_enrollment_rate: float


class SourceEffectivenessResponse(BaseSchema):
    school_id: UUID
    period_id: UUID | None
    sources: list[SourceEffectivenessRow]


# --- Re-enrollment ---


class ReEnrollmentYearRow(BaseSchema):
    """Re-enrollment rate for one academic year."""

    academic_year_id: UUID
    academic_year_name: str
    total_students: int
    returning_count: int
    re_enrollment_rate: float


class ReEnrollmentResponse(BaseSchema):
    school_id: UUID
    years: list[ReEnrollmentYearRow]


# --- Attrition ---


class AttritionReasonRow(BaseSchema):
    """Count of students lost for a given reason."""

    reason: str
    count: int


class AttritionResponse(BaseSchema):
    school_id: UUID
    academic_year_id: UUID | None
    withdrawn_count: int
    not_returning_count: int
    total_attrition: int
    withdrawal_reasons: list[AttritionReasonRow]
    not_returning_reasons: list[AttritionReasonRow]


# --- Enrollment vs Capacity ---


class EnrollmentVsCapacityRow(BaseSchema):
    """Per-class comparison of target, actual, and capacity."""

    class_id: UUID
    class_name: str
    target: int | None
    actual_enrolled: int
    capacity: int | None
    variance: int | None  # actual - target (positive = over target)
    fill_pct: float | None  # actual / capacity * 100


class EnrollmentVsCapacityResponse(BaseSchema):
    school_id: UUID
    academic_year_id: UUID
    classes: list[EnrollmentVsCapacityRow]
    total_target: int | None
    total_enrolled: int
    total_capacity: int | None


# --- Re-enrollment Confirmation Summary ---


class ReEnrollmentSummaryResponse(BaseSchema):
    """Summary for a return intent campaign's re-enrollment confirmations."""

    campaign_id: UUID
    total_intents: int
    confirmed_count: int
    pending_count: int
    not_returning_count: int
    undecided_count: int
    total_outstanding_fees: float
    by_class: list[dict]  # [{class_name, confirmed, pending, not_returning}]

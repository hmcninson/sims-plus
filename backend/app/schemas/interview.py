"""
SIMS Plus - Interview & Screening Schemas

Pydantic v2 schemas for interview scheduling, feedback recording,
and screening checklist management endpoints.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# =========================
# Interview Schemas
# =========================


class InterviewCreate(BaseSchema):
    """Schedule an interview for an application."""

    application_id: UUID
    interviewer_id: UUID
    scheduled_date: date
    scheduled_time: time | None = None
    duration_minutes: int = Field(30, ge=10, le=180)
    venue: str = Field(..., min_length=1, max_length=255)


class InterviewUpdate(BaseSchema):
    """Reschedule or update interview details."""

    scheduled_date: date | None = None
    scheduled_time: time | None = None
    duration_minutes: int | None = Field(None, ge=10, le=180)
    venue: str | None = Field(None, min_length=1, max_length=255)
    interviewer_id: UUID | None = None


class InterviewFeedback(BaseSchema):
    """Record interview outcome and scoring."""

    status: str = Field(..., pattern=r"^(completed|no_show)$")
    feedback: str | None = Field(None, max_length=5000)
    score: Decimal | None = Field(None, ge=0)
    max_score: Decimal | None = Field(None, ge=0)
    scoring_criteria: dict[str, Any] | None = None

    @field_validator("scoring_criteria")
    @classmethod
    def validate_scoring_criteria(
        cls, v: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Validate scoring_criteria structure: each value must have score >= 0, max > 0, score <= max."""
        if v is None:
            return v
        for criterion, values in v.items():
            if not isinstance(values, dict):
                raise ValueError(
                    f"Criterion '{criterion}' must be a dict with 'score' and 'max' keys"
                )
            if "score" not in values or "max" not in values:
                raise ValueError(
                    f"Criterion '{criterion}' must have 'score' and 'max' keys"
                )
            score_val = values["score"]
            max_val = values["max"]
            if not isinstance(score_val, (int, float)):
                raise ValueError(
                    f"Criterion '{criterion}' score must be numeric"
                )
            if not isinstance(max_val, (int, float)):
                raise ValueError(
                    f"Criterion '{criterion}' max must be numeric"
                )
            if score_val < 0:
                raise ValueError(
                    f"Criterion '{criterion}' score must be >= 0"
                )
            if max_val <= 0:
                raise ValueError(
                    f"Criterion '{criterion}' max must be > 0"
                )
            if score_val > max_val:
                raise ValueError(
                    f"Criterion '{criterion}' score ({score_val}) exceeds max ({max_val})"
                )
        return v

    @field_validator("max_score")
    @classmethod
    def max_score_required_with_score(
        cls, v: Decimal | None, info
    ) -> Decimal | None:
        """If score is provided, max_score must also be provided."""
        score = info.data.get("score")
        if score is not None and v is None:
            raise ValueError("max_score is required when score is provided")
        if v is not None and score is not None and score > v:
            raise ValueError("score cannot exceed max_score")
        return v


class InterviewResponse(BaseSchema):
    """Full interview detail response."""

    id: UUID
    school_id: UUID
    application_id: UUID
    interviewer_id: UUID | None
    interviewer_name: str | None = None
    applicant_name: str | None = None
    scheduled_date: date
    scheduled_time: time | None
    duration_minutes: int
    venue: str
    status: str
    feedback: str | None
    score: Decimal | None
    max_score: Decimal | None
    scoring_criteria: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InterviewListResponse(BaseSchema):
    """Paginated interview list."""

    items: list[InterviewResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Screening Checklist Schemas
# =========================


class ScreeningItemCreate(BaseSchema):
    """Add a screening checklist item."""

    item_name: str = Field(..., min_length=1, max_length=255)
    item_category: str = Field(
        ..., pattern=r"^(documents|academic|medical|other)$"
    )


class ScreeningItemBulkCreate(BaseSchema):
    """Bulk-add screening items (apply template)."""

    items: list[ScreeningItemCreate] = Field(..., max_length=50)


class ScreeningItemComplete(BaseSchema):
    """Mark a screening item as completed."""

    notes: str | None = None


class ScreeningItemResponse(BaseSchema):
    """Screening checklist item detail."""

    id: UUID
    application_id: UUID
    item_name: str
    item_category: str
    is_completed: bool
    completed_by: UUID | None
    completed_by_name: str | None = None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime


class ScreeningProgressResponse(BaseSchema):
    """Screening progress summary for an application."""

    application_id: UUID
    total_items: int
    completed_items: int
    progress_pct: float
    items: list[ScreeningItemResponse]

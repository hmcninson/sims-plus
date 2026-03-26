"""
SIMS Plus - Preschool Report Schemas

Pydantic schemas for preschool reports.
"""

from datetime import datetime
from uuid import UUID as StdUUID

from pydantic import BaseModel

from app.schemas.preschool.core import BaseSchema

# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Preschool Report Schemas
# =========================


class LearningAreaSummary(BaseModel):
    """Summary for a learning area in a report."""

    learning_area_id: UUID
    learning_area_name: str
    rating: str  # Overall rating (e.g., "proficient")
    summary: str | None = None


class PreschoolReportBase(BaseSchema):
    """Base schema for preschool reports."""

    days_present: int | None = None
    days_absent: int | None = None
    total_school_days: int | None = None
    overall_progress: str | None = None
    strengths: str | None = None
    areas_for_growth: str | None = None
    teacher_recommendations: str | None = None
    highlights: list[str] | None = None
    next_term_goals: list[str] | None = None
    class_teacher_remark: str | None = None
    head_teacher_remark: str | None = None


class PreschoolReportCreate(PreschoolReportBase):
    """Schema for creating a preschool report."""

    student_id: UUID
    academic_year_id: UUID
    term_id: UUID
    class_id: UUID
    learning_area_summaries: list[LearningAreaSummary] | None = None
    report_type: str = "term"  # term, interim, progress_update
    photo_urls: list[dict] | None = None  # [{url, caption}]


class PreschoolReportUpdate(BaseModel):
    """Schema for updating a preschool report."""

    days_present: int | None = None
    days_absent: int | None = None
    total_school_days: int | None = None
    learning_area_summaries: list[LearningAreaSummary] | None = None
    overall_progress: str | None = None
    strengths: str | None = None
    areas_for_growth: str | None = None
    teacher_recommendations: str | None = None
    highlights: list[str] | None = None
    next_term_goals: list[str] | None = None
    class_teacher_remark: str | None = None
    head_teacher_remark: str | None = None
    photo_urls: list[dict] | None = None
    chart_data: dict | None = None


class PreschoolReportResponse(PreschoolReportBase):
    """Schema for preschool report response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    academic_year_id: UUID
    term_id: UUID
    class_id: UUID
    learning_area_summaries: list[LearningAreaSummary] | None = None
    is_published: bool
    published_at: datetime | None = None
    report_type: str = "term"
    photo_urls: list[dict] | None = None
    chart_data: dict | None = None
    created_at: datetime
    updated_at: datetime



class PreschoolReportGenerateRequest(BaseModel):
    """Request to generate reports for a class."""

    class_id: UUID
    academic_year_id: UUID
    term_id: UUID
    report_type: str = "term"  # term, interim, progress_update


class PreschoolReportPublishRequest(BaseModel):
    """Request to publish reports."""

    report_ids: list[UUID]

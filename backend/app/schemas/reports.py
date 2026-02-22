"""
SIMS Plus - Report Schemas

Pydantic schemas for report generation.
"""

from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class ReportFormat(str, Enum):
    """Supported report output formats."""
    PDF = "pdf"


class FinancialReportType(str, Enum):
    """Types of financial reports."""
    FEE_COLLECTION = "fee_collection"
    OUTSTANDING_FEES = "outstanding_fees"
    PAYMENT_SUMMARY = "payment_summary"


class FinancialReportRequest(BaseSchema):
    """Request to generate a financial report."""

    report_type: FinancialReportType
    academic_year_id: UUID
    term_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    format: ReportFormat = ReportFormat.PDF


class AttendanceReportRequest(BaseSchema):
    """Request to generate an attendance report."""

    class_id: UUID
    section_id: Optional[UUID] = None
    date_from: date
    date_to: date
    format: ReportFormat = ReportFormat.PDF


class ReportGenerationResponse(BaseSchema):
    """Response after report generation (metadata only, PDF is streamed)."""

    report_type: str
    generated_at: str
    filters: dict

"""
SIMS Plus - CSSPS Import Schemas

Pydantic schemas for CSSPS (Computerised School Selection and Placement System)
placement data import. CSSPS places JHS graduates into SHS.

See spec/enrollment-gap-closure/00-overview.md Section 5 for the file format definition.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Column Mapping ---


class CSSPSColumnMapping(BaseSchema):
    """
    Maps file column headers to standard CSSPS fields.

    Keys are our standard field names; values are the actual column
    headers in the uploaded file. Only mapped columns are extracted.
    """

    index_number: str = Field(
        "index_number", description="Column header for BECE index number"
    )
    first_name: str = Field("first_name", description="Column header for first name")
    last_name: str = Field("last_name", description="Column header for last name")
    other_names: str | None = Field(
        None, description="Column header for middle/other names"
    )
    gender: str = Field("gender", description="Column header for gender (M/F)")
    date_of_birth: str | None = Field(
        None, description="Column header for date of birth"
    )
    programme: str = Field(
        "programme", description="Column header for SHS programme"
    )
    aggregate: str | None = Field(
        None, description="Column header for BECE aggregate"
    )
    jhs_school: str | None = Field(
        None, description="Column header for previous JHS"
    )
    jhs_district: str | None = Field(
        None, description="Column header for JHS district"
    )
    region: str | None = Field(None, description="Column header for home region")
    parent_name: str | None = Field(
        None, description="Column header for parent name"
    )
    parent_phone: str | None = Field(
        None, description="Column header for parent phone"
    )
    residential_status: str | None = Field(
        None, description="Column header for boarding/day status"
    )
    house: str | None = Field(
        None, description="Column header for assigned house"
    )


# --- Preview Request/Response ---


class CSSPSPreviewRequest(BaseSchema):
    """Request body for CSSPS file preview (parse without DB writes)."""

    column_mapping: CSSPSColumnMapping = Field(default_factory=CSSPSColumnMapping)


class CSSPSPreviewRow(BaseSchema):
    """Single parsed row in preview."""

    row_number: int
    index_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    other_names: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    programme: str | None = None
    aggregate: int | None = None
    jhs_school: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    residential_status: str | None = None
    house: str | None = None
    errors: list[str] = []


class CSSPSPreviewResponse(BaseSchema):
    """Preview result -- parsed rows without DB writes."""

    total_rows: int
    valid_rows: int
    error_rows: int
    detected_columns: list[str]
    rows: list[CSSPSPreviewRow]


# --- Import Request/Response ---


class CSSPSImportRequest(BaseSchema):
    """
    Request body for CSSPS placement import.

    column_mapping: maps file headers to standard fields.
    programme_to_class_mapping: maps programme names to class UUIDs.
    """

    admission_period_id: UUID
    column_mapping: CSSPSColumnMapping = Field(default_factory=CSSPSColumnMapping)
    programme_to_class_mapping: dict[str, UUID] = Field(
        ...,
        description="Maps programme names to class UUIDs",
        min_length=1,
    )


class CSSPSImportResult(BaseSchema):
    """Single row import result."""

    row_number: int
    index_number: str
    status: str  # "imported", "skipped", "error"
    application_id: UUID | None = None
    error: str | None = None


class CSSPSImportResponse(BaseSchema):
    """Full import result summary."""

    total_rows: int
    imported: int
    skipped: int
    errors: int
    results: list[CSSPSImportResult]

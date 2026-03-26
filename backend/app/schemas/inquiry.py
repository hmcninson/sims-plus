"""
SIMS Plus - Inquiry Schemas (Enrollment Gap Closure Phase 1)

Pydantic v2 schemas for inquiry/lead management endpoints.
Covers: inquiries, communications, follow-ups, bulk import, duplicate check, stats.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Schema-Level Enums
# =========================


class InquirySourceEnum(str, Enum):
    """How the inquiry reached the school."""

    WEBSITE = "website"
    WALK_IN = "walk_in"
    PHONE = "phone"
    REFERRAL = "referral"
    EVENT = "event"
    SOCIAL_MEDIA = "social_media"
    OTHER = "other"


class InquiryStatusEnum(str, Enum):
    """Lead progression workflow."""

    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    APPLIED = "applied"
    ENROLLED = "enrolled"
    LOST = "lost"


class CommunicationChannelEnum(str, Enum):
    """Communication channel type."""

    SMS = "sms"
    EMAIL = "email"
    PHONE = "phone"
    IN_PERSON = "in_person"


class CommunicationDirectionEnum(str, Enum):
    """Communication direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class FollowUpPriorityEnum(str, Enum):
    """Follow-up task priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =========================
# Inquiry Schemas
# =========================


class InquiryCreate(BaseSchema):
    """Create a new inquiry/lead."""

    source: InquirySourceEnum
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    target_class_id: Optional[UUID] = None
    guardian_name: str = Field(..., min_length=1, max_length=200)
    guardian_phone: str = Field(..., min_length=1, max_length=20)
    guardian_email: Optional[EmailStr] = None
    referred_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None

    @field_validator("first_name", "last_name", "guardian_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if v not in ("male", "female"):
                raise ValueError("gender must be 'male' or 'female'")
        return v


class InquiryUpdate(BaseSchema):
    """Update an existing inquiry. All fields optional."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    target_class_id: Optional[UUID] = None
    guardian_name: Optional[str] = Field(None, min_length=1, max_length=200)
    guardian_phone: Optional[str] = Field(None, min_length=1, max_length=20)
    guardian_email: Optional[EmailStr] = None
    referred_by: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if v not in ("male", "female"):
                raise ValueError("gender must be 'male' or 'female'")
        return v


class InquiryStatusUpdate(BaseSchema):
    """Update inquiry status."""

    status: InquiryStatusEnum


class InquiryAssign(BaseSchema):
    """Assign inquiry to a staff member."""

    assigned_to: UUID


class InquiryConvert(BaseSchema):
    """Convert inquiry to a formal application."""

    period_id: UUID


class InquiryResponse(BaseSchema):
    """Full inquiry response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    source: str
    status: str
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    target_class_id: Optional[UUID] = None
    guardian_name: str
    guardian_phone: str
    guardian_email: Optional[str] = None
    assigned_to: Optional[UUID] = None
    referred_by: Optional[str] = None
    notes: Optional[str] = None
    converted_application_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class InquiryListResponse(BaseSchema):
    """Paginated inquiry list."""

    items: list[InquiryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class InquiryStatsResponse(BaseSchema):
    """Inquiry pipeline statistics."""

    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    conversion_rate: float


# =========================
# Communication Schemas
# =========================


class CommunicationCreate(BaseSchema):
    """Log a communication with an inquiry contact."""

    channel: CommunicationChannelEnum
    direction: CommunicationDirectionEnum
    content: str = Field(..., min_length=1, max_length=2000)


class CommunicationResponse(BaseSchema):
    """Communication log entry response."""

    id: UUID
    inquiry_id: UUID
    channel: str
    direction: str
    content: str
    sent_by: Optional[UUID] = None
    sent_at: datetime
    created_at: datetime


# =========================
# Follow-Up Schemas
# =========================


class FollowUpCreate(BaseSchema):
    """Create a follow-up task for an inquiry."""

    due_date: date
    priority: FollowUpPriorityEnum = FollowUpPriorityEnum.MEDIUM
    notes: Optional[str] = None
    assigned_to: UUID


class FollowUpResponse(BaseSchema):
    """Follow-up task response."""

    id: UUID
    inquiry_id: UUID
    assigned_to: UUID
    due_date: date
    priority: str
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


# =========================
# Bulk Import Schemas
# =========================


class BulkInquiryImportRow(BaseSchema):
    """Single row for bulk inquiry import."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    guardian_name: str = Field(..., min_length=1, max_length=200)
    guardian_phone: str = Field(..., min_length=1, max_length=20)
    guardian_email: Optional[EmailStr] = None
    source: Optional[InquirySourceEnum] = None
    notes: Optional[str] = None


class BulkImportRequest(BaseSchema):
    """Bulk import request body."""

    rows: list[BulkInquiryImportRow] = Field(..., min_length=1, max_length=200)


class BulkImportResponse(BaseSchema):
    """Bulk import result."""

    imported: int
    skipped: int
    errors: list[dict]


# =========================
# Duplicate Check Schemas
# =========================


class DuplicateCheckResponse(BaseSchema):
    """Duplicate check result."""

    has_duplicates: bool
    matches: list[InquiryResponse]

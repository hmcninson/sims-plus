"""
SIMS Plus - Messaging Schemas

Pydantic schemas for SMS and email messaging endpoints:
send, bulk send, history, stats, and recipient resolution.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===========================
# Shared Enums
# ===========================


class RecipientType(str, Enum):
    """Audience segment for bulk messaging."""

    ALL_PARENTS = "all_parents"
    ALL_STAFF = "all_staff"
    CLASS_PARENTS = "class_parents"
    SPECIFIC = "specific"


# ===========================
# SMS Schemas
# ===========================


class SMSSendRequest(BaseModel):
    """Send SMS to one or more specific phone numbers."""

    recipient_phones: list[str] = Field(
        ..., min_length=1, max_length=100, description="List of phone numbers"
    )
    message: str = Field(..., min_length=1, max_length=918, description="SMS message body")

    @field_validator("recipient_phones")
    @classmethod
    def validate_phones(cls, v: list[str]) -> list[str]:
        cleaned = []
        for phone in v:
            phone = phone.strip().replace(" ", "")
            if not phone:
                continue
            # Accept numbers starting with + or country code digits
            if not (phone.startswith("+") or phone[0].isdigit()):
                raise ValueError(f"Invalid phone number format: {phone}")
            cleaned.append(phone)
        if not cleaned:
            raise ValueError("At least one valid phone number is required")
        return cleaned


class SMSBulkRequest(BaseModel):
    """Send SMS to an audience segment."""

    audience: RecipientType = Field(..., description="Target audience")
    class_id: UUID | None = Field(
        default=None,
        description="Required when audience is class_parents",
    )
    message: str = Field(..., min_length=1, max_length=918, description="SMS message body")

    @field_validator("class_id")
    @classmethod
    def validate_class_id_for_class_parents(cls, v: UUID | None, info) -> UUID | None:
        # Validation that class_id is required for class_parents is done at the service layer
        # because Pydantic model_validator with mode="after" needs special handling
        return v


class SMSLogResponse(BaseModel):
    """Single SMS log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_phone: str
    message: str
    provider: str
    status: str
    external_id: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


class SMSHistoryResponse(BaseModel):
    """Paginated SMS history."""

    items: list[SMSLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SMSStatsResponse(BaseModel):
    """SMS delivery statistics."""

    total_sent: int = 0
    total_failed: int = 0
    total_pending: int = 0
    total_delivered: int = 0
    credits_used: int = Field(
        default=0,
        description="Approximate SMS credits consumed (1 credit per 160-char segment)",
    )


# ===========================
# Email Schemas
# ===========================


class EmailSendRequest(BaseModel):
    """Send email to one or more specific addresses."""

    recipient_emails: list[str] = Field(
        ..., min_length=1, max_length=100, description="List of email addresses"
    )
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000, description="HTML or plain text body")
    recipient_names: list[str] | None = Field(
        default=None,
        description="Optional names matching recipient_emails order",
    )

    @field_validator("recipient_emails")
    @classmethod
    def validate_emails(cls, v: list[str]) -> list[str]:
        cleaned = []
        for email in v:
            email = email.strip().lower()
            if not email:
                continue
            # Basic email format check (full validation happens at SMTP level)
            if "@" not in email or "." not in email.split("@")[-1]:
                raise ValueError(f"Invalid email format: {email}")
            cleaned.append(email)
        if not cleaned:
            raise ValueError("At least one valid email address is required")
        return cleaned


class EmailBulkRequest(BaseModel):
    """Send email to an audience segment."""

    audience: RecipientType = Field(..., description="Target audience")
    class_id: UUID | None = Field(
        default=None,
        description="Required when audience is class_parents",
    )
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000, description="HTML or plain text body")


class EmailLogResponse(BaseModel):
    """Single email log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_email: str
    recipient_name: str | None = None
    subject: str
    status: str
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


class EmailHistoryResponse(BaseModel):
    """Paginated email history."""

    items: list[EmailLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmailStatsResponse(BaseModel):
    """Email delivery statistics."""

    total_sent: int = 0
    total_failed: int = 0
    total_pending: int = 0
    total_delivered: int = 0
    total_bounced: int = 0


# ===========================
# Recipient Schemas
# ===========================


class RecipientInfo(BaseModel):
    """A resolved recipient with contact details."""

    name: str
    email: str | None = None
    phone: str | None = None
    type: str = Field(description="Recipient category: parent, staff, etc.")


class RecipientListResponse(BaseModel):
    """Resolved list of recipients for a given audience."""

    recipients: list[RecipientInfo]
    total: int

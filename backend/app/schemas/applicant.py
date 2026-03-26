"""
SIMS Plus - Applicant Account Schemas

Pydantic schemas for applicant account endpoints.
Covers: registration, login, profile management, my applications,
draft save/submit, application claiming, and printable views.
"""

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.admissions import (
    AdmissionDecisionResponse,
    ApplicationDocumentResponse,
    ApplicationGuardianResponse,
    ApplicationPaymentResponse,
    StatusHistoryResponse,
)


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


def _validate_password_strength(v: str) -> str:
    """Shared password strength validator for applicant schemas."""
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[^a-zA-Z0-9]", v):
        raise ValueError("Password must contain at least one special character")
    return v


# =========================
# Registration & Auth
# =========================


class ApplicantRegisterRequest(BaseSchema):
    """Create a new applicant account."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8)
    turnstile_token: str = Field(..., min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class ApplicantRegisterResponse(BaseSchema):
    """Response after successful applicant registration."""

    user_id: UUID
    email: str
    message: str = "Account created. Please check your email to verify."


class ApplicantLoginRequest(BaseSchema):
    """Applicant login request."""

    email: EmailStr
    password: str
    turnstile_token: Optional[str] = None  # Required after 3 failed attempts


class ApplicantLoginResponse(BaseSchema):
    """Response after successful applicant login."""

    access_token: str
    refresh_token: str
    user: "ApplicantProfileResponse"
    token_type: str = "bearer"


class ApplicantProfileResponse(BaseSchema):
    """Applicant profile data."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email_verified: bool
    created_at: datetime


class ApplicantProfileUpdate(BaseSchema):
    """Update applicant profile. All fields optional for partial update."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)


class ApplicantPasswordChange(BaseSchema):
    """Change applicant password (requires current password)."""

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class ApplicantForgotPasswordRequest(BaseSchema):
    """Request a password reset email."""

    email: EmailStr
    turnstile_token: str = Field(..., min_length=1)


class ApplicantResetPasswordRequest(BaseSchema):
    """Reset password using token from email."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class ApplicantVerifyEmailRequest(BaseSchema):
    """Verify email using token from verification link."""

    token: str = Field(..., min_length=1)


class ApplicantResendVerificationRequest(BaseSchema):
    """Resend email verification to applicant."""

    email: EmailStr
    turnstile_token: str = Field(..., min_length=1)


# =========================
# My Applications
# =========================


class GuardianPrefillResponse(BaseSchema):
    """Guardian data for pre-filling new application forms."""

    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    relationship: str
    is_primary: bool
    occupation: Optional[str] = None
    address: Optional[str] = None


class MyApplicationListItem(BaseSchema):
    """Lightweight application item for dashboard list view."""

    id: UUID
    tracking_code: str
    admission_period_id: UUID  # Needed by frontend to build "Continue" link for drafts
    applicant_first_name: str
    applicant_last_name: str
    target_class_name: Optional[str] = None
    admission_period_name: Optional[str] = None
    status: str
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MyApplicationListResponse(BaseSchema):
    """Paginated list of applicant's own applications."""

    items: list[MyApplicationListItem]
    total: int
    page: int
    page_size: int
    pages: int


class MyApplicationDetailResponse(BaseSchema):
    """Full application detail for applicant view."""
    id: UUID
    tenant_id: UUID
    tracking_code: str
    admission_period_id: UUID
    admission_period_name: Optional[str] = None
    applicant_first_name: str
    applicant_last_name: str
    applicant_other_names: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    target_class_id: Optional[UUID] = None
    target_class_name: Optional[str] = None
    status: str
    custom_fields: dict[str, Any] = {}
    fee_waived: bool
    exam_waived: bool
    applicant_photo_url: Optional[str] = None
    previous_school: Optional[str] = None
    medical_info: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Nested relations (typed to match admin ApplicationResponse schemas)
    guardians: list[ApplicationGuardianResponse] = []
    documents: list[ApplicationDocumentResponse] = []
    payments: list[ApplicationPaymentResponse] = []
    status_history: list[StatusHistoryResponse] = []
    decision: Optional[AdmissionDecisionResponse] = None


# =========================
# Draft Application
# =========================


class DraftGuardianData(BaseSchema):
    """Guardian info for draft save. Same as ApplicationGuardianSubmit but all optional."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    relationship: Optional[str] = Field(
        None, pattern="^(father|mother|guardian|other)$"
    )
    is_primary: bool = False
    occupation: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None


class DraftApplicationCreate(BaseSchema):
    """
    Create a new draft application.

    Only admission_period_id and child's name are required to start a draft.
    All other fields can be populated later via update.
    """

    admission_period_id: UUID
    applicant_first_name: str = Field(..., min_length=1, max_length=100)
    applicant_last_name: str = Field(..., min_length=1, max_length=100)
    applicant_other_names: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    nationality: Optional[str] = Field(None, max_length=100)
    target_class_id: Optional[UUID] = None
    previous_school: Optional[str] = Field(None, max_length=255)
    medical_info: Optional[str] = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    guardians: Optional[list[DraftGuardianData]] = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date | None) -> date | None:
        if v is not None:
            from datetime import date as date_cls

            if v > date_cls.today():
                raise ValueError("Date of birth cannot be in the future")
        return v


class DraftApplicationUpdate(BaseSchema):
    """
    Update an existing draft application.

    All fields optional for partial save (auto-save on each wizard step).
    """

    applicant_first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    applicant_last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    applicant_other_names: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    nationality: Optional[str] = Field(None, max_length=100)
    target_class_id: Optional[UUID] = None
    previous_school: Optional[str] = Field(None, max_length=255)
    medical_info: Optional[str] = None
    custom_fields: Optional[dict[str, Any]] = None
    guardians: Optional[list[DraftGuardianData]] = None

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date | None) -> date | None:
        if v is not None:
            from datetime import date as date_cls

            if v > date_cls.today():
                raise ValueError("Date of birth cannot be in the future")
        return v


class DraftSubmitResponse(BaseSchema):
    """Response after submitting a draft application."""

    id: UUID
    tracking_code: str
    status: str
    payment_required: bool
    application_fee_amount: Optional[Decimal] = None


# =========================
# Claim Application
# =========================


class ClaimApplicationRequest(BaseSchema):
    """Claim an anonymous application by tracking code."""

    tracking_code: str = Field(..., min_length=1, max_length=100)


class ClaimApplicationResponse(BaseSchema):
    """Response after successfully claiming an application."""

    application_id: UUID
    tracking_code: str
    status: str
    message: str = "Application claimed successfully"


# =========================
# Printable Application
# =========================


class PrintableGuardianInfo(BaseSchema):
    """Guardian info formatted for print view."""

    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    relationship: str
    is_primary: bool
    occupation: Optional[str] = None
    address: Optional[str] = None


class PrintableDocumentInfo(BaseSchema):
    """Document info formatted for print view."""

    document_type: str
    file_name: str
    created_at: datetime


class PrintablePaymentInfo(BaseSchema):
    """Payment info formatted for print view."""

    amount: Decimal
    currency: str
    payment_method: Optional[str] = None
    status: str
    paid_at: Optional[datetime] = None


class PrintableDecisionInfo(BaseSchema):
    """Decision info formatted for print view."""

    decision_type: str
    offered_class_name: Optional[str] = None
    conditions: Optional[str] = None
    decision_date: date
    response_deadline: Optional[date] = None


class PrintableApplicationResponse(BaseSchema):
    """
    Full application data formatted for server-rendered print view.

    Includes all nested relations: guardians, documents, payments, decision.
    No sensitive internal data (notes, status history are excluded).
    """

    id: UUID
    tracking_code: str
    school_name: str
    school_logo_url: Optional[str] = None
    admission_period_name: str
    applicant_first_name: str
    applicant_last_name: str
    applicant_other_names: Optional[str] = None
    date_of_birth: Optional[date] = None  # Nullable for draft applications
    gender: Optional[str] = None  # Nullable for draft applications
    nationality: Optional[str] = None
    target_class_name: Optional[str] = None  # Nullable when no target class selected yet
    previous_school: Optional[str] = None
    medical_info: Optional[str] = None
    custom_fields: dict[str, Any]
    status: str
    submitted_at: Optional[datetime] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime
    guardians: list[PrintableGuardianInfo]
    documents: list[PrintableDocumentInfo]
    payments: list[PrintablePaymentInfo]
    decision: Optional[PrintableDecisionInfo] = None

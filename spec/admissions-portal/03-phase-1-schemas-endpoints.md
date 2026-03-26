# Phase 1: Schemas & Endpoints

**Sprint:** 19-20
**Agent:** 3 (Schemas + Endpoints)
**Depends on:** Agent 1 (models) + Agent 2 (services) — needs model classes and service classes to exist
**Produces:** All Pydantic schemas, all endpoint functions, router registration, public path configuration

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 3.1 | Create all Pydantic schemas | `backend/app/schemas/admissions.py` | 2d |
| 3.2 | Create public endpoints | `backend/app/api/v1/endpoints/admissions/public.py` | 1.5d |
| 3.3 | Create Paystack webhook endpoint | `backend/app/api/v1/endpoints/admissions/webhook.py` | 0.5d |
| 3.4 | Create period management endpoints | `backend/app/api/v1/endpoints/admissions/periods.py` | 1d |
| 3.5 | Create application management endpoints | `backend/app/api/v1/endpoints/admissions/applications.py` | 1d |
| 3.6 | Create exam management endpoints | `backend/app/api/v1/endpoints/admissions/exams.py` | 0.75d |
| 3.7 | Create decision endpoints | `backend/app/api/v1/endpoints/admissions/decisions.py` | 0.5d |
| 3.8 | Create enrollment endpoints | `backend/app/api/v1/endpoints/admissions/enrollment.py` | 0.75d |
| 3.9 | Create class promotion endpoints | `backend/app/api/v1/endpoints/admissions/promotions.py` | 0.75d |
| 3.9b | Create return intent endpoints | `backend/app/api/v1/endpoints/admissions/return_intents.py` | 0.5d |
| 3.10 | Create dashboard endpoints | `backend/app/api/v1/endpoints/admissions/dashboard.py` | 0.5d |
| 3.11 | Create admissions router `__init__.py` | `backend/app/api/v1/endpoints/admissions/__init__.py` | 0.25d |
| 3.12 | Register in main router | `backend/app/api/v1/router.py` | 0.1d |

---

## 3.1 Pydantic Schemas

**File:** `backend/app/schemas/admissions.py`

All schemas follow the existing pattern: `BaseSchema` with `ConfigDict(from_attributes=True, str_strip_whitespace=True)`. Create/Update schemas use `Field()` with validation. Response schemas include `id`, `tenant_id`, timestamps.

```python
"""
SIMS Plus - Admissions Portal Schemas

Pydantic schemas for admissions endpoints (Sprint 19-24).
Covers: admission periods, applications, guardians, documents,
payments, status tracking, entrance exams, decisions, enrollment,
class promotions, return intent surveys, and dashboard analytics.
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
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


class ApplicationStatusEnum(str, Enum):
    """Application status values for schema validation."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    SHORTLISTED = "shortlisted"
    EXAM_SCHEDULED = "exam_scheduled"
    EXAM_COMPLETED = "exam_completed"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    WAITLISTED = "waitlisted"
    REJECTED = "rejected"
    ENROLLED = "enrolled"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    DEFERRED = "deferred"


class AdmissionPeriodStatusEnum(str, Enum):
    """Admission period status values."""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class EntranceExamStatusEnum(str, Enum):
    """Entrance exam status values."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionTypeEnum(str, Enum):
    """Decision type values."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"
    DEFERRED = "deferred"


# =========================
# Admission Period Schemas
# =========================


class AdmissionPeriodCreate(BaseSchema):
    """Create admission period request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    academic_year_id: UUID
    start_date: date
    end_date: date
    application_fee_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    application_fee_required: bool = False
    entrance_exam_required: bool = False
    max_applications: Optional[int] = Field(None, ge=1)
    target_classes: list[UUID] = Field(default_factory=list)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v

    @field_validator("application_fee_amount")
    @classmethod
    def fee_required_if_amount(cls, v: Decimal | None, info) -> Decimal | None:
        required = info.data.get("application_fee_required")
        if required and (v is None or v <= 0):
            raise ValueError("application_fee_amount required when application_fee_required is true")
        return v


class AdmissionPeriodUpdate(BaseSchema):
    """Update admission period request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    application_fee_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    application_fee_required: Optional[bool] = None
    entrance_exam_required: Optional[bool] = None
    max_applications: Optional[int] = Field(None, ge=1)
    target_classes: Optional[list[UUID]] = None


class AdmissionPeriodStatusUpdate(BaseSchema):
    """Update admission period status (open/close/archive)."""

    status: AdmissionPeriodStatusEnum


class AdmissionPeriodResponse(BaseSchema):
    """Admission period response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    academic_year_id: UUID
    name: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    status: str
    application_fee_amount: Optional[Decimal] = None
    application_fee_required: bool
    entrance_exam_required: bool
    max_applications: Optional[int] = None
    target_classes: list[UUID]
    application_count: Optional[int] = None  # Populated by service
    created_at: datetime
    updated_at: datetime


class AdmissionPeriodListResponse(BaseSchema):
    """Paginated admission period list."""

    items: list[AdmissionPeriodResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Form Config Schemas
# =========================


class FormConfigUpdate(BaseSchema):
    """Update form configuration for an admission period."""

    form_schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema object defining custom form fields"
    )
    required_documents: list[str] = Field(
        default_factory=list,
        description="List of required document types (e.g., 'birth_certificate', 'passport_photo')"
    )


class FormConfigResponse(BaseSchema):
    """Form configuration response."""

    id: UUID
    admission_period_id: UUID
    form_schema: dict[str, Any]
    required_documents: list[str]
    created_at: datetime
    updated_at: datetime


# =========================
# Public Schemas (Unauthenticated)
# =========================


class PublicSchoolInfoResponse(BaseSchema):
    """School branding info for public application form."""

    school_name: str
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    motto: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class PublicPeriodResponse(BaseSchema):
    """Public-facing admission period (minimal info)."""

    id: UUID
    name: str
    description: Optional[str] = None
    start_date: date
    end_date: date
    application_fee_amount: Optional[Decimal] = None
    application_fee_required: bool
    entrance_exam_required: bool
    target_classes: list[dict[str, Any]]  # [{id, name, level}]


class PublicPeriodListResponse(BaseSchema):
    """List of open admission periods (public)."""

    items: list[PublicPeriodResponse]
    school: PublicSchoolInfoResponse


class PublicFormConfigResponse(BaseSchema):
    """Form configuration for public application form."""

    admission_period_id: UUID
    period_name: str
    form_schema: dict[str, Any]
    required_documents: list[str]
    application_fee_amount: Optional[Decimal] = None
    application_fee_required: bool
    target_classes: list[dict[str, Any]]  # [{id, name, level}]


class ApplicationGuardianSubmit(BaseSchema):
    """Guardian info submitted with application."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    relationship: str = Field(..., pattern="^(father|mother|guardian|other)$")
    is_primary: bool = False
    occupation: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None


class ApplicationSubmitRequest(BaseSchema):
    """Public application submission request."""

    admission_period_id: UUID
    applicant_first_name: str = Field(..., min_length=1, max_length=100)
    applicant_last_name: str = Field(..., min_length=1, max_length=100)
    applicant_other_names: Optional[str] = Field(None, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(male|female)$")
    nationality: Optional[str] = Field(None, max_length=100)
    target_class_id: UUID
    previous_school: Optional[str] = Field(None, max_length=255)
    medical_info: Optional[str] = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    guardians: list[ApplicationGuardianSubmit] = Field(..., min_length=1, max_length=5)
    turnstile_token: str = Field(..., min_length=1)

    @field_validator("guardians")
    @classmethod
    def at_least_one_primary(cls, v: list[ApplicationGuardianSubmit]) -> list[ApplicationGuardianSubmit]:
        if not any(g.is_primary for g in v):
            # Auto-set first guardian as primary
            v[0].is_primary = True
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date) -> date:
        from datetime import date as date_cls
        if v > date_cls.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class ApplicationSubmitResponse(BaseSchema):
    """Response after successful application submission."""

    tracking_code: str
    application_id: UUID
    status: str
    message: str = "Application submitted successfully"
    payment_required: bool
    application_fee_amount: Optional[Decimal] = None


class ApplicationStatusCheckResponse(BaseSchema):
    """Public status check response — minimal data only (no PII beyond first name)."""

    status: str
    applicant_first_name: str
    submitted_at: Optional[datetime] = None
    last_updated_at: datetime


class DocumentUploadRequest(BaseSchema):
    """Request presigned URL for document upload."""

    document_type: str = Field(
        ...,
        pattern="^(birth_certificate|passport_photo|transcript|medical_report|recommendation_letter|other)$"
    )
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(
        ...,
        pattern="^(application/pdf|image/jpeg|image/png)$"
    )
    file_size: int = Field(..., gt=0, le=5242880)  # Max 5MB


class DocumentUploadResponse(BaseSchema):
    """Presigned URL for document upload."""

    document_id: UUID
    upload_url: str
    s3_key: str
    expires_in: int = 3600  # 1 hour


class PaymentInitiateRequest(BaseSchema):
    """Initiate application fee payment."""

    callback_url: str = Field(..., min_length=1, max_length=500)
    payment_method: Optional[str] = Field(None, pattern="^(mobile_money|card)$")

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: str) -> str:
        """Prevent open redirect — only allow HTTPS on simsplus.io domains."""
        import re
        if not v.startswith("https://"):
            raise ValueError("callback_url must use HTTPS")
        if not re.match(r"^https://[\w.-]+\.simsplus\.io/", v):
            raise ValueError("callback_url must be on simsplus.io domain")
        return v


class PaymentInitiateResponse(BaseSchema):
    """Payment initiation response."""

    payment_id: UUID
    authorization_url: str
    access_code: str
    reference: str
    amount: Decimal
    currency: str = "GHS"


# =========================
# Admin Application Schemas
# =========================


class ApplicationResponse(BaseSchema):
    """Full application detail for admin view."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    admission_period_id: UUID
    tracking_code: str
    applicant_first_name: str
    applicant_last_name: str
    applicant_other_names: Optional[str] = None
    date_of_birth: date
    gender: str
    nationality: Optional[str] = None
    target_class_id: UUID
    target_class_name: Optional[str] = None  # Populated by service
    status: str
    custom_fields: dict[str, Any]
    fee_waived: bool
    exam_waived: bool
    converted_student_id: Optional[UUID] = None
    applicant_photo_url: Optional[str] = None
    previous_school: Optional[str] = None
    medical_info: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Nested relations (populated when fetching detail)
    guardians: list["ApplicationGuardianResponse"] = []
    documents: list["ApplicationDocumentResponse"] = []
    payments: list["ApplicationPaymentResponse"] = []
    notes: list["ApplicationNoteResponse"] = []
    status_history: list["StatusHistoryResponse"] = []
    exam_results: list["ExamResultResponse"] = []
    decision: Optional["AdmissionDecisionResponse"] = None


class ApplicationListItem(BaseSchema):
    """Application list item (lightweight for table views)."""

    id: UUID
    tracking_code: str
    applicant_first_name: str
    applicant_last_name: str
    date_of_birth: date
    gender: str
    target_class_name: Optional[str] = None
    status: str
    fee_waived: bool
    exam_waived: bool
    submitted_at: Optional[datetime] = None
    created_at: datetime


class ApplicationListResponse(BaseSchema):
    """Paginated application list."""

    items: list[ApplicationListItem]
    total: int
    page: int
    page_size: int
    pages: int


class ApplicationStatusChangeRequest(BaseSchema):
    """Change application status (admin action)."""

    status: ApplicationStatusEnum
    reason: Optional[str] = None


class ApplicationGuardianResponse(BaseSchema):
    """Guardian info in application detail."""

    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    relationship: str
    is_primary: bool
    occupation: Optional[str] = None
    address: Optional[str] = None


class ApplicationDocumentResponse(BaseSchema):
    """Document info in application detail."""

    id: UUID
    document_type: str
    file_name: str
    s3_key: str
    file_size: int
    mime_type: str
    download_url: Optional[str] = None  # Presigned URL generated on request
    created_at: datetime


class ApplicationPaymentResponse(BaseSchema):
    """Payment record in application detail."""

    id: UUID
    amount: Decimal
    currency: str
    payment_method: Optional[str] = None
    provider_reference: Optional[str] = None
    status: str
    paid_at: Optional[datetime] = None
    created_at: datetime


class ApplicationNoteCreate(BaseSchema):
    """Create internal note on application."""

    content: str = Field(..., min_length=1, max_length=5000)
    is_internal: bool = True


class ApplicationNoteResponse(BaseSchema):
    """Application note in detail view."""

    id: UUID
    author_id: UUID
    author_name: Optional[str] = None  # Populated by service
    content: str
    is_internal: bool
    created_at: datetime


class StatusHistoryResponse(BaseSchema):
    """Status history entry."""

    id: UUID
    from_status: Optional[str] = None
    to_status: str
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None  # Populated by service
    reason: Optional[str] = None
    created_at: datetime


class FeeWaiverRequest(BaseSchema):
    """Waive application fee."""

    reason: str = Field(..., min_length=1, max_length=500)


class ExamWaiverRequest(BaseSchema):
    """Waive entrance exam."""

    reason: str = Field(..., min_length=1, max_length=500)


# =========================
# Entrance Exam Schemas
# =========================


class EntranceExamCreate(BaseSchema):
    """Create entrance exam session."""

    admission_period_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    exam_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    venue: str = Field(..., min_length=1, max_length=255)
    capacity: int = Field(..., ge=1)
    instructions: Optional[str] = None


class EntranceExamUpdate(BaseSchema):
    """Update entrance exam session."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    exam_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    venue: Optional[str] = Field(None, min_length=1, max_length=255)
    capacity: Optional[int] = Field(None, ge=1)
    instructions: Optional[str] = None
    status: Optional[EntranceExamStatusEnum] = None


class EntranceExamResponse(BaseSchema):
    """Entrance exam session response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    admission_period_id: UUID
    name: str
    exam_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    venue: str
    capacity: int
    status: str
    instructions: Optional[str] = None
    registered_count: Optional[int] = None  # Populated by service
    attended_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class EntranceExamListResponse(BaseSchema):
    """Paginated entrance exam list."""

    items: list[EntranceExamResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ExamRegistrationRequest(BaseSchema):
    """Register applicants to an exam session."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class ExamRegistrationResponse(BaseSchema):
    """Exam registration response."""

    id: UUID
    entrance_exam_id: UUID
    application_id: UUID
    seat_number: Optional[str] = None
    attended: bool
    applicant_name: Optional[str] = None


class ExamResultEntry(BaseSchema):
    """Single exam result entry."""

    application_id: UUID
    score: Decimal = Field(..., ge=0)
    max_score: Decimal = Field(..., gt=0)
    grade: Optional[str] = Field(None, max_length=10)
    passed: bool
    remarks: Optional[str] = None


class ExamResultsSubmitRequest(BaseSchema):
    """Submit exam results for multiple applicants."""

    results: list[ExamResultEntry] = Field(..., min_length=1, max_length=200)


class ExamResultResponse(BaseSchema):
    """Exam result detail."""

    id: UUID
    entrance_exam_id: UUID
    application_id: UUID
    applicant_name: Optional[str] = None
    score: Decimal
    max_score: Decimal
    grade: Optional[str] = None
    passed: bool
    remarks: Optional[str] = None
    scored_by: Optional[UUID] = None
    created_at: datetime


# =========================
# Decision Schemas
# =========================


class AdmissionDecisionCreate(BaseSchema):
    """Make admission decision for single application."""

    application_id: UUID
    decision_type: DecisionTypeEnum
    offered_class_id: Optional[UUID] = None  # May differ from target class
    conditions: Optional[str] = None
    response_deadline: Optional[date] = None

    @field_validator("offered_class_id")
    @classmethod
    def class_required_for_acceptance(cls, v: UUID | None, info) -> UUID | None:
        dt = info.data.get("decision_type")
        if dt == DecisionTypeEnum.ACCEPTED and v is None:
            raise ValueError("offered_class_id required for acceptance decision")
        return v


class BulkDecisionRequest(BaseSchema):
    """Bulk admission decision request."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    decision_type: DecisionTypeEnum
    offered_class_id: Optional[UUID] = None
    conditions: Optional[str] = None
    response_deadline: Optional[date] = None


class BulkDecisionResponse(BaseSchema):
    """Bulk decision result with partial success."""

    succeeded: list[dict[str, Any]]  # [{application_id, decision_id}]
    failed: list[dict[str, Any]]  # [{application_id, error}]
    total_succeeded: int
    total_failed: int


class AdmissionDecisionResponse(BaseSchema):
    """Admission decision detail."""

    id: UUID
    application_id: UUID
    decision_type: str
    decided_by: UUID
    decided_by_name: Optional[str] = None
    offered_class_id: Optional[UUID] = None
    offered_class_name: Optional[str] = None
    conditions: Optional[str] = None
    decision_date: date
    response_deadline: Optional[date] = None
    decision_letter_url: Optional[str] = None
    created_at: datetime


# =========================
# Enrollment Schemas
# =========================


class EnrollRequest(BaseSchema):
    """Enroll a single accepted applicant as a student."""

    generate_invoice: bool = True  # Whether to auto-generate admission invoice
    class_section_id: Optional[UUID] = None  # Optional section assignment


class EnrollResponse(BaseSchema):
    """Enrollment result."""

    application_id: UUID
    student_id: UUID
    student_number: str
    guardian_ids: list[UUID]
    invoice_id: Optional[UUID] = None
    parent_account_created: bool = False
    message: str = "Applicant enrolled successfully"


class BulkEnrollRequest(BaseSchema):
    """Bulk enroll accepted applicants."""

    application_ids: list[UUID] = Field(..., min_length=1, max_length=50)
    generate_invoice: bool = True


class BulkEnrollResponse(BaseSchema):
    """Bulk enrollment result with partial success pattern."""

    succeeded: list[EnrollResponse]
    failed: list[dict[str, Any]]  # [{application_id, error}]
    total_succeeded: int
    total_failed: int


# =========================
# Class Promotion Schemas
# =========================


class ClassPromotionCreate(BaseSchema):
    """Create a promotion batch."""

    source_academic_year_id: UUID
    target_academic_year_id: UUID
    name: str = Field(..., min_length=1, max_length=255)


class ClassPromotionResponse(BaseSchema):
    """Promotion batch detail."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    source_academic_year_id: UUID
    source_academic_year_name: Optional[str] = None
    target_academic_year_id: UUID
    target_academic_year_name: Optional[str] = None
    name: str
    status: str  # draft, preview, in_progress, completed, failed
    total_students: int
    promoted_count: int
    repeated_count: int
    graduated_count: int
    withdrawn_count: int
    executed_at: Optional[datetime] = None
    executed_by: Optional[UUID] = None
    executed_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ClassPromotionListResponse(BaseSchema):
    """Paginated promotion batch list."""

    items: list[ClassPromotionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ClassPromotionEntryResponse(BaseSchema):
    """Per-student promotion entry."""

    id: UUID
    promotion_id: UUID
    student_id: UUID
    student_name: Optional[str] = None
    student_number: Optional[str] = None
    source_class_id: UUID
    source_class_name: Optional[str] = None
    source_section_id: Optional[UUID] = None
    source_section_name: Optional[str] = None
    target_class_id: Optional[UUID] = None
    target_class_name: Optional[str] = None
    target_section_id: Optional[UUID] = None
    target_section_name: Optional[str] = None
    action: str  # promote, repeat, graduate, withdraw
    reason: Optional[str] = None
    processed: bool


class ClassPromotionEntryListResponse(BaseSchema):
    """Paginated entry list."""

    items: list[ClassPromotionEntryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PromotionEntryUpdate(BaseSchema):
    """Update a single promotion entry's action."""

    action: str = Field(..., pattern="^(promote|repeat|graduate|withdraw)$")
    target_class_id: Optional[UUID] = None
    target_section_id: Optional[UUID] = None
    reason: Optional[str] = None


class PromotionEntryBulkItem(BaseSchema):
    """Single entry in a bulk promotion update."""

    entry_id: UUID
    action: str = Field(..., pattern="^(promote|repeat|graduate|withdraw)$")
    target_class_id: Optional[UUID] = None
    target_section_id: Optional[UUID] = None
    reason: Optional[str] = Field(None, max_length=500)


class BulkPromotionEntryUpdate(BaseSchema):
    """Bulk update entries — typed for proper Pydantic validation."""

    updates: list[PromotionEntryBulkItem] = Field(
        ..., min_length=1, max_length=200,
    )


class BulkPromotionUpdateResponse(BaseSchema):
    """Bulk update result."""

    succeeded: int
    failed: list[dict[str, Any]]  # [{entry_id, error}]


# =========================
# Return Intent Schemas
# =========================


class ReturnIntentCampaignCreate(BaseSchema):
    """Create return intent survey campaign."""

    name: str = Field(..., min_length=1, max_length=255)
    academic_year_id: UUID
    target_classes: list[UUID] = Field(..., min_length=1)
    message_template: Optional[str] = None
    deadline: Optional[date] = None


class ReturnIntentCampaignResponse(BaseSchema):
    """Return intent campaign detail."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    academic_year_id: UUID
    name: str
    target_classes: list[UUID]
    message_template: Optional[str] = None
    status: str  # draft, sent, completed
    sent_at: Optional[datetime] = None
    sent_count: int
    deadline: Optional[date] = None
    # Stats populated by service
    total_students: Optional[int] = None
    returning_count: Optional[int] = None
    not_returning_count: Optional[int] = None
    undecided_count: Optional[int] = None
    pending_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ReturnIntentCampaignListResponse(BaseSchema):
    """Paginated campaign list."""

    items: list[ReturnIntentCampaignResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ReturnIntentResponse(BaseSchema):
    """Individual return intent record."""

    id: UUID
    student_id: UUID
    student_name: Optional[str] = None
    current_class_name: Optional[str] = None
    intent: str  # pending, returning, not_returning, undecided
    responded_at: Optional[datetime] = None
    responded_by: Optional[UUID] = None
    reason: Optional[str] = None


class ReturnIntentRespondRequest(BaseSchema):
    """Parent responds to return intent survey."""

    intent: str = Field(..., pattern="^(returning|not_returning|undecided)$")
    reason: Optional[str] = None


# =========================
# Dashboard Schemas
# =========================


class DashboardStatsResponse(BaseSchema):
    """Admissions dashboard statistics."""

    total_applications: int
    by_status: dict[str, int]  # {status: count}
    by_class: list[dict[str, Any]]  # [{class_name, count}]
    by_period: list[dict[str, Any]]  # [{period_name, count}]
    conversion_rate: Optional[float] = None  # enrolled / total
    pending_decisions: int
    pending_enrollment: int  # accepted but not yet enrolled
    recent_applications: list[ApplicationListItem]


class DemographicsResponse(BaseSchema):
    """Applicant demographic breakdown."""

    by_gender: dict[str, int]  # {male: N, female: N}
    by_nationality: list[dict[str, Any]]  # [{nationality, count}]
    by_previous_school: list[dict[str, Any]]  # [{school, count}]
    age_distribution: list[dict[str, Any]]  # [{age_range, count}]
```

---

## 3.2 Public Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/public.py`

These are the unauthenticated endpoints accessed by prospective parents. They use `get_public_tenant_db()` instead of `get_db()`.

```python
"""
SIMS Plus - Admissions Portal Public Endpoints

Unauthenticated endpoints for the public application form.
Tenant resolved from subdomain via TenantMiddleware → request.state.tenant_id.
Uses get_public_tenant_db() for tenant-scoped DB without JWT.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_public_tenant_db, PublicTenantSession
from app.schemas.admissions import (
    ApplicationStatusCheckResponse,
    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PublicFormConfigResponse,
    PublicPeriodListResponse,
    PublicSchoolInfoResponse,
)
from app.services.admissions import (
    AdmissionPeriodService,
    AdmissionServiceError,
    ApplicationPaymentService,
    ApplicationService,
)

router = APIRouter(prefix="/public")


@router.get(
    "/school-info",
    response_model=PublicSchoolInfoResponse,
    summary="Get school branding for application form",
)
async def get_school_info(
    request: Request,
    db: PublicTenantSession,
) -> PublicSchoolInfoResponse:
    """
    Returns school name, logo, colors, and contact info.
    Used by the public application form to render school branding.
    No authentication required — tenant resolved from subdomain.
    """
    service = ApplicationService(db)
    try:
        return await service.get_school_info(
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/periods",
    response_model=PublicPeriodListResponse,
    summary="List open admission periods",
)
async def list_open_periods(
    request: Request,
    db: PublicTenantSession,
) -> PublicPeriodListResponse:
    """
    Returns all admission periods with status='open' for this school,
    including target class info (id, name, level) and fee details.
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.list_open_periods(
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/periods/{period_id}/form",
    response_model=PublicFormConfigResponse,
    summary="Get form configuration for a period",
)
async def get_period_form(
    period_id: UUID,
    request: Request,
    db: PublicTenantSession,
) -> PublicFormConfigResponse:
    """
    Returns the custom form schema, required documents, fee info,
    and target classes for a specific admission period.
    Used to render the multi-step application form.
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.get_form_config(
            period_id=period_id,
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/applications",
    response_model=ApplicationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit application",
)
async def submit_application(
    data: ApplicationSubmitRequest,
    request: Request,
    db: PublicTenantSession,
) -> ApplicationSubmitResponse:
    """
    Submit a new application. Requires Cloudflare Turnstile token.

    Flow:
    1. Verify Turnstile token
    2. Validate admission period is open
    3. Validate target_class_id is in period's target_classes
    4. Validate custom_fields against form_schema (jsonschema)
    5. Check max_applications cap not exceeded
    6. Create application + guardians
    7. Log status history (NULL → SUBMITTED or DRAFT → SUBMITTED)
    8. Send confirmation SMS/email to primary guardian

    Returns tracking_code for status checking and document upload.
    If payment is required and fee_waived=false, status starts as DRAFT
    until payment is confirmed.
    """
    # NOTE: school_id is NOT on request.state for public endpoints.
    # Derive it from the admission period's school_id in the service layer:
    #   period = await period_service.get(data.admission_period_id)
    #   school_id = period.school_id
    service = ApplicationService(db)
    try:
        return await service.submit_application(
            data=data,
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/applications/{tracking_code}/status",
    response_model=ApplicationStatusCheckResponse,
    summary="Check application status",
)
async def check_application_status(
    tracking_code: str,
    request: Request,
    db: PublicTenantSession,
) -> ApplicationStatusCheckResponse:
    """
    Check the status of an application using the tracking code.

    SECURITY: Returns ONLY minimal data:
    - status (e.g., "submitted", "offered")
    - applicant_first_name (already known to the person who applied)
    - submitted_at
    - last_updated_at

    No guardian info, no PII, no documents, no decision details.
    """
    service = ApplicationService(db)
    try:
        return await service.check_status(
            tracking_code=tracking_code,
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/applications/{tracking_code}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document for application",
)
async def upload_document(
    tracking_code: str,
    data: DocumentUploadRequest,
    request: Request,
    db: PublicTenantSession,
) -> DocumentUploadResponse:
    """
    Request a presigned S3 URL for document upload.

    Validation:
    - Application must exist and be in DRAFT or SUBMITTED status
    - Max 5 documents per application
    - File size max 5MB
    - MIME types: application/pdf, image/jpeg, image/png
    - Document type must be in required_documents or 'other'

    S3 path format: admissions/{tenant_id}/{application_id}/{uuid}.{ext}

    Returns a presigned PUT URL. Frontend uploads directly to S3.
    After successful upload, the document record is created.
    """
    service = ApplicationService(db)
    try:
        return await service.upload_document(
            tracking_code=tracking_code,
            data=data,
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/applications/{tracking_code}/pay",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate application fee payment",
)
async def initiate_payment(
    tracking_code: str,
    data: PaymentInitiateRequest,
    request: Request,
    db: PublicTenantSession,
) -> PaymentInitiateResponse:
    """
    Initialize Paystack payment for application fee.

    Validates:
    - Application exists and fee is not waived
    - No completed payment already exists for this application
    - Admission period has application_fee_amount set

    Creates application_payments record with status='pending',
    then calls Paystack to create a transaction.

    Paystack metadata includes: application_id, tenant_id, school_id, context="application_fee"

    Returns authorization_url for redirect or access_code for inline popup.
    """
    service = ApplicationPaymentService(db)
    try:
        return await service.initiate_payment(
            tracking_code=tracking_code,
            data=data,
            tenant_id=request.state.tenant_id,
        )
    except AdmissionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
```

**Document Upload Security Note:** The presigned URL should include a `Content-Type` condition matching `data.mime_type` so S3 rejects mismatched content types. Additionally, after the client uploads, a confirmation callback or S3 event should trigger magic byte validation (using `validate_file_magic()` from the existing media upload pattern) before marking the document as verified. Until verified, documents should not be downloadable by admins.

---

## 3.3 Paystack Webhook Endpoint

**File:** `backend/app/api/v1/endpoints/admissions/webhook.py`

Follows the exact same pattern as the parent portal webhook in `backend/app/api/v1/endpoints/parent/payment.py`.

```python
"""
SIMS Plus - Admissions Portal Paystack Webhook

Unauthenticated webhook for Paystack payment confirmations.
Uses UnscopedDatabaseSession + manual set_tenant_context from metadata.
Verifies HMAC-SHA512 signature before processing.
"""

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

from app.api.deps import UnscopedDatabaseSession
from app.config import settings
from app.services.admissions import ApplicationPaymentService, AdmissionServiceError

router = APIRouter(prefix="/public/webhook")


@router.post(
    "/paystack",
    status_code=status.HTTP_200_OK,
    summary="Paystack webhook for application payments",
)
async def handle_paystack_webhook(
    request: Request,
    db: UnscopedDatabaseSession,
) -> dict:
    """
    Handle Paystack webhook for application fee payment confirmation.

    Security:
    1. Verify HMAC-SHA512 signature using PAYSTACK_WEBHOOK_SECRET (or PAYSTACK_SECRET_KEY fallback)
    2. Extract tenant_id from event metadata
    3. Look up payment by provider_reference (unscoped) and cross-validate tenant_id
    4. Set tenant context with VALIDATED tenant_id from DB record
    5. Process payment confirmation

    Uses UnscopedDatabaseSession because:
    - Webhook has no subdomain context (called by Paystack servers)
    - tenant_id comes from Paystack metadata (set during payment initiation)
    - We manually set_tenant_context after extracting from metadata

    Returns 200 OK immediately — Paystack retries on non-200.
    """
    # 1. Read raw body for signature verification
    body = await request.body()

    # 2. Verify HMAC-SHA512 signature
    signature = request.headers.get("x-paystack-signature", "")
    # Prefer dedicated webhook secret, fall back to API secret key
    secret_key = getattr(settings, "PAYSTACK_WEBHOOK_SECRET", None) or settings.PAYSTACK_SECRET_KEY
    expected = hmac.new(
        secret_key.encode(),
        body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # 3. Parse event
    import json
    event = json.loads(body)

    # Only process charge.success events
    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    # 4. Extract metadata
    data = event.get("data", {})
    metadata = data.get("metadata", {})

    # Validate context is application_fee
    if metadata.get("context") != "application_fee":
        return {"status": "ignored", "reason": "not application_fee context"}

    webhook_tenant_id = metadata.get("tenant_id")
    if not webhook_tenant_id:
        return {"status": "ignored", "reason": "no tenant_id in metadata"}

    reference = data.get("reference")
    if not reference:
        return {"status": "ignored", "reason": "no reference in data"}

    # 5. Cross-validate tenant_id: look up payment by provider_reference first
    from app.models.admissions.application import ApplicationPayment
    from sqlalchemy import select

    result = await db.execute(
        select(ApplicationPayment).where(
            ApplicationPayment.provider_reference == reference,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        import structlog
        structlog.get_logger().warning("webhook_payment_not_found", reference=reference)
        return {"status": "ignored", "reason": "payment not found"}

    # Validate metadata tenant_id matches actual payment's tenant_id
    if str(payment.tenant_id) != webhook_tenant_id:
        import structlog
        structlog.get_logger().error(
            "webhook_tenant_mismatch",
            expected=str(payment.tenant_id),
            received=webhook_tenant_id,
        )
        return {"status": "ignored", "reason": "tenant mismatch"}

    # 6. Set tenant context with VALIDATED tenant_id from DB record
    await db.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(payment.tenant_id)},
    )

    # 7. Process payment
    try:
        service = ApplicationPaymentService(db)
        await service.process_webhook(
            provider_reference=reference,
            amount=data.get("amount", 0) / 100,  # Paystack sends in kobo/pesewas
            payment_method=data.get("channel"),
            metadata=metadata,
        )
    except AdmissionServiceError:
        # Log but don't raise — return 200 to prevent retries
        import structlog
        logger = structlog.get_logger()
        logger.error(
            "admission_webhook_processing_failed",
            reference=data.get("reference"),
            tenant_id=tenant_id,
        )

    return {"status": "processed"}
```

---

## 3.4 Period Management Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/periods.py`

```python
"""
SIMS Plus - Admission Period Management Endpoints

Admin endpoints for creating and managing admission periods.
Requires authentication + admissions permissions.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    AdmissionPeriodCreate,
    AdmissionPeriodListResponse,
    AdmissionPeriodResponse,
    AdmissionPeriodStatusUpdate,
    AdmissionPeriodUpdate,
    FormConfigResponse,
    FormConfigUpdate,
)
from app.services.admissions import AdmissionPeriodService, AdmissionServiceError

router = APIRouter(prefix="/periods")


def _handle_error(e: AdmissionServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "PERIOD_OVERLAP": 409,
        "VALIDATION_ERROR": 422,
        "INVALID_STATUS_TRANSITION": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=AdmissionPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create admission period",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_period(
    data: AdmissionPeriodCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """
    Create a new admission period.

    Validates:
    - academic_year_id exists and belongs to tenant
    - target_classes are valid class IDs in the school
    - No overlapping periods for the same classes
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.create(
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            created_by=UUID(user["user_id"]),
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=AdmissionPeriodListResponse,
    summary="List admission periods",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_periods(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    academic_year_id: UUID | None = Query(None),
) -> AdmissionPeriodListResponse:
    """List admission periods with optional filters."""
    service = AdmissionPeriodService(db)
    return await service.list_periods(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        academic_year_id=academic_year_id,
    )


@router.get(
    "/{period_id}",
    response_model=AdmissionPeriodResponse,
    summary="Get admission period details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_period(
    period_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """Get admission period details including application count."""
    service = AdmissionPeriodService(db)
    try:
        return await service.get_by_id(
            period_id=period_id,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{period_id}",
    response_model=AdmissionPeriodResponse,
    summary="Update admission period",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_period(
    period_id: UUID,
    data: AdmissionPeriodUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """Update admission period. Only draft periods can be fully edited."""
    service = AdmissionPeriodService(db)
    try:
        return await service.update(
            period_id=period_id,
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{period_id}/status",
    response_model=AdmissionPeriodResponse,
    summary="Change admission period status",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def change_period_status(
    period_id: UUID,
    data: AdmissionPeriodStatusUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionPeriodResponse:
    """
    Change admission period status.
    Valid transitions: draft→open, open→closed, closed→archived.
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.change_status(
            period_id=period_id,
            new_status=data.status.value,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{period_id}/form-config",
    response_model=FormConfigResponse,
    summary="Update form configuration",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_form_config(
    period_id: UUID,
    data: FormConfigUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> FormConfigResponse:
    """
    Update the custom form schema and required documents for a period.
    Creates the form config if it doesn't exist (upsert).
    """
    service = AdmissionPeriodService(db)
    try:
        return await service.update_form_config(
            period_id=period_id,
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)
```

---

## 3.5 Application Management Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/applications.py`

```python
"""
SIMS Plus - Application Management Endpoints

Admin endpoints for reviewing and managing applications.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    ApplicationListResponse,
    ApplicationNoteCreate,
    ApplicationNoteResponse,
    ApplicationResponse,
    ApplicationStatusChangeRequest,
    ExamWaiverRequest,
    FeeWaiverRequest,
)
from app.services.admissions import ApplicationService, AdmissionServiceError

router = APIRouter(prefix="/applications")


def _handle_error(e: AdmissionServiceError) -> HTTPException:
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_STATUS_TRANSITION": 422,
        "VALIDATION_ERROR": 422,
        "ALREADY_WAIVED": 409,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.get(
    "",
    response_model=ApplicationListResponse,
    summary="List applications",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_applications(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    admission_period_id: UUID | None = Query(None),
    target_class_id: UUID | None = Query(None),
    search: str | None = Query(None, max_length=100),
    sort_by: str = Query("created_at", pattern="^(created_at|submitted_at|applicant_last_name|status)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> ApplicationListResponse:
    """
    List applications with filtering, search, sort, and pagination.

    Search queries applicant_first_name, applicant_last_name, tracking_code.
    """
    service = ApplicationService(db)
    return await service.list_applications(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        admission_period_id=admission_period_id,
        target_class_id=target_class_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get application details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_application(
    application_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Get full application detail including guardians, documents,
    payments, notes, status history, exam results, and decision.
    """
    service = ApplicationService(db)
    try:
        return await service.get_detail(
            application_id=application_id,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{application_id}/status",
    response_model=ApplicationResponse,
    summary="Change application status",
    dependencies=[Depends(require_permissions("admissions.review"))],
)
async def change_application_status(
    application_id: UUID,
    data: ApplicationStatusChangeRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Change application status with validation against the status machine.
    Records transition in application_status_history.
    Sends notification on relevant transitions (offered, etc.).
    """
    service = ApplicationService(db)
    try:
        return await service.change_status(
            application_id=application_id,
            new_status=data.status.value,
            reason=data.reason,
            changed_by=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{application_id}/notes",
    response_model=ApplicationNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add note to application",
    dependencies=[Depends(require_permissions("admissions.review"))],
)
async def add_note(
    application_id: UUID,
    data: ApplicationNoteCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationNoteResponse:
    """Add an internal note to an application."""
    service = ApplicationService(db)
    try:
        return await service.add_note(
            application_id=application_id,
            content=data.content,
            is_internal=data.is_internal,
            author_id=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{application_id}/waive-fee",
    response_model=ApplicationResponse,
    summary="Waive application fee",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def waive_fee(
    application_id: UUID,
    data: FeeWaiverRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Waive the application fee. Sets fee_waived=true.
    If application is in DRAFT status and payment was the only blocker,
    automatically transitions to SUBMITTED.
    Records the waiver reason in status_history.
    """
    service = ApplicationService(db)
    try:
        return await service.waive_fee(
            application_id=application_id,
            reason=data.reason,
            waived_by=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{application_id}/waive-exam",
    response_model=ApplicationResponse,
    summary="Waive entrance exam",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def waive_exam(
    application_id: UUID,
    data: ExamWaiverRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ApplicationResponse:
    """
    Waive the entrance exam. Sets exam_waived=true.
    Allows application to skip EXAM_SCHEDULED/EXAM_COMPLETED states.
    Records the waiver reason in status_history.
    """
    service = ApplicationService(db)
    try:
        return await service.waive_exam(
            application_id=application_id,
            reason=data.reason,
            waived_by=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)
```

---

## 3.6 Exam Management Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/exams.py`

```python
"""
SIMS Plus - Entrance Exam Management Endpoints
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    EntranceExamCreate,
    EntranceExamListResponse,
    EntranceExamResponse,
    EntranceExamUpdate,
    ExamRegistrationRequest,
    ExamRegistrationResponse,
    ExamResultResponse,
    ExamResultsSubmitRequest,
)
from app.services.admissions import ExamService, AdmissionServiceError

router = APIRouter(prefix="/exams")


def _handle_error(e: AdmissionServiceError) -> HTTPException:
    status_map = {"NOT_FOUND": 404, "VALIDATION_ERROR": 422, "CAPACITY_EXCEEDED": 409}
    return HTTPException(status_code=status_map.get(e.code, 400), detail=e.message)


@router.post(
    "",
    response_model=EntranceExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create entrance exam session",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_exam(
    data: EntranceExamCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EntranceExamResponse:
    """Create an entrance exam session for an admission period."""
    service = ExamService(db)
    try:
        return await service.create(
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=EntranceExamListResponse,
    summary="List entrance exams",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_exams(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admission_period_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> EntranceExamListResponse:
    """List entrance exam sessions with optional filters."""
    service = ExamService(db)
    return await service.list_exams(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
        admission_period_id=admission_period_id,
        status_filter=status_filter,
    )


@router.get(
    "/{exam_id}",
    response_model=EntranceExamResponse,
    summary="Get entrance exam details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_exam(
    exam_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EntranceExamResponse:
    """Get exam details including registration and attendance counts."""
    service = ExamService(db)
    try:
        return await service.get_by_id(
            exam_id=exam_id,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.put(
    "/{exam_id}",
    response_model=EntranceExamResponse,
    summary="Update entrance exam",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_exam(
    exam_id: UUID,
    data: EntranceExamUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EntranceExamResponse:
    """Update exam details. Cannot update completed/cancelled exams."""
    service = ExamService(db)
    try:
        return await service.update(
            exam_id=exam_id,
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{exam_id}/register",
    response_model=list[ExamRegistrationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register applicants to exam",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def register_applicants(
    exam_id: UUID,
    data: ExamRegistrationRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ExamRegistrationResponse]:
    """
    Register applicants to an exam session.
    Validates capacity is not exceeded. Auto-assigns seat numbers.
    Updates application status to EXAM_SCHEDULED.
    """
    service = ExamService(db)
    try:
        return await service.register_applicants(
            exam_id=exam_id,
            application_ids=data.application_ids,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{exam_id}/results",
    response_model=list[ExamResultResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Submit exam results",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def submit_results(
    exam_id: UUID,
    data: ExamResultsSubmitRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ExamResultResponse]:
    """
    Submit or update exam results for registered applicants.
    Updates application status to EXAM_COMPLETED.
    Upserts results (create if new, update if existing).
    """
    service = ExamService(db)
    try:
        return await service.submit_results(
            exam_id=exam_id,
            results=data.results,
            scored_by=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)
```

---

## 3.7 Decision Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/decisions.py`

```python
"""
SIMS Plus - Admission Decision Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    AdmissionDecisionCreate,
    AdmissionDecisionResponse,
    BulkDecisionRequest,
    BulkDecisionResponse,
)
from app.services.admissions import DecisionService, AdmissionServiceError

from uuid import UUID

router = APIRouter(prefix="/decisions")


def _handle_error(e: AdmissionServiceError) -> HTTPException:
    status_map = {"NOT_FOUND": 404, "INVALID_STATUS_TRANSITION": 422, "ALREADY_DECIDED": 409}
    return HTTPException(status_code=status_map.get(e.code, 400), detail=e.message)


@router.post(
    "",
    response_model=AdmissionDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Make admission decision",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def make_decision(
    data: AdmissionDecisionCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionDecisionResponse:
    """
    Make an admission decision for a single application.

    Creates admission_decisions record and updates application status:
    - accepted → status=OFFERED (not ACCEPTED — applicant must accept offer)
    - rejected → status=REJECTED
    - waitlisted → status=WAITLISTED
    - deferred → status=DEFERRED

    Sends notification to primary guardian on acceptance/rejection.
    """
    service = DecisionService(db)
    try:
        return await service.decide(
            data=data,
            decided_by=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/bulk",
    response_model=BulkDecisionResponse,
    summary="Bulk admission decision",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def bulk_decision(
    data: BulkDecisionRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkDecisionResponse:
    """
    Make bulk admission decisions.

    Each decision is processed in its own savepoint:
    - If one fails, others still succeed
    - Returns partial success: {succeeded: [...], failed: [...]}
    - If ALL fail → HTTP 422; if some succeed → HTTP 200

    Max 100 applications per request.
    """
    service = DecisionService(db)
    result = await service.bulk_decide(
        application_ids=data.application_ids,
        decision_type=data.decision_type.value,
        decided_by=UUID(user["user_id"]),
        offered_class_id=data.offered_class_id,
        conditions=data.conditions,
        response_deadline=data.response_deadline,
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
    )

    if result.total_succeeded == 0 and result.total_failed > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "All decisions failed",
                "failed": result.failed,
            },
        )

    return result
```

---

## 3.8 Enrollment Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/enrollment.py`

```python
"""
SIMS Plus - Enrollment Endpoints (Applicant → Student Conversion)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    BulkEnrollRequest,
    BulkEnrollResponse,
    EnrollRequest,
    EnrollResponse,
)
from app.services.admissions import EnrollmentService, AdmissionServiceError

router = APIRouter()


def _handle_error(e: AdmissionServiceError) -> HTTPException:
    status_map = {
        "NOT_FOUND": 404,
        "ALREADY_ENROLLED": 409,
        "INVALID_STATUS_TRANSITION": 422,
        "GUARDIAN_CONFLICT": 409,
    }
    return HTTPException(status_code=status_map.get(e.code, 400), detail=e.message)


@router.post(
    "/applications/{application_id}/enroll",
    response_model=EnrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll accepted applicant",
    dependencies=[Depends(require_permissions("admissions.enroll"))],
)
async def enroll_applicant(
    application_id: UUID,
    data: EnrollRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EnrollResponse:
    """
    Convert an accepted applicant into a student record.

    Atomic operation within a single transaction:
    1. Validate application status is ACCEPTED
    2. Check idempotency (converted_student_id must be NULL)
    3. Create/link Guardian records (deduplicate by email OR phone)
    4. Create Student record with auto-generated student ID
    5. Create StudentGuardian junction records
    6. Generate invoice (if generate_invoice=true and fee structure exists)
    7. Update application status to ENROLLED
    8. Create parent User account if guardian has email
    9. Send enrollment notification to guardian

    If application already has converted_student_id (idempotency),
    returns the existing student without creating a duplicate.
    """
    service = EnrollmentService(db)
    try:
        return await service.enroll(
            application_id=application_id,
            data=data,
            enrolled_by=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except AdmissionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/enroll/bulk",
    response_model=BulkEnrollResponse,
    summary="Bulk enroll accepted applicants",
    dependencies=[Depends(require_permissions("admissions.enroll"))],
)
async def bulk_enroll(
    data: BulkEnrollRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkEnrollResponse:
    """
    Bulk enroll accepted applicants.

    Each enrollment runs in its own savepoint (session.begin_nested()):
    - Failed enrollments don't affect successful ones
    - Returns partial success: {succeeded: [...], failed: [...]}
    - If ALL fail → HTTP 422; if some succeed → HTTP 200
    - Max 50 applications per request

    Common failure reasons:
    - Application not in ACCEPTED status
    - Guardian email conflict with existing guardian in different record
    - Missing fee structure for target class
    """
    service = EnrollmentService(db)
    result = await service.bulk_enroll(
        application_ids=data.application_ids,
        generate_invoice=data.generate_invoice,
        enrolled_by=UUID(user["user_id"]),
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
    )

    if result.total_succeeded == 0 and result.total_failed > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "All enrollments failed",
                "failed": result.failed,
            },
        )

    return result
```

---

## 3.9 Class Promotion Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/promotions.py`

```python
"""
SIMS Plus - Class Promotion Endpoints

End-of-year class promotion management. This is the primary tool
for Ghanaian academic year transitions.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    BulkPromotionEntryUpdate,
    BulkPromotionUpdateResponse,
    ClassPromotionCreate,
    ClassPromotionEntryListResponse,
    ClassPromotionListResponse,
    ClassPromotionResponse,
    PromotionEntryUpdate,
    ClassPromotionEntryResponse,
)
from app.services.admissions import ClassPromotionService, ClassPromotionError

router = APIRouter(prefix="/promotions")


def _handle_error(e: ClassPromotionError) -> HTTPException:
    status_map = {
        "NOT_FOUND": 404,
        "ALREADY_EXECUTED": 409,
        "DUPLICATE_BATCH": 409,
        "INVALID_STATUS": 422,
        "VALIDATION_ERROR": 422,
    }
    return HTTPException(status_code=status_map.get(e.code, 400), detail=e.message)


@router.post(
    "",
    response_model=ClassPromotionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create promotion batch",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_batch(
    data: ClassPromotionCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """
    Create a new class promotion batch in draft status.
    Validates both academic years exist and no duplicate batch exists.
    """
    service = ClassPromotionService(db)
    try:
        return await service.create_batch(
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=ClassPromotionListResponse,
    summary="List promotion batches",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_batches(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ClassPromotionListResponse:
    """List promotion batches for the school."""
    service = ClassPromotionService(db)
    return await service.list_batches(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{promotion_id}",
    response_model=ClassPromotionResponse,
    summary="Get promotion batch details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_batch(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """Get batch details with counts."""
    service = ClassPromotionService(db)
    try:
        return await service.get_batch(
            promotion_id=promotion_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.post(
    "/{promotion_id}/preview",
    response_model=ClassPromotionResponse,
    summary="Generate promotion preview",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def generate_preview(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """
    Generate ClassPromotionEntry records for all active students.
    Default: promote to next class; terminal class students: graduate.
    Sets batch status to 'preview'.
    """
    service = ClassPromotionService(db)
    try:
        return await service.generate_preview(
            promotion_id=promotion_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.get(
    "/{promotion_id}/entries",
    response_model=ClassPromotionEntryListResponse,
    summary="List promotion entries",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_entries(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    source_class_id: UUID | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ClassPromotionEntryListResponse:
    """List entries for a batch with optional filters."""
    service = ClassPromotionService(db)
    return await service.get_entries(
        promotion_id=promotion_id,
        tenant_id=UUID(user["tenant_id"]),
        source_class_id=source_class_id,
        action=action,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/entries/{entry_id}",
    response_model=ClassPromotionEntryResponse,
    summary="Update promotion entry",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def update_entry(
    entry_id: UUID,
    data: PromotionEntryUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionEntryResponse:
    """Update a single student's promotion action."""
    service = ClassPromotionService(db)
    try:
        return await service.update_entry(
            entry_id=entry_id,
            data=data,
            tenant_id=UUID(user["tenant_id"]),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.put(
    "/{promotion_id}/entries/bulk",
    response_model=BulkPromotionUpdateResponse,
    summary="Bulk update promotion entries",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def bulk_update_entries(
    promotion_id: UUID,
    data: BulkPromotionEntryUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkPromotionUpdateResponse:
    """Bulk update multiple entries' actions."""
    service = ClassPromotionService(db)
    try:
        return await service.bulk_update_entries(
            promotion_id=promotion_id,
            updates=data.updates,
            tenant_id=UUID(user["tenant_id"]),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)


@router.post(
    "/{promotion_id}/execute",
    response_model=ClassPromotionResponse,
    summary="Execute promotion batch",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def execute_batch(
    promotion_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ClassPromotionResponse:
    """
    Execute the promotion batch. Updates student class assignments.
    Each entry processed in its own savepoint (partial success).
    Status transitions: preview → in_progress → completed/failed.
    """
    service = ClassPromotionService(db)
    try:
        return await service.execute_batch(
            promotion_id=promotion_id,
            tenant_id=UUID(user["tenant_id"]),
            executed_by=UUID(user["user_id"]),
        )
    except ClassPromotionError as e:
        raise _handle_error(e)
```

---

## 3.9b Return Intent Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/return_intents.py`

```python
"""
SIMS Plus - Return Intent Survey Endpoints

Optional intent-to-return survey for boarding/private schools.
Results are advisory only — does NOT block promotion or enrollment.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import (
    ReturnIntentCampaignCreate,
    ReturnIntentCampaignListResponse,
    ReturnIntentCampaignResponse,
    ReturnIntentResponse,
)
from app.services.admissions import ReturnIntentService, ReturnIntentError

router = APIRouter(prefix="/return-intents")


def _handle_error(e: ReturnIntentError) -> HTTPException:
    status_map = {"NOT_FOUND": 404, "ALREADY_SENT": 409, "VALIDATION_ERROR": 422}
    return HTTPException(status_code=status_map.get(e.code, 400), detail=e.message)


@router.post(
    "/campaigns",
    response_model=ReturnIntentCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create return intent campaign",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_campaign(
    data: ReturnIntentCampaignCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentCampaignResponse:
    """Create a return intent survey campaign for existing students."""
    service = ReturnIntentService(db)
    try:
        return await service.create_campaign(
            data=data,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.get(
    "/campaigns",
    response_model=ReturnIntentCampaignListResponse,
    summary="List return intent campaigns",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_campaigns(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReturnIntentCampaignListResponse:
    """List return intent campaigns with stats."""
    service = ReturnIntentService(db)
    return await service.list_campaigns(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/campaigns/{campaign_id}",
    response_model=ReturnIntentCampaignResponse,
    summary="Get campaign details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_campaign(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentCampaignResponse:
    """Get campaign details with response breakdown."""
    service = ReturnIntentService(db)
    try:
        return await service.get_campaign(
            campaign_id=campaign_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.get(
    "/campaigns/{campaign_id}/intents",
    response_model=list[ReturnIntentResponse],
    summary="Get campaign intent list",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_campaign_intents(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    intent_filter: str | None = Query(None, alias="intent"),
) -> list[ReturnIntentResponse]:
    """Get list of students with their intent status."""
    service = ReturnIntentService(db)
    try:
        return await service.get_campaign_intents(
            campaign_id=campaign_id,
            tenant_id=UUID(user["tenant_id"]),
            intent_filter=intent_filter,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.post(
    "/campaigns/{campaign_id}/send",
    response_model=ReturnIntentCampaignResponse,
    summary="Send return intent survey",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def send_campaign(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentCampaignResponse:
    """
    Send SMS/email survey to parents of students in the campaign.
    Creates ReturnIntent records for all active students in target classes.
    Campaign status changes from 'draft' to 'sent'.
    """
    service = ReturnIntentService(db)
    try:
        return await service.send_campaign(
            campaign_id=campaign_id,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)
```

**Parent Portal Integration:** Parents respond to return intent surveys via the parent portal. Add the following endpoint to the existing parent portal endpoints (`backend/app/api/v1/endpoints/parent/`):

```python
# In backend/app/api/v1/endpoints/parent/ — new file or added to existing

@router.post(
    "/return-intent/{intent_id}/respond",
    response_model=ReturnIntentResponse,
    summary="Respond to return intent survey",
)
async def respond_to_return_intent(
    intent_id: UUID,
    data: ReturnIntentRespondRequest,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentResponse:
    """
    Parent responds to a return intent survey for their child.
    Valid intents: returning, not_returning, undecided.
    Parent must be the guardian of the student associated with this intent.
    """
    service = ReturnIntentService(db)
    return await service.respond(
        intent_id=intent_id,
        intent=data.intent,
        reason=data.reason,
        responded_by=UUID(user["user_id"]),
        tenant_id=UUID(user["tenant_id"]),
    )


@router.get(
    "/return-intents",
    response_model=list[ReturnIntentResponse],
    summary="List return intent surveys for parent's children",
)
async def list_my_return_intents(
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ReturnIntentResponse]:
    """Get all pending return intent surveys for the current parent's children."""
    service = ReturnIntentService(db)
    return await service.list_for_parent(
        parent_user_id=UUID(user["user_id"]),
        tenant_id=UUID(user["tenant_id"]),
    )
```

---

## 3.10 Dashboard Endpoints

**File:** `backend/app/api/v1/endpoints/admissions/dashboard.py`

```python
"""
SIMS Plus - Admissions Dashboard Endpoints
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.admissions import DashboardStatsResponse, DemographicsResponse
from app.services.admissions import ApplicationService

router = APIRouter(prefix="/dashboard")


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get admissions pipeline statistics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_stats(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    admission_period_id: UUID | None = Query(None),
) -> DashboardStatsResponse:
    """
    Get admissions pipeline statistics:
    - Total applications count
    - Breakdown by status (pipeline)
    - Breakdown by target class
    - Breakdown by admission period
    - Conversion rate (enrolled / total)
    - Pending decisions count
    - Pending enrollment count (accepted but not enrolled)
    - Recent applications (last 10)
    """
    service = ApplicationService(db)
    return await service.get_dashboard_stats(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        admission_period_id=admission_period_id,
    )


@router.get(
    "/demographics",
    response_model=DemographicsResponse,
    summary="Get applicant demographics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_demographics(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    admission_period_id: UUID | None = Query(None),
) -> DemographicsResponse:
    """
    Get applicant demographic breakdown:
    - Gender distribution
    - Nationality breakdown
    - Previous school distribution
    - Age distribution
    """
    service = ApplicationService(db)
    return await service.get_demographics(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        admission_period_id=admission_period_id,
    )
```

---

## 3.11 Admissions Router Package

**File:** `backend/app/api/v1/endpoints/admissions/__init__.py`

```python
"""
SIMS Plus - Admissions Portal Endpoints Package

Combines all admissions sub-routers into a single router.
Public endpoints are under /public prefix (unauthenticated).
All other endpoints require JWT authentication + admissions permissions.
"""

from fastapi import APIRouter

from .public import router as public_router
from .webhook import router as webhook_router
from .periods import router as periods_router
from .applications import router as applications_router
from .exams import router as exams_router
from .decisions import router as decisions_router
from .enrollment import router as enrollment_router
from .promotions import router as promotions_router
from .return_intents import router as return_intents_router
from .dashboard import router as dashboard_router

router = APIRouter()

# Public endpoints (unauthenticated)
router.include_router(public_router)
router.include_router(webhook_router)

# Admin endpoints (authenticated)
router.include_router(periods_router)
router.include_router(applications_router)
router.include_router(exams_router)
router.include_router(decisions_router)
router.include_router(enrollment_router)
router.include_router(promotions_router)
router.include_router(return_intents_router)
router.include_router(dashboard_router)
```

---

## 3.12 Register in Main Router

**File to modify:** `backend/app/api/v1/router.py`

Add the following import and registration:

```python
# In the import line at the top, add 'admissions':
from app.api.v1.endpoints import auth, tenant, onboarding, academic, schools, media, users, students, staff, attendance, exams, preschool, timetable, finance, notifications, audit, dashboard, boarding, transport, push, parent, teacher, chain, communication_settings, messaging, admissions

# Add after the messaging section:

# =========================
# Admissions Portal
# =========================
api_router.include_router(admissions.router, prefix="/admissions", tags=["Admissions"])
```

---

## Endpoint Summary

### Public Endpoints (8)

| Method | Full Path | Rate Limit |
|--------|-----------|-----------|
| GET | `/api/v1/admissions/public/school-info` | 10/min |
| GET | `/api/v1/admissions/public/periods` | 10/min |
| GET | `/api/v1/admissions/public/periods/{id}/form` | 10/min |
| POST | `/api/v1/admissions/public/applications` | 3/min |
| GET | `/api/v1/admissions/public/applications/{tracking_code}/status` | 10/min |
| POST | `/api/v1/admissions/public/applications/{tracking_code}/documents` | 10/min |
| POST | `/api/v1/admissions/public/applications/{tracking_code}/pay` | 5/min |
| POST | `/api/v1/admissions/public/webhook/paystack` | N/A |

### Admin Endpoints (30)

| Method | Full Path | Permission |
|--------|-----------|-----------|
| POST | `/api/v1/admissions/periods` | admissions.manage |
| GET | `/api/v1/admissions/periods` | admissions.read |
| GET | `/api/v1/admissions/periods/{id}` | admissions.read |
| PUT | `/api/v1/admissions/periods/{id}` | admissions.manage |
| PUT | `/api/v1/admissions/periods/{id}/status` | admissions.manage |
| PUT | `/api/v1/admissions/periods/{id}/form-config` | admissions.manage |
| GET | `/api/v1/admissions/applications` | admissions.read |
| GET | `/api/v1/admissions/applications/{id}` | admissions.read |
| PUT | `/api/v1/admissions/applications/{id}/status` | admissions.review |
| POST | `/api/v1/admissions/applications/{id}/notes` | admissions.review |
| PUT | `/api/v1/admissions/applications/{id}/waive-fee` | admissions.manage |
| PUT | `/api/v1/admissions/applications/{id}/waive-exam` | admissions.manage |
| POST | `/api/v1/admissions/exams` | admissions.manage |
| GET | `/api/v1/admissions/exams` | admissions.read |
| GET | `/api/v1/admissions/exams/{id}` | admissions.read |
| PUT | `/api/v1/admissions/exams/{id}` | admissions.manage |
| POST | `/api/v1/admissions/exams/{id}/register` | admissions.manage |
| POST | `/api/v1/admissions/exams/{id}/results` | admissions.manage |
| POST | `/api/v1/admissions/decisions` | admissions.decide |
| POST | `/api/v1/admissions/decisions/bulk` | admissions.decide |
| POST | `/api/v1/admissions/applications/{id}/enroll` | admissions.enroll |
| POST | `/api/v1/admissions/enroll/bulk` | admissions.enroll |
| POST | `/api/v1/admissions/promotions` | admissions.manage |
| GET | `/api/v1/admissions/promotions` | admissions.read |
| GET | `/api/v1/admissions/promotions/{id}` | admissions.read |
| POST | `/api/v1/admissions/promotions/{id}/preview` | admissions.manage |
| GET | `/api/v1/admissions/promotions/{id}/entries` | admissions.read |
| PUT | `/api/v1/admissions/promotions/entries/{id}` | admissions.manage |
| PUT | `/api/v1/admissions/promotions/{id}/entries/bulk` | admissions.manage |
| POST | `/api/v1/admissions/promotions/{id}/execute` | admissions.manage |
| POST | `/api/v1/admissions/return-intents/campaigns` | admissions.manage |
| GET | `/api/v1/admissions/return-intents/campaigns` | admissions.read |
| GET | `/api/v1/admissions/return-intents/campaigns/{id}` | admissions.read |
| GET | `/api/v1/admissions/return-intents/campaigns/{id}/intents` | admissions.read |
| POST | `/api/v1/admissions/return-intents/campaigns/{id}/send` | admissions.manage |
| GET | `/api/v1/admissions/dashboard/stats` | admissions.read |
| GET | `/api/v1/admissions/dashboard/demographics` | admissions.read |

---

## Type Alias Addition

The `get_public_tenant_db()` dependency needs a type alias. Add to `backend/app/api/deps.py`:

```python
# After the existing type aliases (line ~137):
PublicTenantSession = Annotated[AsyncSession, Depends(get_public_tenant_db)]
```

This allows endpoints to use `db: PublicTenantSession` instead of `db: Annotated[AsyncSession, Depends(get_public_tenant_db)]`.

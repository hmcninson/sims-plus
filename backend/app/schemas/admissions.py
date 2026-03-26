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
    application_fee_amount: Optional[Decimal] = Field(None, ge=0)
    application_fee_required: bool = False
    entrance_exam_required: bool = False
    max_applications: Optional[int] = Field(None, ge=1)
    target_classes: list[UUID] = Field(default_factory=list)
    require_applicant_account: bool = False

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
            raise ValueError(
                "application_fee_amount required when application_fee_required is true"
            )
        return v


class AdmissionPeriodUpdate(BaseSchema):
    """Update admission period request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    application_fee_amount: Optional[Decimal] = Field(None, ge=0)
    application_fee_required: Optional[bool] = None
    entrance_exam_required: Optional[bool] = None
    max_applications: Optional[int] = Field(None, ge=1)
    target_classes: Optional[list[UUID]] = None
    require_applicant_account: Optional[bool] = None


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
    require_applicant_account: bool
    # Phase 2: reminder configuration
    reminder_enabled: bool = False
    reminder_days_before_close: Optional[int] = None
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
        ..., description="JSON Schema object defining custom form fields"
    )
    required_documents: list[str] = Field(
        default_factory=list,
        description="List of required document types (e.g., 'birth_certificate', 'passport_photo')",
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
    require_applicant_account: bool = False


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
    require_applicant_account: bool = False
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
    guardians: list[ApplicationGuardianSubmit] = Field(
        ..., min_length=1, max_length=5
    )
    turnstile_token: str = Field(..., min_length=1)

    @field_validator("guardians")
    @classmethod
    def at_least_one_primary(
        cls, v: list[ApplicationGuardianSubmit],
    ) -> list[ApplicationGuardianSubmit]:
        if not any(g.is_primary for g in v):
            # Auto-set first guardian as primary if none marked
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
    """Public status check response -- minimal data only (no PII beyond first name)."""

    status: str
    applicant_first_name: str
    submitted_at: Optional[datetime] = None
    last_updated_at: datetime


class DocumentUploadRequest(BaseSchema):
    """Request presigned URL for document upload."""

    document_type: str = Field(
        ...,
        pattern="^(birth_certificate|passport_photo|transcript|medical_report|recommendation_letter|other)$",
    )
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(
        ..., pattern="^(application/pdf|image/jpeg|image/png)$"
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
    payment_method: Optional[str] = Field(
        None, pattern="^(mobile_money|card)$"
    )

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: str) -> str:
        """Prevent open redirect -- only allow HTTPS on simsplus.io domains."""
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
    # Phase 2: rejection letter + waitlist fields
    rejection_reason: Optional[str] = None
    rejection_letter_url: Optional[str] = None
    waitlist_rank: Optional[int] = None
    waitlist_notes: Optional[str] = None
    created_at: datetime


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
    date_of_birth: Optional[date] = None  # Nullable for draft applications
    gender: Optional[str] = None  # Nullable for draft applications
    nationality: Optional[str] = None
    target_class_id: Optional[UUID] = None  # Nullable for draft applications
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
    guardians: list[ApplicationGuardianResponse] = []
    documents: list[ApplicationDocumentResponse] = []
    payments: list[ApplicationPaymentResponse] = []
    notes: list[ApplicationNoteResponse] = []
    status_history: list[StatusHistoryResponse] = []
    exam_results: list[ExamResultResponse] = []
    decision: Optional[AdmissionDecisionResponse] = None


class ApplicationListItem(BaseSchema):
    """Application list item (lightweight for table views)."""

    id: UUID
    tracking_code: str
    applicant_first_name: str
    applicant_last_name: str
    date_of_birth: Optional[date] = None  # Nullable for draft applications
    gender: Optional[str] = None  # Nullable for draft applications
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
    """Bulk update entries -- typed for proper Pydantic validation."""

    updates: list[PromotionEntryBulkItem] = Field(
        ...,
        min_length=1,
        max_length=200,
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


# =========================
# Enrollment Gap Closure Phase 2:
# Offer Response, Waitlist, Letters, Reminders
# =========================


class OfferResponseEnum(str, Enum):
    """Applicant's response to an admission offer."""

    ACCEPTED = "accepted"
    DECLINED = "declined"


class OfferResponseRequest(BaseSchema):
    """Accept or decline an admission offer."""

    response: OfferResponseEnum
    notes: Optional[str] = Field(None, max_length=2000)


class OfferDetailResponse(BaseSchema):
    """Full offer details for applicant portal."""

    application_id: UUID
    applicant_name: str
    tracking_code: str
    school_name: str
    offered_class_name: Optional[str] = None
    decision_type: str
    decision_date: date
    conditions: Optional[str] = None
    response_deadline: Optional[date] = None
    decision_letter_url: Optional[str] = None
    offer_responded_at: Optional[datetime] = None
    offer_response: Optional[str] = None
    offer_response_notes: Optional[str] = None
    is_expired: bool = False


class WaitlistRankUpdate(BaseSchema):
    """Update waitlist rank for a single decision."""

    rank: int = Field(..., ge=1, le=9999)


class WaitlistReorderRequest(BaseSchema):
    """Bulk reorder waitlist by specifying ordered decision IDs."""

    period_id: UUID
    ordered_decision_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Decision IDs in desired rank order (index 0 = rank 1)",
    )


class WaitlistPromoteRequest(BaseSchema):
    """Promote a waitlisted applicant to offered status."""

    offered_class_id: UUID
    response_deadline: Optional[date] = None
    conditions: Optional[str] = None


class WaitlistEntryResponse(BaseSchema):
    """Waitlist entry with application details."""

    decision_id: UUID
    application_id: UUID
    applicant_name: str
    tracking_code: str
    target_class_name: Optional[str] = None
    waitlist_rank: Optional[int] = None
    waitlist_notes: Optional[str] = None
    decision_date: date
    created_at: datetime


class WaitlistListResponse(BaseSchema):
    """Paginated waitlist."""

    items: list[WaitlistEntryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class GenerateLetterResponse(BaseSchema):
    """Response after generating a letter PDF."""

    decision_id: UUID
    letter_url: str
    letter_type: str  # "admission" or "rejection"


class ReminderConfigUpdate(BaseSchema):
    """Update reminder settings on an admission period."""

    reminder_enabled: bool
    reminder_days_before_close: Optional[int] = Field(None, ge=1, le=90)

    @field_validator("reminder_days_before_close")
    @classmethod
    def days_required_when_enabled(cls, v: int | None, info) -> int | None:
        enabled = info.data.get("reminder_enabled")
        if enabled and v is None:
            raise ValueError(
                "reminder_days_before_close is required when reminder_enabled is True"
            )
        return v

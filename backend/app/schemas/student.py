"""
SIMS Plus - Student and Guardian Schemas

Pydantic schemas for student management endpoints.
"""

from datetime import date, datetime
from datetime import date as date_type
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, EmailStr


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Guardian Schemas
# =========================


class GuardianBase(BaseSchema):
    """Base guardian fields."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    occupation: Optional[str] = Field(None, max_length=200)
    workplace: Optional[str] = Field(None, max_length=200)
    work_phone: Optional[str] = Field(None, max_length=20)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class GuardianCreate(GuardianBase):
    """Create guardian request."""

    pass


class GuardianUpdate(BaseSchema):
    """Update guardian request."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    phone_secondary: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    occupation: Optional[str] = Field(None, max_length=200)
    workplace: Optional[str] = Field(None, max_length=200)
    work_phone: Optional[str] = Field(None, max_length=20)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class GuardianResponse(GuardianBase):
    """Guardian response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        """Get the guardian's full name."""
        return f"{self.first_name} {self.last_name}"


class GuardianListResponse(BaseSchema):
    """Guardian with student count for listing."""

    id: UUID
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    occupation: Optional[str] = None
    student_count: int = 0


# =========================
# Student-Guardian Link Schemas
# =========================


class StudentGuardianCreate(BaseSchema):
    """Link student to guardian request."""

    guardian_id: UUID
    relationship: str = Field(
        ...,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
        description="Relationship to student",
    )
    is_primary: bool = False
    is_emergency_contact: bool = True
    can_pickup: bool = True


class StudentGuardianWithNewGuardian(BaseSchema):
    """Create new guardian and link to student."""

    guardian: GuardianCreate
    relationship: str = Field(
        ...,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
    )
    is_primary: bool = False
    is_emergency_contact: bool = True
    can_pickup: bool = True


class StudentGuardianUpdate(BaseSchema):
    """Update student-guardian link."""

    relationship: Optional[str] = Field(
        None,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
    )
    is_primary: Optional[bool] = None
    is_emergency_contact: Optional[bool] = None
    can_pickup: Optional[bool] = None


class StudentGuardianResponse(BaseSchema):
    """Student-guardian link response."""

    id: UUID
    student_id: UUID
    guardian_id: UUID
    relationship: str
    is_primary: bool
    is_emergency_contact: bool
    can_pickup: bool
    guardian: GuardianResponse
    created_at: datetime
    updated_at: datetime


# =========================
# Student Schemas
# =========================


class StudentBase(BaseSchema):
    """Base student fields."""

    student_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="System-generated unique student ID (e.g., STU-2026-001)",
    )
    previous_student_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Student ID from previous/external system (for migration reference)",
    )
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    nhis_number: Optional[str] = Field(None, max_length=50)
    school_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    admission_date: Optional[date] = None
    admission_number: Optional[str] = Field(None, max_length=50)
    status: str = Field(
        default="active",
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    is_boarder: bool = False
    blood_group: Optional[str] = Field(None, max_length=10)
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date) -> date:
        """Ensure date of birth is not in the future."""
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class StudentCreate(BaseSchema):
    """Create student request.

    Note: student_id is always auto-generated by the system.
    Use previous_student_id to store IDs from external/previous systems.
    """

    # previous_student_id for migration from other systems
    previous_student_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Student ID from previous/external system (for migration reference)",
    )
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    nhis_number: Optional[str] = Field(None, max_length=50)
    school_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    admission_date: Optional[date] = None
    admission_number: Optional[str] = Field(None, max_length=50)
    status: str = Field(
        default="active",
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    is_boarder: bool = False
    blood_group: Optional[str] = Field(None, max_length=10)
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    birth_certificate_number: Optional[str] = Field(None, max_length=100)

    # Optional: create guardians at the same time
    guardians: Optional[list[StudentGuardianWithNewGuardian]] = Field(
        default=None,
        description="Guardians to create and link to student",
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date) -> date:
        """Ensure date of birth is not in the future."""
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class StudentUpdate(BaseSchema):
    """Update student request.

    Note: student_id cannot be changed as it's system-generated.
    """

    # previous_student_id can be updated
    previous_student_id: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    ghana_card_number: Optional[str] = Field(None, max_length=50)
    nhis_number: Optional[str] = Field(None, max_length=50)
    school_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    admission_date: Optional[date] = None
    admission_number: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(
        None,
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    is_boarder: Optional[bool] = None
    blood_group: Optional[str] = Field(None, max_length=10)
    medical_conditions: Optional[str] = None
    allergies: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    birth_certificate_number: Optional[str] = Field(None, max_length=100)
    # Preschool enrollment session type
    enrollment_session: Optional[str] = Field(
        None,
        pattern="^(half_day_morning|half_day_afternoon|full_day|extended)$",
    )


class StudentResponse(StudentBase):
    """Student response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    birth_certificate_number: Optional[str] = None
    structured_medical: Optional[dict] = None
    # Preschool fields
    enrollment_session: Optional[str] = None
    dietary_requirements: Optional[dict] = None

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        """Calculate the student's age."""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class StudentWithGuardiansResponse(StudentResponse):
    """Student with guardians."""

    guardians: list[StudentGuardianResponse] = []
    school_name: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None


class StudentListResponse(BaseSchema):
    """Simplified student response for listing."""

    id: UUID
    student_id: str
    previous_student_id: Optional[str] = None
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: str
    date_of_birth: date
    status: str
    class_id: Optional[UUID] = None
    class_name: Optional[str] = None
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    photo_url: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"


class StudentBulkCreate(BaseSchema):
    """Bulk create students request."""

    students: list[StudentCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of students to create (max 100)",
    )


class StudentBulkResponse(BaseSchema):
    """Bulk create response."""

    created: int
    failed: int
    errors: list[dict] = []


class StudentImportResponse(BaseSchema):
    """File import response."""

    total_rows: int
    created: int
    failed: int
    errors: list[dict] = []
    preview: list[dict] = Field(
        default=[],
        description="Preview of first few rows (only in preview mode)",
    )


class StudentImportColumnMapping(BaseSchema):
    """Column mapping for student import.

    Note: student_id from import file is mapped to previous_student_id.
    The system always auto-generates the actual student_id.
    """

    previous_student_id: Optional[str] = Field(
        None,
        description="Column name for previous_student_id (IDs from external system)",
    )
    first_name: Optional[str] = Field(None, description="Column name for first_name")
    middle_name: Optional[str] = Field(None, description="Column name for middle_name")
    last_name: Optional[str] = Field(None, description="Column name for last_name")
    date_of_birth: Optional[str] = Field(None, description="Column name for date_of_birth")
    gender: Optional[str] = Field(None, description="Column name for gender")
    email: Optional[str] = Field(None, description="Column name for email")
    phone: Optional[str] = Field(None, description="Column name for phone")
    address: Optional[str] = Field(None, description="Column name for address")
    city: Optional[str] = Field(None, description="Column name for city")
    region: Optional[str] = Field(None, description="Column name for region")
    class_name: Optional[str] = Field(None, description="Column name for class_name (will lookup class_id)")
    is_boarder: Optional[str] = Field(None, description="Column name for is_boarder")


class StudentStatsResponse(BaseSchema):
    """Student statistics response."""

    total: int
    active: int
    inactive: int
    graduated: int
    transferred: int
    withdrawn: int
    suspended: int
    male: int
    female: int
    boarders: int
    day_students: int


class StudentPromotionRequest(BaseSchema):
    """Bulk promote students from one class to another."""

    from_class_id: UUID
    to_class_id: UUID
    student_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of student UUIDs to promote",
    )


class StudentPromotionResponse(BaseSchema):
    """Response for student promotion."""

    promoted: int
    failed: int
    errors: list[dict] = []


class StudentFilterParams(BaseSchema):
    """Student filter parameters."""

    search: Optional[str] = Field(None, description="Search by name or student ID")
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    school_id: Optional[UUID] = None
    status: Optional[str] = Field(
        None,
        pattern="^(active|inactive|graduated|transferred|withdrawn|suspended)$",
    )
    gender: Optional[str] = Field(None, pattern="^(male|female)$")
    is_boarder: Optional[bool] = None


# =========================
# Class History Schemas
# =========================


class StudentClassHistoryResponse(BaseSchema):
    """Response for a single class assignment history record."""

    id: UUID
    student_id: UUID
    school_id: UUID
    class_id: UUID
    section_id: Optional[UUID] = None
    academic_year_id: UUID
    enrolled_date: date_type
    left_date: Optional[date_type] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    academic_year_name: Optional[str] = None


class StudentClassHistoryListResponse(BaseSchema):
    """Paginated list of class assignment history records."""

    records: list[StudentClassHistoryResponse]
    total: int


# =========================
# Status Change Schemas
# =========================


class StudentStatusChangeResponse(BaseSchema):
    """Response for a single status change record."""

    id: UUID
    student_id: UUID
    school_id: UUID
    from_status: Optional[str] = None
    to_status: str
    reason: Optional[str] = None
    effective_date: date_type
    performed_by: Optional[UUID] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None
    performed_by_name: Optional[str] = None


class StudentStatusChangeListResponse(BaseSchema):
    """Paginated list of status change records."""

    records: list[StudentStatusChangeResponse]
    total: int


# =========================
# Enrollment Analytics Schemas
# =========================


class ClassEnrollmentBreakdown(BaseSchema):
    """Enrollment breakdown for a single class."""

    class_id: UUID
    class_name: str
    total: int
    male: int
    female: int
    boarders: int
    day_students: int


class EnrollmentTrend(BaseSchema):
    """Enrollment trend for a single academic year."""

    academic_year_id: UUID
    academic_year_name: str
    total_enrolled: int
    new_enrollments: int
    withdrawals: int
    transfers_out: int
    graduations: int


class EnrollmentAnalyticsResponse(BaseSchema):
    """Enhanced enrollment analytics response."""

    total_active: int
    total_inactive: int
    total_graduated: int
    total_transferred: int
    total_withdrawn: int
    total_suspended: int
    by_class: list[ClassEnrollmentBreakdown]
    trends: list[EnrollmentTrend]
    attrition_rate: float
    new_enrollment_rate: float


# =========================
# Lifecycle Schemas (Withdrawal / Transfer)
# =========================


class OutstandingInvoiceSummary(BaseSchema):
    """Summary of a single outstanding invoice."""

    invoice_id: UUID
    invoice_number: str
    amount: float
    balance: float
    status: str
    due_date: Optional[date_type] = None


class OutstandingFeeCheckResponse(BaseSchema):
    """Response for outstanding fee check."""

    has_outstanding: bool
    total_outstanding: float
    invoice_count: int
    invoices: list[OutstandingInvoiceSummary]


class WithdrawalInitiateRequest(BaseSchema):
    """Request to initiate student withdrawal."""

    reason: str = Field(..., min_length=5, max_length=1000)
    effective_date: date_type
    fee_override: bool = False

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: date_type) -> date_type:
        """Effective date must not be in the past."""
        if v < date.today():
            raise ValueError("Effective date cannot be in the past")
        return v


class WithdrawalClearanceResponse(BaseSchema):
    """Response for a withdrawal/transfer clearance record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    status_change_id: Optional[UUID] = None
    type: str
    library_cleared: bool
    finance_cleared: bool
    property_cleared: bool
    boarding_cleared: Optional[bool] = None
    outstanding_fees: Optional[float] = None
    fee_override: bool
    notes: Optional[str] = None
    is_complete: bool
    cleared_by: Optional[UUID] = None
    cleared_at: Optional[str] = None
    created_at: str


class WithdrawalClearanceUpdateRequest(BaseSchema):
    """Request to update clearance checklist items."""

    library_cleared: Optional[bool] = None
    finance_cleared: Optional[bool] = None
    property_cleared: Optional[bool] = None
    boarding_cleared: Optional[bool] = None
    notes: Optional[str] = None


class WithdrawalCompleteResponse(BaseSchema):
    """Response for completing a withdrawal."""

    student_id: UUID
    status: str
    clearance_completed: bool
    withdrawal_letter_available: bool


class TransferInitiateRequest(BaseSchema):
    """Request to initiate student external transfer."""

    destination_school: str = Field(..., min_length=2, max_length=255)
    reason: str = Field(..., min_length=5, max_length=1000)
    effective_date: date_type
    fee_override: bool = False

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: date_type) -> date_type:
        """Effective date must not be in the past."""
        if v < date.today():
            raise ValueError("Effective date cannot be in the past")
        return v


class ChainTransferRequest(BaseSchema):
    """Request to transfer a student within a school chain."""

    to_school_id: UUID
    to_class_id: UUID
    to_section_id: Optional[UUID] = None
    reason: str = Field(..., min_length=5, max_length=1000)
    effective_date: date_type
    fee_override: bool = False

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: date_type) -> date_type:
        """Effective date must not be in the past."""
        if v < date.today():
            raise ValueError("Effective date cannot be in the past")
        return v


class ChainTransferResponse(BaseSchema):
    """Response for a chain transfer."""

    student_id: UUID
    from_school_id: UUID
    to_school_id: UUID
    to_class_id: UUID
    status: str  # Should remain "active" for chain transfers


# =========================
# Document Schemas
# =========================


class StudentDocumentUploadResponse(BaseSchema):
    """Response after uploading a student document."""

    id: UUID
    student_id: UUID
    document_type: str
    title: str
    file_size: int
    mime_type: str
    uploaded_by: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: str


class StudentDocumentListResponse(BaseSchema):
    """Response for listing student documents."""

    documents: list[StudentDocumentUploadResponse]
    total: int
    total_size_bytes: int


class StudentDocumentDownloadResponse(BaseSchema):
    """Response containing a presigned download URL."""

    download_url: str
    expires_in: int


# =========================
# Previous School Schemas
# =========================


class PreviousSchoolCreate(BaseSchema):
    """Create a previous school record."""

    school_name: str = Field(..., min_length=2, max_length=255)
    school_address: Optional[str] = None
    last_class: Optional[str] = Field(None, max_length=100)
    years_attended: Optional[str] = Field(None, max_length=50)
    transfer_reason: Optional[str] = None
    leaving_certificate_ref: Optional[str] = Field(None, max_length=100)


class PreviousSchoolUpdate(BaseSchema):
    """Update a previous school record."""

    school_name: Optional[str] = Field(None, min_length=2, max_length=255)
    school_address: Optional[str] = None
    last_class: Optional[str] = Field(None, max_length=100)
    years_attended: Optional[str] = Field(None, max_length=50)
    transfer_reason: Optional[str] = None
    leaving_certificate_ref: Optional[str] = Field(None, max_length=100)


class PreviousSchoolResponse(BaseSchema):
    """Response for a previous school record."""

    id: UUID
    student_id: UUID
    school_name: str
    school_address: Optional[str] = None
    last_class: Optional[str] = None
    years_attended: Optional[str] = None
    transfer_reason: Optional[str] = None
    leaving_certificate_ref: Optional[str] = None
    created_at: str


# =========================
# Structured Medical Schemas (F-13)
# =========================


class MedicalCondition(BaseSchema):
    """A single medical condition entry."""

    name: str = Field(..., min_length=1, max_length=200)
    severity: Optional[str] = Field(None, pattern="^(mild|moderate|severe)$")
    diagnosed_date: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)


class MedicalAllergy(BaseSchema):
    """A single allergy entry."""

    name: str = Field(..., min_length=1, max_length=200)
    severity: Optional[str] = Field(None, pattern="^(mild|moderate|severe)$")
    reaction: Optional[str] = Field(None, max_length=500)


class MedicalMedication(BaseSchema):
    """A single medication entry."""

    name: str = Field(..., min_length=1, max_length=200)
    dosage: Optional[str] = Field(None, max_length=200)
    frequency: Optional[str] = Field(None, max_length=200)
    prescriber: Optional[str] = Field(None, max_length=200)


class StructuredMedical(BaseSchema):
    """Structured medical information for a student."""

    conditions: list[MedicalCondition] = Field(default=[], max_length=50)
    allergies: list[MedicalAllergy] = Field(default=[], max_length=50)
    medications: list[MedicalMedication] = Field(default=[], max_length=50)
    emergency_protocol: Optional[str] = Field(None, max_length=2000)
    doctor_name: Optional[str] = Field(None, max_length=200)
    doctor_phone: Optional[str] = Field(None, max_length=20)
    hospital: Optional[str] = Field(None, max_length=200)
    blood_group: Optional[str] = Field(None, pattern="^(A|B|AB|O)[+-]$")

    @field_validator("emergency_protocol")
    @classmethod
    def sanitize_emergency_protocol(cls, v: str | None) -> str | None:
        """F-13: Sanitize HTML in emergency protocol to prevent injection."""
        if v:
            import nh3
            return nh3.clean(v)
        return v


# =========================
# Promotion Rule Schemas
# =========================


class PromotionRuleCreate(BaseSchema):
    """Create a promotion rule for auto-populating promotion batch decisions.

    At least one criterion (min_average, min_attendance_pct, or
    core_subject_pass_count) must be provided.  When class_id is None
    the rule is the school-wide default; a non-None class_id targets a
    specific class and takes precedence.
    """

    school_id: UUID
    academic_year_id: UUID
    class_id: Optional[UUID] = None
    min_average: Optional[float] = Field(None, ge=0, le=100)
    min_attendance_pct: Optional[float] = Field(None, ge=0, le=100)
    core_subject_pass_count: Optional[int] = Field(None, ge=0)
    pass_mark: Optional[float] = Field(50.0, ge=0, le=100)
    auto_apply: bool = False

    @model_validator(mode="after")
    def at_least_one_criterion(self) -> "PromotionRuleCreate":
        """Ensure the rule defines at least one meaningful threshold."""
        if (
            self.min_average is None
            and self.min_attendance_pct is None
            and self.core_subject_pass_count is None
        ):
            raise ValueError("At least one criterion must be set")
        return self


class PromotionRuleUpdate(BaseSchema):
    """Update promotion rule fields.  All fields are optional."""

    min_average: Optional[float] = Field(None, ge=0, le=100)
    min_attendance_pct: Optional[float] = Field(None, ge=0, le=100)
    core_subject_pass_count: Optional[int] = Field(None, ge=0)
    pass_mark: Optional[float] = Field(None, ge=0, le=100)
    auto_apply: Optional[bool] = None
    is_active: Optional[bool] = None


class PromotionRuleResponse(BaseSchema):
    """Response for a single promotion rule."""

    id: UUID
    school_id: UUID
    academic_year_id: UUID
    class_id: Optional[UUID] = None
    min_average: Optional[float] = None
    min_attendance_pct: Optional[float] = None
    core_subject_pass_count: Optional[int] = None
    pass_mark: Optional[float] = None
    auto_apply: bool
    is_active: bool
    created_at: str
    class_name: Optional[str] = None
    academic_year_name: Optional[str] = None


class PromotionRuleEvaluationResult(BaseSchema):
    """Per-student result of promotion rule evaluation."""

    student_id: UUID
    student_name: str
    recommended_action: str  # "promote" or "repeat"
    reason: str
    term_average: Optional[float] = None
    attendance_pct: Optional[float] = None
    core_subjects_passed: Optional[int] = None
    criteria_met: dict


# Update forward references
StudentWithGuardiansResponse.model_rebuild()
StudentGuardianResponse.model_rebuild()

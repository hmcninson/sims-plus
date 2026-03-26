"""
SIMS Plus - Parent Portal Schemas

Pydantic schemas for parent portal endpoints (Sprint 13-14).
Covers: child views, grades, attendance, finance, communication,
payment integration, notification preferences, and invitations.
"""

from datetime import date, datetime, time
from decimal import Decimal
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
# Enums (schema-level)
# =========================


class AttendanceStatusEnum(str, Enum):
    """Attendance status for parent-facing views."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    SICK = "sick"


class NoteTypeEnum(str, Enum):
    """Types of teacher notes."""

    POSITIVE = "positive"
    CONCERN = "concern"
    INFORMATION = "information"
    ACTION_REQUIRED = "action_required"


class AnnouncementPriorityEnum(str, Enum):
    """Announcement priority levels."""

    NORMAL = "normal"
    IMPORTANT = "important"
    URGENT = "urgent"


class AnnouncementTargetEnum(str, Enum):
    """Target audience for announcements."""

    ALL_PARENTS = "all_parents"
    SPECIFIC_CLASS = "specific_class"
    SPECIFIC_HOUSE = "specific_house"
    BOARDING_PARENTS = "boarding_parents"
    TRANSPORT_PARENTS = "transport_parents"


class PaymentMethodEnum(str, Enum):
    """Payment methods available to parents."""

    MOBILE_MONEY = "mobile_money"
    CARD = "card"


class ActivityTypeEnum(str, Enum):
    """Types of activity items shown on parent dashboard."""

    GRADE = "grade"
    ATTENDANCE = "attendance"
    FINANCE = "finance"
    ANNOUNCEMENT = "announcement"
    REPORT = "report"
    NOTE = "note"


# =========================
# Child/Student Schemas (read-only for parents)
# =========================


class ChildSummary(BaseSchema):
    """Lightweight child summary used across multiple parent views."""

    id: UUID
    first_name: str
    last_name: str
    photo_url: Optional[str] = None
    class_name: Optional[str] = None
    section_name: Optional[str] = None
    admission_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    # School context -- useful for chain tenants where a parent has
    # children across different schools within the same organization
    school_id: Optional[UUID] = None
    school_name: Optional[str] = None


class ChildDetail(ChildSummary):
    """Extended child detail with enrollment and academic context."""

    enrollment_status: Optional[str] = None
    class_teacher_name: Optional[str] = None
    current_term: Optional[str] = None
    academic_year: Optional[str] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None


class ChildQuickStats(BaseSchema):
    """Quick statistics for a single child, shown on parent dashboard."""

    attendance_rate: Optional[float] = None
    average_score: Optional[Decimal] = None
    class_position: Optional[int] = None
    class_size: Optional[int] = None
    outstanding_balance: Decimal = Decimal("0.00")


class ChildOverview(BaseSchema):
    """Full overview for a child combining summary, stats, and activity."""

    child: ChildDetail
    stats: ChildQuickStats
    recent_activity: list["ActivityItem"] = []


# =========================
# Grades Schemas
# =========================


class SubjectGrade(BaseSchema):
    """Grade for a single subject within a term."""

    subject_name: str
    ca_score: Optional[Decimal] = None
    ca_max: Optional[Decimal] = None
    exam_score: Optional[Decimal] = None
    exam_max: Optional[Decimal] = None
    total: Optional[Decimal] = None
    grade: Optional[str] = None
    remark: Optional[str] = None
    class_average: Optional[Decimal] = None
    position: Optional[int] = None


class TermGradesOverall(BaseSchema):
    """Aggregate grade summary for a term."""

    total_marks: Optional[Decimal] = None
    average: Optional[Decimal] = None
    class_position: Optional[int] = None
    class_size: Optional[int] = None
    # Curriculum-specific aggregate metrics (read from TermReport)
    gpa: Optional[Decimal] = None
    weighted_gpa: Optional[Decimal] = None
    cumulative_gpa: Optional[Decimal] = None
    honor_roll: Optional[bool] = None
    total_credits_earned: Optional[Decimal] = None
    ib_total_points: Optional[int] = None
    french_mention: Optional[str] = None


class TermGrades(BaseSchema):
    """Complete term grades for a student."""

    student: ChildSummary
    term_id: UUID
    term_name: str
    academic_year: Optional[str] = None
    subjects: list[SubjectGrade] = []
    overall: TermGradesOverall
    # Curriculum context — allows frontend to switch display modes
    curriculum_type: str = "ges"
    score_display_mode: str = "grade_and_score"
    # True when aggregate metrics come from a published TermReport
    report_generated: bool = False


class GradeTrend(BaseSchema):
    """Single data point for charting grade trends across terms."""

    term_id: UUID
    term_name: str
    average: Optional[Decimal] = None
    position: Optional[int] = None
    class_size: Optional[int] = None
    # Curriculum-appropriate metric (e.g. "gpa", "ib_total_points", "average_score")
    metric: str = "average_score"
    value: Optional[float] = None
    label: str = ""


class AssessmentScore(BaseSchema):
    """Individual assessment score (CA component) for parent view."""

    id: UUID
    subject_name: str
    assessment_name: str
    score: Optional[Decimal] = None
    max_score: Decimal
    date: date


# =========================
# Finance Schemas (parent-facing)
# =========================


class ParentInvoiceSummary(BaseSchema):
    """Compact invoice summary for parent invoice lists."""

    id: UUID
    invoice_number: str
    term_name: Optional[str] = None
    total_amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    status: str
    due_date: Optional[date] = None
    created_at: datetime


class ParentInvoiceItem(BaseSchema):
    """Single line item on a parent-facing invoice."""

    fee_type_name: str
    amount: Decimal
    description: Optional[str] = None


class ParentPaymentSummary(BaseSchema):
    """Payment record as shown to parents."""

    id: UUID
    amount: Decimal
    method: str
    reference_number: Optional[str] = None
    receipt_number: Optional[str] = None
    date: datetime
    invoice_number: Optional[str] = None


class ParentInvoiceDetail(ParentInvoiceSummary):
    """Full invoice detail with line items, payments, and credit notes."""

    items: list[ParentInvoiceItem] = []
    payments: list[ParentPaymentSummary] = []
    scholarship_discount: Decimal = Decimal("0.00")
    credit_notes_applied: Decimal = Decimal("0.00")


class FeeStatement(BaseSchema):
    """Complete fee statement for a student in a given term."""

    student: ChildSummary
    term_name: Optional[str] = None
    total_billed: Decimal = Decimal("0.00")
    total_paid: Decimal = Decimal("0.00")
    total_credits: Decimal = Decimal("0.00")
    outstanding_balance: Decimal = Decimal("0.00")
    invoices: list[ParentInvoiceSummary] = []


# =========================
# Attendance Schemas (parent-facing)
# =========================


class AttendanceDay(BaseSchema):
    """Attendance record for a single day."""

    date: date
    status: AttendanceStatusEnum
    note: Optional[str] = None


class AttendanceSummary(BaseSchema):
    """Monthly attendance summary with daily breakdown."""

    student: ChildSummary
    month: str = Field(
        ...,
        description="Month label in YYYY-MM format",
        pattern=r"^\d{4}-\d{2}$",
    )
    total_school_days: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    rate: float = 0.0
    daily: list[AttendanceDay] = []


class AttendanceTrend(BaseSchema):
    """Single data point for charting attendance rate over months."""

    month: str = Field(
        ...,
        description="Month label in YYYY-MM format",
        pattern=r"^\d{4}-\d{2}$",
    )
    rate: float = 0.0
    present: int = 0
    total_days: int = 0


# =========================
# Communication Schemas - Announcements
# =========================


class AnnouncementResponse(BaseSchema):
    """School announcement as seen by parents."""

    id: UUID
    title: str
    content: str
    author_name: Optional[str] = None
    priority: AnnouncementPriorityEnum = AnnouncementPriorityEnum.NORMAL
    target_audience: AnnouncementTargetEnum = AnnouncementTargetEnum.ALL_PARENTS
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_pinned: bool = False
    attachment_url: Optional[str] = None
    created_at: Optional[datetime] = None


class AnnouncementCreate(BaseSchema):
    """Create a new school announcement (staff/admin use)."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)
    target_audience: AnnouncementTargetEnum = AnnouncementTargetEnum.ALL_PARENTS
    target_class_id: Optional[UUID] = None
    target_house_id: Optional[UUID] = None
    priority: AnnouncementPriorityEnum = AnnouncementPriorityEnum.NORMAL
    expires_at: Optional[datetime] = None
    is_pinned: bool = False
    attachment_url: Optional[str] = Field(None, max_length=500)

    @field_validator("attachment_url")
    @classmethod
    def validate_attachment_url_scheme(cls, v: Optional[str]) -> Optional[str]:
        """Block dangerous URL schemes (javascript:, data:, etc.)."""
        if v is not None:
            v = v.strip()
            if not v.lower().startswith(("https://", "http://")):
                raise ValueError("attachment_url must use https:// or http:// scheme")
        return v

    @field_validator("target_class_id")
    @classmethod
    def class_required_for_class_audience(cls, v: Optional[UUID], info) -> Optional[UUID]:
        audience = info.data.get("target_audience")
        if audience == AnnouncementTargetEnum.SPECIFIC_CLASS and v is None:
            raise ValueError("target_class_id is required when target_audience is 'specific_class'")
        return v

    @field_validator("target_house_id")
    @classmethod
    def house_required_for_house_audience(cls, v: Optional[UUID], info) -> Optional[UUID]:
        audience = info.data.get("target_audience")
        if audience == AnnouncementTargetEnum.SPECIFIC_HOUSE and v is None:
            raise ValueError("target_house_id is required when target_audience is 'specific_house'")
        return v


class AnnouncementUpdate(BaseSchema):
    """Update an existing announcement. All fields optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    target_audience: Optional[AnnouncementTargetEnum] = None
    target_class_id: Optional[UUID] = None
    target_house_id: Optional[UUID] = None
    priority: Optional[AnnouncementPriorityEnum] = None
    expires_at: Optional[datetime] = None
    is_pinned: Optional[bool] = None
    attachment_url: Optional[str] = Field(None, max_length=500)

    @field_validator("attachment_url")
    @classmethod
    def validate_attachment_url_scheme(cls, v: Optional[str]) -> Optional[str]:
        """Block dangerous URL schemes (javascript:, data:, etc.)."""
        if v is not None:
            v = v.strip()
            if not v.lower().startswith(("https://", "http://")):
                raise ValueError("attachment_url must use https:// or http:// scheme")
        return v


# =========================
# Communication Schemas - Teacher Notes
# =========================


class TeacherNoteResponse(BaseSchema):
    """Teacher note as seen by parents or staff."""

    id: UUID
    student_id: UUID
    student_name: Optional[str] = None
    teacher_name: Optional[str] = None
    subject_name: Optional[str] = None
    note_type: NoteTypeEnum
    content: str
    is_visible_to_parent: bool = True
    parent_acknowledged: bool = False
    parent_acknowledged_at: Optional[datetime] = None
    created_at: datetime


class TeacherNoteCreate(BaseSchema):
    """Create a teacher note for a student."""

    student_id: UUID
    subject_id: Optional[UUID] = None
    note_type: NoteTypeEnum
    content: str = Field(..., min_length=1, max_length=5000)
    is_visible_to_parent: bool = True


class TeacherNoteUpdate(BaseSchema):
    """Update an existing teacher note. All fields optional."""

    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    note_type: Optional[NoteTypeEnum] = None
    is_visible_to_parent: Optional[bool] = None


# =========================
# Payment Integration Schemas
# =========================


class PaymentInitiateRequest(BaseSchema):
    """Initiate an online payment from the parent portal."""

    invoice_id: UUID
    amount: Decimal = Field(..., gt=0, description="Amount to pay towards the invoice")
    method: PaymentMethodEnum
    phone: Optional[str] = Field(
        None,
        min_length=10,
        max_length=20,
        description="Phone number for Mobile Money (required when method is mobile_money)",
    )

    @field_validator("phone")
    @classmethod
    def phone_required_for_momo(cls, v: Optional[str], info) -> Optional[str]:
        method = info.data.get("method")
        if method == PaymentMethodEnum.MOBILE_MONEY and not v:
            raise ValueError("Phone number is required for mobile money payments")
        return v


class PaymentInitiateResponse(BaseSchema):
    """Response after initiating an online payment."""

    authorization_url: Optional[str] = None
    reference: str
    access_code: Optional[str] = None


class PaymentVerifyResponse(BaseSchema):
    """Response after verifying a payment transaction."""

    status: str
    amount: Decimal
    method: str
    receipt_number: Optional[str] = None
    invoice_number: Optional[str] = None
    balance_remaining: Decimal = Decimal("0.00")


# =========================
# Notification Preferences Schemas
# =========================


class NotificationPreferencesResponse(BaseSchema):
    """Current notification preferences for a parent."""

    id: UUID
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False
    notify_attendance: bool = True
    notify_grades: bool = True
    notify_finance: bool = True
    notify_announcements: bool = True
    notify_transport: bool = False
    notify_boarding: bool = True
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


class NotificationPreferencesUpdate(BaseSchema):
    """Update notification preferences. All fields optional (PATCH semantics)."""

    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    notify_attendance: Optional[bool] = None
    notify_grades: Optional[bool] = None
    notify_finance: Optional[bool] = None
    notify_announcements: Optional[bool] = None
    notify_transport: Optional[bool] = None
    notify_boarding: Optional[bool] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


# =========================
# Parent Onboarding / Invitation Schemas
# =========================


class ParentInviteRequest(BaseSchema):
    """Invite a single parent to the portal."""

    email: EmailStr
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    relationship: str = Field(
        ...,
        pattern="^(father|mother|guardian|grandfather|grandmother|uncle|aunt|sibling|other)$",
        description="Relationship to student",
    )


class ParentInviteWithStudent(ParentInviteRequest):
    """Parent invite that also links to a specific student."""

    student_id: UUID


class BulkParentInviteRequest(BaseSchema):
    """Invite multiple parents in a single operation."""

    invitations: list[ParentInviteWithStudent] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="List of parent invitations (max 200 per batch)",
    )


class BulkParentInviteError(BaseSchema):
    """Error detail for a failed invitation within a bulk operation."""

    index: int
    email: str
    error: str


class BulkParentInviteResponse(BaseSchema):
    """Result of a bulk parent invitation operation."""

    created: int = 0
    linked: int = 0
    errors: list[BulkParentInviteError] = []


class ParentProfileCompletion(BaseSchema):
    """Profile completion request for newly-invited parents."""

    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = True


# =========================
# Activity / Dashboard Schemas
# =========================


class ActivityItem(BaseSchema):
    """Generic activity item for the parent activity feed."""

    type: ActivityTypeEnum
    title: str
    description: str
    date: datetime
    link: Optional[str] = None


class UpcomingEvent(BaseSchema):
    """Upcoming event shown on the parent dashboard."""

    title: str
    date: date
    event_type: Optional[str] = None
    description: Optional[str] = None
    is_overdue: bool = False


class ParentDashboard(BaseSchema):
    """Full parent dashboard response."""

    children: list[ChildSummary] = []
    active_child: Optional[ChildOverview] = None
    announcements: list[AnnouncementResponse] = []
    upcoming: list[UpcomingEvent] = []


# =========================
# Parent Engagement Stats (Admin view)
# =========================


class ParentEngagementStats(BaseSchema):
    """Aggregate engagement metrics for school admins."""

    total_parents: int = 0
    registered_parents: int = 0
    active_this_week: int = 0
    announcements_read_rate: float = 0.0
    notes_acknowledged_rate: float = 0.0
    online_payments_this_month: int = 0
    online_payments_amount: Decimal = Decimal("0.00")

"""
SIMS Plus Schemas package.

Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, ConfigDict

from app.schemas.tenant import (
    SubdomainCheckRequest,
    SubdomainCheckResponse,
    TenantBranding,
    TenantPublic,
    TenantResponse,
    TenantValidationResponse,
)

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
    TokenResponse,
    ChangePasswordRequest,
    UserResponse,
    UserMeResponse,
)

from app.schemas.onboarding import (
    SchoolRegistrationRequest,
    SchoolRegistrationResponse,
)

from app.schemas.student import (
    GuardianCreate,
    GuardianUpdate,
    GuardianResponse,
    GuardianListResponse,
    StudentGuardianCreate,
    StudentGuardianWithNewGuardian,
    StudentGuardianUpdate,
    StudentGuardianResponse,
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentWithGuardiansResponse,
    StudentListResponse,
    StudentBulkCreate,
    StudentBulkResponse,
    StudentStatsResponse,
    StudentFilterParams,
)

from app.schemas.staff import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentListResponse,
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffListResponse,
    StaffStatsResponse,
    StaffWithAssignmentsResponse,
    StaffAssignmentCreate,
    StaffAssignmentUpdate,
    StaffAssignmentResponse,
)

from app.schemas.attendance import (
    StudentAttendanceMark,
    BulkStudentAttendanceMark,
    StudentAttendanceResponse,
    StudentAttendanceListItem,
    StudentAttendanceSummary,
    SectionAttendanceSummary,
    DailyAttendanceReport,
    BulkAttendanceResult,
    StaffAttendanceMark,
    BulkStaffAttendanceMark,
    StaffAttendanceResponse,
    StaffAttendanceSummary,
)

from app.schemas.exam import (
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    ExamWithContextResponse,
    ExamListResponse,
    ExamSubjectCreate,
    ExamSubjectBulkCreate,
    ExamSubjectUpdate,
    ExamSubjectResponse,
    ExamSubjectWithDetailsResponse,
    ScoreEntry,
    ExamScoreBulkCreate,
    ExamScoreUpdate,
    ExamScoreResponse,
    ExamScoreWithStudentResponse,
    ScoreEntryFormResponse,
    BulkScoreResult,
    CACreate,
    CABulkCreate,
    CAUpdate,
    CAResponse,
    CAWithDetailsResponse,
    CASummaryResponse,
    SubjectResult,
    StudentExamResult,
    ClassResultsResponse,
    TermReportGenerate,
    TermReportRemarksUpdate,
    TermReportResponse,
    TermReportWithDetailsResponse,
    TermReportListResponse,
)

from app.schemas.preschool import (
    LearningAreaCreate,
    LearningAreaUpdate,
    LearningAreaResponse,
    LearningAreaWithSkills,
    DevelopmentalSkillCreate,
    DevelopmentalSkillUpdate,
    DevelopmentalSkillResponse,
    DevelopmentalSkillBulkCreate,
    PreschoolRatingCreate,
    PreschoolRatingResponse,
    PreschoolRatingScaleCreate,
    PreschoolRatingScaleUpdate,
    PreschoolRatingScaleResponse,
    PreschoolRatingScaleWithRatings,
    StudentSkillAssessmentCreate,
    StudentSkillAssessmentBulk,
    SkillAssessmentEntry,
    StudentSkillAssessmentResponse,
    StudentSkillAssessmentWithDetails,
    AttachmentSchema,
    ProgressObservationCreate,
    ProgressObservationUpdate,
    ProgressObservationResponse,
    MealEntry,
    DailyActivityLogCreate,
    DailyActivityLogUpdate,
    DailyActivityLogResponse,
    LearningAreaSummary,
    PreschoolReportCreate,
    PreschoolReportUpdate,
    PreschoolReportResponse,
    PreschoolReportGenerateRequest,
    PreschoolReportPublishRequest,
    SeedLearningAreasRequest,
    SeedRatingScaleRequest,
)

from app.schemas.academic import (
    TimetableEntryCreate,
    TimetableEntryUpdate,
    TimetableEntryResponse,
    TimetableBulkEntry,
    TimetableBulkCreate,
    TimetableDayResponse,
    TimetableWeekResponse,
    TimetableSubjectResponse,
    TimetableTeacherResponse,
    TimetableTermResponse,
    PeriodTemplate,
    TimetableTemplate,
    SchoolPeriodCreate,
    SchoolPeriodUpdate,
    SchoolPeriodResponse,
    SchoolHolidayCreate,
    SchoolHolidayUpdate,
    SchoolHolidayResponse,
)

from app.schemas.finance import (
    # Fee Structures
    FeeItemCreate,
    FeeItemUpdate,
    FeeItemResponse,
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureResponse,
    FeeStructureWithItemsResponse,
    FeeStructureListResponse,
    # Invoices
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceScholarshipItemResponse,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceWithDetailsResponse,
    InvoiceListResponse,
    InvoiceBulkGenerate,
    InvoiceBulkResult,
    InvoiceIssue,
    InvoiceCancel,
    # Payments
    PaymentCreate,
    PaymentResponse,
    PaymentWithDetailsResponse,
    PaymentListResponse,
    PaymentVoid,
    PaymentReceiptResponse,
    # Scholarships
    ScholarshipCreate,
    ScholarshipUpdate,
    ScholarshipResponse,
    ScholarshipWithStatsResponse,
    ScholarshipListResponse,
    ScholarshipAward,
    ScholarshipBulkAward,
    ScholarshipRevoke,
    StudentScholarshipResponse,
    StudentScholarshipWithDetailsResponse,
    StudentScholarshipListResponse,
    # Applications
    ScholarshipApplicationCreate,
    ScholarshipApplicationReview,
    ScholarshipApplicationResponse,
    ScholarshipApplicationWithDetailsResponse,
    ScholarshipApplicationListResponse,
    # Dashboard
    FinanceDashboardStats,
    RecentPayment,
    OutstandingByClass,
    FinanceDashboardResponse,
)


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class MessageResponse(BaseSchema):
    """Standard message response."""

    message: str
    success: bool = True


class PaginationParams(BaseSchema):
    """Pagination parameters."""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseSchema):
    """Paginated response wrapper."""

    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

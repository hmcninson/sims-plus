"""
SIMS Plus - Database Base

Import ALL models here for Alembic to detect schema changes.

IMPORTANT: Every new SQLAlchemy model MUST be imported here.
If you create a new model file and forget to import it here,
Alembic autogenerate will not detect the table and will not
create a migration for it.
"""

# Import base model class
from app.models.base import Base  # noqa: F401

# Core models (no tenant_id)
from app.models.tenant import Tenant  # noqa: F401
from app.models.reserved_subdomain import ReservedSubdomain  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

# Tenant-scoped models (all have tenant_id)
from app.models.user import User  # noqa: F401
from app.models.user_session import UserSession  # noqa: F401
from app.models.school import School  # noqa: F401
from app.models.student import Student, Guardian, StudentGuardian, StudentClassHistory, StudentStatusChange, WithdrawalClearance, StudentDocument, StudentDocumentType, PreviousSchool  # noqa: F401
from app.models.staff import Staff, Department, StaffClassAssignment, StaffDocument, StaffEmploymentHistory  # noqa: F401
from app.models.leave import LeaveType, LeaveBalance, LeaveRequest  # noqa: F401
from app.models.academic import (  # noqa: F401
    AcademicYear,
    Term,
    Class,
    ClassSection,
    Subject,
    ClassSubject,
    GradingScale,
    Grade,
    AssessmentWeight,
    AcademicSettings,
    SchoolPeriod,
    SchoolHoliday,
    ClassTimetable,
)
from app.models.exam import (  # noqa: F401
    Exam,
    ExamSubject,
    ExamScore,
    ScoreChangeLog,
    ContinuousAssessment,
    TermReport,
)
from app.models.attendance import StudentAttendance, StaffAttendance  # noqa: F401
from app.models.preschool import (  # noqa: F401
    LearningArea,
    DevelopmentalSkill,
    PreschoolRatingScale,
    PreschoolRating,
    StudentSkillAssessment,
    ProgressObservation,
    DailyActivityLog,
    PreschoolReport,
    PreschoolIncident,
    AuthorizedPickup,
    PickupLog,
    LearningStory,
    ExtendedCareSession,
    ClassCaregiverRatio,
    PreschoolSupply,
)
from app.models.finance import (  # noqa: F401
    FeeType,
    FeeStructure,
    FeeItem,
    Invoice,
    InvoiceItem,
    Payment,
    Scholarship,
    StudentScholarship,
    ScholarshipApplication,
    CreditNote,
    FinanceAuditLog,
    InvoiceScholarshipItem,
)
from app.models.notification import Notification  # noqa: F401
from app.models.sms import SMSLog  # noqa: F401

# Boarding models
from app.models.boarding import (  # noqa: F401
    House,
    Dormitory,
    Bed,
    StudentBoarding,
    BoardingRollCall,
    BoardingRollCallEntry,
    Exeat,
    BoardingIncident,
    DiningMeal,
)

# Transport models
from app.models.transport import (  # noqa: F401
    Vehicle,
    Driver,
    Route,
    RouteStop,
    StudentTransport,
    TripLog,
    VehicleMaintenance,
)

# Parent portal models
from app.models.parent import (  # noqa: F401
    Announcement,
    TeacherNote,
    ParentNotificationPreference,
)

# Push notification model
from app.models.push_subscription import PushSubscription  # noqa: F401

# Admissions models
from app.models.admissions import (  # noqa: F401
    AdmissionDecision,
    AdmissionFormConfig,
    AdmissionPeriod,
    Application,
    ApplicationDocument,
    ApplicationGuardian,
    ApplicationNote,
    ApplicationPayment,
    ApplicationStatusHistory,
    ClassPromotion,
    ClassPromotionEntry,
    PromotionRule,
    EnrollmentChecklist,
    EnrollmentChecklistItem,
    EnrollmentTarget,
    EntranceExam,
    EntranceExamRegistration,
    EntranceExamResult,
    EventRegistration,
    Inquiry,
    InquiryCommunication,
    InquiryFollowUp,
    Interview,
    ReturnIntent,
    ReturnIntentCampaign,
    SchoolEvent,
    ScreeningChecklist,
)

# Payroll + Loan models
from app.models.payroll import (  # noqa: F401
    SalaryGrade,
    AllowanceType,
    DeductionType,
    TaxBracket,
    StaffSalaryConfig,
    StaffAllowance,
    StaffDeduction,
    PayrollRun,
    PayrollItem,
    PayrollItemEarning,
    PayrollItemDeduction,
    PayrollApproval,
    BankFileConfig,
    PayrollAuditLog,
    LoanType,
    StaffLoan,
    LoanInstallment,
    LoanGuarantor,
    LoanPayment,
)

# Platform admin (no tenant_id, no RLS)
from app.models.platform_audit import PlatformAuditLog  # noqa: F401

__all__ = ["Base"]

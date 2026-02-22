"""
SIMS Plus Services package.

Business logic and service layer.
"""

from app.services.tenant import TenantService
from app.services.auth import AuthService, AuthenticationError
from app.services.onboarding import OnboardingService, OnboardingError
from app.services.audit import AuditService, AuditEventType
from app.services.student import StudentService, StudentServiceError
from app.services.staff import StaffService, DepartmentService, StaffServiceError
from app.services.attendance import AttendanceService, AttendanceServiceError
from app.services.exam import (
    ExamService,
    ScoreService,
    CAService,
    TermReportService,
    ExamServiceError,
)
from app.services.preschool import PreschoolService
from app.services.timetable import TimetableService, TimetableServiceError
from app.services.finance import (
    FeeStructureService,
    InvoiceService,
    PaymentService,
    ScholarshipService,
    FinanceDashboardService,
    FinanceAuditService,
    CreditNoteService,
    FinanceServiceError,
)

__all__ = [
    "TenantService",
    "AuthService",
    "AuthenticationError",
    "OnboardingService",
    "OnboardingError",
    "AuditService",
    "AuditEventType",
    "StudentService",
    "StudentServiceError",
    "StaffService",
    "DepartmentService",
    "StaffServiceError",
    "AttendanceService",
    "AttendanceServiceError",
    "ExamService",
    "ScoreService",
    "CAService",
    "TermReportService",
    "ExamServiceError",
    "PreschoolService",
    "TimetableService",
    "TimetableServiceError",
    "FeeStructureService",
    "InvoiceService",
    "PaymentService",
    "ScholarshipService",
    "FinanceDashboardService",
    "FinanceAuditService",
    "CreditNoteService",
    "FinanceServiceError",
]

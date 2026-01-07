"""
SIMS Plus Services package.

Business logic and service layer.
"""

from app.services.tenant import TenantService
from app.services.auth import AuthService, AuthenticationError
from app.services.onboarding import OnboardingService, OnboardingError
from app.services.audit import AuditService, AuditEventType
from app.services.student import StudentService, StudentServiceError
from app.services.staff import StaffService, StaffServiceError
from app.services.attendance import AttendanceService, AttendanceServiceError

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
    "StaffServiceError",
    "AttendanceService",
    "AttendanceServiceError",
]

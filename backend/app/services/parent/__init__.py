"""
SIMS Plus - Parent Portal Services Package

Re-exports all service classes for backward compatibility.
Existing imports like `from app.services.parent import ParentService` continue to work.
"""

from app.services.parent._shared import ParentServiceError
from app.services.parent.parent_service import ParentService
from app.services.parent.parent_academic import ParentAcademicService
from app.services.parent.parent_finance import ParentFinanceService
from app.services.parent.parent_attendance import ParentAttendanceService
from app.services.parent.parent_communication import ParentCommunicationService
from app.services.parent.parent_onboarding import ParentOnboardingService
from app.services.parent.notification_preferences import NotificationPreferencesService

__all__ = [
    "ParentServiceError",
    "ParentService",
    "ParentAcademicService",
    "ParentFinanceService",
    "ParentAttendanceService",
    "ParentCommunicationService",
    "ParentOnboardingService",
    "NotificationPreferencesService",
]

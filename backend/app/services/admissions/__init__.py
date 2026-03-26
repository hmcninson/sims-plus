"""
SIMS Plus - Admissions Services Package

Re-exports all service classes for convenient imports.
Existing imports like `from app.services.admissions import ApplicationService` work.
"""

from app.services.admissions.period_service import (
    AdmissionPeriodService,
    AdmissionPeriodError,
)
from app.services.admissions.application_service import (
    ApplicationService,
    ApplicationServiceError,
)
from app.services.admissions.payment_service import (
    ApplicationPaymentService,
    ApplicationPaymentError,
)
from app.services.admissions.notification_service import (
    AdmissionNotificationService,
)
from app.services.admissions.enrollment_service import (
    EnrollmentService,
    EnrollmentError,
)
from app.services.admissions.exam_service import (
    EntranceExamService,
    EntranceExamServiceError,
)
from app.services.admissions.decision_service import (
    DecisionService,
    DecisionServiceError,
)
from app.services.admissions.promotion_service import (
    ClassPromotionService,
    ClassPromotionError,
)
from app.services.admissions.return_intent_service import (
    ReturnIntentService,
    ReturnIntentError,
)
from app.services.admissions.applicant_service import (
    ApplicantAccountService,
    ApplicantAccountError,
)
from app.services.admissions.inquiry_service import (
    InquiryService,
    InquiryServiceError,
)
from app.services.admissions.interview_service import (
    InterviewService,
    InterviewServiceError,
)
from app.services.admissions.cssps_service import (
    CSSPSImportService,
    CSSPSImportError,
)
from app.services.admissions.capacity_service import (
    CapacityService,
    CapacityServiceError,
)
from app.services.admissions.event_service import (
    EventService,
    EventServiceError,
)
from app.services.admissions.analytics_service import (
    AdmissionsAnalyticsService,
    AnalyticsServiceError,
)

__all__ = [
    # Period management
    "AdmissionPeriodService",
    "AdmissionPeriodError",
    # Application submission and workflow
    "ApplicationService",
    "ApplicationServiceError",
    # Application payment (Paystack)
    "ApplicationPaymentService",
    "ApplicationPaymentError",
    # SMS/email notifications
    "AdmissionNotificationService",
    # Enrollment (applicant -> student conversion)
    "EnrollmentService",
    "EnrollmentError",
    # Entrance exam management
    "EntranceExamService",
    "EntranceExamServiceError",
    # Admission decisions
    "DecisionService",
    "DecisionServiceError",
    # Class promotion
    "ClassPromotionService",
    "ClassPromotionError",
    # Return intent surveys
    "ReturnIntentService",
    "ReturnIntentError",
    # Applicant accounts
    "ApplicantAccountService",
    "ApplicantAccountError",
    # Inquiry / lead management
    "InquiryService",
    "InquiryServiceError",
    # Interview & screening
    "InterviewService",
    "InterviewServiceError",
    # CSSPS import
    "CSSPSImportService",
    "CSSPSImportError",
    # Capacity planning
    "CapacityService",
    "CapacityServiceError",
    # School events
    "EventService",
    "EventServiceError",
    # Analytics
    "AdmissionsAnalyticsService",
    "AnalyticsServiceError",
]

"""
SIMS Plus - Admissions Models Package

Re-exports all admissions models for convenient imports.
"""

# Enums
from app.models.admissions.enums import (
    AdmissionApplicationStatus,
    AdmissionPeriodStatus,
    BoardingStatus,
    ChecklistItemType,
    ChecklistType,
    DecisionType,
    EntranceExamStatus,
    EventStatus,
    EventType,
    InquirySource,
    InquiryStatus,
    InterviewStatus,
    OfferResponse,
    PromotionAction,
    PromotionBatchStatus,
    INQUIRY_TERMINAL_STATUSES,
    INQUIRY_VALID_TRANSITIONS,
    INTERVIEW_VALID_TRANSITIONS,
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
)

# Period models
from app.models.admissions.period import AdmissionFormConfig, AdmissionPeriod

# Application models
from app.models.admissions.application import (
    Application,
    ApplicationDocument,
    ApplicationGuardian,
    ApplicationNote,
    ApplicationPayment,
    ApplicationStatusHistory,
)

# Exam models
from app.models.admissions.exam import (
    EntranceExam,
    EntranceExamRegistration,
    EntranceExamResult,
)

# Decision model
from app.models.admissions.decision import AdmissionDecision

# Inquiry models (Enrollment Gap Closure Phase 1)
from app.models.admissions.inquiry import (
    Inquiry,
    InquiryCommunication,
    InquiryFollowUp,
)

# Interview models (Enrollment Gap Closure Phase 1)
from app.models.admissions.interview import Interview, ScreeningChecklist

# Class promotion models
from app.models.admissions.promotion import ClassPromotion, ClassPromotionEntry, PromotionRule

# Return intent models
from app.models.admissions.return_intent import ReturnIntent, ReturnIntentCampaign

# Enrollment checklist models (Enrollment Gap Closure Phase 3)
from app.models.admissions.enrollment_checklist import (
    EnrollmentChecklist,
    EnrollmentChecklistItem,
)

# Capacity planning models (Enrollment Gap Closure Phase 4)
from app.models.admissions.capacity import EnrollmentTarget

# School event models (Enrollment Gap Closure Phase 4)
from app.models.admissions.event import EventRegistration, SchoolEvent

__all__ = [
    # Enums
    "AdmissionApplicationStatus",
    "AdmissionPeriodStatus",
    "BoardingStatus",
    "ChecklistItemType",
    "ChecklistType",
    "EntranceExamStatus",
    "EventStatus",
    "EventType",
    "DecisionType",
    "InquirySource",
    "InquiryStatus",
    "InterviewStatus",
    "PromotionBatchStatus",
    "PromotionAction",
    "VALID_TRANSITIONS",
    "TERMINAL_STATUSES",
    "INQUIRY_VALID_TRANSITIONS",
    "INQUIRY_TERMINAL_STATUSES",
    "INTERVIEW_VALID_TRANSITIONS",
    "OfferResponse",
    # Period
    "AdmissionPeriod",
    "AdmissionFormConfig",
    # Application
    "Application",
    "ApplicationGuardian",
    "ApplicationDocument",
    "ApplicationPayment",
    "ApplicationStatusHistory",
    "ApplicationNote",
    # Exam
    "EntranceExam",
    "EntranceExamRegistration",
    "EntranceExamResult",
    # Decision
    "AdmissionDecision",
    # Inquiry
    "Inquiry",
    "InquiryCommunication",
    "InquiryFollowUp",
    # Interview
    "Interview",
    "ScreeningChecklist",
    # Class Promotion
    "ClassPromotion",
    "ClassPromotionEntry",
    "PromotionRule",
    # Return Intent
    "ReturnIntentCampaign",
    "ReturnIntent",
    # Enrollment Checklist
    "EnrollmentChecklist",
    "EnrollmentChecklistItem",
    # Capacity Planning
    "EnrollmentTarget",
    # School Events
    "SchoolEvent",
    "EventRegistration",
]

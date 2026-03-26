"""
SIMS Plus - Admissions Enums

Enum types for the admissions module.
All enums follow the project convention:
- Python class: class Name(str, Enum) with UPPERCASE members
- Database: lowercase .value strings
- PostgreSQL type: lowercase name with no underscores
"""

from enum import Enum


class AdmissionApplicationStatus(str, Enum):
    """Application workflow states."""
    # Named AdmissionApplicationStatus to avoid collision with finance.ApplicationStatus

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


class AdmissionPeriodStatus(str, Enum):
    """Admission period lifecycle states."""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class EntranceExamStatus(str, Enum):
    """Entrance exam session states."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionType(str, Enum):
    """Admission decision types."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"
    DEFERRED = "deferred"


class PromotionBatchStatus(str, Enum):
    """Class promotion batch lifecycle states."""

    DRAFT = "draft"
    PREVIEW = "preview"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PromotionAction(str, Enum):
    """Per-student promotion action."""

    PROMOTE = "promote"
    REPEAT = "repeat"
    GRADUATE = "graduate"
    WITHDRAW = "withdraw"


# ---------------------------------------------------------------
# Status Machine -- Valid Transitions
# ---------------------------------------------------------------

VALID_TRANSITIONS: dict[AdmissionApplicationStatus, list[AdmissionApplicationStatus]] = {
    AdmissionApplicationStatus.DRAFT: [
        AdmissionApplicationStatus.SUBMITTED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.SUBMITTED: [
        AdmissionApplicationStatus.UNDER_REVIEW,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.UNDER_REVIEW: [
        AdmissionApplicationStatus.SHORTLISTED,
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WAITLISTED,
        AdmissionApplicationStatus.DEFERRED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.SHORTLISTED: [
        AdmissionApplicationStatus.EXAM_SCHEDULED,
        AdmissionApplicationStatus.OFFERED,  # When exam_waived=true
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.EXAM_SCHEDULED: [
        AdmissionApplicationStatus.EXAM_COMPLETED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.EXAM_COMPLETED: [
        AdmissionApplicationStatus.OFFERED,
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WAITLISTED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.OFFERED: [
        AdmissionApplicationStatus.ACCEPTED,
        AdmissionApplicationStatus.EXPIRED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.ACCEPTED: [
        AdmissionApplicationStatus.ENROLLED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.WAITLISTED: [
        AdmissionApplicationStatus.OFFERED,
        AdmissionApplicationStatus.REJECTED,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
    AdmissionApplicationStatus.REJECTED: [],  # Terminal
    AdmissionApplicationStatus.ENROLLED: [],  # Terminal
    AdmissionApplicationStatus.WITHDRAWN: [],  # Terminal
    AdmissionApplicationStatus.EXPIRED: [
        AdmissionApplicationStatus.OFFERED,  # Can re-offer after expiry
    ],
    AdmissionApplicationStatus.DEFERRED: [
        AdmissionApplicationStatus.UNDER_REVIEW,
        AdmissionApplicationStatus.WITHDRAWN,
    ],
}

# Terminal states -- no further transitions allowed (except EXPIRED -> OFFERED)
TERMINAL_STATUSES = {
    AdmissionApplicationStatus.REJECTED,
    AdmissionApplicationStatus.ENROLLED,
    AdmissionApplicationStatus.WITHDRAWN,
}


# ---------------------------------------------------------------
# Inquiry & Interview Enums (Enrollment Gap Closure Phase 1)
# ---------------------------------------------------------------

class InquirySource(str, Enum):
    """How the inquiry reached the school."""

    WEBSITE = "website"
    WALK_IN = "walk_in"
    PHONE = "phone"
    REFERRAL = "referral"
    EVENT = "event"
    SOCIAL_MEDIA = "social_media"
    OTHER = "other"


class InquiryStatus(str, Enum):
    """Lead progression workflow."""

    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    APPLIED = "applied"
    ENROLLED = "enrolled"
    LOST = "lost"


class InterviewStatus(str, Enum):
    """Interview session lifecycle."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


# Valid status transitions for inquiry workflow
INQUIRY_VALID_TRANSITIONS: dict[str, list[str]] = {
    "new": ["contacted", "interested", "lost"],
    "contacted": ["interested", "lost"],
    "interested": ["applied", "lost"],
    "applied": ["enrolled"],
    "enrolled": [],
    "lost": ["new", "contacted"],
}

INQUIRY_TERMINAL_STATUSES = {"enrolled"}

# Valid status transitions for interview workflow
INTERVIEW_VALID_TRANSITIONS: dict[str, list[str]] = {
    "scheduled": ["completed", "cancelled", "no_show", "rescheduled"],
    "rescheduled": ["completed", "cancelled", "no_show"],
    "completed": [],
    "cancelled": ["scheduled"],
    "no_show": ["rescheduled"],
}


# ---------------------------------------------------------------
# Offer Response Enum (Enrollment Gap Closure Phase 2)
# ---------------------------------------------------------------

class OfferResponse(str, Enum):
    """Applicant's response to an admission offer."""

    ACCEPTED = "accepted"
    DECLINED = "declined"


# ---------------------------------------------------------------
# Enrollment Checklist Enums (Enrollment Gap Closure Phase 3)
# ---------------------------------------------------------------

class ChecklistType(str, Enum):
    """Enrollment checklist variants."""

    STANDARD = "standard"
    BOARDING = "boarding"


class ChecklistItemType(str, Enum):
    """Categories for enrollment checklist items."""

    DOCUMENT = "document"
    PAYMENT = "payment"
    FORM = "form"
    BOARDING = "boarding"
    MEDICAL = "medical"


class BoardingStatus(str, Enum):
    """Residential status for enrolled students."""

    BOARDING = "boarding"
    DAY = "day"


# ---------------------------------------------------------------
# School Event Enums (Enrollment Gap Closure Phase 4)
# ---------------------------------------------------------------

class EventType(str, Enum):
    """School event types for prospective families."""

    OPEN_DAY = "open_day"
    TOUR = "tour"
    ORIENTATION = "orientation"


class EventStatus(str, Enum):
    """School event lifecycle."""

    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

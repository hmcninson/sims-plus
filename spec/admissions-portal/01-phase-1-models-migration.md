# Phase 1: Models & Migration

**Sprint:** 19-20
**Agent:** 1 (Data Model + Migration)
**Depends on:** Nothing (can start immediately)
**Parallel with:** Agent 2 (Services + Infrastructure)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 1.1 | Create enum definitions | `backend/app/models/admissions/enums.py` | 0.5d |
| 1.2 | Create period models | `backend/app/models/admissions/period.py` | 0.5d |
| 1.3 | Create application models | `backend/app/models/admissions/application.py` | 1d |
| 1.4 | Create exam models | `backend/app/models/admissions/exam.py` | 0.5d |
| 1.5 | Create decision model | `backend/app/models/admissions/decision.py` | 0.5d |
| 1.6 | Create class promotion models | `backend/app/models/admissions/promotion.py` | 0.75d |
| 1.6b | Create return intent models | `backend/app/models/admissions/return_intent.py` | 0.5d |
| 1.7 | Create package `__init__.py` | `backend/app/models/admissions/__init__.py` | 0.25d |
| 1.8 | Register models in main `__init__.py` | `backend/app/models/__init__.py` | 0.25d |
| 1.9 | Create Alembic migration | `backend/alembic/versions/20260303_0100_admissions_tables.py` | 2d |
| 1.10 | Update test infrastructure | `backend/tests/conftest.py`, `backend/scripts/verify_rls.py` | 0.5d |

---

## 1.1 Enum Definitions

**File:** `backend/app/models/admissions/enums.py`

```python
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
# Status Machine — Valid Transitions
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

# Terminal states — no further transitions allowed (except EXPIRED → OFFERED)
TERMINAL_STATUSES = {
    AdmissionApplicationStatus.REJECTED,
    AdmissionApplicationStatus.ENROLLED,
    AdmissionApplicationStatus.WITHDRAWN,
}
```

---

## 1.2 Period Models

**File:** `backend/app/models/admissions/period.py`

```python
"""
SIMS Plus - Admission Period Models

AdmissionPeriod: Intake windows for applications.
AdmissionFormConfig: Custom form field definitions per period.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import AdmissionPeriodStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.admissions.application import Application
    from app.models.admissions.exam import EntranceExam
    from app.models.school import School


class AdmissionPeriod(Base, TenantMixin, SoftDeleteMixin):
    """
    Admission Period model.

    Represents an intake window (e.g., "2026/2027 Admissions for Form 1").
    Controls when applications are accepted, fee requirements, and target classes.
    """

    __tablename__ = "admission_periods"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Period name, e.g., '2026/2027 Admissions'",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Applications open date",
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Applications close date",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AdmissionPeriodStatus.DRAFT.value,
        server_default="draft",
        comment="draft, open, closed, archived",
    )
    application_fee_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Fee amount in tenant currency (null = free)",
    )
    application_fee_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    entrance_exam_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    max_applications: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of applications (null = unlimited)",
    )
    target_classes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of class UUIDs this period accepts applications for",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    form_config: Mapped["AdmissionFormConfig | None"] = relationship(
        back_populates="admission_period",
        lazy="raise",
        uselist=False,
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="admission_period",
        lazy="raise",
    )
    entrance_exams: Mapped[list["EntranceExam"]] = relationship(
        back_populates="admission_period",
        lazy="raise",
    )


class AdmissionFormConfig(Base, TenantMixin, SoftDeleteMixin):
    """
    Admission Form Configuration model.

    Stores JSON Schema for custom form fields per admission period.
    Schools use this to add fields like "Previous School", "Medical Info", etc.
    """

    __tablename__ = "admission_form_configs"

    __table_args__ = (
        UniqueConstraint("tenant_id", "admission_period_id", name="uq_form_configs_tenant_period"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    admission_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admission_periods.id", ondelete="CASCADE"),
        nullable=False,
        comment="One form config per period",
    )
    form_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="JSON Schema defining custom form fields",
    )
    required_documents: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of required document types, e.g., ['birth_certificate', 'passport_photo']",
    )

    # Relationships
    admission_period: Mapped["AdmissionPeriod"] = relationship(
        back_populates="form_config",
        lazy="raise",
    )
```

---

## 1.3 Application Models

**File:** `backend/app/models/admissions/application.py`

```python
"""
SIMS Plus - Application Models

Core application record and related tables:
Application, ApplicationGuardian, ApplicationDocument,
ApplicationPayment, ApplicationStatusHistory, ApplicationNote.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import AdmissionApplicationStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.admissions.decision import AdmissionDecision
    from app.models.admissions.exam import (
        EntranceExamRegistration,
        EntranceExamResult,
    )
    from app.models.admissions.period import AdmissionPeriod
    from app.models.school import School
    from app.models.student import Student
    from app.models.tenant import User


class Application(Base, TenantMixin, SoftDeleteMixin):
    """
    Application model — the central entity of the admissions module.

    Tracks a prospective student's application from submission through
    enrollment. The tracking_code is the public identifier; the UUID id
    is used internally.
    """

    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint("tenant_id", "tracking_code", name="uq_applications_tenant_tracking"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    admission_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admission_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    tracking_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Public identifier — secrets.token_urlsafe(48), 384-bit entropy",
    )
    applicant_first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    applicant_last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    applicant_other_names: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    date_of_birth: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    gender: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="male or female",
    )
    nationality: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    target_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Class the applicant is applying to",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AdmissionApplicationStatus.DRAFT.value,
        server_default="draft",
    )
    custom_fields: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Dynamic fields validated against form_schema",
    )
    fee_waived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, application fee payment is not required",
    )
    exam_waived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, entrance exam is not required",
    )
    converted_student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set on enrollment — serves as idempotency guard",
    )
    applicant_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    previous_school: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    medical_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when moved from draft to submitted",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    admission_period: Mapped["AdmissionPeriod"] = relationship(
        back_populates="applications",
        lazy="raise",
    )
    target_class: Mapped["Class"] = relationship(
        lazy="raise",
        foreign_keys=[target_class_id],
    )
    converted_student: Mapped["Student | None"] = relationship(
        lazy="raise",
        foreign_keys=[converted_student_id],
    )
    guardians: Mapped[list["ApplicationGuardian"]] = relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["ApplicationPayment"]] = relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list["ApplicationNote"]] = relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    decision: Mapped["AdmissionDecision | None"] = relationship(
        back_populates="application",
        lazy="raise",
        uselist=False,
    )
    exam_registrations: Mapped[list["EntranceExamRegistration"]] = relationship(
        back_populates="application",
        lazy="raise",
    )
    exam_results: Mapped[list["EntranceExamResult"]] = relationship(
        back_populates="application",
        lazy="raise",
    )


class ApplicationGuardian(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Guardian model.

    Stores guardian/parent info as submitted with the application.
    These are NOT the same as Guardian records — conversion happens
    during enrollment with deduplication.
    """

    __tablename__ = "application_guardians"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Primary contact phone",
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="father, mother, guardian, other",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Primary contact for this application",
    )
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="guardians",
        lazy="raise",
    )


class ApplicationDocument(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Document model.

    Stores metadata for uploaded files (actual files live in S3).
    S3 key format: admissions/{tenant_id}/{application_id}/{uuid}.{ext}
    """

    __tablename__ = "application_documents"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="birth_certificate, passport_photo, transcript, medical_report, etc.",
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original uploaded filename",
    )
    s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="S3 object key: admissions/{tenant_id}/{app_id}/{uuid}.{ext}",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes (max 5MB = 5242880)",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="application/pdf, image/jpeg, image/png",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="documents",
        lazy="raise",
    )


class ApplicationPayment(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Payment model.

    Tracks application fee payments via Paystack.
    Separate from the main payments table since applicants are not students yet.
    """

    __tablename__ = "application_payments"

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_reference", name="uq_payments_tenant_reference"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="GHS",
        server_default="GHS",
    )
    payment_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="mobile_money, card, bank_transfer",
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Paystack transaction reference",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="pending, completed, failed, refunded",
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Provider-specific response data",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="payments",
        lazy="raise",
    )


class ApplicationStatusHistory(Base, TenantMixin):
    """
    Application Status History model.

    Append-only audit log of all status transitions.
    No SoftDeleteMixin — audit records are never deleted.
    No updated_at — records are immutable.
    """

    __tablename__ = "application_status_history"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="NULL for initial creation",
    )
    to_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL for public actions (e.g., applicant submission)",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why the status was changed",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="status_history",
        lazy="raise",
    )
    changed_by_user: Mapped["User | None"] = relationship(lazy="raise")


class ApplicationNote(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Note model.

    Internal reviewer notes on applications. Not shown to applicants.
    """

    __tablename__ = "application_notes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="If true, only visible to admin (not applicant)",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="notes",
        lazy="raise",
    )
    author: Mapped["User"] = relationship(lazy="raise")
```

---

## 1.4 Exam Models

**File:** `backend/app/models/admissions/exam.py`

```python
"""
SIMS Plus - Entrance Exam Models

EntranceExam: Exam session definitions.
EntranceExamRegistration: Applicant-to-exam assignments.
EntranceExamResult: Exam scores per applicant.
"""

import uuid
from datetime import date, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    Time,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import EntranceExamStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.admissions.application import Application
    from app.models.admissions.period import AdmissionPeriod
    from app.models.school import School
    from app.models.tenant import User


class EntranceExam(Base, TenantMixin, SoftDeleteMixin):
    """
    Entrance Exam model.

    Represents an exam session with date, venue, and capacity.
    """

    __tablename__ = "entrance_exams"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    admission_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admission_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., 'Entrance Exam — Batch 1'",
    )
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    venue: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum number of candidates",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EntranceExamStatus.SCHEDULED.value,
        server_default="scheduled",
    )
    instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Instructions sent to candidates",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    admission_period: Mapped["AdmissionPeriod"] = relationship(
        back_populates="entrance_exams",
        lazy="raise",
    )
    registrations: Mapped[list["EntranceExamRegistration"]] = relationship(
        back_populates="entrance_exam",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    results: Mapped[list["EntranceExamResult"]] = relationship(
        back_populates="entrance_exam",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class EntranceExamRegistration(Base, TenantMixin, SoftDeleteMixin):
    """
    Entrance Exam Registration model.

    Links an applicant to an exam session with optional seat assignment.
    """

    __tablename__ = "entrance_exam_registrations"

    entrance_exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entrance_exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    seat_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    attended: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Relationships
    entrance_exam: Mapped["EntranceExam"] = relationship(
        back_populates="registrations",
        lazy="raise",
    )
    application: Mapped["Application"] = relationship(
        back_populates="exam_registrations",
        lazy="raise",
    )


class EntranceExamResult(Base, TenantMixin, SoftDeleteMixin):
    """
    Entrance Exam Result model.

    Stores scores for each applicant per exam session.
    """

    __tablename__ = "entrance_exam_results"

    entrance_exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entrance_exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )
    grade: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Optional letter grade",
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    entrance_exam: Mapped["EntranceExam"] = relationship(
        back_populates="results",
        lazy="raise",
    )
    application: Mapped["Application"] = relationship(
        back_populates="exam_results",
        lazy="raise",
    )
    scored_by_user: Mapped["User | None"] = relationship(lazy="raise")
```

---

## 1.5 Decision Model

**File:** `backend/app/models/admissions/decision.py`

```python
"""
SIMS Plus - Admission Decision Model
"""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import DecisionType
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.admissions.application import Application
    from app.models.tenant import User


class AdmissionDecision(Base, TenantMixin, SoftDeleteMixin):
    """
    Admission Decision model.

    Records the formal admission decision for an application.
    One decision per application (enforced by unique constraint).
    """

    __tablename__ = "admission_decisions"

    __table_args__ = (
        UniqueConstraint("tenant_id", "application_id", name="uq_decisions_tenant_application"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="One decision per application",
    )
    decision_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="accepted, rejected, waitlisted, deferred",
    )
    decided_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    offered_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="May differ from application's target_class_id",
    )
    conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditional offer terms",
    )
    decision_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    response_deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Deadline for applicant to accept the offer",
    )
    decision_letter_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Generated PDF letter S3 URL",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="decision",
        lazy="raise",
    )
    decided_by_user: Mapped["User"] = relationship(lazy="raise")
    offered_class: Mapped["Class | None"] = relationship(lazy="raise")
```

---

## 1.6 Class Promotion Models

**File:** `backend/app/models/admissions/promotion.py`

```python
"""
SIMS Plus - Class Promotion Models

ClassPromotion: Batch promotion operation record (end-of-year).
ClassPromotionEntry: Per-student promotion decision.

This is the primary tool for Ghanaian academic year transitions.
Students are automatically promoted to the next class unless marked
for repeat, graduation, or withdrawal.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import PromotionAction, PromotionBatchStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, ClassSection
    from app.models.school import School
    from app.models.student import Student
    from app.models.tenant import User


class ClassPromotion(Base, TenantMixin, SoftDeleteMixin):
    """
    Class Promotion batch model.

    Represents a single end-of-year promotion operation.
    Admin creates a batch, previews entries (each student gets a default
    action), adjusts as needed, then executes the batch.
    """

    __tablename__ = "class_promotions"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        comment="Current (ending) academic year",
    )
    target_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        comment="Next (incoming) academic year",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., '2025/2026 → 2026/2027 Promotion'",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PromotionBatchStatus.DRAFT.value,
        server_default="draft",
        comment="draft, preview, in_progress, completed, failed",
    )
    total_students: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    promoted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    repeated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    graduated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    withdrawn_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    executed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who executed the promotion",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    source_academic_year: Mapped["AcademicYear"] = relationship(
        foreign_keys=[source_academic_year_id], lazy="raise",
    )
    target_academic_year: Mapped["AcademicYear"] = relationship(
        foreign_keys=[target_academic_year_id], lazy="raise",
    )
    executed_by_user: Mapped["User | None"] = relationship(lazy="raise")
    entries: Mapped[list["ClassPromotionEntry"]] = relationship(
        back_populates="promotion",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class ClassPromotionEntry(Base, TenantMixin, SoftDeleteMixin):
    """
    Per-student promotion decision within a batch.

    Default action is 'promote'. Admin can override to repeat, graduate,
    or withdraw individual students before executing the batch.
    """

    __tablename__ = "class_promotion_entries"

    promotion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_promotions.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Student's current class",
    )
    source_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
        comment="Student's current section",
    )
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Next class (null for graduated/withdrawn)",
    )
    target_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
        comment="Assigned section in new class",
    )
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PromotionAction.PROMOTE.value,
        server_default="promote",
        comment="promote, repeat, graduate, withdraw",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Reason for repeat/withdraw",
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Whether this entry has been executed",
    )

    # Relationships
    promotion: Mapped["ClassPromotion"] = relationship(
        back_populates="entries", lazy="raise",
    )
    student: Mapped["Student"] = relationship(lazy="raise")
    source_class: Mapped["Class"] = relationship(
        foreign_keys=[source_class_id], lazy="raise",
    )
    source_section: Mapped["ClassSection | None"] = relationship(
        foreign_keys=[source_section_id], lazy="raise",
    )
    target_class: Mapped["Class | None"] = relationship(
        foreign_keys=[target_class_id], lazy="raise",
    )
    target_section: Mapped["ClassSection | None"] = relationship(
        foreign_keys=[target_section_id], lazy="raise",
    )
```

---

## 1.6b Return Intent Models

**File:** `backend/app/models/admissions/return_intent.py`

```python
"""
SIMS Plus - Return Intent Models

ReturnIntentCampaign: Optional survey for boarding/private schools.
ReturnIntent: Per-student intent-to-return response.

This is NOT a gate — purely informational. In Ghana, students are
automatically promoted. This feature helps schools (especially boarding
schools) plan capacity by surveying parents about return intentions.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.school import School
    from app.models.student import Student
    from app.models.tenant import User


class ReturnIntentCampaign(Base, TenantMixin, SoftDeleteMixin):
    """
    Return Intent Campaign model.

    Optional survey sent to parents/guardians asking whether their
    child plans to return for the next academic year. Does NOT block
    promotion or enrollment — results are advisory only.
    """

    __tablename__ = "return_intent_campaigns"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
        comment="Target academic year",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="e.g., '2026/2027 Return Intent Survey'",
    )
    target_classes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of class UUIDs to target",
    )
    message_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="SMS/email template with placeholders",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
        comment="draft, sent, completed",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Response deadline",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    intents: Mapped[list["ReturnIntent"]] = relationship(
        back_populates="campaign",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class ReturnIntent(Base, TenantMixin, SoftDeleteMixin):
    """
    Return Intent model.

    Tracks individual student/parent response to a return intent survey.
    Values: pending, returning, not_returning, undecided.
    """

    __tablename__ = "return_intents"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("return_intent_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    intent: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="pending, returning, not_returning, undecided",
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    responded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent user who responded",
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Reason if not returning",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    campaign: Mapped["ReturnIntentCampaign"] = relationship(
        back_populates="intents",
        lazy="raise",
    )
    student: Mapped["Student"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    responded_by_user: Mapped["User | None"] = relationship(lazy="raise")
```

---

## 1.7 Package `__init__.py`

**File:** `backend/app/models/admissions/__init__.py`

```python
"""
SIMS Plus - Admissions Models Package

Re-exports all admissions models for convenient imports.
"""

# Enums
from app.models.admissions.enums import (
    AdmissionApplicationStatus,
    AdmissionPeriodStatus,
    DecisionType,
    EntranceExamStatus,
    PromotionAction,
    PromotionBatchStatus,
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

# Class promotion models
from app.models.admissions.promotion import ClassPromotion, ClassPromotionEntry

# Return intent models
from app.models.admissions.return_intent import ReturnIntent, ReturnIntentCampaign

__all__ = [
    # Enums
    "AdmissionApplicationStatus",
    "AdmissionPeriodStatus",
    "EntranceExamStatus",
    "DecisionType",
    "PromotionBatchStatus",
    "PromotionAction",
    "VALID_TRANSITIONS",
    "TERMINAL_STATUSES",
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
    # Class Promotion
    "ClassPromotion",
    "ClassPromotionEntry",
    # Return Intent
    "ReturnIntentCampaign",
    "ReturnIntent",
]
```

---

## 1.8 Register in Main `__init__.py`

**File to modify:** `backend/app/models/__init__.py`

Add these imports after the existing finance imports:

```python
# Admissions models
from app.models.admissions import (
    AdmissionApplicationStatus,
    AdmissionDecision,
    AdmissionFormConfig,
    AdmissionPeriod,
    AdmissionPeriodStatus,
    Application,
    ApplicationDocument,
    ApplicationGuardian,
    ApplicationNote,
    ApplicationPayment,
    ApplicationStatusHistory,
    DecisionType,
    EntranceExam,
    EntranceExamRegistration,
    EntranceExamResult,
    EntranceExamStatus,
    PromotionAction,
    PromotionBatchStatus,
    ClassPromotion,
    ClassPromotionEntry,
    ReturnIntent,
    ReturnIntentCampaign,
)
```

---

## 1.9 Alembic Migration

**File:** `backend/alembic/versions/20260303_0100_admissions_tables.py`

```python
"""Add admissions portal tables, enums, RLS policies, and indexes

Sprint 19-20: Admissions Portal

1. Create 6 enum types (applicationstatus, admissionperiodstatus, entranceexamstatus,
   decisiontype, promotionbatchstatus, promotionaction)
2. Create 16 tables with FK constraints
3. Enable RLS + FORCE RLS on all 16 tables
4. Create tenant_isolation policies using get_current_tenant_id()
5. Grant permissions to sims_app_user
6. Create composite indexes for common query patterns

Revision ID: 20260303_0100
Revises: 20260302_0100
Create Date: 2026-03-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "20260303_0100"
down_revision: Union[str, None] = "20260302_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All 16 tenant-scoped tables that need RLS
ADMISSIONS_TABLES = [
    "admission_periods",
    "admission_form_configs",
    "applications",
    "application_guardians",
    "application_documents",
    "application_payments",
    "application_status_history",
    "application_notes",
    "entrance_exams",
    "entrance_exam_registrations",
    "entrance_exam_results",
    "admission_decisions",
    "class_promotions",
    "class_promotion_entries",
    "return_intent_campaigns",
    "return_intents",
]


def upgrade() -> None:
    # =================================================================
    # PHASE 1: Create enum types
    # =================================================================
    # Note: We do NOT use SQLAlchemy Enum() in create_table for these
    # because we want precise control over the type name and values.
    # Instead, columns use sa.String() and validation is in the app layer.
    # The enums below are created for documentation/constraint purposes.

    # applicationstatus is stored as VARCHAR(30) — too many values for
    # a PG enum to be practical (14 values that may grow). Skip PG enum.
    # admissionperiodstatus, entranceexamstatus, decisiontype are small
    # enough for PG enums but we use VARCHAR for consistency.

    # =================================================================
    # PHASE 2: Create tables
    # =================================================================

    # --- Table 1: admission_periods ---
    op.create_table(
        "admission_periods",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("application_fee_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("application_fee_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entrance_exam_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("max_applications", sa.Integer(), nullable=True),
        sa.Column("target_classes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 2: admission_form_configs ---
    op.create_table(
        "admission_form_configs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_period_id", UUID(as_uuid=True), sa.ForeignKey("admission_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_schema", JSONB(), nullable=False, server_default="{}"),
        sa.Column("required_documents", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "admission_period_id", name="uq_form_configs_tenant_period"),
    )

    # --- Table 3: applications ---
    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_period_id", UUID(as_uuid=True), sa.ForeignKey("admission_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tracking_code", sa.String(100), nullable=False),
        sa.Column("applicant_first_name", sa.String(100), nullable=False),
        sa.Column("applicant_last_name", sa.String(100), nullable=False),
        sa.Column("applicant_other_names", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("target_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("custom_fields", JSONB(), nullable=False, server_default="{}"),
        sa.Column("fee_waived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("exam_waived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("converted_student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applicant_photo_url", sa.String(500), nullable=True),
        sa.Column("previous_school", sa.String(255), nullable=True),
        sa.Column("medical_info", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "tracking_code", name="uq_applications_tenant_tracking"),
    )

    # --- Table 4: application_guardians ---
    op.create_table(
        "application_guardians",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 5: application_documents ---
    op.create_table(
        "application_documents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 6: application_payments ---
    op.create_table(
        "application_payments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GHS"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "provider_reference", name="uq_payments_tenant_reference"),
    )

    # --- Table 7: application_status_history (NO soft delete, append-only) ---
    op.create_table(
        "application_status_history",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # NOTE: No updated_at or deleted_at — this is immutable audit data
    )

    # --- Table 8: application_notes ---
    op.create_table(
        "application_notes",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 9: entrance_exams ---
    op.create_table(
        "entrance_exams",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_period_id", UUID(as_uuid=True), sa.ForeignKey("admission_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("venue", sa.String(255), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 10: entrance_exam_registrations ---
    op.create_table(
        "entrance_exam_registrations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entrance_exam_id", UUID(as_uuid=True), sa.ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat_number", sa.String(20), nullable=True),
        sa.Column("attended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 11: entrance_exam_results ---
    op.create_table(
        "entrance_exam_results",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entrance_exam_id", UUID(as_uuid=True), sa.ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("grade", sa.String(10), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("scored_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 12: admission_decisions ---
    op.create_table(
        "admission_decisions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_type", sa.String(20), nullable=False),
        sa.Column("decided_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("offered_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("decision_letter_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "application_id", name="uq_decisions_tenant_application"),
    )

    # --- Table 13: class_promotions ---
    op.create_table(
        "class_promotions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_students", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promoted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("graduated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("withdrawn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 14: class_promotion_entries ---
    op.create_table(
        "class_promotion_entries",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("promotion_id", UUID(as_uuid=True), sa.ForeignKey("class_promotions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_section_id", UUID(as_uuid=True), sa.ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_section_id", UUID(as_uuid=True), sa.ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(20), nullable=False, server_default="promote"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 15: return_intent_campaigns ---
    op.create_table(
        "return_intent_campaigns",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_classes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 16: return_intents ---
    op.create_table(
        "return_intents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("return_intent_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # =================================================================
    # PHASE 3: Enable RLS on all 16 tables
    # =================================================================
    for table_name in ADMISSIONS_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """)

    # =================================================================
    # PHASE 4: Grant permissions to application role
    # =================================================================
    for table_name in ADMISSIONS_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")

    # =================================================================
    # PHASE 5: Create composite indexes for common query patterns
    # =================================================================

    # admission_periods
    op.create_index("ix_admission_periods_tenant_school", "admission_periods", ["tenant_id", "school_id"])
    op.create_index("ix_admission_periods_tenant_year", "admission_periods", ["tenant_id", "academic_year_id"])
    op.create_index("ix_admission_periods_tenant_status", "admission_periods", ["tenant_id", "status"])

    # admission_form_configs
    op.create_index("ix_admission_form_configs_tenant_period", "admission_form_configs", ["tenant_id", "admission_period_id"])

    # applications (most queried table)
    op.create_index("ix_applications_tenant_school", "applications", ["tenant_id", "school_id"])
    op.create_index("ix_applications_tenant_period", "applications", ["tenant_id", "admission_period_id"])
    op.create_index("ix_applications_tenant_status", "applications", ["tenant_id", "status"])
    op.create_index("ix_applications_tenant_class", "applications", ["tenant_id", "target_class_id"])

    # application_guardians
    op.create_index("ix_application_guardians_tenant_app", "application_guardians", ["tenant_id", "application_id"])

    # application_documents
    op.create_index("ix_application_documents_tenant_app", "application_documents", ["tenant_id", "application_id"])

    # application_payments
    op.create_index("ix_application_payments_tenant_app", "application_payments", ["tenant_id", "application_id"])

    # application_status_history
    op.create_index("ix_app_status_history_tenant_app", "application_status_history", ["tenant_id", "application_id"])
    op.create_index("ix_app_status_history_tenant_created", "application_status_history", ["tenant_id", "created_at"])

    # application_notes
    op.create_index("ix_application_notes_tenant_app", "application_notes", ["tenant_id", "application_id"])

    # entrance_exams
    op.create_index("ix_entrance_exams_tenant_period", "entrance_exams", ["tenant_id", "admission_period_id"])
    op.create_index("ix_entrance_exams_tenant_date", "entrance_exams", ["tenant_id", "exam_date"])

    # entrance_exam_registrations
    op.create_index("ix_exam_regs_tenant_exam", "entrance_exam_registrations", ["tenant_id", "entrance_exam_id"])
    op.create_index("ix_exam_regs_tenant_app", "entrance_exam_registrations", ["tenant_id", "application_id"], unique=True)

    # entrance_exam_results
    op.create_index("ix_exam_results_tenant_exam", "entrance_exam_results", ["tenant_id", "entrance_exam_id"])
    op.create_index("ix_exam_results_tenant_app", "entrance_exam_results", ["tenant_id", "application_id"], unique=True)

    # admission_decisions
    op.create_index("ix_admission_decisions_tenant_type", "admission_decisions", ["tenant_id", "decision_type"])

    # class_promotions
    op.create_index("ix_class_promotions_tenant_school", "class_promotions", ["tenant_id", "school_id"])
    op.create_index("ix_class_promotions_tenant_source_year", "class_promotions", ["tenant_id", "source_academic_year_id"])
    op.create_index("ix_class_promotions_tenant_target_year", "class_promotions", ["tenant_id", "target_academic_year_id"])

    # class_promotion_entries
    op.create_index("ix_promotion_entries_tenant_promotion", "class_promotion_entries", ["tenant_id", "promotion_id"])
    op.create_index("ix_promotion_entries_tenant_student", "class_promotion_entries", ["tenant_id", "student_id", "promotion_id"], unique=True)

    # return_intent_campaigns
    op.create_index("ix_return_intent_campaigns_tenant_school", "return_intent_campaigns", ["tenant_id", "school_id"])
    op.create_index("ix_return_intent_campaigns_tenant_year", "return_intent_campaigns", ["tenant_id", "academic_year_id"])

    # return_intents
    op.create_index("ix_return_intents_tenant_campaign", "return_intents", ["tenant_id", "campaign_id"])
    op.create_index("ix_return_intents_tenant_student_year", "return_intents", ["tenant_id", "student_id", "academic_year_id"], unique=True)


def downgrade() -> None:
    # Drop in reverse order (child tables first to respect FK constraints)

    # Drop RLS policies and grants
    for table_name in reversed(ADMISSIONS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
        op.execute(f"REVOKE ALL ON {table_name} FROM sims_app_user")

    # Drop tables in reverse order
    op.drop_table("return_intents")
    op.drop_table("return_intent_campaigns")
    op.drop_table("class_promotion_entries")
    op.drop_table("class_promotions")
    op.drop_table("admission_decisions")
    op.drop_table("entrance_exam_results")
    op.drop_table("entrance_exam_registrations")
    op.drop_table("entrance_exams")
    op.drop_table("application_notes")
    op.drop_table("application_status_history")
    op.drop_table("application_payments")
    op.drop_table("application_documents")
    op.drop_table("application_guardians")
    op.drop_table("applications")
    op.drop_table("admission_form_configs")
    op.drop_table("admission_periods")
```

---

## 1.10 Update Test Infrastructure

### `backend/tests/conftest.py` — Add to TENANT_SCOPED_TABLES

Add these 16 entries to the existing `TENANT_SCOPED_TABLES` list:

```python
TENANT_SCOPED_TABLES = [
    # ... existing 55 tables ...

    # Admissions (Sprint 19-20)
    "admission_periods",
    "admission_form_configs",
    "applications",
    "application_guardians",
    "application_documents",
    "application_payments",
    "application_status_history",
    "application_notes",
    "entrance_exams",
    "entrance_exam_registrations",
    "entrance_exam_results",
    "admission_decisions",
    "class_promotions",
    "class_promotion_entries",
    "return_intent_campaigns",
    "return_intents",
]
```

**New count:** 55 + 16 = **71 tenant-scoped tables**

### `backend/scripts/verify_rls.py` — Add to verification list

Add the same 16 table names to the `TENANT_SCOPED_TABLES` list in this script.

---

## Acceptance Criteria

- [ ] All 16 model classes created across files in `backend/app/models/admissions/`
- [ ] All models inherit `Base, TenantMixin, SoftDeleteMixin` (except `ApplicationStatusHistory` which omits `SoftDeleteMixin`)
- [ ] All relationships use `lazy="raise"` (no lazy loading)
- [ ] `__init__.py` re-exports all models
- [ ] Models registered in `backend/app/models/__init__.py`
- [ ] Migration creates all 16 tables with correct columns and constraints
- [ ] RLS enabled and forced on all 16 tables
- [ ] `tenant_isolation` policy uses `get_current_tenant_id()` on all tables
- [ ] `sims_app_user` granted SELECT, INSERT, UPDATE, DELETE on all tables
- [ ] Composite indexes created for all common query patterns
- [ ] Composite unique constraints on: `applications(tenant_id, tracking_code)`, `admission_form_configs(tenant_id, admission_period_id)`, `application_payments(tenant_id, provider_reference)`, `admission_decisions(tenant_id, application_id)`, `entrance_exam_registrations(tenant_id, application_id)`, `entrance_exam_results(tenant_id, application_id)`, `class_promotion_entries(tenant_id, student_id, promotion_id)`, `return_intents(tenant_id, student_id, academic_year_id)`
- [ ] `TENANT_SCOPED_TABLES` updated in both `conftest.py` and `verify_rls.py`
- [ ] Migration runs successfully: `alembic upgrade head`
- [ ] RLS verification passes: `python scripts/verify_rls.py`

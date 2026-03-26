# Phase 1: Inquiry & Lead Management + Interview/Screening

**Covers:** GAP 1 (EM-001 to EM-009), GAP 4 (EM-043 to EM-049)
**Estimated Effort:** 2 weeks (1 sprint)
**New Tables:** 5
**Modified Tables:** 3
**New Endpoints:** 25
**New Tests:** ~46

---

## 1. Database Schema

### 1.1 New Enums

Add to `backend/app/models/admissions/enums.py`:

```python
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
    APPLIED = "applied"       # Converted to application
    ENROLLED = "enrolled"     # Application resulted in enrollment
    LOST = "lost"             # Disengaged / unresponsive

# Valid status transitions for inquiry workflow
INQUIRY_VALID_TRANSITIONS: dict[str, list[str]] = {
    "new": ["contacted", "interested", "lost"],
    "contacted": ["interested", "lost"],
    "interested": ["applied", "lost"],
    "applied": ["enrolled"],     # Set automatically when linked application enrolls
    "enrolled": [],              # Terminal
    "lost": ["new", "contacted"],  # Can re-engage a lost lead
}

INQUIRY_TERMINAL_STATUSES = {"enrolled"}


class InterviewStatus(str, Enum):
    """Interview session lifecycle."""
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
```

### 1.2 New Tables

#### Table 1: `inquiries`

Pre-application leads capturing prospective student and guardian information.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `school_id` | UUID | No | | FK schools.id CASCADE | |
| `source` | VARCHAR(20) | No | | | InquirySource enum value |
| `status` | VARCHAR(20) | No | `'new'` | | InquiryStatus enum value |
| `first_name` | VARCHAR(100) | No | | | Prospective student first name |
| `last_name` | VARCHAR(100) | No | | | Prospective student last name |
| `date_of_birth` | DATE | Yes | | | |
| `gender` | VARCHAR(10) | Yes | | | |
| `target_class_id` | UUID | Yes | | FK classes.id SET NULL | Desired class level |
| `guardian_name` | VARCHAR(200) | No | | | Primary guardian name |
| `guardian_phone` | VARCHAR(20) | No | | | Primary guardian phone |
| `guardian_email` | VARCHAR(255) | Yes | | | Primary guardian email |
| `assigned_to` | UUID | Yes | | FK users.id SET NULL | Staff member managing lead |
| `referred_by` | VARCHAR(255) | Yes | | | Free text referral source |
| `notes` | TEXT | Yes | | | Admin notes |
| `converted_application_id` | UUID | Yes | | FK applications.id SET NULL | Links to resulting application |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Indexes:**
```sql
CREATE INDEX ix_inquiries_tenant_status ON inquiries(tenant_id, school_id, status) WHERE deleted_at IS NULL;
CREATE INDEX ix_inquiries_tenant_source ON inquiries(tenant_id, school_id, source) WHERE deleted_at IS NULL;
CREATE INDEX ix_inquiries_guardian_phone ON inquiries(tenant_id, guardian_phone) WHERE deleted_at IS NULL;
CREATE INDEX ix_inquiries_guardian_email ON inquiries(tenant_id, guardian_email) WHERE deleted_at IS NULL AND guardian_email IS NOT NULL;
CREATE INDEX ix_inquiries_assigned ON inquiries(tenant_id, assigned_to) WHERE deleted_at IS NULL AND assigned_to IS NOT NULL;
```

**RLS Policy:**
```sql
ALTER TABLE inquiries ENABLE ROW LEVEL SECURITY;
ALTER TABLE inquiries FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inquiries
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON inquiries TO sims_app_user;
```

#### Table 2: `inquiry_communications`

Append-only communication log per inquiry. **No SoftDeleteMixin** — audit records are immutable.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `inquiry_id` | UUID | No | | FK inquiries.id CASCADE | |
| `channel` | VARCHAR(20) | No | | | `sms`, `email`, `phone`, `in_person` |
| `direction` | VARCHAR(10) | No | | | `inbound`, `outbound` |
| `content` | TEXT | No | | | Summary of communication |
| `sent_by` | UUID | Yes | | FK users.id SET NULL | Staff who logged it |
| `sent_at` | TIMESTAMPTZ | No | now() | | When communication occurred |
| `created_at` | TIMESTAMPTZ | No | now() | | When record was created |
| `updated_at` | TIMESTAMPTZ | No | now() | | |

**Note:** No `deleted_at` column. This is an append-only audit log. Records are never soft-deleted.

**Indexes:**
```sql
CREATE INDEX ix_inquiry_comms_inquiry ON inquiry_communications(tenant_id, inquiry_id);
```

**RLS:** Same pattern as above (tenant_isolation policy).

#### Table 3: `inquiry_follow_ups`

Scheduled follow-up tasks assigned to staff members.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `inquiry_id` | UUID | No | | FK inquiries.id CASCADE | |
| `assigned_to` | UUID | No | | FK users.id RESTRICT | Staff responsible (RESTRICT forces reassignment before user deletion) |
| `due_date` | DATE | No | | | When follow-up is due |
| `priority` | VARCHAR(10) | No | `'medium'` | | `low`, `medium`, `high` |
| `notes` | TEXT | Yes | | | Task description |
| `completed_at` | TIMESTAMPTZ | Yes | | | When completed (null = pending) |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Indexes:**
```sql
CREATE INDEX ix_followups_pending ON inquiry_follow_ups(tenant_id, assigned_to, due_date)
    WHERE completed_at IS NULL AND deleted_at IS NULL;
CREATE INDEX ix_followups_inquiry ON inquiry_follow_ups(tenant_id, inquiry_id) WHERE deleted_at IS NULL;
```

**RLS:** Same tenant_isolation pattern.

#### Table 4: `interviews`

Interview scheduling and scoring for selective admissions.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `school_id` | UUID | No | | FK schools.id CASCADE | |
| `application_id` | UUID | No | | FK applications.id CASCADE | |
| `interviewer_id` | UUID | Yes | | FK users.id SET NULL | Staff conducting interview (nullable to preserve history) |
| `scheduled_date` | DATE | No | | | |
| `scheduled_time` | TIME | Yes | | | |
| `duration_minutes` | INTEGER | No | `30` | CHECK >= 10, <= 180 | |
| `venue` | VARCHAR(255) | No | | | Room/location |
| `status` | VARCHAR(20) | No | `'scheduled'` | | InterviewStatus enum value |
| `feedback` | TEXT | Yes | | | Written feedback |
| `score` | NUMERIC(6,2) | Yes | | | Overall score |
| `max_score` | NUMERIC(6,2) | Yes | | | Maximum possible score |
| `scoring_criteria` | JSONB | No | `'{}'` | | Breakdown by criterion (see AD-2) |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Unique constraint:** `UNIQUE(tenant_id, application_id) WHERE deleted_at IS NULL` — one active interview per application.

**Indexes:**
```sql
CREATE UNIQUE INDEX uq_interviews_application ON interviews(tenant_id, application_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_interviews_scheduled ON interviews(tenant_id, school_id, scheduled_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_interviews_interviewer ON interviews(tenant_id, interviewer_id, scheduled_date) WHERE deleted_at IS NULL;
```

**scoring_criteria JSONB format:**
```json
{
  "communication": { "score": 8, "max": 10 },
  "aptitude": { "score": 7, "max": 10 },
  "confidence": { "score": 9, "max": 10 },
  "general_knowledge": { "score": 6, "max": 10 }
}
```

**RLS:** Same tenant_isolation pattern.

#### Table 5: `screening_checklists`

Per-application screening items tracking document verification, academic record evaluation, medical checks, etc.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `application_id` | UUID | No | | FK applications.id CASCADE | |
| `item_name` | VARCHAR(255) | No | | | e.g., "Birth certificate verified" |
| `item_category` | VARCHAR(100) | No | | | `documents`, `academic`, `medical`, `other` |
| `is_completed` | BOOLEAN | No | `false` | | |
| `completed_by` | UUID | Yes | | FK users.id SET NULL | Staff who verified |
| `completed_at` | TIMESTAMPTZ | Yes | | | |
| `notes` | TEXT | Yes | | | Verification notes |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Indexes:**
```sql
CREATE INDEX ix_screening_application ON screening_checklists(tenant_id, application_id) WHERE deleted_at IS NULL;
```

**RLS:** Same tenant_isolation pattern.

### 1.3 Column Additions to Existing Tables

#### `applications` table — add `inquiry_id`

```sql
ALTER TABLE applications ADD COLUMN inquiry_id UUID REFERENCES inquiries(id) ON DELETE SET NULL;
CREATE INDEX ix_applications_inquiry ON applications(tenant_id, inquiry_id) WHERE inquiry_id IS NOT NULL AND deleted_at IS NULL;
```

**Model change:** Add to `Application` class in `backend/app/models/admissions/application.py`:
```python
inquiry_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("inquiries.id", ondelete="SET NULL"),
    nullable=True,
    default=None,
)
# Relationship
inquiry: Mapped["Inquiry | None"] = sa_relationship(
    "Inquiry", foreign_keys=[inquiry_id], lazy="raise"
)
```

#### `admission_decisions` table — add interview/screening scores

```sql
ALTER TABLE admission_decisions ADD COLUMN interview_score NUMERIC(6,2);
ALTER TABLE admission_decisions ADD COLUMN screening_score NUMERIC(6,2);
```

**Model change:** Add to `AdmissionDecision` class in `backend/app/models/admissions/decision.py`:
```python
interview_score: Mapped[Decimal | None] = mapped_column(
    Numeric(6, 2), nullable=True, default=None,
    comment="Persisted interview score for decision audit",
)
screening_score: Mapped[Decimal | None] = mapped_column(
    Numeric(6, 2), nullable=True, default=None,
    comment="Composite screening checklist score",
)
```

#### `entrance_exam_results` table — add subject-level scoring

```sql
ALTER TABLE entrance_exam_results ADD COLUMN subject_name VARCHAR(100);
ALTER TABLE entrance_exam_results ADD COLUMN weight NUMERIC(4,2) DEFAULT 1.0;
```

**Model change:** Add to `EntranceExamResult` class in `backend/app/models/admissions/exam.py`:
```python
subject_name: Mapped[str | None] = mapped_column(
    String(100), nullable=True, default=None,
    comment="Per-subject scoring. NULL = aggregate score only",
)
weight: Mapped[Decimal | None] = mapped_column(
    Numeric(4, 2), nullable=True, default=Decimal("1.0"),
    comment="Subject weight for composite score calculation",
)
```

---

## 2. Models

### 2.1 New File: `backend/app/models/admissions/inquiry.py`

```python
"""
SIMS Plus - Inquiry Models
Pre-application lead tracking: inquiries, communications, and follow-up tasks.
"""

import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    Date, DateTime, ForeignKey, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.admissions.application import Application
    from app.models.school import School
    from app.models.tenant import User


class Inquiry(Base, TenantMixin, SoftDeleteMixin):
    """
    Pre-application lead. Tracks prospective families from first contact
    through conversion to a formal application.
    """

    __tablename__ = "inquiries"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="InquirySource enum value: website, walk_in, phone, referral, event, social_media, other",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", server_default="new",
        comment="InquiryStatus enum value: new, contacted, interested, applied, enrolled, lost",
    )

    # Prospective student info
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Guardian info
    guardian_name: Mapped[str] = mapped_column(String(200), nullable=False)
    guardian_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Tracking
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    referred_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships (all lazy="raise")
    school: Mapped["School"] = sa_relationship("School", lazy="raise")
    target_class: Mapped["Class | None"] = sa_relationship(
        "Class", foreign_keys=[target_class_id], lazy="raise"
    )
    assigned_user: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[assigned_to], lazy="raise"
    )
    converted_application: Mapped["Application | None"] = sa_relationship(
        "Application", foreign_keys=[converted_application_id], lazy="raise"
    )
    communications: Mapped[list["InquiryCommunication"]] = sa_relationship(
        "InquiryCommunication", back_populates="inquiry", lazy="raise",
    )
    follow_ups: Mapped[list["InquiryFollowUp"]] = sa_relationship(
        "InquiryFollowUp", back_populates="inquiry", lazy="raise",
    )


class InquiryCommunication(Base, TenantMixin):
    """
    Append-only communication log per inquiry.
    NO SoftDeleteMixin — these are immutable audit records.
    """

    __tablename__ = "inquiry_communications"

    inquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inquiries.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="sms, email, phone, in_person",
    )
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="inbound, outbound",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    # Relationships
    inquiry: Mapped["Inquiry"] = sa_relationship(
        "Inquiry", back_populates="communications", lazy="raise"
    )
    sender: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[sent_by], lazy="raise"
    )


class InquiryFollowUp(Base, TenantMixin, SoftDeleteMixin):
    """Scheduled follow-up task assigned to a staff member."""

    __tablename__ = "inquiry_follow_ups"

    inquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inquiries.id", ondelete="CASCADE"),
        nullable=False,
    )
    # RESTRICT forces reassignment before user deletion
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium", server_default="medium",
        comment="low, medium, high",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    inquiry: Mapped["Inquiry"] = sa_relationship(
        "Inquiry", back_populates="follow_ups", lazy="raise"
    )
    assignee: Mapped["User"] = sa_relationship(
        "User", foreign_keys=[assigned_to], lazy="raise"
    )
```

### 2.2 New File: `backend/app/models/admissions/interview.py`

```python
"""
SIMS Plus - Interview & Screening Models
Interview scheduling/scoring and application screening checklists.
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.admissions.application import Application
    from app.models.school import School
    from app.models.tenant import User


class Interview(Base, TenantMixin, SoftDeleteMixin):
    """
    Interview session for a selective admissions process.
    Scoring criteria stored as JSONB for school-configurable flexibility.
    """

    __tablename__ = "interviews"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SET NULL preserves interview history if interviewer is deleted
    interviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
    )
    venue: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled",
        comment="InterviewStatus: scheduled, completed, cancelled, no_show",
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True,
        comment="Overall interview score (sum of criteria or manual)",
    )
    max_score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True,
        comment="Maximum possible score",
    )
    scoring_criteria: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
        comment='School-defined criteria: {"criterion": {"score": N, "max": N}}',
    )

    # Relationships
    school: Mapped["School"] = sa_relationship("School", lazy="raise")
    application: Mapped["Application"] = sa_relationship(
        "Application", foreign_keys=[application_id], lazy="raise"
    )
    interviewer: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[interviewer_id], lazy="raise"
    )


class ScreeningChecklist(Base, TenantMixin, SoftDeleteMixin):
    """
    Per-application screening checklist item.
    Tracks verification of documents, academic records, medical requirements, etc.
    """

    __tablename__ = "screening_checklists"
    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "application_id", "item_name", name="uq_screening_tenant_app_item"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="e.g., 'Birth certificate verified', 'Immunization records checked'",
    )
    item_category: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="documents, academic, medical, other",
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    application: Mapped["Application"] = sa_relationship(
        "Application", foreign_keys=[application_id], lazy="raise"
    )
    completer: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[completed_by], lazy="raise"
    )
```

### 2.3 Update `backend/app/models/admissions/__init__.py`

Add the following imports and __all__ entries:

```python
from app.models.admissions.enums import (
    InquirySource,
    InquiryStatus,
    InterviewStatus,
    INQUIRY_VALID_TRANSITIONS,
    INQUIRY_TERMINAL_STATUSES,
    # ... existing enum exports
)
from app.models.admissions.inquiry import (
    Inquiry,
    InquiryCommunication,
    InquiryFollowUp,
)
from app.models.admissions.interview import (
    Interview,
    ScreeningChecklist,
)
```

### 2.4 Update `backend/app/db/base.py`

Ensure the new models are imported so Alembic discovers them:

```python
from app.models.admissions.inquiry import Inquiry, InquiryCommunication, InquiryFollowUp  # noqa
from app.models.admissions.interview import Interview, ScreeningChecklist  # noqa
```

---

## 3. Schemas

### 3.1 New File: `backend/app/schemas/inquiry.py`

```python
"""
SIMS Plus - Inquiry Schemas
Pydantic schemas for inquiry/lead management endpoints.
"""

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Enums for schema validation ---

class InquirySourceEnum(str, Enum):
    WEBSITE = "website"
    WALK_IN = "walk_in"
    PHONE = "phone"
    REFERRAL = "referral"
    EVENT = "event"
    SOCIAL_MEDIA = "social_media"
    OTHER = "other"


class InquiryStatusEnum(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    APPLIED = "applied"
    ENROLLED = "enrolled"
    LOST = "lost"


# --- Inquiry Schemas ---

class InquiryCreate(BaseSchema):
    """Create a new inquiry/lead."""
    source: InquirySourceEnum
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=10)
    target_class_id: UUID | None = None
    guardian_name: str = Field(..., min_length=1, max_length=200)
    guardian_phone: str = Field(..., min_length=1, max_length=20)
    guardian_email: EmailStr | None = None
    assigned_to: UUID | None = None
    referred_by: str | None = Field(None, max_length=255)
    notes: str | None = None


class InquiryUpdate(BaseSchema):
    """Update existing inquiry fields."""
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=10)
    target_class_id: UUID | None = None
    guardian_name: str | None = Field(None, min_length=1, max_length=200)
    guardian_phone: str | None = Field(None, min_length=1, max_length=20)
    guardian_email: EmailStr | None = None
    notes: str | None = None
    referred_by: str | None = Field(None, max_length=255)


class InquiryStatusUpdate(BaseSchema):
    """Transition inquiry status."""
    status: InquiryStatusEnum
    notes: str | None = None


class InquiryAssign(BaseSchema):
    """Assign inquiry to a staff member."""
    assigned_to: UUID


class InquiryConvert(BaseSchema):
    """Convert inquiry into an application."""
    admission_period_id: UUID
    target_class_id: UUID | None = None


class InquiryResponse(BaseSchema):
    """Full inquiry detail response."""
    id: UUID
    school_id: UUID
    source: str
    status: str
    first_name: str
    last_name: str
    date_of_birth: date | None
    gender: str | None
    target_class_id: UUID | None
    target_class_name: str | None = None
    guardian_name: str
    guardian_phone: str
    guardian_email: str | None
    assigned_to: UUID | None
    assigned_to_name: str | None = None
    referred_by: str | None
    notes: str | None
    converted_application_id: UUID | None
    created_at: datetime
    updated_at: datetime


class InquiryListResponse(BaseSchema):
    """Paginated inquiry list."""
    items: list[InquiryResponse]
    total: int
    page: int
    page_size: int
    pages: int


# --- Communication Schemas ---

class CommunicationCreate(BaseSchema):
    """Log a communication entry."""
    channel: str = Field(..., pattern=r"^(sms|email|phone|in_person)$")
    direction: str = Field(..., pattern=r"^(inbound|outbound)$")
    content: str = Field(..., min_length=1, max_length=5000)
    sent_at: datetime | None = None  # Default: now


class CommunicationResponse(BaseSchema):
    id: UUID
    inquiry_id: UUID
    channel: str
    direction: str
    content: str
    sent_by: UUID | None
    sent_by_name: str | None = None
    sent_at: datetime
    created_at: datetime


# --- Follow-Up Schemas ---

class FollowUpCreate(BaseSchema):
    """Create a follow-up task."""
    due_date: date
    assigned_to: UUID
    priority: str = Field("medium", pattern=r"^(low|medium|high)$")
    notes: str | None = None


class FollowUpComplete(BaseSchema):
    """Complete a follow-up task."""
    notes: str | None = None


class FollowUpResponse(BaseSchema):
    id: UUID
    inquiry_id: UUID
    assigned_to: UUID
    assigned_to_name: str | None = None
    due_date: date
    priority: str
    notes: str | None
    completed_at: datetime | None
    is_overdue: bool = False
    created_at: datetime


# --- Bulk Import Schemas ---

class BulkInquiryImportRow(BaseSchema):
    """Single row in bulk import."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    guardian_name: str = Field(..., min_length=1, max_length=200)
    guardian_phone: str = Field(..., min_length=1, max_length=20)
    guardian_email: EmailStr | None = None
    target_class_id: UUID | None = None
    notes: str | None = None


class BulkInquiryImport(BaseSchema):
    """Bulk import from event/fair."""
    inquiries: list[BulkInquiryImportRow] = Field(..., max_length=200)
    source: InquirySourceEnum = InquirySourceEnum.EVENT


class BulkImportResponse(BaseSchema):
    created: int
    duplicates_skipped: int
    errors: list[str]


# --- Duplicate Check ---

class DuplicateCheckResponse(BaseSchema):
    is_duplicate: bool
    matches: list[InquiryResponse]


# --- Stats ---

class InquiryStatsResponse(BaseSchema):
    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    conversion_rate: float  # applied / total
    overdue_follow_ups: int
```

### 3.2 New File: `backend/app/schemas/interview.py`

```python
"""
SIMS Plus - Interview & Screening Schemas
Pydantic schemas for interview scheduling and screening checklist endpoints.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Interview Schemas ---

class InterviewCreate(BaseSchema):
    """Schedule an interview for an application."""
    application_id: UUID
    interviewer_id: UUID
    scheduled_date: date
    scheduled_time: time | None = None
    duration_minutes: int = Field(30, ge=10, le=180)
    venue: str = Field(..., min_length=1, max_length=255)


class InterviewUpdate(BaseSchema):
    """Reschedule or update interview details."""
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    duration_minutes: int | None = Field(None, ge=10, le=180)
    venue: str | None = Field(None, min_length=1, max_length=255)
    interviewer_id: UUID | None = None


class InterviewFeedback(BaseSchema):
    """Record interview outcome and scoring."""
    status: str = Field(..., pattern=r"^(completed|no_show)$")
    feedback: str | None = None
    score: Decimal | None = Field(None, ge=0)
    max_score: Decimal | None = Field(None, ge=0)
    scoring_criteria: dict[str, Any] | None = None


class InterviewResponse(BaseSchema):
    id: UUID
    school_id: UUID
    application_id: UUID
    interviewer_id: UUID | None
    interviewer_name: str | None = None
    applicant_name: str | None = None
    scheduled_date: date
    scheduled_time: time | None
    duration_minutes: int
    venue: str
    status: str
    feedback: str | None
    score: Decimal | None
    max_score: Decimal | None
    scoring_criteria: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InterviewListResponse(BaseSchema):
    items: list[InterviewResponse]
    total: int
    page: int
    page_size: int
    pages: int


# --- Screening Checklist Schemas ---

class ScreeningItemCreate(BaseSchema):
    """Add a screening checklist item."""
    item_name: str = Field(..., min_length=1, max_length=255)
    item_category: str = Field(..., pattern=r"^(documents|academic|medical|other)$")


class ScreeningItemBulkCreate(BaseSchema):
    """Bulk-add screening items (apply template)."""
    items: list[ScreeningItemCreate] = Field(..., max_length=50)


class ScreeningItemComplete(BaseSchema):
    """Mark a screening item as completed."""
    notes: str | None = None


class ScreeningItemResponse(BaseSchema):
    id: UUID
    application_id: UUID
    item_name: str
    item_category: str
    is_completed: bool
    completed_by: UUID | None
    completed_by_name: str | None = None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime


class ScreeningProgressResponse(BaseSchema):
    """Screening progress summary for an application."""
    application_id: UUID
    total_items: int
    completed_items: int
    progress_pct: float
    items: list[ScreeningItemResponse]
```

---

## 4. Services

### 4.1 New File: `backend/app/services/admissions/inquiry_service.py`

```python
"""
SIMS Plus - Inquiry Service
Handles inquiry/lead CRUD, status transitions, communication logging,
follow-up task management, duplicate detection, and bulk import.
"""

import uuid
from datetime import UTC, date, datetime

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admissions import (
    Application,
    ApplicationGuardian,
    Inquiry,
    InquiryCommunication,
    InquiryFollowUp,
    InquirySource,
    InquiryStatus,
    INQUIRY_VALID_TRANSITIONS,
    INQUIRY_TERMINAL_STATUSES,
)
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger(__name__)


class InquiryServiceError(Exception):
    def __init__(self, message: str, code: str = "INQUIRY_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InquiryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- CRUD ----

    async def create(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        source: str,
        first_name: str,
        last_name: str,
        guardian_name: str,
        guardian_phone: str,
        guardian_email: str | None = None,
        date_of_birth: date | None = None,
        gender: str | None = None,
        target_class_id: uuid.UUID | None = None,
        assigned_to: uuid.UUID | None = None,
        referred_by: str | None = None,
        notes: str | None = None,
    ) -> Inquiry:
        """Create a new inquiry/lead."""
        # Validate source enum
        if source not in [s.value for s in InquirySource]:
            raise InquiryServiceError(f"Invalid source: {source}", "INVALID_SOURCE")

        inquiry = Inquiry(
            tenant_id=tenant_id,
            school_id=school_id,
            source=source,
            status=InquiryStatus.NEW.value,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            target_class_id=target_class_id,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
            guardian_email=guardian_email,
            assigned_to=assigned_to,
            referred_by=referred_by,
            notes=notes,
        )
        self.db.add(inquiry)
        await self.db.flush()
        await self.db.refresh(inquiry)

        logger.info("inquiry_created", inquiry_id=str(inquiry.id), source=source)
        return inquiry

    async def get(self, tenant_id: uuid.UUID, inquiry_id: uuid.UUID) -> Inquiry:
        """Get inquiry by ID with defense-in-depth tenant check."""
        result = await self.db.execute(
            select(Inquiry)
            .filter(
                Inquiry.id == inquiry_id,
                Inquiry.tenant_id == tenant_id,
                Inquiry.deleted_at.is_(None),
            )
        )
        inquiry = result.scalar_one_or_none()
        if not inquiry:
            raise InquiryServiceError("Inquiry not found", "NOT_FOUND")
        return inquiry

    async def list_inquiries(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        status: str | None = None,
        source: str | None = None,
        assigned_to: uuid.UUID | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Inquiry], int]:
        """List inquiries with filters and pagination."""
        query = (
            select(Inquiry)
            .filter(
                Inquiry.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                Inquiry.deleted_at.is_(None),
            )
        )

        if status:
            query = query.filter(Inquiry.status == status)
        if source:
            query = query.filter(Inquiry.source == source)
        if assigned_to:
            query = query.filter(Inquiry.assigned_to == assigned_to)
        if search:
            escaped = escape_ilike(search)
            query = query.filter(
                or_(
                    Inquiry.first_name.ilike(f"%{escaped}%"),
                    Inquiry.last_name.ilike(f"%{escaped}%"),
                    Inquiry.guardian_name.ilike(f"%{escaped}%"),
                    Inquiry.guardian_phone.ilike(f"%{escaped}%"),
                )
            )

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate
        query = query.order_by(Inquiry.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    _PROTECTED_FIELDS = {"id", "tenant_id", "school_id", "created_at", "updated_at", "deleted_at"}

    async def update(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
        **kwargs,
    ) -> Inquiry:
        """Update inquiry fields."""
        inquiry = await self.get(tenant_id, inquiry_id)
        for key, value in kwargs.items():
            if key in self._PROTECTED_FIELDS:
                continue
            if value is not None and hasattr(inquiry, key):
                setattr(inquiry, key, value)
        await self.db.flush()
        await self.db.refresh(inquiry)
        return inquiry

    async def delete(self, tenant_id: uuid.UUID, inquiry_id: uuid.UUID) -> None:
        """Soft-delete an inquiry."""
        inquiry = await self.get(tenant_id, inquiry_id)
        inquiry.deleted_at = datetime.now(UTC)
        await self.db.flush()

    # ---- Status Transitions ----

    async def update_status(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
        *,
        status: str,
        notes: str | None = None,
    ) -> Inquiry:
        """Transition inquiry status with validation."""
        inquiry = await self.get(tenant_id, inquiry_id)

        valid_targets = INQUIRY_VALID_TRANSITIONS.get(inquiry.status, [])
        if status not in valid_targets:
            raise InquiryServiceError(
                f"Cannot transition from '{inquiry.status}' to '{status}'. "
                f"Valid transitions: {valid_targets}",
                "INVALID_TRANSITION",
            )

        old_status = inquiry.status
        inquiry.status = status
        if notes:
            inquiry.notes = notes
        await self.db.flush()
        await self.db.refresh(inquiry)

        logger.info(
            "inquiry_status_changed",
            inquiry_id=str(inquiry_id),
            from_status=old_status,
            to_status=status,
        )
        return inquiry

    # ---- Assignment ----

    async def assign(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Inquiry:
        """Assign inquiry to a staff member."""
        inquiry = await self.get(tenant_id, inquiry_id)
        inquiry.assigned_to = user_id
        await self.db.flush()
        await self.db.refresh(inquiry)
        return inquiry

    # ---- Conversion ----

    async def convert_to_application(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
        *,
        admission_period_id: uuid.UUID,
        target_class_id: uuid.UUID | None = None,
        converted_by: uuid.UUID,
    ) -> Application:
        """
        Convert inquiry into an application.

        Steps:
        1. Validate inquiry is in 'interested' status
        2. Check inquiry not already converted
        3. Create Application pre-populated with inquiry data
        4. Copy guardian info to ApplicationGuardian
        5. Set inquiry status to 'applied' and link converted_application_id
        """
        import secrets
        from app.models.admissions import AdmissionApplicationStatus

        inquiry = await self.get(tenant_id, inquiry_id)

        if inquiry.converted_application_id is not None:
            raise InquiryServiceError(
                "Inquiry already converted to application",
                "ALREADY_CONVERTED",
            )

        if inquiry.status not in ("interested", "contacted"):
            raise InquiryServiceError(
                f"Inquiry must be in 'interested' or 'contacted' status to convert. Current: {inquiry.status}",
                "INVALID_STATUS",
            )

        # Create application
        application = Application(
            tenant_id=tenant_id,
            school_id=inquiry.school_id,
            admission_period_id=admission_period_id,
            tracking_code=secrets.token_urlsafe(48),
            applicant_first_name=inquiry.first_name,
            applicant_last_name=inquiry.last_name,
            date_of_birth=inquiry.date_of_birth,
            gender=inquiry.gender,
            target_class_id=target_class_id or inquiry.target_class_id,
            status=AdmissionApplicationStatus.DRAFT.value,
            custom_fields={},
            inquiry_id=inquiry.id,
        )
        self.db.add(application)
        await self.db.flush()

        # Copy guardian
        guardian = ApplicationGuardian(
            tenant_id=tenant_id,
            application_id=application.id,
            first_name=inquiry.guardian_name.split(" ", 1)[0] if inquiry.guardian_name else "",
            last_name=inquiry.guardian_name.split(" ", 1)[-1] if inquiry.guardian_name else "",
            phone=inquiry.guardian_phone,
            email=inquiry.guardian_email,
            relationship="parent",
            is_primary=True,
        )
        self.db.add(guardian)

        # Update inquiry
        inquiry.status = InquiryStatus.APPLIED.value
        inquiry.converted_application_id = application.id
        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "inquiry_converted",
            inquiry_id=str(inquiry_id),
            application_id=str(application.id),
        )
        return application

    # ---- Communications ----

    async def add_communication(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
        *,
        channel: str,
        direction: str,
        content: str,
        sent_by: uuid.UUID | None = None,
        sent_at: datetime | None = None,
    ) -> InquiryCommunication:
        """Add a communication log entry."""
        # Validate inquiry exists
        await self.get(tenant_id, inquiry_id)

        comm = InquiryCommunication(
            tenant_id=tenant_id,
            inquiry_id=inquiry_id,
            channel=channel,
            direction=direction,
            content=content,
            sent_by=sent_by,
            sent_at=sent_at or datetime.now(UTC),
        )
        self.db.add(comm)
        await self.db.flush()
        await self.db.refresh(comm)
        return comm

    async def list_communications(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
    ) -> list[InquiryCommunication]:
        """List all communications for an inquiry (chronological)."""
        await self.get(tenant_id, inquiry_id)

        result = await self.db.execute(
            select(InquiryCommunication)
            .filter(
                InquiryCommunication.tenant_id == tenant_id,
                InquiryCommunication.inquiry_id == inquiry_id,
            )
            .order_by(InquiryCommunication.sent_at.asc())
        )
        return list(result.scalars().all())

    # ---- Follow-Ups ----

    async def create_follow_up(
        self,
        tenant_id: uuid.UUID,
        inquiry_id: uuid.UUID,
        *,
        assigned_to: uuid.UUID,
        due_date: date,
        priority: str = "medium",
        notes: str | None = None,
    ) -> InquiryFollowUp:
        """Create a follow-up task."""
        await self.get(tenant_id, inquiry_id)

        follow_up = InquiryFollowUp(
            tenant_id=tenant_id,
            inquiry_id=inquiry_id,
            assigned_to=assigned_to,
            due_date=due_date,
            priority=priority,
            notes=notes,
        )
        self.db.add(follow_up)
        await self.db.flush()
        await self.db.refresh(follow_up)
        return follow_up

    async def complete_follow_up(
        self,
        tenant_id: uuid.UUID,
        follow_up_id: uuid.UUID,
        *,
        notes: str | None = None,
    ) -> InquiryFollowUp:
        """Mark a follow-up task as completed."""
        result = await self.db.execute(
            select(InquiryFollowUp).filter(
                InquiryFollowUp.id == follow_up_id,
                InquiryFollowUp.tenant_id == tenant_id,
                InquiryFollowUp.deleted_at.is_(None),
            )
        )
        follow_up = result.scalar_one_or_none()
        if not follow_up:
            raise InquiryServiceError("Follow-up not found", "NOT_FOUND")

        if follow_up.completed_at is not None:
            raise InquiryServiceError("Follow-up already completed", "ALREADY_COMPLETED")

        follow_up.completed_at = datetime.now(UTC)
        if notes:
            follow_up.notes = notes
        await self.db.flush()
        await self.db.refresh(follow_up)
        return follow_up

    async def list_pending_follow_ups(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        assigned_to: uuid.UUID | None = None,
        overdue_only: bool = False,
    ) -> list[InquiryFollowUp]:
        """List pending follow-ups, optionally filtered by assignee."""
        query = (
            select(InquiryFollowUp)
            .join(Inquiry, InquiryFollowUp.inquiry_id == Inquiry.id)
            .filter(
                InquiryFollowUp.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                InquiryFollowUp.completed_at.is_(None),
                InquiryFollowUp.deleted_at.is_(None),
            )
        )
        if assigned_to:
            query = query.filter(InquiryFollowUp.assigned_to == assigned_to)
        if overdue_only:
            query = query.filter(InquiryFollowUp.due_date < date.today())
        query = query.order_by(InquiryFollowUp.due_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ---- Duplicate Detection ----

    async def check_duplicate(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        phone: str | None = None,
        email: str | None = None,
    ) -> list[Inquiry]:
        """
        Check for potential duplicate inquiries by phone or email.
        Returns matching inquiries (advisory, not blocking).
        """
        if not phone and not email:
            return []

        conditions = []
        if phone:
            conditions.append(Inquiry.guardian_phone == phone)
        if email:
            conditions.append(Inquiry.guardian_email == email)

        result = await self.db.execute(
            select(Inquiry).filter(
                Inquiry.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                Inquiry.deleted_at.is_(None),
                or_(*conditions),
            )
        )
        return list(result.scalars().all())

    # ---- Bulk Import ----

    async def bulk_import(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        inquiries: list[dict],
        source: str,
    ) -> dict:
        """
        Bulk import inquiries from events/fairs.
        Deduplicates by guardian_phone within the same school.
        Returns { created: N, duplicates_skipped: N, errors: [...] }
        """
        created = 0
        duplicates_skipped = 0
        errors: list[str] = []

        for idx, row in enumerate(inquiries):
            try:
                # Check duplicate by phone
                dupes = await self.check_duplicate(
                    tenant_id, school_id, phone=row.get("guardian_phone")
                )
                if dupes:
                    duplicates_skipped += 1
                    continue

                inquiry = Inquiry(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    source=source,
                    status=InquiryStatus.NEW.value,
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    guardian_name=row["guardian_name"],
                    guardian_phone=row["guardian_phone"],
                    guardian_email=row.get("guardian_email"),
                    target_class_id=row.get("target_class_id"),
                    notes=row.get("notes"),
                )
                self.db.add(inquiry)
                created += 1
            except Exception as e:
                errors.append(f"Row {idx + 1}: {str(e)}")

        if created > 0:
            await self.db.flush()

        logger.info(
            "inquiry_bulk_import",
            created=created,
            duplicates_skipped=duplicates_skipped,
            errors_count=len(errors),
        )
        return {
            "created": created,
            "duplicates_skipped": duplicates_skipped,
            "errors": errors,
        }

    # ---- Stats ----

    async def get_stats(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
    ) -> dict:
        """Get inquiry statistics for dashboard."""
        base_filter = and_(
            Inquiry.tenant_id == tenant_id,
            Inquiry.school_id == school_id,
            Inquiry.deleted_at.is_(None),
        )

        # Total
        total_result = await self.db.execute(
            select(func.count()).select_from(Inquiry).filter(base_filter)
        )
        total = total_result.scalar() or 0

        # By status
        status_result = await self.db.execute(
            select(Inquiry.status, func.count())
            .filter(base_filter)
            .group_by(Inquiry.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        # By source
        source_result = await self.db.execute(
            select(Inquiry.source, func.count())
            .filter(base_filter)
            .group_by(Inquiry.source)
        )
        by_source = {row[0]: row[1] for row in source_result.all()}

        # Conversion rate
        applied_count = by_status.get("applied", 0) + by_status.get("enrolled", 0)
        conversion_rate = (applied_count / total * 100) if total > 0 else 0.0

        # Overdue follow-ups
        overdue_result = await self.db.execute(
            select(func.count())
            .select_from(InquiryFollowUp)
            .join(Inquiry, InquiryFollowUp.inquiry_id == Inquiry.id)
            .filter(
                InquiryFollowUp.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                InquiryFollowUp.completed_at.is_(None),
                InquiryFollowUp.deleted_at.is_(None),
                InquiryFollowUp.due_date < date.today(),
            )
        )
        overdue_follow_ups = overdue_result.scalar() or 0

        return {
            "total": total,
            "by_status": by_status,
            "by_source": by_source,
            "conversion_rate": round(conversion_rate, 1),
            "overdue_follow_ups": overdue_follow_ups,
        }
```

### 4.2 New File: `backend/app/services/admissions/interview_service.py`

```python
"""
SIMS Plus - Interview & Screening Service
Handles interview scheduling, feedback recording, and screening checklist management.
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    Application,
    Interview,
    InterviewStatus,
    ScreeningChecklist,
)

logger = structlog.get_logger(__name__)


class InterviewServiceError(Exception):
    def __init__(self, message: str, code: str = "INTERVIEW_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InterviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Interview CRUD ----

    async def schedule(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        application_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        scheduled_date: date,
        scheduled_time: time | None = None,
        duration_minutes: int = 30,
        venue: str,
    ) -> Interview:
        """
        Schedule an interview for an application.

        Validations:
        1. Application exists and is not in a terminal status
        2. No existing active interview for this application
        3. Interviewer has no overlapping interview at same date/time
        """
        # Validate application
        app_result = await self.db.execute(
            select(Application).filter(
                Application.id == application_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise InterviewServiceError("Application not found", "APP_NOT_FOUND")

        from app.models.admissions.enums import TERMINAL_STATUSES
        if application.status in TERMINAL_STATUSES:
            raise InterviewServiceError(
                f"Cannot schedule interview for application in '{application.status}' status",
                "TERMINAL_STATUS",
            )

        # Check no existing active interview
        existing = await self.db.execute(
            select(Interview).filter(
                Interview.tenant_id == tenant_id,
                Interview.application_id == application_id,
                Interview.status == InterviewStatus.SCHEDULED.value,
                Interview.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise InterviewServiceError(
                "An active interview already exists for this application",
                "INTERVIEW_EXISTS",
            )

        # Check interviewer overlap (same date + overlapping time)
        if scheduled_time:
            overlap = await self._check_interviewer_overlap(
                tenant_id, interviewer_id, scheduled_date, scheduled_time, duration_minutes
            )
            if overlap:
                raise InterviewServiceError(
                    f"Interviewer has an overlapping interview at {scheduled_time}",
                    "INTERVIEWER_CONFLICT",
                )

        interview = Interview(
            tenant_id=tenant_id,
            school_id=school_id,
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            venue=venue,
            status=InterviewStatus.SCHEDULED.value,
            scoring_criteria={},
        )
        self.db.add(interview)
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "interview_scheduled",
            interview_id=str(interview.id),
            application_id=str(application_id),
            date=str(scheduled_date),
        )
        return interview

    async def _check_interviewer_overlap(
        self,
        tenant_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        target_date: date,
        target_time: time,
        duration: int,
    ) -> bool:
        """Check if interviewer has an overlapping interview."""
        result = await self.db.execute(
            select(Interview).filter(
                Interview.tenant_id == tenant_id,
                Interview.interviewer_id == interviewer_id,
                Interview.scheduled_date == target_date,
                Interview.status == InterviewStatus.SCHEDULED.value,
                Interview.scheduled_time.isnot(None),
                Interview.deleted_at.is_(None),
            )
        )
        existing_interviews = result.scalars().all()

        from datetime import timedelta
        target_start = datetime.combine(target_date, target_time)
        target_end = target_start + timedelta(minutes=duration)

        for existing in existing_interviews:
            ex_start = datetime.combine(existing.scheduled_date, existing.scheduled_time)
            ex_end = ex_start + timedelta(minutes=existing.duration_minutes)
            # Overlap check
            if target_start < ex_end and target_end > ex_start:
                return True
        return False

    async def update(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
        **kwargs,
    ) -> Interview:
        """Update interview details (reschedule)."""
        interview = await self._get_interview(tenant_id, interview_id)

        if interview.status != InterviewStatus.SCHEDULED.value:
            raise InterviewServiceError(
                "Can only update scheduled interviews",
                "NOT_SCHEDULED",
            )

        for key, value in kwargs.items():
            if value is not None and hasattr(interview, key):
                setattr(interview, key, value)
        await self.db.flush()
        await self.db.refresh(interview)
        return interview

    async def record_feedback(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
        *,
        status: str,
        feedback: str | None = None,
        score: Decimal | None = None,
        max_score: Decimal | None = None,
        scoring_criteria: dict | None = None,
    ) -> Interview:
        """
        Record interview outcome. Sets status to 'completed' or 'no_show'.
        If scoring_criteria provided, auto-calculates total score.
        """
        interview = await self._get_interview(tenant_id, interview_id)

        if interview.status != InterviewStatus.SCHEDULED.value:
            raise InterviewServiceError(
                "Can only record feedback for scheduled interviews",
                "NOT_SCHEDULED",
            )

        if status not in (InterviewStatus.COMPLETED.value, InterviewStatus.NO_SHOW.value):
            raise InterviewServiceError(
                f"Invalid feedback status: {status}",
                "INVALID_STATUS",
            )

        interview.status = status
        interview.feedback = feedback

        if scoring_criteria:
            interview.scoring_criteria = scoring_criteria
            # Auto-calculate total score from criteria
            total_score = sum(
                c.get("score", 0) for c in scoring_criteria.values()
                if isinstance(c, dict)
            )
            total_max = sum(
                c.get("max", 0) for c in scoring_criteria.values()
                if isinstance(c, dict)
            )
            interview.score = Decimal(str(total_score))
            interview.max_score = Decimal(str(total_max))
        else:
            interview.score = score
            interview.max_score = max_score

        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "interview_feedback_recorded",
            interview_id=str(interview_id),
            status=status,
            score=str(interview.score),
        )
        return interview

    async def cancel(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
    ) -> Interview:
        """Cancel a scheduled interview."""
        interview = await self._get_interview(tenant_id, interview_id)

        if interview.status != InterviewStatus.SCHEDULED.value:
            raise InterviewServiceError(
                "Can only cancel scheduled interviews",
                "NOT_SCHEDULED",
            )

        interview.status = InterviewStatus.CANCELLED.value
        await self.db.flush()
        await self.db.refresh(interview)
        return interview

    async def list_interviews(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        interviewer_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Interview], int]:
        """List interviews with filters."""
        query = (
            select(Interview).filter(
                Interview.tenant_id == tenant_id,
                Interview.school_id == school_id,
                Interview.deleted_at.is_(None),
            )
        )
        if date_from:
            query = query.filter(Interview.scheduled_date >= date_from)
        if date_to:
            query = query.filter(Interview.scheduled_date <= date_to)
        if interviewer_id:
            query = query.filter(Interview.interviewer_id == interviewer_id)
        if status:
            query = query.filter(Interview.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(Interview.scheduled_date.asc(), Interview.scheduled_time.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total

    async def get_by_application(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Interview | None:
        """Get the active interview for an application."""
        result = await self.db.execute(
            select(Interview).filter(
                Interview.tenant_id == tenant_id,
                Interview.application_id == application_id,
                Interview.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_interview(self, tenant_id: uuid.UUID, interview_id: uuid.UUID) -> Interview:
        result = await self.db.execute(
            select(Interview).filter(
                Interview.id == interview_id,
                Interview.tenant_id == tenant_id,
                Interview.deleted_at.is_(None),
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise InterviewServiceError("Interview not found", "NOT_FOUND")
        return interview

    # ---- Screening Checklist ----

    async def create_screening_item(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        item_name: str,
        item_category: str,
    ) -> ScreeningChecklist:
        """Add a screening checklist item to an application."""
        item = ScreeningChecklist(
            tenant_id=tenant_id,
            application_id=application_id,
            item_name=item_name,
            item_category=item_category,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def bulk_create_screening_items(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        items: list[dict],
    ) -> list[ScreeningChecklist]:
        """Bulk-add screening items (apply a template)."""
        created = []
        for item_data in items:
            item = ScreeningChecklist(
                tenant_id=tenant_id,
                application_id=application_id,
                item_name=item_data["item_name"],
                item_category=item_data["item_category"],
            )
            self.db.add(item)
            created.append(item)
        await self.db.flush()
        for item in created:
            await self.db.refresh(item)
        return created

    async def complete_screening_item(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        notes: str | None = None,
    ) -> ScreeningChecklist:
        """Mark a screening item as completed."""
        result = await self.db.execute(
            select(ScreeningChecklist).filter(
                ScreeningChecklist.id == item_id,
                ScreeningChecklist.tenant_id == tenant_id,
                ScreeningChecklist.deleted_at.is_(None),
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise InterviewServiceError("Screening item not found", "NOT_FOUND")

        if item.is_completed:
            raise InterviewServiceError("Item already completed", "ALREADY_COMPLETED")

        item.is_completed = True
        item.completed_by = user_id
        item.completed_at = datetime.now(UTC)
        if notes:
            item.notes = notes
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_screening_progress(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> dict:
        """Get screening completion progress for an application."""
        result = await self.db.execute(
            select(ScreeningChecklist).filter(
                ScreeningChecklist.tenant_id == tenant_id,
                ScreeningChecklist.application_id == application_id,
                ScreeningChecklist.deleted_at.is_(None),
            ).order_by(ScreeningChecklist.item_category, ScreeningChecklist.created_at)
        )
        items = list(result.scalars().all())

        total = len(items)
        completed = sum(1 for i in items if i.is_completed)
        progress_pct = (completed / total * 100) if total > 0 else 0.0

        return {
            "application_id": application_id,
            "total_items": total,
            "completed_items": completed,
            "progress_pct": round(progress_pct, 1),
            "items": items,
        }
```

### 4.3 Update `backend/app/services/admissions/__init__.py`

Add:
```python
from app.services.admissions.inquiry_service import (
    InquiryService,
    InquiryServiceError,
)
from app.services.admissions.interview_service import (
    InterviewService,
    InterviewServiceError,
)
```

---

## 5. Endpoints

### 5.1 New File: `backend/app/api/v1/endpoints/admissions/inquiries.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/inquiries` | Create inquiry | admissions.create | InquiryCreate | InquiryResponse (201) |
| GET | `/admissions/inquiries` | List inquiries | admissions.read | Query: status, source, assigned_to, search, page, page_size | InquiryListResponse |
| GET | `/admissions/inquiries/{id}` | Get detail | admissions.read | - | InquiryResponse |
| PATCH | `/admissions/inquiries/{id}` | Update fields | admissions.update | InquiryUpdate | InquiryResponse |
| PATCH | `/admissions/inquiries/{id}/status` | Change status | admissions.update | InquiryStatusUpdate | InquiryResponse |
| PATCH | `/admissions/inquiries/{id}/assign` | Assign to staff | admissions.update | InquiryAssign | InquiryResponse |
| POST | `/admissions/inquiries/{id}/convert` | Convert to application | admissions.create | InquiryConvert | ApplicationResponse (201) |
| DELETE | `/admissions/inquiries/{id}` | Soft delete | admissions.delete | - | 204 |
| POST | `/admissions/inquiries/{id}/communications` | Add comm log | admissions.update | CommunicationCreate | CommunicationResponse (201) |
| GET | `/admissions/inquiries/{id}/communications` | List comms | admissions.read | - | list[CommunicationResponse] |
| POST | `/admissions/inquiries/{id}/follow-ups` | Create task | admissions.update | FollowUpCreate | FollowUpResponse (201) |
| PATCH | `/admissions/inquiries/follow-ups/{id}/complete` | Complete task | admissions.update | FollowUpComplete | FollowUpResponse |
| GET | `/admissions/inquiries/follow-ups/pending` | My pending tasks | admissions.read | Query: overdue_only | list[FollowUpResponse] |
| POST | `/admissions/inquiries/bulk-import` | Bulk import | admissions.create | BulkInquiryImport | BulkImportResponse |
| GET | `/admissions/inquiries/check-duplicate` | Dup check | admissions.read | Query: phone, email | DuplicateCheckResponse |
| GET | `/admissions/inquiries/stats` | Statistics | admissions.read | - | InquiryStatsResponse |

**Endpoint implementation pattern** (follows existing decisions.py pattern):

```python
from uuid import UUID

router = APIRouter(prefix="/inquiries")

def _handle_error(e: InquiryServiceError) -> HTTPException:
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_TRANSITION": 422,
        "INVALID_SOURCE": 422,
        "ALREADY_CONVERTED": 409,
        "INVALID_STATUS": 422,
        "ALREADY_COMPLETED": 409,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )

@router.post(
    "",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create inquiry",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def create_inquiry(
    data: InquiryCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryResponse:
    try:
        svc = InquiryService(db)
        inquiry = await svc.create(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            source=data.source.value,
            first_name=data.first_name,
            last_name=data.last_name,
            guardian_name=data.guardian_name,
            guardian_phone=data.guardian_phone,
            guardian_email=data.guardian_email,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            target_class_id=data.target_class_id,
            assigned_to=data.assigned_to,
            referred_by=data.referred_by,
            notes=data.notes,
        )
        return InquiryResponse.model_validate(inquiry)
    except InquiryServiceError as e:
        raise _handle_error(e)
```

### 5.2 New File: `backend/app/api/v1/endpoints/admissions/interviews.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/interviews` | Schedule | admissions.update | InterviewCreate | InterviewResponse (201) |
| GET | `/admissions/interviews` | List | admissions.read | Query: date_from, date_to, interviewer_id, status, page, page_size | InterviewListResponse |
| GET | `/admissions/interviews/{id}` | Get detail | admissions.read | - | InterviewResponse |
| PATCH | `/admissions/interviews/{id}` | Reschedule | admissions.update | InterviewUpdate | InterviewResponse |
| POST | `/admissions/interviews/{id}/feedback` | Record result | admissions.review | InterviewFeedback | InterviewResponse |
| DELETE | `/admissions/interviews/{id}` | Cancel | admissions.update | - | InterviewResponse |
| POST | `/admissions/applications/{id}/screening` | Add item | admissions.update | ScreeningItemCreate | ScreeningItemResponse (201) |
| POST | `/admissions/applications/{id}/screening/bulk` | Bulk add | admissions.update | ScreeningItemBulkCreate | list[ScreeningItemResponse] |
| PATCH | `/admissions/screening/{id}/complete` | Complete item | admissions.update | ScreeningItemComplete | ScreeningItemResponse |
| GET | `/admissions/applications/{id}/screening` | Get progress | admissions.read | - | ScreeningProgressResponse |

### 5.3 Update `backend/app/api/v1/endpoints/admissions/__init__.py`

Add to the router registration:

```python
from .inquiries import router as inquiries_router
from .interviews import router as interviews_router

# In the router.include_router() section:
router.include_router(inquiries_router, tags=["Inquiries"])
router.include_router(interviews_router, tags=["Interviews"])
```

---

## 6. Migration

### File: `backend/alembic/versions/20260401_0200_inquiry_and_interview.py`

```python
"""Inquiry/Lead Management and Interview/Screening tables.

Revision ID: 20260401_0200
Revises: <current_head>
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260401_0200"
down_revision = "<CURRENT_HEAD>"  # Replace with actual current head
branch_labels = None
depends_on = None

# All new tables for batch RLS setup
NEW_TABLES = [
    "inquiries",
    "inquiry_communications",
    "inquiry_follow_ups",
    "interviews",
    "screening_checklists",
]


def upgrade() -> None:
    # Status/type columns use VARCHAR(20), not PG enums, for migration flexibility.

    # ========== PHASE 1: Create Tables ==========

    op.create_table(
        "inquiries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("target_class_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("guardian_name", sa.String(200), nullable=False),
        sa.Column("guardian_phone", sa.String(20), nullable=False),
        sa.Column("guardian_email", sa.String(255), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("referred_by", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("converted_application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_class_id"], ["classes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["converted_application_id"], ["applications.id"], ondelete="SET NULL"),
    )

    # inquiry_communications (NO deleted_at — append-only audit log)
    op.create_table(
        "inquiry_communications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sent_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sent_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "inquiry_follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"], ondelete="CASCADE"),
        # RESTRICT forces reassignment before user deletion
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        # SET NULL preserves interview history if interviewer is deleted
        sa.Column("interviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("scheduled_time", sa.Time, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("venue", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("feedback", sa.Text, nullable=True),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("scoring_criteria", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("duration_minutes >= 10 AND duration_minutes <= 180", name="ck_interviews_duration"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interviewer_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "screening_checklists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("item_category", sa.String(100), nullable=False),
        sa.Column("is_completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ========== PHASE 3: Column Additions ==========

    op.add_column("applications", sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_applications_inquiry", "applications", "inquiries", ["inquiry_id"], ["id"], ondelete="SET NULL")

    op.add_column("admission_decisions", sa.Column("interview_score", sa.Numeric(6, 2), nullable=True))
    op.add_column("admission_decisions", sa.Column("screening_score", sa.Numeric(6, 2), nullable=True))

    op.add_column("entrance_exam_results", sa.Column("subject_name", sa.String(100), nullable=True))
    op.add_column("entrance_exam_results", sa.Column("weight", sa.Numeric(4, 2), nullable=True, server_default="1.0"))

    # ========== PHASE 4: RLS ==========

    for table_name in NEW_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """)

    # ========== PHASE 5: Grants ==========

    for table_name in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")

    # ========== PHASE 6: Indexes ==========

    op.create_index("ix_inquiries_tenant_status", "inquiries", ["tenant_id", "school_id", "status"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_inquiries_tenant_source", "inquiries", ["tenant_id", "school_id", "source"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_inquiries_guardian_phone", "inquiries", ["tenant_id", "guardian_phone"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_inquiries_guardian_email", "inquiries", ["tenant_id", "guardian_email"], postgresql_where=sa.text("deleted_at IS NULL AND guardian_email IS NOT NULL"))
    op.create_index("ix_inquiries_assigned", "inquiries", ["tenant_id", "assigned_to"], postgresql_where=sa.text("deleted_at IS NULL AND assigned_to IS NOT NULL"))

    op.create_index("ix_inquiry_comms_inquiry", "inquiry_communications", ["tenant_id", "inquiry_id"])

    op.create_index("ix_followups_pending", "inquiry_follow_ups", ["tenant_id", "assigned_to", "due_date"], postgresql_where=sa.text("completed_at IS NULL AND deleted_at IS NULL"))
    op.create_index("ix_followups_inquiry", "inquiry_follow_ups", ["tenant_id", "inquiry_id"], postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_index("uq_interviews_application", "interviews", ["tenant_id", "application_id"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_interviews_scheduled", "interviews", ["tenant_id", "school_id", "scheduled_date"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_interviews_interviewer", "interviews", ["tenant_id", "interviewer_id", "scheduled_date"], postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_index("ix_screening_application", "screening_checklists", ["tenant_id", "application_id"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("uq_screening_tenant_app_item", "screening_checklists", ["tenant_id", "application_id", "item_name"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_index("ix_applications_inquiry", "applications", ["tenant_id", "inquiry_id"], postgresql_where=sa.text("inquiry_id IS NOT NULL AND deleted_at IS NULL"))


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_applications_inquiry", table_name="applications")
    op.drop_index("uq_screening_tenant_app_item", table_name="screening_checklists")
    op.drop_index("ix_screening_application", table_name="screening_checklists")
    op.drop_index("ix_interviews_interviewer", table_name="interviews")
    op.drop_index("ix_interviews_scheduled", table_name="interviews")
    op.drop_index("uq_interviews_application", table_name="interviews")
    op.drop_index("ix_followups_inquiry", table_name="inquiry_follow_ups")
    op.drop_index("ix_followups_pending", table_name="inquiry_follow_ups")
    op.drop_index("ix_inquiry_comms_inquiry", table_name="inquiry_communications")
    op.drop_index("ix_inquiries_assigned", table_name="inquiries")
    op.drop_index("ix_inquiries_guardian_email", table_name="inquiries")
    op.drop_index("ix_inquiries_guardian_phone", table_name="inquiries")
    op.drop_index("ix_inquiries_tenant_source", table_name="inquiries")
    op.drop_index("ix_inquiries_tenant_status", table_name="inquiries")

    # Drop added columns (reverse order)
    op.drop_column("entrance_exam_results", "weight")
    op.drop_column("entrance_exam_results", "subject_name")
    op.drop_column("admission_decisions", "screening_score")
    op.drop_column("admission_decisions", "interview_score")
    op.drop_constraint("fk_applications_inquiry", "applications", type_="foreignkey")
    op.drop_column("applications", "inquiry_id")

    # Drop tables (child first)
    op.drop_table("screening_checklists")
    op.drop_table("interviews")
    op.drop_table("inquiry_follow_ups")
    op.drop_table("inquiry_communications")
    op.drop_table("inquiries")

    # No PG enum types to drop — columns use VARCHAR(20)
```

---

## 7. Frontend

### 7.1 Types: `frontend/types/inquiry.type.ts`

Define TypeScript types matching the Pydantic schemas — InquirySource, InquiryStatus, InquiryResponse, InquiryListResponse, InquiryCreate, CommunicationCreate, CommunicationResponse, FollowUpCreate, FollowUpResponse, BulkInquiryImport, BulkImportResponse, DuplicateCheckResponse, InquiryStatsResponse.

### 7.2 Types: `frontend/types/interview.type.ts`

InterviewStatus, InterviewCreate, InterviewUpdate, InterviewFeedback, InterviewResponse, InterviewListResponse, ScreeningItemCreate, ScreeningItemResponse, ScreeningProgressResponse.

### 7.3 Server Actions: `frontend/actions/inquiries.action.ts`

Follow the existing pattern in `admissions.action.ts`:
- `createInquiry(data)`, `getInquiries(params)`, `getInquiry(id)`, `updateInquiry(id, data)`, `updateInquiryStatus(id, status, notes)`, `assignInquiry(id, userId)`, `convertInquiry(id, data)`, `deleteInquiry(id)`, `addCommunication(id, data)`, `getCommunications(id)`, `createFollowUp(id, data)`, `completeFollowUp(id, notes)`, `getPendingFollowUps(params)`, `bulkImportInquiries(data)`, `checkDuplicate(params)`, `getInquiryStats()`

### 7.4 Server Actions: `frontend/actions/interviews.action.ts`

`scheduleInterview(data)`, `getInterviews(params)`, `getInterview(id)`, `updateInterview(id, data)`, `recordInterviewFeedback(id, data)`, `cancelInterview(id)`, `addScreeningItem(applicationId, data)`, `bulkAddScreeningItems(applicationId, data)`, `completeScreeningItem(itemId, notes)`, `getScreeningProgress(applicationId)`

### 7.5 Pages

**`/admissions/inquiries/page.tsx`** — Inquiry list page with:
- Stats cards at top (total, by status, conversion rate, overdue tasks)
- Data table with columns: Name, Guardian, Phone, Source, Status, Assigned To, Created
- Filters: status dropdown, source dropdown, search box, assigned_to
- Row actions: View, Assign, Change Status, Convert to Application
- Bulk import button (opens CSV upload dialog)

**`/admissions/inquiries/[id]/page.tsx`** — Inquiry detail page with:
- Header: student name, status badge, source badge
- Info card: all student + guardian details
- Tabs:
  - Communications: timeline of all logged communications with "Add Entry" button
  - Follow-ups: task list with due dates, priority badges, complete button
  - Screening: checklist items with progress bar (shown if application linked)
  - Interview: interview details with feedback form (shown if application linked)
- Actions sidebar: Change Status, Assign, Convert to Application, Delete

### 7.6 Components

| Component | Props | Description |
|-----------|-------|-------------|
| `inquiry-form.tsx` | onSubmit, defaultValues | React Hook Form + Zod for create/edit |
| `inquiry-status-badge.tsx` | status | Color-coded badge (new=blue, contacted=yellow, interested=green, applied=purple, enrolled=emerald, lost=gray) |
| `inquiry-table.tsx` | inquiries, onAction | TanStack Table with sorting, filtering, row selection |
| `communication-log.tsx` | communications, onAdd | Timeline view with channel icons + "Add" form |
| `follow-up-list.tsx` | followUps, onComplete | Task list with overdue highlighting |
| `bulk-import-dialog.tsx` | onImport | File upload + preview table + confirm |
| `duplicate-warning.tsx` | matches | Alert banner with matching inquiry details |
| `interview-scheduler.tsx` | onSchedule, interviewers | Date/time/venue form with interviewer dropdown |
| `interview-feedback-form.tsx` | onSubmit, criteria | Dynamic scoring criteria form |
| `screening-checklist.tsx` | items, onComplete | Checklist with progress bar and category groups |

### 7.7 Sidebar Update

In `frontend/components/dashboard/app-sidebar.tsx`, add to the admissions navigation group:

```typescript
{ title: "Inquiries", url: "/admissions/inquiries", icon: UserPlus },
```

Position it as the first item in the admissions group (before Applications), since inquiries are the start of the funnel.

---

## 8. Tests

### 8.1 `backend/tests/test_inquiries.py` (~18 tests)

Follow the two-engine pattern from `test_admission_applications.py`:

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestInquiries:
    # CRUD
    async def test_create_inquiry(self, app_session, prereqs)
    async def test_create_inquiry_invalid_source(self, app_session, prereqs)
    async def test_get_inquiry(self, app_session, prereqs)
    async def test_get_inquiry_not_found(self, app_session, prereqs)
    async def test_list_inquiries_with_filters(self, app_session, prereqs)
    async def test_list_inquiries_search(self, app_session, prereqs)
    async def test_update_inquiry(self, app_session, prereqs)
    async def test_delete_inquiry(self, app_session, prereqs)

    # Status transitions
    async def test_status_transition_valid(self, app_session, prereqs)
    async def test_status_transition_invalid(self, app_session, prereqs)
    async def test_status_cannot_change_from_enrolled(self, app_session, prereqs)

    # Assignment
    async def test_assign_inquiry(self, app_session, prereqs)

    # Conversion
    async def test_convert_to_application(self, app_session, prereqs)
    async def test_convert_already_converted(self, app_session, prereqs)
    async def test_convert_copies_guardian(self, app_session, prereqs)

    # Communications
    async def test_add_communication(self, app_session, prereqs)
    async def test_list_communications_chronological(self, app_session, prereqs)

    # Follow-ups
    async def test_create_follow_up(self, app_session, prereqs)
    async def test_complete_follow_up(self, app_session, prereqs)
    async def test_list_pending_follow_ups(self, app_session, prereqs)
    async def test_list_overdue_follow_ups(self, app_session, prereqs)
```

### 8.2 `backend/tests/test_inquiry_bulk_import.py` (~8 tests)

```python
class TestBulkImport:
    async def test_bulk_import_success(self, app_session, prereqs)
    async def test_bulk_import_deduplicates_by_phone(self, app_session, prereqs)
    async def test_bulk_import_max_200_rows(self, app_session, prereqs)
    async def test_bulk_import_with_errors(self, app_session, prereqs)
    async def test_duplicate_check_by_phone(self, app_session, prereqs)
    async def test_duplicate_check_by_email(self, app_session, prereqs)
    async def test_duplicate_check_no_match(self, app_session, prereqs)
    async def test_inquiry_stats(self, app_session, prereqs)
```

### 8.3 `backend/tests/test_interviews.py` (~14 tests)

```python
class TestInterviews:
    async def test_schedule_interview(self, app_session, prereqs)
    async def test_schedule_prevents_duplicate(self, app_session, prereqs)
    async def test_schedule_checks_interviewer_overlap(self, app_session, prereqs)
    async def test_schedule_rejects_terminal_application(self, app_session, prereqs)
    async def test_update_interview(self, app_session, prereqs)
    async def test_record_feedback_completed(self, app_session, prereqs)
    async def test_record_feedback_no_show(self, app_session, prereqs)
    async def test_record_feedback_auto_calculates_score(self, app_session, prereqs)
    async def test_cancel_interview(self, app_session, prereqs)
    async def test_list_interviews_by_date(self, app_session, prereqs)

    # Screening
    async def test_create_screening_item(self, app_session, prereqs)
    async def test_bulk_create_screening_items(self, app_session, prereqs)
    async def test_complete_screening_item(self, app_session, prereqs)
    async def test_screening_progress(self, app_session, prereqs)
```

### 8.4 `backend/tests/test_inquiries_rls.py` (~6 tests)

```python
@pytest.mark.rls
@pytest.mark.asyncio
@pytest.mark.xdist_group("rls_serial")
class TestInquiriesRLS:
    async def test_inquiry_tenant_isolation(self, admin_session, app_session)
    async def test_communication_tenant_isolation(self, admin_session, app_session)
    async def test_follow_up_tenant_isolation(self, admin_session, app_session)
    async def test_interview_tenant_isolation(self, admin_session, app_session)
    async def test_screening_tenant_isolation(self, admin_session, app_session)
    async def test_cross_tenant_inquiry_invisible(self, admin_session, app_session)
```

### 8.5 Update `backend/tests/conftest.py`

Add to TENANT_SCOPED_TABLES:
```python
# Inquiry & Interview (Phase 1)
"inquiries",
"inquiry_communications",
"inquiry_follow_ups",
"interviews",
"screening_checklists",
```

### 8.5 Operational Updates

**Update `backend/scripts/verify_rls.py`:** Add all 5 new tables to the verification list.

**Update `backend/app/tasks/tenant_cleanup.py`:** Add the 5 new tables to `_TABLES_DELETION_ORDER` in correct dependency order (child tables first):
1. `inquiry_follow_ups`
2. `inquiry_communications`
3. `screening_checklists`
4. `interviews`
5. `inquiries`

These must be inserted BEFORE `applications` in the deletion order since `inquiries.converted_application_id` references `applications`.

---

## 9. Task Checklist

Developers should complete these tasks in order:

- [ ] **P1-01**: Add enums to `backend/app/models/admissions/enums.py` (InquirySource, InquiryStatus, InterviewStatus, INQUIRY_VALID_TRANSITIONS)
- [ ] **P1-02**: Create `backend/app/models/admissions/inquiry.py` (Inquiry, InquiryCommunication, InquiryFollowUp)
- [ ] **P1-03**: Create `backend/app/models/admissions/interview.py` (Interview, ScreeningChecklist)
- [ ] **P1-04**: Update `backend/app/models/admissions/__init__.py` (re-exports)
- [ ] **P1-05**: Update `backend/app/db/base.py` (import new models)
- [ ] **P1-06**: Add inquiry_id column to Application model
- [ ] **P1-07**: Add interview_score, screening_score to AdmissionDecision model
- [ ] **P1-08**: Add subject_name, weight to EntranceExamResult model
- [ ] **P1-09**: Create migration `20260401_0200_inquiry_and_interview.py`
- [ ] **P1-10**: Create `backend/app/schemas/inquiry.py`
- [ ] **P1-11**: Create `backend/app/schemas/interview.py`
- [ ] **P1-12**: Create `backend/app/services/admissions/inquiry_service.py`
- [ ] **P1-13**: Create `backend/app/services/admissions/interview_service.py`
- [ ] **P1-14**: Update `backend/app/services/admissions/__init__.py` (re-exports)
- [ ] **P1-15**: Create `backend/app/api/v1/endpoints/admissions/inquiries.py`
- [ ] **P1-16**: Create `backend/app/api/v1/endpoints/admissions/interviews.py`
- [ ] **P1-17**: Update `backend/app/api/v1/endpoints/admissions/__init__.py` (register routers)
- [ ] **P1-18**: Update `backend/tests/conftest.py` (add 5 tables to TENANT_SCOPED_TABLES)
- [ ] **P1-19**: Write `backend/tests/test_inquiries.py`
- [ ] **P1-20**: Write `backend/tests/test_inquiry_bulk_import.py`
- [ ] **P1-21**: Write `backend/tests/test_interviews.py`
- [ ] **P1-22**: Write `backend/tests/test_inquiries_rls.py`
- [ ] **P1-23**: Create `frontend/types/inquiry.type.ts`
- [ ] **P1-24**: Create `frontend/types/interview.type.ts`
- [ ] **P1-25**: Create `frontend/actions/inquiries.action.ts`
- [ ] **P1-26**: Create `frontend/actions/interviews.action.ts`
- [ ] **P1-27**: Create inquiry page components (form, table, status badge, communication log, follow-up list, bulk import dialog, duplicate warning)
- [ ] **P1-28**: Create interview page components (scheduler, feedback form, screening checklist)
- [ ] **P1-29**: Create `/admissions/inquiries/page.tsx` (list page)
- [ ] **P1-30**: Create `/admissions/inquiries/[id]/page.tsx` (detail page)
- [ ] **P1-31**: Update sidebar navigation with Inquiries item
- [ ] **P1-32**: Run all tests, verify RLS, verify migration up/down
- [ ] **P1-33**: Update `backend/scripts/verify_rls.py` with 5 new tables
- [ ] **P1-34**: Update `backend/app/tasks/tenant_cleanup.py` with 5 new tables in deletion order

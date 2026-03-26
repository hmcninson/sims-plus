# Phase 4: Capacity Planning, Re-enrollment, School Tours & Analytics

**Covers:** GAP 7 (EM-082, EM-088, EM-089), GAP 8 (EM-100 to EM-107), GAP 9 (EM-130 to EM-137), GAP 2 (EM-010 to EM-016)
**Estimated Effort:** 2 weeks (1 sprint)
**New Tables:** 3 (enrollment_targets, school_events, event_registrations)
**Modified Tables:** 1 (return_intents)
**New Endpoints:** 19
**New Tests:** ~44

---

## 1. Database Schema

### 1.1 New Enums

Add to `backend/app/models/admissions/enums.py`:

```python
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
```

### 1.2 New Tables

#### Table 1: `enrollment_targets`

Per-class enrollment targets per academic year, used for capacity planning dashboards.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `school_id` | UUID | No | | FK schools.id CASCADE | |
| `academic_year_id` | UUID | No | | FK academic_years.id CASCADE | |
| `class_id` | UUID | No | | FK classes.id CASCADE | |
| `target_count` | INTEGER | No | | CHECK >= 0 | Total enrollment target |
| `boarding_target` | INTEGER | Yes | | CHECK >= 0 | Boarding places target |
| `day_target` | INTEGER | Yes | | CHECK >= 0 | Day student target |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Unique constraint:** `UNIQUE(tenant_id, academic_year_id, class_id) WHERE deleted_at IS NULL` -- one active target per class per year.

**Indexes:**
```sql
CREATE UNIQUE INDEX uq_enrollment_targets_class_year ON enrollment_targets(tenant_id, academic_year_id, class_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_enrollment_targets_school_year ON enrollment_targets(tenant_id, school_id, academic_year_id) WHERE deleted_at IS NULL;
```

**RLS Policy:**
```sql
ALTER TABLE enrollment_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollment_targets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON enrollment_targets
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON enrollment_targets TO sims_app_user;
```

#### Table 2: `school_events`

Tours, open days, and orientation events for prospective families.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `school_id` | UUID | No | | FK schools.id CASCADE | |
| `event_type` | VARCHAR(20) | No | | | EventType enum value |
| `name` | VARCHAR(255) | No | | | Event display name |
| `description` | TEXT | Yes | | | |
| `event_date` | DATE | No | | | |
| `start_time` | TIME | Yes | | | |
| `end_time` | TIME | Yes | | | |
| `venue` | VARCHAR(255) | Yes | | | |
| `capacity` | INTEGER | Yes | | CHECK >= 1 | Max registrants (null = unlimited) |
| `registered_count` | INTEGER | No | `0` | CHECK >= 0 | Maintained via service-level increment/decrement |
| `status` | VARCHAR(20) | No | `'upcoming'` | | EventStatus enum value |
| `guide_id` | UUID | Yes | | FK users.id SET NULL | Tour guide / event lead |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Indexes:**
```sql
CREATE INDEX ix_school_events_tenant_date ON school_events(tenant_id, school_id, event_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_school_events_tenant_type ON school_events(tenant_id, school_id, event_type) WHERE deleted_at IS NULL;
CREATE INDEX ix_school_events_guide ON school_events(tenant_id, guide_id) WHERE deleted_at IS NULL AND guide_id IS NOT NULL;
```

**RLS:** Same tenant_isolation pattern.

#### Table 3: `event_registrations`

Registrations for school events. **No SoftDeleteMixin** -- cancelled registrations are hard-deleted so that `registered_count` stays accurate without soft-delete bookkeeping.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin only |
| `event_id` | UUID | No | | FK school_events.id CASCADE | |
| `registrant_name` | VARCHAR(200) | No | | | Parent/guardian name |
| `registrant_phone` | VARCHAR(20) | No | | | |
| `registrant_email` | VARCHAR(255) | Yes | | | |
| `student_name` | VARCHAR(200) | Yes | | | Prospective student name |
| `attended` | BOOLEAN | No | `false` | | Marked by staff post-event |
| `registered_at` | TIMESTAMPTZ | No | now() | | |
| `notes` | TEXT | Yes | | | |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |

**Note:** No `deleted_at` column. Cancellations are hard-deletes. The service decrements `school_events.registered_count` atomically.

**Indexes:**
```sql
CREATE INDEX ix_event_registrations_event ON event_registrations(tenant_id, event_id);
CREATE INDEX ix_event_registrations_phone ON event_registrations(tenant_id, registrant_phone);
```

**RLS:** Same tenant_isolation pattern.

### 1.3 Column Additions to Existing Tables

#### `return_intents` table -- re-enrollment confirmation fields

```sql
ALTER TABLE return_intents ADD COLUMN re_enrollment_confirmed BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE return_intents ADD COLUMN re_enrollment_confirmed_at TIMESTAMPTZ;
ALTER TABLE return_intents ADD COLUMN outstanding_fees_checked BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE return_intents ADD COLUMN outstanding_fee_amount NUMERIC(10,2);
```

**Model change:** Add to `ReturnIntent` class in `backend/app/models/admissions/return_intent.py`:
```python
import sqlalchemy as sa
from sqlalchemy import Boolean, Numeric

re_enrollment_confirmed: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default=sa.text("false"),
    comment="True when admin confirms this returning student is re-enrolled",
)
re_enrollment_confirmed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True,
)
outstanding_fees_checked: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False, server_default=sa.text("false"),
    comment="True when outstanding fees were checked during confirmation",
)
outstanding_fee_amount: Mapped[Decimal | None] = mapped_column(
    Numeric(10, 2), nullable=True,
    comment="Snapshot of outstanding fee balance at confirmation time",
)
```

---

## 2. Models

### 2.1 New File: `backend/app/models/admissions/capacity.py`

```python
"""
SIMS Plus - Enrollment Target Models

Per-class enrollment targets for capacity planning dashboards.
Allows schools to set target enrollment counts per class per academic year,
with optional boarding/day breakdowns.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class
    from app.models.school import School


class EnrollmentTarget(Base, TenantMixin, SoftDeleteMixin):
    """
    Per-class enrollment target for a given academic year.

    Used by the capacity planning dashboard to compare targets against
    actual enrollment counts, application pipeline, and class capacity.
    """

    __tablename__ = "enrollment_targets"

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
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_count: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Total enrollment target for this class/year",
    )
    boarding_target: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Target number of boarding students (subset of target_count)",
    )
    day_target: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Target number of day students (subset of target_count)",
    )

    # Relationships (all lazy="raise")
    school: Mapped["School"] = sa_relationship("School", lazy="raise")
    academic_year: Mapped["AcademicYear"] = sa_relationship("AcademicYear", lazy="raise")
    target_class: Mapped["Class"] = sa_relationship(
        "Class", foreign_keys=[class_id], lazy="raise"
    )
```

### 2.2 New File: `backend/app/models/admissions/event.py`

```python
"""
SIMS Plus - School Event Models

School tours, open days, and orientation events for prospective families.
EventRegistration uses hard deletes (no SoftDeleteMixin) because
cancellations must decrement registered_count atomically.
"""

import uuid
from datetime import date, datetime, time, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.tenant import User


class SchoolEvent(Base, TenantMixin, SoftDeleteMixin):
    """
    School event (tour, open day, orientation) for prospective families.

    The registered_count is maintained by the service layer via
    atomic increment/decrement to avoid race conditions.
    """

    __tablename__ = "school_events"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="EventType enum value: open_day, tour, orientation",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    capacity: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Max registrants. NULL = unlimited",
    )
    registered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Current registration count, maintained atomically by service",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="upcoming",
        comment="EventStatus: upcoming, completed, cancelled",
    )
    guide_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Tour guide or event lead",
    )

    # Relationships
    school: Mapped["School"] = sa_relationship("School", lazy="raise")
    guide: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[guide_id], lazy="raise"
    )
    registrations: Mapped[list["EventRegistration"]] = sa_relationship(
        "EventRegistration", back_populates="event", lazy="raise",
        cascade="all, delete-orphan",
    )


class EventRegistration(Base, TenantMixin):
    """
    Registration for a school event.

    NO SoftDeleteMixin -- cancellations are hard-deleted so that
    SchoolEvent.registered_count stays accurate without needing
    to reconcile soft-delete states.
    """

    __tablename__ = "event_registrations"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "event_id", "registrant_phone",
            name="uq_event_reg_phone",
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    registrant_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Parent/guardian name",
    )
    registrant_phone: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    registrant_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    student_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="Prospective student name",
    )
    attended: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Marked by staff post-event",
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    event: Mapped["SchoolEvent"] = sa_relationship(
        "SchoolEvent", back_populates="registrations", lazy="raise"
    )
```

### 2.3 Update `backend/app/models/admissions/return_intent.py`

Add the re-enrollment confirmation columns to the `ReturnIntent` class (see section 1.3 for the column definitions).

Add these imports at the top of the file:
```python
from decimal import Decimal
from sqlalchemy import Boolean, Numeric
```

### 2.4 Update `backend/app/models/admissions/__init__.py`

Add the following imports and `__all__` entries:

```python
from app.models.admissions.enums import (
    EventType,
    EventStatus,
    # ... existing enum exports
)
from app.models.admissions.capacity import EnrollmentTarget
from app.models.admissions.event import SchoolEvent, EventRegistration
```

Add to `__all__`:
```python
# Enums
"EventType",
"EventStatus",
# Capacity
"EnrollmentTarget",
# Events
"SchoolEvent",
"EventRegistration",
```

### 2.5 Update `backend/app/db/base.py`

Ensure the new models are imported so Alembic discovers them:

```python
from app.models.admissions.capacity import EnrollmentTarget  # noqa
from app.models.admissions.event import SchoolEvent, EventRegistration  # noqa
```

---

## 3. Schemas

### 3.1 New File: `backend/app/schemas/capacity.py`

```python
"""
SIMS Plus - Capacity Planning Schemas
Pydantic schemas for enrollment target and capacity dashboard endpoints.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Enrollment Target Schemas ---

class EnrollmentTargetCreate(BaseSchema):
    """Set enrollment target for a class/year (upsert semantics)."""
    academic_year_id: UUID
    class_id: UUID
    target_count: int = Field(..., ge=0)
    boarding_target: int | None = Field(None, ge=0)
    day_target: int | None = Field(None, ge=0)


class EnrollmentTargetResponse(BaseSchema):
    """Full enrollment target response."""
    id: UUID
    school_id: UUID
    academic_year_id: UUID
    class_id: UUID
    class_name: str | None = None
    target_count: int
    boarding_target: int | None
    day_target: int | None
    created_at: datetime
    updated_at: datetime


class EnrollmentTargetListResponse(BaseSchema):
    """List of targets for a year."""
    items: list[EnrollmentTargetResponse]
    academic_year_id: UUID


# --- Capacity Dashboard Schemas ---

class ClassCapacityRow(BaseSchema):
    """Per-class capacity breakdown in the dashboard."""
    class_id: UUID
    class_name: str
    capacity: int | None              # From Class model (physical capacity)
    target: int | None                # From EnrollmentTarget
    boarding_target: int | None
    day_target: int | None
    current_enrolled: int             # Count of active students
    applications_in_pipeline: int     # Non-terminal applications
    utilization_pct: float            # current_enrolled / capacity * 100


class CapacityDashboardResponse(BaseSchema):
    """Full capacity dashboard for a school/year."""
    academic_year_id: UUID
    school_id: UUID
    total_capacity: int | None
    total_target: int | None
    total_enrolled: int
    total_pipeline: int
    classes: list[ClassCapacityRow]


# --- Capacity Check Schema ---

class CapacityCheckResponse(BaseSchema):
    """Quick capacity check for a single class."""
    class_id: UUID
    class_name: str | None = None
    capacity: int | None
    current_enrolled: int
    remaining: int | None             # None if capacity is unlimited
    is_full: bool
```

### 3.2 New File: `backend/app/schemas/event.py`

```python
"""
SIMS Plus - School Event Schemas
Pydantic schemas for school tours, open days, and orientation events.
"""

from datetime import date, datetime, time
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Enums for schema validation ---

class EventTypeEnum(str, Enum):
    OPEN_DAY = "open_day"
    TOUR = "tour"
    ORIENTATION = "orientation"


class EventStatusEnum(str, Enum):
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# --- Event Schemas ---

class EventCreate(BaseSchema):
    """Create a school event."""
    event_type: EventTypeEnum
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    event_date: date
    start_time: time | None = None
    end_time: time | None = None
    venue: str | None = Field(None, max_length=255)
    capacity: int | None = Field(None, ge=1)
    guide_id: UUID | None = None


class EventUpdate(BaseSchema):
    """Update event details. Only upcoming events can be updated."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    event_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    venue: str | None = Field(None, max_length=255)
    capacity: int | None = Field(None, ge=1)
    guide_id: UUID | None = None


class EventResponse(BaseSchema):
    """Full event detail response."""
    id: UUID
    school_id: UUID
    event_type: str
    name: str
    description: str | None
    event_date: date
    start_time: time | None
    end_time: time | None
    venue: str | None
    capacity: int | None
    registered_count: int
    status: str
    guide_id: UUID | None
    guide_name: str | None = None
    created_at: datetime
    updated_at: datetime


class EventListResponse(BaseSchema):
    """Paginated event list."""
    items: list[EventResponse]
    total: int
    page: int
    page_size: int
    pages: int


# --- Registration Schemas ---

class RegistrationCreate(BaseSchema):
    """Register for a school event."""
    registrant_name: str = Field(..., min_length=1, max_length=200)
    registrant_phone: str = Field(..., min_length=1, max_length=20)
    registrant_email: EmailStr | None = None
    student_name: str | None = Field(None, max_length=200)
    notes: str | None = None


class RegistrationResponse(BaseSchema):
    """Registration detail."""
    id: UUID
    event_id: UUID
    registrant_name: str
    registrant_phone: str
    registrant_email: str | None
    student_name: str | None
    attended: bool
    registered_at: datetime
    notes: str | None
    created_at: datetime


class AttendanceUpdate(BaseSchema):
    """Mark attendance for a registration."""
    attended: bool


# --- Event Stats ---

class EventStatsResponse(BaseSchema):
    """Statistics for a single event."""
    event_id: UUID
    event_name: str
    total_registered: int
    total_attended: int
    attendance_rate: float
    capacity: int | None
    fill_rate: float | None           # registered / capacity * 100
```

### 3.3 New File: `backend/app/schemas/enrollment_analytics.py`

```python
"""
SIMS Plus - Admissions Analytics Schemas
Pydantic schemas for enrollment funnel, trends, and analytics endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Funnel ---

class FunnelStageResponse(BaseSchema):
    """Single stage in the admissions funnel."""
    stage: str
    count: int
    conversion_rate: float | None      # Percentage of previous stage


class FunnelResponse(BaseSchema):
    """Full admissions funnel from inquiry to enrollment."""
    school_id: UUID
    period_id: UUID | None
    stages: list[FunnelStageResponse]


# --- Trends ---

class YearClassCount(BaseSchema):
    """Enrollment count for a single class in a year."""
    class_id: UUID
    class_name: str
    count: int


class YearTrendRow(BaseSchema):
    """One academic year's enrollment data."""
    academic_year_id: UUID
    academic_year_name: str
    total_enrolled: int
    by_class: list[YearClassCount]


class TrendsResponse(BaseSchema):
    """Year-over-year enrollment trends."""
    school_id: UUID
    years: list[YearTrendRow]


# --- Lead Source Effectiveness ---

class SourceEffectivenessRow(BaseSchema):
    """Conversion metrics for a single lead source."""
    source: str
    inquiry_count: int
    application_count: int
    enrollment_count: int
    inquiry_to_application_rate: float
    inquiry_to_enrollment_rate: float


class SourceEffectivenessResponse(BaseSchema):
    school_id: UUID
    period_id: UUID | None
    sources: list[SourceEffectivenessRow]


# --- Re-enrollment ---

class ReEnrollmentYearRow(BaseSchema):
    """Re-enrollment rate for one academic year."""
    academic_year_id: UUID
    academic_year_name: str
    total_students: int
    returning_count: int
    re_enrollment_rate: float


class ReEnrollmentResponse(BaseSchema):
    school_id: UUID
    years: list[ReEnrollmentYearRow]


# --- Attrition ---

class AttritionReasonRow(BaseSchema):
    """Count of students lost for a given reason."""
    reason: str
    count: int


class AttritionResponse(BaseSchema):
    school_id: UUID
    academic_year_id: UUID | None
    withdrawn_count: int
    not_returning_count: int
    total_attrition: int
    withdrawal_reasons: list[AttritionReasonRow]
    not_returning_reasons: list[AttritionReasonRow]


# --- Enrollment vs Capacity ---

class EnrollmentVsCapacityRow(BaseSchema):
    """Per-class comparison of target, actual, and capacity."""
    class_id: UUID
    class_name: str
    target: int | None
    actual_enrolled: int
    capacity: int | None
    variance: int | None              # actual - target (positive = over target)
    fill_pct: float | None            # actual / capacity * 100


class EnrollmentVsCapacityResponse(BaseSchema):
    school_id: UUID
    academic_year_id: UUID
    classes: list[EnrollmentVsCapacityRow]
    total_target: int | None
    total_enrolled: int
    total_capacity: int | None


# --- Re-enrollment Confirmation Summary ---

class ReEnrollmentSummaryResponse(BaseSchema):
    """Summary for a return intent campaign's re-enrollment confirmations."""
    campaign_id: UUID
    total_intents: int
    confirmed_count: int
    pending_count: int
    not_returning_count: int
    undecided_count: int
    total_outstanding_fees: float
    by_class: list[dict]              # [{class_name, confirmed, pending, not_returning}]
```

---

## 4. Services

### 4.1 New File: `backend/app/services/admissions/capacity_service.py`

```python
"""
SIMS Plus - Capacity Planning Service

Manages enrollment targets and provides capacity dashboard data.
Dashboard queries use SQL aggregation (not Python-side loops) for efficiency.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    AdmissionApplicationStatus,
    Application,
    EnrollmentTarget,
    TERMINAL_STATUSES,
)
from app.models.academic import AcademicYear, Class
from app.models.student import Student

logger = structlog.get_logger(__name__)


class CapacityServiceError(Exception):
    def __init__(self, message: str, code: str = "CAPACITY_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class CapacityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_target(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        academic_year_id: uuid.UUID,
        class_id: uuid.UUID,
        target_count: int,
        boarding_target: int | None = None,
        day_target: int | None = None,
    ) -> EnrollmentTarget:
        """
        Upsert enrollment target for a class/year.

        If a target already exists for this class/year, updates it.
        Otherwise, creates a new one.
        """
        # Validate academic year exists and belongs to tenant
        year_result = await self.db.execute(
            select(AcademicYear).filter(
                AcademicYear.id == academic_year_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not year_result.scalar_one_or_none():
            raise CapacityServiceError("Academic year not found", "YEAR_NOT_FOUND")

        # Validate class exists and belongs to tenant
        class_result = await self.db.execute(
            select(Class).filter(
                Class.id == class_id,
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
            )
        )
        if not class_result.scalar_one_or_none():
            raise CapacityServiceError("Class not found", "CLASS_NOT_FOUND")

        # Check for existing target (upsert)
        existing_result = await self.db.execute(
            select(EnrollmentTarget).filter(
                EnrollmentTarget.tenant_id == tenant_id,
                EnrollmentTarget.academic_year_id == academic_year_id,
                EnrollmentTarget.class_id == class_id,
                EnrollmentTarget.deleted_at.is_(None),
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.target_count = target_count
            existing.boarding_target = boarding_target
            existing.day_target = day_target
            await self.db.flush()
            await self.db.refresh(existing)
            logger.info(
                "enrollment_target_updated",
                target_id=str(existing.id),
                class_id=str(class_id),
                target_count=target_count,
            )
            return existing

        target = EnrollmentTarget(
            tenant_id=tenant_id,
            school_id=school_id,
            academic_year_id=academic_year_id,
            class_id=class_id,
            target_count=target_count,
            boarding_target=boarding_target,
            day_target=day_target,
        )
        self.db.add(target)
        await self.db.flush()
        await self.db.refresh(target)

        logger.info(
            "enrollment_target_created",
            target_id=str(target.id),
            class_id=str(class_id),
            target_count=target_count,
        )
        return target

    async def get_targets(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> list[EnrollmentTarget]:
        """Get all enrollment targets for a school/year."""
        result = await self.db.execute(
            select(EnrollmentTarget).filter(
                EnrollmentTarget.tenant_id == tenant_id,
                EnrollmentTarget.school_id == school_id,
                EnrollmentTarget.academic_year_id == academic_year_id,
                EnrollmentTarget.deleted_at.is_(None),
            ).order_by(EnrollmentTarget.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_dashboard(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> dict:
        """
        Build capacity dashboard with a single efficient query.

        For each class: joins classes, enrollment_targets, students (count),
        and applications (pipeline count) using SQL aggregation.
        """
        # Validate academic year
        year_result = await self.db.execute(
            select(AcademicYear).filter(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not year_result.scalar_one_or_none():
            raise CapacityServiceError("Academic year not found", "YEAR_NOT_FOUND")

        # Subquery: count of active students per class
        student_counts = (
            select(
                Student.class_id,
                func.count(Student.id).label("enrolled_count"),
            )
            .filter(
                Student.tenant_id == tenant_id,
                Student.school_id == school_id,
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
            .group_by(Student.class_id)
            .subquery("student_counts")
        )

        # Subquery: count of non-terminal applications per target_class
        pipeline_statuses = [
            s.value for s in AdmissionApplicationStatus
            if s not in TERMINAL_STATUSES
        ]
        pipeline_counts = (
            select(
                Application.target_class_id,
                func.count(Application.id).label("pipeline_count"),
            )
            .filter(
                Application.tenant_id == tenant_id,
                Application.school_id == school_id,
                Application.status.in_(pipeline_statuses),
                Application.deleted_at.is_(None),
            )
            .group_by(Application.target_class_id)
            .subquery("pipeline_counts")
        )

        # Main query: classes LEFT JOIN targets, student counts, pipeline counts
        query = (
            select(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.capacity.label("class_capacity"),
                EnrollmentTarget.target_count,
                EnrollmentTarget.boarding_target,
                EnrollmentTarget.day_target,
                func.coalesce(student_counts.c.enrolled_count, 0).label("current_enrolled"),
                func.coalesce(pipeline_counts.c.pipeline_count, 0).label("applications_in_pipeline"),
            )
            .select_from(Class)
            .outerjoin(
                EnrollmentTarget,
                and_(
                    EnrollmentTarget.class_id == Class.id,
                    EnrollmentTarget.academic_year_id == academic_year_id,
                    EnrollmentTarget.tenant_id == tenant_id,
                    EnrollmentTarget.deleted_at.is_(None),
                ),
            )
            .outerjoin(student_counts, student_counts.c.class_id == Class.id)
            .outerjoin(pipeline_counts, pipeline_counts.c.target_class_id == Class.id)
            .filter(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
                Class.is_active.is_(True),
            )
            .order_by(Class.sequence.asc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        classes = []
        total_capacity = 0
        total_target = 0
        total_enrolled = 0
        total_pipeline = 0

        for row in rows:
            capacity = row.class_capacity
            enrolled = row.current_enrolled
            target = row.target_count

            # Calculate utilization as percentage of physical capacity
            utilization = 0.0
            if capacity and capacity > 0:
                utilization = round(enrolled / capacity * 100, 1)

            classes.append({
                "class_id": row.class_id,
                "class_name": row.class_name,
                "capacity": capacity,
                "target": target,
                "boarding_target": row.boarding_target,
                "day_target": row.day_target,
                "current_enrolled": enrolled,
                "applications_in_pipeline": row.applications_in_pipeline,
                "utilization_pct": utilization,
            })

            if capacity:
                total_capacity += capacity
            if target:
                total_target += target
            total_enrolled += enrolled
            total_pipeline += row.applications_in_pipeline

        return {
            "academic_year_id": academic_year_id,
            "school_id": school_id,
            "total_capacity": total_capacity or None,
            "total_target": total_target or None,
            "total_enrolled": total_enrolled,
            "total_pipeline": total_pipeline,
            "classes": classes,
        }

    async def check_capacity(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> dict:
        """
        Quick capacity check for a single class.

        Returns current enrollment vs physical capacity from the Class model.
        Used by application submission and enrollment endpoints to warn about full classes.
        """
        # Get class with capacity
        class_result = await self.db.execute(
            select(Class).filter(
                Class.id == class_id,
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
            )
        )
        cls = class_result.scalar_one_or_none()
        if not cls:
            raise CapacityServiceError("Class not found", "CLASS_NOT_FOUND")

        # Count active students in this class
        count_result = await self.db.execute(
            select(func.count(Student.id)).filter(
                Student.class_id == class_id,
                Student.tenant_id == tenant_id,
                Student.school_id == school_id,
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
        )
        current = count_result.scalar() or 0

        capacity = cls.capacity
        remaining = (capacity - current) if capacity is not None else None
        is_full = remaining is not None and remaining <= 0

        return {
            "class_id": class_id,
            "class_name": cls.name,
            "capacity": capacity,
            "current_enrolled": current,
            "remaining": remaining,
            "is_full": is_full,
        }
```

### 4.2 New File: `backend/app/services/admissions/event_service.py`

```python
"""
SIMS Plus - School Event Service

Manages school tours, open days, and orientation events.
EventRegistration uses hard deletes; registered_count is maintained atomically.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import EventStatus, EventType, SchoolEvent, EventRegistration
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger(__name__)


class EventServiceError(Exception):
    def __init__(self, message: str, code: str = "EVENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        event_type: str,
        name: str,
        description: str | None = None,
        event_date,
        start_time=None,
        end_time=None,
        venue: str | None = None,
        capacity: int | None = None,
        guide_id: uuid.UUID | None = None,
    ) -> SchoolEvent:
        """Create a new school event."""
        # Validate event_type
        if event_type not in [e.value for e in EventType]:
            raise EventServiceError(f"Invalid event type: {event_type}", "INVALID_TYPE")

        event = SchoolEvent(
            tenant_id=tenant_id,
            school_id=school_id,
            event_type=event_type,
            name=name,
            description=description,
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            capacity=capacity,
            registered_count=0,
            status=EventStatus.UPCOMING.value,
            guide_id=guide_id,
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)

        logger.info(
            "school_event_created",
            event_id=str(event.id),
            event_type=event_type,
            event_date=str(event_date),
        )
        return event

    # Fields that must never be overwritten via update kwargs
    _PROTECTED_FIELDS = {"id", "tenant_id", "school_id", "created_at", "updated_at", "deleted_at"}

    async def update_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        **kwargs,
    ) -> SchoolEvent:
        """Update event details. Only upcoming events can be modified."""
        event = await self._get_event(tenant_id, event_id)

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Only upcoming events can be updated",
                "NOT_UPCOMING",
            )

        for key, value in kwargs.items():
            # Skip protected fields to prevent accidental overwrites of immutable columns
            if key in self._PROTECTED_FIELDS:
                continue
            if value is not None and hasattr(event, key):
                setattr(event, key, value)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def cancel_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> SchoolEvent:
        """Cancel an upcoming event."""
        event = await self._get_event(tenant_id, event_id)

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Only upcoming events can be cancelled",
                "NOT_UPCOMING",
            )

        event.status = EventStatus.CANCELLED.value
        await self.db.flush()
        await self.db.refresh(event)

        logger.info("school_event_cancelled", event_id=str(event_id))
        return event

    async def complete_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> SchoolEvent:
        """Mark an upcoming event as completed."""
        event = await self._get_event(tenant_id, event_id)

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Only upcoming events can be marked as completed",
                "NOT_UPCOMING",
            )

        event.status = EventStatus.COMPLETED.value
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def list_events(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        event_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SchoolEvent], int]:
        """List events with optional filters and pagination."""
        query = (
            select(SchoolEvent).filter(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.school_id == school_id,
                SchoolEvent.deleted_at.is_(None),
            )
        )

        if event_type:
            query = query.filter(SchoolEvent.event_type == event_type)
        if status:
            query = query.filter(SchoolEvent.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(SchoolEvent.event_date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total

    async def register(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        *,
        registrant_name: str,
        registrant_phone: str,
        registrant_email: str | None = None,
        student_name: str | None = None,
        notes: str | None = None,
    ) -> EventRegistration:
        """
        Register a prospective family for an event.

        Checks capacity before registering. Uses with_for_update() on the
        event row to prevent race conditions when checking/incrementing count.
        """
        # Lock the event row to prevent race conditions on registered_count
        event_result = await self.db.execute(
            select(SchoolEvent)
            .filter(
                SchoolEvent.id == event_id,
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.deleted_at.is_(None),
            )
            .with_for_update()
        )
        event = event_result.scalar_one_or_none()
        if not event:
            raise EventServiceError("Event not found", "NOT_FOUND")

        if event.status != EventStatus.UPCOMING.value:
            raise EventServiceError(
                "Cannot register for a non-upcoming event",
                "NOT_UPCOMING",
            )

        # Check capacity
        if event.capacity is not None and event.registered_count >= event.capacity:
            raise EventServiceError(
                "Event is at full capacity",
                "EVENT_FULL",
            )

        registration = EventRegistration(
            tenant_id=tenant_id,
            event_id=event_id,
            registrant_name=registrant_name,
            registrant_phone=registrant_phone,
            registrant_email=registrant_email,
            student_name=student_name,
            notes=notes,
        )
        self.db.add(registration)

        # Atomically increment registered_count
        event.registered_count += 1

        await self.db.flush()
        await self.db.refresh(registration)

        logger.info(
            "event_registration_created",
            registration_id=str(registration.id),
            event_id=str(event_id),
        )
        return registration

    async def delete_registration(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        registration_id: uuid.UUID,
    ) -> None:
        """
        Hard-delete a registration and decrement the event's registered_count.

        Uses with_for_update() to prevent race conditions.
        IDOR check: registration must belong to the specified event.
        """
        # Lock event row for atomic decrement
        event_result = await self.db.execute(
            select(SchoolEvent)
            .filter(
                SchoolEvent.id == event_id,
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.deleted_at.is_(None),
            )
            .with_for_update()
        )
        event = event_result.scalar_one_or_none()
        if not event:
            raise EventServiceError("Event not found", "NOT_FOUND")

        # Get registration with IDOR check: must belong to this event
        reg_result = await self.db.execute(
            select(EventRegistration).filter(
                EventRegistration.id == registration_id,
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,  # IDOR prevention
            )
        )
        registration = reg_result.scalar_one_or_none()
        if not registration:
            raise EventServiceError("Registration not found", "REG_NOT_FOUND")

        await self.db.delete(registration)

        # Atomically decrement registered_count (floor at 0)
        if event.registered_count > 0:
            event.registered_count -= 1

        await self.db.flush()

        logger.info(
            "event_registration_deleted",
            registration_id=str(registration_id),
            event_id=str(event_id),
        )

    async def mark_attendance(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        registration_id: uuid.UUID,
        *,
        attended: bool,
    ) -> EventRegistration:
        """
        Mark attendance for a registration.
        IDOR check: registration must belong to the specified event.
        """
        # IDOR: verify registration belongs to the specified event
        reg_result = await self.db.execute(
            select(EventRegistration).filter(
                EventRegistration.id == registration_id,
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,  # IDOR prevention
            )
        )
        registration = reg_result.scalar_one_or_none()
        if not registration:
            raise EventServiceError("Registration not found", "REG_NOT_FOUND")

        registration.attended = attended
        await self.db.flush()
        await self.db.refresh(registration)
        return registration

    async def get_event_stats(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> dict:
        """Get attendance and registration stats for an event."""
        event = await self._get_event(tenant_id, event_id)

        # Count attended using SQL aggregation
        attended_result = await self.db.execute(
            select(func.count(EventRegistration.id)).filter(
                EventRegistration.tenant_id == tenant_id,
                EventRegistration.event_id == event_id,
                EventRegistration.attended.is_(True),
            )
        )
        attended_count = attended_result.scalar() or 0

        total = event.registered_count
        attendance_rate = round(attended_count / total * 100, 1) if total > 0 else 0.0
        fill_rate = None
        if event.capacity and event.capacity > 0:
            fill_rate = round(total / event.capacity * 100, 1)

        return {
            "event_id": event.id,
            "event_name": event.name,
            "total_registered": total,
            "total_attended": attended_count,
            "attendance_rate": attendance_rate,
            "capacity": event.capacity,
            "fill_rate": fill_rate,
        }

    async def _get_event(
        self,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> SchoolEvent:
        """Get event by ID with defense-in-depth tenant check."""
        result = await self.db.execute(
            select(SchoolEvent).filter(
                SchoolEvent.id == event_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                SchoolEvent.tenant_id == tenant_id,
                SchoolEvent.deleted_at.is_(None),
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise EventServiceError("Event not found", "NOT_FOUND")
        return event
```

### 4.3 New File: `backend/app/services/admissions/analytics_service.py`

```python
"""
SIMS Plus - Admissions Analytics Service

Provides enrollment funnel, trends, lead source effectiveness, re-enrollment
rates, attrition analysis, and enrollment-vs-capacity comparisons.

All analytics use SQL aggregation -- no bulk-loading records into Python.
"""

import uuid

import structlog
from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class
from app.models.admissions import (
    AdmissionApplicationStatus,
    Application,
    EnrollmentTarget,
    ReturnIntent,
    ReturnIntentCampaign,
    TERMINAL_STATUSES,
)
from app.models.student import Student

logger = structlog.get_logger(__name__)


class AnalyticsServiceError(Exception):
    def __init__(self, message: str, code: str = "ANALYTICS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class AdmissionsAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_full_funnel(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Full admissions funnel: inquiry -> application -> offered -> accepted -> enrolled.

        Each stage shows its count and conversion rate from the previous stage.
        Uses SQL COUNT with CASE expressions for single-pass aggregation.
        """
        # Inquiry count (from inquiries table if Phase 1 is deployed)
        try:
            from app.models.admissions.inquiry import Inquiry

            inquiry_query = select(func.count(Inquiry.id)).filter(
                Inquiry.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                Inquiry.deleted_at.is_(None),
            )
            inquiry_result = await self.db.execute(inquiry_query)
            inquiry_count = inquiry_result.scalar() or 0
        except Exception:
            # Phase 1 may not be deployed yet
            inquiry_count = 0

        # Application stage counts -- single query with CASE aggregation
        base_filter = [
            Application.tenant_id == tenant_id,
            Application.school_id == school_id,
            Application.deleted_at.is_(None),
        ]
        if period_id:
            base_filter.append(Application.admission_period_id == period_id)

        app_stats = await self.db.execute(
            select(
                func.count(Application.id).label("total"),
                func.count(case(
                    (Application.status.in_([
                        AdmissionApplicationStatus.OFFERED.value,
                        AdmissionApplicationStatus.ACCEPTED.value,
                        AdmissionApplicationStatus.ENROLLED.value,
                    ]), Application.id),
                )).label("offered"),
                func.count(case(
                    (Application.status.in_([
                        AdmissionApplicationStatus.ACCEPTED.value,
                        AdmissionApplicationStatus.ENROLLED.value,
                    ]), Application.id),
                )).label("accepted"),
                func.count(case(
                    (Application.status == AdmissionApplicationStatus.ENROLLED.value, Application.id),
                )).label("enrolled"),
            ).filter(*base_filter)
        )
        row = app_stats.one()
        application_count = row.total
        offered_count = row.offered
        accepted_count = row.accepted
        enrolled_count = row.enrolled

        def rate(numerator: int, denominator: int) -> float | None:
            if denominator == 0:
                return None
            return round(numerator / denominator * 100, 1)

        stages = [
            {"stage": "inquiry", "count": inquiry_count, "conversion_rate": None},
            {"stage": "application", "count": application_count, "conversion_rate": rate(application_count, inquiry_count)},
            {"stage": "offered", "count": offered_count, "conversion_rate": rate(offered_count, application_count)},
            {"stage": "accepted", "count": accepted_count, "conversion_rate": rate(accepted_count, offered_count)},
            {"stage": "enrolled", "count": enrolled_count, "conversion_rate": rate(enrolled_count, accepted_count)},
        ]

        return {
            "school_id": school_id,
            "period_id": period_id,
            "stages": stages,
        }

    async def get_enrollment_trends(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        year_count: int = 3,
    ) -> dict:
        """
        Year-over-year enrollment counts by class.

        Queries the N most recent academic years and counts active students
        per class within each year. Uses SQL aggregation with GROUP BY.
        """
        # Get the most recent N academic years
        years_result = await self.db.execute(
            select(AcademicYear)
            .filter(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
            .order_by(AcademicYear.start_date.desc())
            .limit(year_count)
        )
        years = list(years_result.scalars().all())

        if not years:
            return {"school_id": school_id, "years": []}

        year_data = []
        for year in reversed(years):  # Chronological order
            # Count students per class for this academic year
            # Students are linked to a class; the academic year association
            # comes through their enrollment being active during that year
            counts_result = await self.db.execute(
                select(
                    Class.id.label("class_id"),
                    Class.name.label("class_name"),
                    func.count(Student.id).label("count"),
                )
                .select_from(Student)
                .join(Class, Student.class_id == Class.id)
                .filter(
                    Student.tenant_id == tenant_id,
                    Student.school_id == school_id,
                    Student.academic_year_id == year.id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                    Class.deleted_at.is_(None),
                )
                .group_by(Class.id, Class.name)
                .order_by(Class.name)
            )
            class_counts = [
                {"class_id": r.class_id, "class_name": r.class_name, "count": r.count}
                for r in counts_result.all()
            ]

            total = sum(c["count"] for c in class_counts)

            year_data.append({
                "academic_year_id": year.id,
                "academic_year_name": year.name,
                "total_enrolled": total,
                "by_class": class_counts,
            })

        return {"school_id": school_id, "years": year_data}

    async def get_lead_source_effectiveness(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Lead source effectiveness: inquiries -> applications -> enrollments per source.

        Requires Phase 1 (inquiry model) to be deployed. Falls back gracefully
        if the inquiry table doesn't exist.
        """
        try:
            from app.models.admissions.inquiry import Inquiry

            base_filter = [
                Inquiry.tenant_id == tenant_id,
                Inquiry.school_id == school_id,
                Inquiry.deleted_at.is_(None),
            ]

            # Count inquiries, applications (converted), and enrollments per source
            source_stats = await self.db.execute(
                select(
                    Inquiry.source,
                    func.count(Inquiry.id).label("inquiry_count"),
                    func.count(case(
                        (Inquiry.status.in_(["applied", "enrolled"]), Inquiry.id),
                    )).label("application_count"),
                    func.count(case(
                        (Inquiry.status == "enrolled", Inquiry.id),
                    )).label("enrollment_count"),
                )
                .filter(*base_filter)
                .group_by(Inquiry.source)
                .order_by(func.count(Inquiry.id).desc())
            )

            sources = []
            for row in source_stats.all():
                inq = row.inquiry_count
                app = row.application_count
                enr = row.enrollment_count
                sources.append({
                    "source": row.source,
                    "inquiry_count": inq,
                    "application_count": app,
                    "enrollment_count": enr,
                    "inquiry_to_application_rate": round(app / inq * 100, 1) if inq > 0 else 0.0,
                    "inquiry_to_enrollment_rate": round(enr / inq * 100, 1) if inq > 0 else 0.0,
                })

            return {"school_id": school_id, "period_id": period_id, "sources": sources}

        except Exception:
            logger.warning("lead_source_analytics_unavailable", reason="inquiry model not deployed")
            return {"school_id": school_id, "period_id": period_id, "sources": []}

    async def get_re_enrollment_rates(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        year_count: int = 3,
    ) -> dict:
        """
        Re-enrollment rates over multiple years.

        Uses return_intents data to determine how many students indicated
        they would return vs total surveyed, per academic year.
        """
        # Get recent years
        years_result = await self.db.execute(
            select(AcademicYear)
            .filter(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
            .order_by(AcademicYear.start_date.desc())
            .limit(year_count)
        )
        years = list(years_result.scalars().all())

        year_data = []
        for year in reversed(years):
            # Count return intents for this year using SQL aggregation
            stats_result = await self.db.execute(
                select(
                    func.count(ReturnIntent.id).label("total"),
                    func.count(case(
                        (ReturnIntent.intent == "returning", ReturnIntent.id),
                    )).label("returning"),
                )
                .filter(
                    ReturnIntent.tenant_id == tenant_id,
                    ReturnIntent.school_id == school_id,
                    ReturnIntent.academic_year_id == year.id,
                    ReturnIntent.deleted_at.is_(None),
                )
            )
            row = stats_result.one()
            total = row.total
            returning = row.returning

            year_data.append({
                "academic_year_id": year.id,
                "academic_year_name": year.name,
                "total_students": total,
                "returning_count": returning,
                "re_enrollment_rate": round(returning / total * 100, 1) if total > 0 else 0.0,
            })

        return {"school_id": school_id, "years": year_data}

    async def get_attrition_analysis(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID | None = None,
    ) -> dict:
        """
        Attrition analysis: withdrawn students and not-returning intents with reasons.

        Aggregates reasons from:
        1. Students with status='withdrawn' (from Student model)
        2. ReturnIntents with intent='not_returning' (from return intent surveys)
        """
        # Withdrawn students -- count + reasons
        withdrawn_filter = [
            Student.tenant_id == tenant_id,
            Student.school_id == school_id,
            Student.status == "withdrawn",
            Student.deleted_at.is_(None),
        ]
        if academic_year_id:
            withdrawn_filter.append(Student.academic_year_id == academic_year_id)

        withdrawn_result = await self.db.execute(
            select(func.count(Student.id)).filter(*withdrawn_filter)
        )
        withdrawn_count = withdrawn_result.scalar() or 0

        # Withdrawal reasons (from Student.withdrawal_reason if the column exists)
        withdrawal_reasons: list[dict] = []
        try:
            reason_result = await self.db.execute(
                select(
                    Student.withdrawal_reason,
                    func.count(Student.id).label("count"),
                )
                .filter(
                    *withdrawn_filter,
                    Student.withdrawal_reason.isnot(None),
                )
                .group_by(Student.withdrawal_reason)
                .order_by(func.count(Student.id).desc())
            )
            withdrawal_reasons = [
                {"reason": r.withdrawal_reason, "count": r.count}
                for r in reason_result.all()
            ]
        except Exception:
            # withdrawal_reason column may not exist yet
            pass

        # Not-returning intents
        nr_filter = [
            ReturnIntent.tenant_id == tenant_id,
            ReturnIntent.school_id == school_id,
            ReturnIntent.intent == "not_returning",
            ReturnIntent.deleted_at.is_(None),
        ]
        if academic_year_id:
            nr_filter.append(ReturnIntent.academic_year_id == academic_year_id)

        nr_result = await self.db.execute(
            select(func.count(ReturnIntent.id)).filter(*nr_filter)
        )
        not_returning_count = nr_result.scalar() or 0

        # Not-returning reasons
        nr_reason_result = await self.db.execute(
            select(
                ReturnIntent.reason,
                func.count(ReturnIntent.id).label("count"),
            )
            .filter(
                *nr_filter,
                ReturnIntent.reason.isnot(None),
            )
            .group_by(ReturnIntent.reason)
            .order_by(func.count(ReturnIntent.id).desc())
        )
        not_returning_reasons = [
            {"reason": r.reason, "count": r.count}
            for r in nr_reason_result.all()
        ]

        return {
            "school_id": school_id,
            "academic_year_id": academic_year_id,
            "withdrawn_count": withdrawn_count,
            "not_returning_count": not_returning_count,
            "total_attrition": withdrawn_count + not_returning_count,
            "withdrawal_reasons": withdrawal_reasons,
            "not_returning_reasons": not_returning_reasons,
        }

    async def get_enrollment_vs_capacity(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> dict:
        """
        Per-class comparison of target, actual enrollment, and physical capacity.

        Single efficient query joining classes, enrollment_targets, and student counts.
        """
        # Validate academic year
        year_result = await self.db.execute(
            select(AcademicYear).filter(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not year_result.scalar_one_or_none():
            raise AnalyticsServiceError("Academic year not found", "YEAR_NOT_FOUND")

        # Student counts per class (subquery)
        student_counts = (
            select(
                Student.class_id,
                func.count(Student.id).label("enrolled_count"),
            )
            .filter(
                Student.tenant_id == tenant_id,
                Student.school_id == school_id,
                Student.academic_year_id == academic_year_id,
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
            .group_by(Student.class_id)
            .subquery("student_counts")
        )

        # Main query
        query = (
            select(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.capacity.label("capacity"),
                EnrollmentTarget.target_count.label("target"),
                func.coalesce(student_counts.c.enrolled_count, 0).label("actual_enrolled"),
            )
            .select_from(Class)
            .outerjoin(
                EnrollmentTarget,
                and_(
                    EnrollmentTarget.class_id == Class.id,
                    EnrollmentTarget.academic_year_id == academic_year_id,
                    EnrollmentTarget.tenant_id == tenant_id,
                    EnrollmentTarget.deleted_at.is_(None),
                ),
            )
            .outerjoin(student_counts, student_counts.c.class_id == Class.id)
            .filter(
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
                Class.is_active.is_(True),
            )
            .order_by(Class.sequence.asc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        classes = []
        total_target = 0
        total_enrolled = 0
        total_capacity = 0

        for row in rows:
            target = row.target
            actual = row.actual_enrolled
            capacity = row.capacity

            variance = (actual - target) if target is not None else None
            fill_pct = round(actual / capacity * 100, 1) if capacity and capacity > 0 else None

            classes.append({
                "class_id": row.class_id,
                "class_name": row.class_name,
                "target": target,
                "actual_enrolled": actual,
                "capacity": capacity,
                "variance": variance,
                "fill_pct": fill_pct,
            })

            if target:
                total_target += target
            total_enrolled += actual
            if capacity:
                total_capacity += capacity

        return {
            "school_id": school_id,
            "academic_year_id": academic_year_id,
            "classes": classes,
            "total_target": total_target or None,
            "total_enrolled": total_enrolled,
            "total_capacity": total_capacity or None,
        }
```

### 4.4 Additions to `backend/app/services/admissions/return_intent_service.py`

Add the following methods to the `ReturnIntentService` class:

```python
    async def confirm_re_enrollment(
        self,
        tenant_id: uuid.UUID,
        intent_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> ReturnIntent:
        """
        Confirm re-enrollment for a returning student.

        Steps:
        1. Validate intent == "returning"
        2. Check outstanding fees via finance service query
        3. Set re_enrollment_confirmed = True with timestamp
        4. Snapshot outstanding fee balance
        """
        from decimal import Decimal

        intent_record = await self._get_intent(tenant_id, intent_id)

        if intent_record.intent != "returning":
            raise ReturnIntentError(
                "Can only confirm re-enrollment for 'returning' intents. "
                f"Current intent: {intent_record.intent}",
                code="INVALID_INTENT_STATE",
            )

        if intent_record.re_enrollment_confirmed:
            raise ReturnIntentError(
                "Re-enrollment already confirmed",
                code="ALREADY_CONFIRMED",
            )

        # Check outstanding fees for this student via finance tables
        outstanding_amount = Decimal("0.00")
        try:
            from app.models.finance.fee_models import Invoice

            fee_result = await self.db.execute(
                select(func.coalesce(func.sum(Invoice.balance), 0)).filter(
                    Invoice.tenant_id == tenant_id,
                    Invoice.student_id == intent_record.student_id,
                    Invoice.status.in_(["sent", "partially_paid", "overdue"]),
                    Invoice.deleted_at.is_(None),
                )
            )
            outstanding_amount = fee_result.scalar() or Decimal("0.00")
        except Exception:
            # Finance module may not be deployed; proceed without fee check
            logger.warning(
                "outstanding_fees_check_failed",
                intent_id=str(intent_id),
            )

        intent_record.re_enrollment_confirmed = True
        intent_record.re_enrollment_confirmed_at = datetime.now(UTC)
        intent_record.outstanding_fees_checked = True
        intent_record.outstanding_fee_amount = outstanding_amount

        await self.db.flush()
        await self.db.refresh(intent_record)

        logger.info(
            "re_enrollment_confirmed",
            intent_id=str(intent_id),
            student_id=str(intent_record.student_id),
            outstanding_fees=str(outstanding_amount),
        )
        return intent_record

    async def get_re_enrollment_summary(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> dict:
        """
        Re-enrollment summary for a campaign.

        Returns: confirmed vs pending vs not_returning counts,
        outstanding fee totals, and per-class breakdown.
        """
        # Verify campaign exists
        await self._get_campaign(tenant_id, campaign_id)

        base_filter = [
            ReturnIntent.campaign_id == campaign_id,
            ReturnIntent.tenant_id == tenant_id,
            ReturnIntent.deleted_at.is_(None),
        ]

        # Aggregate counts using CASE expressions
        stats_result = await self.db.execute(
            select(
                func.count(ReturnIntent.id).label("total"),
                func.count(case(
                    (ReturnIntent.re_enrollment_confirmed.is_(True), ReturnIntent.id),
                )).label("confirmed"),
                func.count(case(
                    (and_(
                        ReturnIntent.intent == "returning",
                        ReturnIntent.re_enrollment_confirmed.is_(False),
                    ), ReturnIntent.id),
                )).label("pending"),
                func.count(case(
                    (ReturnIntent.intent == "not_returning", ReturnIntent.id),
                )).label("not_returning"),
                func.count(case(
                    (ReturnIntent.intent.in_(["pending", "undecided"]), ReturnIntent.id),
                )).label("undecided"),
                func.coalesce(
                    func.sum(case(
                        (ReturnIntent.outstanding_fee_amount.isnot(None), ReturnIntent.outstanding_fee_amount),
                        else_=0,
                    )), 0,
                ).label("total_fees"),
            ).filter(*base_filter)
        )
        stats = stats_result.one()

        # Per-class breakdown using Student join
        class_result = await self.db.execute(
            select(
                Class.name.label("class_name"),
                func.count(case(
                    (ReturnIntent.re_enrollment_confirmed.is_(True), ReturnIntent.id),
                )).label("confirmed"),
                func.count(case(
                    (and_(
                        ReturnIntent.intent == "returning",
                        ReturnIntent.re_enrollment_confirmed.is_(False),
                    ), ReturnIntent.id),
                )).label("pending"),
                func.count(case(
                    (ReturnIntent.intent == "not_returning", ReturnIntent.id),
                )).label("not_returning"),
            )
            .select_from(ReturnIntent)
            .join(Student, ReturnIntent.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .filter(*base_filter)
            .group_by(Class.name)
            .order_by(Class.name)
        )
        by_class = [
            {
                "class_name": r.class_name,
                "confirmed": r.confirmed,
                "pending": r.pending,
                "not_returning": r.not_returning,
            }
            for r in class_result.all()
        ]

        return {
            "campaign_id": campaign_id,
            "total_intents": stats.total,
            "confirmed_count": stats.confirmed,
            "pending_count": stats.pending,
            "not_returning_count": stats.not_returning,
            "undecided_count": stats.undecided,
            "total_outstanding_fees": float(stats.total_fees),
            "by_class": by_class,
        }
```

Also add the necessary import at the top of the file:

```python
from app.models.academic import Class
from app.models.student import Student
```

### 4.5 Update `backend/app/services/admissions/__init__.py`

Add:
```python
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
```

Add to `__all__`:
```python
# Capacity planning
"CapacityService",
"CapacityServiceError",
# School events
"EventService",
"EventServiceError",
# Analytics
"AdmissionsAnalyticsService",
"AnalyticsServiceError",
```

---

## 5. Endpoints

### 5.1 New File: `backend/app/api/v1/endpoints/admissions/capacity.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/capacity/targets` | Set target (upsert) | admissions.update | EnrollmentTargetCreate | EnrollmentTargetResponse (201) |
| GET | `/admissions/capacity/targets` | List targets for year | admissions.read | Query: academic_year_id | EnrollmentTargetListResponse |
| GET | `/admissions/capacity/dashboard` | Capacity dashboard | admissions.read | Query: academic_year_id | CapacityDashboardResponse |
| GET | `/admissions/capacity/check/{class_id}` | Quick capacity check | admissions.read | - | CapacityCheckResponse |

**Endpoint implementation pattern:**

```python
"""
SIMS Plus - Capacity Planning Endpoints

Enrollment targets and capacity dashboard for admissions planning.
"""

import math
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.capacity import (
    CapacityCheckResponse,
    CapacityDashboardResponse,
    EnrollmentTargetCreate,
    EnrollmentTargetListResponse,
    EnrollmentTargetResponse,
)
from app.services.admissions import CapacityService, CapacityServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/capacity")


def _handle_error(e: CapacityServiceError) -> HTTPException:
    status_map = {
        "YEAR_NOT_FOUND": 404,
        "CLASS_NOT_FOUND": 404,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "/targets",
    response_model=EnrollmentTargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set enrollment target",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def set_target(
    data: EnrollmentTargetCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EnrollmentTargetResponse:
    """Set or update enrollment target for a class/year (upsert semantics)."""
    try:
        svc = CapacityService(db)
        target = await svc.set_target(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            target_count=data.target_count,
            boarding_target=data.boarding_target,
            day_target=data.day_target,
        )
        return EnrollmentTargetResponse.model_validate(target)
    except CapacityServiceError as e:
        raise _handle_error(e)


@router.get(
    "/targets",
    response_model=EnrollmentTargetListResponse,
    summary="List enrollment targets",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_targets(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(..., description="Academic year to get targets for"),
) -> EnrollmentTargetListResponse:
    svc = CapacityService(db)
    targets = await svc.get_targets(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        academic_year_id=academic_year_id,
    )
    return EnrollmentTargetListResponse(
        items=targets,
        academic_year_id=academic_year_id,
    )


@router.get(
    "/dashboard",
    response_model=CapacityDashboardResponse,
    summary="Capacity planning dashboard",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_dashboard(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(..., description="Academic year for dashboard"),
) -> CapacityDashboardResponse:
    try:
        svc = CapacityService(db)
        return await svc.get_dashboard(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=academic_year_id,
        )
    except CapacityServiceError as e:
        raise _handle_error(e)


@router.get(
    "/check/{class_id}",
    response_model=CapacityCheckResponse,
    summary="Check class capacity",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def check_capacity(
    class_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> CapacityCheckResponse:
    try:
        svc = CapacityService(db)
        return await svc.check_capacity(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            class_id=class_id,
        )
    except CapacityServiceError as e:
        raise _handle_error(e)
```

### 5.2 New File: `backend/app/api/v1/endpoints/admissions/events.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/events` | Create event | admissions.create | EventCreate | EventResponse (201) |
| GET | `/admissions/events` | List events | admissions.read | Query: event_type, status, page, page_size | EventListResponse |
| GET | `/admissions/events/{id}` | Get event detail | admissions.read | - | EventResponse |
| PATCH | `/admissions/events/{id}` | Update event | admissions.update | EventUpdate | EventResponse |
| DELETE | `/admissions/events/{id}` | Cancel event | admissions.delete | - | EventResponse |
| POST | `/admissions/events/{id}/register` | Register for event | admissions.create | RegistrationCreate | RegistrationResponse (201) |
| DELETE | `/admissions/events/{id}/registrations/{rid}` | Cancel registration | admissions.delete | - | 204 |
| PATCH | `/admissions/events/{id}/registrations/{rid}/attendance` | Mark attendance | admissions.update | AttendanceUpdate | RegistrationResponse |
| GET | `/admissions/events/{id}/stats` | Event statistics | admissions.read | - | EventStatsResponse |

**Endpoint implementation:**

```python
"""
SIMS Plus - School Event Endpoints

Tours, open days, and orientation event management.
"""

import math
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.event import (
    AttendanceUpdate,
    EventCreate,
    EventListResponse,
    EventResponse,
    EventStatsResponse,
    EventUpdate,
    RegistrationCreate,
    RegistrationResponse,
)
from app.services.admissions import EventService, EventServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events")


def _handle_error(e: EventServiceError) -> HTTPException:
    status_map = {
        "NOT_FOUND": 404,
        "REG_NOT_FOUND": 404,
        "NOT_UPCOMING": 409,
        "EVENT_FULL": 409,
        "INVALID_TYPE": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create school event",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def create_event(
    data: EventCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        event = await svc.create_event(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            **data.model_dump(),
        )
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=EventListResponse,
    summary="List school events",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_events(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    event_type: str | None = Query(None),
    event_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EventListResponse:
    svc = EventService(db)
    items, total = await svc.list_events(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        event_type=event_type,
        status=event_status,
        page=page,
        page_size=page_size,
    )
    return EventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event detail",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_event(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        event = await svc._get_event(UUID(user["tenant_id"]), event_id)
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update event",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        # Only pass non-None values to the service
        update_data = data.model_dump(exclude_unset=True)
        event = await svc.update_event(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            **update_data,
        )
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.delete(
    "/{event_id}",
    response_model=EventResponse,
    summary="Cancel event",
    dependencies=[Depends(require_permissions("admissions.delete"))],
)
async def cancel_event(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        event = await svc.cancel_event(UUID(user["tenant_id"]), event_id)
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{event_id}/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register for event",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def register_for_event(
    event_id: UUID,
    data: RegistrationCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RegistrationResponse:
    try:
        svc = EventService(db)
        reg = await svc.register(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            **data.model_dump(),
        )
        return RegistrationResponse.model_validate(reg)
    except EventServiceError as e:
        raise _handle_error(e)


@router.delete(
    "/{event_id}/registrations/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel registration",
    dependencies=[Depends(require_permissions("admissions.delete"))],
)
async def cancel_registration(
    event_id: UUID,
    registration_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
):
    try:
        svc = EventService(db)
        await svc.delete_registration(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            registration_id=registration_id,
        )
    except EventServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{event_id}/registrations/{registration_id}/attendance",
    response_model=RegistrationResponse,
    summary="Mark attendance",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def mark_attendance(
    event_id: UUID,
    registration_id: UUID,
    data: AttendanceUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RegistrationResponse:
    try:
        svc = EventService(db)
        reg = await svc.mark_attendance(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            registration_id=registration_id,
            attended=data.attended,
        )
        return RegistrationResponse.model_validate(reg)
    except EventServiceError as e:
        raise _handle_error(e)


@router.get(
    "/{event_id}/stats",
    response_model=EventStatsResponse,
    summary="Event statistics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_event_stats(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventStatsResponse:
    try:
        svc = EventService(db)
        return await svc.get_event_stats(UUID(user["tenant_id"]), event_id)
    except EventServiceError as e:
        raise _handle_error(e)
```

### 5.3 New File: `backend/app/api/v1/endpoints/admissions/analytics.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| GET | `/admissions/analytics/funnel` | Full admissions funnel | admissions.read | Query: period_id (optional) | FunnelResponse |
| GET | `/admissions/analytics/trends` | Year-over-year trends | admissions.read | Query: year_count (optional) | TrendsResponse |
| GET | `/admissions/analytics/lead-sources` | Lead source effectiveness | admissions.read | Query: period_id (optional) | SourceEffectivenessResponse |
| GET | `/admissions/analytics/re-enrollment` | Re-enrollment rates | admissions.read | Query: year_count (optional) | ReEnrollmentResponse |
| GET | `/admissions/analytics/attrition` | Attrition analysis | admissions.read | Query: academic_year_id (optional) | AttritionResponse |
| GET | `/admissions/analytics/capacity` | Enrollment vs capacity | admissions.read | Query: academic_year_id (required) | EnrollmentVsCapacityResponse |

**Endpoint implementation:**

```python
"""
SIMS Plus - Admissions Analytics Endpoints

Enrollment funnel, trends, lead source effectiveness, re-enrollment rates,
attrition analysis, and enrollment-vs-capacity comparisons.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.enrollment_analytics import (
    AttritionResponse,
    EnrollmentVsCapacityResponse,
    FunnelResponse,
    ReEnrollmentResponse,
    SourceEffectivenessResponse,
    TrendsResponse,
)
from app.services.admissions import AdmissionsAnalyticsService, AnalyticsServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics")


def _handle_error(e: AnalyticsServiceError) -> HTTPException:
    status_map = {
        "YEAR_NOT_FOUND": 404,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.get(
    "/funnel",
    response_model=FunnelResponse,
    summary="Admissions funnel",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_funnel(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    period_id: UUID | None = Query(None, description="Filter by admission period"),
) -> FunnelResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_full_funnel(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        period_id=period_id,
    )


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Year-over-year enrollment trends",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_trends(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    year_count: int = Query(3, ge=1, le=10, description="Number of years to show"),
) -> TrendsResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_enrollment_trends(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        year_count=year_count,
    )


@router.get(
    "/lead-sources",
    response_model=SourceEffectivenessResponse,
    summary="Lead source effectiveness",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_lead_sources(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    period_id: UUID | None = Query(None),
) -> SourceEffectivenessResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_lead_source_effectiveness(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        period_id=period_id,
    )


@router.get(
    "/re-enrollment",
    response_model=ReEnrollmentResponse,
    summary="Re-enrollment rates",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_re_enrollment(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    year_count: int = Query(3, ge=1, le=10),
) -> ReEnrollmentResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_re_enrollment_rates(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        year_count=year_count,
    )


@router.get(
    "/attrition",
    response_model=AttritionResponse,
    summary="Attrition analysis",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_attrition(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID | None = Query(None),
) -> AttritionResponse:
    svc = AdmissionsAnalyticsService(db)
    return await svc.get_attrition_analysis(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        academic_year_id=academic_year_id,
    )


@router.get(
    "/capacity",
    response_model=EnrollmentVsCapacityResponse,
    summary="Enrollment vs capacity",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_enrollment_vs_capacity(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    academic_year_id: UUID = Query(..., description="Academic year for comparison"),
) -> EnrollmentVsCapacityResponse:
    try:
        svc = AdmissionsAnalyticsService(db)
        return await svc.get_enrollment_vs_capacity(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=academic_year_id,
        )
    except AnalyticsServiceError as e:
        raise _handle_error(e)
```

### 5.4 Additions to `backend/app/api/v1/endpoints/admissions/return_intents.py`

Add two new endpoints to the existing return_intents router:

```python
@router.post(
    "/{intent_id}/confirm",
    response_model=ReturnIntentResponse,
    summary="Confirm re-enrollment",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def confirm_re_enrollment(
    intent_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentResponse:
    """
    Confirm re-enrollment for a returning student.
    Checks outstanding fees and records confirmation timestamp.
    """
    service = ReturnIntentService(db)
    try:
        return await service.confirm_re_enrollment(
            tenant_id=UUID(user["tenant_id"]),
            intent_id=intent_id,
            user_id=UUID(user["user_id"]),
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.get(
    "/campaigns/{campaign_id}/summary",
    response_model=ReEnrollmentSummaryResponse,
    summary="Re-enrollment summary",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_re_enrollment_summary(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReEnrollmentSummaryResponse:
    """
    Get re-enrollment confirmation summary for a campaign.
    Shows confirmed/pending/not-returning counts, outstanding fees, and class breakdown.
    """
    service = ReturnIntentService(db)
    try:
        return await service.get_re_enrollment_summary(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            campaign_id=campaign_id,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)
```

Add these imports to the top of return_intents.py:
```python
from app.schemas.enrollment_analytics import ReEnrollmentSummaryResponse
```

Also add to the `_handle_error` status_map:
```python
"INVALID_INTENT_STATE": 422,
"ALREADY_CONFIRMED": 409,
```

### 5.5 Update `backend/app/api/v1/endpoints/admissions/__init__.py`

Add to the router registration:

```python
from .capacity import router as capacity_router
from .events import router as events_router
from .analytics import router as analytics_router

# In the router.include_router() section:
router.include_router(capacity_router, tags=["Capacity Planning"])
router.include_router(events_router, tags=["School Events"])
router.include_router(analytics_router, tags=["Admissions Analytics"])
```

---

## 6. Migration

### File: `backend/alembic/versions/20260422_0100_capacity_events.py`

```python
"""Capacity planning, school events, and re-enrollment confirmation.

Revision ID: 20260422_0100
Revises: <CURRENT_HEAD>
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260422_0100"
down_revision = "<CURRENT_HEAD>"  # Replace with actual current head
branch_labels = None
depends_on = None

# New tables for batch RLS setup
NEW_TABLES = [
    "enrollment_targets",
    "school_events",
    "event_registrations",
]


def upgrade() -> None:
    # ========== PHASE 1: Create Enums ==========

    event_type = postgresql.ENUM(
        "open_day", "tour", "orientation",
        name="eventtype", create_type=False,
    )
    event_type.create(op.get_bind(), checkfirst=True)

    event_status = postgresql.ENUM(
        "upcoming", "completed", "cancelled",
        name="eventstatus", create_type=False,
    )
    event_status.create(op.get_bind(), checkfirst=True)

    # ========== PHASE 2: Create Tables ==========

    op.create_table(
        "enrollment_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_count", sa.Integer, nullable=False),
        sa.Column("boarding_target", sa.Integer, nullable=True),
        sa.Column("day_target", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.CheckConstraint("target_count >= 0", name="ck_enrollment_targets_count"),
        sa.CheckConstraint("boarding_target >= 0 OR boarding_target IS NULL", name="ck_enrollment_targets_boarding"),
        sa.CheckConstraint("day_target >= 0 OR day_target IS NULL", name="ck_enrollment_targets_day"),
    )

    op.create_table(
        "school_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("start_time", sa.Time, nullable=True),
        sa.Column("end_time", sa.Time, nullable=True),
        sa.Column("venue", sa.String(255), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("registered_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("guide_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guide_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("capacity >= 1 OR capacity IS NULL", name="ck_school_events_capacity"),
        sa.CheckConstraint("registered_count >= 0", name="ck_school_events_reg_count"),
    )

    # event_registrations (NO deleted_at — hard deletes for cancellations)
    op.create_table(
        "event_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("registrant_name", sa.String(200), nullable=False),
        sa.Column("registrant_phone", sa.String(20), nullable=False),
        sa.Column("registrant_email", sa.String(255), nullable=True),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("attended", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["school_events.id"], ondelete="CASCADE"),
    )

    # ========== PHASE 3: Column Additions to return_intents ==========

    op.add_column("return_intents", sa.Column("re_enrollment_confirmed", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("return_intents", sa.Column("re_enrollment_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("return_intents", sa.Column("outstanding_fees_checked", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("return_intents", sa.Column("outstanding_fee_amount", sa.Numeric(10, 2), nullable=True))

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

    # enrollment_targets
    op.create_index(
        "uq_enrollment_targets_class_year",
        "enrollment_targets",
        ["tenant_id", "academic_year_id", "class_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_enrollment_targets_school_year",
        "enrollment_targets",
        ["tenant_id", "school_id", "academic_year_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # school_events
    op.create_index(
        "ix_school_events_tenant_date",
        "school_events",
        ["tenant_id", "school_id", "event_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_school_events_tenant_type",
        "school_events",
        ["tenant_id", "school_id", "event_type"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_school_events_guide",
        "school_events",
        ["tenant_id", "guide_id"],
        postgresql_where=sa.text("deleted_at IS NULL AND guide_id IS NOT NULL"),
    )

    # event_registrations
    op.create_index(
        "ix_event_registrations_event",
        "event_registrations",
        ["tenant_id", "event_id"],
    )
    op.create_index(
        "ix_event_registrations_phone",
        "event_registrations",
        ["tenant_id", "registrant_phone"],
    )

    # Prevent double-registration by same phone for same event
    op.create_index(
        "uq_event_reg_phone",
        "event_registrations",
        ["tenant_id", "event_id", "registrant_phone"],
        unique=True,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("uq_event_reg_phone", table_name="event_registrations")
    op.drop_index("ix_event_registrations_phone", table_name="event_registrations")
    op.drop_index("ix_event_registrations_event", table_name="event_registrations")
    op.drop_index("ix_school_events_guide", table_name="school_events")
    op.drop_index("ix_school_events_tenant_type", table_name="school_events")
    op.drop_index("ix_school_events_tenant_date", table_name="school_events")
    op.drop_index("ix_enrollment_targets_school_year", table_name="enrollment_targets")
    op.drop_index("uq_enrollment_targets_class_year", table_name="enrollment_targets")

    # Drop added columns (reverse order)
    op.drop_column("return_intents", "outstanding_fee_amount")
    op.drop_column("return_intents", "outstanding_fees_checked")
    op.drop_column("return_intents", "re_enrollment_confirmed_at")
    op.drop_column("return_intents", "re_enrollment_confirmed")

    # Drop tables (child first)
    op.drop_table("event_registrations")
    op.drop_table("school_events")
    op.drop_table("enrollment_targets")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS eventstatus")
    op.execute("DROP TYPE IF EXISTS eventtype")
```

---

## 7. Frontend

### 7.1 Types: `frontend/types/capacity.type.ts`

Define TypeScript types matching the Pydantic schemas -- EnrollmentTargetCreate, EnrollmentTargetResponse, EnrollmentTargetListResponse, ClassCapacityRow, CapacityDashboardResponse, CapacityCheckResponse.

### 7.2 Types: `frontend/types/event.type.ts`

EventType, EventStatus, EventCreate, EventUpdate, EventResponse, EventListResponse, RegistrationCreate, RegistrationResponse, AttendanceUpdate, EventStatsResponse.

### 7.3 Types: additions to `frontend/types/admissions.type.ts`

FunnelStageResponse, FunnelResponse, YearTrendRow, TrendsResponse, SourceEffectivenessRow, SourceEffectivenessResponse, ReEnrollmentYearRow, ReEnrollmentResponse, AttritionResponse, EnrollmentVsCapacityRow, EnrollmentVsCapacityResponse, ReEnrollmentSummaryResponse.

### 7.4 Server Actions: `frontend/actions/capacity.action.ts`

Follow the existing pattern in `admissions.action.ts`:
- `setEnrollmentTarget(data)`, `getEnrollmentTargets(academicYearId)`, `getCapacityDashboard(academicYearId)`, `checkClassCapacity(classId)`

### 7.5 Server Actions: `frontend/actions/events.action.ts`

`createEvent(data)`, `getEvents(params)`, `getEvent(id)`, `updateEvent(id, data)`, `cancelEvent(id)`, `registerForEvent(eventId, data)`, `cancelRegistration(eventId, registrationId)`, `markAttendance(eventId, registrationId, attended)`, `getEventStats(eventId)`

### 7.6 Server Actions: additions to `frontend/actions/admissions.action.ts`

`getAdmissionsFunnel(periodId?)`, `getEnrollmentTrends(yearCount?)`, `getLeadSourceEffectiveness(periodId?)`, `getReEnrollmentRates(yearCount?)`, `getAttritionAnalysis(academicYearId?)`, `getEnrollmentVsCapacity(academicYearId)`, `confirmReEnrollment(intentId)`, `getReEnrollmentSummary(campaignId)`

### 7.7 Pages

**`/admissions/capacity/page.tsx`** -- Capacity Planning Dashboard:
- Academic year selector at top
- Summary cards: total capacity, total target, total enrolled, fill rate
- Bar chart comparing target vs actual vs capacity per class (CapacityChart component)
- Data table with per-class breakdown: class name, capacity, target, enrolled, pipeline, utilization % (CapacityTable component)
- Inline editing for targets (click to set/update target count per class)

**`/admissions/events/page.tsx`** -- School Events:
- Stats cards: upcoming events, total registrations, average attendance rate
- Data table with columns: Name, Type, Date, Venue, Registered/Capacity, Status
- Filters: event_type dropdown, status dropdown
- Row actions: View, Edit, Cancel
- "New Event" button (opens EventForm dialog)

**`/admissions/events/[id]/page.tsx`** -- Event Detail:
- Header: event name, type badge, status badge, date/time, venue
- Stats row: registered count, attended count, attendance rate, fill rate
- Registration table with columns: Name, Phone, Email, Student, Attended
- "Register" button to add new registration
- Bulk mark attendance toggle
- Export registrations as CSV

**`/admissions/analytics/page.tsx`** -- Admissions Analytics Dashboard:
- Period selector (optional filter)
- Row 1: EnrollmentFunnel visualization (horizontal funnel with conversion rates)
- Row 2: TrendChart (multi-year line chart by class) + LeadSourceChart (bar chart by source)
- Row 3: AttritionReport (pie chart of reasons) + EnrollmentVsCapacity bar chart
- Tabs for re-enrollment rates by year

**`/admissions/return-intents/[campaignId]/summary/page.tsx`** -- Re-enrollment Summary:
- Summary cards: confirmed, pending, not returning, undecided, total outstanding fees
- Table by class: class name, confirmed count, pending count, not returning count
- Action button on each returning intent: "Confirm Re-enrollment"
- Outstanding fee warning badges

### 7.8 Components

| Component | File | Props | Description |
|-----------|------|-------|-------------|
| `CapacityChart` | `components/admissions/capacity-chart.tsx` | classes: ClassCapacityRow[] | Stacked bar chart (Recharts) showing target vs actual vs capacity |
| `CapacityTable` | `components/admissions/capacity-table.tsx` | classes, onSetTarget | TanStack Table with inline target editing |
| `EnrollmentFunnel` | `components/admissions/enrollment-funnel.tsx` | stages: FunnelStageResponse[] | Horizontal funnel visualization with conversion rate labels |
| `TrendChart` | `components/admissions/trend-chart.tsx` | years: YearTrendRow[] | Multi-line Recharts chart with year-over-year comparison |
| `LeadSourceChart` | `components/admissions/lead-source-chart.tsx` | sources: SourceEffectivenessRow[] | Bar chart with conversion rates |
| `AttritionReport` | `components/admissions/attrition-report.tsx` | data: AttritionResponse | Donut chart of reasons + summary stats |
| `EventForm` | `components/admissions/event-form.tsx` | onSubmit, defaultValues | React Hook Form + Zod for create/edit event |
| `EventRegistrationTable` | `components/admissions/event-registration-table.tsx` | registrations, onMarkAttendance, onDelete | TanStack Table with attendance toggle |
| `ReEnrollmentConfirmation` | `components/admissions/re-enrollment-confirmation.tsx` | intent, onConfirm | Confirmation dialog with outstanding fee display |

### 7.9 Sidebar Update

In `frontend/components/dashboard/app-sidebar.tsx`, add to the admissions navigation group:

```typescript
{ title: "Capacity Planning", url: "/admissions/capacity", icon: BarChart3 },
{ title: "Events & Tours", url: "/admissions/events", icon: CalendarDays },
{ title: "Analytics", url: "/admissions/analytics", icon: TrendingUp },
```

Position them after the existing admissions items (Applications, Decisions, etc.).

---

## 8. Tests

### 8.1 `backend/tests/test_capacity_planning.py` (~10 tests)

Follow the two-engine pattern from `test_admission_applications.py`:

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestCapacityPlanning:
    # Target CRUD
    async def test_set_target_create(self, app_session, prereqs)
    async def test_set_target_upsert_updates_existing(self, app_session, prereqs)
    async def test_set_target_invalid_year(self, app_session, prereqs)
    async def test_set_target_invalid_class(self, app_session, prereqs)
    async def test_get_targets_for_year(self, app_session, prereqs)
    async def test_get_targets_empty_year(self, app_session, prereqs)

    # Dashboard
    async def test_dashboard_aggregation(self, app_session, prereqs)
    async def test_dashboard_includes_pipeline_count(self, app_session, prereqs)
    async def test_dashboard_utilization_calculation(self, app_session, prereqs)

    # Capacity check
    async def test_check_capacity_with_room(self, app_session, prereqs)
    async def test_check_capacity_full_class(self, app_session, prereqs)
    async def test_check_capacity_unlimited(self, app_session, prereqs)
```

### 8.2 `backend/tests/test_school_events.py` (~10 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestSchoolEvents:
    # Event CRUD
    async def test_create_event(self, app_session, prereqs)
    async def test_create_event_invalid_type(self, app_session, prereqs)
    async def test_update_event(self, app_session, prereqs)
    async def test_update_completed_event_fails(self, app_session, prereqs)
    async def test_cancel_event(self, app_session, prereqs)
    async def test_list_events_with_filters(self, app_session, prereqs)

    # Registration
    async def test_register_for_event(self, app_session, prereqs)
    async def test_register_at_capacity_fails(self, app_session, prereqs)
    async def test_cancel_registration_decrements_count(self, app_session, prereqs)

    # Attendance
    async def test_mark_attendance(self, app_session, prereqs)
    async def test_event_stats_calculation(self, app_session, prereqs)

    # IDOR
    async def test_registration_idor_prevention(self, app_session, prereqs)
```

### 8.3 `backend/tests/test_admissions_analytics.py` (~12 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestAdmissionsAnalytics:
    # Funnel
    async def test_funnel_counts_all_stages(self, app_session, prereqs)
    async def test_funnel_conversion_rates(self, app_session, prereqs)
    async def test_funnel_with_period_filter(self, app_session, prereqs)

    # Trends
    async def test_enrollment_trends_multiple_years(self, app_session, prereqs)
    async def test_enrollment_trends_empty(self, app_session, prereqs)

    # Lead sources
    async def test_lead_source_effectiveness(self, app_session, prereqs)
    async def test_lead_source_without_inquiries(self, app_session, prereqs)

    # Re-enrollment
    async def test_re_enrollment_rates(self, app_session, prereqs)

    # Attrition
    async def test_attrition_analysis_withdrawn(self, app_session, prereqs)
    async def test_attrition_analysis_not_returning(self, app_session, prereqs)

    # Enrollment vs capacity
    async def test_enrollment_vs_capacity(self, app_session, prereqs)
    async def test_enrollment_vs_capacity_invalid_year(self, app_session, prereqs)
```

### 8.4 `backend/tests/test_re_enrollment_confirmation.py` (~8 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestReEnrollmentConfirmation:
    async def test_confirm_returning_intent(self, app_session, prereqs)
    async def test_confirm_non_returning_fails(self, app_session, prereqs)
    async def test_confirm_already_confirmed_fails(self, app_session, prereqs)
    async def test_confirm_checks_outstanding_fees(self, app_session, prereqs)
    async def test_confirm_snapshots_fee_amount(self, app_session, prereqs)
    async def test_summary_counts(self, app_session, prereqs)
    async def test_summary_by_class_breakdown(self, app_session, prereqs)
    async def test_summary_outstanding_fee_total(self, app_session, prereqs)
```

### 8.5 `backend/tests/test_events_rls.py` (~4 tests)

```python
@pytest.mark.rls
@pytest.mark.asyncio
@pytest.mark.xdist_group("rls_serial")
class TestEventsRLS:
    async def test_enrollment_target_tenant_isolation(self, admin_session, app_session)
    async def test_school_event_tenant_isolation(self, admin_session, app_session)
    async def test_event_registration_tenant_isolation(self, admin_session, app_session)
    async def test_cross_tenant_event_invisible(self, admin_session, app_session)
```

### 8.6 Update `backend/tests/conftest.py`

Add to TENANT_SCOPED_TABLES:
```python
# Capacity & Events (Phase 4)
"enrollment_targets",
"school_events",
"event_registrations",
```

---

## 9. Task Checklist

Developers should complete these tasks in order:

- [ ] **P4-01**: Add enums to `backend/app/models/admissions/enums.py` (EventType, EventStatus)
- [ ] **P4-02**: Create `backend/app/models/admissions/capacity.py` (EnrollmentTarget)
- [ ] **P4-03**: Create `backend/app/models/admissions/event.py` (SchoolEvent, EventRegistration)
- [ ] **P4-04**: Add re-enrollment columns to `backend/app/models/admissions/return_intent.py` (re_enrollment_confirmed, re_enrollment_confirmed_at, outstanding_fees_checked, outstanding_fee_amount)
- [ ] **P4-05**: Update `backend/app/models/admissions/__init__.py` (re-exports for new models and enums)
- [ ] **P4-06**: Update `backend/app/db/base.py` (import new models for Alembic discovery)
- [ ] **P4-07**: Create migration `20260422_0100_capacity_events.py`
- [ ] **P4-08**: Create `backend/app/schemas/capacity.py`
- [ ] **P4-09**: Create `backend/app/schemas/event.py`
- [ ] **P4-10**: Create `backend/app/schemas/enrollment_analytics.py`
- [ ] **P4-11**: Create `backend/app/services/admissions/capacity_service.py`
- [ ] **P4-12**: Create `backend/app/services/admissions/event_service.py`
- [ ] **P4-13**: Create `backend/app/services/admissions/analytics_service.py`
- [ ] **P4-14**: Add `confirm_re_enrollment()` and `get_re_enrollment_summary()` to `backend/app/services/admissions/return_intent_service.py`
- [ ] **P4-15**: Update `backend/app/services/admissions/__init__.py` (re-exports for new services)
- [ ] **P4-16**: Create `backend/app/api/v1/endpoints/admissions/capacity.py`
- [ ] **P4-17**: Create `backend/app/api/v1/endpoints/admissions/events.py`
- [ ] **P4-18**: Create `backend/app/api/v1/endpoints/admissions/analytics.py`
- [ ] **P4-19**: Add confirm/summary endpoints to `backend/app/api/v1/endpoints/admissions/return_intents.py`
- [ ] **P4-20**: Update `backend/app/api/v1/endpoints/admissions/__init__.py` (register new routers)
- [ ] **P4-21**: Update `backend/tests/conftest.py` (add 3 tables to TENANT_SCOPED_TABLES)
- [ ] **P4-22**: Write `backend/tests/test_capacity_planning.py`
- [ ] **P4-23**: Write `backend/tests/test_school_events.py`
- [ ] **P4-24**: Write `backend/tests/test_admissions_analytics.py`
- [ ] **P4-25**: Write `backend/tests/test_re_enrollment_confirmation.py`
- [ ] **P4-26**: Write `backend/tests/test_events_rls.py`
- [ ] **P4-27**: Create `frontend/types/capacity.type.ts`
- [ ] **P4-28**: Create `frontend/types/event.type.ts`
- [ ] **P4-29**: Add analytics types to `frontend/types/admissions.type.ts`
- [ ] **P4-30**: Create `frontend/actions/capacity.action.ts`
- [ ] **P4-31**: Create `frontend/actions/events.action.ts`
- [ ] **P4-32**: Add analytics + re-enrollment actions to `frontend/actions/admissions.action.ts`
- [ ] **P4-33**: Create capacity dashboard components (CapacityChart, CapacityTable)
- [ ] **P4-34**: Create analytics components (EnrollmentFunnel, TrendChart, LeadSourceChart, AttritionReport)
- [ ] **P4-35**: Create event components (EventForm, EventRegistrationTable)
- [ ] **P4-36**: Create ReEnrollmentConfirmation component
- [ ] **P4-37**: Create `/admissions/capacity/page.tsx`
- [ ] **P4-38**: Create `/admissions/events/page.tsx` and `/admissions/events/[id]/page.tsx`
- [ ] **P4-39**: Create `/admissions/analytics/page.tsx`
- [ ] **P4-40**: Create `/admissions/return-intents/[campaignId]/summary/page.tsx`
- [ ] **P4-41**: Update sidebar navigation with Capacity Planning, Events & Tours, Analytics items
- [ ] **P4-42**: Run all tests, verify RLS, verify migration up/down

---

## 10. Operational Updates

### 10.1 Update `backend/scripts/verify_rls.py`

Add the following tables to the `TENANT_SCOPED_TABLES` list:

```python
"enrollment_targets",
"school_events",
"event_registrations",
```

### 10.2 Update `backend/app/tasks/tenant_cleanup.py`

Add the following tables to the deletion order, respecting FK dependencies:

```python
# Phase 4 tables -- delete in this order (child before parent)
"event_registrations",   # FK -> school_events (delete before school_events)
"school_events",
"enrollment_targets",
```

These must be deleted **before** `schools`, `academic_years`, `classes`, and `users` (which they reference via FKs).

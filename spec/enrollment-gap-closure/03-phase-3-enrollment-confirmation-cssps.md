# Phase 3: Enrollment Confirmation Workflow + CSSPS Import

**Covers:** GAP 6 (EM-070 to EM-079), GAP 3 partial (EM-033)
**Estimated Effort:** 2 weeks (1 sprint)
**New Tables:** 2
**Modified Tables:** 2
**New Endpoints:** 9
**New Tests:** ~42
**New PDF Templates:** 1

---

## 1. Database Schema

### 1.1 New Enums

Add to `backend/app/models/admissions/enums.py`:

```python
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
```

### 1.2 New Tables

#### Table 1: `enrollment_checklists`

Per-application enrollment checklist that tracks completion of all required pre-enrollment steps. One checklist per application.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `school_id` | UUID | No | | FK schools.id CASCADE | |
| `application_id` | UUID | No | | FK applications.id CASCADE | One checklist per application per tenant |
| `checklist_type` | VARCHAR(20) | No | `'standard'` | | ChecklistType enum value |
| `completed_at` | TIMESTAMPTZ | Yes | | | Set when all required items done |
| `completed_by` | UUID | Yes | | FK users.id SET NULL | Staff who marked final item |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Unique constraint:** `UNIQUE(tenant_id, application_id) WHERE deleted_at IS NULL` -- one active checklist per application.

**Indexes:**
```sql
CREATE UNIQUE INDEX uq_enrollment_checklist_app ON enrollment_checklists(tenant_id, application_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_enrollment_checklists_school ON enrollment_checklists(tenant_id, school_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_enrollment_checklists_incomplete ON enrollment_checklists(tenant_id, school_id) WHERE completed_at IS NULL AND deleted_at IS NULL;
```

**RLS Policy:**
```sql
ALTER TABLE enrollment_checklists ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollment_checklists FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON enrollment_checklists
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
GRANT SELECT, INSERT, UPDATE, DELETE ON enrollment_checklists TO sims_app_user;
```

#### Table 2: `enrollment_checklist_items`

Individual items within an enrollment checklist. Each item represents a task the school or parent must complete before enrollment.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | uuid4() | PK | |
| `tenant_id` | UUID | No | | FK tenants.id CASCADE | TenantMixin |
| `checklist_id` | UUID | No | | FK enrollment_checklists.id CASCADE | |
| `item_type` | VARCHAR(20) | No | | | ChecklistItemType enum value |
| `item_name` | VARCHAR(255) | No | | | Human-readable description |
| `description` | TEXT | Yes | | | Extended instructions |
| `is_required` | BOOLEAN | No | `true` | | Required items block enrollment |
| `is_completed` | BOOLEAN | No | `false` | | |
| `completed_at` | TIMESTAMPTZ | Yes | | | |
| `completed_by` | UUID | Yes | | FK users.id SET NULL | Staff who verified |
| `notes` | TEXT | Yes | | | Verification notes |
| `metadata` | JSONB | No | `'{}'` | | Flexible data: document_url, payment_ref, etc. |
| `created_at` | TIMESTAMPTZ | No | now() | | |
| `updated_at` | TIMESTAMPTZ | No | now() | | |
| `deleted_at` | TIMESTAMPTZ | Yes | | | SoftDeleteMixin |

**Indexes:**
```sql
CREATE INDEX ix_checklist_items_checklist ON enrollment_checklist_items(tenant_id, checklist_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_checklist_items_incomplete ON enrollment_checklist_items(tenant_id, checklist_id, is_required)
    WHERE is_completed = false AND deleted_at IS NULL;
```

**RLS:** Same tenant_isolation pattern.

### 1.3 Column Additions to Existing Tables

#### `applications` table -- enrollment confirmation fields

```sql
ALTER TABLE applications ADD COLUMN enrollment_deposit_paid BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE applications ADD COLUMN enrollment_deposit_amount NUMERIC(10,2);
ALTER TABLE applications ADD COLUMN enrollment_deposit_reference VARCHAR(255);
ALTER TABLE applications ADD COLUMN boarding_status VARCHAR(20);
ALTER TABLE applications ADD COLUMN enrollment_confirmation_url VARCHAR(500);
ALTER TABLE applications ADD COLUMN welcome_pack_sent BOOLEAN NOT NULL DEFAULT false;
```

**Model change:** Add to `Application` class in `backend/app/models/admissions/application.py`:

```python
# Enrollment confirmation fields (Phase 3)
enrollment_deposit_paid: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default="false",
    comment="Whether enrollment deposit has been received",
)
enrollment_deposit_amount: Mapped[Decimal | None] = mapped_column(
    Numeric(10, 2),
    nullable=True,
    comment="Deposit amount in tenant currency",
)
enrollment_deposit_reference: Mapped[str | None] = mapped_column(
    String(255),
    nullable=True,
    comment="Payment reference (receipt number, bank ref, etc.)",
)
boarding_status: Mapped[str | None] = mapped_column(
    String(20),
    nullable=True,
    comment="boarding or day -- set during enrollment confirmation",
)
enrollment_confirmation_url: Mapped[str | None] = mapped_column(
    String(500),
    nullable=True,
    comment="S3 URL for generated enrollment confirmation PDF",
)
welcome_pack_sent: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default="false",
    comment="Whether welcome/orientation info has been sent",
)
```

**New relationship on Application:**
```python
# TYPE_CHECKING import:
from app.models.admissions.enrollment_checklist import EnrollmentChecklist

# Relationship (add after existing relationships):
enrollment_checklist: Mapped["EnrollmentChecklist | None"] = sa_relationship(
    "EnrollmentChecklist",
    back_populates="application",
    lazy="raise",
    uselist=False,
)
```

#### `admission_periods` table -- enrollment deposit configuration

```sql
ALTER TABLE admission_periods ADD COLUMN enrollment_deposit_required BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE admission_periods ADD COLUMN enrollment_deposit_amount NUMERIC(10,2);
ALTER TABLE admission_periods ADD COLUMN enrollment_checklist_template JSONB NOT NULL DEFAULT '[]';
```

**Model change:** Add to `AdmissionPeriod` class in `backend/app/models/admissions/period.py`:

```python
# Enrollment confirmation config (Phase 3)
enrollment_deposit_required: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default="false",
    comment="Whether enrollment deposit is required before enrollment",
)
enrollment_deposit_amount: Mapped[Decimal | None] = mapped_column(
    Numeric(10, 2),
    nullable=True,
    comment="Required deposit amount (null if not required)",
)
enrollment_checklist_template: Mapped[list] = mapped_column(
    JSONB,
    nullable=False,
    default=list,
    server_default="[]",
    comment="Template items auto-populated when checklist is created",
)
```

**enrollment_checklist_template JSONB format:**
```json
[
  {"item_type": "document", "item_name": "Birth certificate submitted", "is_required": true},
  {"item_type": "document", "item_name": "Passport photos (2)", "is_required": true},
  {"item_type": "medical", "item_name": "Medical form completed", "is_required": true},
  {"item_type": "payment", "item_name": "Enrollment deposit paid", "is_required": true},
  {"item_type": "form", "item_name": "Parent agreement signed", "is_required": true}
]
```

**Boarding-specific items** (auto-added when `boarding_status == "boarding"`):
```json
[
  {"item_type": "boarding", "item_name": "Boarding fee paid", "is_required": true},
  {"item_type": "boarding", "item_name": "Dormitory preference submitted", "is_required": false},
  {"item_type": "medical", "item_name": "Boarding medical clearance", "is_required": true},
  {"item_type": "document", "item_name": "Boarding agreement signed", "is_required": true}
]
```

---

## 2. Models

### 2.1 New File: `backend/app/models/admissions/enrollment_checklist.py`

```python
"""
SIMS Plus - Enrollment Checklist Models

Per-application enrollment checklists that track completion of required
pre-enrollment steps: document submission, payment verification, medical
forms, boarding requirements, and parent agreements.

The checklist is OPTIONAL (see AD-3 in overview.md). Applications without
a checklist proceed to enrollment normally. When a checklist exists, ALL
required items must be completed before EnrollmentService.enroll() succeeds.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.admissions.application import Application
    from app.models.school import School
    from app.models.tenant import User


class EnrollmentChecklist(Base, TenantMixin, SoftDeleteMixin):
    """
    Enrollment checklist for an accepted application.

    Auto-populated from the admission period's enrollment_checklist_template
    when created. Boarding-specific items are appended when the application's
    boarding_status is set to 'boarding'.

    The checklist is considered complete when all required items (is_required=True)
    have is_completed=True. completed_at is set automatically at that point.
    """

    __tablename__ = "enrollment_checklists"

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
    checklist_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        server_default="standard",
        comment="standard or boarding -- determines which template items are included",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when all required items are completed",
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff who completed the final required item",
    )

    # Relationships
    school: Mapped["School"] = sa_relationship("School", lazy="raise")
    application: Mapped["Application"] = sa_relationship(
        "Application",
        back_populates="enrollment_checklist",
        lazy="raise",
    )
    completed_by_user: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[completed_by], lazy="raise"
    )
    items: Mapped[list["EnrollmentChecklistItem"]] = sa_relationship(
        "EnrollmentChecklistItem",
        back_populates="checklist",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class EnrollmentChecklistItem(Base, TenantMixin, SoftDeleteMixin):
    """
    Individual item within an enrollment checklist.

    Items are categorized by type (document, payment, form, boarding, medical)
    for UI grouping. Required items must be completed before enrollment can
    proceed. Optional items are tracked for completeness but do not block.

    The metadata JSONB field stores type-specific data:
    - document: {"document_url": "s3://..."}
    - payment: {"payment_ref": "REC-001", "amount": 500.00}
    - form: {"signed_date": "2026-04-10"}
    - boarding: {"dormitory_preference": "Aggrey House"}
    - medical: {"doctor_name": "Dr. Mensah", "clearance_date": "2026-04-08"}
    """

    __tablename__ = "enrollment_checklist_items"

    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollment_checklists.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="document, payment, form, boarding, medical",
    )
    item_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable task description",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extended instructions for this item",
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="If true, must be completed before enrollment",
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes from staff",
    )
    item_metadata: Mapped[dict] = mapped_column(
        "metadata",  # DB column name stays the same
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Type-specific data: document_url, payment_ref, etc.",
    )

    # Relationships
    checklist: Mapped["EnrollmentChecklist"] = sa_relationship(
        "EnrollmentChecklist",
        back_populates="items",
        lazy="raise",
    )
    completer: Mapped["User | None"] = sa_relationship(
        "User", foreign_keys=[completed_by], lazy="raise"
    )
```

### 2.2 Update `backend/app/models/admissions/__init__.py`

Add the following imports and `__all__` entries:

```python
from app.models.admissions.enums import (
    BoardingStatus,
    ChecklistItemType,
    ChecklistType,
    # ... existing enum exports
)
from app.models.admissions.enrollment_checklist import (
    EnrollmentChecklist,
    EnrollmentChecklistItem,
)
```

### 2.3 Update `backend/app/db/base.py`

Ensure the new models are imported so Alembic discovers them:

```python
from app.models.admissions.enrollment_checklist import EnrollmentChecklist, EnrollmentChecklistItem  # noqa
```

---

## 3. Schemas

### 3.1 New File: `backend/app/schemas/enrollment_checklist.py`

```python
"""
SIMS Plus - Enrollment Checklist Schemas
Pydantic schemas for enrollment checklist and deposit endpoints.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Enums for schema validation ---

class ChecklistItemTypeEnum(str, Enum):
    DOCUMENT = "document"
    PAYMENT = "payment"
    FORM = "form"
    BOARDING = "boarding"
    MEDICAL = "medical"


class BoardingStatusEnum(str, Enum):
    BOARDING = "boarding"
    DAY = "day"


# --- Checklist Item Schemas ---

class ChecklistItemResponse(BaseSchema):
    """Single checklist item detail."""
    id: UUID
    checklist_id: UUID
    item_type: str
    item_name: str
    description: str | None
    is_required: bool
    is_completed: bool
    completed_at: datetime | None
    completed_by: UUID | None
    completed_by_name: str | None = None
    notes: str | None
    metadata: dict[str, Any]
    created_at: datetime


class ChecklistItemComplete(BaseSchema):
    """Mark a checklist item as completed."""
    notes: str | None = None
    metadata: dict[str, Any] | None = None


# --- Checklist Schemas ---

class ChecklistResponse(BaseSchema):
    """Full enrollment checklist with items."""
    id: UUID
    school_id: UUID
    application_id: UUID
    checklist_type: str
    completed_at: datetime | None
    completed_by: UUID | None
    completed_by_name: str | None = None
    total_items: int = 0
    completed_items: int = 0
    required_items: int = 0
    required_completed: int = 0
    progress_pct: float = 0.0
    items: list[ChecklistItemResponse] = []
    created_at: datetime
    updated_at: datetime


# --- Enrollment Deposit Schemas ---

class EnrollmentDepositRecord(BaseSchema):
    """Record an enrollment deposit payment."""
    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    reference: str = Field(..., min_length=1, max_length=255)

    @property
    def amount_as_decimal(self) -> Decimal:
        return self.amount


class EnrollmentDepositResponse(BaseSchema):
    """Deposit recording result."""
    application_id: UUID
    enrollment_deposit_paid: bool
    enrollment_deposit_amount: Decimal | None
    enrollment_deposit_reference: str | None


# --- Boarding Status Schemas ---

class BoardingStatusAssign(BaseSchema):
    """Assign boarding or day status to an application."""
    boarding_status: BoardingStatusEnum


class BoardingStatusResponse(BaseSchema):
    """Boarding status assignment result."""
    application_id: UUID
    boarding_status: str
    boarding_items_added: int = 0


# --- Confirmation & Welcome Pack ---

class ConfirmationLetterResponse(BaseSchema):
    """Generated enrollment confirmation letter."""
    application_id: UUID
    confirmation_url: str
    applicant_name: str


class WelcomePackResponse(BaseSchema):
    """Welcome pack send result."""
    application_id: UUID
    welcome_pack_sent: bool
    channels: list[str]  # ["email", "sms"]
```

### 3.2 New File: `backend/app/schemas/cssps.py`

```python
"""
SIMS Plus - CSSPS Import Schemas
Pydantic schemas for CSSPS placement data import.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Column Mapping ---

class CSSPSColumnMapping(BaseSchema):
    """
    Maps file column headers to standard CSSPS fields.

    Keys are our standard field names; values are the actual column
    headers in the uploaded file. Only mapped columns are extracted.
    """
    index_number: str = Field("index_number", description="Column header for BECE index number")
    first_name: str = Field("first_name", description="Column header for first name")
    last_name: str = Field("last_name", description="Column header for last name")
    other_names: str | None = Field(None, description="Column header for middle/other names")
    gender: str = Field("gender", description="Column header for gender (M/F)")
    date_of_birth: str | None = Field(None, description="Column header for date of birth")
    programme: str = Field("programme", description="Column header for SHS programme")
    aggregate: str | None = Field(None, description="Column header for BECE aggregate")
    jhs_school: str | None = Field(None, description="Column header for previous JHS")
    jhs_district: str | None = Field(None, description="Column header for JHS district")
    region: str | None = Field(None, description="Column header for home region")
    parent_name: str | None = Field(None, description="Column header for parent name")
    parent_phone: str | None = Field(None, description="Column header for parent phone")
    residential_status: str | None = Field(None, description="Column header for boarding/day status")
    house: str | None = Field(None, description="Column header for assigned house")


# --- Preview Request/Response ---

class CSSPSPreviewRequest(BaseSchema):
    """Request body for CSSPS file preview (parse without DB writes)."""
    column_mapping: CSSPSColumnMapping = Field(default_factory=CSSPSColumnMapping)


class CSSPSPreviewRow(BaseSchema):
    """Single parsed row in preview."""
    row_number: int
    index_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    other_names: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    programme: str | None = None
    aggregate: int | None = None
    jhs_school: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    residential_status: str | None = None
    house: str | None = None
    errors: list[str] = []


class CSSPSPreviewResponse(BaseSchema):
    """Preview result -- parsed rows without DB writes."""
    total_rows: int
    valid_rows: int
    error_rows: int
    detected_columns: list[str]
    rows: list[CSSPSPreviewRow]


# --- Import Request/Response ---

class CSSPSImportRequest(BaseSchema):
    """
    Request body for CSSPS placement import.

    column_mapping: maps file headers to standard fields.
    programme_to_class_mapping: maps programme names to class UUIDs.
    """
    admission_period_id: UUID
    column_mapping: CSSPSColumnMapping = Field(default_factory=CSSPSColumnMapping)
    programme_to_class_mapping: dict[str, UUID] = Field(
        ...,
        description="Maps programme names to class UUIDs",
        min_length=1,
    )


class CSSPSImportResult(BaseSchema):
    """Single row import result."""
    row_number: int
    index_number: str
    status: str  # "imported", "skipped", "error"
    application_id: UUID | None = None
    error: str | None = None


class CSSPSImportResponse(BaseSchema):
    """Full import result summary."""
    total_rows: int
    imported: int
    skipped: int
    errors: int
    results: list[CSSPSImportResult]
```

---

## 4. Services

### 4.1 Modified: `backend/app/services/admissions/enrollment_service.py`

Add the following methods to the existing `EnrollmentService` class. The existing `enroll()` method is also modified to enforce checklist and deposit requirements.

```python
# Add these imports at the top of enrollment_service.py
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import selectinload

from app.models.admissions.enrollment_checklist import (
    EnrollmentChecklist,
    EnrollmentChecklistItem,
)


class EnrollmentService:
    # ... existing __init__ and methods ...

    # ---- Enrollment Checklist ----

    async def create_enrollment_checklist(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> EnrollmentChecklist:
        """
        Create an enrollment checklist for an accepted application.

        Auto-populates items from the admission period's enrollment_checklist_template.
        If the application has boarding_status == 'boarding', additional boarding-specific
        items are appended and the checklist_type is set to 'boarding'.

        Raises EnrollmentError if:
        - Application not found or not in ACCEPTED status
        - A checklist already exists for this application
        """
        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                "Checklist can only be created for applications in ACCEPTED status",
                code="INVALID_STATUS",
            )

        # Check for existing checklist -- one per application
        existing = await self.db.execute(
            select(EnrollmentChecklist).filter(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise EnrollmentError(
                "A checklist already exists for this application",
                code="CHECKLIST_EXISTS",
            )

        # Determine checklist type from boarding status
        is_boarding = app.boarding_status == "boarding"
        checklist_type = "boarding" if is_boarding else "standard"

        checklist = EnrollmentChecklist(
            tenant_id=tenant_id,
            school_id=school_id,
            application_id=application_id,
            checklist_type=checklist_type,
        )
        self.db.add(checklist)
        await self.db.flush()

        # Load template from admission period
        from app.models.admissions import AdmissionPeriod

        period_result = await self.db.execute(
            select(AdmissionPeriod).filter(
                AdmissionPeriod.id == app.admission_period_id,
                AdmissionPeriod.tenant_id == tenant_id,
            )
        )
        period = period_result.scalar_one_or_none()
        template_items = period.enrollment_checklist_template if period else []

        # Create items from template
        for item_data in template_items:
            item = EnrollmentChecklistItem(
                tenant_id=tenant_id,
                checklist_id=checklist.id,
                item_type=item_data.get("item_type", "document"),
                item_name=item_data.get("item_name", ""),
                description=item_data.get("description"),
                is_required=item_data.get("is_required", True),
            )
            self.db.add(item)

        # Append boarding-specific items if applicable
        if is_boarding:
            boarding_items = [
                {"item_type": "boarding", "item_name": "Boarding fee paid", "is_required": True},
                {"item_type": "boarding", "item_name": "Dormitory preference submitted", "is_required": False},
                {"item_type": "medical", "item_name": "Boarding medical clearance", "is_required": True},
                {"item_type": "document", "item_name": "Boarding agreement signed", "is_required": True},
            ]
            for item_data in boarding_items:
                item = EnrollmentChecklistItem(
                    tenant_id=tenant_id,
                    checklist_id=checklist.id,
                    item_type=item_data["item_type"],
                    item_name=item_data["item_name"],
                    is_required=item_data["is_required"],
                )
                self.db.add(item)

        await self.db.flush()
        await self.db.refresh(checklist)

        logger.info(
            "enrollment_checklist_created",
            checklist_id=str(checklist.id),
            application_id=str(application_id),
            checklist_type=checklist_type,
        )
        return checklist

    async def get_checklist(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> EnrollmentChecklist:
        """
        Get the enrollment checklist for an application, with items eagerly loaded.
        Raises EnrollmentError if no checklist exists.
        """
        result = await self.db.execute(
            select(EnrollmentChecklist)
            .options(selectinload(EnrollmentChecklist.items))
            .filter(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        checklist = result.scalar_one_or_none()
        if not checklist:
            raise EnrollmentError("No enrollment checklist found for this application", code="NOT_FOUND")
        return checklist

    async def complete_checklist_item(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        notes: str | None = None,
        metadata: dict | None = None,
    ) -> EnrollmentChecklistItem:
        """
        Mark a checklist item as completed.

        After marking, checks if all required items are now complete.
        If so, auto-completes the parent checklist (sets completed_at/completed_by).
        """
        result = await self.db.execute(
            select(EnrollmentChecklistItem).filter(
                EnrollmentChecklistItem.id == item_id,
                EnrollmentChecklistItem.tenant_id == tenant_id,
                EnrollmentChecklistItem.deleted_at.is_(None),
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise EnrollmentError("Checklist item not found", code="NOT_FOUND")

        if item.is_completed:
            raise EnrollmentError("Item already completed", code="ALREADY_COMPLETED")

        item.is_completed = True
        item.completed_at = datetime.now(UTC)
        item.completed_by = user_id
        if notes:
            item.notes = notes
        if metadata:
            # Merge metadata -- preserve existing keys, add/overwrite new ones
            existing_meta = item.item_metadata or {}
            existing_meta.update(metadata)
            item.item_metadata = existing_meta

        await self.db.flush()
        await self.db.refresh(item)

        # Check if all required items in the checklist are now complete
        await self._auto_complete_checklist(tenant_id, item.checklist_id, user_id)

        logger.info(
            "checklist_item_completed",
            item_id=str(item_id),
            item_name=item.item_name,
        )
        return item

    async def _auto_complete_checklist(
        self,
        tenant_id: uuid.UUID,
        checklist_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Check if all required items are complete. If so, mark the checklist
        as completed. Called after every item completion.
        """
        result = await self.db.execute(
            select(EnrollmentChecklistItem).filter(
                EnrollmentChecklistItem.tenant_id == tenant_id,
                EnrollmentChecklistItem.checklist_id == checklist_id,
                EnrollmentChecklistItem.is_required.is_(True),
                EnrollmentChecklistItem.deleted_at.is_(None),
            )
        )
        required_items = list(result.scalars().all())

        if not required_items:
            return

        all_complete = all(item.is_completed for item in required_items)
        if not all_complete:
            return

        # All required items done -- mark checklist as completed
        checklist_result = await self.db.execute(
            select(EnrollmentChecklist).filter(
                EnrollmentChecklist.id == checklist_id,
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.deleted_at.is_(None),
            )
        )
        checklist = checklist_result.scalar_one_or_none()
        if checklist and checklist.completed_at is None:
            checklist.completed_at = datetime.now(UTC)
            checklist.completed_by = user_id
            await self.db.flush()

            logger.info(
                "enrollment_checklist_auto_completed",
                checklist_id=str(checklist_id),
            )

    # ---- Enrollment Deposit ----

    async def record_enrollment_deposit(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        amount: Decimal,
        reference: str,
    ) -> Application:
        """
        Record an enrollment deposit payment.

        Sets the deposit fields on the application. If a checklist exists
        with a 'payment' type item named 'Enrollment deposit paid', that
        item is auto-completed.
        """
        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                "Deposits can only be recorded for ACCEPTED applications",
                code="INVALID_STATUS",
            )

        if app.enrollment_deposit_paid:
            raise EnrollmentError(
                "Deposit already recorded for this application",
                code="DEPOSIT_ALREADY_PAID",
            )

        app.enrollment_deposit_paid = True
        app.enrollment_deposit_amount = amount
        app.enrollment_deposit_reference = reference
        await self.db.flush()

        # Auto-complete the deposit checklist item if it exists
        deposit_item_result = await self.db.execute(
            select(EnrollmentChecklistItem)
            .join(EnrollmentChecklist, EnrollmentChecklistItem.checklist_id == EnrollmentChecklist.id)
            .filter(
                EnrollmentChecklist.tenant_id == tenant_id,
                EnrollmentChecklist.application_id == application_id,
                EnrollmentChecklist.deleted_at.is_(None),
                EnrollmentChecklistItem.item_type == "payment",
                EnrollmentChecklistItem.item_name.ilike("%deposit%"),
                EnrollmentChecklistItem.is_completed.is_(False),
                EnrollmentChecklistItem.deleted_at.is_(None),
            )
        )
        deposit_item = deposit_item_result.scalar_one_or_none()
        if deposit_item:
            deposit_item.is_completed = True
            deposit_item.completed_at = datetime.now(UTC)
            deposit_item.item_metadata = {
                "payment_ref": reference,
                "amount": float(amount),
            }
            await self.db.flush()

            # Re-check checklist completion after auto-completing the deposit item
            await self._auto_complete_checklist(
                tenant_id, deposit_item.checklist_id, deposit_item.completed_by or uuid.UUID(int=0)
            )

        await self.db.refresh(app)

        logger.info(
            "enrollment_deposit_recorded",
            application_id=str(application_id),
            amount=str(amount),
            reference=reference,
        )
        return app

    # ---- Boarding Status ----

    async def assign_boarding_status(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        status: str,
    ) -> tuple[Application, int]:
        """
        Assign boarding or day status to an application.

        If status is 'boarding' and a checklist exists, boarding-specific
        items are added to the checklist. Returns (application, boarding_items_added).
        """
        if status not in ("boarding", "day"):
            raise EnrollmentError(
                f"Invalid boarding status: {status}. Must be 'boarding' or 'day'",
                code="INVALID_BOARDING_STATUS",
            )

        app = await self._get_application(tenant_id, application_id)

        if app.status != AdmissionApplicationStatus.ACCEPTED.value:
            raise EnrollmentError(
                "Boarding status can only be assigned to ACCEPTED applications",
                code="INVALID_STATUS",
            )

        app.boarding_status = status
        await self.db.flush()

        boarding_items_added = 0

        # If boarding and checklist exists, add boarding items
        if status == "boarding":
            checklist_result = await self.db.execute(
                select(EnrollmentChecklist).filter(
                    EnrollmentChecklist.tenant_id == tenant_id,
                    EnrollmentChecklist.application_id == application_id,
                    EnrollmentChecklist.deleted_at.is_(None),
                )
            )
            checklist = checklist_result.scalar_one_or_none()

            if checklist and checklist.checklist_type != "boarding":
                # Upgrade checklist type and add boarding items
                checklist.checklist_type = "boarding"

                boarding_items = [
                    {"item_type": "boarding", "item_name": "Boarding fee paid", "is_required": True},
                    {"item_type": "boarding", "item_name": "Dormitory preference submitted", "is_required": False},
                    {"item_type": "medical", "item_name": "Boarding medical clearance", "is_required": True},
                    {"item_type": "document", "item_name": "Boarding agreement signed", "is_required": True},
                ]
                for item_data in boarding_items:
                    item = EnrollmentChecklistItem(
                        tenant_id=tenant_id,
                        checklist_id=checklist.id,
                        item_type=item_data["item_type"],
                        item_name=item_data["item_name"],
                        is_required=item_data["is_required"],
                    )
                    self.db.add(item)
                    boarding_items_added += 1

                await self.db.flush()

        await self.db.refresh(app)

        logger.info(
            "boarding_status_assigned",
            application_id=str(application_id),
            boarding_status=status,
            items_added=boarding_items_added,
        )
        return app, boarding_items_added

    # ---- Enrollment Confirmation PDF ----

    async def generate_enrollment_confirmation(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> str:
        """
        Generate an enrollment confirmation letter as a PDF and upload to S3.

        The PDF includes:
        - School branding (logo, name, address, colors)
        - Student details (name, DOB, gender)
        - Assigned class
        - Checklist completion summary (if checklist exists)
        - Boarding status (if applicable)
        - Next steps / orientation information

        Returns the S3 URL of the generated PDF.
        """
        from app.models.school import School
        from app.models.academic import Class
        from app.services.pdf import PDFService
        from app.services.s3 import get_s3_service

        app = await self._get_application(tenant_id, application_id)

        if app.status not in (
            AdmissionApplicationStatus.ACCEPTED.value,
            AdmissionApplicationStatus.ENROLLED.value,
        ):
            raise EnrollmentError(
                "Confirmation letter can only be generated for ACCEPTED or ENROLLED applications",
                code="INVALID_STATUS",
            )

        # Load school for branding
        school_result = await self.db.execute(
            select(School).filter(
                School.id == app.school_id,
                School.tenant_id == tenant_id,
            )
        )
        school = school_result.scalar_one_or_none()
        if not school:
            raise EnrollmentError("School not found", code="SCHOOL_NOT_FOUND")

        # Load target class name
        class_name = "To be assigned"
        if app.target_class_id:
            class_result = await self.db.execute(
                select(Class).filter(
                    Class.id == app.target_class_id,
                    Class.tenant_id == tenant_id,
                )
            )
            target_class = class_result.scalar_one_or_none()
            if target_class:
                class_name = target_class.name

        # Load checklist summary if it exists
        checklist_summary = None
        try:
            checklist = await self.get_checklist(tenant_id, application_id)
            items = [i for i in checklist.items if i.deleted_at is None]
            total = len(items)
            completed = sum(1 for i in items if i.is_completed)
            checklist_summary = {
                "total": total,
                "completed": completed,
                "items": [
                    {
                        "name": i.item_name,
                        "type": i.item_type,
                        "completed": i.is_completed,
                        "required": i.is_required,
                    }
                    for i in items
                ],
            }
        except EnrollmentError:
            # No checklist -- that is fine, it is optional
            pass

        # Generate PDF
        pdf_service = PDFService()
        template_context = {
            "school": school,
            "applicant_name": f"{app.applicant_first_name} {app.applicant_last_name}",
            "applicant_first_name": app.applicant_first_name,
            "applicant_last_name": app.applicant_last_name,
            "date_of_birth": app.date_of_birth,
            "gender": app.gender,
            "class_name": class_name,
            "boarding_status": app.boarding_status,
            "tracking_code": app.tracking_code,
            "deposit_paid": app.enrollment_deposit_paid,
            "deposit_amount": app.enrollment_deposit_amount,
            "checklist": checklist_summary,
            "generated_date": datetime.now(UTC),
        }

        pdf_bytes = pdf_service.render_template(
            "admissions/enrollment_confirmation.html",
            template_context,
        )

        # Upload to S3
        s3 = get_s3_service()
        s3_key = f"admissions/{tenant_id}/{application_id}/enrollment_confirmation.pdf"
        url = await s3.upload_bytes(
            pdf_bytes,
            key=s3_key,
            content_type="application/pdf",
        )

        # Save URL on application
        app.enrollment_confirmation_url = url
        await self.db.flush()

        logger.info(
            "enrollment_confirmation_generated",
            application_id=str(application_id),
            url=url,
        )
        return url

    # ---- Welcome Pack ----

    async def send_welcome_pack(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> tuple[Application, list[str]]:
        """
        Send welcome pack / orientation information via email and SMS.

        The welcome pack includes:
        - Enrollment confirmation (attached PDF if generated)
        - School term dates
        - Required materials list
        - Orientation date and time
        - Contact information

        Returns (application, channels_used).
        """
        app = await self._get_application(tenant_id, application_id)

        if app.status not in (
            AdmissionApplicationStatus.ACCEPTED.value,
            AdmissionApplicationStatus.ENROLLED.value,
        ):
            raise EnrollmentError(
                "Welcome pack can only be sent for ACCEPTED or ENROLLED applications",
                code="INVALID_STATUS",
            )

        if app.welcome_pack_sent:
            raise EnrollmentError(
                "Welcome pack already sent for this application",
                code="ALREADY_SENT",
            )

        channels: list[str] = []

        # Load guardians for contact info
        guardian_result = await self.db.execute(
            select(ApplicationGuardian).filter(
                ApplicationGuardian.application_id == application_id,
                ApplicationGuardian.tenant_id == tenant_id,
                ApplicationGuardian.deleted_at.is_(None),
            )
        )
        guardians = list(guardian_result.scalars().all())
        primary = next((g for g in guardians if g.is_primary), guardians[0] if guardians else None)

        if not primary:
            raise EnrollmentError(
                "No guardian found for this application",
                code="NO_GUARDIAN",
            )

        # Send via notification service (best effort)
        try:
            from app.services.admissions.notification_service import AdmissionNotificationService

            notifier = AdmissionNotificationService(self.db)
            await notifier.notify_status_change(
                tenant_id=tenant_id,
                application_id=application_id,
                new_status="welcome_pack",
                extra_context={
                    "boarding_status": app.boarding_status or "day",
                    "confirmation_url": app.enrollment_confirmation_url,
                },
            )
            channels.append("email")
            if primary.phone:
                channels.append("sms")
        except Exception:
            logger.exception("welcome_pack_notification_failed")

        app.welcome_pack_sent = True
        await self.db.flush()
        await self.db.refresh(app)

        logger.info(
            "welcome_pack_sent",
            application_id=str(application_id),
            channels=channels,
        )
        return app, channels

    # ---- Modified enroll() -- add checklist and deposit guards ----

    # ADD these checks at the beginning of the existing enroll() method,
    # AFTER the idempotency check and status validation (after line ~87),
    # BEFORE step 2 (class determination):

    """
    # --- Phase 3 guards: checklist completion + deposit requirement ---
    # These checks are backward-compatible: if no checklist exists or no
    # deposit is required, the existing flow proceeds unchanged.

    # Check enrollment checklist (if one exists for this application)
    checklist_result = await self.db.execute(
        select(EnrollmentChecklist)
        .options(selectinload(EnrollmentChecklist.items))
        .filter(
            EnrollmentChecklist.tenant_id == tenant_id,
            EnrollmentChecklist.application_id == application_id,
            EnrollmentChecklist.deleted_at.is_(None),
        )
    )
    checklist = checklist_result.scalar_one_or_none()
    if checklist:
        # Only block if there are incomplete REQUIRED items
        incomplete_required = [
            i for i in checklist.items
            if i.is_required and not i.is_completed and i.deleted_at is None
        ]
        if incomplete_required:
            item_names = [i.item_name for i in incomplete_required[:5]]
            raise EnrollmentError(
                f"Enrollment checklist has {len(incomplete_required)} incomplete required "
                f"item(s): {', '.join(item_names)}",
                code="CHECKLIST_INCOMPLETE",
            )

    # Check enrollment deposit (if required by the admission period)
    from app.models.admissions import AdmissionPeriod
    period_result = await self.db.execute(
        select(AdmissionPeriod).filter(
            AdmissionPeriod.id == app.admission_period_id,
            AdmissionPeriod.tenant_id == tenant_id,
        )
    )
    period = period_result.scalar_one_or_none()
    if period and period.enrollment_deposit_required and not app.enrollment_deposit_paid:
        raise EnrollmentError(
            "Enrollment deposit is required but has not been recorded",
            code="DEPOSIT_REQUIRED",
        )
    """

    # ALSO: After step 8 (status history), add automatic confirmation + welcome pack:
    """
    # --- Phase 3: Post-enrollment automation ---
    # Generate confirmation PDF and send welcome pack (best effort)
    try:
        confirmation_url = await self.generate_enrollment_confirmation(
            tenant_id, application_id
        )
    except Exception:
        logger.warning("enrollment_confirmation_generation_failed", application_id=str(application_id))

    try:
        await self.send_welcome_pack(tenant_id, application_id)
    except Exception:
        logger.warning("enrollment_welcome_pack_failed", application_id=str(application_id))
    """
```

### 4.2 New File: `backend/app/services/admissions/cssps_service.py`

```python
"""
SIMS Plus - CSSPS Import Service

Parses CSSPS (Computerised School Selection and Placement System) placement
files and imports them as applications. CSSPS places JHS graduates into SHS.

The parser supports:
- CSV files with configurable column mapping
- Excel (.xlsx) files with configurable column mapping
- Deduplication by BECE index_number within the same admission period
- Programme-to-class mapping (admin maps programme names to class UUIDs)
- Preview mode (parse without DB writes)

See 00-overview.md Section 5 for the CSSPS file format definition.
"""

import csv
import io
import secrets
import uuid
from datetime import date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    AdmissionApplicationStatus,
    Application,
    ApplicationGuardian,
    ApplicationStatusHistory,
)

logger = structlog.get_logger(__name__)


class CSSPSImportError(Exception):
    def __init__(self, message: str, code: str = "CSSPS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class CSSPSImportService:
    MAX_CSSPS_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_IMPORT_ROWS = 1000

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- File Parsing ---

    def parse_file(
        self,
        file_bytes: bytes,
        file_type: str,
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """
        Parse a CSV or Excel file into a list of standardized record dicts.

        column_mapping maps our standard field names to the actual file column headers.
        Only mapped columns are extracted; unmapped fields default to None.

        Returns a list of dicts with standardized field names.
        """
        # Enforce file size limit at the service layer (defense-in-depth)
        if len(file_bytes) > self.MAX_CSSPS_FILE_SIZE:
            raise CSSPSImportError("File too large. Maximum 5MB.", "FILE_TOO_LARGE")

        if file_type in ("text/csv", "application/csv", ".csv"):
            return self._parse_csv(file_bytes, column_mapping)
        elif file_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        ):
            return self._parse_excel(file_bytes, column_mapping)
        else:
            raise CSSPSImportError(
                f"Unsupported file type: {file_type}. Use CSV or Excel (.xlsx)",
                code="UNSUPPORTED_FILE_TYPE",
            )

    def _parse_csv(
        self,
        file_bytes: bytes,
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """Parse CSV with configurable column mapping."""
        # Try UTF-8 first, fall back to latin-1 for legacy files
        try:
            text = file_bytes.decode("utf-8-sig")  # utf-8-sig strips BOM
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        return self._map_rows(list(reader), column_mapping)

    def _parse_excel(
        self,
        file_bytes: bytes,
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """Parse Excel (.xlsx) with configurable column mapping."""
        try:
            import openpyxl
        except ImportError:
            raise CSSPSImportError(
                "openpyxl is required for Excel import",
                code="MISSING_DEPENDENCY",
            )

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            raise CSSPSImportError("Excel file has no active worksheet", code="EMPTY_FILE")

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            raise CSSPSImportError("File has no data rows", code="EMPTY_FILE")

        # First row is headers
        headers = [str(h).strip() if h else "" for h in rows[0]]
        data_rows = []
        for row in rows[1:]:
            if all(cell is None for cell in row):
                continue  # Skip empty rows
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = str(row[i]).strip() if row[i] is not None else None
            data_rows.append(row_dict)

        wb.close()
        return self._map_rows(data_rows, column_mapping)

    def _map_rows(
        self,
        rows: list[dict],
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """Map file columns to standard field names using the provided mapping."""
        # Invert: standard_field -> file_column_header
        mapped = []
        for row_num, row in enumerate(rows, start=1):
            record: dict = {"_row_number": row_num}
            for standard_field, file_column in column_mapping.items():
                if file_column is None:
                    record[standard_field] = None
                else:
                    # Case-insensitive column lookup
                    value = None
                    for key, val in row.items():
                        if key and key.strip().lower() == file_column.strip().lower():
                            value = val
                            break
                    record[standard_field] = value.strip() if value else None
            mapped.append(record)
        return mapped

    # --- Preview (no DB writes) ---

    async def preview_import(
        self,
        tenant_id: uuid.UUID,
        file_bytes: bytes,
        file_type: str,
        column_mapping: dict[str, str | None],
    ) -> dict:
        """
        Parse file and return preview data without writing to the database.

        Returns:
        {
            total_rows: int,
            valid_rows: int,
            error_rows: int,
            detected_columns: list[str],
            rows: list[dict]  # Each row has parsed fields + errors list
        }
        """
        records = self.parse_file(file_bytes, file_type, column_mapping)

        preview_rows = []
        valid_count = 0
        error_count = 0

        for record in records:
            errors = self._validate_record(record)
            row_data = {
                "row_number": record.get("_row_number", 0),
                "index_number": record.get("index_number"),
                "first_name": record.get("first_name"),
                "last_name": record.get("last_name"),
                "other_names": record.get("other_names"),
                "gender": record.get("gender"),
                "date_of_birth": record.get("date_of_birth"),
                "programme": record.get("programme"),
                "aggregate": self._safe_int(record.get("aggregate")),
                "jhs_school": record.get("jhs_school"),
                "parent_name": record.get("parent_name"),
                "parent_phone": record.get("parent_phone"),
                "residential_status": record.get("residential_status"),
                "house": record.get("house"),
                "errors": errors,
            }
            preview_rows.append(row_data)
            if errors:
                error_count += 1
            else:
                valid_count += 1

        # Detect columns from the raw file for the mapping UI
        raw_records = self.parse_file(file_bytes, file_type, {
            k: k for k in column_mapping
        })
        detected_columns: list[str] = []
        if raw_records:
            detected_columns = [
                k for k in raw_records[0].keys()
                if k != "_row_number"
            ]

        return {
            "total_rows": len(records),
            "valid_rows": valid_count,
            "error_rows": error_count,
            "detected_columns": detected_columns,
            "rows": preview_rows,
        }

    # --- Import (creates Application records) ---

    async def import_placements(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID,
        *,
        file_bytes: bytes,
        file_type: str,
        column_mapping: dict[str, str | None],
        programme_to_class_mapping: dict[str, uuid.UUID],
    ) -> dict:
        """
        Import CSSPS placement data as application records.

        For each valid row:
        1. Check dedup by index_number within the same admission period
        2. Map programme to target_class_id via programme_to_class_mapping
        3. Create Application (status=submitted, custom_fields.cssps=true)
        4. Create ApplicationGuardian if parent_name/phone present
        5. Set boarding_status from residential_status

        Returns:
        {
            total_rows: int,
            imported: int,
            skipped: int,
            errors: int,
            results: list[dict]
        }
        """
        records = self.parse_file(file_bytes, file_type, column_mapping)

        # Enforce row cap to prevent resource exhaustion
        if len(records) > self.MAX_IMPORT_ROWS:
            raise CSSPSImportError(
                f"File contains {len(records)} rows. Maximum {self.MAX_IMPORT_ROWS}. "
                "Split the file into smaller batches.",
                "TOO_MANY_ROWS",
            )

        # Pre-load existing index_numbers for this period to check duplicates
        existing_result = await self.db.execute(
            select(Application.custom_fields).filter(
                Application.tenant_id == tenant_id,
                Application.admission_period_id == period_id,
                Application.deleted_at.is_(None),
            )
        )
        existing_index_numbers: set[str] = set()
        for (custom_fields,) in existing_result.all():
            if isinstance(custom_fields, dict) and custom_fields.get("index_number"):
                existing_index_numbers.add(str(custom_fields["index_number"]))

        results: list[dict] = []
        imported = 0
        skipped = 0
        errors = 0

        for record in records:
            row_num = record.get("_row_number", 0)
            index_number = record.get("index_number", "")

            # Validate required fields
            validation_errors = self._validate_record(record)
            if validation_errors:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number or "",
                    "status": "error",
                    "application_id": None,
                    "error": "; ".join(validation_errors),
                })
                errors += 1
                continue

            # Dedup check by index_number within same period
            if index_number in existing_index_numbers:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "skipped",
                    "application_id": None,
                    "error": "Duplicate index number in this period",
                })
                skipped += 1
                continue

            # Map programme to class
            programme = record.get("programme", "")
            target_class_id = programme_to_class_mapping.get(programme)
            if not target_class_id:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "error",
                    "application_id": None,
                    "error": f"No class mapping for programme: {programme}",
                })
                errors += 1
                continue

            # Parse date of birth
            dob = self._parse_date(record.get("date_of_birth"))

            # Normalize gender
            gender = self._normalize_gender(record.get("gender"))

            # Parse aggregate
            aggregate = self._safe_int(record.get("aggregate"))

            # Determine boarding status
            residential = record.get("residential_status", "")
            boarding_status = None
            if residential:
                boarding_status = "boarding" if residential.lower() in ("boarding", "b") else "day"

            # Build custom_fields with CSSPS metadata
            custom_fields = {
                "cssps": True,
                "index_number": index_number,
                "aggregate": aggregate,
                "jhs_school": record.get("jhs_school"),
                "jhs_district": record.get("jhs_district"),
                "region": record.get("region"),
                "programme": programme,
                "house": record.get("house"),
            }

            try:
                # Create application
                application = Application(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    admission_period_id=period_id,
                    tracking_code=secrets.token_urlsafe(48),
                    applicant_first_name=record["first_name"],
                    applicant_last_name=record["last_name"],
                    applicant_other_names=record.get("other_names"),
                    date_of_birth=dob,
                    gender=gender,
                    target_class_id=target_class_id,
                    status=AdmissionApplicationStatus.SUBMITTED.value,
                    custom_fields=custom_fields,
                    boarding_status=boarding_status,
                )
                self.db.add(application)
                await self.db.flush()

                # Create guardian if parent info present
                parent_name = record.get("parent_name")
                parent_phone = record.get("parent_phone")
                if parent_name:
                    # Split name into first/last (best effort)
                    parts = parent_name.strip().split(" ", 1)
                    guardian = ApplicationGuardian(
                        tenant_id=tenant_id,
                        application_id=application.id,
                        first_name=parts[0],
                        last_name=parts[-1] if len(parts) > 1 else parts[0],
                        phone=parent_phone or "",
                        relationship="parent",
                        is_primary=True,
                    )
                    self.db.add(guardian)

                # Create status history entry
                history = ApplicationStatusHistory(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    from_status=None,
                    to_status=AdmissionApplicationStatus.SUBMITTED.value,
                    reason="Imported from CSSPS placement data",
                )
                self.db.add(history)

                await self.db.flush()

                # Track for dedup within this batch
                existing_index_numbers.add(index_number)

                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "imported",
                    "application_id": str(application.id),
                    "error": None,
                })
                imported += 1

            except Exception as e:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "error",
                    "application_id": None,
                    "error": "Import failed for this row",
                })
                errors += 1
                # Log actual error but don't expose to client
                logger.error(
                    "cssps_row_import_failed",
                    row_number=row_num,
                    index_number=index_number,
                    error=str(e),
                )

        logger.info(
            "cssps_import_completed",
            total=len(records),
            imported=imported,
            skipped=skipped,
            errors=errors,
        )

        return {
            "total_rows": len(records),
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "results": results,
        }

    # --- Validation Helpers ---

    def _validate_record(self, record: dict) -> list[str]:
        """Validate a parsed record. Returns list of error messages (empty = valid)."""
        errors = []
        if not record.get("index_number"):
            errors.append("Missing index_number")
        if not record.get("first_name"):
            errors.append("Missing first_name")
        if not record.get("last_name"):
            errors.append("Missing last_name")
        if not record.get("gender"):
            errors.append("Missing gender")
        if not record.get("programme"):
            errors.append("Missing programme")
        return errors

    def _normalize_gender(self, value: str | None) -> str | None:
        """Normalize gender values: M/m/Male -> male, F/f/Female -> female."""
        if not value:
            return None
        v = value.strip().lower()
        if v in ("m", "male"):
            return "male"
        if v in ("f", "female"):
            return "female"
        return value.lower()

    def _parse_date(self, value: str | None) -> date | None:
        """Parse date in DD/MM/YYYY format (Ghana standard)."""
        if not value:
            return None
        try:
            # Try DD/MM/YYYY first (Ghana format)
            parts = value.strip().split("/")
            if len(parts) == 3:
                return date(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            pass
        try:
            # Fall back to ISO format YYYY-MM-DD
            return date.fromisoformat(value.strip())
        except ValueError:
            return None

    def _safe_int(self, value: str | None) -> int | None:
        """Safely convert to int, returning None on failure."""
        if not value:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
```

### 4.3 Update `backend/app/services/admissions/__init__.py`

Add:
```python
from app.services.admissions.cssps_service import (
    CSSPSImportService,
    CSSPSImportError,
)
```

---

## 5. Endpoints

### 5.1 New File: `backend/app/api/v1/endpoints/admissions/enrollment_checklist.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/applications/{id}/checklist` | Create checklist from template | admissions.update | - | ChecklistResponse (201) |
| GET | `/admissions/applications/{id}/checklist` | Get checklist with items | admissions.read | - | ChecklistResponse |
| PATCH | `/admissions/checklist-items/{id}/complete` | Complete a checklist item | admissions.update | ChecklistItemComplete | ChecklistItemResponse |
| POST | `/admissions/applications/{id}/enrollment-deposit` | Record deposit payment | admissions.update | EnrollmentDepositRecord | EnrollmentDepositResponse (201) |
| PATCH | `/admissions/applications/{id}/boarding-status` | Assign boarding/day status | admissions.update | BoardingStatusAssign | BoardingStatusResponse |
| POST | `/admissions/applications/{id}/confirmation-letter` | Generate confirmation PDF | admissions.update | - | ConfirmationLetterResponse (201) |
| POST | `/admissions/applications/{id}/welcome-pack` | Send welcome info | admissions.update | - | WelcomePackResponse (201) |

**Endpoint implementation pattern** (follows existing enrollment.py pattern):

```python
"""
SIMS Plus - Enrollment Checklist & Confirmation Endpoints

Manages enrollment checklists, deposits, boarding status,
confirmation letters, and welcome pack delivery.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.enrollment_checklist import (
    BoardingStatusAssign,
    BoardingStatusResponse,
    ChecklistItemComplete,
    ChecklistItemResponse,
    ChecklistResponse,
    ConfirmationLetterResponse,
    EnrollmentDepositRecord,
    EnrollmentDepositResponse,
    WelcomePackResponse,
)
from app.services.admissions import EnrollmentError, EnrollmentService

logger = structlog.get_logger(__name__)

router = APIRouter()


def _handle_error(e: EnrollmentError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_STATUS": 422,
        "CHECKLIST_EXISTS": 409,
        "ALREADY_COMPLETED": 409,
        "DEPOSIT_ALREADY_PAID": 409,
        "INVALID_BOARDING_STATUS": 422,
        "SCHOOL_NOT_FOUND": 404,
        "ALREADY_SENT": 409,
        "NO_GUARDIAN": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


def _build_checklist_response(checklist, items=None) -> ChecklistResponse:
    """Build ChecklistResponse with computed progress fields."""
    active_items = items or []
    if hasattr(checklist, "items") and not items:
        active_items = [i for i in checklist.items if i.deleted_at is None]

    total = len(active_items)
    completed = sum(1 for i in active_items if i.is_completed)
    required = sum(1 for i in active_items if i.is_required)
    required_completed = sum(1 for i in active_items if i.is_required and i.is_completed)
    progress_pct = (required_completed / required * 100) if required > 0 else 100.0

    return ChecklistResponse(
        id=checklist.id,
        school_id=checklist.school_id,
        application_id=checklist.application_id,
        checklist_type=checklist.checklist_type,
        completed_at=checklist.completed_at,
        completed_by=checklist.completed_by,
        total_items=total,
        completed_items=completed,
        required_items=required,
        required_completed=required_completed,
        progress_pct=round(progress_pct, 1),
        items=[ChecklistItemResponse.model_validate(i) for i in active_items],
        created_at=checklist.created_at,
        updated_at=checklist.updated_at,
    )


@router.post(
    "/applications/{application_id}/checklist",
    response_model=ChecklistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create enrollment checklist",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def create_checklist(
    application_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChecklistResponse:
    """
    Create an enrollment checklist for an accepted application.

    Auto-populates items from the admission period's enrollment_checklist_template.
    If the application has boarding_status='boarding', additional boarding items
    are appended and checklist_type is set to 'boarding'.

    Only one checklist per application is allowed.
    """
    try:
        svc = EnrollmentService(db)
        checklist = await svc.create_enrollment_checklist(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            application_id=application_id,
        )
        # Reload with items
        checklist = await svc.get_checklist(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        return _build_checklist_response(checklist)
    except EnrollmentError as e:
        raise _handle_error(e)


@router.get(
    "/applications/{application_id}/checklist",
    response_model=ChecklistResponse,
    summary="Get enrollment checklist",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_checklist(
    application_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChecklistResponse:
    try:
        svc = EnrollmentService(db)
        checklist = await svc.get_checklist(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        return _build_checklist_response(checklist)
    except EnrollmentError as e:
        raise _handle_error(e)


@router.patch(
    "/checklist-items/{item_id}/complete",
    response_model=ChecklistItemResponse,
    summary="Complete checklist item",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def complete_checklist_item(
    item_id: UUID,
    data: ChecklistItemComplete,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ChecklistItemResponse:
    """
    Mark a checklist item as completed.

    If this completes all required items, the parent checklist is
    automatically marked as completed.
    """
    try:
        svc = EnrollmentService(db)
        item = await svc.complete_checklist_item(
            tenant_id=UUID(user["tenant_id"]),
            item_id=item_id,
            user_id=UUID(user["user_id"]),
            notes=data.notes,
            metadata=data.metadata,
        )
        return ChecklistItemResponse.model_validate(item)
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/enrollment-deposit",
    response_model=EnrollmentDepositResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record enrollment deposit",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def record_deposit(
    application_id: UUID,
    data: EnrollmentDepositRecord,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EnrollmentDepositResponse:
    """
    Record an enrollment deposit payment (manual entry by admin).

    If a checklist exists with a deposit payment item, that item is
    auto-completed.
    """
    try:
        svc = EnrollmentService(db)
        app = await svc.record_enrollment_deposit(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            amount=data.amount,
            reference=data.reference,
        )
        return EnrollmentDepositResponse(
            application_id=app.id,
            enrollment_deposit_paid=app.enrollment_deposit_paid,
            enrollment_deposit_amount=app.enrollment_deposit_amount,
            enrollment_deposit_reference=app.enrollment_deposit_reference,
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.patch(
    "/applications/{application_id}/boarding-status",
    response_model=BoardingStatusResponse,
    summary="Assign boarding status",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def assign_boarding_status(
    application_id: UUID,
    data: BoardingStatusAssign,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingStatusResponse:
    """
    Assign boarding or day status to an application.

    If status is 'boarding' and a checklist exists, boarding-specific items
    are added automatically.
    """
    try:
        svc = EnrollmentService(db)
        app, items_added = await svc.assign_boarding_status(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
            status=data.boarding_status.value,
        )
        return BoardingStatusResponse(
            application_id=app.id,
            boarding_status=app.boarding_status,
            boarding_items_added=items_added,
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/confirmation-letter",
    response_model=ConfirmationLetterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate confirmation letter",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def generate_confirmation(
    application_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ConfirmationLetterResponse:
    """
    Generate an enrollment confirmation letter PDF and upload to S3.

    Returns the S3 URL for the generated document.
    """
    try:
        svc = EnrollmentService(db)
        url = await svc.generate_enrollment_confirmation(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        app = await svc._get_application(UUID(user["tenant_id"]), application_id)
        return ConfirmationLetterResponse(
            application_id=application_id,
            confirmation_url=url,
            applicant_name=f"{app.applicant_first_name} {app.applicant_last_name}",
        )
    except EnrollmentError as e:
        raise _handle_error(e)


@router.post(
    "/applications/{application_id}/welcome-pack",
    response_model=WelcomePackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send welcome pack",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def send_welcome_pack(
    application_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> WelcomePackResponse:
    """
    Send welcome pack / orientation information via email and SMS.

    Can only be sent once per application.
    """
    try:
        svc = EnrollmentService(db)
        app, channels = await svc.send_welcome_pack(
            tenant_id=UUID(user["tenant_id"]),
            application_id=application_id,
        )
        return WelcomePackResponse(
            application_id=app.id,
            welcome_pack_sent=app.welcome_pack_sent,
            channels=channels,
        )
    except EnrollmentError as e:
        raise _handle_error(e)
```

### 5.2 New File: `backend/app/api/v1/endpoints/admissions/cssps.py`

| Method | Path | Purpose | Permission | Request Body | Response |
|--------|------|---------|------------|-------------|----------|
| POST | `/admissions/cssps/preview` | Preview parsed file | admissions.create | Form: file + CSSPSPreviewRequest | CSSPSPreviewResponse |
| POST | `/admissions/cssps/import` | Import placements | admissions.create | Form: file + CSSPSImportRequest | CSSPSImportResponse |

**Rate limit: 5/hour (bulk operations category).** Both CSSPS endpoints are bulk operations and should be rate-limited accordingly.

```python
"""
SIMS Plus - CSSPS Placement Import Endpoints

Import CSSPS (Computerised School Selection and Placement System) data
for SHS student placement. Supports CSV and Excel files with configurable
column mapping.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.cssps import (
    CSSPSImportRequest,
    CSSPSImportResponse,
    CSSPSPreviewRequest,
    CSSPSPreviewResponse,
)
from app.services.admissions.cssps_service import CSSPSImportError, CSSPSImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/cssps")

# Maximum file size: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024


def _handle_error(e: CSSPSImportError) -> HTTPException:
    status_map = {
        "UNSUPPORTED_FILE_TYPE": 422,
        "EMPTY_FILE": 422,
        "FILE_TOO_LARGE": 413,
        "TOO_MANY_ROWS": 422,
        "MISSING_DEPENDENCY": 500,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "/preview",
    response_model=CSSPSPreviewResponse,
    summary="Preview CSSPS file",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def preview_cssps(
    file: UploadFile = File(...),
    column_mapping: str = Form("{}"),
    user: ValidatedUser = Depends(),
    db: DatabaseSession = Depends(),
) -> CSSPSPreviewResponse:
    """
    Parse and preview a CSSPS placement file without creating any records.

    Upload a CSV or Excel file. Optionally provide column_mapping as a JSON
    string to map file columns to standard CSSPS fields. Returns parsed rows
    with validation errors.
    """
    import json

    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5MB limit",
        )

    # Parse column mapping from form data
    try:
        mapping_dict = json.loads(column_mapping) if column_mapping != "{}" else {}
        preview_req = CSSPSPreviewRequest(
            column_mapping=mapping_dict if mapping_dict else CSSPSPreviewRequest().column_mapping,
        )
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid column_mapping JSON: {str(e)}",
        )

    try:
        svc = CSSPSImportService(db)
        # Determine file type from content type or filename
        file_type = file.content_type or ""
        if file.filename and file.filename.endswith(".csv"):
            file_type = ".csv"
        elif file.filename and file.filename.endswith(".xlsx"):
            file_type = ".xlsx"

        result = await svc.preview_import(
            tenant_id=UUID(user["tenant_id"]),
            file_bytes=file_bytes,
            file_type=file_type,
            column_mapping=preview_req.column_mapping.model_dump(exclude_none=True),
        )
        return CSSPSPreviewResponse(**result)
    except CSSPSImportError as e:
        raise _handle_error(e)


@router.post(
    "/import",
    response_model=CSSPSImportResponse,
    summary="Import CSSPS placements",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def import_cssps(
    file: UploadFile = File(...),
    import_config: str = Form(...),
    school: SchoolCtx = Depends(),
    user: ValidatedUser = Depends(),
    db: DatabaseSession = Depends(),
) -> CSSPSImportResponse:
    """
    Import CSSPS placement data as application records.

    Upload a CSV or Excel file with import_config as a JSON string containing:
    - admission_period_id: UUID of the target admission period
    - column_mapping: maps file column headers to standard fields
    - programme_to_class_mapping: maps programme names to class UUIDs

    Deduplication: rows with index_numbers already present in the same
    admission period are skipped.
    """
    import json

    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5MB limit",
        )

    # Parse import config from form data
    try:
        config = json.loads(import_config)
        import_req = CSSPSImportRequest(**config)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid import_config JSON: {str(e)}",
        )

    try:
        svc = CSSPSImportService(db)
        file_type = file.content_type or ""
        if file.filename and file.filename.endswith(".csv"):
            file_type = ".csv"
        elif file.filename and file.filename.endswith(".xlsx"):
            file_type = ".xlsx"

        result = await svc.import_placements(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=import_req.admission_period_id,
            file_bytes=file_bytes,
            file_type=file_type,
            column_mapping=import_req.column_mapping.model_dump(exclude_none=True),
            programme_to_class_mapping={
                k: v for k, v in import_req.programme_to_class_mapping.items()
            },
        )
        return CSSPSImportResponse(**result)
    except CSSPSImportError as e:
        raise _handle_error(e)
```

### 5.3 Update `backend/app/api/v1/endpoints/admissions/__init__.py`

Add to the router registration:

```python
from .enrollment_checklist import router as enrollment_checklist_router
from .cssps import router as cssps_router

# In the router.include_router() section:
router.include_router(enrollment_checklist_router, tags=["Enrollment Checklist"])
router.include_router(cssps_router, tags=["CSSPS Import"])
```

---

## 6. PDF Template

### 6.1 New File: `backend/app/templates/admissions/enrollment_confirmation.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #1a1a1a;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid {{ school.primary_color or '#1a56db' }};
            padding-bottom: 20px;
        }
        .header img {
            max-height: 80px;
            margin-bottom: 10px;
        }
        .header h1 {
            font-size: 18pt;
            margin: 5px 0;
            color: {{ school.primary_color or '#1a56db' }};
        }
        .header p {
            font-size: 10pt;
            color: #666;
            margin: 2px 0;
        }
        .title {
            text-align: center;
            font-size: 16pt;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 30px 0 20px;
            color: {{ school.primary_color or '#1a56db' }};
        }
        .date-ref {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            font-size: 10pt;
            color: #666;
        }
        .details-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .details-table td {
            padding: 8px 12px;
            border: 1px solid #e5e7eb;
        }
        .details-table td:first-child {
            font-weight: 600;
            background-color: #f9fafb;
            width: 40%;
        }
        .section-title {
            font-size: 13pt;
            font-weight: 600;
            margin: 25px 0 10px;
            color: {{ school.primary_color or '#1a56db' }};
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 5px;
        }
        .checklist-item {
            padding: 4px 0;
            font-size: 11pt;
        }
        .checklist-item .status {
            display: inline-block;
            width: 16px;
            text-align: center;
            margin-right: 8px;
        }
        .checklist-item .completed { color: #059669; }
        .checklist-item .pending { color: #dc2626; }
        .next-steps {
            background-color: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 4px;
            padding: 15px;
            margin: 20px 0;
        }
        .next-steps h3 {
            margin: 0 0 10px;
            color: #166534;
        }
        .next-steps li {
            margin: 5px 0;
            font-size: 11pt;
        }
        .footer {
            margin-top: 40px;
            padding-top: 15px;
            border-top: 1px solid #e5e7eb;
            font-size: 9pt;
            color: #9ca3af;
            text-align: center;
        }
        .signature {
            margin-top: 50px;
        }
        .signature-line {
            border-top: 1px solid #333;
            width: 200px;
            margin-top: 40px;
            padding-top: 5px;
            font-size: 10pt;
        }
    </style>
</head>
<body>
    <div class="header">
        {% if school.logo_url %}
        <img src="{{ school.logo_url }}" alt="{{ school.name }} logo">
        {% endif %}
        <h1>{{ school.name }}</h1>
        {% if school.address %}
        <p>{{ school.address }}</p>
        {% endif %}
        {% if school.phone %}
        <p>Tel: {{ school.phone }}</p>
        {% endif %}
    </div>

    <div class="title">Enrollment Confirmation</div>

    <div class="date-ref">
        <span>Date: {{ generated_date.strftime('%d/%m/%Y') }}</span>
        <span>Ref: {{ tracking_code[:16] }}</span>
    </div>

    <p>Dear Parent/Guardian,</p>

    <p>
        We are pleased to confirm the enrollment of <strong>{{ applicant_name }}</strong>
        at {{ school.name }}. Please find the enrollment details below.
    </p>

    <div class="section-title">Student Details</div>
    <table class="details-table">
        <tr>
            <td>Full Name</td>
            <td>{{ applicant_first_name }} {{ applicant_last_name }}</td>
        </tr>
        {% if date_of_birth %}
        <tr>
            <td>Date of Birth</td>
            <td>{{ date_of_birth.strftime('%d/%m/%Y') }}</td>
        </tr>
        {% endif %}
        {% if gender %}
        <tr>
            <td>Gender</td>
            <td>{{ gender|capitalize }}</td>
        </tr>
        {% endif %}
        <tr>
            <td>Assigned Class</td>
            <td>{{ class_name }}</td>
        </tr>
        {% if boarding_status %}
        <tr>
            <td>Residential Status</td>
            <td>{{ boarding_status|capitalize }}</td>
        </tr>
        {% endif %}
        {% if deposit_paid %}
        <tr>
            <td>Enrollment Deposit</td>
            <td>GHS {{ "%.2f"|format(deposit_amount) }} (Paid)</td>
        </tr>
        {% endif %}
    </table>

    {% if checklist %}
    <div class="section-title">Enrollment Checklist</div>
    {% for item in checklist.items %}
    <div class="checklist-item">
        <span class="status {{ 'completed' if item.completed else 'pending' }}">
            {{ '&#10003;' if item.completed else '&#10007;' }}
        </span>
        {{ item.name }}
        {% if item.required %}<em>(required)</em>{% endif %}
    </div>
    {% endfor %}
    <p style="font-size: 10pt; color: #666; margin-top: 10px;">
        {{ checklist.completed }}/{{ checklist.total }} items completed
    </p>
    {% endif %}

    <div class="next-steps">
        <h3>Next Steps</h3>
        <ol>
            <li>Complete all required checklist items (if any remain)</li>
            <li>Attend the orientation session (details will be communicated separately)</li>
            <li>Ensure all fees are settled before the start of term</li>
            {% if boarding_status == 'boarding' %}
            <li>Submit dormitory preference form and boarding medical clearance</li>
            {% endif %}
            <li>Report to school on the designated resumption date</li>
        </ol>
    </div>

    <div class="signature">
        <p>Congratulations on your enrollment. We look forward to welcoming
        {{ applicant_first_name }} to our school community.</p>

        <div class="signature-line">
            Head of Admissions<br>
            {{ school.name }}
        </div>
    </div>

    <div class="footer">
        This is a computer-generated document. No signature is required.<br>
        Generated on {{ generated_date.strftime('%d/%m/%Y at %H:%M UTC') }}
    </div>
</body>
</html>
```

---

## 7. Frontend

### 7.1 Types: `frontend/types/enrollment-checklist.type.ts`

Define TypeScript types matching the Pydantic schemas:

- `ChecklistItemType` -- "document" | "payment" | "form" | "boarding" | "medical"
- `BoardingStatus` -- "boarding" | "day"
- `ChecklistItem` -- id, checklist_id, item_type, item_name, description, is_required, is_completed, completed_at, completed_by, completed_by_name, notes, metadata, created_at
- `EnrollmentChecklist` -- id, school_id, application_id, checklist_type, completed_at, completed_by, completed_by_name, total_items, completed_items, required_items, required_completed, progress_pct, items, created_at, updated_at
- `EnrollmentDepositRecord` -- amount, reference
- `EnrollmentDepositResponse` -- application_id, enrollment_deposit_paid, enrollment_deposit_amount, enrollment_deposit_reference
- `BoardingStatusAssign` -- boarding_status
- `BoardingStatusResponse` -- application_id, boarding_status, boarding_items_added
- `ConfirmationLetterResponse` -- application_id, confirmation_url, applicant_name
- `WelcomePackResponse` -- application_id, welcome_pack_sent, channels
- `CSSPSColumnMapping` -- field-to-header mapping (all string keys)
- `CSSPSPreviewRow` -- row_number, index_number, first_name, last_name, ..., errors
- `CSSPSPreviewResponse` -- total_rows, valid_rows, error_rows, detected_columns, rows
- `CSSPSImportRequest` -- admission_period_id, column_mapping, programme_to_class_mapping
- `CSSPSImportResult` -- row_number, index_number, status, application_id, error
- `CSSPSImportResponse` -- total_rows, imported, skipped, errors, results

### 7.2 Server Actions: Added to `frontend/actions/admissions.action.ts`

Follow the existing pattern in `admissions.action.ts`:

- `createEnrollmentChecklist(applicationId)` -- POST `/admissions/applications/{id}/checklist`
- `getEnrollmentChecklist(applicationId)` -- GET `/admissions/applications/{id}/checklist`
- `completeChecklistItem(itemId, data)` -- PATCH `/admissions/checklist-items/{id}/complete`
- `recordEnrollmentDeposit(applicationId, data)` -- POST `/admissions/applications/{id}/enrollment-deposit`
- `assignBoardingStatus(applicationId, data)` -- PATCH `/admissions/applications/{id}/boarding-status`
- `generateConfirmationLetter(applicationId)` -- POST `/admissions/applications/{id}/confirmation-letter`
- `sendWelcomePack(applicationId)` -- POST `/admissions/applications/{id}/welcome-pack`
- `previewCSSPS(file, columnMapping?)` -- POST `/admissions/cssps/preview` (FormData)
- `importCSSPS(file, config)` -- POST `/admissions/cssps/import` (FormData)

### 7.3 Pages

**`/admissions/applications/[id]/enrollment/page.tsx`** -- Enrollment confirmation page with:
- Header: applicant name, status badge, boarding status badge
- Enrollment checklist card with progress bar and grouped items
- Deposit payment recording form (amount + reference input)
- Boarding status selector (radio: Boarding / Day)
- Actions: Create Checklist, Generate Confirmation Letter, Send Welcome Pack
- Download link for confirmation PDF (when generated)

**`/admissions/cssps/page.tsx`** -- CSSPS import page with:
- Step 1: File upload (drag-and-drop zone, accepts .csv and .xlsx)
- Step 2: Column mapping (side-by-side: detected columns -> standard fields, dropdown selectors)
- Step 3: Programme-to-class mapping (detected programmes -> class dropdown selectors)
- Step 4: Preview table with row-level validation errors highlighted
- Step 5: Import confirmation with progress and result summary
- Back/Next navigation between steps

### 7.4 Components

| Component | Props | Description |
|-----------|-------|-------------|
| `enrollment-checklist.tsx` | checklist, onComplete | Grouped checklist items with checkboxes, progress bar |
| `deposit-payment-form.tsx` | onSubmit, depositRequired, depositAmount | Amount + reference input fields |
| `boarding-selector.tsx` | currentStatus, onAssign | Radio group for boarding/day with confirmation |
| `cssps-upload.tsx` | onFileSelected | Drag-and-drop file zone for CSV/Excel |
| `cssps-column-mapper.tsx` | detectedColumns, standardFields, mapping, onChange | Column mapping UI with dropdowns |
| `cssps-programme-mapper.tsx` | programmes, classes, mapping, onChange | Programme-to-class mapping |
| `cssps-preview-table.tsx` | rows | Preview table with error highlighting |
| `cssps-import-summary.tsx` | result | Import result with imported/skipped/error counts |
| `welcome-pack-preview.tsx` | application | Preview of welcome information before sending |

### 7.5 Sidebar Update

No sidebar changes needed -- the enrollment checklist page is accessed from the application detail page. The CSSPS import page is added to the admissions navigation group:

```typescript
{ title: "CSSPS Import", url: "/admissions/cssps", icon: Upload },
```

---

## 8. Migration

### File: `backend/alembic/versions/20260415_0100_enrollment_checklists.py`

```python
"""Enrollment checklists, deposit columns, and CSSPS support.

Revision ID: 20260415_0100
Revises: 20260408_0100
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260415_0100"
down_revision = "20260408_0100"  # Phase 2 migration
branch_labels = None
depends_on = None

# New tables for batch RLS setup
NEW_TABLES = [
    "enrollment_checklists",
    "enrollment_checklist_items",
]


def upgrade() -> None:
    # ========== PHASE 1: Create Enums ==========

    checklist_type = postgresql.ENUM(
        "standard", "boarding",
        name="checklisttype", create_type=False,
    )
    checklist_type.create(op.get_bind(), checkfirst=True)

    checklist_item_type = postgresql.ENUM(
        "document", "payment", "form", "boarding", "medical",
        name="checklistitemtype", create_type=False,
    )
    checklist_item_type.create(op.get_bind(), checkfirst=True)

    boarding_status = postgresql.ENUM(
        "boarding", "day",
        name="boardingstatus", create_type=False,
    )
    boarding_status.create(op.get_bind(), checkfirst=True)

    # ========== PHASE 2: Create Tables ==========

    op.create_table(
        "enrollment_checklists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_type", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "enrollment_checklist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_completed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checklist_id"], ["enrollment_checklists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ========== PHASE 3: Column Additions ==========

    # Applications: enrollment confirmation fields
    op.add_column("applications", sa.Column("enrollment_deposit_paid", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("applications", sa.Column("enrollment_deposit_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("applications", sa.Column("enrollment_deposit_reference", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("boarding_status", sa.String(20), nullable=True))
    op.add_column("applications", sa.Column("enrollment_confirmation_url", sa.String(500), nullable=True))
    op.add_column("applications", sa.Column("welcome_pack_sent", sa.Boolean, nullable=False, server_default=sa.text("false")))

    # Admission periods: enrollment deposit config + checklist template
    op.add_column("admission_periods", sa.Column("enrollment_deposit_required", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("admission_periods", sa.Column("enrollment_deposit_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("admission_periods", sa.Column("enrollment_checklist_template", postgresql.JSONB, nullable=False, server_default="[]"))

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

    # Enrollment checklists
    op.create_index(
        "uq_enrollment_checklist_app",
        "enrollment_checklists",
        ["tenant_id", "application_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_enrollment_checklists_school",
        "enrollment_checklists",
        ["tenant_id", "school_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_enrollment_checklists_incomplete",
        "enrollment_checklists",
        ["tenant_id", "school_id"],
        postgresql_where=sa.text("completed_at IS NULL AND deleted_at IS NULL"),
    )

    # Enrollment checklist items
    op.create_index(
        "ix_checklist_items_checklist",
        "enrollment_checklist_items",
        ["tenant_id", "checklist_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_checklist_items_incomplete",
        "enrollment_checklist_items",
        ["tenant_id", "checklist_id", "is_required"],
        postgresql_where=sa.text("is_completed = false AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_checklist_items_incomplete", table_name="enrollment_checklist_items")
    op.drop_index("ix_checklist_items_checklist", table_name="enrollment_checklist_items")
    op.drop_index("ix_enrollment_checklists_incomplete", table_name="enrollment_checklists")
    op.drop_index("ix_enrollment_checklists_school", table_name="enrollment_checklists")
    op.drop_index("uq_enrollment_checklist_app", table_name="enrollment_checklists")

    # Drop added columns (reverse order)
    op.drop_column("admission_periods", "enrollment_checklist_template")
    op.drop_column("admission_periods", "enrollment_deposit_amount")
    op.drop_column("admission_periods", "enrollment_deposit_required")

    op.drop_column("applications", "welcome_pack_sent")
    op.drop_column("applications", "enrollment_confirmation_url")
    op.drop_column("applications", "boarding_status")
    op.drop_column("applications", "enrollment_deposit_reference")
    op.drop_column("applications", "enrollment_deposit_amount")
    op.drop_column("applications", "enrollment_deposit_paid")

    # Drop tables (child first)
    op.drop_table("enrollment_checklist_items")
    op.drop_table("enrollment_checklists")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS boardingstatus")
    op.execute("DROP TYPE IF EXISTS checklistitemtype")
    op.execute("DROP TYPE IF EXISTS checklisttype")
```

---

## 9. Tests

### 9.1 `backend/tests/test_enrollment_checklist.py` (~12 tests)

Follow the two-engine pattern from `test_admission_applications.py`:

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestEnrollmentChecklist:
    # Creation
    async def test_create_checklist_from_template(self, app_session, prereqs):
        """Verify checklist auto-populates items from period template."""

    async def test_create_checklist_rejects_non_accepted(self, app_session, prereqs):
        """Verify checklist creation fails for non-ACCEPTED applications."""

    async def test_create_checklist_prevents_duplicate(self, app_session, prereqs):
        """Verify only one checklist per application is allowed."""

    async def test_create_checklist_adds_boarding_items(self, app_session, prereqs):
        """Verify boarding items are appended when boarding_status='boarding'."""

    # Item completion
    async def test_complete_checklist_item(self, app_session, prereqs):
        """Verify item is marked completed with timestamp and user."""

    async def test_complete_item_already_completed(self, app_session, prereqs):
        """Verify completing an already-completed item raises ALREADY_COMPLETED."""

    async def test_complete_item_with_metadata(self, app_session, prereqs):
        """Verify metadata is merged into the item on completion."""

    # Auto-completion
    async def test_auto_complete_checklist_all_required_done(self, app_session, prereqs):
        """Verify checklist auto-completes when all required items are done."""

    async def test_auto_complete_ignores_optional_items(self, app_session, prereqs):
        """Verify checklist completes even if optional items remain incomplete."""

    async def test_no_auto_complete_if_required_incomplete(self, app_session, prereqs):
        """Verify checklist stays incomplete if any required item is pending."""

    # Enrollment blocking
    async def test_enrollment_blocked_by_incomplete_checklist(self, app_session, prereqs):
        """Verify enroll() raises CHECKLIST_INCOMPLETE when required items remain."""

    async def test_enrollment_proceeds_without_checklist(self, app_session, prereqs):
        """Verify enroll() works normally when no checklist exists (backward compat)."""
```

### 9.2 `backend/tests/test_enrollment_deposit.py` (~6 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestEnrollmentDeposit:
    async def test_record_deposit(self, app_session, prereqs):
        """Verify deposit fields are set on the application."""

    async def test_record_deposit_rejects_non_accepted(self, app_session, prereqs):
        """Verify deposit recording fails for non-ACCEPTED applications."""

    async def test_record_deposit_prevents_duplicate(self, app_session, prereqs):
        """Verify DEPOSIT_ALREADY_PAID error on second recording."""

    async def test_deposit_auto_completes_checklist_item(self, app_session, prereqs):
        """Verify deposit recording auto-completes the deposit checklist item."""

    async def test_enrollment_blocked_without_required_deposit(self, app_session, prereqs):
        """Verify enroll() raises DEPOSIT_REQUIRED when period requires deposit."""

    async def test_enrollment_proceeds_without_deposit_requirement(self, app_session, prereqs):
        """Verify enroll() works when period has enrollment_deposit_required=false."""
```

### 9.3 `backend/tests/test_enrollment_confirmation.py` (~8 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestEnrollmentConfirmation:
    # Boarding status
    async def test_assign_boarding_status(self, app_session, prereqs):
        """Verify boarding_status is set on application."""

    async def test_assign_boarding_adds_checklist_items(self, app_session, prereqs):
        """Verify boarding items are added to existing checklist."""

    async def test_assign_boarding_invalid_status(self, app_session, prereqs):
        """Verify INVALID_BOARDING_STATUS for values other than boarding/day."""

    # Confirmation PDF
    async def test_generate_confirmation_pdf(self, app_session, prereqs):
        """Verify PDF is generated and URL is stored on application."""

    async def test_generate_confirmation_rejects_draft(self, app_session, prereqs):
        """Verify confirmation fails for non-ACCEPTED/ENROLLED applications."""

    async def test_confirmation_includes_checklist_summary(self, app_session, prereqs):
        """Verify PDF context includes checklist completion data."""

    # Welcome pack
    async def test_send_welcome_pack(self, app_session, prereqs):
        """Verify welcome_pack_sent is set and channels are returned."""

    async def test_send_welcome_pack_prevents_duplicate(self, app_session, prereqs):
        """Verify ALREADY_SENT error on second send attempt."""
```

### 9.4 `backend/tests/test_cssps_import.py` (~12 tests)

```python
@pytest.mark.asyncio
@pytest.mark.xdist_group("admissions")
class TestCSSPSImport:
    # File parsing
    async def test_parse_csv_standard_columns(self, app_session, prereqs):
        """Verify CSV parsing with standard column headers."""

    async def test_parse_csv_custom_column_mapping(self, app_session, prereqs):
        """Verify CSV parsing with custom column mapping."""

    async def test_parse_excel(self, app_session, prereqs):
        """Verify Excel (.xlsx) parsing."""

    async def test_parse_unsupported_file_type(self, app_session, prereqs):
        """Verify UNSUPPORTED_FILE_TYPE error for non-CSV/Excel files."""

    # Preview
    async def test_preview_returns_parsed_rows(self, app_session, prereqs):
        """Verify preview returns total_rows, valid_rows, error_rows without DB writes."""

    async def test_preview_flags_missing_required_fields(self, app_session, prereqs):
        """Verify preview flags rows with missing index_number, first_name, etc."""

    # Import
    async def test_import_creates_applications(self, app_session, prereqs):
        """Verify import creates Application records with correct fields."""

    async def test_import_creates_guardians(self, app_session, prereqs):
        """Verify import creates ApplicationGuardian when parent_name is present."""

    async def test_import_deduplicates_by_index_number(self, app_session, prereqs):
        """Verify duplicate index_numbers within same period are skipped."""

    async def test_import_within_batch_dedup(self, app_session, prereqs):
        """Verify two rows with same index_number in one file: first imported, second skipped."""

    async def test_import_unmapped_programme_error(self, app_session, prereqs):
        """Verify rows with unmapped programme names are reported as errors."""

    async def test_import_sets_cssps_custom_fields(self, app_session, prereqs):
        """Verify custom_fields contains cssps=true, index_number, aggregate, etc."""
```

### 9.5 `backend/tests/test_enrollment_checklist_rls.py` (~4 tests)

```python
@pytest.mark.rls
@pytest.mark.asyncio
@pytest.mark.xdist_group("rls_serial")
class TestEnrollmentChecklistRLS:
    async def test_checklist_tenant_isolation(self, admin_session, app_session):
        """Verify tenant A cannot see tenant B's enrollment checklists."""

    async def test_checklist_item_tenant_isolation(self, admin_session, app_session):
        """Verify tenant A cannot see tenant B's checklist items."""

    async def test_cross_tenant_checklist_invisible(self, admin_session, app_session):
        """Verify SELECT returns 0 rows when querying another tenant's checklists."""

    async def test_cross_tenant_item_update_blocked(self, admin_session, app_session):
        """Verify UPDATE on another tenant's checklist items affects 0 rows."""
```

### 9.6 Update `backend/tests/conftest.py`

Add to TENANT_SCOPED_TABLES:
```python
# Enrollment Checklist (Phase 3)
"enrollment_checklists",
"enrollment_checklist_items",
```

---

## 10. Task Checklist

Developers should complete these tasks in order:

- [ ] **P3-01**: Add enums to `backend/app/models/admissions/enums.py` (ChecklistType, ChecklistItemType, BoardingStatus)
- [ ] **P3-02**: Create `backend/app/models/admissions/enrollment_checklist.py` (EnrollmentChecklist, EnrollmentChecklistItem)
- [ ] **P3-03**: Update `backend/app/models/admissions/__init__.py` (re-exports)
- [ ] **P3-04**: Update `backend/app/db/base.py` (import new models)
- [ ] **P3-05**: Add enrollment confirmation columns to Application model (enrollment_deposit_paid, enrollment_deposit_amount, enrollment_deposit_reference, boarding_status, enrollment_confirmation_url, welcome_pack_sent)
- [ ] **P3-06**: Add enrollment_checklist relationship to Application model
- [ ] **P3-07**: Add enrollment deposit config columns to AdmissionPeriod model (enrollment_deposit_required, enrollment_deposit_amount, enrollment_checklist_template)
- [ ] **P3-08**: Create migration `20260415_0100_enrollment_checklists.py`
- [ ] **P3-09**: Create `backend/app/schemas/enrollment_checklist.py`
- [ ] **P3-10**: Create `backend/app/schemas/cssps.py`
- [ ] **P3-11**: Add enrollment checklist methods to `backend/app/services/admissions/enrollment_service.py` (create_enrollment_checklist, get_checklist, complete_checklist_item, record_enrollment_deposit, assign_boarding_status, generate_enrollment_confirmation, send_welcome_pack)
- [ ] **P3-12**: Add checklist + deposit guards to existing `enroll()` method
- [ ] **P3-13**: Create `backend/app/services/admissions/cssps_service.py`
- [ ] **P3-14**: Update `backend/app/services/admissions/__init__.py` (re-exports)
- [ ] **P3-15**: Create `backend/app/api/v1/endpoints/admissions/enrollment_checklist.py`
- [ ] **P3-16**: Create `backend/app/api/v1/endpoints/admissions/cssps.py`
- [ ] **P3-17**: Update `backend/app/api/v1/endpoints/admissions/__init__.py` (register routers)
- [ ] **P3-18**: Create `backend/app/templates/admissions/enrollment_confirmation.html`
- [ ] **P3-19**: Update `backend/tests/conftest.py` (add 2 tables to TENANT_SCOPED_TABLES)
- [ ] **P3-20**: Write `backend/tests/test_enrollment_checklist.py`
- [ ] **P3-21**: Write `backend/tests/test_enrollment_deposit.py`
- [ ] **P3-22**: Write `backend/tests/test_enrollment_confirmation.py`
- [ ] **P3-23**: Write `backend/tests/test_cssps_import.py`
- [ ] **P3-24**: Write `backend/tests/test_enrollment_checklist_rls.py`
- [ ] **P3-25**: Create `frontend/types/enrollment-checklist.type.ts`
- [ ] **P3-26**: Add enrollment + CSSPS actions to `frontend/actions/admissions.action.ts`
- [ ] **P3-27**: Create enrollment checklist components (enrollment-checklist.tsx, deposit-payment-form.tsx, boarding-selector.tsx, welcome-pack-preview.tsx)
- [ ] **P3-28**: Create CSSPS import components (cssps-upload.tsx, cssps-column-mapper.tsx, cssps-programme-mapper.tsx, cssps-preview-table.tsx, cssps-import-summary.tsx)
- [ ] **P3-29**: Create `/admissions/applications/[id]/enrollment/page.tsx` (enrollment confirmation page)
- [ ] **P3-30**: Create `/admissions/cssps/page.tsx` (CSSPS import wizard)
- [ ] **P3-31**: Update sidebar navigation with CSSPS Import item
- [ ] **P3-32**: Run all tests, verify RLS, verify migration up/down

---

## 11. Operational Updates

### 11.1 `backend/scripts/verify_rls.py`

Add the two new tables to the verification script's table list:

```python
# Enrollment Checklist (Phase 3)
"enrollment_checklists",
"enrollment_checklist_items",
```

### 11.2 `backend/app/tasks/tenant_cleanup.py`

Add the new tables to the tenant cleanup deletion order. Items must be deleted before checklists, and both must be deleted before applications:

```python
# In the ordered deletion list, insert BEFORE "applications":
"enrollment_checklist_items",   # FK -> enrollment_checklists
"enrollment_checklists",        # FK -> applications
# ... then "applications" as before
```

### 11.3 PDF Template Security: `enrollment_confirmation.html`

The enrollment confirmation PDF template must apply the same security hardening as Phase 2 report templates:

1. **Hex color validation**: Validate `school.primary_color` is a valid hex color before rendering. In `generate_enrollment_confirmation()`, add before building template_context:

```python
import re

# Validate school colors to prevent CSS injection in PDF template
safe_color = "#1a56db"  # fallback
if school.primary_color and re.fullmatch(r"#[0-9a-fA-F]{6}", school.primary_color):
    safe_color = school.primary_color
```

Pass `safe_color` as `primary_color` in the template context instead of using `school.primary_color` directly.

2. **Logo URL validation**: Validate `school.logo_url` is a safe HTTPS URL before including in the PDF:

```python
# Validate logo URL scheme to prevent SSRF in PDF renderer
safe_logo_url = None
if school.logo_url and school.logo_url.startswith("https://"):
    safe_logo_url = school.logo_url
```

Pass `safe_logo_url` as `logo_url` in the template context.

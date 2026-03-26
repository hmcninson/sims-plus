# Phase 1: Models & Migration — Safety & Enrollment

**Sprint:** 20.5
**Depends on:** `20260327_0100_user_sessions` migration
**Parallel with:** Phase 1 Schemas & Endpoints (doc 02), Phase 1 Frontend (doc 03)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 1.1 | Create new enum definitions | `backend/app/models/preschool.py` | 0.25d |
| 1.2 | Create PreschoolIncident model | `backend/app/models/preschool.py` | 0.5d |
| 1.3 | Create AuthorizedPickup model | `backend/app/models/preschool.py` | 0.25d |
| 1.4 | Create PickupLog model | `backend/app/models/preschool.py` | 0.25d |
| 1.5 | Add columns to Student model | `backend/app/models/student.py` | 0.25d |
| 1.6 | Add column to FeeStructure model | `backend/app/models/finance/fee_models.py` | 0.25d |
| 1.7 | Create Alembic migration | `backend/alembic/versions/20260328_0100_preschool_phase1.py` | 1d |
| 1.8 | Update test infrastructure | `backend/tests/conftest.py`, `backend/scripts/verify_rls.py` | 0.25d |

---

## 1.1 New Enum Definitions

**File:** `backend/app/models/preschool.py` (append after existing enums, before `LearningArea` class)

```python
class PreschoolSessionType(str, Enum):
    """Enrollment session types for preschool students."""

    HALF_DAY_MORNING = "half_day_morning"
    HALF_DAY_AFTERNOON = "half_day_afternoon"
    FULL_DAY = "full_day"
    EXTENDED = "extended"


class PreschoolIncidentType(str, Enum):
    """Types of preschool incidents/accidents."""

    ACCIDENT = "accident"              # Physical injury (fall, bump, scrape)
    ILLNESS = "illness"                # Fell sick at school
    BEHAVIORAL = "behavioral"          # Behavioral issue
    ALLERGIC_REACTION = "allergic_reaction"  # Allergy-related
    OTHER = "other"


class PreschoolIncidentSeverity(str, Enum):
    """Severity levels for preschool incidents."""

    MINOR = "minor"        # Scraped knee, small bump — no parent call needed
    MODERATE = "moderate"  # Needs first aid, parent should be notified
    SERIOUS = "serious"    # Medical attention required, parent MUST be notified


class PreschoolIncidentStatus(str, Enum):
    """Workflow status for preschool incidents."""

    REPORTED = "reported"
    REVIEWED = "reviewed"
    PARENT_NOTIFIED = "parent_notified"
    RESOLVED = "resolved"


# ---------------------------------------------------------------
# Incident Status Machine — Valid Transitions
# ---------------------------------------------------------------

VALID_INCIDENT_TRANSITIONS: dict[PreschoolIncidentStatus, list[PreschoolIncidentStatus]] = {
    PreschoolIncidentStatus.REPORTED: [
        PreschoolIncidentStatus.REVIEWED,
        PreschoolIncidentStatus.PARENT_NOTIFIED,  # Skip review for urgent cases
    ],
    PreschoolIncidentStatus.REVIEWED: [
        PreschoolIncidentStatus.PARENT_NOTIFIED,
        PreschoolIncidentStatus.RESOLVED,          # Only minor incidents can skip parent notification
    ],
    PreschoolIncidentStatus.PARENT_NOTIFIED: [
        PreschoolIncidentStatus.RESOLVED,
    ],
    PreschoolIncidentStatus.RESOLVED: [],  # Terminal
}

# CHILD SAFETY: Severity-based resolution rules (enforced in service layer)
# - "minor": Can be resolved from REVIEWED without parent notification
# - "moderate"/"serious": MUST go through PARENT_NOTIFIED before RESOLVED
# The service layer's resolve_incident() enforces this gate.
```

**Conventions followed:**
- `class Name(str, Enum)` with UPPERCASE members
- Lowercase `.value` strings for DB storage
- Status machine dict for valid transitions (matches admissions pattern)

---

## 1.2 PreschoolIncident Model

**File:** `backend/app/models/preschool.py` (append after `PreschoolReport` class)

```python
class PreschoolIncident(Base, TenantMixin, SoftDeleteMixin):
    """
    Preschool incident/accident report.

    Tracks incidents from initial report through review, parent notification,
    and resolution. "Serious" severity auto-triggers parent notification.

    Workflow: reported → reviewed → parent_notified → resolved
    """

    __tablename__ = "preschool_incidents"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="accident, illness, behavioral, allergic_reaction, other",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="minor, moderate, serious",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PreschoolIncidentStatus.REPORTED.value,
        comment="reported, reviewed, parent_notified, resolved",
    )
    incident_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    incident_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Where the incident occurred (e.g., playground, classroom)",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of what happened",
    )
    action_taken: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="What was done immediately after the incident",
    )
    first_aid_given: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether first aid was administered",
    )
    medical_attention_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether professional medical attention is needed",
    )
    parent_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    parent_notified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    witnesses: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='List of witness names, e.g., ["Ms. Adjei", "Mr. Mensah"]',
    )
    attachments: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Photos: [{url, type, thumbnail, filename}]',
    )
    follow_up_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Follow-up observations after initial incident",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships (all lazy="raise")
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    reported_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reported_by],
        lazy="raise",
    )
    parent_notified_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[parent_notified_by],
        lazy="raise",
    )
    resolved_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[resolved_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PreschoolIncident(student_id='{self.student_id}', type='{self.incident_type}', severity='{self.severity}')>"
```

**Key design notes:**
- `SoftDeleteMixin` for audit trail (incidents should never be hard-deleted)
- Three separate user FKs: `reported_by`, `parent_notified_by`, `resolved_by` — different staff may handle each step
- `attachments` JSONB reuses the same `[{url, type, thumbnail, filename}]` structure as `ProgressObservation.attachments`
- No `academic_year_id` or `term_id` — incidents are date-based, not term-scoped

---

## 1.3 AuthorizedPickup Model

**File:** `backend/app/models/preschool.py` (append after `PreschoolIncident`)

```python
class AuthorizedPickup(Base, TenantMixin, SoftDeleteMixin):
    """
    Non-guardian persons authorized to pick up a student.

    Guardians with can_pickup=True on StudentGuardian are implicitly authorized.
    This table tracks ADDITIONAL authorized persons (nannies, family friends, etc.)
    who are not registered guardians.
    """

    __tablename__ = "authorized_pickups"
    # NOTE: Unique constraint is a PARTIAL index (WHERE deleted_at IS NULL)
    # created in the migration, NOT via UniqueConstraint, to allow
    # re-adding soft-deleted phone numbers.

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Contact phone number",
    )
    relationship_to_student: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g., uncle, family friend, nanny, driver",
    )
    photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 presigned URL for photo identification",
    )
    id_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 presigned URL for ID document scan",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Can be deactivated without deletion for audit trail",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Any special notes (e.g., only on Fridays)",
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    added_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[added_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<AuthorizedPickup(name='{self.full_name}', student_id='{self.student_id}')>"
```

**Key design notes:**
- Unique constraint on `(tenant_id, student_id, phone)` — same person can be authorized for multiple students
- `is_active` flag allows deactivation without losing audit trail (plus SoftDeleteMixin for permanent removal)
- `photo_url` and `id_document_url` MUST use S3 presigned URLs (never publicly accessible)

---

## 1.4 PickupLog Model

**File:** `backend/app/models/preschool.py` (append after `AuthorizedPickup`)

```python
class PickupLog(Base, TenantMixin):
    """
    Record of each pickup event.

    Tracks who picked up which student, when, and who (teacher/admin) verified it.
    Does NOT use SoftDeleteMixin — pickup records are immutable audit entries.
    """

    __tablename__ = "pickup_logs"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    pickup_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    pickup_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    picked_up_by_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'guardian' or 'authorized_person'",
    )
    picked_up_by_guardian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardians.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when picked_up_by_type = 'guardian'",
    )
    picked_up_by_authorized_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("authorized_pickups.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when picked_up_by_type = 'authorized_person'",
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Teacher/admin who verified the pickup",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        foreign_keys=[student_id],
        lazy="raise",
    )
    guardian: Mapped["Guardian | None"] = relationship(
        "Guardian",
        foreign_keys=[picked_up_by_guardian_id],
        lazy="raise",
    )
    authorized_pickup: Mapped["AuthorizedPickup | None"] = relationship(
        "AuthorizedPickup",
        foreign_keys=[picked_up_by_authorized_id],
        lazy="raise",
    )
    verified_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[verified_by],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<PickupLog(student_id='{self.student_id}', date='{self.pickup_date}')>"
```

**Key design notes:**
- **NO SoftDeleteMixin** — pickup logs are immutable audit records
- `picked_up_by_type` discriminator: exactly one of `picked_up_by_guardian_id` or `picked_up_by_authorized_id` should be set (validated in service layer)
- `pickup_date` is set server-side to prevent date manipulation
- Add `Guardian` to the TYPE_CHECKING imports at the top of preschool.py

---

## 1.5 Student Model Changes

**File:** `backend/app/models/student.py`

Add two new columns to the `Student` class, after the `notes` field (line ~143):

```python
    # Preschool-specific fields
    enrollment_session: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Preschool session type: half_day_morning, half_day_afternoon, full_day, extended",
    )
    dietary_requirements: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured dietary/allergy data for preschool students",
    )
```

**Required import addition:**
```python
from sqlalchemy.dialects.postgresql import JSONB  # Add to imports if not already present
```

**`dietary_requirements` JSONB schema:**

```json
{
  "allergies": [
    {
      "allergen": "peanuts",
      "severity": "severe",
      "reaction": "anaphylaxis",
      "medication": "EpiPen in nurse's office"
    },
    {
      "allergen": "dairy",
      "severity": "moderate",
      "reaction": "rash"
    }
  ],
  "dietary_restrictions": ["vegetarian", "halal"],
  "notes": "Must avoid all tree nuts. Has EpiPen in office."
}
```

**Key design notes:**
- Both columns are nullable — they only apply to preschool students
- The existing `Student.allergies` text field is NOT removed (backward compatibility)
- `enrollment_session` values match `PreschoolSessionType` enum values
- `dietary_requirements` is validated by Pydantic schema on write (see doc 02)

---

## 1.6 FeeStructure Model Changes

**File:** `backend/app/models/finance/fee_models.py`

Add one new column to `FeeStructure`, after the `student_type` field (line ~148):

```python
    session_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Preschool session type: half_day_morning, half_day_afternoon, full_day, extended. NULL = applies to all sessions.",
    )
```

**Key design notes:**
- NULL means the fee structure applies to all session types (backward compatible)
- When generating invoices for preschool students, the finance service should match `fee_structures.session_type` against `students.enrollment_session`
- Non-preschool fee structures will always have `session_type = NULL`

---

## 1.7 Alembic Migration

**File:** `backend/alembic/versions/20260328_0100_preschool_phase1.py`

```python
"""Preschool Phase 1: Incidents, Pickups, Allergies, Sessions

Creates:
- preschool_incidents table with RLS
- authorized_pickups table with RLS
- pickup_logs table with RLS
- enrollment_session column on students
- dietary_requirements JSONB column on students
- session_type column on fee_structures
- 4 new enum types

Revision ID: 20260328_0100
Revises: 20260327_0100
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260328_0100"
down_revision = "user_sessions"  # IMPORTANT: use actual revision ID, not filename prefix
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # NOTE: No PG enum types created. All enum-like columns use String + CHECK constraints,
    # matching the existing preschool pattern (ObservationType, MoodType, etc. are all String(20)).
    # This avoids ALTER TYPE headaches when adding new values later.

    # ---------------------------------------------------------------
    # 1. Create preschool_incidents table
    # ---------------------------------------------------------------
    op.create_table(
        "preschool_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="reported"),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("incident_time", sa.Time(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("first_aid_given", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("medical_attention_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("parent_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_notified_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("witnesses", JSONB(), nullable=True),
        sa.Column("attachments", JSONB(), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reported_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # 3. Create authorized_pickups table
    # ---------------------------------------------------------------
    op.create_table(
        "authorized_pickups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("relationship_to_student", sa.String(100), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("id_document_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial unique index to allow re-adding soft-deleted phone numbers
    op.execute("""
        CREATE UNIQUE INDEX uq_authorized_pickup_phone
        ON authorized_pickups (tenant_id, student_id, phone)
        WHERE deleted_at IS NULL
    """)

    # ---------------------------------------------------------------
    # 4. Create pickup_logs table
    # ---------------------------------------------------------------
    op.create_table(
        "pickup_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pickup_date", sa.Date(), nullable=False),
        sa.Column("pickup_time", sa.Time(), nullable=False),
        sa.Column("picked_up_by_type", sa.String(20), nullable=False),
        sa.Column("picked_up_by_guardian_id", UUID(as_uuid=True), sa.ForeignKey("guardians.id", ondelete="SET NULL"), nullable=True),
        sa.Column("picked_up_by_authorized_id", UUID(as_uuid=True), sa.ForeignKey("authorized_pickups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---------------------------------------------------------------
    # 5. Add columns to existing tables
    # ---------------------------------------------------------------
    # students: enrollment_session + dietary_requirements
    op.add_column("students", sa.Column(
        "enrollment_session", sa.String(20), nullable=True,
        comment="Preschool session type: half_day_morning, half_day_afternoon, full_day, extended",
    ))
    op.add_column("students", sa.Column(
        "dietary_requirements", JSONB(), nullable=True,
        comment="Structured dietary/allergy data for preschool students",
    ))

    # fee_structures: session_type
    op.add_column("fee_structures", sa.Column(
        "session_type", sa.String(20), nullable=True,
        comment="Preschool session type filter. NULL = applies to all sessions.",
    ))

    # ---------------------------------------------------------------
    # 6. Create indexes
    # ---------------------------------------------------------------
    # preschool_incidents
    op.create_index("ix_preschool_incidents_tenant", "preschool_incidents", ["tenant_id"])
    op.create_index("ix_preschool_incidents_school", "preschool_incidents", ["school_id"])
    op.create_index("ix_preschool_incidents_student_date", "preschool_incidents", ["tenant_id", "student_id", "incident_date"])
    op.create_index("ix_preschool_incidents_status", "preschool_incidents", ["tenant_id", "status"])

    # authorized_pickups
    op.create_index("ix_authorized_pickups_tenant", "authorized_pickups", ["tenant_id"])
    op.create_index("ix_authorized_pickups_school", "authorized_pickups", ["school_id"])
    op.create_index("ix_authorized_pickups_student", "authorized_pickups", ["tenant_id", "student_id"])

    # pickup_logs
    op.create_index("ix_pickup_logs_tenant", "pickup_logs", ["tenant_id"])
    op.create_index("ix_pickup_logs_school", "pickup_logs", ["school_id"])
    op.create_index("ix_pickup_logs_student_date", "pickup_logs", ["tenant_id", "student_id", "pickup_date"])

    # students: GIN index for dietary_requirements JSONB queries
    op.execute(
        "CREATE INDEX ix_students_dietary_requirements ON students "
        "USING GIN (dietary_requirements) WHERE dietary_requirements IS NOT NULL"
    )

    # ---------------------------------------------------------------
    # 7. CHECK constraints (enforce valid enum values at DB level)
    # ---------------------------------------------------------------
    op.execute("""
        ALTER TABLE preschool_incidents
        ADD CONSTRAINT ck_incident_type CHECK (incident_type IN ('accident', 'illness', 'behavioral', 'allergic_reaction', 'other')),
        ADD CONSTRAINT ck_incident_severity CHECK (severity IN ('minor', 'moderate', 'serious')),
        ADD CONSTRAINT ck_incident_status CHECK (status IN ('reported', 'reviewed', 'parent_notified', 'resolved'))
    """)
    op.execute("""
        ALTER TABLE pickup_logs
        ADD CONSTRAINT ck_pickup_type CHECK (picked_up_by_type IN ('guardian', 'authorized_person')),
        ADD CONSTRAINT ck_pickup_person CHECK (
            (picked_up_by_type = 'guardian' AND picked_up_by_guardian_id IS NOT NULL AND picked_up_by_authorized_id IS NULL)
            OR
            (picked_up_by_type = 'authorized_person' AND picked_up_by_authorized_id IS NOT NULL AND picked_up_by_guardian_id IS NULL)
        )
    """)

    # ---------------------------------------------------------------
    # 8. RLS policies (using project-standard rls_helpers)
    # ---------------------------------------------------------------
    from app.db.rls_helpers import enable_rls_for_table
    for table in ["preschool_incidents", "authorized_pickups", "pickup_logs"]:
        enable_rls_for_table(conn, table)


def downgrade() -> None:
    from app.db.rls_helpers import disable_rls_for_table
    conn = op.get_bind()

    # Disable RLS before dropping tables
    for table in ["pickup_logs", "authorized_pickups", "preschool_incidents"]:
        disable_rls_for_table(conn, table)

    # Drop tables (reverse order)
    op.drop_table("pickup_logs")
    op.drop_table("authorized_pickups")
    op.drop_table("preschool_incidents")

    # Drop added columns
    op.drop_column("fee_structures", "session_type")
    op.drop_index("ix_students_dietary_requirements", "students")
    op.drop_column("students", "dietary_requirements")
    op.drop_column("students", "enrollment_session")
```

---

## 1.8 Update Test Infrastructure

### conftest.py

**File:** `backend/tests/conftest.py`

Add to `TENANT_SCOPED_TABLES` list (currently 102 entries), after the existing preschool entries:

```python
    # Preschool Phase 1 (Gap Closure)
    "preschool_incidents", "authorized_pickups", "pickup_logs",
```

After Phase 1, the total will be **105 entries**.

### verify_rls.py

**File:** `backend/scripts/verify_rls.py`

Add the same 3 table names to the tables list in the verification script.

---

## Import Updates

### preschool.py model file — top-of-file imports

Add to the existing `if TYPE_CHECKING:` block:

```python
if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class, Term
    from app.models.student import Guardian, Student  # Add Guardian
    from app.models.user import User
```

### db/base.py — model registration

Ensure the new models are imported for Alembic autodiscovery. The existing preschool import should already cover this since we're appending to the same file:

```python
from app.models.preschool import (  # noqa: F401
    LearningArea, DevelopmentalSkill, PreschoolRatingScale, PreschoolRating,
    StudentSkillAssessment, ProgressObservation, DailyActivityLog, PreschoolReport,
    PreschoolIncident, AuthorizedPickup, PickupLog,  # Add these
)
```

---

## Validation Checklist

Before moving to Phase 1 endpoints (doc 02), verify:

- [ ] All 4 enums defined with lowercase values
- [ ] `VALID_INCIDENT_TRANSITIONS` dict covers all states
- [ ] `PreschoolIncident` has `SoftDeleteMixin`, `PickupLog` does NOT
- [ ] All relationships use `lazy="raise"`
- [ ] All FK constraints have `ondelete` specified
- [ ] `school_id` is nullable on all new models (chain support)
- [ ] UniqueConstraint on `authorized_pickups` includes `tenant_id`
- [ ] Migration creates RLS policies with BOTH `USING` and `WITH CHECK`
- [ ] Migration includes `FORCE ROW LEVEL SECURITY` (applies to table owner too)
- [ ] Migration grants to `sims_app_user`
- [ ] `TENANT_SCOPED_TABLES` updated with 3 new entries
- [ ] GIN index created on `students.dietary_requirements`
- [ ] `downgrade()` reverses all changes in correct order

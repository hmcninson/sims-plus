# Phase 1: Class Assignment History & Enrollment Analytics

**Covers:** SM-017 (Class History), STU-020 (Enrollment History), STU-022 (Enrollment Statistics)
**Priority:** Must
**Estimated Effort:** 3–4 days
**New Tables:** 2
**New Endpoints:** 3
**New Tests:** ~18
**Dependencies:** None — start here

---

## 1. Database Schema

### 1.1 New Table: `student_class_history`

Tracks every class/section assignment for a student across academic years. One row per assignment period. When a student is promoted, the current row gets a `left_date` and `reason`, and a new row is created for the new class.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | `uuid4()` | PK | |
| `tenant_id` | UUID | No | | FK `tenants.id` CASCADE | TenantMixin |
| `student_id` | UUID | No | | FK `students.id` CASCADE | |
| `school_id` | UUID | No | | FK `schools.id` CASCADE | Needed for chain tenants to filter by school |
| `class_id` | UUID | No | | FK `classes.id` CASCADE | |
| `section_id` | UUID | Yes | | FK `class_sections.id` SET NULL | NULL if student has no section |
| `academic_year_id` | UUID | No | | FK `academic_years.id` CASCADE | |
| `enrolled_date` | DATE | No | | | Date the student started in this class |
| `left_date` | DATE | Yes | | | Date the student left this class (NULL = currently enrolled) |
| `reason` | VARCHAR(50) | Yes | | | Why the student left: `promoted`, `repeated`, `transferred`, `withdrawn`, `graduated`, `reassigned` |
| `created_at` | TIMESTAMPTZ | No | `now()` | | Base model |
| `updated_at` | TIMESTAMPTZ | No | `now()` | | Base model |

**NOT using SoftDeleteMixin** — this is an immutable audit record.

**Indexes:**

```sql
-- Primary lookup: student's full history
CREATE INDEX ix_sch_student ON student_class_history(student_id, created_at DESC);

-- Per-student per-year lookup (most common query)
CREATE INDEX ix_sch_student_year ON student_class_history(student_id, academic_year_id);

-- Class roster for a year (used by analytics)
CREATE INDEX ix_sch_class_year ON student_class_history(class_id, academic_year_id);

-- Prevent duplicate active assignments for same student+class+year
CREATE UNIQUE INDEX uq_sch_active_assignment
    ON student_class_history(student_id, class_id, academic_year_id, tenant_id)
    WHERE left_date IS NULL;
```

**RLS Policy:**

```sql
ALTER TABLE student_class_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_class_history FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON student_class_history
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON student_class_history TO sims_app_user;
```

### 1.2 New Table: `student_status_changes`

Unified audit trail for all student status transitions. Every time a student's status changes (enrollment, withdrawal, transfer, graduation, suspension, reactivation), a row is inserted here.

| Column | Type | Nullable | Default | Constraints | Notes |
|--------|------|----------|---------|-------------|-------|
| `id` | UUID | No | `uuid4()` | PK | |
| `tenant_id` | UUID | No | | FK `tenants.id` CASCADE | TenantMixin |
| `student_id` | UUID | No | | FK `students.id` CASCADE | |
| `school_id` | UUID | No | | FK `schools.id` CASCADE | School at time of change (important for chain transfers) |
| `from_status` | VARCHAR(20) | Yes | | | Previous status. NULL for initial enrollment (new student) |
| `to_status` | VARCHAR(20) | No | | | New status value |
| `reason` | TEXT | Yes | | | Human-readable reason for the change |
| `effective_date` | DATE | No | | | When the change takes effect (may differ from created_at) |
| `performed_by` | UUID | Yes | | FK `users.id` SET NULL | User who performed the action. Nullable to allow user deletion without breaking audit trail. |
| `metadata` | JSONB | Yes | | | Extra context, varies by transition type (see below) |
| `created_at` | TIMESTAMPTZ | No | `now()` | | Base model |
| `updated_at` | TIMESTAMPTZ | No | `now()` | | Base model |

**NOT using SoftDeleteMixin** — this is an immutable audit record.

**Metadata JSONB Examples:**

```json
// Withdrawal
{
    "withdrawal_type": "voluntary",
    "fee_override": true,
    "outstanding_amount": "150.00",
    "overridden_by": "user-uuid",
    "clearance_id": "clearance-uuid"
}

// External Transfer
{
    "transfer_type": "external",
    "destination_school": "St. Augustine's College",
    "transfer_certificate_generated": true
}

// Intra-Chain Transfer
{
    "transfer_type": "intra_chain",
    "from_school_id": "school-uuid-1",
    "to_school_id": "school-uuid-2",
    "to_class_id": "class-uuid"
}

// Graduation
{
    "graduating_class": "JHS 3",
    "academic_year": "2025/2026",
    "certificate_generated": false
}

// Suspension
{
    "suspension_reason": "Disciplinary action",
    "expected_return_date": "2026-05-01"
}
```

**Indexes:**

```sql
-- Student timeline (most common query)
CREATE INDEX ix_ssc_student ON student_status_changes(student_id, created_at DESC);

-- Analytics: status changes by date range
CREATE INDEX ix_ssc_effective ON student_status_changes(tenant_id, effective_date);

-- Analytics: filter by target status
CREATE INDEX ix_ssc_to_status ON student_status_changes(tenant_id, to_status, effective_date);
```

**RLS Policy:**

```sql
ALTER TABLE student_status_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_status_changes FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON student_status_changes
    FOR ALL TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON student_status_changes TO sims_app_user;
```

---

## 2. Alembic Migration

**File:** `backend/alembic/versions/20260326_0300_student_history_tables.py`

**Revision chain:** Revises the current HEAD migration.

### Migration Content

```python
"""Add student class history and status change tables.

Revision ID: 20260326_0300
Revises: <current_head>
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260326_0300"
down_revision = "<current_head>"  # Replace with actual HEAD
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Table 1: student_class_history ---
    op.create_table(
        "student_class_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", UUID(as_uuid=True), sa.ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrolled_date", sa.Date, nullable=False),
        sa.Column("left_date", sa.Date, nullable=True),
        sa.Column("reason", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # Indexes
    op.create_index("ix_sch_student", "student_class_history", ["student_id", sa.text("created_at DESC")])
    op.create_index("ix_sch_student_year", "student_class_history", ["student_id", "academic_year_id"])
    op.create_index("ix_sch_class_year", "student_class_history", ["class_id", "academic_year_id"])
    op.execute("""
        CREATE UNIQUE INDEX uq_sch_active_assignment
        ON student_class_history(student_id, class_id, academic_year_id, tenant_id)
        WHERE left_date IS NULL
    """)

    # RLS
    op.execute("ALTER TABLE student_class_history ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_class_history FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_student_class_history ON student_class_history
        FOR ALL TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON student_class_history TO sims_app_user")
    -- UPDATE needed for closing assignments (left_date, reason). No DELETE on audit tables.

    # --- Table 2: student_status_changes ---
    op.create_table(
        "student_status_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("performed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # Indexes
    op.create_index("ix_ssc_student", "student_status_changes", ["student_id", sa.text("created_at DESC")])
    op.create_index("ix_ssc_effective", "student_status_changes", ["tenant_id", "effective_date"])
    op.create_index("ix_ssc_to_status", "student_status_changes", ["tenant_id", "to_status", "effective_date"])

    # RLS
    op.execute("ALTER TABLE student_status_changes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_status_changes FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_student_status_changes ON student_status_changes
        FOR ALL TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT ON student_status_changes TO sims_app_user")
    -- Append-only audit table: no UPDATE or DELETE.

    # --- Backfill: Create class history from current student assignments ---
    # For each active student with a class_id, insert one row using admission_date or created_at
    # as the enrolled_date, linked to the current active academic year.
    op.execute("""
        INSERT INTO student_class_history (
            id, tenant_id, student_id, school_id, class_id, section_id,
            academic_year_id, enrolled_date, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            s.tenant_id,
            s.id,
            s.school_id,
            s.class_id,
            s.section_id,
            ay.id,
            COALESCE(s.admission_date, s.created_at::date),
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM students s
        INNER JOIN academic_years ay
            ON ay.tenant_id = s.tenant_id
            AND ay.school_id = s.school_id
            AND ay.status = 'active'
        WHERE s.class_id IS NOT NULL
            AND s.school_id IS NOT NULL
            AND s.status = 'active'
            AND s.deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON student_status_changes")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON student_class_history")
    op.drop_table("student_status_changes")
    op.drop_table("student_class_history")
```

### Backfill Notes

- The backfill only inserts for **active** students with a non-NULL `class_id` and `school_id`
- It joins on the **active** academic year for the same tenant (`ay.status = 'active'`)
- If no active academic year exists for a tenant, those students are skipped (no-op — acceptable)
- `enrolled_date` uses `admission_date` if present, otherwise falls back to `created_at::date`
- `left_date` and `reason` are left NULL (student is currently in this class)
- Graduated/transferred/withdrawn students are intentionally skipped — they've already left their class

---

## 3. SQLAlchemy Models

**File:** `backend/app/models/student.py`

Add these two models after the existing `StudentGuardian` class. They do NOT use `SoftDeleteMixin`.

### 3.1 StudentClassHistory Model

```python
class StudentClassHistory(Base, TenantMixin):
    """Historical record of student class/section assignments.

    One row per assignment period. When a student is promoted, transferred, or
    withdrawn, the current row receives a left_date and reason, and (if applicable)
    a new row is created for the destination class.

    Immutable audit record — no SoftDeleteMixin.
    """
    __tablename__ = "student_class_history"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        comment="RESTRICT: cannot delete a class that has history records",
    )
    section_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="RESTRICT"),
        nullable=False,
        comment="RESTRICT: cannot delete an academic year that has history records",
    )
    enrolled_date: Mapped[date] = mapped_column(Date, nullable=False)
    left_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="promoted, repeated, transferred, withdrawn, graduated, reassigned",
    )

    # Relationships (lazy="raise" per project convention)
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    class_: Mapped["Class"] = relationship("Class", lazy="raise")
    section: Mapped[Optional["ClassSection"]] = relationship("ClassSection", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
```

**Add to Student model relationships:**

```python
# In the Student class, add:
class_history: Mapped[list["StudentClassHistory"]] = relationship(
    "StudentClassHistory",
    back_populates="student",
    lazy="raise",
    cascade="all, delete-orphan",
)
```

### 3.2 StudentStatusChange Model

```python
class StudentStatusChange(Base, TenantMixin):
    """Audit trail for all student status transitions.

    Records every status change with the previous status, new status, reason,
    effective date, who performed it, and optional metadata.

    Immutable audit record — no SoftDeleteMixin.
    """
    __tablename__ = "student_status_changes"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Previous status. NULL for initial enrollment.",
    )
    to_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Nullable to allow user deletion without breaking audit trail",
    )
    # NOTE: Python attribute is "change_metadata" to avoid shadowing Base.metadata.
    # The DB column remains "metadata".
    change_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Extra context: transfer destination, fee override, etc.",
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    performer: Mapped["User"] = relationship("User", lazy="raise")
```

**Add to Student model relationships:**

```python
# In the Student class, add:
status_changes: Mapped[list["StudentStatusChange"]] = relationship(
    "StudentStatusChange",
    back_populates="student",
    lazy="raise",
    cascade="all, delete-orphan",
)
```

### 3.3 Import Updates

Add to `backend/app/models/student.py` imports:

```python
from sqlalchemy import Text  # If not already imported
from sqlalchemy.dialects.postgresql import JSONB  # Already imported
```

Add to `backend/app/db/base.py` (model registry) — ensure the new models are imported so Alembic can detect them.

Add TYPE_CHECKING imports:

```python
if TYPE_CHECKING:
    from app.models.academic import Class, ClassSection, AcademicYear
    from app.models.user import User
```

---

## 4. Pydantic Schemas

**File:** `backend/app/schemas/student.py`

Add these schemas. They can be placed after the existing `StudentFilterParams` class.

### 4.1 Class History Schemas

```python
from datetime import date as date_type
from pydantic import BaseModel, ConfigDict
from uuid import UUID


class StudentClassHistoryResponse(BaseModel):
    """Response schema for a single class history record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    school_id: UUID
    class_id: UUID
    section_id: UUID | None = None
    academic_year_id: UUID
    enrolled_date: date_type
    left_date: date_type | None = None
    reason: str | None = None
    created_at: str

    # Populated via eager loading
    class_name: str | None = None
    section_name: str | None = None
    academic_year_name: str | None = None


class StudentClassHistoryListResponse(BaseModel):
    """List of class history records for a student."""
    records: list[StudentClassHistoryResponse]
    total: int
```

### 4.2 Status Change Schemas

```python
class StudentStatusChangeResponse(BaseModel):
    """Response schema for a single status change record."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    school_id: UUID
    from_status: str | None = None
    to_status: str
    reason: str | None = None
    effective_date: date_type
    performed_by: UUID
    metadata: dict | None = None
    created_at: str

    # Populated via eager loading
    performed_by_name: str | None = None


class StudentStatusChangeListResponse(BaseModel):
    """List of status change records for a student."""
    records: list[StudentStatusChangeResponse]
    total: int
```

### 4.3 Enrollment Analytics Schema

```python
class ClassEnrollmentBreakdown(BaseModel):
    """Enrollment count for a single class."""
    class_id: UUID
    class_name: str
    total: int
    male: int
    female: int
    boarders: int
    day_students: int


class EnrollmentTrend(BaseModel):
    """Enrollment count for a single academic year."""
    academic_year_id: UUID
    academic_year_name: str
    total_enrolled: int
    new_enrollments: int
    withdrawals: int
    transfers_out: int
    graduations: int


class EnrollmentAnalyticsResponse(BaseModel):
    """Enhanced enrollment analytics response."""
    # Current state
    total_active: int
    total_inactive: int
    total_graduated: int
    total_transferred: int
    total_withdrawn: int
    total_suspended: int

    # Breakdown by class (current academic year)
    by_class: list[ClassEnrollmentBreakdown]

    # Trends over academic years (last 5)
    trends: list[EnrollmentTrend]

    # Rates (current academic year)
    attrition_rate: float  # (withdrawals + transfers_out) / start_of_year_active * 100
    new_enrollment_rate: float  # new_enrollments / total_active * 100
```

---

## 5. Service Layer

**File:** `backend/app/services/student/history_service.py` (new file)

### 5.1 StudentHistoryMixin

```python
"""
SIMS Plus - Student History Service

Tracks class assignment history and student status changes.
Provides enrollment analytics.
"""

from datetime import date, datetime, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, case, literal_column
from sqlalchemy.orm import selectinload, joinedload

from app.models.student import (
    Student, StudentStatus, StudentClassHistory, StudentStatusChange,
)
from app.models.academic import AcademicYear, Class, ClassSection
from app.models.user import User
from app.services.student._shared import StudentServiceError


class StudentHistoryMixin:
    """Mixin for class history tracking, status change recording, and enrollment analytics."""

    # ─── Class History ───────────────────────────────────────────────

    async def record_class_assignment(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        class_id: UUID,
        section_id: UUID | None,
        academic_year_id: UUID,
        enrolled_date: date,
    ) -> StudentClassHistory:
        """Record a new class assignment for a student.

        Called when:
        - A student is first enrolled
        - A student is promoted to a new class
        - A student is reassigned to a different class mid-year
        - A student transfers to a different school within the chain

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID
            school_id: School UUID
            class_id: Target class UUID
            section_id: Target section UUID (optional)
            academic_year_id: Academic year UUID
            enrolled_date: Date the assignment starts

        Returns:
            The created StudentClassHistory record
        """
        record = StudentClassHistory(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            class_id=class_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            enrolled_date=enrolled_date,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def close_class_assignment(
        self,
        tenant_id: UUID,
        student_id: UUID,
        academic_year_id: UUID,
        left_date: date,
        reason: str,
    ) -> None:
        """Close the current (open) class assignment for a student.

        Sets left_date and reason on the most recent open assignment
        for the given student and academic year.

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID
            academic_year_id: Academic year UUID
            left_date: Date the student left this class
            reason: One of: promoted, repeated, transferred, withdrawn, graduated, reassigned
        """
        stmt = (
            select(StudentClassHistory)
            .where(
                StudentClassHistory.tenant_id == tenant_id,
                StudentClassHistory.student_id == student_id,
                StudentClassHistory.academic_year_id == academic_year_id,
                StudentClassHistory.left_date.is_(None),
            )
            .order_by(StudentClassHistory.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            record.left_date = left_date
            record.reason = reason
            await self.db.flush()

    async def get_class_history(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentClassHistory]:
        """Get the complete class assignment history for a student.

        Returns records ordered by enrolled_date descending (most recent first).
        Eager-loads class, section, and academic year names.

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID

        Returns:
            List of StudentClassHistory records with related objects loaded
        """
        stmt = (
            select(StudentClassHistory)
            .options(
                joinedload(StudentClassHistory.class_),
                joinedload(StudentClassHistory.section),
                joinedload(StudentClassHistory.academic_year),
            )
            .where(
                StudentClassHistory.tenant_id == tenant_id,
                StudentClassHistory.student_id == student_id,
            )
            .order_by(StudentClassHistory.enrolled_date.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    # ─── Status Changes ─────────────────────────────────────────────

    async def record_status_change(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        effective_date: date,
        performed_by: UUID,
        metadata: dict | None = None,
    ) -> StudentStatusChange:
        """Record a student status transition.

        Called whenever a student's status field changes. This is the
        canonical audit trail for the student lifecycle.

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID
            school_id: School UUID at time of change
            from_status: Previous status (None for initial enrollment)
            to_status: New status
            reason: Human-readable reason
            effective_date: When the change takes effect
            performed_by: User UUID who performed the action
            metadata: Optional JSONB context (transfer destination, fee override, etc.)

        Returns:
            The created StudentStatusChange record
        """
        record = StudentStatusChange(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            effective_date=effective_date,
            performed_by=performed_by,
            metadata=metadata,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_status_history(
        self,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentStatusChange]:
        """Get the complete status change history for a student.

        Returns records ordered by created_at descending (most recent first).
        Eager-loads the performer's name.

        Args:
            tenant_id: Tenant UUID
            student_id: Student UUID

        Returns:
            List of StudentStatusChange records
        """
        stmt = (
            select(StudentStatusChange)
            .options(joinedload(StudentStatusChange.performer))
            .where(
                StudentStatusChange.tenant_id == tenant_id,
                StudentStatusChange.student_id == student_id,
            )
            .order_by(StudentStatusChange.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    # ─── Enrollment Analytics ────────────────────────────────────────

    async def get_enrollment_analytics(
        self,
        tenant_id: UUID,
        school_id: UUID | None = None,
        academic_year_id: UUID | None = None,
    ) -> dict:
        """Compute enhanced enrollment analytics.

        Returns:
        - Current counts by status
        - Breakdown by class (for the given or active academic year)
        - Trends over the last 5 academic years
        - Attrition and new enrollment rates

        Args:
            tenant_id: Tenant UUID
            school_id: Optional school filter (for chain tenants)
            academic_year_id: Optional academic year (defaults to active year)

        Returns:
            Dictionary matching EnrollmentAnalyticsResponse schema
        """
        # 1. Current status counts
        status_filters = [
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
        ]
        if school_id:
            status_filters.append(Student.school_id == school_id)

        status_stmt = (
            select(
                Student.status,
                func.count(Student.id).label("count"),
            )
            .where(*status_filters)
            .group_by(Student.status)
        )
        status_result = await self.db.execute(status_stmt)
        status_counts = {row.status: row.count for row in status_result}

        total_active = status_counts.get(StudentStatus.ACTIVE.value, 0) or status_counts.get(StudentStatus.ACTIVE, 0)
        total_inactive = status_counts.get(StudentStatus.INACTIVE.value, 0) or status_counts.get(StudentStatus.INACTIVE, 0)
        total_graduated = status_counts.get(StudentStatus.GRADUATED.value, 0) or status_counts.get(StudentStatus.GRADUATED, 0)
        total_transferred = status_counts.get(StudentStatus.TRANSFERRED.value, 0) or status_counts.get(StudentStatus.TRANSFERRED, 0)
        total_withdrawn = status_counts.get(StudentStatus.WITHDRAWN.value, 0) or status_counts.get(StudentStatus.WITHDRAWN, 0)
        total_suspended = status_counts.get(StudentStatus.SUSPENDED.value, 0) or status_counts.get(StudentStatus.SUSPENDED, 0)

        # 2. Resolve academic year
        if not academic_year_id:
            ay_stmt = (
                select(AcademicYear.id)
                .where(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.status == "active",
                )
                .limit(1)
            )
            ay_result = await self.db.execute(ay_stmt)
            academic_year_id = ay_result.scalar_one_or_none()

        # 3. Breakdown by class (current academic year)
        by_class = []
        if academic_year_id:
            class_filters = [
                StudentClassHistory.tenant_id == tenant_id,
                StudentClassHistory.academic_year_id == academic_year_id,
                StudentClassHistory.left_date.is_(None),  # Currently assigned
            ]
            if school_id:
                class_filters.append(StudentClassHistory.school_id == school_id)

            class_stmt = (
                select(
                    StudentClassHistory.class_id,
                    Class.name.label("class_name"),
                    func.count(StudentClassHistory.id).label("total"),
                    func.count(func.nullif(Student.gender == "male", False)).label("male"),
                    func.count(func.nullif(Student.gender == "female", False)).label("female"),
                    func.count(func.nullif(Student.is_boarder == True, False)).label("boarders"),
                    func.count(func.nullif(Student.is_boarder == False, False)).label("day_students"),
                )
                .join(Student, Student.id == StudentClassHistory.student_id)
                .join(Class, Class.id == StudentClassHistory.class_id)
                .where(*class_filters)
                .group_by(StudentClassHistory.class_id, Class.name)
                .order_by(Class.name)
            )
            class_result = await self.db.execute(class_stmt)
            by_class = [
                {
                    "class_id": str(row.class_id),
                    "class_name": row.class_name,
                    "total": row.total,
                    "male": row.male,
                    "female": row.female,
                    "boarders": row.boarders,
                    "day_students": row.day_students,
                }
                for row in class_result
            ]

        # 4. Trends over last 5 academic years
        trends = []
        trend_stmt = (
            select(AcademicYear)
            .where(AcademicYear.tenant_id == tenant_id)
            .order_by(AcademicYear.start_date.desc())
            .limit(5)
        )
        trend_result = await self.db.execute(trend_stmt)
        academic_years = list(trend_result.scalars().all())

        for ay in academic_years:
            # Total enrolled in this year (from class history)
            enrolled_count_stmt = (
                select(func.count(StudentClassHistory.id))
                .where(
                    StudentClassHistory.tenant_id == tenant_id,
                    StudentClassHistory.academic_year_id == ay.id,
                )
            )
            if school_id:
                enrolled_count_stmt = enrolled_count_stmt.where(
                    StudentClassHistory.school_id == school_id
                )
            enrolled_result = await self.db.execute(enrolled_count_stmt)
            total_enrolled = enrolled_result.scalar() or 0

            # Status change counts for this year
            change_filters = [
                StudentStatusChange.tenant_id == tenant_id,
                StudentStatusChange.effective_date >= ay.start_date,
                StudentStatusChange.effective_date <= ay.end_date,
            ]
            if school_id:
                change_filters.append(StudentStatusChange.school_id == school_id)

            new_stmt = (
                select(func.count(StudentStatusChange.id))
                .where(*change_filters, StudentStatusChange.from_status.is_(None))
            )
            new_result = await self.db.execute(new_stmt)
            new_enrollments = new_result.scalar() or 0

            withdrawn_stmt = (
                select(func.count(StudentStatusChange.id))
                .where(*change_filters, StudentStatusChange.to_status == "withdrawn")
            )
            withdrawn_result = await self.db.execute(withdrawn_stmt)
            withdrawals = withdrawn_result.scalar() or 0

            transferred_stmt = (
                select(func.count(StudentStatusChange.id))
                .where(*change_filters, StudentStatusChange.to_status == "transferred")
            )
            transferred_result = await self.db.execute(transferred_stmt)
            transfers_out = transferred_result.scalar() or 0

            graduated_stmt = (
                select(func.count(StudentStatusChange.id))
                .where(*change_filters, StudentStatusChange.to_status == "graduated")
            )
            graduated_result = await self.db.execute(graduated_stmt)
            graduations = graduated_result.scalar() or 0

            trends.append({
                "academic_year_id": str(ay.id),
                "academic_year_name": ay.name,
                "total_enrolled": total_enrolled,
                "new_enrollments": new_enrollments,
                "withdrawals": withdrawals,
                "transfers_out": transfers_out,
                "graduations": graduations,
            })

        # 5. Rates
        start_count = total_active + total_withdrawn + total_transferred  # Approximate start-of-year
        attrition_rate = 0.0
        if start_count > 0:
            attrition_rate = round(
                (total_withdrawn + total_transferred) / start_count * 100, 2
            )

        total_all = total_active + total_inactive + total_graduated + total_transferred + total_withdrawn + total_suspended
        new_enrollment_rate = 0.0
        if total_active > 0 and trends:
            current_year_new = trends[0]["new_enrollments"] if trends else 0
            new_enrollment_rate = round(current_year_new / total_active * 100, 2)

        return {
            "total_active": total_active,
            "total_inactive": total_inactive,
            "total_graduated": total_graduated,
            "total_transferred": total_transferred,
            "total_withdrawn": total_withdrawn,
            "total_suspended": total_suspended,
            "by_class": by_class,
            "trends": trends,
            "attrition_rate": attrition_rate,
            "new_enrollment_rate": new_enrollment_rate,
        }
```

### 5.2 Update `__init__.py`

```python
# backend/app/services/student/__init__.py
from app.services.student.history_service import StudentHistoryMixin

class StudentService(
    StudentCoreMixin,
    StudentImportMixin,
    StudentGuardianMixin,
    StudentHistoryMixin,  # Phase 1
):
    def __init__(self, db: AsyncSession):
        self.db = db
```

---

## 6. Integration: Recording Status Changes Automatically

### 6.1 Modify `StudentCoreMixin.update_student()`

**File:** `backend/app/services/student/student_service.py`

When `update_student()` receives a `status` change, it must call `record_status_change()`. This ensures all status transitions are tracked regardless of whether they come from the withdrawal workflow, transfer workflow, or a simple admin update.

**Changes to make:**

In the `update_student()` method, after the existing update logic but before `flush()`:

```python
# Detect status change
old_status = student.status
# ... apply updates to student ...

# If status changed, record it
if "status" in update_data and str(update_data["status"]) != str(old_status):
    new_status_str = update_data["status"]
    if hasattr(new_status_str, "value"):
        new_status_str = new_status_str.value
    old_status_str = old_status.value if hasattr(old_status, "value") else str(old_status)

    await self.record_status_change(
        tenant_id=tenant_id,
        student_id=student.id,
        school_id=student.school_id,
        from_status=old_status_str,
        to_status=new_status_str,
        reason=None,  # Simple status update via admin, no reason
        effective_date=date.today(),
        performed_by=performed_by,  # NOTE: update_student needs to accept performed_by param
    )
```

**Important:** The `update_student()` method signature needs to accept `performed_by: UUID` as a parameter. The endpoint must pass the current user's ID. Check the current signature and add this parameter if missing.

### 6.2 Modify `PromotionService.execute_batch()`

**File:** `backend/app/services/admissions/promotion_service.py`

When executing promotion entries, the service must record class history changes:

```python
# For each entry being processed:
# 1. Close the current class assignment
await student_service.close_class_assignment(
    tenant_id=tenant_id,
    student_id=entry.student_id,
    academic_year_id=batch.academic_year_id,
    left_date=date.today(),
    reason=entry.action.value,  # "promote", "repeat", "graduate", "withdraw"
)

# 2. If promoted or repeated (student gets a new class), open a new assignment
if entry.action in (PromotionAction.PROMOTE, PromotionAction.REPEAT):
    target_class_id = entry.target_class_id if entry.action == PromotionAction.PROMOTE else entry.source_class_id
    target_section_id = entry.target_section_id

    # Determine the next academic year (for promoted students)
    next_academic_year_id = ...  # Query for the next academic year

    await student_service.record_class_assignment(
        tenant_id=tenant_id,
        student_id=entry.student_id,
        school_id=student.school_id,
        class_id=target_class_id,
        section_id=target_section_id,
        academic_year_id=next_academic_year_id,
        enrolled_date=date.today(),
    )

# 3. If graduated or withdrawn, record status change
if entry.action in (PromotionAction.GRADUATE, PromotionAction.WITHDRAW):
    await student_service.record_status_change(
        tenant_id=tenant_id,
        student_id=entry.student_id,
        school_id=student.school_id,
        from_status="active",
        to_status="graduated" if entry.action == PromotionAction.GRADUATE else "withdrawn",
        reason=entry.reason,
        effective_date=date.today(),
        performed_by=batch.executed_by,
        metadata={"source": "promotion_batch", "batch_id": str(batch.id)},
    )
```

**Note:** The `PromotionService` needs access to a `StudentService` instance. It should accept it as a parameter to `execute_batch()` or instantiate it internally with the same `db` session.

---

## 7. API Endpoints

**File:** `backend/app/api/v1/endpoints/students.py`

Add these endpoints to the existing students router.

### 7.1 GET `/students/{student_id}/class-history`

```python
@router.get("/students/{student_id}/class-history")
async def get_student_class_history(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Get the complete class assignment history for a student.

    Returns a chronological list of all class/section assignments
    with academic year, enrolled date, left date, and reason.
    """
    tenant_id = user["tenant_id"]
    service = StudentService(db)

    # Verify student exists and belongs to tenant
    student = await service.get_student(tenant_id, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    records = await service.get_class_history(tenant_id, student_id)

    return {
        "records": [
            {
                "id": str(r.id),
                "student_id": str(r.student_id),
                "school_id": str(r.school_id),
                "class_id": str(r.class_id),
                "section_id": str(r.section_id) if r.section_id else None,
                "academic_year_id": str(r.academic_year_id),
                "enrolled_date": r.enrolled_date.isoformat(),
                "left_date": r.left_date.isoformat() if r.left_date else None,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
                "class_name": r.class_.name if r.class_ else None,
                "section_name": r.section.name if r.section else None,
                "academic_year_name": r.academic_year.name if r.academic_year else None,
            }
            for r in records
        ],
        "total": len(records),
    }
```

### 7.2 GET `/students/{student_id}/status-history`

```python
@router.get("/students/{student_id}/status-history")
async def get_student_status_history(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Get the complete status change history for a student.

    Returns a chronological list of all status transitions with
    from/to status, reason, effective date, and who performed it.
    """
    tenant_id = user["tenant_id"]
    service = StudentService(db)

    student = await service.get_student(tenant_id, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    records = await service.get_status_history(tenant_id, student_id)

    return {
        "records": [
            {
                "id": str(r.id),
                "student_id": str(r.student_id),
                "school_id": str(r.school_id),
                "from_status": r.from_status,
                "to_status": r.to_status,
                "reason": r.reason,
                "effective_date": r.effective_date.isoformat(),
                "performed_by": str(r.performed_by),
                "metadata": r.metadata,
                "created_at": r.created_at.isoformat(),
                "performed_by_name": (
                    f"{r.performer.first_name} {r.performer.last_name}"
                    if r.performer else None
                ),
            }
            for r in records
        ],
        "total": len(records),
    }
```

### 7.3 GET `/students/analytics/enrollment`

```python
@router.get("/students/analytics/enrollment")
async def get_enrollment_analytics(
    school_id: UUID | None = None,
    academic_year_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(ValidatedUser),
    _: None = Depends(require_permissions("students.read")),
):
    """Get enhanced enrollment analytics.

    Returns current counts by status, breakdown by class,
    trends over the last 5 academic years, and attrition/enrollment rates.

    Query Parameters:
    - school_id: Filter by school (for chain tenants)
    - academic_year_id: Specific academic year (defaults to active year)
    """
    tenant_id = user["tenant_id"]
    service = StudentService(db)

    analytics = await service.get_enrollment_analytics(
        tenant_id=tenant_id,
        school_id=school_id,
        academic_year_id=academic_year_id,
    )

    return analytics
```

---

## 8. Frontend Changes

### 8.1 TypeScript Types

**File:** `frontend/types/index.ts`

```typescript
// Student Class History
export interface StudentClassHistoryRecord {
  id: string;
  student_id: string;
  school_id: string;
  class_id: string;
  section_id: string | null;
  academic_year_id: string;
  enrolled_date: string;
  left_date: string | null;
  reason: string | null;
  created_at: string;
  class_name: string | null;
  section_name: string | null;
  academic_year_name: string | null;
}

export interface StudentClassHistoryResponse {
  records: StudentClassHistoryRecord[];
  total: number;
}

// Student Status Change
export interface StudentStatusChangeRecord {
  id: string;
  student_id: string;
  school_id: string;
  from_status: string | null;
  to_status: string;
  reason: string | null;
  effective_date: string;
  performed_by: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  performed_by_name: string | null;
}

export interface StudentStatusChangeResponse {
  records: StudentStatusChangeRecord[];
  total: number;
}

// Enrollment Analytics
export interface ClassEnrollmentBreakdown {
  class_id: string;
  class_name: string;
  total: number;
  male: number;
  female: number;
  boarders: number;
  day_students: number;
}

export interface EnrollmentTrend {
  academic_year_id: string;
  academic_year_name: string;
  total_enrolled: number;
  new_enrollments: number;
  withdrawals: number;
  transfers_out: number;
  graduations: number;
}

export interface EnrollmentAnalytics {
  total_active: number;
  total_inactive: number;
  total_graduated: number;
  total_transferred: number;
  total_withdrawn: number;
  total_suspended: number;
  by_class: ClassEnrollmentBreakdown[];
  trends: EnrollmentTrend[];
  attrition_rate: number;
  new_enrollment_rate: number;
}
```

### 8.2 Server Actions

**File:** `frontend/actions/students.action.ts`

```typescript
export async function getClassHistory(studentId: string): Promise<ActionResult<StudentClassHistoryResponse>> {
  try {
    const response = await apiGet<StudentClassHistoryResponse>(`/students/${studentId}/class-history`);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch class history" };
  }
}

export async function getStatusHistory(studentId: string): Promise<ActionResult<StudentStatusChangeResponse>> {
  try {
    const response = await apiGet<StudentStatusChangeResponse>(`/students/${studentId}/status-history`);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch status history" };
  }
}

export async function getEnrollmentAnalytics(params?: {
  school_id?: string;
  academic_year_id?: string;
}): Promise<ActionResult<EnrollmentAnalytics>> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.school_id) searchParams.set("school_id", params.school_id);
    if (params?.academic_year_id) searchParams.set("academic_year_id", params.academic_year_id);
    const query = searchParams.toString();
    const url = `/students/analytics/enrollment${query ? `?${query}` : ""}`;
    const response = await apiGet<EnrollmentAnalytics>(url);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch analytics" };
  }
}
```

### 8.3 Student Detail Page — History Tab

**File:** `frontend/app/(dashboard)/students/[id]/page.tsx`

Add a new "History" tab to the existing student detail page. This tab shows two timelines:

1. **Class Assignment Timeline** — A vertical timeline showing each class the student has been in, with dates and reasons for leaving.
2. **Status Change Timeline** — A vertical timeline showing every status transition.

**Component structure:**

```
students/[id]/
  ├── page.tsx                    (existing — add "History" tab)
  ├── student-class-timeline.tsx  (new — renders class history)
  └── student-status-timeline.tsx (new — renders status changes)
```

**Class Timeline component:**
- Fetches data via `getClassHistory(studentId)`
- Renders as a vertical timeline with cards
- Each card shows: Academic Year, Class Name, Section Name, Enrolled Date, Left Date, Reason badge
- Current assignment (left_date = null) is highlighted with a "Current" badge
- Empty state: "No class history recorded"

**Status Timeline component:**
- Fetches data via `getStatusHistory(studentId)`
- Renders as a vertical timeline with cards
- Each card shows: From → To status badges, Reason, Effective Date, Performed By
- Color-coded by status type (green=active, red=withdrawn, blue=transferred, yellow=graduated)
- Empty state: "No status changes recorded"

### 8.4 Enrollment Analytics Section

**Location options:**
- Option A: New page at `/students/analytics` (accessible from sidebar)
- Option B: Section within the existing dashboard page at `/dashboard`

**Recommended: Option A** — a dedicated analytics page provides more room for charts.

**Component structure:**

```
students/
  └── analytics/
      └── page.tsx
      └── enrollment-analytics.tsx
```

**Content:**
- **Summary cards** (top row): Total Active, Total Graduated, Total Transferred, Total Withdrawn, Attrition Rate %, New Enrollment Rate %
- **Enrollment by Class** (table): Class name, Total, Male, Female, Boarders, Day Students — using TanStack Table
- **Enrollment Trends** (chart): Recharts line chart with academic years on x-axis, lines for total_enrolled, new_enrollments, withdrawals, transfers_out, graduations
- **School filter** (dropdown): For chain tenants, filter by school
- **Academic year selector** (dropdown): Choose which year for the class breakdown

---

## 9. Test Plan

### 9.1 `tests/test_student_class_history.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_record_class_assignment` | Unit | Create a class history record, verify all fields |
| 2 | `test_close_class_assignment` | Unit | Close an open assignment, verify left_date and reason set |
| 3 | `test_close_nonexistent_assignment` | Unit | Closing when no open assignment exists is a no-op (no error) |
| 4 | `test_get_class_history_ordered` | Unit | History returns records ordered by enrolled_date DESC |
| 5 | `test_get_class_history_empty` | Unit | Returns empty list for student with no history |
| 6 | `test_backfill_creates_records` | Integration | After migration, active students with class_id have one history record |
| 7 | `test_unique_active_assignment` | Constraint | Cannot create two active (left_date=NULL) records for same student+class+year |
| 8 | `test_class_history_rls` | RLS | Tenant A cannot see tenant B's class history |

### 9.2 `tests/test_student_status_changes.py`

| # | Test | Type | Description |
|---|------|------|-------------|
| 1 | `test_record_status_change` | Unit | Create a status change record, verify all fields |
| 2 | `test_record_initial_enrollment` | Unit | from_status=None for new student |
| 3 | `test_record_with_metadata` | Unit | Metadata JSONB stored and retrieved correctly |
| 4 | `test_get_status_history_ordered` | Unit | History returns records ordered by created_at DESC |
| 5 | `test_get_status_history_empty` | Unit | Returns empty list for student with no changes |
| 6 | `test_status_change_on_update` | Integration | Updating student status via update_student() creates a status_change record |
| 7 | `test_status_change_on_promotion` | Integration | Executing a promotion batch creates status_change records for graduated/withdrawn |
| 8 | `test_status_changes_rls` | RLS | Tenant A cannot see tenant B's status changes |
| 9 | `test_enrollment_analytics_basic` | Unit | Analytics returns correct counts and rates |
| 10 | `test_enrollment_analytics_school_filter` | Unit | School filter works for chain tenants |

### 9.3 RLS Tests Addition

**File:** `tests/test_student_mgmt_rls.py`

Add both `student_class_history` and `student_status_changes` to the RLS test suite. Follow the existing pattern from `test_admissions_rls.py`:

```python
@pytest.mark.parametrize("table", [
    "student_class_history",
    "student_status_changes",
])
async def test_tenant_isolation(table, admin_session, app_session):
    # Seed data for tenant A and tenant B via admin
    # Switch app_session to tenant A
    # Verify only tenant A records are visible
    # Switch to tenant B
    # Verify only tenant B records are visible
```

---

## 10. Checklist

- [ ] Create migration `20260326_0300_student_history_tables.py`
- [ ] Run migration and verify backfill
- [ ] Add `StudentClassHistory` model to `models/student.py`
- [ ] Add `StudentStatusChange` model to `models/student.py`
- [ ] Add relationships to `Student` model
- [ ] Register new models in `db/base.py`
- [ ] Create `services/student/history_service.py` with `StudentHistoryMixin`
- [ ] Update `services/student/__init__.py` to include `StudentHistoryMixin`
- [ ] Modify `StudentCoreMixin.update_student()` to record status changes
- [ ] Modify `PromotionService.execute_batch()` to record class history + status changes
- [ ] Add schemas to `schemas/student.py`
- [ ] Add 3 endpoints to `api/v1/endpoints/students.py`
- [ ] Add `student_class_history` and `student_status_changes` to `TENANT_SCOPED_TABLES` in `tests/conftest.py`
- [ ] Add both tables to `backend/scripts/verify_rls.py`
- [ ] Add both tables to `backend/app/tasks/tenant_cleanup.py`
- [ ] Write `tests/test_student_class_history.py` (~8 tests)
- [ ] Write `tests/test_student_status_changes.py` (~10 tests)
- [ ] Add RLS tests to `tests/test_student_mgmt_rls.py`
- [ ] Add TypeScript types to `frontend/types/index.ts`
- [ ] Add server actions to `frontend/actions/students.action.ts`
- [ ] Create `student-class-timeline.tsx` component
- [ ] Create `student-status-timeline.tsx` component
- [ ] Add "History" tab to student detail page
- [ ] Create enrollment analytics page at `/students/analytics`
- [ ] Test all endpoints manually via Swagger UI

# Phase 1: Models & Migration

**Module:** Applicant Accounts (extension to Admissions Portal)
**Agent:** 1 (Data Model + Migration)
**Depends on:** Admissions Portal Phase 1 (`20260303_0100_admissions_tables.py` migration)
**Parallel with:** Nothing (must complete before Phase 2 services/endpoints)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 1.1 | Add `APPLICANT` to `UserRole` enum | `backend/app/models/user.py` | 0.1d |
| 1.2 | Add `applicant_user_id` column to Application model | `backend/app/models/admissions/application.py` | 0.25d |
| 1.3 | Add `require_applicant_account` column to AdmissionPeriod model | `backend/app/models/admissions/period.py` | 0.1d |
| 1.4 | Create Alembic migration | `backend/alembic/versions/20260303_0200_applicant_accounts.py` | 0.5d |
| 1.5 | Verify test infrastructure (no changes needed) | N/A | 0.1d |
| 1.6 | Drop global unique on `users.email`, add tenant-scoped composite unique | `backend/app/models/user.py`, migration | 0.25d |
| 1.7 | Make `date_of_birth`, `gender`, `target_class_id` nullable on Application | `backend/app/models/admissions/application.py`, migration | 0.15d |

**Total estimated effort: 1.45 days**

---

## 1.1 Add APPLICANT to UserRole Enum

**File:** `backend/app/models/user.py`

Add `APPLICANT = "applicant"` as the last member of the `UserRole` enum, after `STUDENT`. (Task 1.6 also modifies this file to change the email uniqueness constraint.)

### Current Code

```python
class UserRole(str, Enum):
    """User roles for RBAC."""

    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    PARENT = "parent"
    STUDENT = "student"
```

### Updated Code

```python
class UserRole(str, Enum):
    """User roles for RBAC."""

    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    PARENT = "parent"
    STUDENT = "student"
    APPLICANT = "applicant"
```

### Why This Works

The `userrole` PostgreSQL enum type already exists in the database. The `User.role` column is defined with `values_callable=lambda x: [e.value for e in x]`, which means SQLAlchemy sends the `.value` strings to PostgreSQL. Adding the Python enum member here keeps the ORM in sync with the database enum (which will be updated by the migration in task 1.4).

No changes to the `SQLEnum` column definition on the `User` model are needed -- `values_callable` dynamically reads all enum members at import time.

### Notes

- The overview spec (`00-overview.md`) references `models/tenant.py` for `UserRole`, but the actual location is `models/user.py`. Use the correct path.
- The `User` model's `role` column already uses `values_callable=lambda x: [e.value for e in x]`, so no changes to that column are required.
- Do NOT modify `is_admin` property -- `APPLICANT` is intentionally excluded from admin roles.

---

## 1.2 Add `applicant_user_id` to Application Model

**File:** `backend/app/models/admissions/application.py`

Add a nullable FK column linking an application to the applicant's user account, plus a relationship for eager loading.

### Changes Required

#### 1. Add `User` to `TYPE_CHECKING` imports

The `User` import already exists in the `TYPE_CHECKING` block (imported from `app.models.tenant`). No change needed.

**Current:**
```python
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
```

`User` is already imported here. No changes to the import block.

#### 2. Add `applicant_user_id` column

Add the column after `converted_student_id` and before `applicant_photo_url`:

```python
    converted_student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set on enrollment -- serves as idempotency guard",
    )

    # Applicant account link (null for anonymous applications)
    applicant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Owning applicant account (null for anonymous submissions)",
    )

    applicant_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
```

**Column details:**

| Property | Value |
|----------|-------|
| Type | `UUID(as_uuid=True)` |
| FK target | `users.id` |
| ON DELETE | `SET NULL` (preserve application if user is deleted) |
| Nullable | `True` (anonymous applications have no user account) |
| Index | Partial index created in migration (not on column def) |

**Why `ON DELETE SET NULL`:** If an applicant's user account is deleted (e.g., admin removes a spam account), the application record should survive -- it may already have been reviewed, offered, or enrolled. Setting to NULL makes it an "orphaned" anonymous application.

**Why no unique constraint:** One parent can submit multiple applications for different children. The `(tenant_id, applicant_user_id)` combination is intentionally non-unique.

#### 3. Add `applicant_user` relationship

Add after the `converted_student` relationship, before `guardians`:

```python
    converted_student: Mapped["Student | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[converted_student_id],
    )

    # Applicant account relationship
    applicant_user: Mapped["User | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[applicant_user_id],
    )

    guardians: Mapped[list["ApplicationGuardian"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
```

**Relationship details:**

| Property | Value | Reason |
|----------|-------|--------|
| `lazy="raise"` | Required | Project convention -- prevents N+1 queries in async context |
| `foreign_keys=[applicant_user_id]` | Required | Disambiguates from `converted_student` and other User FKs (e.g., `ApplicationStatusHistory.changed_by`, `ApplicationNote.author_id`) |
| No `back_populates` | Intentional | We do not add a reverse `applications` relationship on `User` -- querying user's applications goes through the service layer with explicit `selectinload` |

#### 4. No changes to `__table_args__`

The `__table_args__` tuple remains unchanged:

```python
    __table_args__ = (
        UniqueConstraint("tenant_id", "tracking_code", name="uq_applications_tenant_tracking"),
    )
```

No unique constraint on `applicant_user_id` -- one user can own many applications (multi-child support).

### Complete Updated Application Class (Relevant Section)

For clarity, here is the full column and relationship section showing where the new code fits:

```python
class Application(Base, TenantMixin, SoftDeleteMixin):
    """
    Application model -- the central entity of the admissions module.

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
        comment="Public identifier -- secrets.token_urlsafe(48), 384-bit entropy",
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
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,  # Nullable to support partial draft saves (see task 1.7)
    )
    gender: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,  # Nullable to support partial draft saves (see task 1.7)
        comment="male or female",
    )
    nationality: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,  # Nullable to support partial draft saves (see task 1.7)
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
        comment="Set on enrollment -- serves as idempotency guard",
    )

    # Applicant account link (null for anonymous applications)
    applicant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Owning applicant account (null for anonymous submissions)",
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
    school: Mapped["School"] = sa_relationship(lazy="raise")
    admission_period: Mapped["AdmissionPeriod"] = sa_relationship(
        back_populates="applications",
        lazy="raise",
    )
    target_class: Mapped["Class"] = sa_relationship(
        lazy="raise",
        foreign_keys=[target_class_id],
    )
    converted_student: Mapped["Student | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[converted_student_id],
    )

    # Applicant account relationship
    applicant_user: Mapped["User | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[applicant_user_id],
    )

    guardians: Mapped[list["ApplicationGuardian"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["ApplicationDocument"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["ApplicationPayment"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list["ApplicationStatusHistory"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list["ApplicationNote"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    decision: Mapped["AdmissionDecision | None"] = sa_relationship(
        back_populates="application",
        lazy="raise",
        uselist=False,
    )
    exam_registrations: Mapped[list["EntranceExamRegistration"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
    )
    exam_results: Mapped[list["EntranceExamResult"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
    )
```

---

## 1.3 Add `require_applicant_account` to AdmissionPeriod Model

**File:** `backend/app/models/admissions/period.py`

Add a boolean column that controls whether the admission period requires applicants to create an account before submitting.

### Change Required

Add the column after `target_classes` and before the relationships block:

```python
    target_classes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of class UUIDs this period accepts applications for",
    )

    # Applicant account requirement toggle
    require_applicant_account: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, applicants must register/login before submitting",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
```

**Column details:**

| Property | Value | Reason |
|----------|-------|--------|
| Type | `Boolean` | Binary toggle |
| Nullable | `False` | Always has a value |
| Default (Python) | `False` | New periods default to anonymous-allowed |
| Server Default | `"false"` | Existing rows get `false` when column is added |

**Why `server_default="false"`:** When the migration adds this column to existing `admission_periods` rows, PostgreSQL needs a default value for the NOT NULL constraint. `"false"` ensures all existing periods continue to work in anonymous mode -- no behavioral change for existing schools.

### No Import Changes Required

`Boolean` is already imported in `period.py`:

```python
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
```

---

## 1.4 Create Alembic Migration

**File:** `backend/alembic/versions/20260303_0200_applicant_accounts.py`

### Migration Chain

```
20260302_0100 (messaging_tables)
    └── 20260303_0100 (admissions_tables)
        └── 20260303_0200 (applicant_accounts)  ← THIS MIGRATION
```

### Critical: PostgreSQL Enum ALTER TYPE Restriction

`ALTER TYPE ... ADD VALUE` **cannot run inside a transaction block** in PostgreSQL. Alembic runs migrations inside a transaction by default. The migration uses the `AUTOCOMMIT` isolation level pattern as the **primary approach**:

1. Get the connection via `op.get_bind()`
2. Set `isolation_level="AUTOCOMMIT"` before the `ALTER TYPE` statement
3. Restore `isolation_level="READ COMMITTED"` immediately after
4. Proceed with the normal transactional DDL (column additions, indexes)

This is a well-known PostgreSQL limitation. The Alembic documentation recommends using `AUTOCOMMIT` for enum value additions. This is the only universally safe approach.

### Full Migration File

```python
"""Add applicant accounts support: userrole enum, email uniqueness, nullable drafts, applicant FK

Applicant Accounts (extension to Admissions Portal)

1. Add 'applicant' value to userrole PostgreSQL enum (AUTOCOMMIT required)
2. Drop global unique on users.email, create tenant-scoped composite unique
3. Make date_of_birth, gender, target_class_id nullable on applications (draft support)
4. Add applicant_user_id nullable FK column to applications table
5. Add FK constraint for applicant_user_id
6. Add partial index on (tenant_id, applicant_user_id) for efficient lookups
7. Add require_applicant_account boolean column to admission_periods table

Revision ID: 20260303_0200
Revises: 20260303_0100
Create Date: 2026-03-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260303_0200"
down_revision: Union[str, None] = "20260303_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =================================================================
    # STEP 1: Add 'applicant' to userrole enum
    #
    # ALTER TYPE ... ADD VALUE cannot reliably run inside a transaction
    # in PostgreSQL. Use AUTOCOMMIT isolation level for this single
    # statement, then restore READ COMMITTED for remaining DDL.
    # =================================================================
    connection = op.get_bind()
    connection.execution_options(isolation_level="AUTOCOMMIT")
    connection.execute(
        sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'applicant'")
    )
    connection.execution_options(isolation_level="READ COMMITTED")

    # =================================================================
    # STEP 2: Drop global unique on users.email, add tenant-scoped composite
    #
    # The existing unique=True on User.email creates a DB-wide unique
    # constraint, blocking the same email from registering as applicant
    # at two different schools. Replace with (tenant_id, email) unique
    # filtered by deleted_at IS NULL (soft-deleted users don't block).
    # =================================================================
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_email"))
    op.execute(sa.text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key"))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX uq_users_tenant_email "
        "ON users(tenant_id, email) WHERE deleted_at IS NULL"
    ))

    # =================================================================
    # STEP 3: Make date_of_birth, gender, target_class_id nullable
    #
    # Draft applications need to be saved with partial data. These
    # columns must be nullable so drafts can be created incrementally.
    # Completeness is enforced at the service layer on submit.
    # =================================================================
    op.execute(sa.text(
        "ALTER TABLE applications ALTER COLUMN date_of_birth DROP NOT NULL"
    ))
    op.execute(sa.text(
        "ALTER TABLE applications ALTER COLUMN gender DROP NOT NULL"
    ))
    op.execute(sa.text(
        "ALTER TABLE applications ALTER COLUMN target_class_id DROP NOT NULL"
    ))

    # =================================================================
    # STEP 4: Add applicant_user_id column to applications table
    #
    # Nullable FK to users.id with ON DELETE SET NULL.
    # Null = anonymous application (no account).
    # No unique constraint -- one user can own many applications.
    # =================================================================
    op.add_column(
        "applications",
        sa.Column(
            "applicant_user_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Owning applicant account (null for anonymous submissions)",
        ),
    )

    # =================================================================
    # STEP 5: Add FK constraint
    # =================================================================
    op.create_foreign_key(
        "fk_applications_applicant_user_id",
        "applications",
        "users",
        ["applicant_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # =================================================================
    # STEP 6: Create partial index for efficient applicant lookups
    #
    # Only indexes rows where applicant_user_id IS NOT NULL, keeping
    # the index small (anonymous applications are excluded).
    # Used by: list_my_applications(tenant_id, user_id) queries.
    # =================================================================
    op.create_index(
        "ix_applications_tenant_applicant_user",
        "applications",
        ["tenant_id", "applicant_user_id"],
        postgresql_where=sa.text("applicant_user_id IS NOT NULL"),
    )

    # =================================================================
    # STEP 7: Add require_applicant_account column to admission_periods
    #
    # Default false -- existing periods continue to accept anonymous
    # submissions. Schools opt in per-period.
    # =================================================================
    op.add_column(
        "admission_periods",
        sa.Column(
            "require_applicant_account",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="If true, applicants must register/login before submitting",
        ),
    )


def downgrade() -> None:
    # =================================================================
    # Reverse in opposite order of upgrade
    # =================================================================

    # STEP 1: Drop require_applicant_account from admission_periods
    op.drop_column("admission_periods", "require_applicant_account")

    # STEP 2: Drop partial index
    op.drop_index("ix_applications_tenant_applicant_user", table_name="applications")

    # STEP 3: Drop FK constraint
    op.drop_constraint(
        "fk_applications_applicant_user_id",
        "applications",
        type_="foreignkey",
    )

    # STEP 4: Drop applicant_user_id column
    op.drop_column("applications", "applicant_user_id")

    # STEP 5: Restore NOT NULL on date_of_birth, gender, target_class_id
    # Backfill NULLs first to avoid constraint violation
    op.execute(sa.text(
        "UPDATE applications SET date_of_birth = '2000-01-01' "
        "WHERE date_of_birth IS NULL"
    ))
    op.execute(sa.text(
        "UPDATE applications SET gender = 'male' WHERE gender IS NULL"
    ))
    # target_class_id cannot be trivially restored; delete incomplete drafts
    op.execute(sa.text(
        "DELETE FROM applications "
        "WHERE target_class_id IS NULL AND status = 'draft'"
    ))
    op.execute(sa.text(
        "ALTER TABLE applications ALTER COLUMN date_of_birth SET NOT NULL"
    ))
    op.execute(sa.text(
        "ALTER TABLE applications ALTER COLUMN gender SET NOT NULL"
    ))
    op.execute(sa.text(
        "ALTER TABLE applications ALTER COLUMN target_class_id SET NOT NULL"
    ))

    # STEP 6: Restore global unique on users.email, drop tenant-scoped composite
    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_tenant_email"))
    op.execute(sa.text("CREATE UNIQUE INDEX ix_users_email ON users(email)"))

    # STEP 7: PostgreSQL does NOT support removing values from an enum type.
    # The 'applicant' value will remain in the userrole enum after downgrade.
    # This is a known PostgreSQL limitation. To fully remove it, you would
    # need to: create a new enum type without the value, alter the column
    # to use the new type, and drop the old type. This is not worth the
    # complexity for a downgrade path that is unlikely to be used in
    # production.
    #
    # See: https://www.postgresql.org/docs/16/sql-altertype.html
    # "ADD VALUE ... there is no way to remove a value from an enum type."
```

### Migration Notes

**Why `IF NOT EXISTS` on `ADD VALUE`:** If the migration is re-run (e.g., during development), `ADD VALUE` without `IF NOT EXISTS` will fail with `ERROR: enum label "applicant" already exists`. The `IF NOT EXISTS` clause makes the statement idempotent. This clause was added in PostgreSQL 9.3 and is safe for our PostgreSQL 16 target.

**Why `AUTOCOMMIT` is the primary pattern:** `ALTER TYPE ... ADD VALUE` cannot reliably run inside a transaction block in PostgreSQL. While PostgreSQL 12+ relaxes this restriction when the new value is not used in the same transaction, this is fragile -- if any future migration step references the new enum value, or if the Alembic runner configuration changes, the migration will fail with `ERROR: unsafe use of new value "applicant" of enum type userrole`. The `AUTOCOMMIT` pattern is the only universally safe approach and should always be used for enum value additions.

If for some reason `AUTOCOMMIT` is unavailable (e.g., offline/SQL mode), the transactional approach may work as a fallback:

```python
# Fallback (transactional) -- only works if the new value is not referenced
# in the same transaction. Fragile; prefer AUTOCOMMIT above.
def upgrade() -> None:
    op.execute(
        sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'applicant'")
    )
    # ... remaining DDL ...
```

**Why no RLS changes:** Both `applications` and `admission_periods` already have RLS enabled with `tenant_isolation` policies from the `20260303_0100` migration. Adding columns to existing tables does not require new RLS policies -- the existing `USING (tenant_id = get_current_tenant_id())` policy covers all columns automatically.

**Why no GRANT changes:** The `20260303_0100` migration already granted `ALL ON applications` and `ALL ON admission_periods` to `sims_app_user`. Column additions are covered by existing table-level grants.

---

## 1.5 Verify Test Infrastructure

### No Changes Needed

This migration adds columns to existing tables and a new value to an existing enum. It does **not** create new tables.

| Check | Status | Reason |
|-------|--------|--------|
| `TENANT_SCOPED_TABLES` in `conftest.py` | No change | No new tables created |
| `verify_rls.py` | No change | RLS already covers `applications` and `admission_periods` |
| `models/__init__.py` | No change | No new model classes (only new columns on existing models) |
| `admissions/__init__.py` | No change | No new model classes to re-export |

> **Note:** The total `TENANT_SCOPED_TABLES` count in `conftest.py` should be verified at implementation time. Depending on which sprint landed first (messaging, admissions, etc.), the count may be 71 or 72. Cross-reference with the actual table list in the test database after running all migrations.

### Verification Steps

After running the migration, verify with these checks:

```sql
-- 1. Confirm 'applicant' value exists in userrole enum
SELECT unnest(enum_range(NULL::userrole));
-- Should include 'applicant' in the list

-- 2. Confirm tenant-scoped email unique index replaced global unique
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'users' AND indexname = 'uq_users_tenant_email';
-- Should show: CREATE UNIQUE INDEX uq_users_tenant_email ON users(tenant_id, email) WHERE (deleted_at IS NULL)
-- Also confirm the old global index is gone:
SELECT indexname FROM pg_indexes WHERE tablename = 'users' AND indexname = 'ix_users_email';
-- Should return 0 rows

-- 3. Confirm date_of_birth, gender, target_class_id are nullable
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'applications' AND column_name IN ('date_of_birth', 'gender', 'target_class_id');
-- All three should return: is_nullable = YES

-- 4. Confirm applicant_user_id column exists
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'applications' AND column_name = 'applicant_user_id';
-- Should return: applicant_user_id | uuid | YES

-- 5. Confirm partial index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'applications' AND indexname = 'ix_applications_tenant_applicant_user';
-- Should show partial index with WHERE clause

-- 6. Confirm require_applicant_account column exists with default
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'admission_periods' AND column_name = 'require_applicant_account';
-- Should return: require_applicant_account | boolean | NO | false

-- 7. Confirm FK constraint exists
SELECT constraint_name, table_name
FROM information_schema.table_constraints
WHERE constraint_name = 'fk_applications_applicant_user_id';
-- Should return the FK constraint

-- 8. Confirm RLS is still active on both tables
SELECT tablename, rowsecurity, forcerowsecurity
FROM pg_tables
WHERE tablename IN ('applications', 'admission_periods');
-- Both should show: rowsecurity = true, forcerowsecurity = true
```

### Existing Test Compatibility

Existing tests that create `Application` records do not need updating because:
- `applicant_user_id` is nullable -- existing test fixtures that omit it will get `NULL`
- `require_applicant_account` has `server_default="false"` -- existing `AdmissionPeriod` fixtures that omit it will get `false`

No test data migrations are needed.

---

## 1.6 Drop Global Unique on `users.email`, Add Tenant-Scoped Composite Unique

**File:** `backend/app/models/user.py`, migration

### Problem

The existing `User.email` column has `unique=True`, which creates a database-wide unique index (`ix_users_email` or `users_email_key`). This means the same email address cannot exist in two different tenants. For multi-tenant applicant registration, this is a blocking issue -- a parent applying to two different schools (two different tenants) would be rejected on the second registration attempt.

### Change to User Model

Remove `unique=True` from the `email` column definition and add a tenant-scoped composite unique index via `__table_args__`:

**Before:**
```python
class User(Base, TenantMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,      # <-- PROBLEM: global unique
        nullable=False,
        index=True,
    )
```

**After:**
```python
class User(Base, TenantMixin, SoftDeleteMixin):
    __tablename__ = "users"

    __table_args__ = (
        sa.Index(
            "uq_users_tenant_email",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )

    email: Mapped[str] = mapped_column(
        String(255),
        # unique=True removed -- replaced by tenant-scoped composite in __table_args__
        nullable=False,
    )
```

**Why the partial index with `WHERE deleted_at IS NULL`:** Soft-deleted users should not block new registrations. If a user is soft-deleted and a new user registers with the same email in the same tenant, the partial index allows it.

**Why this is safe:** Within a single tenant, email uniqueness is still enforced for active (non-deleted) users. Across tenants, the same email can now exist independently -- which is the correct behavior for multi-tenant SaaS.

### Migration SQL (included in task 1.4 migration)

**upgrade:**
```sql
-- Drop global unique constraint on email
DROP INDEX IF EXISTS ix_users_email;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key;

-- Create tenant-scoped composite unique
CREATE UNIQUE INDEX uq_users_tenant_email ON users(tenant_id, email) WHERE deleted_at IS NULL;
```

**downgrade:**
```sql
DROP INDEX IF EXISTS uq_users_tenant_email;
CREATE UNIQUE INDEX ix_users_email ON users(email);
```

---

## 1.7 Make `date_of_birth`, `gender`, `target_class_id` Nullable on Application

**File:** `backend/app/models/admissions/application.py`, migration

### Problem

Draft applications need to be saved with partial data. A user starting an application may not have filled in the child's date of birth, gender, or target class yet. With the current `NOT NULL` constraints, draft creation would fail unless all three fields are provided upfront.

### Changes to Application Model (task 1.2)

The following column type annotations change from required to optional:

| Column | Before | After |
|--------|--------|-------|
| `date_of_birth` | `Mapped[date]` | `Mapped[date \| None]` |
| `gender` | `Mapped[str]` | `Mapped[str \| None]` |
| `target_class_id` | `Mapped[uuid.UUID]` | `Mapped[uuid.UUID \| None]` |

**Updated column definitions:**
```python
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,  # Changed: was nullable=False
    )
    gender: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,  # Changed: was nullable=False
        comment="male or female",
    )
    # ...
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,  # Changed: was nullable=False
        comment="Class the applicant is applying to",
    )
```

**Service-layer enforcement:** The `NOT NULL` constraint moves to the service layer -- the submit action (Phase 2) must validate that these fields are non-null before transitioning from `draft` to `submitted` status. This is a deliberate trade-off: the database allows partial drafts, but the business logic enforces completeness on submission.

### Migration SQL (included in task 1.4 migration)

**upgrade:**
```sql
ALTER TABLE applications ALTER COLUMN date_of_birth DROP NOT NULL;
ALTER TABLE applications ALTER COLUMN gender DROP NOT NULL;
ALTER TABLE applications ALTER COLUMN target_class_id DROP NOT NULL;
```

**downgrade:**
```sql
-- Restore NOT NULL (only safe if no NULLs exist)
UPDATE applications SET date_of_birth = '2000-01-01' WHERE date_of_birth IS NULL;
UPDATE applications SET gender = 'male' WHERE gender IS NULL;
-- target_class_id cannot be trivially restored; skip or delete drafts first
DELETE FROM applications WHERE target_class_id IS NULL AND status = 'draft';
ALTER TABLE applications ALTER COLUMN date_of_birth SET NOT NULL;
ALTER TABLE applications ALTER COLUMN gender SET NOT NULL;
ALTER TABLE applications ALTER COLUMN target_class_id SET NOT NULL;
```

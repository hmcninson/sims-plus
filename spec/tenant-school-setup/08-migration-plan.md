# Migration Plan

**All Alembic migrations for this implementation, in sequence.**

---

## Migration Chain

```
Current head: 20260302_0100 (messaging_tables)
    │
    ├── 20260322_0100_trial_subscription_fields     (Phase 1A)
    │       └── Adds trial/subscription columns to tenants
    │
    ├── 20260322_0200_school_category_fields         (Phase 3A)
    │       └── Adds category and boarding_type to schools
    │
    └── 20260322_0300_academic_year_archiving         (Phase 3B)
            └── Adds 'archived' to academicyearstatus enum
```

Phases 1B, 2A, 2B, and 4 require NO migrations (pure application logic).

---

## Migration 1: `20260322_0100_trial_subscription_fields`

**Phase:** 1A — Trial & Subscription Enforcement
**Tables affected:** `tenants`
**Reversible:** Yes

### Changes

Since this is a **clean slate** (all existing tenants deleted), the migration is straightforward — no data migration needed.

```python
"""Add trial and subscription enforcement fields to tenants.

Revision ID: 20260322_0100
Revises: 20260302_0100
Create Date: 2026-03-22

Clean slate: no existing tenant data to migrate.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260322_0100"
down_revision = "20260302_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The tenants table may already have trial_ends_at and subscription_end.
    # Check if they exist before adding. If they already exist, this is a no-op.
    # If they don't exist, add them.

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "trial_ends_at" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column(
                "trial_ends_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="When the trial period expires",
            ),
        )

    if "subscription_end" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column(
                "subscription_end",
                sa.Date(),
                nullable=True,
                comment="When the paid subscription expires",
            ),
        )

    if "subscription_start" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column(
                "subscription_start",
                sa.Date(),
                nullable=True,
                comment="When the paid subscription started",
            ),
        )

    # Add index for efficient trial expiration queries
    op.create_index(
        "idx_tenants_trial_expires",
        "tenants",
        ["status", "trial_ends_at"],
        postgresql_where=sa.text("status = 'trial'"),
    )

    # Add index for subscription expiration queries
    op.create_index(
        "idx_tenants_subscription_expires",
        "tenants",
        ["status", "subscription_end"],
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("idx_tenants_subscription_expires", table_name="tenants")
    op.drop_index("idx_tenants_trial_expires", table_name="tenants")

    # Only drop columns we added (check existence)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    for col in ["trial_ends_at", "subscription_start", "subscription_end"]:
        if col in existing_columns:
            op.drop_column("tenants", col)
```

### Post-Migration Verification

```sql
-- Verify columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'tenants'
  AND column_name IN ('trial_ends_at', 'subscription_start', 'subscription_end');

-- Verify indexes
SELECT indexname FROM pg_indexes WHERE tablename = 'tenants' AND indexname LIKE 'idx_tenants_%';
```

---

## Migration 2: `20260322_0200_school_category_fields`

**Phase:** 3A — School Category Fields
**Tables affected:** `schools`
**Reversible:** Yes

```python
"""Add school_category and boarding_type enums and columns to schools.

Revision ID: 20260322_0200
Revises: 20260322_0100
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa

revision = "20260322_0200"
down_revision = "20260322_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    schoolcategory = sa.Enum(
        "public", "private", "international", "faith_based",
        name="schoolcategory",
    )
    schoolcategory.create(op.get_bind(), checkfirst=True)

    boardingtype = sa.Enum(
        "day_only", "boarding_only", "mixed",
        name="boardingtype",
    )
    boardingtype.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column(
        "schools",
        sa.Column(
            "category",
            sa.Enum("public", "private", "international", "faith_based", name="schoolcategory"),
            nullable=True,
            comment="Ownership: public, private, international, faith_based",
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "boarding_type",
            sa.Enum("day_only", "boarding_only", "mixed", name="boardingtype"),
            nullable=True,
            comment="Residential: day_only, boarding_only, mixed",
        ),
    )


def downgrade() -> None:
    op.drop_column("schools", "boarding_type")
    op.drop_column("schools", "category")

    sa.Enum(name="boardingtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="schoolcategory").drop(op.get_bind(), checkfirst=True)
```

### Post-Migration Verification

```sql
-- Verify enum types
SELECT typname, enumlabel
FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname IN ('schoolcategory', 'boardingtype')
ORDER BY typname, enumsortorder;

-- Verify columns
SELECT column_name, udt_name
FROM information_schema.columns
WHERE table_name = 'schools'
  AND column_name IN ('category', 'boarding_type');
```

---

## Migration 3: `20260322_0300_academic_year_archiving`

**Phase:** 3B — Academic Year Archiving
**Tables affected:** `academicyearstatus` enum (no table DDL)
**Reversible:** No (cannot remove enum values in PostgreSQL)

```python
"""Add 'archived' value to academicyearstatus enum.

Revision ID: 20260322_0300
Revises: 20260322_0200
Create Date: 2026-03-22

Note: ALTER TYPE ... ADD VALUE is not transactional in PostgreSQL.
This migration cannot be rolled back (enum values cannot be removed).
"""

from alembic import op

revision = "20260322_0300"
down_revision = "20260322_0200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE academicyearstatus ADD VALUE IF NOT EXISTS 'archived'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL.
    # This is intentionally a no-op.
    # If rollback is needed, the 'archived' value will remain but be unused.
    pass
```

### Post-Migration Verification

```sql
-- Verify 'archived' exists in enum
SELECT enumlabel
FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname = 'academicyearstatus'
ORDER BY enumsortorder;

-- Expected: planning, active, completed, archived
```

---

## Running Migrations

### Development (clean slate):

```bash
# From backend directory
cd backend

# Reset database (clean slate as agreed)
alembic downgrade base
alembic upgrade head

# Or if starting fresh:
# Drop and recreate database, then:
alembic upgrade head
```

### Verify migration chain:

```bash
# Check current head
alembic heads

# Check history
alembic history --verbose

# Expected chain:
# 20260302_0100 → 20260322_0100 → 20260322_0200 → 20260322_0300
```

---

## Test Infrastructure Updates

### File: `backend/tests/conftest.py`

No new tenant-scoped tables are added, so `TENANT_SCOPED_TABLES` list stays at 55 (or current count).

However, the raw SQL in test fixtures for creating tenants must include any new NOT NULL columns if any were added. Since all new columns are **nullable**, no test fixture changes are needed.

### Enum Values in Tests

If tests use raw SQL to create academic years, they can now use `'archived'` as a valid status value.

---

## Rollback Plan

| Migration | Rollback Safety |
|-----------|----------------|
| `20260322_0100` | Safe — drops indexes and columns |
| `20260322_0200` | Safe — drops columns and enums |
| `20260322_0300` | **NOT reversible** — `archived` enum value stays forever. But it's harmless if unused. |

For a full rollback:
```bash
alembic downgrade 20260302_0100
```

This rolls back migrations 1 and 2 (skipping 3's no-op downgrade). The `archived` enum value will persist but won't cause issues.

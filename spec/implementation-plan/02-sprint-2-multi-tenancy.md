# SIMS Plus -- Implementation Plan: Sprint 2

**Document:** 02 of 04
**Version:** 1.0
**Date:** 15 February 2026
**Author:** Harry McNinson
**Status:** Ready for Implementation
**Sprint Window:** 2 weeks (Weeks 3-4)

---

## Sprint 2 Goal

Complete tenant isolation verified by automated tests. Auth system working end-to-end through all 7 defense-in-depth layers. Every tenant-scoped table has hardened RLS policies with zero bypasses.

**Prerequisite:** Sprint 1 is complete. `docker-compose up` starts all services. `init-db.sql` creates `sims_app_user`. Nginx routes wildcard subdomains.

---

## Table of Contents

1. [Task S2-01: Tenants Table and Model Verification](#task-s2-01-tenants-table-and-model-verification)
2. [Task S2-02: Reserved Subdomains Table Verification](#task-s2-02-reserved-subdomains-table-verification)
3. [Task S2-03: RLS Policies Rework (CRITICAL)](#task-s2-03-rls-policies-rework-critical--highest-priority)
4. [Task S2-04: Tenant Context Functions](#task-s2-04-tenant-context-functions)
5. [Task S2-05: Schools Table Verification](#task-s2-05-schools-table-verification)
6. [Task S2-06: Users Table Verification](#task-s2-06-users-table-verification)
7. [Task S2-07: get_db() Tenant Enforcement](#task-s2-07-get_db-tenant-enforcement-high-security)
8. [Task S2-08: Alembic Migration Consolidation](#task-s2-08-alembic-migration-consolidation)
9. [Task S2-09: Next.js proxy.ts Subdomain Detection](#task-s2-09-nextjs-proxyts-subdomain-detection)
10. [Task S2-10: React Tenant Context Provider](#task-s2-10-react-tenant-context-provider)
11. [Task S2-11: Tenant Lookup Caching (Redis)](#task-s2-11-tenant-lookup-caching-redis)
12. [Task S2-12: Multi-Tenant Integration Tests (CRITICAL)](#task-s2-12-multi-tenant-integration-tests-critical)
13. [Task S2-13: API Health Check Enhancement](#task-s2-13-api-health-check-enhancement)
14. [Week-by-Week Summary](#week-by-week-summary)

---

## Task S2-01: Tenants Table and Model Verification

| Field | Value |
|---|---|
| **Task ID** | S2-01 |
| **Priority** | P0 (Day 1) |
| **Effort** | 0.5 days |
| **Owner** | Track B (Backend 1) |
| **Dependencies** | S1-05 (init-db.sql rewrite) |

### Background

The `Tenant` model at `backend/app/models/tenant.py` is the root entity for multi-tenancy. It has **no `tenant_id` column** because it IS the tenant. It must NOT have RLS policies -- it is queried by the `TenantMiddleware` before the tenant context is known.

### Actions

**1. Verify `backend/app/models/tenant.py` matches the required schema.**

The current file uses `SQLEnum(TenantType)` without `values_callable`. This must be corrected to match the project convention (see MEMORY.md: `values_callable=lambda x: [e.value for e in x]`).

**File:** `backend/app/models/tenant.py`

```python
"""
SIMS Plus - Tenant Model

Multi-tenant root entity representing a school or school chain.
"""

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin


class TenantType(str, Enum):
    """Type of tenant."""

    SINGLE_SCHOOL = "single_school"
    SCHOOL_CHAIN = "school_chain"


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""

    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    """Tenant account status."""

    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Tenant(Base, SoftDeleteMixin):
    """
    Tenant model - represents a school or school chain.

    This is the root entity for multi-tenancy.
    All school data is isolated by tenant_id referencing this table.

    SECURITY:
    - NO tenant_id column -- this IS the tenant.
    - NO RLS on this table -- it is queried before tenant context is known.
    - Queried via UnscopedDatabaseSession in middleware and onboarding.
    """

    __tablename__ = "tenants"

    # Basic Information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organization/School chain name",
    )
    subdomain: Mapped[str] = mapped_column(
        String(63),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique subdomain for tenant (e.g., presec, achimota)",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-friendly identifier",
    )
    tenant_type: Mapped[TenantType] = mapped_column(
        SQLEnum(
            TenantType,
            name="tenanttype",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TenantType.SINGLE_SCHOOL,
        nullable=False,
    )

    # Subscription
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(
            SubscriptionTier,
            name="subscriptiontier",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=SubscriptionTier.TRIAL,
        nullable=False,
    )
    status: Mapped[TenantStatus] = mapped_column(
        SQLEnum(
            TenantStatus,
            name="tenantstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TenantStatus.TRIAL,
        nullable=False,
    )
    subscription_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscription_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_students: Mapped[int] = mapped_column(
        Integer, default=50, comment="Max students allowed by plan"
    )
    max_staff: Mapped[int] = mapped_column(
        Integer, default=10, comment="Max staff allowed by plan"
    )
    features: Mapped[dict | None] = mapped_column(
        JSONB,
        default=dict,
        comment="Feature flags: boarding, transport, api_access, etc.",
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON settings for tenant customization",
    )

    # Branding
    logo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="URL to tenant logo"
    )
    primary_color: Mapped[str | None] = mapped_column(
        String(7), nullable=True, default="#1B4F72", comment="Primary brand color (hex)"
    )

    def __repr__(self) -> str:
        return f"<Tenant(name='{self.name}', subdomain='{self.subdomain}')>"
```

**Key changes from current file:**

| Change | Why |
|---|---|
| Added `values_callable` to both `SQLEnum` columns | Match project convention. Ensures DB stores lowercase string values, not Python enum names. |
| Added `TenantStatus` enum and `status` column | Track tenant lifecycle (trial/active/suspended/cancelled) separately from `is_active` flag. |
| Added `max_staff`, `features`, `trial_ends_at` columns | Required by subscription tier enforcement and feature gating. |
| Removed relationships (commented out in current file) | Keep them commented out until the FK references are validated. Relationships use `lazy="raise"` per project convention. |

**2. Verify indexes exist.**

After running `alembic upgrade head`, confirm in psql:

```sql
-- Connect as sims_admin (superuser) for DDL inspection
\c sims_plus sims_admin

-- Check indexes on tenants table
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'tenants';
```

Expected indexes:

| Index Name | Column(s) | Unique |
|---|---|---|
| `tenants_pkey` | `id` | Yes |
| `ix_tenants_subdomain` | `subdomain` | Yes |
| `ix_tenants_slug` | `slug` | Yes |

If any index is missing, create an Alembic migration:

```python
# Only if needed -- check first
op.create_index("ix_tenants_subdomain", "tenants", ["subdomain"], unique=True)
op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
```

**3. Verify NO RLS on tenants table.**

```sql
SELECT tablename, policyname
FROM pg_policies
WHERE tablename = 'tenants';
-- Expected: 0 rows
```

If any policies exist, drop them:

```sql
-- In a migration
ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenants NO FORCE ROW LEVEL SECURITY;
```

### Acceptance Criteria

- [ ] Tenant model matches schema above (enums use `values_callable`)
- [ ] No `tenant_id` column on tenants table (it IS the tenant)
- [ ] `SoftDeleteMixin` applied (provides `deleted_at` column)
- [ ] `ix_tenants_subdomain` unique index exists
- [ ] `ix_tenants_slug` unique index exists
- [ ] Zero RLS policies on `tenants` table
- [ ] `alembic check` shows no drift for tenant-related columns

---

## Task S2-02: Reserved Subdomains Table Verification

| Field | Value |
|---|---|
| **Task ID** | S2-02 |
| **Priority** | P0 (Day 1) |
| **Effort** | 0.5 days |
| **Owner** | Track B (Backend 1) |
| **Dependencies** | S1-05 |

### Background

Reserved subdomains prevent schools from registering subdomains that conflict with system URLs. The reservation must be enforced at three levels: database table (authoritative), Python set in `TenantMiddleware`, and TypeScript set in `proxy.ts`.

### Actions

**1. Verify `backend/app/models/reserved_subdomain.py` exists and is correct.**

The current file at `backend/app/models/reserved_subdomain.py` is correct. It defines `ReservedSubdomain` model and `DEFAULT_RESERVED_SUBDOMAINS` list with 35 entries. No changes needed.

**2. Verify seed data is applied via migration.**

Check that a migration exists to seed the `reserved_subdomains` table. If not, create one.

**File:** `backend/alembic/versions/YYYYMMDD_HHMM_seed_reserved_subdomains.py` (create only if seed migration does not exist)

```python
"""Seed reserved subdomains table.

Revision ID: seed_reserved_subdomains
Revises: <current_head>
"""
from alembic import op
from sqlalchemy import text

revision = "seed_reserved_subdomains"
down_revision = "<current_head>"  # UPDATE to actual current head
branch_labels = None
depends_on = None

RESERVED_SUBDOMAINS = [
    ("www", "Main website"),
    ("app", "Application portal"),
    ("api", "API endpoint"),
    ("admin", "Admin portal"),
    ("mail", "Email services"),
    ("ftp", "FTP services"),
    ("status", "Status page"),
    ("blog", "Blog"),
    ("help", "Help center"),
    ("support", "Support portal"),
    ("docs", "Documentation"),
    ("cdn", "Content delivery"),
    ("assets", "Static assets"),
    ("staging", "Staging environment"),
    ("dev", "Development environment"),
    ("test", "Testing environment"),
    ("demo", "Demo environment"),
    ("sandbox", "Sandbox environment"),
    ("beta", "Beta environment"),
    ("alpha", "Alpha environment"),
    ("portal", "Generic portal"),
    ("login", "Login page"),
    ("register", "Registration page"),
    ("signup", "Signup page"),
    ("dashboard", "Dashboard"),
    ("billing", "Billing portal"),
    ("payments", "Payments"),
    ("webhooks", "Webhook endpoints"),
    ("graphql", "GraphQL endpoint"),
    ("ws", "WebSocket endpoint"),
    ("static", "Static files"),
    ("media", "Media files"),
    ("images", "Image files"),
    ("files", "File storage"),
    ("downloads", "Downloads"),
    ("uploads", "Uploads"),
]


def upgrade() -> None:
    connection = op.get_bind()
    for subdomain, reason in RESERVED_SUBDOMAINS:
        connection.execute(
            text("""
                INSERT INTO reserved_subdomains (id, subdomain, reason, created_at, updated_at)
                VALUES (gen_random_uuid(), :subdomain, :reason, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (subdomain) DO NOTHING
            """),
            {"subdomain": subdomain, "reason": reason},
        )


def downgrade() -> None:
    connection = op.get_bind()
    subdomains = [s[0] for s in RESERVED_SUBDOMAINS]
    for sub in subdomains:
        connection.execute(
            text("DELETE FROM reserved_subdomains WHERE subdomain = :sub"),
            {"sub": sub},
        )
```

**3. Sync the Python set in `backend/app/middleware/tenant.py`.**

The current `RESERVED_SUBDOMAINS` set in `tenant.py` has only 18 entries. It must match the database seed data (35 entries).

**File:** `backend/app/middleware/tenant.py` -- update the `RESERVED_SUBDOMAINS` constant.

Replace the existing set (lines 86-90) with:

```python
# Reserved subdomains -- MUST match database seed data AND frontend/proxy.ts
RESERVED_SUBDOMAINS = {
    "www", "app", "api", "admin", "mail", "ftp", "status", "blog",
    "help", "support", "docs", "cdn", "assets", "staging", "dev",
    "test", "demo", "sandbox", "beta", "alpha", "portal", "login",
    "register", "signup", "dashboard", "billing", "payments",
    "webhooks", "graphql", "ws", "static", "media", "images",
    "files", "downloads", "uploads",
}
```

**4. Sync the TypeScript set in `frontend/proxy.ts`.**

The current `RESERVED_SUBDOMAINS` set in `proxy.ts` has only 18 entries. It must also match.

**File:** `frontend/proxy.ts` -- update the `RESERVED_SUBDOMAINS` constant.

Replace the existing set (lines 17-36) with:

```typescript
// Reserved subdomains -- MUST match database seed data AND backend/middleware/tenant.py
const RESERVED_SUBDOMAINS = new Set([
  "www", "app", "api", "admin", "mail", "ftp", "status", "blog",
  "help", "support", "docs", "cdn", "assets", "staging", "dev",
  "test", "demo", "sandbox", "beta", "alpha", "portal", "login",
  "register", "signup", "dashboard", "billing", "payments",
  "webhooks", "graphql", "ws", "static", "media", "images",
  "files", "downloads", "uploads",
]);
```

### Acceptance Criteria

- [ ] `reserved_subdomains` table has 35+ entries after migration
- [ ] Python `RESERVED_SUBDOMAINS` set in `backend/app/middleware/tenant.py` has 35 entries
- [ ] TypeScript `RESERVED_SUBDOMAINS` set in `frontend/proxy.ts` has 35 entries
- [ ] All three lists are identical
- [ ] `INSERT INTO reserved_subdomains ... ON CONFLICT DO NOTHING` is idempotent (safe to re-run)
- [ ] No RLS on `reserved_subdomains` table (global table, no `tenant_id`)

---

## Task S2-03: RLS Policies Rework (CRITICAL -- HIGHEST PRIORITY)

| Field | Value |
|---|---|
| **Task ID** | S2-03 |
| **Priority** | P0 (Day 1-5) |
| **Effort** | 5 days |
| **Owner** | Track C (Backend 2 / Security Lead) + Tech Lead |
| **Dependencies** | S1-05 (init-db.sql creates sims_app_user) |

### Background

The existing `comprehensive_rls` migration at `backend/alembic/versions/20260104_0500_comprehensive_rls.py` contains two critical vulnerabilities:

1. **NULL bypass** (lines 82-83): `OR (get_current_tenant_id() IS NULL)` -- allows full table access when tenant context is not set (e.g., connection pool reuse, missing middleware). This is Finding F1 (CRITICAL).
2. **Platform admin bypass** (lines 86-87): `OR (current_setting('app.is_platform_admin', true) = 'true')` -- any code or SQL injection that sets this session variable bypasses all tenant isolation. This is Finding F5 (HIGH).

Both bypasses must be removed. The hardened policy uses ONLY `tenant_id = get_current_tenant_id()`. When `get_current_tenant_id()` returns NULL, the comparison `tenant_id = NULL` evaluates to NULL (treated as FALSE by PostgreSQL). Zero rows returned. This is the safe default.

### Actions

**1. Create reusable RLS helper module.**

**File:** `backend/app/db/rls_helpers.py` (NEW)

```python
"""
Reusable RLS helpers for Alembic migrations.

Every migration that creates a new tenant-scoped table MUST call:
    from app.db.rls_helpers import enable_rls_for_table, disable_rls_for_table

    def upgrade():
        # ... create table ...
        enable_rls_for_table(op.get_bind(), 'new_table_name')

    def downgrade():
        disable_rls_for_table(op.get_bind(), 'new_table_name')
        # ... drop table ...

SECURITY INVARIANTS:
- No NULL bypass: when get_current_tenant_id() returns NULL, tenant_id = NULL
  evaluates to NULL (FALSE). Zero rows returned.
- No platform admin bypass: platform admin operations use the sims_admin
  superuser role, not a session variable.
- FORCE ROW LEVEL SECURITY: RLS is enforced even for the table owner.
  This means sims_app_user cannot bypass RLS even if it owns the table.
- Policy targets sims_app_user specifically (not PUBLIC), so superuser
  connections (sims_admin, postgres) are not affected during migrations.
"""

from sqlalchemy import text


def enable_rls_for_table(connection, table_name: str) -> None:
    """Enable hardened RLS with tenant isolation policy on a table.

    Args:
        connection: SQLAlchemy connection (from op.get_bind())
        table_name: Name of the table to protect

    SECURITY: No NULL bypass. No platform admin bypass.
    When get_current_tenant_id() returns NULL, tenant_id = NULL evaluates
    to FALSE. Zero rows returned. Safe default.
    """
    # Drop any existing policies on this table
    connection.execute(text(f"""
        DO $$
        DECLARE
            pol RECORD;
        BEGIN
            FOR pol IN
                SELECT policyname FROM pg_policies WHERE tablename = '{table_name}'
            LOOP
                EXECUTE 'DROP POLICY IF EXISTS ' || pol.policyname || ' ON {table_name}';
            END LOOP;
        END $$;
    """))

    # Enable RLS
    connection.execute(text(
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
    ))

    # FORCE RLS even for table owner (critical for defense-in-depth)
    connection.execute(text(
        f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"
    ))

    # Create hardened policy -- NO bypasses
    # Target sims_app_user specifically so superuser migrations are not blocked
    connection.execute(text(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
        FOR ALL
        TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """))

    # Grant table permissions to app user
    connection.execute(text(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
    ))


def disable_rls_for_table(connection, table_name: str) -> None:
    """Remove RLS from a table (for migration downgrade).

    Args:
        connection: SQLAlchemy connection (from op.get_bind())
        table_name: Name of the table to unprotect
    """
    connection.execute(text(
        f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"
    ))
    connection.execute(text(
        f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"
    ))
    connection.execute(text(
        f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"
    ))
```

**2. Create the hardened RLS migration.**

This migration drops ALL existing RLS policies on ALL tenant-scoped tables and recreates them with the hardened policy. It also drops the `is_platform_admin()` function and the old `current_tenant_id()` function.

**File:** `backend/alembic/versions/YYYYMMDD_HHMM_hardened_rls_policies.py` (NEW)

```python
"""Hardened RLS policies -- remove NULL bypass and platform admin bypass.

Fixes:
- F1 (CRITICAL): Removes OR (get_current_tenant_id() IS NULL) from all policies
- F5 (HIGH): Removes OR (current_setting('app.is_platform_admin', true) = 'true')
- F9 (MEDIUM): Drops old current_tenant_id() function, standardizes on get_current_tenant_id()

After this migration:
- sims_app_user without tenant context sees ZERO rows (safe default)
- sims_app_user with context sees ONLY that tenant's rows
- sims_app_user cannot INSERT with a different tenant_id (WITH CHECK)
- sims_admin (superuser) bypasses RLS for migrations (PostgreSQL built-in behavior)

Revision ID: hardened_rls_policies
Revises: <CURRENT_HEAD>
"""
from alembic import op
from sqlalchemy import text

revision = "hardened_rls_policies"
down_revision = "<CURRENT_HEAD>"  # UPDATE to actual head revision
branch_labels = None
depends_on = None

# ALL tenant-scoped tables in the database.
# This list MUST be kept in sync with backend/tests/conftest.py TENANT_SCOPED_TABLES.
# When adding a new tenant-scoped table, add it here AND in conftest.py.
TENANT_SCOPED_TABLES = [
    # Core
    "schools",
    "users",
    # Students
    "students",
    "guardians",
    "student_guardians",
    # Academic
    "academic_years",
    "terms",
    "classes",
    "class_sections",
    "subjects",
    "class_subjects",
    "grading_scales",
    "grades",
    "assessment_weights",
    "academic_settings",
    "school_holidays",
    # Staff
    "departments",
    "staff",
    # Attendance
    "student_attendance",
    "staff_attendance",
    # Exams
    "exams",
    "exam_subjects",
    "exam_scores",
    "continuous_assessments",
    "term_reports",
    "score_change_log",
    # Timetable
    "class_timetables",
    "timetable_periods",
    # Preschool
    "developmental_domains",
    "developmental_milestones",
    "student_observations",
    "daily_activity_logs",
    "preschool_assessments",
    "preschool_reports",
    # Finance
    "fee_types",
    "fee_structures",
    "fee_items",
    "invoices",
    "invoice_items",
    "payments",
    "scholarships",
    "student_scholarships",
    "scholarship_applications",
    "credit_notes",
    "finance_audit_log",
]


def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: Ensure get_current_tenant_id() function is correct and canonical
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION get_current_tenant_id()
        RETURNS UUID AS $$
        DECLARE
            tenant_str TEXT;
            tenant_uuid UUID;
        BEGIN
            -- Get the setting, with empty string as default if not set
            tenant_str := current_setting('app.current_tenant_id', true);

            -- Return NULL if empty or not set
            IF tenant_str IS NULL OR tenant_str = '' THEN
                RETURN NULL;
            END IF;

            -- Try to cast to UUID safely
            BEGIN
                tenant_uuid := tenant_str::UUID;
                RETURN tenant_uuid;
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL;
            END;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))

    # Step 2: Ensure set_tenant_context() function exists
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, false);
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Step 3: Ensure clear_tenant_context() function exists
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION clear_tenant_context()
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', '', false);
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Step 4: Drop old function names (F9 fix)
    connection.execute(text("DROP FUNCTION IF EXISTS current_tenant_id()"))

    # Step 5: Drop is_platform_admin() function (F5 fix)
    connection.execute(text("DROP FUNCTION IF EXISTS is_platform_admin()"))

    # Step 6: For each tenant-scoped table, drop old policies and create hardened ones
    for table_name in TENANT_SCOPED_TABLES:
        # Check if table exists (some tables may not exist yet in all environments)
        result = connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """), {"table_name": table_name})
        table_exists = result.scalar()

        if not table_exists:
            continue

        # Drop ALL existing policies on this table
        connection.execute(text(f"""
            DO $$
            DECLARE
                pol RECORD;
            BEGIN
                FOR pol IN
                    SELECT policyname FROM pg_policies WHERE tablename = '{table_name}'
                LOOP
                    EXECUTE 'DROP POLICY IF EXISTS ' || pol.policyname || ' ON {table_name}';
                END LOOP;
            END $$;
        """))

        # Enable RLS
        connection.execute(text(
            f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
        ))

        # FORCE RLS even for table owner
        connection.execute(text(
            f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"
        ))

        # Create hardened policy -- NO bypasses
        connection.execute(text(f"""
            CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """))

        # Grant table permissions to app user
        connection.execute(text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
        ))

        # Ensure tenant_id index exists for RLS performance
        connection.execute(text(f"""
            CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant_id
            ON {table_name} (tenant_id)
        """))

    # Step 7: Grant usage on sequences to sims_app_user
    connection.execute(text(
        "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user"
    ))


def downgrade() -> None:
    """Restore old policies (NOT recommended -- only for emergency rollback)."""
    connection = op.get_bind()

    for table_name in TENANT_SCOPED_TABLES:
        result = connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """), {"table_name": table_name})
        table_exists = result.scalar()

        if not table_exists:
            continue

        connection.execute(text(
            f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"
        ))
        connection.execute(text(
            f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"
        ))
        connection.execute(text(
            f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"
        ))

    # Restore old functions (for rollback only)
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION is_platform_admin()
        RETURNS BOOLEAN AS $$
        BEGIN
            RETURN COALESCE(current_setting('app.is_platform_admin', true), 'false') = 'true';
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))
```

**3. Manual verification after migration.**

Run these commands to verify the migration worked correctly:

```sql
-- Connect as sims_app_user (NOT postgres, NOT sims_admin)
\c sims_plus sims_app_user

-- Test 1: No context = no rows
SELECT clear_tenant_context();
SELECT count(*) FROM users;
-- Expected: 0

-- Test 2: No context = no rows from schools
SELECT count(*) FROM schools;
-- Expected: 0

-- Test 3: Set context = see only that tenant's rows
-- (Requires seeded test data -- use sims_admin to insert first)
SELECT set_tenant_context('tenant-a-uuid-here'::UUID);
SELECT count(*) FROM users;
-- Expected: only Tenant A's users

-- Test 4: Cannot insert with wrong tenant_id
SELECT set_tenant_context('tenant-a-uuid-here'::UUID);
INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name, role, status)
VALUES (gen_random_uuid(), 'tenant-b-uuid-here'::UUID, 'cross@test.com', 'hash', 'Cross', 'Tenant', 'teacher', 'active');
-- Expected: ERROR: new row violates row-level security policy

-- Test 5: Verify no NULL bypass or admin bypass in any policy
SELECT tablename, policyname, qual, with_check
FROM pg_policies
WHERE schemaname = 'public';
-- Expected: every policy has ONLY tenant_id = get_current_tenant_id()
-- No IS NULL, no is_platform_admin
```

**4. Verify with pg_policies query.**

```sql
-- Connect as sims_admin (superuser) to inspect policies
\c sims_plus sims_admin

-- List all policies and verify none contain bypasses
SELECT tablename, policyname,
       qual LIKE '%IS NULL%' AS has_null_bypass,
       qual LIKE '%is_platform_admin%' AS has_admin_bypass
FROM pg_policies
WHERE schemaname = 'public';

-- Expected: has_null_bypass = false AND has_admin_bypass = false for ALL rows
```

### Acceptance Criteria

- [ ] No RLS policy contains `IS NULL` bypass anywhere in `USING` or `WITH CHECK`
- [ ] No RLS policy contains `is_platform_admin` bypass
- [ ] `is_platform_admin()` function has been dropped
- [ ] `current_tenant_id()` (old function name) has been dropped
- [ ] `get_current_tenant_id()` is the sole canonical function
- [ ] `set_tenant_context()` and `clear_tenant_context()` functions exist
- [ ] `FORCE ROW LEVEL SECURITY` is set on ALL tenant-scoped tables
- [ ] Policies target `sims_app_user` (not `PUBLIC`)
- [ ] Connecting as `sims_app_user` without context: `SELECT * FROM users` returns 0 rows
- [ ] Connecting as `sims_app_user` without context: `SELECT * FROM schools` returns 0 rows
- [ ] Cannot insert a row with a different `tenant_id` than the current context
- [ ] `alembic upgrade head` succeeds (migration runs as sims_admin superuser)
- [ ] `rls_helpers.py` module exists and is importable

---

## Task S2-04: Tenant Context Functions

| Field | Value |
|---|---|
| **Task ID** | S2-04 |
| **Priority** | P0 (Day 3-5) |
| **Effort** | 2 days |
| **Owner** | Track C (Backend 2) |
| **Dependencies** | S2-03 |

### Background

After S2-03, the canonical function name is `get_current_tenant_id()`. The old `current_tenant_id()` has been dropped. This task ensures the application code and the connection pool are aligned.

### Actions

**1. Standardize on `get_current_tenant_id()` throughout codebase.**

Search for any remaining references to `current_tenant_id()` (without the `get_` prefix):

```bash
grep -r "current_tenant_id" --include="*.py" --include="*.sql" backend/ \
  | grep -v "get_current_tenant_id" \
  | grep -v "__pycache__" \
  | grep -v ".pyc"
```

Replace all occurrences. The init-db.sql currently defines `current_tenant_id()` (line 16). After Sprint 1's S1-05 fix, this should already be `get_current_tenant_id()`. Verify it is.

**2. Add connection pool event listener to prevent context leaking.**

When a connection is returned to the pool and later checked out by a new request, the previous request's `app.current_tenant_id` session variable may still be set. This is a security risk: the new request could see the previous tenant's data before the middleware sets the correct context.

**File:** `backend/app/db/session.py` -- replace entire contents.

```python
"""
SIMS Plus - Database Session Management

Async SQLAlchemy engine and session configuration.

SECURITY:
- Connection pool checkout listener resets tenant context to prevent leaking.
- The application MUST connect as sims_app_user (non-superuser) so RLS is enforced.
- expire_on_commit=False for performance; manual expire_all() after context switch.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Create async engine
# The DATABASE_URL MUST point to sims_app_user (non-superuser) for RLS enforcement.
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE if not settings.DEBUG else 5,
    max_overflow=settings.DATABASE_MAX_OVERFLOW if not settings.DEBUG else 10,
)


# CRITICAL: Reset tenant context when connection is checked out from pool.
# This prevents stale context from a previous request leaking to a new request.
# The listener fires on the sync_engine because asyncpg uses sync connections
# under the hood via greenlet.
@event.listens_for(engine.sync_engine, "checkout")
def _reset_tenant_context_on_checkout(dbapi_connection, connection_record, connection_proxy):
    """Clear tenant context when a connection is checked out from the pool.

    Without this, a connection returned to the pool after handling Tenant A's
    request could be checked out for Tenant B's request with Tenant A's context
    still set. The middleware would set Tenant B's context, but there is a window
    between checkout and middleware execution where the old context is active.

    By clearing on checkout, the worst case is zero rows (NULL context = no match),
    never wrong-tenant rows.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SELECT set_config('app.current_tenant_id', '', false)")
    cursor.close()


# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncSession:
    """Get a new async database session.

    Returns:
        AsyncSession instance
    """
    async with async_session_maker() as session:
        return session
```

**3. Fix onboarding service to set tenant context after tenant creation (F4 fix).**

The onboarding service at `backend/app/services/onboarding.py` inserts into RLS-protected tables (`schools`, `users`) without first setting the tenant context. After the hardened RLS policies, these inserts will fail because the `WITH CHECK` clause will reject rows where `tenant_id != get_current_tenant_id()` (and the context is NULL).

**File:** `backend/app/services/onboarding.py` -- add `set_tenant_context()` call after tenant flush.

Find the section that creates the tenant, flushes, then creates school and admin user. Add the context-setting call between the flush and the school creation:

```python
# After the tenant is created and flushed (so tenant.id is available):
await self.db.flush()

# CRITICAL: Set tenant context for RLS before inserting into tenant-scoped tables.
# Without this, the hardened RLS WITH CHECK clause rejects the inserts.
from app.middleware.tenant import set_db_tenant_context
await set_db_tenant_context(self.db, tenant.id)

# Now create school and admin user (these tables have RLS)
school = School(
    tenant_id=tenant.id,
    # ... rest of school fields ...
)
```

The import should be at the top of the file, not inline. Move it there:

```python
# At the top of backend/app/services/onboarding.py, add:
from app.middleware.tenant import set_db_tenant_context
```

### Acceptance Criteria

- [ ] No references to `current_tenant_id()` exist in codebase (only `get_current_tenant_id()`)
- [ ] Connection pool resets context on checkout (event listener in `session.py`)
- [ ] Onboarding service sets tenant context before inserting into `schools` and `users`
- [ ] Context does not leak between sequential requests (verified by integration test in S2-12)
- [ ] `grep -r "current_tenant_id" --include="*.py" backend/ | grep -v "get_current_tenant_id"` returns zero results (excluding `__pycache__`)

---

## Task S2-05: Schools Table Verification

| Field | Value |
|---|---|
| **Task ID** | S2-05 |
| **Priority** | P0 (Day 1-2) |
| **Effort** | 0.5 days |
| **Owner** | Track B (Backend 1) |
| **Dependencies** | S2-01 |

### Background

The `School` model at `backend/app/models/school.py` uses `TenantMixin` (which provides `tenant_id`). It needs verification for correct indexes, RLS policy (applied by S2-03), and relationship safety.

### Actions

**1. Verify model has `tenant_id` NOT NULL.**

The current `School` model inherits from `TenantMixin` which adds:

```python
tenant_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    nullable=False,
    index=True,
)
```

This is correct. Verify it includes `nullable=False`.

**2. Fix relationships to use `lazy="raise"`.**

The current model at `backend/app/models/school.py` uses `lazy="selectin"` on lines 175-184. Per the project convention (MEMORY.md), all relationships MUST use `lazy="raise"` to prevent accidental lazy loading in async context.

**File:** `backend/app/models/school.py` -- change relationship lazy loading.

Replace:

```python
    # Relationships
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="school",
        lazy="selectin",
    )
    staff_members: Mapped[list["Staff"]] = relationship(
        "Staff",
        back_populates="school",
        lazy="selectin",
    )
```

With:

```python
    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use joinedload() or selectinload() explicitly in queries that need these.
    students: Mapped[list["Student"]] = relationship(
        "Student",
        back_populates="school",
        lazy="raise",
    )
    staff_members: Mapped[list["Staff"]] = relationship(
        "Staff",
        back_populates="school",
        lazy="raise",
    )
```

**3. Verify indexes.**

After migration, verify in psql:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'schools';
```

Expected indexes:

| Index Name | Column(s) | Notes |
|---|---|---|
| `schools_pkey` | `id` | Primary key |
| `ix_schools_tenant_id` | `tenant_id` | RLS performance + FK lookup |
| `ix_schools_slug` | `slug` | URL-friendly lookups |

**4. Verify composite index for common query patterns.**

If the following index does not exist, add it via migration:

```sql
-- Composite index for the most common query: "get all schools for this tenant"
CREATE INDEX IF NOT EXISTS ix_schools_tenant_id_id ON schools (tenant_id, id);

-- Partial unique index for student_id_prefix within a tenant
CREATE UNIQUE INDEX IF NOT EXISTS ix_schools_tenant_student_prefix
ON schools (tenant_id, student_id_prefix) WHERE deleted_at IS NULL;
```

### Acceptance Criteria

- [ ] `School` model has `tenant_id` NOT NULL (via `TenantMixin`)
- [ ] RLS policy exists on `schools` table (verified by S2-03)
- [ ] `lazy="raise"` on all relationships
- [ ] `ix_schools_tenant_id` index exists
- [ ] `ix_schools_slug` index exists

---

## Task S2-06: Users Table Verification

| Field | Value |
|---|---|
| **Task ID** | S2-06 |
| **Priority** | P0 (Day 1-2) |
| **Effort** | 0.5 days |
| **Owner** | Track B (Backend 1) |
| **Dependencies** | S2-01 |

### Background

The `User` model at `backend/app/models/user.py` stores system users. It uses `TenantMixin` for `tenant_id`. The email column is currently globally unique (`unique=True`), which is intentional -- it prevents the same email from being used across tenants.

### Actions

**1. Verify model has `tenant_id` NOT NULL.**

The current `User` model inherits from `TenantMixin`. Verify `nullable=False` is present in the mixin.

**2. Fix relationships to use `lazy="raise"`.**

The current model uses `lazy="selectin"` on line 124. Change it.

**File:** `backend/app/models/user.py` -- change relationship lazy loading.

Replace:

```python
    # Relationships
    staff_profile: Mapped["Staff | None"] = relationship(
        "Staff",
        back_populates="user",
        uselist=False,
        lazy="selectin",
    )
```

With:

```python
    # Relationships
    # lazy="raise" prevents accidental lazy loading in async context.
    # Use joinedload() explicitly in queries that need the staff profile.
    staff_profile: Mapped["Staff | None"] = relationship(
        "Staff",
        back_populates="user",
        uselist=False,
        lazy="raise",
    )
```

**3. Fix UserRole enum to use `values_callable`.**

The current model uses `SQLEnum(UserRole)` without `values_callable`. Per MEMORY.md, the existing `userrole` and `userstatus` enums in the database use UPPERCASE values. However, the current Python enum defines lowercase values (e.g., `"platform_admin"`, `"teacher"`).

**IMPORTANT:** Check the actual database enum values before changing anything:

```sql
SELECT enumlabel FROM pg_enum
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
WHERE pg_type.typname = 'userrole'
ORDER BY enumsortorder;
```

If the database has UPPERCASE values (`PLATFORM_ADMIN`, `TEACHER`, etc.), the Python enum values must match. If the database has lowercase values (`platform_admin`, `teacher`, etc.), the current code is correct.

**If database has lowercase values** (which is the case based on the current Python enum), add `values_callable`:

```python
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name="userrole",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserRole.TEACHER,
        nullable=False,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(
            UserStatus,
            name="userstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserStatus.PENDING,
        nullable=False,
    )
```

**4. Verify account lockout fields exist.**

Confirm these columns exist in the model and database:

| Column | Type | Purpose |
|---|---|---|
| `failed_login_attempts` | Integer, default 0 | Count of failed logins |
| `locked_until` | DateTime (tz), nullable | Lockout expiry |
| `email_verified` | Boolean, default False | Email verification status |
| `email_verified_at` | DateTime (tz), nullable | When email was verified |

All present in current model. No changes needed.

**5. Verify password field stores Argon2id hash.**

The `password_hash` column is `String(255)`. Argon2id hashes are approximately 97 characters. `String(255)` is sufficient. No changes needed.

**6. Uncomment school_id ForeignKey.**

The current model has the FK commented out (line 87). Uncomment it if the `schools` table exists:

```python
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id"),
        nullable=True,
        index=True,
    )
```

### Acceptance Criteria

- [ ] `User` model has `tenant_id` NOT NULL (via `TenantMixin`)
- [ ] RLS policy exists on `users` table (verified by S2-03)
- [ ] `lazy="raise"` on all relationships
- [ ] Email uniqueness constraint is correct (globally unique)
- [ ] Enum columns use `values_callable`
- [ ] Account lockout fields exist (`failed_login_attempts`, `locked_until`)
- [ ] `school_id` FK to `schools.id` is active (not commented out)

---

## Task S2-07: `get_db()` Tenant Enforcement (HIGH SECURITY)

| Field | Value |
|---|---|
| **Task ID** | S2-07 |
| **Priority** | P0 (Day 1-3) |
| **Effort** | 2 days |
| **Owner** | Track C (Backend 2) |
| **Dependencies** | S2-03, S2-04 |

### Background

The current `get_db()` in `backend/app/api/deps.py` (lines 26-59) silently proceeds without tenant context. If `request.state.tenant_id` is `None`, the session is yielded without calling `set_tenant_context()`. With hardened RLS (no NULL bypass), queries return zero rows -- a silent data loss bug (Finding F3).

The fix: raise HTTP 400 for non-public routes without tenant context. Create a separate `get_unscoped_db()` for operations that legitimately do not need tenant context (onboarding, tenant lookup, audit logging).

### Actions

**1. Rewrite `backend/app/api/deps.py`.**

**File:** `backend/app/api/deps.py` -- replace the `get_db` and add `get_unscoped_db`.

The file should be modified to include the following `get_db` and `get_unscoped_db` functions. The rest of the file (JWT validation, permission checking) remains unchanged.

Replace the `get_db` function and add `get_unscoped_db` and `UnscopedDatabaseSession`:

```python
# Paths that don't require tenant context (subset of middleware PUBLIC_PATHS)
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/onboarding/register",
    "/api/v1/onboarding/suggest-subdomain",
    "/api/v1/tenant/check-subdomain",
    "/api/v1/tenant/validate",
}

_PUBLIC_PATH_PREFIXES = (
    "/api/v1/tenant/validate/",
    "/api/v1/tenant/check-subdomain/",
    "/api/v1/onboarding/",
    "/api/v1/auth/register",
    "/api/v1/auth/validate-reset-token",
    "/api/v1/auth/reset-password",
)


def _is_public_path(path: str) -> bool:
    """Check if path doesn't require tenant context."""
    if path in _PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Tenant-scoped database session.

    Sets the PostgreSQL session variable for RLS based on tenant_id
    from request.state (set by TenantMiddleware).

    SECURITY:
    - Raises HTTP 400 if tenant context is missing for non-public API routes.
    - This prevents accidental unscoped queries that would return zero rows
      (silent data loss) with hardened RLS.
    - Always clears tenant context in finally block.
    """
    async with async_session_maker() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)

            if tenant_id:
                await session.execute(
                    text("SELECT set_tenant_context(:tenant_id)"),
                    {"tenant_id": str(tenant_id)},
                )
            else:
                # CRITICAL: Reject non-public API routes without tenant context.
                # This prevents silent zero-row queries with hardened RLS.
                path = request.url.path
                if path.startswith("/api/") and not _is_public_path(path):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tenant context required but not set. Access via school subdomain.",
                    )

            yield session
            await session.commit()
        except HTTPException:
            raise  # Don't rollback for HTTP exceptions we raised intentionally
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                pass  # Best effort cleanup
            await session.close()


async def get_unscoped_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session WITHOUT tenant RLS context.

    Use ONLY for:
    - Tenant lookup in middleware (tenants table has no RLS)
    - Onboarding (creating new tenant + school + admin user)
    - Audit log insertion (audit_logs table has no RLS)
    - Reserved subdomain queries

    SECURITY WARNING:
    With FORCE ROW LEVEL SECURITY and sims_app_user, this session
    CANNOT read/write tenant-scoped tables because tenant_id = NULL
    evaluates to FALSE. It only works for non-RLS tables (tenants,
    reserved_subdomains, audit_logs).
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type aliases for dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
UnscopedDatabaseSession = Annotated[AsyncSession, Depends(get_unscoped_db)]
```

**2. Update any endpoint that uses `UnscopedDatabaseSession`.**

Search for endpoints or services that need unscoped access. These should use `get_unscoped_db` instead of `get_db`:

| File | Function | Why Unscoped |
|---|---|---|
| `backend/app/api/v1/endpoints/auth.py` | Password reset endpoints | Uses token-based auth, not subdomain |
| `backend/app/services/onboarding.py` | `register_school()` | Creates tenant before context exists |
| `backend/app/services/tenant.py` | `validate_subdomain()` | Queries tenants table (no RLS) |
| `backend/app/services/audit.py` | `log_event()` | Audit log table has no RLS |

For the onboarding endpoint, if the router injects `DatabaseSession`, it should switch to `UnscopedDatabaseSession`:

```python
# In the onboarding endpoint file:
from app.api.deps import UnscopedDatabaseSession

@router.post("/register")
async def register_school(
    data: SchoolRegistrationRequest,
    db: UnscopedDatabaseSession,  # Changed from DatabaseSession
):
    service = OnboardingService(db)
    # ... onboarding sets its own context via set_db_tenant_context()
```

### Acceptance Criteria

- [ ] Non-public API routes without tenant context return HTTP 400 with message "Tenant context required but not set."
- [ ] Public routes (`/health`, `/api/v1/onboarding/*`, `/api/v1/tenant/*`) work without tenant context
- [ ] `UnscopedDatabaseSession` type alias is available for injection
- [ ] Onboarding endpoint uses `UnscopedDatabaseSession`
- [ ] No silent failures when tenant context is missing on protected routes
- [ ] `clear_tenant_context()` is called in finally block of both `get_db` and `get_unscoped_db`
- [ ] HTTP exceptions raised by `get_db` do not trigger rollback (they are intentional)

---

## Task S2-08: Alembic Migration Consolidation

| Field | Value |
|---|---|
| **Task ID** | S2-08 |
| **Priority** | P2 (Day 5-7) |
| **Effort** | 2 days |
| **Owner** | Track B (Backend 1) |
| **Dependencies** | S2-01 through S2-06 |

### Background

The project has 30+ Alembic migrations. This task ensures all models are registered for Alembic autogenerate and provides an optional squash script for fresh installations.

### Actions

**1. Update `backend/app/db/base.py` to import ALL models.**

The current file only imports `Tenant` and `User`. All other models are commented out. Alembic's autogenerate relies on all models being imported here.

**File:** `backend/app/db/base.py` -- replace entire contents.

```python
"""
SIMS Plus - Database Base

Import ALL models here for Alembic to detect schema changes.

IMPORTANT: Every new SQLAlchemy model MUST be imported here.
If you create a new model file and forget to import it here,
Alembic autogenerate will not detect the table and will not
create a migration for it.
"""

# Import base model class
from app.models.base import Base  # noqa: F401

# Core models (no tenant_id)
from app.models.tenant import Tenant  # noqa: F401
from app.models.reserved_subdomain import ReservedSubdomain  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

# Tenant-scoped models (all have tenant_id)
from app.models.user import User  # noqa: F401
from app.models.school import School  # noqa: F401
from app.models.student import Student, Guardian, StudentGuardian  # noqa: F401
from app.models.staff import Staff, Department  # noqa: F401
from app.models.academic import (  # noqa: F401
    AcademicYear,
    Term,
    Class,
    ClassSection,
    Subject,
    ClassSubject,
    GradingScale,
    Grade,
    AssessmentWeight,
    AcademicSettings,
    SchoolHoliday,
)
from app.models.exam import (  # noqa: F401
    Exam,
    ExamSubject,
    ExamScore,
    ContinuousAssessment,
    TermReport,
)
from app.models.attendance import StudentAttendance, StaffAttendance  # noqa: F401
from app.models.preschool import (  # noqa: F401
    DevelopmentalDomain,
    DevelopmentalMilestone,
    StudentObservation,
    DailyActivityLog,
    PreschoolAssessment,
    PreschoolReport,
)
from app.models.finance import (  # noqa: F401
    FeeType,
    FeeStructure,
    FeeItem,
    Invoice,
    InvoiceItem,
    Payment,
    Scholarship,
    StudentScholarship,
    ScholarshipApplication,
    CreditNote,
    FinanceAuditLog,
)

__all__ = ["Base"]
```

**NOTE:** If any import fails because a model class name does not match, check the actual model file and adjust the import. For example, the timetable models may exist under a different file or class name. If `backend/app/models/timetable.py` does not exist yet (it does not per the file listing), omit the timetable imports until the file is created. The timetable tables were created via raw SQL migrations, not SQLAlchemy models.

**2. Verify with `alembic check`.**

After updating the imports, run:

```bash
cd backend
alembic check
```

This compares the current database schema against the model metadata. Any drift will be reported. If drift exists, create a migration to resolve it:

```bash
alembic revision --autogenerate -m "sync models with database"
```

**3. Create squash script for FRESH installations only.**

**File:** `backend/scripts/squash_to_baseline.py` (NEW) -- optional, low priority.

```python
"""
Squash all migrations to a single baseline for fresh installations.

USAGE:
    python scripts/squash_to_baseline.py

WARNING:
    Do NOT run this if any shared environment (staging, production) has
    the existing migration chain applied. This is for NEW databases only.

    For existing databases, continue to use the incremental migration chain.
"""
import sys


def main():
    print("Migration squashing is not yet implemented.")
    print("For fresh installations, run: alembic upgrade head")
    print("For existing installations, the incremental chain is preserved.")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### Acceptance Criteria

- [ ] ALL models imported in `backend/app/db/base.py` (no commented-out imports)
- [ ] `alembic check` shows no drift between models and database (or drift is addressed by new migration)
- [ ] Fresh `alembic upgrade head` works on a clean database
- [ ] Existing migration chain is not broken (no squashing of applied migrations)
- [ ] `__all__` exports `Base` for Alembic env.py to use

---

## Task S2-09: Next.js proxy.ts Subdomain Detection

| Field | Value |
|---|---|
| **Task ID** | S2-09 |
| **Priority** | P1 (Day 2-5) |
| **Effort** | 3 days |
| **Owner** | Track D (Frontend) |
| **Dependencies** | S1-04 (Next.js 16 setup), S1-09 (Nginx) |

### Background

The existing `frontend/proxy.ts` is already well-implemented. It extracts subdomains from hostnames, supports development mode (`.localhost`, query params, cookies), validates format, checks reserved subdomains, and sets the `x-subdomain` header and cookie. This task focuses on verification, syncing the reserved list (S2-02), and adding any missing functionality.

### Actions

**1. Sync reserved subdomains list (covered in S2-02).**

Already addressed. Verify the set in `proxy.ts` has all 35 entries.

**2. Verify development mode subdomain detection.**

Test each detection method:

| Method | How to Test | Expected |
|---|---|---|
| `presec.localhost:3000` | Visit URL directly | Subdomain = `presec` |
| `localhost:3000?subdomain=presec` | Add query param | Subdomain = `presec` |
| Cookie fallback | Set `x-subdomain=presec` cookie, visit `localhost:3000` | Subdomain = `presec` |

**3. Add `x-forwarded-host` header support for production reverse proxy.**

When behind Nginx, the original Host header may be rewritten. Add support for `x-forwarded-host`:

**File:** `frontend/proxy.ts` -- modify the `proxy` function to check `x-forwarded-host`.

Find the line:

```typescript
  const hostname = request.headers.get("host") || "";
```

Replace with:

```typescript
  // In production behind Nginx, the original host may be in x-forwarded-host
  const hostname = request.headers.get("x-forwarded-host")
    || request.headers.get("host")
    || "";
```

**4. Verify cookie configuration.**

The current cookie settings are:

```typescript
response.cookies.set("x-subdomain", subdomain, {
  httpOnly: false,    // Client JS can read it (TenantProvider needs this)
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: 60 * 60 * 24,  // 24 hours
});
```

This is correct. `httpOnly: false` is intentional so `TenantProvider` can read the cookie.

**5. Verify the matcher configuration.**

The current matcher excludes static files. Verify it matches all non-static routes:

```typescript
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
```

This is correct. No changes needed.

### Acceptance Criteria

- [ ] Visiting `presec.localhost:3000` sets `x-subdomain` header to `presec`
- [ ] Visiting `localhost:3000?subdomain=presec` sets `x-subdomain` header to `presec`
- [ ] `x-subdomain` cookie is set with correct options
- [ ] Reserved subdomains (e.g., `www.localhost:3000`) do NOT set subdomain
- [ ] Invalid format subdomains (e.g., `ab.localhost:3000` -- too short) do NOT set subdomain
- [ ] Production mode (`presec.simsplus.io`) correctly extracts subdomain
- [ ] `x-forwarded-host` header is checked (for Nginx reverse proxy)
- [ ] Non-public routes without subdomain redirect to `/login?error=no_school`

---

## Task S2-10: React Tenant Context Provider

| Field | Value |
|---|---|
| **Task ID** | S2-10 |
| **Priority** | P1 (Day 3-5) |
| **Effort** | 1.5 days |
| **Owner** | Track D (Frontend) |
| **Dependencies** | S2-09 |

### Background

Two tenant context implementations exist:

1. `frontend/components/providers/TenantProvider.tsx` -- full implementation with API fetching, branding application, and `refreshTenant()` support.
2. `frontend/contexts/tenant-context.tsx` -- simpler implementation that receives tenant data as props from server components.

These should be consolidated. The `TenantProvider` in `components/providers/` is the more complete version and should be the canonical one. The `contexts/tenant-context.tsx` file should be kept for backward compatibility but re-export from the provider.

### Actions

**1. Verify TenantProvider is integrated into root layout.**

**File:** `frontend/app/layout.tsx` -- add TenantProvider to the provider tree.

The current layout wraps children with `ThemeProvider` only. Add `TenantProvider`:

```typescript
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { TenantProvider } from "@/components/providers/TenantProvider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "SIMS Plus",
    template: "%s | SIMS Plus",
  },
  description:
    "School Information Management System Plus - Manage students, staff, academics, and finances in one platform.",
  keywords: [
    "school management",
    "education",
    "student management",
    "school software",
    "SIMS",
    "SaaS",
  ],
  authors: [{ name: "Harry McNinson" }],
  creator: "SIMS Plus",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <ThemeProvider>
          <TenantProvider>
            {children}
            <Toaster position="top-right" richColors />
          </TenantProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

**2. Consolidate `contexts/tenant-context.tsx` to re-export from provider.**

**File:** `frontend/contexts/tenant-context.tsx` -- replace with re-exports.

```typescript
/**
 * SIMS Plus - Tenant Context (Re-export)
 *
 * This file re-exports from the canonical TenantProvider for backward compatibility.
 * New code should import directly from "@/components/providers/TenantProvider".
 */

export {
  TenantProvider,
  useTenant,
  useRequiredTenant,
  type TenantInfo,
  type TenantBranding,
} from "@/components/providers/TenantProvider";

// Backward-compatible hooks
export { useTenant as useTenantData } from "@/components/providers/TenantProvider";

export function useSubdomain(): string | null {
  // Import at usage time to avoid circular dependency
  const { useTenant: useTenantHook } = require("@/components/providers/TenantProvider");
  const { subdomain } = useTenantHook();
  return subdomain;
}

export function useHasTenant(): boolean {
  const { useTenant: useTenantHook } = require("@/components/providers/TenantProvider");
  const { tenant } = useTenantHook();
  return tenant !== null;
}
```

**Alternatively** (simpler approach): update all imports across the codebase from `@/contexts/tenant-context` to `@/components/providers/TenantProvider`, then delete `contexts/tenant-context.tsx`. This is preferred but may touch many files.

**3. Create branded login page that uses tenant info.**

If not already implemented, the login page should show tenant branding.

**File:** `frontend/app/(auth)/login/page.tsx` -- verify or update.

The page should use `useTenant()` to show the school logo and name:

```typescript
"use client";

import { useTenant } from "@/components/providers/TenantProvider";
import Image from "next/image";

export default function LoginPage() {
  const { tenant, isLoading, error } = useTenant();

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md space-y-6 p-8">
        {/* Tenant branding */}
        {isLoading ? (
          <div className="h-16 w-16 mx-auto animate-pulse rounded-full bg-muted" />
        ) : tenant?.branding?.logo_url ? (
          <Image
            src={tenant.branding.logo_url}
            alt={tenant.name}
            width={64}
            height={64}
            className="mx-auto"
          />
        ) : null}

        <h1 className="text-center text-2xl font-bold">
          {tenant?.name || "SIMS Plus"}
        </h1>

        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Login form component goes here */}
      </div>
    </div>
  );
}
```

### Acceptance Criteria

- [ ] `TenantProvider` is in the root layout provider tree
- [ ] Login page shows tenant branding when subdomain is set
- [ ] Login page shows default "SIMS Plus" branding when no subdomain
- [ ] `useTenant()` hook returns `{ tenant, subdomain, isLoading, error, isTenantContext, refreshTenant }`
- [ ] Tenant branding CSS variable (`--tenant-primary-color`) is applied to document
- [ ] `contexts/tenant-context.tsx` re-exports from canonical provider (or is removed with imports updated)

---

## Task S2-11: Tenant Lookup Caching (Redis)

| Field | Value |
|---|---|
| **Task ID** | S2-11 |
| **Priority** | P1 (Day 3-5) |
| **Effort** | 2 days |
| **Owner** | Track C (Backend 2) |
| **Dependencies** | S2-01, Redis running (S1-02) |

### Background

Every request to a tenant subdomain triggers a database query in `TenantMiddleware._get_tenant_by_subdomain()`. This query is:

```sql
SELECT id, subdomain, name, is_active FROM tenants WHERE subdomain = :subdomain AND deleted_at IS NULL
```

For a school with 500 concurrent users making 10 requests/minute each, this is 5,000 queries/minute to the tenants table. Caching in Redis reduces this to at most 1 query per 10 minutes per subdomain.

### Actions

**1. Create centralized cache key module.**

**File:** `backend/app/utils/cache_keys.py` (NEW)

```python
"""
Centralized cache key generation.

ALL Redis keys in SIMS Plus go through this module.
This prevents key collisions and makes it easy to audit all Redis usage.

Key naming convention:
    {namespace}:{identifier}:{sub-identifier}

Tenant-scoped keys MUST include the tenant_id to prevent cross-tenant
cache pollution.
"""


class CacheKeys:
    """Redis cache key generator."""

    # TTL constants (seconds)
    TENANT_LOOKUP_TTL = 600       # 10 minutes
    USER_SESSION_TTL = 900        # 15 minutes
    STUDENT_COUNT_TTL = 300       # 5 minutes
    RATE_LIMIT_TTL = 60           # 1 minute

    @staticmethod
    def tenant_by_subdomain(subdomain: str) -> str:
        """Key for cached tenant lookup by subdomain."""
        return f"tenant:subdomain:{subdomain.lower()}"

    @staticmethod
    def school(tenant_id: str, school_id: str) -> str:
        """Key for cached school data."""
        return f"tenant:{tenant_id}:school:{school_id}"

    @staticmethod
    def user(tenant_id: str, user_id: str) -> str:
        """Key for cached user data."""
        return f"tenant:{tenant_id}:user:{user_id}"

    @staticmethod
    def student_count(tenant_id: str) -> str:
        """Key for cached student count (for limit enforcement)."""
        return f"tenant:{tenant_id}:students:count"

    @staticmethod
    def rate_limit(limit_type: str, identifier: str) -> str:
        """Key for rate limiting."""
        return f"rate_limit:{limit_type}:{identifier}"

    @staticmethod
    def token_blacklist(token_hash: str) -> str:
        """Key for blacklisted JWT token."""
        return f"token_blacklist:{token_hash}"

    @staticmethod
    def user_token_blacklist(user_id: str) -> str:
        """Key for user-level token revocation timestamp."""
        return f"user_token_blacklist:{user_id}"

    @staticmethod
    def invalidate_tenant(subdomain: str) -> str:
        """Key to delete when tenant data changes (admin updates name, etc.)."""
        return f"tenant:subdomain:{subdomain.lower()}"
```

**2. Update TenantMiddleware to use Redis cache.**

**File:** `backend/app/middleware/tenant.py` -- add caching to `_get_tenant_by_subdomain`.

Add Redis import and caching logic. The modification goes inside the `TenantMiddleware` class:

```python
# Add to top of file
import json
import logging

import redis.asyncio as aioredis

from app.config import settings
from app.utils.cache_keys import CacheKeys

logger = logging.getLogger(__name__)
```

Add a Redis connection property and cached lookup method to `TenantMiddleware`:

```python
class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to handle tenant context for multi-tenancy."""

    def __init__(self, app):
        super().__init__(app)
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection (lazy initialization)."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                str(settings.REDIS_URL),
                decode_responses=True,
            )
        return self._redis

    async def _get_tenant_by_subdomain(
        self,
        db: AsyncSession,
        subdomain: str,
    ) -> Optional[dict]:
        """Get tenant by subdomain with Redis cache.

        Cache TTL: 10 minutes. Cache is invalidated when tenant data changes
        (via CacheKeys.invalidate_tenant()).

        Args:
            db: Database session (used on cache miss)
            subdomain: Tenant subdomain

        Returns:
            Tenant dict or None
        """
        subdomain_lower = subdomain.lower()
        cache_key = CacheKeys.tenant_by_subdomain(subdomain_lower)

        # Try cache first
        try:
            redis = await self._get_redis()
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            # Redis failure should not break tenant lookup.
            # Fall through to database query.
            logger.warning("Redis cache read failed for tenant lookup", exc_info=True)

        # Cache miss -- query database
        result = await db.execute(
            text("""
                SELECT id, subdomain, name, is_active
                FROM tenants
                WHERE subdomain = :subdomain
                AND deleted_at IS NULL
            """),
            {"subdomain": subdomain_lower},
        )
        row = result.fetchone()

        if not row:
            return None

        tenant_data = {
            "id": str(row.id),
            "subdomain": row.subdomain,
            "name": row.name,
            "is_active": row.is_active,
        }

        # Write to cache (best effort -- don't fail request if Redis is down)
        try:
            redis = await self._get_redis()
            await redis.setex(
                cache_key,
                CacheKeys.TENANT_LOOKUP_TTL,
                json.dumps(tenant_data),
            )
        except Exception:
            logger.warning("Redis cache write failed for tenant lookup", exc_info=True)

        return tenant_data
```

**3. Add cache invalidation helper.**

When tenant data changes (e.g., admin updates school name, tenant is suspended), the cache must be invalidated.

**File:** `backend/app/utils/cache_keys.py` -- the `invalidate_tenant` key is already defined.

Add a helper function to `backend/app/middleware/tenant.py`:

```python
async def invalidate_tenant_cache(subdomain: str) -> None:
    """Invalidate the cached tenant lookup for a subdomain.

    Call this when tenant data changes (name update, suspension, etc.).
    """
    try:
        redis = aioredis.from_url(str(settings.REDIS_URL), decode_responses=True)
        cache_key = CacheKeys.tenant_by_subdomain(subdomain.lower())
        await redis.delete(cache_key)
        await redis.close()
    except Exception:
        logger.warning(f"Failed to invalidate tenant cache for {subdomain}", exc_info=True)
```

### Acceptance Criteria

- [ ] All Redis keys use `CacheKeys` class (no hardcoded key strings elsewhere)
- [ ] Tenant lookup is cached in Redis for 10 minutes (TTL = 600 seconds)
- [ ] Cache miss falls through to database query transparently
- [ ] Redis failure does not break tenant lookup (graceful degradation)
- [ ] Second request for same subdomain hits cache (< 1ms vs ~5ms for DB query)
- [ ] `invalidate_tenant_cache()` function exists for cache busting
- [ ] Cache key format is `tenant:subdomain:{subdomain}` (lowercase)

---

## Task S2-12: Multi-Tenant Integration Tests (CRITICAL)

| Field | Value |
|---|---|
| **Task ID** | S2-12 |
| **Priority** | P0 (Day 5-10) |
| **Effort** | 5 days |
| **Owner** | QA + Track C (Backend 2) |
| **Dependencies** | S2-03 (RLS hardened), S2-07 (get_db enforcement) |

### Background

Integration tests prove that tenant isolation works at the database level. These tests use the two-engine pattern: an admin engine (superuser, bypasses RLS) for seeding test data, and an app engine (`sims_app_user`, RLS enforced) for running queries that simulate the application.

### Actions

**1. Update `backend/tests/conftest.py` with two-engine pattern.**

The current conftest uses a single engine that inherits `DATABASE_URL` from settings. This likely connects as the superuser, which bypasses RLS. The two-engine pattern is required for meaningful RLS tests.

**File:** `backend/tests/conftest.py` -- replace entire contents.

```python
"""
SIMS Plus - Test Configuration

Two-engine test pattern:
- admin_engine: Connects as sims_admin (superuser). Used for DDL (create/drop tables),
  seeding test data, and verifying data across tenants.
- app_engine: Connects as sims_app_user (non-superuser). RLS is enforced.
  All application-level test queries run through this engine.

IMPORTANT:
- After switching tenant context, always call session.expire_all() to clear
  the ORM identity map. Without this, SQLAlchemy may return cached objects
  from the previous context.
- UUID bind params in raw SQL must use CAST(:param AS uuid) because asyncpg
  sends str params as VARCHAR, which doesn't match uuid columns.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.base import Base
from app.main import app
from app.api.deps import get_db


# Database URLs
# Admin engine: superuser for DDL and seed data (bypasses RLS)
ADMIN_DATABASE_URL = str(settings.DATABASE_URL).replace(
    "/sims_plus", "/sims_plus_test"
)

# App engine: non-superuser for application queries (RLS enforced)
# Replace the username in the URL with sims_app_user
APP_DATABASE_URL = ADMIN_DATABASE_URL.replace(
    "sims_admin:", "sims_app_user:"
).replace(
    "postgres:", "sims_app_user:"
)


# ALL tenant-scoped tables.
# MUST be kept in sync with the hardened_rls_policies migration.
TENANT_SCOPED_TABLES = [
    "schools", "users",
    "students", "guardians", "student_guardians",
    "academic_years", "terms", "classes", "class_sections",
    "subjects", "class_subjects", "grading_scales", "grades",
    "assessment_weights", "academic_settings", "school_holidays",
    "departments", "staff",
    "student_attendance", "staff_attendance",
    "exams", "exam_subjects", "exam_scores",
    "continuous_assessments", "term_reports", "score_change_log",
    "class_timetables", "timetable_periods",
    "developmental_domains", "developmental_milestones",
    "student_observations", "daily_activity_logs",
    "preschool_assessments", "preschool_reports",
    "fee_types", "fee_structures", "fee_items",
    "invoices", "invoice_items", "payments",
    "scholarships", "student_scholarships", "scholarship_applications",
    "credit_notes", "finance_audit_log",
]


# --- Engine fixtures ---

admin_engine = create_async_engine(
    ADMIN_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

app_engine = create_async_engine(
    APP_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

admin_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

app_session_maker = async_sessionmaker(
    app_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def admin_session() -> AsyncGenerator[AsyncSession, None]:
    """Admin database session (superuser, bypasses RLS).

    Use for:
    - Seeding test data across multiple tenants
    - Verifying data across tenants (cross-tenant assertions)
    - DDL operations (create/drop tables)
    """
    async with admin_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def app_session() -> AsyncGenerator[AsyncSession, None]:
    """App database session (sims_app_user, RLS enforced).

    Use for:
    - All application-level queries (simulates the real app)
    - Testing that RLS policies filter correctly
    - Verifying cross-tenant access is blocked
    """
    async with app_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Legacy fixture -- uses admin engine. Prefer admin_session or app_session."""
    async with admin_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with overridden database dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# --- Helper functions ---

async def create_test_tenant(
    admin_session: AsyncSession,
    subdomain: str | None = None,
) -> dict[str, Any]:
    """Create a test tenant via admin session (bypasses RLS).

    Returns dict with tenant info including id.
    """
    tenant_id = uuid4()
    sub = subdomain or f"test{uuid4().hex[:8]}"
    slug = sub

    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active, created_at, updated_at)
            VALUES (
                CAST(:id AS uuid), :subdomain, :slug, :name,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(tenant_id), "subdomain": sub, "slug": slug, "name": f"School {sub}"},
    )
    await admin_session.flush()

    return {"id": tenant_id, "subdomain": sub, "slug": slug, "name": f"School {sub}"}


async def create_test_user(
    admin_session: AsyncSession,
    tenant_id,
    email: str | None = None,
) -> dict[str, Any]:
    """Create a test user via admin session (bypasses RLS).

    Returns dict with user info including id.
    """
    user_id = uuid4()
    user_email = email or f"user-{uuid4().hex[:8]}@test.com"

    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                created_at, updated_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                :fn, :ln, :role, :status,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": user_email,
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash_for_testing",
            "fn": "Test",
            "ln": "User",
            "role": "teacher",
            "status": "active",
        },
    )
    await admin_session.flush()

    return {"id": user_id, "email": user_email, "tenant_id": tenant_id}


async def set_app_tenant_context(app_session: AsyncSession, tenant_id) -> None:
    """Set tenant context on an app session."""
    await app_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_id)},
    )
    app_session.expire_all()  # CRITICAL: clear ORM identity map after context switch


async def clear_app_tenant_context(app_session: AsyncSession) -> None:
    """Clear tenant context on an app session."""
    await app_session.execute(text("SELECT clear_tenant_context()"))
    app_session.expire_all()


@pytest.fixture
def sample_tenant_data() -> dict[str, Any]:
    """Sample tenant data for testing."""
    return {
        "name": "Test School",
        "slug": "test-school",
        "email": "admin@testschool.edu.gh",
        "tenant_type": "single_school",
        "subscription_tier": "professional",
    }


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Sample user data for testing."""
    return {
        "email": "user@testschool.edu.gh",
        "password": "SecurePassword123!",
        "first_name": "Kwame",
        "last_name": "Asante",
        "phone": "0241234567",
        "role": "teacher",
    }
```

**2. Write RLS isolation tests.**

**File:** `backend/tests/test_rls_isolation.py` (NEW)

```python
"""
RLS Isolation Tests

These tests prove that PostgreSQL Row-Level Security correctly isolates
tenant data. They use the two-engine pattern:
- admin_session: superuser, seeds data across tenants
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests MUST run against sims_plus_test database with
RLS policies applied (alembic upgrade head on the test database).
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)


@pytest.mark.asyncio
class TestRLSNoContext:
    """Tests for behavior when NO tenant context is set."""

    async def test_no_context_users_returns_zero_rows(self, app_session, admin_session):
        """Without tenant context, SELECT on users returns 0 rows."""
        # Seed a user via admin
        tenant = await create_test_tenant(admin_session)
        await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Query as app_user WITHOUT context
        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        count = result.scalar()
        assert count == 0, f"Expected 0 rows without context, got {count}"

    async def test_no_context_schools_returns_zero_rows(self, app_session, admin_session):
        """Without tenant context, SELECT on schools returns 0 rows."""
        tenant = await create_test_tenant(admin_session)
        # Insert a school via admin
        await admin_session.execute(
            text("""
                INSERT INTO schools (
                    id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF',
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant["id"]),
                "name": "Test School",
                "slug": f"school-{uuid4().hex[:8]}",
            },
        )
        await admin_session.commit()

        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM schools"))
        count = result.scalar()
        assert count == 0, f"Expected 0 rows without context, got {count}"


@pytest.mark.asyncio
class TestRLSTenantIsolation:
    """Tests for cross-tenant isolation."""

    async def test_tenant_a_cannot_see_tenant_b_users(self, app_session, admin_session):
        """Tenant A's users are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"], "a@test.com")
        user_b = await create_test_user(admin_session, tenant_b["id"], "b@test.com")
        await admin_session.commit()

        # Query as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails = [row[0] for row in result.fetchall()]

        assert user_a["email"] in emails, "Tenant A should see its own user"
        assert user_b["email"] not in emails, "Tenant A must NOT see Tenant B's user"

    async def test_tenant_b_cannot_see_tenant_a_users(self, app_session, admin_session):
        """Tenant B's users are invisible to Tenant A (reverse check)."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Query as Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails = [row[0] for row in result.fetchall()]

        assert user_b["email"] in emails, "Tenant B should see its own user"
        assert user_a["email"] not in emails, "Tenant B must NOT see Tenant A's user"

    async def test_tenant_sees_only_own_count(self, app_session, admin_session):
        """Each tenant sees only its own row count."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # Create 3 users for A, 2 for B
        for _ in range(3):
            await create_test_user(admin_session, tenant_a["id"])
        for _ in range(2):
            await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Tenant A sees 3
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 3

        # Tenant B sees 2
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 2


@pytest.mark.asyncio
class TestRLSInsertProtection:
    """Tests for WITH CHECK clause (insert/update protection)."""

    async def test_cannot_insert_with_wrong_tenant_id(self, app_session, admin_session):
        """Tenant A cannot insert data with Tenant B's tenant_id."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Set context as Tenant A, try to insert with Tenant B's ID
        await set_app_tenant_context(app_session, tenant_a["id"])

        with pytest.raises(Exception) as exc_info:
            await app_session.execute(
                text("""
                    INSERT INTO users (
                        id, tenant_id, email, password_hash,
                        first_name, last_name, role, status,
                        created_at, updated_at
                    ) VALUES (
                        CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                        :fn, :ln, :role, :status,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """),
                {
                    "id": str(uuid4()),
                    "tid": str(tenant_b["id"]),  # WRONG tenant_id
                    "email": f"cross-{uuid4().hex[:6]}@test.com",
                    "pw": "hash",
                    "fn": "Cross",
                    "ln": "Tenant",
                    "role": "teacher",
                    "status": "active",
                },
            )
            await app_session.flush()

        # The error should be an RLS policy violation
        error_msg = str(exc_info.value).lower()
        assert "policy" in error_msg or "permission" in error_msg or "violates" in error_msg

    async def test_can_insert_with_correct_tenant_id(self, app_session, admin_session):
        """Tenant A CAN insert data with its own tenant_id."""
        tenant_a = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])

        # This should succeed
        await app_session.execute(
            text("""
                INSERT INTO users (
                    id, tenant_id, email, password_hash,
                    first_name, last_name, role, status,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),  # CORRECT tenant_id
                "email": f"correct-{uuid4().hex[:6]}@test.com",
                "pw": "hash",
                "fn": "Correct",
                "ln": "Insert",
                "role": "teacher",
                "status": "active",
            },
        )
        # No exception = success


@pytest.mark.asyncio
class TestRLSContextSwitching:
    """Tests for context switching and clearing."""

    async def test_context_cleared_returns_zero_rows(self, app_session, admin_session):
        """After clearing context, queries return 0 rows."""
        tenant = await create_test_tenant(admin_session)
        await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Set context -- should see data
        await set_app_tenant_context(app_session, tenant["id"])
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() > 0, "Should see data with context set"

        # Clear context -- should see 0 rows
        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0, "Should see 0 rows after clearing context"

    async def test_context_switch_between_tenants(self, app_session, admin_session):
        """Switching from Tenant A to Tenant B changes visible data."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"], "switch-a@test.com")
        user_b = await create_test_user(admin_session, tenant_b["id"], "switch-b@test.com")
        await admin_session.commit()

        # Context = Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails_a = [row[0] for row in result.fetchall()]
        assert user_a["email"] in emails_a
        assert user_b["email"] not in emails_a

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails_b = [row[0] for row in result.fetchall()]
        assert user_b["email"] in emails_b
        assert user_a["email"] not in emails_b

    async def test_invalid_uuid_context_returns_zero_rows(self, app_session):
        """Setting an invalid UUID as context returns 0 rows (not an error)."""
        await app_session.execute(
            text("SELECT set_config('app.current_tenant_id', 'not-a-uuid', false)")
        )
        app_session.expire_all()

        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0

    async def test_nonexistent_tenant_id_returns_zero_rows(self, app_session):
        """Setting a valid UUID that doesn't match any tenant returns 0 rows."""
        fake_tenant_id = uuid4()
        await set_app_tenant_context(app_session, fake_tenant_id)
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0
```

**3. Write tenant middleware tests.**

**File:** `backend/tests/test_tenant_middleware.py` (NEW)

```python
"""
Tenant Middleware Tests

Tests for subdomain extraction, validation, and tenant context setting.
"""

import pytest
from app.middleware.tenant import (
    extract_subdomain_from_host,
    is_public_path,
    RESERVED_SUBDOMAINS,
)


class TestSubdomainExtraction:
    """Tests for extract_subdomain_from_host()."""

    def test_production_subdomain(self):
        assert extract_subdomain_from_host("presec.simsplus.io") == "presec"

    def test_production_with_port(self):
        assert extract_subdomain_from_host("presec.simsplus.io:443") == "presec"

    def test_localhost_subdomain(self):
        assert extract_subdomain_from_host("presec.localhost") == "presec"

    def test_localhost_with_port(self):
        assert extract_subdomain_from_host("presec.localhost:3000") == "presec"

    def test_bare_localhost_returns_none(self):
        assert extract_subdomain_from_host("localhost") is None

    def test_bare_localhost_with_port_returns_none(self):
        assert extract_subdomain_from_host("localhost:3000") is None

    def test_reserved_subdomain_returns_none(self):
        assert extract_subdomain_from_host("www.simsplus.io") is None
        assert extract_subdomain_from_host("api.simsplus.io") is None
        assert extract_subdomain_from_host("admin.simsplus.io") is None

    def test_reserved_subdomain_localhost_returns_none(self):
        assert extract_subdomain_from_host("www.localhost") is None
        assert extract_subdomain_from_host("api.localhost") is None

    def test_too_short_subdomain_returns_none(self):
        # Subdomains must be >= 4 characters
        assert extract_subdomain_from_host("ab.simsplus.io") is None
        assert extract_subdomain_from_host("abc.simsplus.io") is None

    def test_minimum_length_subdomain(self):
        assert extract_subdomain_from_host("abcd.simsplus.io") == "abcd"

    def test_hyphenated_subdomain(self):
        assert extract_subdomain_from_host("st-johns.simsplus.io") == "st-johns"

    def test_uppercase_normalized_to_lowercase(self):
        assert extract_subdomain_from_host("PRESEC.simsplus.io") == "presec"

    def test_ip_address_returns_none(self):
        assert extract_subdomain_from_host("127.0.0.1") is None
        assert extract_subdomain_from_host("127.0.0.1:8000") is None


class TestPublicPaths:
    """Tests for is_public_path()."""

    def test_health_is_public(self):
        assert is_public_path("/health") is True

    def test_docs_is_public(self):
        assert is_public_path("/docs") is True

    def test_tenant_validation_is_public(self):
        assert is_public_path("/api/v1/tenant/validate/presec") is True

    def test_onboarding_is_public(self):
        assert is_public_path("/api/v1/onboarding/register") is True

    def test_students_is_not_public(self):
        assert is_public_path("/api/v1/students") is False

    def test_users_is_not_public(self):
        assert is_public_path("/api/v1/users") is False


class TestReservedSubdomains:
    """Tests for reserved subdomain list completeness."""

    def test_minimum_count(self):
        assert len(RESERVED_SUBDOMAINS) >= 35

    def test_critical_subdomains_reserved(self):
        critical = {"www", "api", "admin", "app", "mail", "cdn", "status"}
        assert critical.issubset(RESERVED_SUBDOMAINS)
```

### Acceptance Criteria

- [ ] At least 10 RLS isolation tests pass (target: 12+)
- [ ] Cross-tenant access is provably prevented (Tenant A cannot see Tenant B's data)
- [ ] NULL context test passes (no context = 0 rows)
- [ ] Wrong `tenant_id` INSERT is rejected by `WITH CHECK` clause
- [ ] Context clearing works (set context, clear, verify 0 rows)
- [ ] Context switching works (switch from A to B, verify B's data only)
- [ ] All tests run with `sims_app_user` (app_engine), not postgres
- [ ] Two-engine test pattern is established in conftest.py
- [ ] Test helper functions (`create_test_tenant`, `create_test_user`, etc.) are reusable
- [ ] Subdomain extraction tests pass (12+ tests)
- [ ] `TENANT_SCOPED_TABLES` list in conftest.py matches the hardened RLS migration

---

## Task S2-13: API Health Check Enhancement

| Field | Value |
|---|---|
| **Task ID** | S2-13 |
| **Priority** | P2 (Day 6-8) |
| **Effort** | 1 day |
| **Owner** | Track B (Backend 1) |
| **Dependencies** | S2-04 |

### Background

The health endpoint should verify that all critical dependencies are reachable. Currently it likely just returns `{"status": "ok"}`. It should check database connectivity, Redis connectivity, and optionally report the current Alembic revision.

### Actions

**1. Find and update the health endpoint.**

Locate the health check endpoint. It may be in `backend/app/api/v1/endpoints/` or registered directly in `main.py`.

**File:** Create or update the health endpoint to include dependency checks.

```python
# In the appropriate endpoint file (e.g., backend/app/api/v1/endpoints/health.py)

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db.session import async_session_maker

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns status of all critical dependencies.
    Does NOT require tenant context (public path).

    Returns:
        200 if all checks pass
        503 if any check fails
    """
    checks = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {},
    }

    # Database check
    try:
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["status"] = "unhealthy"
        checks["checks"]["database"] = f"error: {type(e).__name__}"

    # Redis check
    try:
        redis = aioredis.from_url(str(settings.REDIS_URL))
        await redis.ping()
        await redis.close()
        checks["checks"]["redis"] = "ok"
    except Exception as e:
        checks["status"] = "unhealthy"
        checks["checks"]["redis"] = f"error: {type(e).__name__}"

    # Alembic revision check (optional, best effort)
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.fetchone()
            checks["checks"]["migration"] = row[0] if row else "no revision"
    except Exception:
        checks["checks"]["migration"] = "unable to check"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)
```

**2. Ensure `/health` is registered and does NOT require tenant context.**

Verify that `/health` is in the `PUBLIC_PATHS` set in both:
- `backend/app/middleware/tenant.py` (already there)
- `backend/app/api/deps.py` `_PUBLIC_PATHS` (already there after S2-07)

### Acceptance Criteria

- [ ] `GET /health` returns database connectivity status
- [ ] `GET /health` returns Redis connectivity status
- [ ] `GET /health` returns current Alembic migration revision
- [ ] Returns HTTP 200 when all checks pass
- [ ] Returns HTTP 503 when any check fails
- [ ] Does not require tenant context (public path)
- [ ] Response includes `version` and `environment` fields

---

## Week-by-Week Summary

### Week 3 Plan

| Day | Track A (DevOps) | Track B (Backend 1) | Track C (Backend 2 / Security) | Track D (Frontend) |
|---|---|---|---|---|
| **11** | S2-13 (Health checks) | S2-01 (Verify tenants table) | S2-03 (RLS migration -- Day 1) | S2-09 (Verify proxy.ts) |
| **12** | Infrastructure monitoring | S2-02 (Reserved subdomains sync) | S2-03 (RLS testing -- Day 2) | S2-09 (x-forwarded-host, reserved list) |
| **13** | Documentation | S2-05 (Verify schools table) | S2-04 (Context functions, pool listener) | S2-09 (Development mode testing) |
| **14** | Integration support | S2-06 (Verify users table) | S2-07 (get_db enforcement) | S2-10 (TenantProvider in layout) |
| **15** | Bug fixes | S2-08 (db/base.py imports) | S2-07 (continued) + S2-11 (Redis cache) | S2-10 (Login page branding) |

### Week 4 Plan

| Day | Track A (DevOps) | Track B (Backend 1) | Track C (Backend 2 / Security) | Track D (Frontend) |
|---|---|---|---|---|
| **16** | Bug fixes | S2-08 (Alembic check) | S2-11 (Redis cache, continued) | Integration testing |
| **17** | Performance testing | S2-11 (Cache invalidation) | S2-12 (Integration tests -- Day 1) | Cross-origin debugging |
| **18** | Security review | Bug fixes | S2-12 (Integration tests -- Day 2) | Bug fixes |
| **19** | Sprint review prep | Sprint review prep | S2-12 (Integration tests -- Day 3) | Sprint review prep |
| **20** | **Sprint 2 Review** | **Sprint 2 Review** | **Sprint 2 Review** | **Sprint 2 Review** |

### Sprint 2 Exit Criteria

**CRITICAL (must pass before Sprint 2 is complete):**

- [ ] All tenant-scoped tables have RLS policies (verified by `SELECT * FROM pg_policies WHERE schemaname = 'public'`)
- [ ] Connect as `sims_app_user` without context: `SELECT * FROM users` returns 0 rows
- [ ] Connect as `sims_app_user` without context: `SELECT * FROM schools` returns 0 rows
- [ ] Set context to Tenant A: only Tenant A users are visible
- [ ] Set context to Tenant A: `INSERT ... VALUES (Tenant_B_ID)` is REJECTED
- [ ] No RLS policy contains `IS NULL` bypass or `is_platform_admin` bypass
- [ ] `get_db()` raises HTTP 400 on non-public route without tenant context
- [ ] `clear_tenant_context()` called reliably after every request (in finally block)
- [ ] At least 10 integration tests for multi-tenant isolation pass

**HIGH (must pass):**

- [ ] Connection pool checkout resets tenant context (event listener)
- [ ] Next.js proxy.ts extracts subdomain from Host header
- [ ] TenantProvider fetches and provides tenant data to client components
- [ ] Tenant lookup cached in Redis with 10-minute TTL
- [ ] All existing tests continue to pass (no regressions)
- [ ] `backend/app/db/base.py` imports ALL models
- [ ] `/health` endpoint checks database and Redis connectivity

**MEDIUM (should pass, can defer to Sprint 3 if needed):**

- [ ] `alembic check` shows no model-database drift
- [ ] Reserved subdomains synced across database, Python, and TypeScript (35 entries each)
- [ ] Onboarding service sets tenant context before inserting into RLS-protected tables
- [ ] Cache invalidation helper exists for tenant data changes

### Deferrals to Sprint 3-4

| Component | Why It Can Wait |
|---|---|
| Migration consolidation / squash script | Not blocking functionality. 30+ migrations still work. |
| Full monitoring (Prometheus/Grafana) | Sentry + CloudWatch sufficient for dev/staging. |
| Terraform IaC for EKS | Docker Compose sufficient for development. |
| CORS wildcard subdomain production config | `X-Subdomain` header works in development. Addressed when deploying to staging. |
| Celery worker tenant context | No background jobs in Sprint 1-2. |
| E2E tests (Playwright) | Unit + integration tests are sufficient for Sprint 2. |

---

*End of Document 02. See `03-technical-reference.md` for code patterns and SQL templates. See `04-testing-and-quality.md` for the full testing strategy.*

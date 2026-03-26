# Phase 1: Infrastructure

**Complexity:** Small-Medium
**Dependencies:** None
**Estimated effort:** 2 days

---

## Summary

Set up the database infrastructure for platform admin: seed the platform tenant, create the audit log table, define the audit log model, and build a CLI command to create the first platform admin user.

---

## Task 1: Create the Migration

### New File: `backend/alembic/versions/20260326_0100_platform_admin_infrastructure.py`

**Chain:** Latest head → `20260326_0100`

Before writing, verify the current migration head:
```bash
cd backend && alembic heads
```

The migration has 3 parts:

#### Part 1: Seed the Platform Tenant

```python
"""Platform admin infrastructure: platform tenant seed + audit log table.

Revision ID: 20260326_0100
Revises: <current_head>
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260326_0100"
down_revision = "<current_head>"  # Set to actual head
branch_labels = None
depends_on = None

# Well-known UUID for the platform tenant (used in CLI, tests, and deps.py)
PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ============================================================
    # 1. Seed platform tenant
    # ============================================================
    # The _platform subdomain is deliberately invalid per SUBDOMAIN_PATTERN
    # (starts with underscore), so it cannot be registered or routed to
    # via normal subdomain extraction.
    op.execute(f"""
        INSERT INTO tenants (
            id, name, subdomain, slug, tenant_type, subscription_tier,
            status, is_active, max_students, max_staff,
            created_at, updated_at
        ) VALUES (
            '{PLATFORM_TENANT_ID}',
            'SIMS Plus Platform',
            '_platform',
            '_platform',
            'single_school',
            'enterprise',
            'active',
            true,
            0,
            999999,
            NOW(), NOW()
        ) ON CONFLICT (subdomain) DO NOTHING
    """)

    # ============================================================
    # 2. Create platform_audit_log table
    # ============================================================
    # This table has NO tenant_id and NO RLS.
    # Access is controlled at the application layer via platform admin auth.
    op.create_table(
        "platform_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_entity_type", sa.String(50), nullable=True),
        sa.Column("target_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Indexes for platform_audit_log
    op.create_index("idx_platform_audit_actor",
                    "platform_audit_log", ["actor_user_id"])
    op.create_index("idx_platform_audit_target_tenant",
                    "platform_audit_log", ["target_tenant_id"])
    op.create_index("idx_platform_audit_created",
                    "platform_audit_log", ["created_at"])

    # NO RLS on platform_audit_log — this is intentional.
    # The table has no tenant_id. Access is controlled at the API layer.
    # SECURITY: sims_app_user gets INSERT only (for writing audit entries).
    # SELECT is NOT granted to sims_app_user — reading the audit log goes
    # through the superuser engine (PlatformService.get_audit_log uses
    # get_platform_admin_session_maker). This prevents a SQL injection in
    # any school-scoped endpoint from reading platform admin activities.
    op.execute("GRANT INSERT ON platform_audit_log TO sims_app_user")


def downgrade() -> None:
    op.drop_index("idx_platform_audit_created", table_name="platform_audit_log")
    op.drop_index("idx_platform_audit_target_tenant", table_name="platform_audit_log")
    op.drop_index("idx_platform_audit_actor", table_name="platform_audit_log")
    op.drop_table("platform_audit_log")
    op.execute(f"DELETE FROM tenants WHERE id = '{PLATFORM_TENANT_ID}'")
```

**Key points:**
- The platform tenant uses a **well-known UUID** (`00000000-0000-0000-0000-000000000001`) so it can be referenced in code without a DB lookup.
- `ON CONFLICT (subdomain) DO NOTHING` makes the migration idempotent.
- `platform_audit_log` has NO RLS and NO `tenant_id` column. It is a global audit table for platform-level operations only.
- `sims_app_user` gets `INSERT` only on the audit log — entries are immutable and reading is restricted to the superuser engine (via PlatformService).

---

## Task 2: Create the Platform Audit Log Model

### New File: `backend/app/models/platform_audit.py`

```python
"""
Platform audit log model.

Records all platform admin actions: login, tenant CRUD, impersonation.
This table has NO tenant_id and NO RLS — it is a global audit table.
Access is controlled at the API layer via PlatformAdminUser dependency.
"""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class PlatformAuditLog(Base):
    """
    Immutable audit trail for platform admin operations.

    NOT tenant-scoped (no TenantMixin). This is intentional —
    platform operations span multiple tenants.
    """

    __tablename__ = "platform_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
        comment="Platform admin user who performed the action",
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Action type: login, tenant_create, tenant_suspend, impersonate, etc.",
    )
    target_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="Tenant affected by the action (NULL for non-tenant actions like login)",
    )
    target_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Entity type affected: tenant, user, school (NULL for login/analytics)",
    )
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="Entity ID affected (NULL for login/analytics)",
    )
    details: Mapped[dict | None] = mapped_column(
        JSONB(), nullable=True,
        comment="Additional context (e.g., changes made, reason for suspension)",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
        comment="Client IP address (IPv4 or IPv6)",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text(), nullable=True,
        comment="Client user-agent string",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
```

**Action values (standardized strings):**

| Action | Description |
|--------|-------------|
| `platform_login` | Platform admin logged in |
| `platform_logout` | Platform admin logged out |
| `tenant_create` | New tenant created |
| `tenant_update` | Tenant details updated (subscription, limits) |
| `tenant_suspend` | Tenant suspended |
| `tenant_activate` | Tenant activated |
| `impersonate_start` | Platform admin entered a tenant's context |
| `analytics_view` | Platform admin viewed analytics |
| `platform_admin_create` | New platform admin user created (via CLI) |

### Register in models/__init__.py

Read `backend/app/models/__init__.py` first, then add:

```python
from app.models.platform_audit import PlatformAuditLog
```

And add `"PlatformAuditLog"` to `__all__`.

---

## Task 3: Add Platform Tenant ID Constant

### File: `backend/app/config.py`

Add to the Settings class (read file first to find the right location):

```python
# Platform Admin
PLATFORM_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"
PLATFORM_IMPERSONATION_EXPIRY_MINUTES: int = 30
```

This well-known UUID is the same one used in the migration seed. It avoids a DB lookup every time we need to identify the platform tenant.

---

## Task 4: Create the Platform Admin CLI Command

### New File: `backend/app/cli/create_platform_admin.py`

```python
"""
CLI command to create a platform admin user.

Usage:
    python -m app.cli.create_platform_admin \
        --email admin@simsplus.io \
        --first-name Harry \
        --last-name McNinson

The password will be prompted interactively (not passed as argument).

This script:
1. Connects to the database using the same DATABASE_URL as the app
2. Sets tenant context to the platform tenant UUID
3. Creates a User with role=platform_admin, tenant_id=<platform_tenant_id>
4. The user is created with status=ACTIVE and email_verified=True
   (platform admins are created by operators, not self-registered)
5. MFA is NOT enabled on creation — the platform login endpoint
   will enforce MFA setup on first login

Requirements:
- The platform tenant must already exist (run migration first)
- The email must not already be in use
"""

import argparse
import asyncio
import getpass
import sys
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.user import User, UserRole, UserStatus


PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{}|;:,.<>?])'
)


async def create_platform_admin(
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> None:
    """Create a platform admin user in the database."""
    platform_tenant_id = settings.PLATFORM_TENANT_ID

    async with async_session_maker() as session:
        # 1. Verify platform tenant exists
        result = await session.execute(
            text("SELECT id FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": platform_tenant_id},
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            print("ERROR: Platform tenant not found. Run migrations first:")
            print("  alembic upgrade head")
            sys.exit(1)

        # 2. Set tenant context for RLS
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": platform_tenant_id},
        )

        # 3. Check email uniqueness (within platform tenant)
        result = await session.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == platform_tenant_id,
                User.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none():
            print(f"ERROR: A platform admin with email {email} already exists.")
            sys.exit(1)

        # 4. Create the user
        user = User(
            tenant_id=platform_tenant_id,
            email=email.lower(),
            first_name=first_name,
            last_name=last_name,
            password_hash=hash_password(password),
            role=UserRole.PLATFORM_ADMIN,
            status=UserStatus.ACTIVE,
            email_verified=True,
            mfa_enabled=False,  # MFA setup enforced on first login
        )
        session.add(user)
        await session.commit()

        print(f"Platform admin created successfully:")
        print(f"  Email: {email}")
        print(f"  Name: {first_name} {last_name}")
        print(f"  Tenant ID: {platform_tenant_id}")
        print(f"  Role: platform_admin")
        print(f"  Status: active")
        print()
        print("IMPORTANT: MFA setup will be required on first login.")


def main():
    parser = argparse.ArgumentParser(description="Create a platform admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--first-name", required=True, help="First name")
    parser.add_argument("--last-name", required=True, help="Last name")
    args = parser.parse_args()

    # Prompt for password interactively
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            continue
        if not PASSWORD_PATTERN.match(password):
            print("Password must include uppercase, lowercase, digit, and special character.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue
        break

    asyncio.run(create_platform_admin(
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        password=password,
    ))


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
cd backend
python -m app.cli.create_platform_admin \
    --email admin@simsplus.io \
    --first-name Harry \
    --last-name McNinson
```

---

## Task 5: Update .env.example

Add the platform tenant ID and impersonation expiry:

```bash
# Platform Admin
PLATFORM_TENANT_ID=00000000-0000-0000-0000-000000000001
PLATFORM_IMPERSONATION_EXPIRY_MINUTES=30
```

---

## Task 6: Add Startup Health Check for Platform Tenant

### File: `backend/app/main.py`

In the application lifespan (or startup event), add a check that the platform tenant exists. This catches accidental deletion or failed migrations early rather than at first platform admin login.

```python
# In the lifespan or startup event, after DB engine is ready:
async with async_session_maker() as session:
    result = await session.execute(
        text("SELECT id FROM tenants WHERE id = CAST(:tid AS uuid)"),
        {"tid": settings.PLATFORM_TENANT_ID},
    )
    if not result.scalar_one_or_none():
        logger.warning(
            "platform_tenant_missing",
            platform_tenant_id=settings.PLATFORM_TENANT_ID,
            message="Platform tenant row not found. Platform admin features will not work. "
                    "Run 'alembic upgrade head' to create it.",
        )
```

**Why:** If the platform tenant seed row is accidentally deleted, platform admin login fails silently with "Invalid email or password" (the user query returns zero rows). This startup check surfaces the problem immediately in logs.

**Important:** This is a WARNING, not a crash. The application should still start -- school operations are unaffected.

---

## Risk Note: reserved_subdomains Database Table

The `reserved_subdomains` database table (seeded via migration `20260215_0200`) contains an "admin" entry. This spec removes "admin" from the in-memory `RESERVED_SUBDOMAINS` sets in `tenant.py` and `proxy.ts` (Phase 2/3) but does NOT remove it from the database table.

**This is intentional.** The database table is used by the onboarding service to prevent schools from registering "admin" as their subdomain. The in-memory sets are used by the middleware/proxy for request routing. These are separate concerns:
- Routing: "admin" should resolve to the platform admin portal (removed from in-memory set)
- Registration: "admin" should remain reserved so no school can register it (kept in DB table)

---

## Verification Checklist

- [ ] Migration runs cleanly: `alembic upgrade head`
- [ ] Platform tenant exists: `SELECT * FROM tenants WHERE subdomain = '_platform'`
- [ ] Platform tenant has the well-known UUID: `id = '00000000-0000-0000-0000-000000000001'`
- [ ] `platform_audit_log` table exists with correct columns
- [ ] `platform_audit_log` has NO RLS policy: `SELECT * FROM pg_policies WHERE tablename = 'platform_audit_log'` returns empty
- [ ] `sims_app_user` has SELECT, INSERT on `platform_audit_log`
- [ ] CLI creates platform admin: `python -m app.cli.create_platform_admin --email test@simsplus.io --first-name Test --last-name Admin`
- [ ] Created user has `role=platform_admin`, `tenant_id=<platform_tenant_id>`, `status=active`
- [ ] Created user is invisible to other tenants (set tenant context to another tenant, query users — platform admin should not appear)
- [ ] Duplicate email rejected by CLI
- [ ] Weak password rejected by CLI
- [ ] Downgrade works: `alembic downgrade -1` removes table and tenant row

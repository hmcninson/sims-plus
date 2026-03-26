# Migration Plan: User Management & Access Control

**Single Migration File:** `backend/alembic/versions/20260325_0100_user_mgmt_access_control.py`
**Revises:** `20260324_0100` (arkesel_migration — see separate Arkesel migration above)
**Down revision:** Partial rollback (columns can be dropped; enum value addition is irreversible)

---

## Arkesel SMS Migration (SEPARATE, preceding migration)

The smsprovider enum migration from `09-arkesel-sms-migration.md` must be a **separate** migration file: `20260324_0100_arkesel_migration.py` (revises: `20260322_0300`). This migration changes the default SMS provider and enum. It MUST run before the main migration below.

See `09-arkesel-sms-migration.md` for the full Arkesel migration details.

---

## Why a Single Migration (for Phases 1-4)

All schema changes for Phases 1-4 are combined into one migration for simplicity:
- All changes are additive (new columns, new table, new enum value)
- No data transformation required
- Can be applied in a single transaction
- Rollback is straightforward for everything except the enum addition

---

## Migration Script

```python
"""User management and access control gap closure.

Adds:
- HR Officer role to userrole enum
- Phone verification columns on users
- Session timeout column on users
- MFA columns on users
- custom_roles table with RLS
- custom_role_id FK on users

Revision ID: 20260325_0100
Revises: 20260322_0300
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "20260325_0100"
down_revision = "20260324_0100"  # arkesel_migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # 1. Add HR Officer to userrole enum
    # ============================================================
    # NOTE: ALTER TYPE ... ADD VALUE works inside transactions on PostgreSQL 12+.
    # Since we use PostgreSQL 16, this is safe. However, Alembic wraps migrations
    # in a transaction, and ALTER TYPE ADD VALUE requires COMMIT/BEGIN pattern
    # to work correctly with Alembic's transaction management.
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'hr_officer'"))
    connection.execute(sa.text("BEGIN"))

    # ============================================================
    # 2. Phone verification columns on users (Phase 1B)
    # ============================================================
    op.add_column(
        "users",
        sa.Column(
            "phone_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "phone_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ============================================================
    # 3. Session timeout column on users (Phase 2)
    # ============================================================
    op.add_column(
        "users",
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ============================================================
    # 4. MFA columns on users (Phase 3)
    # ============================================================
    # mfa_enabled and mfa_secret already exist from initial migration.
    # Only add the new columns.
    op.add_column(
        "users",
        sa.Column(
            "mfa_backup_codes_hash",
            sa.Text(),
            nullable=True,
            comment="JSON list of Argon2id-hashed backup codes",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_setup_pending_secret",
            sa.Text(),
            nullable=True,
            comment="Encrypted TOTP secret during setup (cleared after verification)",
        ),
    )

    # ============================================================
    # 5. custom_roles table (Phase 4)
    # ============================================================
    op.create_table(
        "custom_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "base_role",
            sa.Enum(
                "platform_admin", "chain_admin", "school_admin", "academic_head",
                "finance_officer", "hr_officer", "teacher", "house_parent",
                "parent", "student", "applicant",
                name="userrole",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("permissions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial unique index: only enforced on non-deleted roles (allows slug reuse after soft-delete)
    op.execute("""
        CREATE UNIQUE INDEX uq_custom_roles_tenant_slug
        ON custom_roles (tenant_id, slug)
        WHERE deleted_at IS NULL
    """)

    # Indexes for custom_roles
    op.create_index("ix_custom_roles_tenant_id", "custom_roles", ["tenant_id"])
    op.create_index("ix_custom_roles_base_role", "custom_roles", ["base_role"])

    # RLS for custom_roles
    op.execute("ALTER TABLE custom_roles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE custom_roles FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_custom_roles ON custom_roles
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON custom_roles TO sims_app_user")

    # ============================================================
    # 6. custom_role_id FK on users (Phase 4)
    # ============================================================
    op.add_column(
        "users",
        sa.Column(
            "custom_role_id",
            UUID(as_uuid=True),
            sa.ForeignKey("custom_roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_custom_role_id", "users", ["custom_role_id"])

    # ============================================================
    # 7. Cross-tenant FK guard trigger for users.custom_role_id
    # ============================================================
    # Prevents assigning a custom_role from a different tenant to a user
    op.execute("""
        CREATE OR REPLACE FUNCTION check_custom_role_tenant()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.custom_role_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM custom_roles
                    WHERE id = NEW.custom_role_id
                    AND tenant_id = NEW.tenant_id
                ) THEN
                    RAISE EXCEPTION 'Custom role does not belong to the same tenant as the user';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_check_custom_role_tenant
        BEFORE INSERT OR UPDATE OF custom_role_id ON users
        FOR EACH ROW
        EXECUTE FUNCTION check_custom_role_tenant();
    """)


def downgrade() -> None:
    """
    Partial downgrade — cannot remove enum values in PostgreSQL.

    Drops:
    - custom_role_id from users
    - custom_roles table (and RLS policy)
    - MFA columns from users
    - Session timeout column from users
    - Phone verification columns from users

    Does NOT drop:
    - hr_officer enum value (irreversible in PostgreSQL)
    """
    # 7. Drop cross-tenant FK trigger
    op.execute("DROP TRIGGER IF EXISTS trg_check_custom_role_tenant ON users")
    op.execute("DROP FUNCTION IF EXISTS check_custom_role_tenant()")

    # 6. Drop custom_role_id from users
    op.drop_index("ix_users_custom_role_id", table_name="users")
    op.drop_column("users", "custom_role_id")

    # 5. Drop custom_roles table
    op.execute("DROP POLICY IF EXISTS tenant_isolation_custom_roles ON custom_roles")
    op.execute("DROP INDEX IF EXISTS uq_custom_roles_tenant_slug")
    op.drop_index("ix_custom_roles_base_role", table_name="custom_roles")
    op.drop_index("ix_custom_roles_tenant_id", table_name="custom_roles")
    op.drop_table("custom_roles")

    # 4. Drop MFA columns
    op.drop_column("users", "mfa_setup_pending_secret")
    op.drop_column("users", "mfa_backup_codes_hash")

    # 3. Drop session timeout column
    op.drop_column("users", "last_activity_at")

    # 2. Drop phone verification columns
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_verified")

    # 1. Cannot remove hr_officer from userrole enum
    # (PostgreSQL does not support ALTER TYPE ... REMOVE VALUE)
```

---

## Test Infrastructure Updates

### File: `backend/tests/conftest.py`

**Update `TENANT_SCOPED_TABLES` list** to include the new table:

```python
TENANT_SCOPED_TABLES = [
    # ... existing tables (check actual count in conftest.py — was 55 as of S18.5) ...
    "custom_roles",     # NEW (Phase 4)
]
# Total: existing count + 1 (verify against actual conftest.py before updating)
```

**Update `verify_rls.py`** (if separate from conftest) to include `custom_roles`.

---

## Pre-Migration Checklist

- [ ] Current migration head is `20260322_0300`
- [ ] All existing migrations pass (`alembic upgrade head`)
- [ ] Database backup taken before running migration
- [ ] `hr_officer` value not already in `userrole` enum (the `IF NOT EXISTS` handles this)
- [ ] `mfa_enabled` and `mfa_secret` columns already exist on users table

## Post-Migration Verification

- [ ] `SELECT 'hr_officer'::userrole` succeeds
- [ ] `SELECT * FROM custom_roles` returns empty result (table exists)
- [ ] RLS policy exists: `SELECT * FROM pg_policies WHERE tablename = 'custom_roles'`
- [ ] New columns exist on users: `phone_verified`, `phone_verified_at`, `last_activity_at`, `mfa_backup_codes_hash`, `mfa_setup_pending_secret`, `custom_role_id`
- [ ] `phone_verified` defaults to `false` for existing users
- [ ] Foreign key constraint exists: `users.custom_role_id → custom_roles.id`
- [ ] Index exists: `ix_users_custom_role_id`

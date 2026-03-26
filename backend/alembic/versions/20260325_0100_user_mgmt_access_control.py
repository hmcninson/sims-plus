"""User management and access control gap closure.

Adds:
- HR Officer role to userrole enum
- Phone verification columns on users
- Session activity tracking column on users
- MFA backup/setup columns on users (mfa_enabled, mfa_secret already exist)
- custom_roles table with RLS
- custom_role_id FK on users
- Cross-tenant FK guard trigger for users.custom_role_id

Revision ID: 20260325_0100
Revises: 20260324_0100
Create Date: 2026-03-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

from app.db.rls_helpers import disable_rls_for_table, enable_rls_for_table


revision: str = "20260325_0100"
down_revision: Union[str, None] = "20260324_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. Add HR Officer to userrole enum
    # ============================================================
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in Alembic.
    # COMMIT the current transaction, add the value, then BEGIN a new one.
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(
        sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'hr_officer'")
    )
    connection.execute(sa.text("BEGIN"))

    # ============================================================
    # 2. Phone verification columns on users
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
    # 3. Session activity tracking column on users
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
    # 4. MFA columns on users
    # ============================================================
    # mfa_enabled and mfa_secret already exist from initial migration
    # (20260104_0011). Only add the new columns.
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
    # 5. custom_roles table
    # ============================================================
    op.create_table(
        "custom_roles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "base_role",
            ENUM(
                "platform_admin", "chain_admin", "school_admin", "academic_head",
                "finance_officer", "hr_officer", "teacher", "house_parent",
                "parent", "student", "applicant",
                name="userrole",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "permissions",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Partial unique index: only enforced on non-deleted roles
    op.execute("""
        CREATE UNIQUE INDEX uq_custom_roles_tenant_slug
        ON custom_roles (tenant_id, slug)
        WHERE deleted_at IS NULL
    """)

    # Standard indexes
    op.create_index("ix_custom_roles_tenant_id", "custom_roles", ["tenant_id"])
    op.create_index("ix_custom_roles_base_role", "custom_roles", ["base_role"])

    # RLS for custom_roles (using rls_helpers)
    conn = op.get_bind()
    enable_rls_for_table(conn, "custom_roles")

    # ============================================================
    # 6. custom_role_id FK on users
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
    """Partial downgrade -- cannot remove enum values in PostgreSQL.

    Drops:
    - Cross-tenant FK trigger and function
    - custom_role_id from users
    - custom_roles table (and RLS policy)
    - MFA columns from users
    - Session activity column from users
    - Phone verification columns from users

    Does NOT drop:
    - hr_officer enum value (irreversible in PostgreSQL)
    """
    conn = op.get_bind()

    # 7. Drop cross-tenant FK trigger
    op.execute("DROP TRIGGER IF EXISTS trg_check_custom_role_tenant ON users")
    op.execute("DROP FUNCTION IF EXISTS check_custom_role_tenant()")

    # 6. Drop custom_role_id from users
    op.drop_index("ix_users_custom_role_id", table_name="users")
    op.drop_column("users", "custom_role_id")

    # 5. Drop custom_roles table
    disable_rls_for_table(conn, "custom_roles")
    op.execute("DROP INDEX IF EXISTS uq_custom_roles_tenant_slug")
    op.drop_index("ix_custom_roles_base_role", table_name="custom_roles")
    op.drop_index("ix_custom_roles_tenant_id", table_name="custom_roles")
    op.drop_table("custom_roles")

    # 4. Drop MFA columns
    op.drop_column("users", "mfa_setup_pending_secret")
    op.drop_column("users", "mfa_backup_codes_hash")

    # 3. Drop session activity column
    op.drop_column("users", "last_activity_at")

    # 2. Drop phone verification columns
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_verified")

    # 1. Cannot remove hr_officer from userrole enum
    # (PostgreSQL does not support ALTER TYPE ... REMOVE VALUE)

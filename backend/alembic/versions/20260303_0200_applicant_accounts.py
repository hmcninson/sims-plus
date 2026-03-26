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
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in
    # PostgreSQL. We must commit the current Alembic transaction first,
    # execute the ALTER TYPE outside a transaction, then let the
    # remaining DDL run in a new auto-begun transaction.
    #
    # The IF NOT EXISTS clause makes this idempotent -- safe to re-run
    # if a previous attempt partially succeeded.
    # =================================================================
    connection = op.get_bind()
    # Commit the Alembic-managed transaction so we're outside a tx block
    connection.execute(sa.text("COMMIT"))
    connection.execute(
        sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'applicant'")
    )
    # Start a new transaction for the remaining DDL statements
    connection.execute(sa.text("BEGIN"))

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

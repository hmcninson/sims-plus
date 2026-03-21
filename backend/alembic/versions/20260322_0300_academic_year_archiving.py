"""Add 'archived' value to academicyearstatus enum.

Phase 3B: Academic Year Archiving

Adds the 'archived' status to the academicyearstatus PostgreSQL enum type.
Archived academic years are read-only and hidden by default in the UI.

Note: ALTER TYPE ... ADD VALUE cannot run inside a transaction in PostgreSQL.
We commit the Alembic-managed transaction, execute the ALTER TYPE, then start
a new transaction -- same pattern as 20260303_0200 (applicant accounts).

Downgrade is a no-op: PostgreSQL does not support removing enum values.

Revision ID: 20260322_0300
Revises: 20260322_0200
Create Date: 2026-03-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_0300"
down_revision: Union[str, None] = "20260322_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =================================================================
    # Add 'archived' to academicyearstatus enum
    #
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in
    # PostgreSQL. We must commit the current Alembic transaction first,
    # execute the ALTER TYPE outside a transaction, then start a new
    # transaction for any remaining statements.
    #
    # The IF NOT EXISTS clause makes this idempotent -- safe to re-run
    # if a previous attempt partially succeeded.
    # =================================================================
    connection = op.get_bind()
    # Commit the Alembic-managed transaction so we're outside a tx block
    connection.execute(sa.text("COMMIT"))
    connection.execute(
        sa.text("ALTER TYPE academicyearstatus ADD VALUE IF NOT EXISTS 'archived'")
    )
    # Start a new transaction for Alembic's post-migration bookkeeping
    connection.execute(sa.text("BEGIN"))


def downgrade() -> None:
    # PostgreSQL does NOT support removing values from an enum type.
    # The 'archived' value will remain in the academicyearstatus enum
    # after downgrade. This is harmless -- the value simply won't be
    # used by application code.
    #
    # See: https://www.postgresql.org/docs/16/sql-altertype.html
    # "ADD VALUE ... there is no way to remove a value from an enum type."
    pass

"""Add transport_officer role to userrole enum.

Revision ID: 20260322_0400
Revises: 20260326_0200
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260322_0400"
down_revision: Union[str, None] = "20260326_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block,
    # so we commit the current transaction, add the value, then re-open.
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(
        sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'transport_officer'")
    )
    connection.execute(sa.text("BEGIN"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # The value is harmless if unused, so downgrade is a no-op.
    pass

"""Add simplified class level enum values.

Revision ID: 20260105_2155
Revises: 20260105_0300
Create Date: 2026-01-05 21:55:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260105_2155"
down_revision: Union[str, None] = "20260105_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add simplified class level categories to the enum."""
    # Add simplified category levels
    op.execute("ALTER TYPE classlevel ADD VALUE IF NOT EXISTS 'preschool'")
    op.execute("ALTER TYPE classlevel ADD VALUE IF NOT EXISTS 'primary'")
    op.execute("ALTER TYPE classlevel ADD VALUE IF NOT EXISTS 'jhs'")
    op.execute("ALTER TYPE classlevel ADD VALUE IF NOT EXISTS 'shs'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL without recreating the type."""
    # Note: PostgreSQL doesn't support removing enum values
    # The simplified values will remain but won't be used
    pass

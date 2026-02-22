"""Add updated_at column to invoice_items table.

Revision ID: 20260121_0100
Revises: 20260120_0100
Create Date: 2026-01-21 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260121_0100'
down_revision: Union[str, None] = '20260120_0300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at column to invoice_items table."""
    op.add_column(
        'invoice_items',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        )
    )


def downgrade() -> None:
    """Remove updated_at column from invoice_items table."""
    op.drop_column('invoice_items', 'updated_at')

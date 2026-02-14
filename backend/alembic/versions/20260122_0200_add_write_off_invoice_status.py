"""Add write_off status to invoice status enum

Revision ID: 20260122_0200
Revises: 20260122_0100
Create Date: 2026-01-22

This migration adds the 'write_off' status to the invoice status enum
for handling uncollectible invoices.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260122_0200"
down_revision: Union[str, None] = "20260122_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'write_off' to the invoicestatus enum
    # PostgreSQL requires us to add the value using ALTER TYPE
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'write_off'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly.
    # To properly downgrade, we would need to:
    # 1. Create a new enum without 'write_off'
    # 2. Update all columns using the old enum
    # 3. Drop the old enum
    # 4. Rename the new enum
    #
    # For safety, we'll just leave a comment here since this is rarely needed
    # and the 'write_off' value being present doesn't break anything.
    pass

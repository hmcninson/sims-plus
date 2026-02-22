"""Add creche class level

Revision ID: 20260121_0200
Revises: 20260121_0100
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260121_0200"
down_revision: Union[str, None] = "20260121_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'creche' to the classlevel enum type
    op.execute("ALTER TYPE classlevel ADD VALUE IF NOT EXISTS 'creche' BEFORE 'nursery_1'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type and all columns using it
    pass

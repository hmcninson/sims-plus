"""Add student_type to fee_structures

Revision ID: 20260120_0200
Revises: 20260120_0100
Create Date: 2026-01-20 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260120_0200"
down_revision: Union[str, None] = "20260120_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add student_type column to fee_structures
    # Values: 'all', 'boarding', 'day'
    op.add_column(
        "fee_structures",
        sa.Column(
            "student_type",
            sa.String(20),
            nullable=False,
            server_default="all",
            comment="Student type this fee applies to: all, boarding, day",
        ),
    )

    # Add level_category column for broader level grouping
    # Values: 'preschool', 'primary', 'jhs', 'shs'
    op.add_column(
        "fee_structures",
        sa.Column(
            "level_category",
            sa.String(20),
            nullable=True,
            comment="Level category: preschool, primary, jhs, shs",
        ),
    )


def downgrade() -> None:
    op.drop_column("fee_structures", "level_category")
    op.drop_column("fee_structures", "student_type")

"""Alter conduct_grade column length from 5 to 50

Revision ID: 20260110_2200
Revises: 20260109_1800_seed_preschool_data
Create Date: 2026-01-10 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110_2200"
down_revision: Union[str, None] = "20260110_1700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter conduct_grade column from VARCHAR(5) to VARCHAR(50)
    op.alter_column(
        "term_reports",
        "conduct_grade",
        existing_type=sa.String(5),
        type_=sa.String(50),
        existing_nullable=True,
        comment="Conduct grade (e.g., Excellent, Very Good, Good, Satisfactory, Needs Improvement)",
    )


def downgrade() -> None:
    # Revert to VARCHAR(5)
    op.alter_column(
        "term_reports",
        "conduct_grade",
        existing_type=sa.String(50),
        type_=sa.String(5),
        existing_nullable=True,
        comment="Conduct grade (A, B, C, D, E, F)",
    )

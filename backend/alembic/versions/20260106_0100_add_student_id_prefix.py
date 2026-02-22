"""Add student_id_prefix to schools

Revision ID: 20260106_0100
Revises: 20260105_2359_add_student_models
Create Date: 2026-01-06 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260106_0100"
down_revision: Union[str, None] = "20260105_2359"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add student_id_prefix column to schools table
    op.add_column(
        "schools",
        sa.Column(
            "student_id_prefix",
            sa.String(10),
            nullable=False,
            server_default="STU",
            comment="Prefix for auto-generated student IDs (e.g., STU, ADM)",
        ),
    )


def downgrade() -> None:
    op.drop_column("schools", "student_id_prefix")

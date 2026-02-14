"""Add configurable report card weights (CA vs Exam split)

Revision ID: 20260110_2300
Revises: 20260110_2200
Create Date: 2026-01-10 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260110_2300"
down_revision: Union[str, None] = "20260110_2200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ca_total_weight column with default 50
    op.add_column(
        "assessment_weights",
        sa.Column(
            "ca_total_weight",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="50",
            comment="Total weight for all Continuous Assessment components on report card (default 50%)",
        ),
    )

    # Add exam_total_weight column with default 50
    op.add_column(
        "assessment_weights",
        sa.Column(
            "exam_total_weight",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="50",
            comment="Total weight for End of Term Exam on report card (default 50%)",
        ),
    )


def downgrade() -> None:
    op.drop_column("assessment_weights", "exam_total_weight")
    op.drop_column("assessment_weights", "ca_total_weight")

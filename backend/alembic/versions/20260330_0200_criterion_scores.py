"""Add criterion_scores JSONB column to exam_scores

Supports IB MYP criterion-referenced grading where each subject has
4 criteria (A-D) scored 0-8, with the final grade (1-7) derived from
the sum. Stored as JSONB to accommodate varying criterion structures
across subject groups.

Creates:
- criterion_scores JSON column on exam_scores (nullable)
- GIN index on criterion_scores for analytics queries

Revision ID: 20260330_0200
Revises: 20260401_0100
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260330_0200"
down_revision = "20260401_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add criterion_scores JSONB column for IB MYP criterion-referenced grading
    op.add_column(
        "exam_scores",
        sa.Column(
            "criterion_scores",
            JSONB(),
            nullable=True,
            comment=(
                "Criterion-referenced scores (IB MYP): "
                "{criteria: [{criterion, name, level, max_level}], "
                "criterion_total, criterion_max}"
            ),
        ),
    )

    # GIN index enables efficient querying of criterion scores for analytics
    # (e.g., "find all students at level 7+ in criterion A across all subjects")
    op.create_index(
        "ix_exam_scores_criterion_scores",
        "exam_scores",
        ["criterion_scores"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_exam_scores_criterion_scores", table_name="exam_scores")
    op.drop_column("exam_scores", "criterion_scores")

"""Add grading_scale_id to exam_subjects table

Revision ID: 20260110_0100
Revises: 20260109_1900
Create Date: 2026-01-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260110_0100"
down_revision = "20260109_1900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add grading_scale_id column to exam_subjects
    op.add_column(
        "exam_subjects",
        sa.Column(
            "grading_scale_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("grading_scales.id", ondelete="SET NULL"),
            nullable=True,
            comment="Grading scale for auto grade calculation",
        ),
    )

    # Create index for faster lookups
    op.create_index(
        "ix_exam_subjects_grading_scale_id",
        "exam_subjects",
        ["grading_scale_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_exam_subjects_grading_scale_id", table_name="exam_subjects")
    op.drop_column("exam_subjects", "grading_scale_id")

"""Add previous_student_id field to students table

Revision ID: 20260107_0100
Revises: 20260106_0100_add_student_id_prefix
Create Date: 2026-01-07

This migration adds a field to store student IDs from previous/external systems,
allowing schools to maintain reference to old IDs during migration while keeping
the system-generated student_id consistent.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260107_0100"
down_revision = "20260106_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add previous_student_id column to students table
    op.add_column(
        "students",
        sa.Column(
            "previous_student_id",
            sa.String(100),
            nullable=True,
            comment="Student ID from previous/external system (for migration reference)",
        ),
    )

    # Add index for searching by previous student ID
    op.create_index(
        "ix_students_previous_student_id",
        "students",
        ["previous_student_id"],
        unique=False,
    )


def downgrade() -> None:
    # Remove index
    op.drop_index("ix_students_previous_student_id", table_name="students")

    # Remove column
    op.drop_column("students", "previous_student_id")

"""Add applicable_levels column to subjects table.

Revision ID: 20260109_0100
Revises: 20260107_0300_add_attendance_models
Create Date: 2026-01-09

This migration adds the applicable_levels JSONB column to the subjects table
to support filtering subjects by class level (preschool, primary, jhs, shs).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260109_0200"
down_revision = "20260109_1700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add applicable_levels column to subjects table
    op.add_column(
        "subjects",
        sa.Column(
            "applicable_levels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="List of class levels this subject applies to (null = all levels)",
        ),
    )

    # Update existing subjects to have default applicable_levels based on common subjects
    # Primary and JHS subjects (most common)
    op.execute("""
        UPDATE subjects
        SET applicable_levels = '["primary", "jhs", "shs"]'::jsonb
        WHERE code IN ('MATH', 'ENG', 'SCI', 'SST', 'ICT', 'RME', 'FRANC', 'TWI', 'GA', 'EWE', 'FANTE')
        AND applicable_levels IS NULL
    """)

    # JHS and SHS only subjects
    op.execute("""
        UPDATE subjects
        SET applicable_levels = '["jhs", "shs"]'::jsonb
        WHERE code IN ('INT_SCI', 'BDT', 'PRETECH')
        AND applicable_levels IS NULL
    """)

    # SHS only subjects
    op.execute("""
        UPDATE subjects
        SET applicable_levels = '["shs"]'::jsonb
        WHERE code IN ('CORE_MATH', 'ELECT_MATH', 'PHYSICS', 'CHEMISTRY', 'BIOLOGY',
                       'ECONOMICS', 'GEOGRAPHY', 'GOVERNMENT', 'HISTORY', 'LITERATURE',
                       'ACCOUNTING', 'COSTING', 'BUSINESS_MGT', 'ELECTIVE_ICT')
        AND applicable_levels IS NULL
    """)


def downgrade() -> None:
    op.drop_column("subjects", "applicable_levels")

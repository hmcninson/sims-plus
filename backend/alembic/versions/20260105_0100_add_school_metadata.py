"""Add school metadata fields

Revision ID: 20260105_0100
Revises: 20260104_0600
Create Date: 2026-01-05

Adds description and year_established fields to schools table.
Note: motto already exists in the schools table.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "20260105_0100"
down_revision = "20260104_0600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add description column
    op.add_column(
        "schools",
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="School description/about",
        ),
    )

    # Add year_established column
    op.add_column(
        "schools",
        sa.Column(
            "year_established",
            sa.Integer(),
            nullable=True,
            comment="Year the school was established",
        ),
    )


def downgrade() -> None:
    op.drop_column("schools", "year_established")
    op.drop_column("schools", "description")

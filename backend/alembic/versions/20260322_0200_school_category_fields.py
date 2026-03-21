"""Add school_category and boarding_type enums and columns to schools.

Revision ID: 20260322_0200
Revises: 20260322_0100
Create Date: 2026-03-22

Adds two nullable enum columns to the schools table for richer
school classification (ownership type and residential type).
Existing uses_boarding boolean is intentionally kept.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260322_0200"
down_revision = "20260322_0100"  # After trial/subscription migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    schoolcategory = sa.Enum(
        "public", "private", "international", "faith_based",
        name="schoolcategory",
    )
    schoolcategory.create(op.get_bind(), checkfirst=True)

    boardingtype = sa.Enum(
        "day_only", "boarding_only", "mixed",
        name="boardingtype",
    )
    boardingtype.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column(
        "schools",
        sa.Column(
            "category",
            sa.Enum(
                "public", "private", "international", "faith_based",
                name="schoolcategory",
            ),
            nullable=True,
            comment="Ownership: public, private, international, faith_based",
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "boarding_type",
            sa.Enum(
                "day_only", "boarding_only", "mixed",
                name="boardingtype",
            ),
            nullable=True,
            comment="Residential: day_only, boarding_only, mixed",
        ),
    )


def downgrade() -> None:
    op.drop_column("schools", "boarding_type")
    op.drop_column("schools", "category")

    sa.Enum(name="boardingtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="schoolcategory").drop(op.get_bind(), checkfirst=True)

"""Add class_id and section_id to school_periods

Revision ID: 20260112_0300
Revises: 20260112_0200
Create Date: 2026-01-12 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260112_0300"
down_revision: Union[str, None] = "20260112_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add class_id and section_id columns
    op.add_column(
        "school_periods",
        sa.Column("class_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "school_periods",
        sa.Column("section_id", sa.UUID(), nullable=True),
    )

    # Add foreign key constraints
    op.create_foreign_key(
        "fk_school_periods_class_id",
        "school_periods",
        "classes",
        ["class_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_school_periods_section_id",
        "school_periods",
        "class_sections",
        ["section_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Drop old unique constraint and create new one
    op.drop_constraint("uq_school_period", "school_periods", type_="unique")
    op.create_unique_constraint(
        "uq_school_period",
        "school_periods",
        ["tenant_id", "class_id", "section_id", "period_number"],
    )


def downgrade() -> None:
    # Drop new unique constraint and recreate old one
    op.drop_constraint("uq_school_period", "school_periods", type_="unique")
    op.create_unique_constraint(
        "uq_school_period",
        "school_periods",
        ["tenant_id", "period_number"],
    )

    # Drop foreign keys
    op.drop_constraint("fk_school_periods_section_id", "school_periods", type_="foreignkey")
    op.drop_constraint("fk_school_periods_class_id", "school_periods", type_="foreignkey")

    # Drop columns
    op.drop_column("school_periods", "section_id")
    op.drop_column("school_periods", "class_id")

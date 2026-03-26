"""Staff HR Gap Closure Phase 1: Staff HR Fields

Add columns to staff table for enhanced HR tracking:
  - tin_number VARCHAR(50)
  - employment_type (new enum employmenttype)
  - ges_staff_id VARCHAR(50)
  - nationality VARCHAR(100)
  - marital_status VARCHAR(20)

New enum:
  - employmenttype: full_time, part_time, contract, temporary, intern

Partial index:
  - ix_staff_employment_type on (tenant_id, employment_type) WHERE employment_type IS NOT NULL

Revision ID: 20260426_0100
Revises: 20260425_0400
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


revision: str = "20260426_0100"
down_revision: Union[str, None] = "20260425_0400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum: employmenttype
    # ------------------------------------------------------------------
    employmenttype = sa.Enum(
        "full_time",
        "part_time",
        "contract",
        "temporary",
        "intern",
        name="employmenttype",
    )
    employmenttype.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # Add columns to staff table
    # ------------------------------------------------------------------
    op.add_column("staff", sa.Column("tin_number", sa.String(50), nullable=True))
    op.add_column(
        "staff",
        sa.Column(
            "employment_type",
            postgresql.ENUM(
                "full_time", "part_time", "contract", "temporary", "intern",
                name="employmenttype",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("staff", sa.Column("ges_staff_id", sa.String(50), nullable=True))
    op.add_column("staff", sa.Column("nationality", sa.String(100), nullable=True))
    op.add_column("staff", sa.Column("marital_status", sa.String(20), nullable=True))

    # ------------------------------------------------------------------
    # Partial index for employment_type filtering
    # ------------------------------------------------------------------
    op.create_index(
        "ix_staff_employment_type",
        "staff",
        ["tenant_id", "employment_type"],
        postgresql_where=text("employment_type IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_staff_employment_type", table_name="staff")
    op.drop_column("staff", "marital_status")
    op.drop_column("staff", "nationality")
    op.drop_column("staff", "ges_staff_id")
    op.drop_column("staff", "employment_type")
    op.drop_column("staff", "tin_number")
    sa.Enum(name="employmenttype").drop(op.get_bind(), checkfirst=True)

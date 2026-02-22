"""Add missing tenant columns: status, max_staff, features, trial_ends_at

Revision ID: 20260221_0200
Revises: 20260221_0100
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "20260221_0200"
down_revision: Union[str, None] = "20260221_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the tenantstatus enum type
    op.execute("CREATE TYPE tenantstatus AS ENUM ('trial', 'active', 'suspended', 'cancelled')")

    # Add missing columns to tenants table
    op.add_column("tenants", sa.Column(
        "status",
        sa.Enum("trial", "active", "suspended", "cancelled", name="tenantstatus", create_type=False),
        nullable=False,
        server_default="trial",
    ))
    op.add_column("tenants", sa.Column(
        "max_staff",
        sa.Integer(),
        nullable=False,
        server_default="10",
    ))
    op.add_column("tenants", sa.Column(
        "features",
        JSONB(),
        nullable=True,
        server_default="{}",
    ))
    op.add_column("tenants", sa.Column(
        "trial_ends_at",
        sa.DateTime(timezone=True),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("tenants", "trial_ends_at")
    op.drop_column("tenants", "features")
    op.drop_column("tenants", "max_staff")
    op.drop_column("tenants", "status")
    op.execute("DROP TYPE IF EXISTS tenantstatus")

"""add_new_school_types

Revision ID: 549287f1f9df
Revises: comprehensive_rls
Create Date: 2026-01-04 04:57:34.223629+00:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '549287f1f9df'
down_revision: Union[str, None] = 'comprehensive_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new school type enum values."""
    # Add new enum values to schooltype
    op.execute("ALTER TYPE schooltype ADD VALUE IF NOT EXISTS 'preschool_primary'")
    op.execute("ALTER TYPE schooltype ADD VALUE IF NOT EXISTS 'basic_preschool'")
    op.execute("ALTER TYPE schooltype ADD VALUE IF NOT EXISTS 'basic_shs'")


def downgrade() -> None:
    """
    Note: PostgreSQL does not support removing enum values directly.
    The values will remain but won't be used if not referenced.
    """
    pass

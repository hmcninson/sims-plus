"""Add preschool_settings JSONB column to schools table

Revision ID: 20260109_1900
Revises: 20260109_1800
Create Date: 2026-01-09 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '20260109_1900'
down_revision: Union[str, None] = '20260109_1800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add preschool_settings JSONB column to schools table
    op.add_column(
        'schools',
        sa.Column(
            'preschool_settings',
            JSONB,
            nullable=True,
            comment='Preschool configuration settings (enabled, tracking options, etc.)'
        )
    )


def downgrade() -> None:
    # Remove preschool_settings column from schools table
    op.drop_column('schools', 'preschool_settings')

"""Add staff import fields (previous_staff_id and staff_id_prefix)

Revision ID: 20260108_0100
Revises: 20260107_0400
Create Date: 2026-01-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260108_0100'
down_revision = '20260107_0400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add previous_staff_id to staff table
    op.add_column(
        'staff',
        sa.Column(
            'previous_staff_id',
            sa.String(100),
            nullable=True,
            comment='ID from previous/external system (for reference during migration)'
        )
    )
    op.create_index('ix_staff_previous_staff_id', 'staff', ['previous_staff_id'])

    # Add staff_id_prefix to schools table
    op.add_column(
        'schools',
        sa.Column(
            'staff_id_prefix',
            sa.String(10),
            nullable=False,
            server_default='STF',
            comment='Prefix for auto-generated staff IDs (e.g., STF, EMP)'
        )
    )


def downgrade() -> None:
    # Remove staff_id_prefix from schools table
    op.drop_column('schools', 'staff_id_prefix')

    # Remove previous_staff_id from staff table
    op.drop_index('ix_staff_previous_staff_id', table_name='staff')
    op.drop_column('staff', 'previous_staff_id')

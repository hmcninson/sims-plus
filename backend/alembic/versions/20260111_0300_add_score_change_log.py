"""Add score change log for audit trail

Revision ID: 20260111_0300
Revises: 20260111_0200
Create Date: 2026-01-11 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260111_0300'
down_revision: Union[str, None] = '20260111_0200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'score_change_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exam_score_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_score', sa.Numeric(5, 2), nullable=True, comment='Previous score value'),
        sa.Column('new_score', sa.Numeric(5, 2), nullable=True, comment='New score value'),
        sa.Column('old_is_absent', sa.Boolean(), nullable=True, comment='Previous absent status'),
        sa.Column('new_is_absent', sa.Boolean(), nullable=True, comment='New absent status'),
        sa.Column('change_type', sa.String(20), nullable=False, comment='Type of change: created, updated, deleted'),
        sa.Column('change_reason', sa.Text(), nullable=True, comment='Optional reason for the change'),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='IP address of the user making the change'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exam_score_id'], ['exam_scores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes for efficient querying
    op.create_index('ix_score_change_logs_tenant_id', 'score_change_logs', ['tenant_id'])
    op.create_index('ix_score_change_logs_exam_score_id', 'score_change_logs', ['exam_score_id'])
    op.create_index('ix_score_change_logs_changed_at', 'score_change_logs', ['changed_at'])
    op.create_index('ix_score_change_logs_changed_by', 'score_change_logs', ['changed_by'])


def downgrade() -> None:
    op.drop_index('ix_score_change_logs_changed_by', table_name='score_change_logs')
    op.drop_index('ix_score_change_logs_changed_at', table_name='score_change_logs')
    op.drop_index('ix_score_change_logs_exam_score_id', table_name='score_change_logs')
    op.drop_index('ix_score_change_logs_tenant_id', table_name='score_change_logs')
    op.drop_table('score_change_logs')

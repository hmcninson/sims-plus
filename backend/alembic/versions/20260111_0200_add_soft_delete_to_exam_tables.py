"""Add soft delete to exam tables

Revision ID: 20260111_0200
Revises: 20260111_0100
Create Date: 2026-01-11 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260111_0200'
down_revision: Union[str, None] = '20260111_0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add deleted_at column to exam_scores
    op.add_column('exam_scores', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_exam_scores_deleted_at', 'exam_scores', ['deleted_at'])

    # Add deleted_at column to continuous_assessments
    op.add_column('continuous_assessments', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_continuous_assessments_deleted_at', 'continuous_assessments', ['deleted_at'])

    # Add deleted_at column to term_reports
    op.add_column('term_reports', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('ix_term_reports_deleted_at', 'term_reports', ['deleted_at'])


def downgrade() -> None:
    # Remove deleted_at from term_reports
    op.drop_index('ix_term_reports_deleted_at', table_name='term_reports')
    op.drop_column('term_reports', 'deleted_at')

    # Remove deleted_at from continuous_assessments
    op.drop_index('ix_continuous_assessments_deleted_at', table_name='continuous_assessments')
    op.drop_column('continuous_assessments', 'deleted_at')

    # Remove deleted_at from exam_scores
    op.drop_index('ix_exam_scores_deleted_at', table_name='exam_scores')
    op.drop_column('exam_scores', 'deleted_at')

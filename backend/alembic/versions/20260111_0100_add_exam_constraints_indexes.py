"""Add exam constraints and indexes for performance

Revision ID: 20260111_0100
Revises: 20260110_2300
Create Date: 2026-01-11 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260111_0100'
down_revision: Union[str, None] = '20260110_2300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add check constraint: pass_mark <= max_score on exam_subjects
    op.execute("""
        ALTER TABLE exam_subjects
        ADD CONSTRAINT chk_pass_mark_lte_max_score
        CHECK (pass_mark <= max_score)
    """)

    # Add check constraint: start_date <= end_date on exams
    op.execute("""
        ALTER TABLE exams
        ADD CONSTRAINT chk_start_date_lte_end_date
        CHECK (start_date IS NULL OR end_date IS NULL OR start_date <= end_date)
    """)

    # Add check constraint: max_score > 0 on exam_subjects
    op.execute("""
        ALTER TABLE exam_subjects
        ADD CONSTRAINT chk_max_score_positive
        CHECK (max_score > 0)
    """)

    # Add check constraint: pass_mark >= 0 on exam_subjects
    op.execute("""
        ALTER TABLE exam_subjects
        ADD CONSTRAINT chk_pass_mark_non_negative
        CHECK (pass_mark >= 0)
    """)

    # Add check constraint: score >= 0 on exam_scores
    op.execute("""
        ALTER TABLE exam_scores
        ADD CONSTRAINT chk_score_non_negative
        CHECK (score IS NULL OR score >= 0)
    """)

    # Add check constraint: max_score > 0 on continuous_assessments
    op.execute("""
        ALTER TABLE continuous_assessments
        ADD CONSTRAINT chk_ca_max_score_positive
        CHECK (max_score > 0)
    """)

    # Add check constraint: score >= 0 on continuous_assessments
    op.execute("""
        ALTER TABLE continuous_assessments
        ADD CONSTRAINT chk_ca_score_non_negative
        CHECK (score IS NULL OR score >= 0)
    """)

    # Performance indexes for exam_scores (frequently queried)
    op.create_index(
        'ix_exam_scores_tenant_subject_student',
        'exam_scores',
        ['tenant_id', 'exam_subject_id', 'student_id'],
    )

    # Performance indexes for continuous_assessments (frequently queried)
    op.create_index(
        'ix_continuous_assessments_tenant_term_student_subject',
        'continuous_assessments',
        ['tenant_id', 'term_id', 'student_id', 'subject_id'],
    )

    op.create_index(
        'ix_continuous_assessments_tenant_term_class',
        'continuous_assessments',
        ['tenant_id', 'term_id', 'class_id'],
    )

    # Performance indexes for term_reports (frequently queried for rankings)
    op.create_index(
        'ix_term_reports_tenant_term_class',
        'term_reports',
        ['tenant_id', 'term_id', 'class_id'],
    )

    op.create_index(
        'ix_term_reports_class_position',
        'term_reports',
        ['tenant_id', 'term_id', 'class_id', 'class_position'],
    )

    # Index for exam_subjects (frequently joined)
    op.create_index(
        'ix_exam_subjects_exam_subject_class',
        'exam_subjects',
        ['exam_id', 'subject_id', 'class_id'],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_exam_subjects_exam_subject_class', table_name='exam_subjects')
    op.drop_index('ix_term_reports_class_position', table_name='term_reports')
    op.drop_index('ix_term_reports_tenant_term_class', table_name='term_reports')
    op.drop_index('ix_continuous_assessments_tenant_term_class', table_name='continuous_assessments')
    op.drop_index('ix_continuous_assessments_tenant_term_student_subject', table_name='continuous_assessments')
    op.drop_index('ix_exam_scores_tenant_subject_student', table_name='exam_scores')

    # Drop check constraints
    op.execute("ALTER TABLE continuous_assessments DROP CONSTRAINT IF EXISTS chk_ca_score_non_negative")
    op.execute("ALTER TABLE continuous_assessments DROP CONSTRAINT IF EXISTS chk_ca_max_score_positive")
    op.execute("ALTER TABLE exam_scores DROP CONSTRAINT IF EXISTS chk_score_non_negative")
    op.execute("ALTER TABLE exam_subjects DROP CONSTRAINT IF EXISTS chk_pass_mark_non_negative")
    op.execute("ALTER TABLE exam_subjects DROP CONSTRAINT IF EXISTS chk_max_score_positive")
    op.execute("ALTER TABLE exams DROP CONSTRAINT IF EXISTS chk_start_date_lte_end_date")
    op.execute("ALTER TABLE exam_subjects DROP CONSTRAINT IF EXISTS chk_pass_mark_lte_max_score")

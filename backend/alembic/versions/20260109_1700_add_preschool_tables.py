"""Add preschool tables

Revision ID: 20260109_1700
Revises: 20260105_2359
Create Date: 2026-01-09 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260109_1700'
down_revision: Union[str, None] = '20260108_0200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================
    # Learning Areas
    # =========================
    op.create_table(
        'learning_areas',
        sa.Column('name', sa.String(100), nullable=False, comment='Learning area name, e.g., Social-Emotional Development'),
        sa.Column('code', sa.String(20), nullable=False, comment='Short code, e.g., SED'),
        sa.Column('description', sa.Text(), nullable=True, comment='Detailed description of the learning area'),
        sa.Column('icon', sa.String(50), nullable=True, comment='Icon identifier for UI'),
        sa.Column('color', sa.String(7), nullable=True, comment='Hex color for visual representation, e.g., #22c55e'),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0, comment='Order for display in UI'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_learning_area_code')
    )
    op.create_index('ix_learning_areas_tenant_id', 'learning_areas', ['tenant_id'])

    # =========================
    # Developmental Skills
    # =========================
    op.create_table(
        'developmental_skills',
        sa.Column('learning_area_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, comment='Skill name, e.g., Recognizes own name in print'),
        sa.Column('description', sa.Text(), nullable=True, comment='Detailed description or criteria'),
        sa.Column('age_range_months_min', sa.Integer(), nullable=True, comment='Minimum age in months (e.g., 36 for 3 years)'),
        sa.Column('age_range_months_max', sa.Integer(), nullable=True, comment='Maximum age in months (e.g., 48 for 4 years)'),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0, comment='Order within learning area'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('applicable_levels', postgresql.JSONB(), nullable=True, comment='List of class levels this skill applies to'),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['learning_area_id'], ['learning_areas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'learning_area_id', 'name', name='uq_skill_name')
    )
    op.create_index('ix_developmental_skills_tenant_id', 'developmental_skills', ['tenant_id'])
    op.create_index('ix_developmental_skills_learning_area_id', 'developmental_skills', ['learning_area_id'])

    # =========================
    # Preschool Rating Scales
    # =========================
    op.create_table(
        'preschool_rating_scales',
        sa.Column('name', sa.String(100), nullable=False, comment='Scale name, e.g., 4-Point Developmental Scale'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False, comment='Is this the default scale for this tenant?'),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_rating_scale_name')
    )
    op.create_index('ix_preschool_rating_scales_tenant_id', 'preschool_rating_scales', ['tenant_id'])

    # =========================
    # Preschool Ratings
    # =========================
    op.create_table(
        'preschool_ratings',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('scale_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False, comment='Rating name, e.g., Proficient'),
        sa.Column('short_code', sa.String(5), nullable=False, comment='Short code, e.g., P or 3'),
        sa.Column('description', sa.Text(), nullable=True, comment='Description, e.g., Child consistently demonstrates this skill'),
        sa.Column('numeric_value', sa.Integer(), nullable=False, comment='Numeric value for calculations/sorting'),
        sa.Column('color', sa.String(7), nullable=True, comment='Hex color, e.g., #22c55e (green)'),
        sa.Column('icon', sa.String(50), nullable=True, comment='Icon identifier or emoji'),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['scale_id'], ['preschool_rating_scales.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scale_id', 'short_code', name='uq_rating_code')
    )
    op.create_index('ix_preschool_ratings_scale_id', 'preschool_ratings', ['scale_id'])

    # =========================
    # Student Skill Assessments
    # =========================
    op.create_table(
        'student_skill_assessments',
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('skill_id', sa.UUID(), nullable=False),
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=False),
        sa.Column('rating_id', sa.UUID(), nullable=True),
        sa.Column('observation_notes', sa.Text(), nullable=True, comment="Teacher's observation notes"),
        sa.Column('evidence_url', sa.String(500), nullable=True, comment='URL to photo/video evidence (optional)'),
        sa.Column('assessed_by', sa.UUID(), nullable=True),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_id'], ['developmental_skills.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rating_id'], ['preschool_ratings.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assessed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'student_id', 'skill_id', 'term_id', name='uq_student_skill_term')
    )
    op.create_index('ix_student_skill_assessments_tenant_id', 'student_skill_assessments', ['tenant_id'])
    op.create_index('ix_student_skill_assessments_student_id', 'student_skill_assessments', ['student_id'])
    op.create_index('ix_student_skill_assessments_skill_id', 'student_skill_assessments', ['skill_id'])
    op.create_index('ix_student_skill_assessments_term_id', 'student_skill_assessments', ['term_id'])

    # =========================
    # Progress Observations
    # =========================
    op.create_table(
        'progress_observations',
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('learning_area_id', sa.UUID(), nullable=True, comment='Optional: link to a specific learning area'),
        sa.Column('observation_type', sa.String(20), nullable=False, comment='Type: anecdote, milestone, photo, video, incident'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('observation_date', sa.Date(), nullable=False),
        sa.Column('attachments', postgresql.JSONB(), nullable=True),
        sa.Column('share_with_parents', sa.Boolean(), nullable=False, default=True, comment='Should this be visible to parents?'),
        sa.Column('is_highlight', sa.Boolean(), nullable=False, default=False, comment='Featured on student profile?'),
        sa.Column('recorded_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['learning_area_id'], ['learning_areas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_progress_observations_tenant_id', 'progress_observations', ['tenant_id'])
    op.create_index('ix_progress_observations_student_id', 'progress_observations', ['student_id'])
    op.create_index('ix_progress_observations_observation_date', 'progress_observations', ['observation_date'])

    # =========================
    # Daily Activity Logs
    # =========================
    op.create_table(
        'daily_activity_logs',
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('arrival_time', sa.Time(), nullable=True),
        sa.Column('arrival_mood', sa.String(20), nullable=True, comment='happy, tired, upset, excited, calm, sick'),
        sa.Column('departure_time', sa.Time(), nullable=True),
        sa.Column('departure_mood', sa.String(20), nullable=True),
        sa.Column('meals', postgresql.JSONB(), nullable=True),
        sa.Column('nap_start', sa.Time(), nullable=True),
        sa.Column('nap_end', sa.Time(), nullable=True),
        sa.Column('nap_quality', sa.String(20), nullable=True, comment='good, restless, didnt_sleep'),
        sa.Column('diaper_changes', sa.Integer(), nullable=True),
        sa.Column('potty_successes', sa.Integer(), nullable=True),
        sa.Column('accidents', sa.Integer(), nullable=True),
        sa.Column('activities', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('highlights', sa.Text(), nullable=True, comment='Special moments to share with parents'),
        sa.Column('logged_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['logged_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'student_id', 'log_date', name='uq_student_daily_log')
    )
    op.create_index('ix_daily_activity_logs_tenant_id', 'daily_activity_logs', ['tenant_id'])
    op.create_index('ix_daily_activity_logs_student_id', 'daily_activity_logs', ['student_id'])
    op.create_index('ix_daily_activity_logs_log_date', 'daily_activity_logs', ['log_date'])

    # =========================
    # Preschool Reports
    # =========================
    op.create_table(
        'preschool_reports',
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('days_present', sa.Integer(), nullable=True),
        sa.Column('days_absent', sa.Integer(), nullable=True),
        sa.Column('total_school_days', sa.Integer(), nullable=True),
        sa.Column('learning_area_summaries', postgresql.JSONB(), nullable=True),
        sa.Column('overall_progress', sa.Text(), nullable=True, comment='General progress narrative'),
        sa.Column('strengths', sa.Text(), nullable=True, comment='What the child excels at'),
        sa.Column('areas_for_growth', sa.Text(), nullable=True, comment='Areas needing development'),
        sa.Column('teacher_recommendations', sa.Text(), nullable=True, comment='Suggestions for parents'),
        sa.Column('highlights', postgresql.JSONB(), nullable=True),
        sa.Column('next_term_goals', postgresql.JSONB(), nullable=True),
        sa.Column('class_teacher_remark', sa.Text(), nullable=True),
        sa.Column('head_teacher_remark', sa.Text(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, default=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'student_id', 'term_id', name='uq_preschool_report')
    )
    op.create_index('ix_preschool_reports_tenant_id', 'preschool_reports', ['tenant_id'])
    op.create_index('ix_preschool_reports_student_id', 'preschool_reports', ['student_id'])
    op.create_index('ix_preschool_reports_term_id', 'preschool_reports', ['term_id'])


def downgrade() -> None:
    # Drop tables in reverse order (dependencies first)
    op.drop_table('preschool_reports')
    op.drop_table('daily_activity_logs')
    op.drop_table('progress_observations')
    op.drop_table('student_skill_assessments')
    op.drop_table('preschool_ratings')
    op.drop_table('preschool_rating_scales')
    op.drop_table('developmental_skills')
    op.drop_table('learning_areas')

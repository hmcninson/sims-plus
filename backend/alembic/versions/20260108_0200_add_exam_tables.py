"""Add examination tables.

Revision ID: 20260108_0200
Revises: 20260108_0100
Create Date: 2026-01-08 02:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260108_0200"
down_revision: Union[str, None] = "20260108_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create exam, exam_subjects, exam_scores, continuous_assessments, and term_reports tables."""

    # Create enums
    examtype_enum = postgresql.ENUM(
        'quiz', 'midterm', 'end_term', 'mock', 'practical', 'project',
        name='examtype', create_type=False
    )
    examtype_enum.create(op.get_bind(), checkfirst=True)

    examstatus_enum = postgresql.ENUM(
        'draft', 'scheduled', 'ongoing', 'completed', 'results_published', 'cancelled',
        name='examstatus', create_type=False
    )
    examstatus_enum.create(op.get_bind(), checkfirst=True)

    examsubjectstatus_enum = postgresql.ENUM(
        'pending', 'scores_entered', 'submitted', 'published',
        name='examsubjectstatus', create_type=False
    )
    examsubjectstatus_enum.create(op.get_bind(), checkfirst=True)

    assessmenttype_enum = postgresql.ENUM(
        'class_work', 'homework', 'test', 'project', 'assignment',
        name='assessmenttype', create_type=False
    )
    assessmenttype_enum.create(op.get_bind(), checkfirst=True)

    # Create exams table
    op.create_table(
        'exams',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        # Foreign keys
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=False),
        # Basic info
        sa.Column('name', sa.String(100), nullable=False, comment='Exam name, e.g., Mid-Term Examination'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('exam_type', examtype_enum, nullable=False),
        # Dates
        sa.Column('start_date', sa.Date(), nullable=True, comment='Exam start date'),
        sa.Column('end_date', sa.Date(), nullable=True, comment='Exam end date'),
        # Status
        sa.Column('status', examstatus_enum, nullable=False, server_default='draft'),
        # Audit
        sa.Column('created_by', sa.UUID(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'academic_year_id', 'term_id', 'name', name='uq_exam_name_per_term'),
    )
    op.create_index('ix_exams_tenant_id', 'exams', ['tenant_id'])
    op.create_index('ix_exams_academic_year_id', 'exams', ['academic_year_id'])
    op.create_index('ix_exams_term_id', 'exams', ['term_id'])
    op.create_index('ix_exams_status', 'exams', ['status'])

    # Create exam_subjects table
    op.create_table(
        'exam_subjects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # Foreign keys
        sa.Column('exam_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.UUID(), nullable=False),
        # Scoring config
        sa.Column('max_score', sa.Numeric(5, 2), nullable=False, server_default='100.00', comment='Maximum possible score'),
        sa.Column('pass_mark', sa.Numeric(5, 2), nullable=False, server_default='50.00', comment='Minimum passing score'),
        # Scheduling
        sa.Column('exam_date', sa.Date(), nullable=True),
        sa.Column('exam_time', sa.Time(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True, comment='Exam duration in minutes'),
        sa.Column('venue', sa.String(100), nullable=True),
        # Status
        sa.Column('status', examsubjectstatus_enum, nullable=False, server_default='pending'),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'exam_id', 'subject_id', 'class_id', name='uq_exam_subject_class'),
    )
    op.create_index('ix_exam_subjects_tenant_id', 'exam_subjects', ['tenant_id'])
    op.create_index('ix_exam_subjects_exam_id', 'exam_subjects', ['exam_id'])
    op.create_index('ix_exam_subjects_subject_id', 'exam_subjects', ['subject_id'])
    op.create_index('ix_exam_subjects_class_id', 'exam_subjects', ['class_id'])

    # Create exam_scores table
    op.create_table(
        'exam_scores',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # Foreign keys
        sa.Column('exam_subject_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        # Score data
        sa.Column('score', sa.Numeric(5, 2), nullable=True, comment='Raw score obtained'),
        sa.Column('is_absent', sa.Boolean(), nullable=False, server_default='false', comment='Student was absent for exam'),
        # Calculated grade
        sa.Column('grade', sa.String(5), nullable=True, comment='Calculated grade (A1, B2, etc.)'),
        sa.Column('grade_point', sa.Numeric(3, 2), nullable=True, comment='Grade point for GPA calculation'),
        sa.Column('grade_remark', sa.String(50), nullable=True, comment='Grade remark (Excellent, Good, etc.)'),
        # Teacher remark
        sa.Column('teacher_remark', sa.Text(), nullable=True, comment='Per-subject teacher remark for report card'),
        # Audit
        sa.Column('entered_by', sa.UUID(), nullable=True),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['exam_subject_id'], ['exam_subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entered_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'exam_subject_id', 'student_id', name='uq_exam_score_student'),
    )
    op.create_index('ix_exam_scores_tenant_id', 'exam_scores', ['tenant_id'])
    op.create_index('ix_exam_scores_exam_subject_id', 'exam_scores', ['exam_subject_id'])
    op.create_index('ix_exam_scores_student_id', 'exam_scores', ['student_id'])

    # Create continuous_assessments table
    op.create_table(
        'continuous_assessments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # Foreign keys
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        # Assessment info
        sa.Column('assessment_type', assessmenttype_enum, nullable=False),
        sa.Column('title', sa.String(100), nullable=False, comment='Assessment title, e.g., Week 3 Class Test'),
        sa.Column('max_score', sa.Numeric(5, 2), nullable=False, server_default='10.00'),
        sa.Column('score', sa.Numeric(5, 2), nullable=True),
        sa.Column('assessment_date', sa.Date(), nullable=False),
        # Audit
        sa.Column('entered_by', sa.UUID(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entered_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_continuous_assessments_tenant_id', 'continuous_assessments', ['tenant_id'])
    op.create_index('ix_continuous_assessments_term_id', 'continuous_assessments', ['term_id'])
    op.create_index('ix_continuous_assessments_student_id', 'continuous_assessments', ['student_id'])
    op.create_index('ix_continuous_assessments_subject_id', 'continuous_assessments', ['subject_id'])

    # Create term_reports table
    op.create_table(
        'term_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # Foreign keys
        sa.Column('academic_year_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.UUID(), nullable=False),
        sa.Column('section_id', sa.UUID(), nullable=True),
        # Aggregate scores
        sa.Column('total_score', sa.Numeric(7, 2), nullable=True, comment='Sum of weighted subject scores'),
        sa.Column('average_score', sa.Numeric(5, 2), nullable=True, comment='Average score across subjects'),
        sa.Column('subjects_count', sa.Integer(), nullable=True, comment='Number of subjects taken'),
        # Rankings
        sa.Column('class_position', sa.Integer(), nullable=True, comment='Position in class (all sections)'),
        sa.Column('section_position', sa.Integer(), nullable=True, comment='Position in section'),
        sa.Column('class_size', sa.Integer(), nullable=True, comment='Total students in class'),
        sa.Column('section_size', sa.Integer(), nullable=True, comment='Total students in section'),
        # Attendance
        sa.Column('attendance_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('days_present', sa.Integer(), nullable=True),
        sa.Column('days_absent', sa.Integer(), nullable=True),
        sa.Column('total_school_days', sa.Integer(), nullable=True),
        # Conduct & Remarks
        sa.Column('conduct_grade', sa.String(5), nullable=True, comment='Conduct grade (A, B, C, D, E, F)'),
        sa.Column('interest', sa.Text(), nullable=True, comment='Student interests/activities'),
        sa.Column('class_teacher_remark', sa.Text(), nullable=True, comment="Class teacher's general remark"),
        sa.Column('headmaster_remark', sa.Text(), nullable=True, comment="Headmaster's remark"),
        # Publishing
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false', comment='Is report visible to parents?'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_id'], ['class_sections.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'term_id', 'student_id', name='uq_term_report_student'),
    )
    op.create_index('ix_term_reports_tenant_id', 'term_reports', ['tenant_id'])
    op.create_index('ix_term_reports_term_id', 'term_reports', ['term_id'])
    op.create_index('ix_term_reports_student_id', 'term_reports', ['student_id'])
    op.create_index('ix_term_reports_class_id', 'term_reports', ['class_id'])


def downgrade() -> None:
    """Drop examination tables."""
    # Drop tables
    op.drop_table('term_reports')
    op.drop_table('continuous_assessments')
    op.drop_table('exam_scores')
    op.drop_table('exam_subjects')
    op.drop_table('exams')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS assessmenttype')
    op.execute('DROP TYPE IF EXISTS examsubjectstatus')
    op.execute('DROP TYPE IF EXISTS examstatus')
    op.execute('DROP TYPE IF EXISTS examtype')

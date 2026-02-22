"""Add class_timetables table

Revision ID: 20260112_0100
Revises: 20260111_0300_add_score_change_log
Create Date: 2026-01-12 01:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260112_0100'
down_revision = '20260111_0300'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create class_timetables table
    op.create_table(
        'class_timetables',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('academic_year_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subject_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('day_of_week', sa.Integer(), nullable=False, comment='Day of week (0=Monday, 6=Sunday)'),
        sa.Column('period_number', sa.Integer(), nullable=False, comment='Period number within the day (1, 2, 3...)'),
        sa.Column('start_time', sa.String(5), nullable=False, comment='Start time in HH:MM format'),
        sa.Column('end_time', sa.String(5), nullable=False, comment='End time in HH:MM format'),
        sa.Column('room', sa.String(100), nullable=True, comment='Room or venue for the class'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='Whether this timetable entry is active'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Additional notes'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_id'], ['class_sections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['teacher_id'], ['staff.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'class_id', 'section_id', 'academic_year_id', 'day_of_week', 'period_number', name='uq_timetable_period'),
    )

    # Create indexes
    op.create_index('ix_class_timetables_tenant_id', 'class_timetables', ['tenant_id'])
    op.create_index('ix_class_timetables_class_id', 'class_timetables', ['class_id'])
    op.create_index('ix_class_timetables_section_id', 'class_timetables', ['section_id'])
    op.create_index('ix_class_timetables_academic_year_id', 'class_timetables', ['academic_year_id'])
    op.create_index('ix_class_timetables_teacher_id', 'class_timetables', ['teacher_id'])
    op.create_index('ix_class_timetables_day_period', 'class_timetables', ['day_of_week', 'period_number'])

    # Enable RLS
    op.execute('ALTER TABLE class_timetables ENABLE ROW LEVEL SECURITY')

    # Create RLS policy
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON class_timetables
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)


def downgrade() -> None:
    # Drop RLS policy
    op.execute('DROP POLICY IF EXISTS tenant_isolation_policy ON class_timetables')

    # Drop indexes
    op.drop_index('ix_class_timetables_day_period', table_name='class_timetables')
    op.drop_index('ix_class_timetables_teacher_id', table_name='class_timetables')
    op.drop_index('ix_class_timetables_academic_year_id', table_name='class_timetables')
    op.drop_index('ix_class_timetables_section_id', table_name='class_timetables')
    op.drop_index('ix_class_timetables_class_id', table_name='class_timetables')
    op.drop_index('ix_class_timetables_tenant_id', table_name='class_timetables')

    # Drop table
    op.drop_table('class_timetables')

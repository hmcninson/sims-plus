"""Add timetable enhancements: term support, periods, holidays

Revision ID: 20260112_0200
Revises: 20260112_0100
Create Date: 2026-01-12 02:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260112_0200'
down_revision = '20260112_0100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================
    # 1. Create school_periods table
    # =====================
    op.create_table(
        'school_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_number', sa.Integer(), nullable=False, comment='Period number (1, 2, 3...)'),
        sa.Column('name', sa.String(50), nullable=True, comment='Period name (e.g., Morning Assembly, Break)'),
        sa.Column('start_time', sa.String(5), nullable=False, comment='Start time in HH:MM format'),
        sa.Column('end_time', sa.String(5), nullable=False, comment='End time in HH:MM format'),
        sa.Column('is_break', sa.Boolean(), nullable=False, default=False, comment='Whether this is a break period'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'period_number', name='uq_school_period'),
    )
    op.create_index('ix_school_periods_tenant_id', 'school_periods', ['tenant_id'])

    # Enable RLS for school_periods
    op.execute('ALTER TABLE school_periods ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON school_periods
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)

    # =====================
    # 2. Create school_holidays table
    # =====================
    op.create_table(
        'school_holidays',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False, comment='Holiday date'),
        sa.Column('name', sa.String(100), nullable=False, comment='Holiday name'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('holiday_type', sa.String(20), nullable=False, default='holiday', comment='Type: holiday, exam, event, vacation'),
        sa.Column('academic_year_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Associated academic year'),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, default=False, comment='Whether this holiday recurs every year'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'date', name='uq_school_holiday_date'),
    )
    op.create_index('ix_school_holidays_tenant_id', 'school_holidays', ['tenant_id'])
    op.create_index('ix_school_holidays_date', 'school_holidays', ['date'])
    op.create_index('ix_school_holidays_academic_year_id', 'school_holidays', ['academic_year_id'])

    # Enable RLS for school_holidays
    op.execute('ALTER TABLE school_holidays ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON school_holidays
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
    """)

    # =====================
    # 3. Add term_id to class_timetables
    # =====================
    op.add_column(
        'class_timetables',
        sa.Column('term_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Optional: if set, timetable applies only to this term')
    )
    op.create_foreign_key(
        'fk_class_timetables_term_id',
        'class_timetables',
        'terms',
        ['term_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.create_index('ix_class_timetables_term_id', 'class_timetables', ['term_id'])

    # =====================
    # 4. Update unique constraint to include term_id
    # =====================
    # Drop old constraint
    op.drop_constraint('uq_timetable_period', 'class_timetables', type_='unique')

    # Create new constraint with term_id
    op.create_unique_constraint(
        'uq_timetable_period',
        'class_timetables',
        ['tenant_id', 'class_id', 'section_id', 'academic_year_id', 'term_id', 'day_of_week', 'period_number']
    )


def downgrade() -> None:
    # Restore old unique constraint
    op.drop_constraint('uq_timetable_period', 'class_timetables', type_='unique')
    op.create_unique_constraint(
        'uq_timetable_period',
        'class_timetables',
        ['tenant_id', 'class_id', 'section_id', 'academic_year_id', 'day_of_week', 'period_number']
    )

    # Remove term_id from class_timetables
    op.drop_index('ix_class_timetables_term_id', table_name='class_timetables')
    op.drop_constraint('fk_class_timetables_term_id', 'class_timetables', type_='foreignkey')
    op.drop_column('class_timetables', 'term_id')

    # Drop school_holidays
    op.execute('DROP POLICY IF EXISTS tenant_isolation_policy ON school_holidays')
    op.drop_index('ix_school_holidays_academic_year_id', table_name='school_holidays')
    op.drop_index('ix_school_holidays_date', table_name='school_holidays')
    op.drop_index('ix_school_holidays_tenant_id', table_name='school_holidays')
    op.drop_table('school_holidays')

    # Drop school_periods
    op.execute('DROP POLICY IF EXISTS tenant_isolation_policy ON school_periods')
    op.drop_index('ix_school_periods_tenant_id', table_name='school_periods')
    op.drop_table('school_periods')

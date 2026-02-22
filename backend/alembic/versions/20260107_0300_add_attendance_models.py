"""Add student and staff attendance tables.

Revision ID: 20260107_0300
Revises: 20260107_0200
Create Date: 2026-01-07 03:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260107_0300"
down_revision: Union[str, None] = "20260107_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create student_attendance and staff_attendance tables."""
    # Create attendance status enum
    attendancestatus_enum = postgresql.ENUM(
        'present', 'absent', 'late', 'excused', 'sick',
        name='attendancestatus', create_type=False
    )
    attendancestatus_enum.create(op.get_bind(), checkfirst=True)

    # Create student_attendance table
    op.create_table(
        'student_attendance',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # Foreign keys
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('section_id', sa.UUID(), nullable=False, comment='Class section at time of attendance'),
        sa.Column('term_id', sa.UUID(), nullable=True, comment='Academic term for this attendance'),
        # Attendance details
        sa.Column('date', sa.Date(), nullable=False, comment='Date of attendance'),
        sa.Column('status', attendancestatus_enum, nullable=False, server_default='present'),
        sa.Column('check_in_time', sa.Time(), nullable=True, comment='Time student checked in'),
        sa.Column('check_out_time', sa.Time(), nullable=True, comment='Time student checked out'),
        # Additional info
        sa.Column('remarks', sa.Text(), nullable=True, comment='Notes/remarks'),
        sa.Column('excuse_reason', sa.String(255), nullable=True, comment='Reason for absence/excuse'),
        sa.Column('marked_by', sa.UUID(), nullable=True, comment='User who marked this attendance'),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_id'], ['class_sections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['marked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'student_id', 'date', name='uq_student_attendance_date'),
    )
    op.create_index('ix_student_attendance_tenant_id', 'student_attendance', ['tenant_id'])
    op.create_index('ix_student_attendance_student_id', 'student_attendance', ['student_id'])
    op.create_index('ix_student_attendance_section_id', 'student_attendance', ['section_id'])
    op.create_index('ix_student_attendance_date', 'student_attendance', ['date'])
    op.create_index('ix_student_attendance_term_id', 'student_attendance', ['term_id'])

    # Create staff_attendance table
    op.create_table(
        'staff_attendance',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        # Foreign keys
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('term_id', sa.UUID(), nullable=True, comment='Academic term for this attendance'),
        # Attendance details
        sa.Column('date', sa.Date(), nullable=False, comment='Date of attendance'),
        sa.Column('status', attendancestatus_enum, nullable=False, server_default='present'),
        sa.Column('check_in_time', sa.Time(), nullable=True, comment='Time staff checked in'),
        sa.Column('check_out_time', sa.Time(), nullable=True, comment='Time staff checked out'),
        # Additional info
        sa.Column('remarks', sa.Text(), nullable=True, comment='Notes/remarks'),
        sa.Column('excuse_reason', sa.String(255), nullable=True, comment='Reason for absence/excuse'),
        sa.Column('marked_by', sa.UUID(), nullable=True, comment='User who marked this attendance'),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['marked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'staff_id', 'date', name='uq_staff_attendance_date'),
    )
    op.create_index('ix_staff_attendance_tenant_id', 'staff_attendance', ['tenant_id'])
    op.create_index('ix_staff_attendance_staff_id', 'staff_attendance', ['staff_id'])
    op.create_index('ix_staff_attendance_date', 'staff_attendance', ['date'])
    op.create_index('ix_staff_attendance_term_id', 'staff_attendance', ['term_id'])

    # Enable RLS on attendance tables
    op.execute("ALTER TABLE student_attendance ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE staff_attendance ENABLE ROW LEVEL SECURITY")

    # Create RLS policies for student_attendance
    op.execute("""
        CREATE POLICY student_attendance_tenant_isolation ON student_attendance
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for staff_attendance
    op.execute("""
        CREATE POLICY staff_attendance_tenant_isolation ON staff_attendance
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    """Drop attendance tables and enum."""
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS staff_attendance_tenant_isolation ON staff_attendance")
    op.execute("DROP POLICY IF EXISTS student_attendance_tenant_isolation ON student_attendance")

    # Drop tables
    op.drop_table('staff_attendance')
    op.drop_table('student_attendance')

    # Drop enum
    op.execute("DROP TYPE IF EXISTS attendancestatus")

"""Add staff and staff_class_assignments tables.

Revision ID: 20260107_0200
Revises: 20260107_0100
Create Date: 2026-01-07 02:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260107_0200"
down_revision: Union[str, None] = "20260107_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create staff and staff_class_assignments tables."""
    # Create enums
    stafftype_enum = postgresql.ENUM(
        'teaching', 'non_teaching', 'administrative',
        name='stafftype', create_type=False
    )
    stafftype_enum.create(op.get_bind(), checkfirst=True)

    staffstatus_enum = postgresql.ENUM(
        'active', 'on_leave', 'suspended', 'terminated', 'retired',
        name='staffstatus', create_type=False
    )
    staffstatus_enum.create(op.get_bind(), checkfirst=True)

    # Create staff table
    op.create_table(
        'staff',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        # System ID
        sa.Column('staff_id', sa.String(50), nullable=False, comment='System-generated unique staff ID'),
        # Basic info
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('gender', postgresql.ENUM('male', 'female', name='gender', create_type=False), nullable=False),
        # Contact
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('phone_secondary', sa.String(20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        # Emergency contact
        sa.Column('emergency_contact_name', sa.String(200), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(20), nullable=True),
        sa.Column('emergency_contact_relationship', sa.String(50), nullable=True),
        # Ghana-specific IDs
        sa.Column('ghana_card_number', sa.String(50), nullable=True),
        sa.Column('ssnit_number', sa.String(50), nullable=True),
        sa.Column('teacher_license_number', sa.String(50), nullable=True, comment='GES Teacher License Number'),
        # Employment info
        sa.Column('staff_type', stafftype_enum, nullable=False, server_default='teaching'),
        sa.Column('status', staffstatus_enum, nullable=False, server_default='active'),
        sa.Column('job_title', sa.String(100), nullable=False),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('employment_date', sa.Date(), nullable=False),
        sa.Column('termination_date', sa.Date(), nullable=True),
        # Qualifications (JSONB)
        sa.Column('qualifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Banking info
        sa.Column('bank_name', sa.String(100), nullable=True),
        sa.Column('bank_branch', sa.String(100), nullable=True),
        sa.Column('account_number', sa.String(50), nullable=True),
        # Photo
        sa.Column('photo_url', sa.String(500), nullable=True),
        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        # Foreign keys
        sa.Column('school_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True, unique=True, comment='Link to User for system login'),
        # Constraints
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id', 'tenant_id', name='uq_staff_staff_id_tenant'),
        sa.UniqueConstraint('email', 'tenant_id', name='uq_staff_email_tenant'),
    )
    op.create_index('ix_staff_tenant_id', 'staff', ['tenant_id'])
    op.create_index('ix_staff_staff_id', 'staff', ['staff_id'])
    op.create_index('ix_staff_email', 'staff', ['email'])
    op.create_index('ix_staff_school_id', 'staff', ['school_id'])

    # Create staff_class_assignments table
    op.create_table(
        'staff_class_assignments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('section_id', sa.UUID(), nullable=False),
        sa.Column('is_class_teacher', sa.Boolean(), nullable=False, server_default='false', comment='Whether this staff is the class teacher'),
        sa.Column('subject_id', sa.UUID(), nullable=True, comment='Subject taught in this section'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_id'], ['class_sections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id', 'section_id', 'tenant_id', name='uq_staff_class_assignment_tenant'),
    )
    op.create_index('ix_staff_class_assignments_tenant_id', 'staff_class_assignments', ['tenant_id'])
    op.create_index('ix_staff_class_assignments_staff_id', 'staff_class_assignments', ['staff_id'])
    op.create_index('ix_staff_class_assignments_section_id', 'staff_class_assignments', ['section_id'])

    # Enable RLS on staff tables
    op.execute("ALTER TABLE staff ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE staff_class_assignments ENABLE ROW LEVEL SECURITY")

    # Create RLS policies for staff
    op.execute("""
        CREATE POLICY staff_tenant_isolation ON staff
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for staff_class_assignments
    op.execute("""
        CREATE POLICY staff_class_assignments_tenant_isolation ON staff_class_assignments
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    """Drop staff tables and enums."""
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS staff_class_assignments_tenant_isolation ON staff_class_assignments")
    op.execute("DROP POLICY IF EXISTS staff_tenant_isolation ON staff")

    # Drop tables
    op.drop_table('staff_class_assignments')
    op.drop_table('staff')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS staffstatus")
    op.execute("DROP TYPE IF EXISTS stafftype")

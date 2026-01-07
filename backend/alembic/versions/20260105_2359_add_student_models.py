"""Add student and guardian models.

Revision ID: 20260105_2359
Revises: 20260105_2155
Create Date: 2026-01-05 23:59:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260105_2359"
down_revision: Union[str, None] = "20260105_2155"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create students, guardians, and student_guardians tables."""
    # Create enums
    gender_enum = postgresql.ENUM('male', 'female', name='gender', create_type=False)
    gender_enum.create(op.get_bind(), checkfirst=True)

    studentstatus_enum = postgresql.ENUM(
        'active', 'inactive', 'graduated', 'transferred', 'withdrawn', 'suspended',
        name='studentstatus', create_type=False
    )
    studentstatus_enum.create(op.get_bind(), checkfirst=True)

    guardianrelationship_enum = postgresql.ENUM(
        'father', 'mother', 'guardian', 'grandfather', 'grandmother',
        'uncle', 'aunt', 'sibling', 'other',
        name='guardianrelationship', create_type=False
    )
    guardianrelationship_enum.create(op.get_bind(), checkfirst=True)

    # Create guardians table
    op.create_table(
        'guardians',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        # Basic info
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        # Contact
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('phone_secondary', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        # Work info
        sa.Column('occupation', sa.String(200), nullable=True),
        sa.Column('workplace', sa.String(200), nullable=True),
        sa.Column('work_phone', sa.String(20), nullable=True),
        # Ghana-specific
        sa.Column('ghana_card_number', sa.String(50), nullable=True),
        # Other
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'tenant_id', name='uq_guardians_email_tenant'),
    )
    op.create_index('ix_guardians_tenant_id', 'guardians', ['tenant_id'])

    # Create students table
    op.create_table(
        'students',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        # Basic info
        sa.Column('student_id', sa.String(50), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', gender_enum, nullable=False),
        # Contact
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        # Ghana-specific IDs
        sa.Column('ghana_card_number', sa.String(50), nullable=True),
        sa.Column('nhis_number', sa.String(50), nullable=True),
        # Academic info
        sa.Column('school_id', sa.UUID(), nullable=True),
        sa.Column('class_id', sa.UUID(), nullable=True),
        sa.Column('section_id', sa.UUID(), nullable=True),
        sa.Column('admission_date', sa.Date(), nullable=True),
        sa.Column('admission_number', sa.String(50), nullable=True),
        # Status
        sa.Column('status', studentstatus_enum, nullable=False, server_default='active'),
        # Boarding
        sa.Column('is_boarder', sa.Boolean(), nullable=False, server_default='false'),
        # Medical
        sa.Column('blood_group', sa.String(10), nullable=True),
        sa.Column('medical_conditions', sa.Text(), nullable=True),
        sa.Column('allergies', sa.Text(), nullable=True),
        # Photo
        sa.Column('photo_url', sa.String(500), nullable=True),
        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['section_id'], ['class_sections.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'tenant_id', name='uq_students_student_id_tenant'),
    )
    op.create_index('ix_students_tenant_id', 'students', ['tenant_id'])
    op.create_index('ix_students_student_id', 'students', ['student_id'])
    op.create_index('ix_students_class_id', 'students', ['class_id'])
    op.create_index('ix_students_section_id', 'students', ['section_id'])

    # Create student_guardians association table
    op.create_table(
        'student_guardians',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('guardian_id', sa.UUID(), nullable=False),
        sa.Column('relationship', guardianrelationship_enum, nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_emergency_contact', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_pickup', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['guardian_id'], ['guardians.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'guardian_id', 'tenant_id', name='uq_student_guardian_tenant'),
    )
    op.create_index('ix_student_guardians_tenant_id', 'student_guardians', ['tenant_id'])
    op.create_index('ix_student_guardians_student_id', 'student_guardians', ['student_id'])
    op.create_index('ix_student_guardians_guardian_id', 'student_guardians', ['guardian_id'])

    # Enable RLS on all tables
    op.execute("ALTER TABLE guardians ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE students ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_guardians ENABLE ROW LEVEL SECURITY")

    # Create RLS policies for guardians
    op.execute("""
        CREATE POLICY guardians_tenant_isolation ON guardians
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for students
    op.execute("""
        CREATE POLICY students_tenant_isolation ON students
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create RLS policies for student_guardians
    op.execute("""
        CREATE POLICY student_guardians_tenant_isolation ON student_guardians
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    """Drop student tables and enums."""
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS student_guardians_tenant_isolation ON student_guardians")
    op.execute("DROP POLICY IF EXISTS students_tenant_isolation ON students")
    op.execute("DROP POLICY IF EXISTS guardians_tenant_isolation ON guardians")

    # Drop tables
    op.drop_table('student_guardians')
    op.drop_table('students')
    op.drop_table('guardians')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS guardianrelationship")
    op.execute("DROP TYPE IF EXISTS studentstatus")
    op.execute("DROP TYPE IF EXISTS gender")

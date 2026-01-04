"""add_schools_table

Revision ID: add_schools_table
Revises: security_fixes_001
Create Date: 2026-01-04 04:00:00.000000+00:00

This migration:
1. Creates the schools table
2. Adds foreign key from users to schools
3. Enables RLS on schools table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_schools_table'
down_revision: Union[str, None] = 'security_fixes_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create schools table and enable RLS."""

    # 1. Create schools table
    op.create_table(
        'schools',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),

        # Basic Information
        sa.Column('name', sa.String(length=255), nullable=False, comment='Official school name'),
        sa.Column('slug', sa.String(length=100), nullable=False, comment='URL-friendly identifier'),
        sa.Column('code', sa.String(length=50), nullable=True, comment='School code (e.g., GES code)'),
        sa.Column('school_type', sa.Enum('primary', 'jhs', 'shs', 'basic', 'international', 'technical', 'preschool', name='schooltype'), nullable=False),
        sa.Column('status', sa.Enum('active', 'inactive', 'suspended', name='schoolstatus'), nullable=False, server_default='active'),

        # Contact
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),

        # Address
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True, comment='Ghana region'),
        sa.Column('gps_address', sa.String(length=50), nullable=True, comment='Ghana GPS address'),

        # Branding
        sa.Column('logo_url', sa.String(length=500), nullable=True, comment='School logo URL'),
        sa.Column('primary_color', sa.String(length=7), nullable=True, comment='Primary brand color (hex)'),
        sa.Column('motto', sa.String(length=255), nullable=True, comment='School motto'),

        # Features
        sa.Column('uses_boarding', sa.Boolean(), nullable=False, server_default='false', comment='Has boarding facilities'),
        sa.Column('uses_transport', sa.Boolean(), nullable=False, server_default='false', comment='Provides transport services'),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),

        # Keys
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )

    # 2. Create indexes
    op.create_index('ix_schools_tenant_id', 'schools', ['tenant_id'])
    op.create_index('ix_schools_slug', 'schools', ['slug'])
    op.create_index('ix_schools_status', 'schools', ['status'])

    # 3. Create unique constraint on slug within tenant
    op.create_unique_constraint(
        'uq_schools_tenant_slug',
        'schools',
        ['tenant_id', 'slug']
    )

    # 4. Enable RLS on schools
    op.execute("ALTER TABLE schools ENABLE ROW LEVEL SECURITY")

    # 5. Create RLS policy for schools
    op.execute("""
        CREATE POLICY tenant_isolation_schools ON schools
        FOR ALL
        TO PUBLIC
        USING (
            (tenant_id = get_current_tenant_id())
            OR
            (current_setting('app.is_platform_admin', true) = 'true')
        )
        WITH CHECK (
            (tenant_id = get_current_tenant_id())
            OR
            (current_setting('app.is_platform_admin', true) = 'true')
        )
    """)

    # 6. Add foreign key from users to schools (if not exists)
    # The users.school_id column already exists, just add the constraint
    op.create_foreign_key(
        'fk_users_school_id',
        'users',
        'schools',
        ['school_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Drop schools table and related constraints."""

    # Remove FK from users
    op.drop_constraint('fk_users_school_id', 'users', type_='foreignkey')

    # Remove RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation_schools ON schools")
    op.execute("ALTER TABLE schools DISABLE ROW LEVEL SECURITY")

    # Drop indexes
    op.drop_constraint('uq_schools_tenant_slug', 'schools', type_='unique')
    op.drop_index('ix_schools_status', table_name='schools')
    op.drop_index('ix_schools_slug', table_name='schools')
    op.drop_index('ix_schools_tenant_id', table_name='schools')

    # Drop table
    op.drop_table('schools')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS schoolstatus")
    op.execute("DROP TYPE IF EXISTS schooltype")

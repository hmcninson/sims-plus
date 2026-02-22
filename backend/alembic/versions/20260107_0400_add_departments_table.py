"""Add departments table

Revision ID: 20260107_0400
Revises: 20260107_0300_add_attendance_models
Create Date: 2026-01-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260107_0400'
down_revision = '20260107_0300'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create departments table
    op.create_table(
        'departments',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('head_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unique constraint for department name per tenant
    op.create_unique_constraint(
        'uq_department_name_tenant',
        'departments',
        ['name', 'tenant_id', 'deleted_at']
    )

    # Create index on tenant_id
    op.create_index('ix_departments_tenant_id', 'departments', ['tenant_id'])

    # Add department_id column to staff table
    op.add_column('staff', sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Add foreign key constraint for department_id
    op.create_foreign_key(
        'fk_staff_department_id',
        'staff',
        'departments',
        ['department_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add foreign key constraint for head_id in departments (after staff table has department_id)
    op.create_foreign_key(
        'fk_department_head_id',
        'departments',
        'staff',
        ['head_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key constraint for head_id
    op.drop_constraint('fk_department_head_id', 'departments', type_='foreignkey')

    # Drop foreign key constraint for department_id
    op.drop_constraint('fk_staff_department_id', 'staff', type_='foreignkey')

    # Drop department_id column from staff
    op.drop_column('staff', 'department_id')

    # Drop departments table
    op.drop_index('ix_departments_tenant_id', 'departments')
    op.drop_constraint('uq_department_name_tenant', 'departments', type_='unique')
    op.drop_table('departments')

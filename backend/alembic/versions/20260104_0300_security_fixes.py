"""security_fixes

Revision ID: security_fixes_001
Revises: add_subdomain_rls
Create Date: 2026-01-04 03:00:00.000000+00:00

This migration fixes security vulnerabilities:
1. Removes dangerous RLS bypass policy
2. Adds proper RLS policy with app user context
3. Adds FK constraint for users.tenant_id
4. Changes email uniqueness to per-tenant
5. Adds audit columns to tenants
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'security_fixes_001'
down_revision: Union[str, None] = 'add_subdomain_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply security fixes."""

    # 1. Remove dangerous RLS bypass policy
    op.execute("DROP POLICY IF EXISTS allow_all_for_setup ON users")

    # 2. Create a safer RLS policy that allows superuser/app role to bypass
    # The application should use a dedicated role with BYPASSRLS for admin operations
    op.execute("""
        CREATE POLICY app_bypass_policy ON users
        FOR ALL
        TO PUBLIC
        USING (
            -- Allow if tenant context is set and matches
            (tenant_id = get_current_tenant_id())
            OR
            -- Allow platform admins (checked via session variable)
            (current_setting('app.is_platform_admin', true) = 'true')
        )
        WITH CHECK (
            (tenant_id = get_current_tenant_id())
            OR
            (current_setting('app.is_platform_admin', true) = 'true')
        )
    """)

    # 3. Drop the old tenant_isolation_policy (we're replacing it)
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON users")

    # 4. Add helper function to set platform admin context
    op.execute("""
        CREATE OR REPLACE FUNCTION set_platform_admin_context(is_admin BOOLEAN)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.is_platform_admin', is_admin::TEXT, false);
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 5. Add helper function to clear tenant context (for safety)
    op.execute("""
        CREATE OR REPLACE FUNCTION clear_tenant_context()
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', '', false);
            PERFORM set_config('app.is_platform_admin', 'false', false);
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 6. Add FK constraint for users.tenant_id
    op.create_foreign_key(
        'fk_users_tenant_id',
        'users',
        'tenants',
        ['tenant_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # 7. Drop global unique constraint on email
    op.drop_index('ix_users_email', table_name='users')

    # 8. Create composite unique constraint (email + tenant_id)
    op.create_unique_constraint(
        'uq_users_email_tenant',
        'users',
        ['email', 'tenant_id']
    )

    # 9. Create index on email for performance (non-unique)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # 10. Add audit columns to tenants table
    op.add_column(
        'tenants',
        sa.Column('created_by', sa.UUID(), nullable=True,
                  comment='User who created the tenant')
    )
    op.add_column(
        'tenants',
        sa.Column('updated_by', sa.UUID(), nullable=True,
                  comment='User who last updated the tenant')
    )

    # 11. Create audit log table for security-sensitive operations
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True, comment='Tenant context (null for platform operations)'),
        sa.Column('user_id', sa.UUID(), nullable=True, comment='User who performed the action'),
        sa.Column('action', sa.String(100), nullable=False, comment='Action type (e.g., tenant.create, user.login)'),
        sa.Column('resource_type', sa.String(100), nullable=False, comment='Resource type (e.g., tenant, user)'),
        sa.Column('resource_id', sa.UUID(), nullable=True, comment='ID of affected resource'),
        sa.Column('details', sa.Text(), nullable=True, comment='JSON details of the action'),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='Client IP address'),
        sa.Column('user_agent', sa.String(500), nullable=True, comment='Client user agent'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    """Revert security fixes."""

    # Drop audit_logs table
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_tenant_id', table_name='audit_logs')
    op.drop_table('audit_logs')

    # Remove audit columns from tenants
    op.drop_column('tenants', 'updated_by')
    op.drop_column('tenants', 'created_by')

    # Restore global unique email constraint
    op.drop_index('ix_users_email', table_name='users')
    op.drop_constraint('uq_users_email_tenant', 'users', type_='unique')
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Remove FK constraint
    op.drop_constraint('fk_users_tenant_id', 'users', type_='foreignkey')

    # Drop helper functions
    op.execute("DROP FUNCTION IF EXISTS clear_tenant_context()")
    op.execute("DROP FUNCTION IF EXISTS set_platform_admin_context(BOOLEAN)")

    # Restore original policies
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON users")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON users
        FOR ALL
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY allow_all_for_setup ON users
        FOR ALL
        USING (get_current_tenant_id() IS NULL)
        WITH CHECK (get_current_tenant_id() IS NULL)
    """)

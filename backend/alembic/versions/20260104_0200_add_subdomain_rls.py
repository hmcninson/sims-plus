"""add_subdomain_and_rls

Revision ID: add_subdomain_rls
Revises: 8176a9079aeb
Create Date: 2026-01-04 02:00:00.000000+00:00

This migration:
1. Adds subdomain column to tenants table
2. Adds branding columns (logo_url, primary_color) to tenants
3. Creates reserved_subdomains table
4. Implements RLS policies and set_tenant_context() function
5. Seeds default reserved subdomains
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'add_subdomain_rls'
down_revision: Union[str, None] = '8176a9079aeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default reserved subdomains
RESERVED_SUBDOMAINS = [
    ("www", "Main website"),
    ("api", "API endpoint"),
    ("app", "Application portal"),
    ("admin", "Admin portal"),
    ("mail", "Email services"),
    ("ftp", "FTP services"),
    ("status", "Status page"),
    ("blog", "Blog"),
    ("help", "Help center"),
    ("support", "Support portal"),
    ("docs", "Documentation"),
    ("cdn", "Content delivery"),
    ("assets", "Static assets"),
    ("staging", "Staging environment"),
    ("dev", "Development environment"),
    ("test", "Testing environment"),
    ("demo", "Demo environment"),
    ("sandbox", "Sandbox environment"),
    ("beta", "Beta environment"),
    ("alpha", "Alpha environment"),
    ("portal", "Generic portal"),
    ("login", "Login page"),
    ("register", "Registration page"),
    ("signup", "Signup page"),
    ("dashboard", "Dashboard"),
    ("billing", "Billing portal"),
    ("payments", "Payments"),
    ("webhooks", "Webhook endpoints"),
    ("graphql", "GraphQL endpoint"),
    ("ws", "WebSocket endpoint"),
    ("static", "Static files"),
    ("media", "Media files"),
    ("images", "Image files"),
    ("files", "File storage"),
    ("downloads", "Downloads"),
    ("uploads", "Uploads"),
]


def upgrade() -> None:
    """Upgrade database schema."""

    # 1. Add subdomain column to tenants (copy from slug initially)
    op.add_column(
        'tenants',
        sa.Column('subdomain', sa.String(length=63), nullable=True,
                  comment='Unique subdomain for tenant (e.g., presec, achimota)')
    )

    # Copy slug values to subdomain
    op.execute("UPDATE tenants SET subdomain = slug WHERE subdomain IS NULL")

    # Make subdomain non-nullable and add unique constraint
    op.alter_column('tenants', 'subdomain', nullable=False)
    op.create_index('ix_tenants_subdomain', 'tenants', ['subdomain'], unique=True)

    # 2. Add branding columns to tenants
    op.add_column(
        'tenants',
        sa.Column('logo_url', sa.String(length=500), nullable=True,
                  comment='URL to tenant logo')
    )
    op.add_column(
        'tenants',
        sa.Column('primary_color', sa.String(length=7), nullable=True,
                  server_default='#1B4F72', comment='Primary brand color (hex)')
    )

    # 3. Create reserved_subdomains table
    op.create_table(
        'reserved_subdomains',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('subdomain', sa.String(length=63), nullable=False,
                  comment='Reserved subdomain (e.g., www, api, admin)'),
        sa.Column('reason', sa.Text(), nullable=True,
                  comment='Reason for reservation'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reserved_subdomains_subdomain', 'reserved_subdomains',
                    ['subdomain'], unique=True)

    # 4. Seed reserved subdomains (using parameterized queries to prevent SQL injection)
    connection = op.get_bind()
    for subdomain, reason in RESERVED_SUBDOMAINS:
        connection.execute(
            text("INSERT INTO reserved_subdomains (subdomain, reason) VALUES (:subdomain, :reason)"),
            {"subdomain": subdomain, "reason": reason}
        )

    # 5. Create set_tenant_context function
    op.execute("""
        CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 6. Create get_current_tenant_id function
    op.execute("""
        CREATE OR REPLACE FUNCTION get_current_tenant_id()
        RETURNS UUID AS $$
        BEGIN
            RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
        EXCEPTION
            WHEN OTHERS THEN
                RETURN NULL;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)

    # 7. Enable RLS on users table
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")

    # 8. Create RLS policy for users table
    # Policy for SELECT, INSERT, UPDATE, DELETE - only see rows where tenant_id matches
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON users
        FOR ALL
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)

    # 9. Create bypass policy for platform admins (superuser role bypasses RLS by default)
    # This policy allows the application to set context before queries
    op.execute("""
        CREATE POLICY allow_all_for_setup ON users
        FOR ALL
        USING (get_current_tenant_id() IS NULL)
        WITH CHECK (get_current_tenant_id() IS NULL)
    """)


def downgrade() -> None:
    """Downgrade database schema."""

    # Remove RLS policies
    op.execute("DROP POLICY IF EXISTS allow_all_for_setup ON users")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS get_current_tenant_id()")
    op.execute("DROP FUNCTION IF EXISTS set_tenant_context(UUID)")

    # Drop reserved_subdomains table
    op.drop_index('ix_reserved_subdomains_subdomain', table_name='reserved_subdomains')
    op.drop_table('reserved_subdomains')

    # Remove branding columns from tenants
    op.drop_column('tenants', 'primary_color')
    op.drop_column('tenants', 'logo_url')

    # Remove subdomain column from tenants
    op.drop_index('ix_tenants_subdomain', table_name='tenants')
    op.drop_column('tenants', 'subdomain')

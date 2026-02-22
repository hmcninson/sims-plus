"""comprehensive_rls_policies

Revision ID: comprehensive_rls
Revises: add_schools_table
Create Date: 2026-01-04 05:00:00.000000+00:00

This migration ensures comprehensive RLS policies across all tenant-scoped tables.
It consolidates RLS policies and ensures consistent tenant isolation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'comprehensive_rls'
down_revision: Union[str, None] = 'add_schools_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that require tenant isolation (all have tenant_id column)
TENANT_SCOPED_TABLES = [
    'users',
    'schools',
    # Future tables will be added as they are created:
    # 'students',
    # 'staff',
    # 'classes',
    # 'sections',
    # 'subjects',
    # 'attendance',
    # 'exams',
    # 'exam_results',
    # 'fees',
    # 'invoices',
    # 'payments',
    # 'dormitories',
    # 'rooms',
    # 'beds',
    # 'exeats',
]


def create_rls_policy(table_name: str) -> None:
    """Create standard RLS policy for a tenant-scoped table."""
    connection = op.get_bind()

    # Drop existing policies if any
    connection.execute(text(f"""
        DO $$
        BEGIN
            -- Drop all existing policies on the table
            EXECUTE (
                SELECT string_agg('DROP POLICY IF EXISTS ' || policyname || ' ON {table_name};', E'\n')
                FROM pg_policies
                WHERE tablename = '{table_name}'
            );
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END $$;
    """))

    # Enable RLS if not already enabled
    connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))

    # Force RLS for table owner too (important for security)
    connection.execute(text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))

    # Create comprehensive tenant isolation policy
    connection.execute(text(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
        FOR ALL
        TO PUBLIC
        USING (
            -- Allow access if:
            -- 1. Tenant context matches the row's tenant_id
            (tenant_id = get_current_tenant_id())
            OR
            -- 2. No tenant context is set (for app startup/migrations)
            (get_current_tenant_id() IS NULL)
            OR
            -- 3. User is a platform admin (superuser)
            (current_setting('app.is_platform_admin', true) = 'true')
        )
        WITH CHECK (
            -- Only allow inserts/updates for:
            -- 1. Rows matching current tenant context
            (tenant_id = get_current_tenant_id())
            OR
            -- 2. No tenant context (app startup/migrations)
            (get_current_tenant_id() IS NULL)
            OR
            -- 3. Platform admin
            (current_setting('app.is_platform_admin', true) = 'true')
        )
    """))


def drop_rls_policy(table_name: str) -> None:
    """Drop RLS policy for a table."""
    connection = op.get_bind()

    connection.execute(text(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"))
    connection.execute(text(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"))
    connection.execute(text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))


def upgrade() -> None:
    """Apply comprehensive RLS policies to all tenant-scoped tables."""
    connection = op.get_bind()

    # First, ensure the helper functions exist and are up to date

    # Update get_current_tenant_id to be more robust
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION get_current_tenant_id()
        RETURNS UUID AS $$
        DECLARE
            tenant_uuid UUID;
            tenant_str TEXT;
        BEGIN
            -- Get the setting, with empty string as default
            tenant_str := current_setting('app.current_tenant_id', true);

            -- Return NULL if empty or not set
            IF tenant_str IS NULL OR tenant_str = '' THEN
                RETURN NULL;
            END IF;

            -- Try to cast to UUID
            BEGIN
                tenant_uuid := tenant_str::UUID;
                RETURN tenant_uuid;
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL;
            END;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))

    # Create a helper to check if current session is platform admin
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION is_platform_admin()
        RETURNS BOOLEAN AS $$
        BEGIN
            RETURN COALESCE(current_setting('app.is_platform_admin', true), 'false') = 'true';
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))

    # Create index on tenant_id for all tables (improves RLS performance)
    for table_name in TENANT_SCOPED_TABLES:
        # Check if table exists before creating policy
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = '{table_name}'
            );
        """))
        table_exists = result.scalar()

        if table_exists:
            # Create index if not exists
            try:
                connection.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant_id
                    ON {table_name} (tenant_id);
                """))
            except Exception:
                pass  # Index might already exist

            # Apply RLS policy
            create_rls_policy(table_name)


def downgrade() -> None:
    """Remove RLS policies from all tenant-scoped tables."""
    connection = op.get_bind()

    # Remove policies from all tables
    for table_name in TENANT_SCOPED_TABLES:
        # Check if table exists
        result = connection.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = '{table_name}'
            );
        """))
        table_exists = result.scalar()

        if table_exists:
            drop_rls_policy(table_name)

    # Drop helper function
    connection.execute(text("DROP FUNCTION IF EXISTS is_platform_admin();"))

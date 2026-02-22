"""
Reusable RLS helpers for Alembic migrations.

Every migration that creates a new tenant-scoped table MUST call:
    from app.db.rls_helpers import enable_rls_for_table, disable_rls_for_table

    def upgrade():
        # ... create table ...
        enable_rls_for_table(op.get_bind(), 'new_table_name')

    def downgrade():
        disable_rls_for_table(op.get_bind(), 'new_table_name')
        # ... drop table ...

SECURITY INVARIANTS:
- No NULL bypass: when get_current_tenant_id() returns NULL, tenant_id = NULL
  evaluates to NULL (FALSE). Zero rows returned.
- No platform admin bypass: platform admin operations use the sims_admin
  superuser role, not a session variable.
- FORCE ROW LEVEL SECURITY: RLS is enforced even for the table owner.
  This means sims_app_user cannot bypass RLS even if it owns the table.
- Policy targets sims_app_user specifically (not PUBLIC), so superuser
  connections (sims_admin, postgres) are not affected during migrations.
"""

from sqlalchemy import text


def enable_rls_for_table(connection, table_name: str) -> None:
    """Enable hardened RLS with tenant isolation policy on a table.

    Args:
        connection: SQLAlchemy connection (from op.get_bind())
        table_name: Name of the table to protect

    SECURITY: No NULL bypass. No platform admin bypass.
    When get_current_tenant_id() returns NULL, tenant_id = NULL evaluates
    to FALSE. Zero rows returned. Safe default.
    """
    # Drop any existing policies on this table
    connection.execute(text(f"""
        DO $$
        DECLARE
            pol RECORD;
        BEGIN
            FOR pol IN
                SELECT policyname FROM pg_policies WHERE tablename = '{table_name}'
            LOOP
                EXECUTE 'DROP POLICY IF EXISTS ' || quote_ident(pol.policyname) || ' ON {table_name}';
            END LOOP;
        END $$;
    """))

    # Enable RLS
    connection.execute(text(
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
    ))

    # FORCE RLS even for table owner (critical for defense-in-depth)
    connection.execute(text(
        f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"
    ))

    # Create hardened policy -- NO bypasses
    # Target sims_app_user specifically so superuser migrations are not blocked
    connection.execute(text(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
        FOR ALL
        TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """))

    # Grant table permissions to app user
    connection.execute(text(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
    ))


def disable_rls_for_table(connection, table_name: str) -> None:
    """Remove RLS from a table (for migration downgrade).

    Args:
        connection: SQLAlchemy connection (from op.get_bind())
        table_name: Name of the table to unprotect
    """
    connection.execute(text(
        f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"
    ))
    connection.execute(text(
        f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"
    ))
    connection.execute(text(
        f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"
    ))

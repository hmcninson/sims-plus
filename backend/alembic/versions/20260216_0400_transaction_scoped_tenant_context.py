"""Update set_tenant_context/clear_tenant_context to transaction-scoped.

Changes the set_config() calls inside set_tenant_context() and
clear_tenant_context() from session-scoped (false) to transaction-scoped
(true). This ensures that:

1. Tenant context is automatically reverted when a transaction ends
   (commit or rollback), providing defense-in-depth against context leaking
   between requests.
2. Even if the application fails to call clear_tenant_context() explicitly,
   the context is cleared at transaction boundary.

The pool checkout listener (session.py) continues to use session-scoped
(false) because it operates at the raw DBAPI level outside of any
SQLAlchemy-managed transaction.

Revision ID: transaction_scoped_tenant_ctx
Revises: rls_policy_rework
Create Date: 2026-02-16 04:00:00.000000
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "transaction_scoped_tenant_ctx"
down_revision = "rls_policy_rework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update tenant context functions to use transaction-scoped set_config."""
    connection = op.get_bind()

    # Update set_tenant_context() to use true (transaction-scoped)
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, true);
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Update clear_tenant_context() to use true (transaction-scoped)
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION clear_tenant_context()
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Smoke test: verify functions exist and are callable
    connection.execute(text("SELECT clear_tenant_context()"))


def downgrade() -> None:
    """Revert to session-scoped set_config."""
    connection = op.get_bind()

    connection.execute(text("""
        CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, false);
        END;
        $$ LANGUAGE plpgsql;
    """))

    connection.execute(text("""
        CREATE OR REPLACE FUNCTION clear_tenant_context()
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', '', false);
        END;
        $$ LANGUAGE plpgsql;
    """))

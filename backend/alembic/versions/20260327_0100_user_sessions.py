"""user_sessions table for active session management

Revision ID: user_sessions
Revises: comprehensive_rls
Create Date: 2026-03-27 01:00:00.000000+00:00

Creates the user_sessions table to track active login sessions.
Each session is linked to a refresh token via its JTI (JWT ID),
enabling users to view and terminate sessions from other devices.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "user_sessions"
down_revision: Union[str, None] = "20260322_0400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_sessions table with RLS."""
    connection = op.get_bind()

    # Create the table
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(255), nullable=False),
        sa.Column("device_info", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Indexes
    op.create_index("ix_user_sessions_tenant_id", "user_sessions", ["tenant_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_jti", "user_sessions", ["jti"], unique=True)
    op.create_index("ix_user_sessions_user_active", "user_sessions", ["user_id", "is_active"])

    # Enable and force RLS
    connection.execute(text("ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY"))
    connection.execute(text("ALTER TABLE user_sessions FORCE ROW LEVEL SECURITY"))

    # Hardened tenant isolation policy — no NULL bypass, no platform_admin bypass
    connection.execute(text("""
        CREATE POLICY tenant_isolation_user_sessions ON user_sessions
        FOR ALL
        TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """))

    # Grant permissions to the application user
    connection.execute(text(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON user_sessions TO sims_app_user"
    ))


def downgrade() -> None:
    """Drop user_sessions table."""
    connection = op.get_bind()

    connection.execute(text("DROP POLICY IF EXISTS tenant_isolation_user_sessions ON user_sessions"))
    connection.execute(text("ALTER TABLE user_sessions NO FORCE ROW LEVEL SECURITY"))
    connection.execute(text("ALTER TABLE user_sessions DISABLE ROW LEVEL SECURITY"))

    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_index("ix_user_sessions_jti", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_tenant_id", table_name="user_sessions")
    op.drop_table("user_sessions")

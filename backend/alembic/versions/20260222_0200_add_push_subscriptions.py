"""Add push_subscriptions table for Web Push notifications

Stores browser push subscription details (endpoint, ECDH keys) per user
so the server can send notifications via the Web Push protocol.

RLS enabled with hardened tenant isolation policy.

Revision ID: 20260222_0200
Revises: 20260222_0100
Create Date: 2026-02-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260222_0200"
down_revision: Union[str, None] = "20260222_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("p256dh_key", sa.String(255), nullable=False),
        sa.Column("auth_key", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Composite index for the most common query: "get all active subs for a user in a tenant"
    op.create_index(
        "idx_push_subscriptions_tenant_user",
        "push_subscriptions",
        ["tenant_id", "user_id"],
    )
    # Index on endpoint for upsert lookups and unsubscribe
    op.create_index(
        "idx_push_subscriptions_endpoint",
        "push_subscriptions",
        ["endpoint"],
    )
    # Tenant index for RLS performance
    op.create_index(
        "idx_push_subscriptions_tenant_id",
        "push_subscriptions",
        ["tenant_id"],
    )

    # Enable RLS and FORCE it so even the table owner is subject to policies
    op.execute("ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE push_subscriptions FORCE ROW LEVEL SECURITY")

    # Hardened tenant isolation policy -- no NULL bypass
    op.execute("""
        CREATE POLICY tenant_isolation_push_subscriptions ON push_subscriptions
            FOR ALL
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)

    # Grant least-privilege permissions to the application database user
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON push_subscriptions TO sims_app_user")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_push_subscriptions ON push_subscriptions")
    op.drop_index("idx_push_subscriptions_tenant_id", table_name="push_subscriptions")
    op.drop_index("idx_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index("idx_push_subscriptions_tenant_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

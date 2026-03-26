"""Platform admin infrastructure: platform tenant seed + audit log table.

Revision ID: 20260326_0100
Revises: 20260325_0100
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260326_0100"
down_revision = "20260325_0100"
branch_labels = None
depends_on = None

# Well-known UUID for the platform tenant (used in CLI, tests, and deps.py)
PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ============================================================
    # 1. Seed platform tenant
    # ============================================================
    # The _platform subdomain is deliberately invalid per SUBDOMAIN_PATTERN
    # (starts with underscore), so it cannot be registered or routed to
    # via normal subdomain extraction.
    op.execute(f"""
        INSERT INTO tenants (
            id, name, subdomain, slug, tenant_type, subscription_tier,
            status, is_active, max_students, max_staff,
            created_at, updated_at
        ) VALUES (
            '{PLATFORM_TENANT_ID}',
            'SIMS Plus Platform',
            '_platform',
            '_platform',
            'single_school',
            'enterprise',
            'active',
            true,
            0,
            999999,
            NOW(), NOW()
        ) ON CONFLICT (subdomain) DO NOTHING
    """)

    # ============================================================
    # 2. Create platform_audit_log table
    # ============================================================
    # This table has NO tenant_id and NO RLS.
    # Access is controlled at the application layer via platform admin auth.
    op.create_table(
        "platform_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_entity_type", sa.String(50), nullable=True),
        sa.Column("target_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        # updated_at inherited from Base — included for ORM compatibility
        # but never updated (audit log entries are immutable)
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # Indexes for platform_audit_log
    op.create_index("idx_platform_audit_actor",
                    "platform_audit_log", ["actor_user_id"])
    op.create_index("idx_platform_audit_target_tenant",
                    "platform_audit_log", ["target_tenant_id"])
    op.create_index("idx_platform_audit_created",
                    "platform_audit_log", ["created_at"])

    # NO RLS on platform_audit_log — this is intentional.
    # The table has no tenant_id. Access is controlled at the API layer.
    # SECURITY: sims_app_user gets INSERT only (for writing audit entries).
    # SELECT is NOT granted to sims_app_user — reading the audit log goes
    # through the superuser engine (PlatformService.get_audit_log uses
    # get_platform_admin_session_maker). This prevents a SQL injection in
    # any school-scoped endpoint from reading platform admin activities.
    op.execute("GRANT INSERT ON platform_audit_log TO sims_app_user")


def downgrade() -> None:
    op.drop_index("idx_platform_audit_created", table_name="platform_audit_log")
    op.drop_index("idx_platform_audit_target_tenant", table_name="platform_audit_log")
    op.drop_index("idx_platform_audit_actor", table_name="platform_audit_log")
    op.drop_table("platform_audit_log")
    op.execute(f"DELETE FROM tenants WHERE id = '{PLATFORM_TENANT_ID}'")

"""Add notifications and SMS log tables

Revision ID: 20260220_0100
Revises: 5e70fd6d9695
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM


revision: str = "20260220_0100"
down_revision: Union[str, None] = "5e70fd6d9695"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types via raw SQL to avoid SQLAlchemy's auto-create conflicts
    op.execute("CREATE TYPE notificationtype AS ENUM ('info', 'success', 'warning', 'error', 'system')")
    op.execute("CREATE TYPE notificationcategory AS ENUM ('academic', 'finance', 'attendance', 'exam', 'general', 'admin')")
    op.execute("CREATE TYPE smsprovider AS ENUM ('hubtel', 'arkesel', 'twilio')")
    op.execute("CREATE TYPE smsstatus AS ENUM ('pending', 'sent', 'delivered', 'failed')")

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("type", ENUM("info", "success", "warning", "error", "system", name="notificationtype", create_type=False), nullable=False, server_default="info"),
        sa.Column("category", ENUM("academic", "finance", "attendance", "exam", "general", "admin", name="notificationcategory", create_type=False), nullable=False, server_default="general"),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create sms_log table
    op.create_table(
        "sms_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_phone", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("provider", ENUM("hubtel", "arkesel", "twilio", name="smsprovider", create_type=False), nullable=False, server_default="hubtel"),
        sa.Column("status", ENUM("pending", "sent", "delivered", "failed", name="smsstatus", create_type=False), nullable=False, server_default="pending"),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index("idx_notifications_tenant_user_read", "notifications", ["tenant_id", "user_id", "is_read"])
    op.create_index("idx_notifications_tenant_created", "notifications", ["tenant_id", sa.text("created_at DESC")])
    op.create_index("idx_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_index("idx_sms_log_tenant_created", "sms_log", ["tenant_id", sa.text("created_at DESC")])
    op.create_index("idx_sms_log_tenant_id", "sms_log", ["tenant_id"])

    # Enable RLS and FORCE it so even the table owner is subject to policies
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sms_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sms_log FORCE ROW LEVEL SECURITY")

    # Create RLS policies (hardened -- no NULL bypass)
    op.execute("""
        CREATE POLICY tenant_isolation_notifications ON notifications
            FOR ALL
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute("""
        CREATE POLICY tenant_isolation_sms_log ON sms_log
            FOR ALL
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_notifications ON notifications")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_sms_log ON sms_log")

    # Disable RLS (NO FORCE + DISABLE)
    op.execute("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sms_log NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sms_log DISABLE ROW LEVEL SECURITY")

    # Drop tables
    op.drop_table("sms_log")
    op.drop_table("notifications")

    # Drop enum types
    sa.Enum(name="smsstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="smsprovider").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationcategory").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationtype").drop(op.get_bind(), checkfirst=True)

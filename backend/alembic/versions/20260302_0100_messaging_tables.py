"""Add email_log table, RLS policy, and communication_settings column on schools

Sprint 19: Messaging System

1. Create emailstatus enum type
2. Create email_log table with tenant_id FK
3. Enable RLS + FORCE RLS on email_log
4. Create tenant_isolation policy using get_current_tenant_id()
5. Grant permissions to sims_app_user
6. Add communication_settings JSONB column to schools table
7. Create indexes on email_log (tenant_id, status, created_at)

Revision ID: 20260302_0100
Revises: 20260301_0100
Create Date: 2026-03-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "20260302_0100"
down_revision: Union[str, None] = "20260301_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. Create email_log table (emailstatus enum auto-created by create_table)
    # ---------------------------------------------------------------
    emailstatus_enum = sa.Enum(
        "pending", "sent", "delivered", "failed", "bounced",
        name="emailstatus",
    )

    op.create_table(
        "email_log",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("recipient_email", sa.String(255), nullable=False, index=True),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", emailstatus_enum, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # ---------------------------------------------------------------
    # 3. RLS: Enable, force, and create tenant isolation policy
    # ---------------------------------------------------------------
    op.execute("ALTER TABLE email_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE email_log FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON email_log
        FOR ALL
        TO sims_app_user
        USING (tenant_id = get_current_tenant_id())
        WITH CHECK (tenant_id = get_current_tenant_id())
    """)

    # ---------------------------------------------------------------
    # 4. Grant permissions to the application role
    # ---------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON email_log TO sims_app_user")

    # ---------------------------------------------------------------
    # 5. Composite indexes for common query patterns
    # ---------------------------------------------------------------
    op.create_index(
        "ix_email_log_tenant_status",
        "email_log",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_email_log_tenant_created_at",
        "email_log",
        ["tenant_id", "created_at"],
    )

    # ---------------------------------------------------------------
    # 6. Add communication_settings JSONB column to schools
    # ---------------------------------------------------------------
    op.add_column(
        "schools",
        sa.Column(
            "communication_settings",
            JSONB(),
            nullable=True,
            comment="Communication settings (SMS, email, notification preferences)",
        ),
    )


def downgrade() -> None:
    # Drop communication_settings column from schools
    op.drop_column("schools", "communication_settings")

    # Drop indexes
    op.drop_index("ix_email_log_tenant_created_at", table_name="email_log")
    op.drop_index("ix_email_log_tenant_status", table_name="email_log")

    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON email_log")

    # Revoke permissions
    op.execute("REVOKE ALL ON email_log FROM sims_app_user")

    # Drop table
    op.drop_table("email_log")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS emailstatus")

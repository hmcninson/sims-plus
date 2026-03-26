"""Enrollment Gap Closure Phase 3: Enrollment Checklists + CSSPS Support

New tables:
  - enrollment_checklists: per-application enrollment checklist
  - enrollment_checklist_items: individual tasks within a checklist

Column additions to existing tables:
  - applications: enrollment_deposit_paid, enrollment_deposit_amount,
    enrollment_deposit_reference, enrollment_deposit_paid_at,
    boarding_status, enrollment_confirmation_url,
    welcome_pack_sent, welcome_pack_sent_at
  - admission_periods: enrollment_deposit_required,
    enrollment_deposit_amount, enrollment_checklist_template

RLS policies on both new tables.

Revision ID: 20260415_0100
Revises: 20260408_0100
Create Date: 2026-04-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "20260415_0100"
down_revision: Union[str, None] = "20260408_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# New tenant-scoped tables that need RLS
NEW_TABLES = [
    "enrollment_checklists",
    "enrollment_checklist_items",
]


def upgrade() -> None:
    # =================================================================
    # PHASE 1: Create new tables
    # =================================================================

    # --- Table 1: enrollment_checklists ---
    op.create_table(
        "enrollment_checklists",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checklist_type", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 2: enrollment_checklist_items ---
    op.create_table(
        "enrollment_checklist_items",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("checklist_id", UUID(as_uuid=True), sa.ForeignKey("enrollment_checklists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("item_metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # =================================================================
    # PHASE 2: Enable RLS on new tables
    # =================================================================
    for table_name in NEW_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """)

    # =================================================================
    # PHASE 3: Grant permissions to application role
    # =================================================================
    for table_name in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")

    # =================================================================
    # PHASE 4: Create indexes on new tables
    # =================================================================

    # enrollment_checklists: unique partial index -- one active checklist per application
    op.execute("""
        CREATE UNIQUE INDEX uq_enrollment_checklist_app
        ON enrollment_checklists(tenant_id, application_id)
        WHERE deleted_at IS NULL
    """)
    # enrollment_checklists: school lookup
    op.execute("""
        CREATE INDEX ix_enrollment_checklists_school
        ON enrollment_checklists(tenant_id, school_id)
        WHERE deleted_at IS NULL
    """)
    # enrollment_checklists: incomplete checklists for dashboard queries
    op.execute("""
        CREATE INDEX ix_enrollment_checklists_incomplete
        ON enrollment_checklists(tenant_id, school_id)
        WHERE completed_at IS NULL AND deleted_at IS NULL
    """)

    # enrollment_checklist_items: lookup by checklist
    op.execute("""
        CREATE INDEX ix_checklist_items_checklist
        ON enrollment_checklist_items(tenant_id, checklist_id)
        WHERE deleted_at IS NULL
    """)
    # enrollment_checklist_items: incomplete required items for progress queries
    op.execute("""
        CREATE INDEX ix_checklist_items_incomplete
        ON enrollment_checklist_items(tenant_id, checklist_id, is_required)
        WHERE is_completed = false AND deleted_at IS NULL
    """)

    # =================================================================
    # PHASE 5: Add columns to existing tables
    # =================================================================

    # --- applications: enrollment confirmation fields ---
    op.add_column("applications", sa.Column(
        "enrollment_deposit_paid", sa.Boolean(), nullable=False, server_default="false",
    ))
    op.add_column("applications", sa.Column(
        "enrollment_deposit_amount", sa.Numeric(10, 2), nullable=True,
    ))
    op.add_column("applications", sa.Column(
        "enrollment_deposit_reference", sa.String(255), nullable=True,
    ))
    op.add_column("applications", sa.Column(
        "enrollment_deposit_paid_at", sa.DateTime(timezone=True), nullable=True,
    ))
    op.add_column("applications", sa.Column(
        "boarding_status", sa.String(20), nullable=True,
    ))
    op.add_column("applications", sa.Column(
        "enrollment_confirmation_url", sa.String(500), nullable=True,
    ))
    op.add_column("applications", sa.Column(
        "welcome_pack_sent", sa.Boolean(), nullable=False, server_default="false",
    ))
    op.add_column("applications", sa.Column(
        "welcome_pack_sent_at", sa.DateTime(timezone=True), nullable=True,
    ))

    # --- admission_periods: enrollment deposit configuration ---
    op.add_column("admission_periods", sa.Column(
        "enrollment_deposit_required", sa.Boolean(), nullable=False, server_default="false",
    ))
    op.add_column("admission_periods", sa.Column(
        "enrollment_deposit_amount", sa.Numeric(10, 2), nullable=True,
    ))
    op.add_column("admission_periods", sa.Column(
        "enrollment_checklist_template", JSONB, nullable=False, server_default="[]",
    ))


def downgrade() -> None:
    # --- Drop columns from admission_periods ---
    op.drop_column("admission_periods", "enrollment_checklist_template")
    op.drop_column("admission_periods", "enrollment_deposit_amount")
    op.drop_column("admission_periods", "enrollment_deposit_required")

    # --- Drop columns from applications ---
    op.drop_column("applications", "welcome_pack_sent_at")
    op.drop_column("applications", "welcome_pack_sent")
    op.drop_column("applications", "enrollment_confirmation_url")
    op.drop_column("applications", "boarding_status")
    op.drop_column("applications", "enrollment_deposit_paid_at")
    op.drop_column("applications", "enrollment_deposit_reference")
    op.drop_column("applications", "enrollment_deposit_amount")
    op.drop_column("applications", "enrollment_deposit_paid")

    # --- Drop indexes (partial indexes need explicit DROP) ---
    op.execute("DROP INDEX IF EXISTS ix_checklist_items_incomplete")
    op.execute("DROP INDEX IF EXISTS ix_checklist_items_checklist")
    op.execute("DROP INDEX IF EXISTS ix_enrollment_checklists_incomplete")
    op.execute("DROP INDEX IF EXISTS ix_enrollment_checklists_school")
    op.execute("DROP INDEX IF EXISTS uq_enrollment_checklist_app")

    # --- Drop RLS policies and grants ---
    for table_name in reversed(NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
        op.execute(f"REVOKE ALL ON {table_name} FROM sims_app_user")

    # --- Drop tables (child first) ---
    op.drop_table("enrollment_checklist_items")
    op.drop_table("enrollment_checklists")

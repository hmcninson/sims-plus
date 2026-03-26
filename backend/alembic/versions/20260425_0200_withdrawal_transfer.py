"""Student Management Gap Closure Phase 2: Withdrawal & Transfer Clearances

New table:
  - withdrawal_clearances: Clearance checklist for student withdrawal or external
    transfer. Tracks library, finance, property, and boarding clearance status.

Restricted grants:
  - withdrawal_clearances: SELECT, INSERT, UPDATE (no DELETE — audit trail)

Revision ID: 20260425_0200
Revises: 20260425_0100
Create Date: 2026-04-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260425_0200"
down_revision: Union[str, None] = "20260425_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # withdrawal_clearances
    # ------------------------------------------------------------------
    op.create_table(
        "withdrawal_clearances",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status_change_id", UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("library_cleared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("finance_cleared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("property_cleared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("boarding_cleared", sa.Boolean(), nullable=True),
        sa.Column("outstanding_fees", sa.Numeric(12, 2), nullable=True),
        sa.Column("fee_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_complete", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("cleared_by", UUID(as_uuid=True), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["status_change_id"], ["student_status_changes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cleared_by"], ["users.id"], ondelete="SET NULL"),
        # CHECK constraint (F-21): type must be 'withdrawal' or 'transfer'
        sa.CheckConstraint("type IN ('withdrawal', 'transfer')", name="ck_wc_type"),
    )

    # Indexes
    op.create_index("ix_wc_tenant", "withdrawal_clearances", ["tenant_id"])
    op.create_index("ix_wc_student", "withdrawal_clearances", ["student_id"])
    op.create_index("ix_wc_status_change", "withdrawal_clearances", ["status_change_id"])
    # Only one active (incomplete) clearance per student per tenant
    op.execute(
        "CREATE UNIQUE INDEX uq_wc_student_active "
        "ON withdrawal_clearances(student_id, tenant_id) "
        "WHERE is_complete = false"
    )

    # ------------------------------------------------------------------
    # RLS
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE withdrawal_clearances ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE withdrawal_clearances FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_withdrawal_clearances "
        "ON withdrawal_clearances FOR ALL TO sims_app_user "
        "USING (tenant_id = get_current_tenant_id()) "
        "WITH CHECK (tenant_id = get_current_tenant_id())"
    )

    # Restricted grants: no DELETE — clearance records are part of audit trail
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON withdrawal_clearances TO sims_app_user"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_withdrawal_clearances "
        "ON withdrawal_clearances"
    )
    op.drop_table("withdrawal_clearances")

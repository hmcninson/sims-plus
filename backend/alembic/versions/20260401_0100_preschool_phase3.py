"""Preschool Phase 3: Supplies Tracking

Creates:
- preschool_supplies table with RLS
- Indexes for tenant_id, school_id, and (tenant_id, student_id)
- CHECK constraints for non-negative quantity and threshold

Revision ID: 20260401_0100
Revises: 20260330_0100
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260401_0100"
down_revision = "20260330_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. Create preschool_supplies table
    # ---------------------------------------------------------------
    op.create_table(
        "preschool_supplies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("quantity_remaining", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("last_restocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # 2. Create indexes
    # ---------------------------------------------------------------
    op.create_index("ix_preschool_supplies_tenant", "preschool_supplies", ["tenant_id"])
    op.create_index("ix_preschool_supplies_school", "preschool_supplies", ["school_id"])
    op.create_index("ix_preschool_supplies_student", "preschool_supplies", ["tenant_id", "student_id"])

    # ---------------------------------------------------------------
    # 3. CHECK constraints
    # ---------------------------------------------------------------
    op.execute("""
        ALTER TABLE preschool_supplies
        ADD CONSTRAINT ck_quantity_non_negative CHECK (quantity_remaining >= 0),
        ADD CONSTRAINT ck_threshold_non_negative CHECK (low_stock_threshold >= 0)
    """)

    # ---------------------------------------------------------------
    # 4. RLS policies (using project-standard rls_helpers)
    # ---------------------------------------------------------------
    from app.db.rls_helpers import enable_rls_for_table
    enable_rls_for_table(op.get_bind(), "preschool_supplies")


def downgrade() -> None:
    from app.db.rls_helpers import disable_rls_for_table
    disable_rls_for_table(op.get_bind(), "preschool_supplies")

    op.drop_index("ix_preschool_supplies_student", "preschool_supplies")
    op.drop_index("ix_preschool_supplies_school", "preschool_supplies")
    op.drop_index("ix_preschool_supplies_tenant", "preschool_supplies")
    op.drop_table("preschool_supplies")

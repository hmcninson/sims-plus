"""Student Management Gap Closure Phase 4: Promotion Rules & Graduation

New table:
  - promotion_rules: Configurable promotion criteria per school/year/class.
    Uses SoftDeleteMixin (deleted_at). Standard grants (SELECT, INSERT, UPDATE, DELETE).

    NULL class_id means school-wide default rule; non-NULL targets a specific class.
    COALESCE unique index handles NULL class_id with a sentinel UUID.

Revision ID: 20260425_0400
Revises: 20260425_0300
Create Date: 2026-04-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260425_0400"
down_revision: Union[str, None] = "20260425_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Table: promotion_rules (SoftDeleteMixin — has deleted_at)
    # ------------------------------------------------------------------
    op.create_table(
        "promotion_rules",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), nullable=True),
        sa.Column("min_average", sa.Numeric(5, 2), nullable=True),
        sa.Column("min_attendance_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("core_subject_pass_count", sa.Integer(), nullable=True),
        sa.Column("pass_mark", sa.Numeric(5, 2), nullable=True, server_default=sa.text("50.00")),
        sa.Column("auto_apply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
    )

    # Indexes
    op.execute(
        "CREATE INDEX ix_pr_school_year "
        "ON promotion_rules(school_id, academic_year_id) "
        "WHERE deleted_at IS NULL AND is_active = true"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_promo_rule "
        "ON promotion_rules("
        "school_id, academic_year_id, "
        "COALESCE(class_id, '00000000-0000-0000-0000-000000000000'::uuid), "
        "tenant_id"
        ") WHERE deleted_at IS NULL"
    )

    # Tenant index (RLS performance)
    op.create_index("ix_promotion_rules_tenant", "promotion_rules", ["tenant_id"])

    # RLS
    op.execute("ALTER TABLE promotion_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE promotion_rules FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_promotion_rules "
        "ON promotion_rules FOR ALL TO sims_app_user "
        "USING (tenant_id = get_current_tenant_id()) "
        "WITH CHECK (tenant_id = get_current_tenant_id())"
    )

    # Standard grants
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON promotion_rules TO sims_app_user"
    )


def downgrade() -> None:
    # Drop RLS policy
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_promotion_rules "
        "ON promotion_rules"
    )

    # Drop indexes (partial indexes created via raw SQL must be dropped via raw SQL)
    op.execute("DROP INDEX IF EXISTS uq_promo_rule")
    op.execute("DROP INDEX IF EXISTS ix_pr_school_year")
    op.drop_index("ix_promotion_rules_tenant", table_name="promotion_rules")

    # Drop table
    op.drop_table("promotion_rules")

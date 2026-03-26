"""Staff HR Gap Closure Phase 1: Employment History

New table:
  - staff_employment_history: Tracks promotions, transfers, department changes,
    title changes, status changes, salary changes, etc.
    NO SoftDeleteMixin (history is permanent). Standard grants.

New enum:
  - employmenteventtype: hired, promoted, demoted, transferred, title_changed,
    department_changed, status_changed, salary_changed, contract_renewed

Revision ID: 20260426_0300
Revises: 20260426_0200
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260426_0300"
down_revision: Union[str, None] = "20260426_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum: employmenteventtype
    # ------------------------------------------------------------------
    employmenteventtype = sa.Enum(
        "hired",
        "promoted",
        "demoted",
        "transferred",
        "title_changed",
        "department_changed",
        "status_changed",
        "salary_changed",
        "contract_renewed",
        name="employmenteventtype",
    )
    employmenteventtype.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # Table: staff_employment_history (NO SoftDeleteMixin — permanent record)
    # ------------------------------------------------------------------
    op.create_table(
        "staff_employment_history",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "hired", "promoted", "demoted", "transferred", "title_changed",
                "department_changed", "status_changed", "salary_changed", "contract_renewed",
                name="employmenteventtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("previous_value", sa.String(255), nullable=True),
        sa.Column("new_value", sa.String(255), nullable=True),
        sa.Column("previous_department_id", UUID(as_uuid=True), nullable=True),
        sa.Column("new_department_id", UUID(as_uuid=True), nullable=True),
        sa.Column("previous_job_title", sa.String(100), nullable=True),
        sa.Column("new_job_title", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["new_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------
    op.create_index(
        "ix_staff_emp_history_tenant_staff",
        "staff_employment_history",
        ["tenant_id", "staff_id"],
    )
    op.execute(
        "CREATE INDEX ix_staff_emp_history_date "
        "ON staff_employment_history(tenant_id, effective_date DESC)"
    )

    # ------------------------------------------------------------------
    # RLS
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE staff_employment_history ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE staff_employment_history FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_staff_employment_history "
        "ON staff_employment_history FOR ALL TO sims_app_user "
        "USING (tenant_id = get_current_tenant_id()) "
        "WITH CHECK (tenant_id = get_current_tenant_id())"
    )

    # Standard grants
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON staff_employment_history TO sims_app_user"
    )


def downgrade() -> None:
    # Drop RLS policy
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_staff_employment_history "
        "ON staff_employment_history"
    )

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_staff_emp_history_date")
    op.drop_index("ix_staff_emp_history_tenant_staff", table_name="staff_employment_history")

    # Drop table
    op.drop_table("staff_employment_history")

    # Drop enum
    sa.Enum(name="employmenteventtype").drop(op.get_bind(), checkfirst=True)

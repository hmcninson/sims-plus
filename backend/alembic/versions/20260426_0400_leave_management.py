"""Staff HR Gap Closure Phase 3: Leave Management

New tables:
  - leave_types: Leave category definitions (Annual, Sick, Maternity, etc.)
    SoftDeleteMixin. Partial unique index on (tenant_id, code) WHERE deleted_at IS NULL.
  - leave_balances: Per-staff, per-type, per-academic-year entitlement tracking.
    No SoftDeleteMixin (recalculated, not soft-deleted).
  - leave_requests: Staff leave request workflow (pending/approved/rejected/cancelled).
    No SoftDeleteMixin (permanent audit records).

New enum:
  - leaverequeststatus: pending, approved, rejected, cancelled

Seed data:
  - 7 default leave types inserted for all active/trial tenants.

Revision ID: 20260426_0400
Revises: 20260426_0300
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260426_0400"
down_revision: Union[str, None] = "20260426_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum: leaverequeststatus
    # ------------------------------------------------------------------
    leaverequeststatus = sa.Enum(
        "pending", "approved", "rejected", "cancelled",
        name="leaverequeststatus",
    )
    leaverequeststatus.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # Table: leave_types (SoftDeleteMixin)
    # ------------------------------------------------------------------
    op.create_table(
        "leave_types",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_days_per_year", sa.Numeric(5, 1), nullable=False),
        sa.Column("max_carryover_days", sa.Numeric(5, 1), server_default="0", nullable=False),
        sa.Column("is_paid", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("requires_approval", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # PK & FKs
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
    )

    # Tenant index (standard)
    op.create_index("ix_leave_types_tenant", "leave_types", ["tenant_id"])

    # Partial unique index: soft-delete aware code uniqueness
    op.execute(
        "CREATE UNIQUE INDEX uq_leave_type_code_tenant "
        "ON leave_types(tenant_id, code) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # Table: leave_balances (NO SoftDeleteMixin)
    # ------------------------------------------------------------------
    op.create_table(
        "leave_balances",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entitled_days", sa.Numeric(5, 1), nullable=False),
        sa.Column("used_days", sa.Numeric(5, 1), server_default="0", nullable=False),
        sa.Column("pending_days", sa.Numeric(5, 1), server_default="0", nullable=False),
        sa.Column("carried_over", sa.Numeric(5, 1), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # PK & FKs
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        # Unique constraint
        sa.UniqueConstraint(
            "tenant_id", "staff_id", "leave_type_id", "academic_year_id",
            name="uq_leave_balance_staff_type_year",
        ),
    )

    # Tenant index
    op.create_index("ix_leave_balances_tenant", "leave_balances", ["tenant_id"])

    # Composite index for FOR UPDATE queries (balance lookups by staff + type + year)
    op.create_index(
        "ix_leave_balances_staff_type_year",
        "leave_balances",
        ["tenant_id", "staff_id", "leave_type_id", "academic_year_id"],
    )

    # ------------------------------------------------------------------
    # Table: leave_requests (NO SoftDeleteMixin — permanent audit records)
    # ------------------------------------------------------------------
    op.create_table(
        "leave_requests",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days_requested", sa.Numeric(5, 1), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "approved", "rejected", "cancelled",
                name="leaverequeststatus",
                create_type=False,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("attachment_key", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # PK & FKs
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
    )

    # Indexes
    op.create_index("ix_leave_requests_tenant", "leave_requests", ["tenant_id"])
    op.create_index("ix_leave_requests_staff", "leave_requests", ["tenant_id", "staff_id"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["tenant_id", "status"])
    op.create_index("ix_leave_requests_dates", "leave_requests", ["tenant_id", "start_date", "end_date"])

    # ------------------------------------------------------------------
    # RLS for all 3 tables
    # ------------------------------------------------------------------
    conn = op.get_bind()

    for table_name in ("leave_types", "leave_balances", "leave_requests"):
        conn.execute(sa.text(
            f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
        ))
        conn.execute(sa.text(
            f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"
        ))
        conn.execute(sa.text(
            f"CREATE POLICY tenant_isolation_{table_name} ON {table_name} "
            f"FOR ALL TO sims_app_user "
            f"USING (tenant_id = get_current_tenant_id()) "
            f"WITH CHECK (tenant_id = get_current_tenant_id())"
        ))
        conn.execute(sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
        ))

    # ------------------------------------------------------------------
    # Seed default leave types for existing tenants
    # ------------------------------------------------------------------
    conn.execute(sa.text("""
        INSERT INTO leave_types (id, tenant_id, name, code, description, default_days_per_year, max_carryover_days, is_paid, requires_approval, is_active, color)
        SELECT
            gen_random_uuid(),
            t.id,
            lt.name,
            lt.code,
            lt.description,
            lt.default_days,
            lt.max_carryover,
            lt.is_paid,
            lt.requires_approval,
            true,
            lt.color
        FROM tenants t
        CROSS JOIN (
            VALUES
                ('Annual Leave',      'ANNUAL',        'Standard annual leave entitlement',                20.0, 5.0,  true,  true,  '#4CAF50'),
                ('Sick Leave',        'SICK',          'Leave for medical reasons',                        15.0, 0.0,  true,  true,  '#F44336'),
                ('Maternity Leave',   'MATERNITY',     'Leave for expectant and new mothers',              90.0, 0.0,  true,  true,  '#E91E63'),
                ('Paternity Leave',   'PATERNITY',     'Leave for new fathers',                             5.0, 0.0,  true,  true,  '#2196F3'),
                ('Casual Leave',      'CASUAL',        'Short-notice personal leave',                       5.0, 0.0,  true,  true,  '#FF9800'),
                ('Study Leave',       'STUDY',         'Leave for academic or professional development',   30.0, 0.0,  false, true,  '#9C27B0'),
                ('Compassionate Leave','COMPASSIONATE','Leave for bereavement or family emergencies',       5.0, 0.0,  true,  true,  '#607D8B')
        ) AS lt(name, code, description, default_days, max_carryover, is_paid, requires_approval, color)
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Drop RLS policies
    # ------------------------------------------------------------------
    for table_name in ("leave_requests", "leave_balances", "leave_types"):
        conn.execute(sa.text(
            f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"
        ))

    # ------------------------------------------------------------------
    # Drop indexes
    # ------------------------------------------------------------------
    op.drop_index("ix_leave_requests_dates", table_name="leave_requests")
    op.drop_index("ix_leave_requests_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_staff", table_name="leave_requests")
    op.drop_index("ix_leave_requests_tenant", table_name="leave_requests")

    op.drop_index("ix_leave_balances_staff_type_year", table_name="leave_balances")
    op.drop_index("ix_leave_balances_tenant", table_name="leave_balances")

    op.execute("DROP INDEX IF EXISTS uq_leave_type_code_tenant")
    op.drop_index("ix_leave_types_tenant", table_name="leave_types")

    # ------------------------------------------------------------------
    # Drop tables (order matters: requests -> balances -> types)
    # ------------------------------------------------------------------
    op.drop_table("leave_requests")
    op.drop_table("leave_balances")
    op.drop_table("leave_types")

    # ------------------------------------------------------------------
    # Drop enum
    # ------------------------------------------------------------------
    sa.Enum(name="leaverequeststatus").drop(op.get_bind(), checkfirst=True)

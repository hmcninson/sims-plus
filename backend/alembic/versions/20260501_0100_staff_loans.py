"""Staff HR Gap Closure Phase 5: Loan Management

5 new tables: loan_types, staff_loans, loan_installments, loan_guarantors,
loan_payments.  2 new PG enums: loanstatus, interestmethod.
1 column addition: payroll_item_deductions.loan_installment_id.

All tables tenant-scoped with RLS + FORCE RLS + standard grants.
loan_installments: NO SoftDeleteMixin (permanent records).
staff_loans: self-referencing FK (restructured_from_id).
loan_types: partial unique index on (tenant_id, code) WHERE deleted_at IS NULL.

Revision ID: 20260501_0100
Revises: 20260430_0200
Create Date: 2026-05-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

from app.db.rls_helpers import enable_rls_for_table, disable_rls_for_table


revision: str = "20260501_0100"
down_revision: Union[str, None] = "20260430_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -- Tables created in this migration (order matters for FK deps) ----------
NEW_TABLES = [
    "loan_types",
    "staff_loans",
    "loan_installments",
    "loan_guarantors",
    "loan_payments",
]


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Create PG enums
    # ------------------------------------------------------------------
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE loanstatus AS ENUM ("
        "'draft', 'pending_approval', 'approved', 'active', "
        "'completed', 'written_off', 'restructured', 'rejected'"
        "); EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE interestmethod AS ENUM ('flat', 'reducing_balance')"
        "; EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # ------------------------------------------------------------------
    # 2. loan_types
    # ------------------------------------------------------------------
    op.create_table(
        "loan_types",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_interest_rate", sa.Numeric(5, 2), server_default="0.00", nullable=False),
        sa.Column(
            "default_interest_method",
            ENUM("flat", "reducing_balance", name="interestmethod", create_type=False),
            server_default="flat",
            nullable=False,
        ),
        sa.Column("max_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_tenure_months", sa.Integer, nullable=True),
        sa.Column("max_active_loans", sa.Integer, server_default="1", nullable=False),
        sa.Column("requires_guarantor", sa.Boolean, server_default="false", nullable=False),
        sa.Column("min_service_months", sa.Integer, server_default="0", nullable=False),
        sa.Column("max_deduction_pct", sa.Numeric(5, 2), server_default="50.00", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    # Partial unique: (tenant_id, code) WHERE deleted_at IS NULL
    op.create_index(
        "uq_loan_types_tenant_code",
        "loan_types",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_loan_types_tenant", "loan_types", ["tenant_id"])

    # ------------------------------------------------------------------
    # 3. staff_loans
    # ------------------------------------------------------------------
    op.create_table(
        "staff_loans",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("loan_number", sa.String(30), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("loan_type_id", UUID(as_uuid=True), sa.ForeignKey("loan_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "status",
            ENUM(
                "draft", "pending_approval", "approved", "active",
                "completed", "written_off", "restructured", "rejected",
                name="loanstatus", create_type=False,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("principal_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(5, 2), server_default="0.00", nullable=False),
        sa.Column(
            "interest_method",
            ENUM("flat", "reducing_balance", name="interestmethod", create_type=False),
            server_default="flat",
            nullable=False,
        ),
        sa.Column("total_interest", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("total_repayable", sa.Numeric(12, 2), nullable=False),
        sa.Column("tenure_months", sa.Integer, nullable=False),
        sa.Column("monthly_installment", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_paid", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("installments_paid", sa.Integer, server_default="0", nullable=False),
        sa.Column("installments_remaining", sa.Integer, nullable=False),
        sa.Column("application_date", sa.Date, server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("approval_date", sa.Date, nullable=True),
        sa.Column("disbursement_date", sa.Date, nullable=True),
        sa.Column("first_deduction_date", sa.Date, nullable=True),
        sa.Column("expected_completion_date", sa.Date, nullable=True),
        sa.Column("actual_completion_date", sa.Date, nullable=True),
        sa.Column("purpose", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("disbursed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Self-referencing FK: restructured loans point to their predecessor
        sa.Column("restructured_from_id", UUID(as_uuid=True), sa.ForeignKey("staff_loans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("write_off_reason", sa.Text, nullable=True),
        sa.Column("write_off_date", sa.Date, nullable=True),
        sa.Column("written_off_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("loan_number", "tenant_id", name="uq_staff_loans_number_tenant"),
    )
    op.create_index("idx_staff_loans_tenant_staff_status", "staff_loans", ["tenant_id", "staff_id", "status"])
    op.create_index("idx_staff_loans_tenant_status", "staff_loans", ["tenant_id", "status"])
    op.create_index("idx_staff_loans_tenant_type", "staff_loans", ["tenant_id", "loan_type_id"])
    op.create_index("idx_staff_loans_tenant", "staff_loans", ["tenant_id"])

    # ------------------------------------------------------------------
    # 4. loan_installments (NO SoftDeleteMixin)
    # ------------------------------------------------------------------
    op.create_table(
        "loan_installments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("loan_id", UUID(as_uuid=True), sa.ForeignKey("staff_loans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installment_number", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("principal_component", sa.Numeric(12, 2), nullable=False),
        sa.Column("interest_component", sa.Numeric(12, 2), nullable=False),
        sa.Column("installment_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("closing_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_paid", sa.Boolean, server_default="false", nullable=False),
        sa.Column("paid_date", sa.Date, nullable=True),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("payroll_run_id", UUID(as_uuid=True), sa.ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payroll_item_deduction_id", UUID(as_uuid=True), sa.ForeignKey("payroll_item_deductions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("loan_id", "installment_number", name="uq_loan_installment_number"),
    )
    op.create_index("idx_loan_installments_tenant_due_paid", "loan_installments", ["tenant_id", "due_date", "is_paid"])
    op.create_index("idx_loan_installments_loan_paid", "loan_installments", ["loan_id", "is_paid"])
    op.create_index("idx_loan_installments_tenant", "loan_installments", ["tenant_id"])

    # ------------------------------------------------------------------
    # 5. loan_guarantors
    # ------------------------------------------------------------------
    op.create_table(
        "loan_guarantors",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("loan_id", UUID(as_uuid=True), sa.ForeignKey("staff_loans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guarantor_staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=True),
        sa.Column("guaranteed_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("consent_given", sa.Boolean, server_default="false", nullable=False),
        sa.Column("consent_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("loan_id", "guarantor_staff_id", name="uq_loan_guarantor_staff"),
    )
    op.create_index("idx_loan_guarantors_tenant", "loan_guarantors", ["tenant_id"])

    # ------------------------------------------------------------------
    # 6. loan_payments
    # ------------------------------------------------------------------
    op.create_table(
        "loan_payments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("loan_id", UUID(as_uuid=True), sa.ForeignKey("staff_loans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_number", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_date", sa.Date, nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("installments_covered", JSONB, nullable=True),
        sa.Column("is_early_repayment", sa.Boolean, server_default="false", nullable=False),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("payment_number", "tenant_id", name="uq_loan_payment_number_tenant"),
    )
    op.create_index("idx_loan_payments_tenant_loan_date", "loan_payments", ["tenant_id", "loan_id", "payment_date"])
    op.create_index("idx_loan_payments_tenant", "loan_payments", ["tenant_id"])

    # ------------------------------------------------------------------
    # 7. Enable RLS on all 5 tables
    # ------------------------------------------------------------------
    for table in NEW_TABLES:
        enable_rls_for_table(conn, table)

    # ------------------------------------------------------------------
    # 8. Add loan_installment_id FK column to payroll_item_deductions
    # ------------------------------------------------------------------
    op.add_column(
        "payroll_item_deductions",
        sa.Column(
            "loan_installment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("loan_installments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_payroll_item_deductions_loan",
        "payroll_item_deductions",
        ["loan_installment_id"],
        postgresql_where=sa.text("loan_installment_id IS NOT NULL"),
    )


def downgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Drop loan_installment_id from payroll_item_deductions
    # ------------------------------------------------------------------
    op.drop_index("ix_payroll_item_deductions_loan", table_name="payroll_item_deductions")
    op.drop_column("payroll_item_deductions", "loan_installment_id")

    # ------------------------------------------------------------------
    # 2. Disable RLS (reverse order)
    # ------------------------------------------------------------------
    for table in reversed(NEW_TABLES):
        disable_rls_for_table(conn, table)

    # ------------------------------------------------------------------
    # 3. Drop tables in reverse FK order
    # ------------------------------------------------------------------
    op.drop_index("idx_loan_payments_tenant", table_name="loan_payments")
    op.drop_index("idx_loan_payments_tenant_loan_date", table_name="loan_payments")
    op.drop_table("loan_payments")

    op.drop_index("idx_loan_guarantors_tenant", table_name="loan_guarantors")
    op.drop_table("loan_guarantors")

    op.drop_index("idx_loan_installments_tenant", table_name="loan_installments")
    op.drop_index("idx_loan_installments_loan_paid", table_name="loan_installments")
    op.drop_index("idx_loan_installments_tenant_due_paid", table_name="loan_installments")
    op.drop_table("loan_installments")

    op.drop_index("idx_staff_loans_tenant", table_name="staff_loans")
    op.drop_index("idx_staff_loans_tenant_type", table_name="staff_loans")
    op.drop_index("idx_staff_loans_tenant_status", table_name="staff_loans")
    op.drop_index("idx_staff_loans_tenant_staff_status", table_name="staff_loans")
    op.drop_table("staff_loans")

    op.drop_index("idx_loan_types_tenant", table_name="loan_types")
    op.drop_index("uq_loan_types_tenant_code", table_name="loan_types")
    op.drop_table("loan_types")

    # ------------------------------------------------------------------
    # 4. Drop enums
    # ------------------------------------------------------------------
    op.execute("DROP TYPE IF EXISTS interestmethod")
    op.execute("DROP TYPE IF EXISTS loanstatus")

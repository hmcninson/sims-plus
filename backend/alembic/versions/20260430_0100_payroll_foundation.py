"""Staff HR Gap Closure Phase 4A: Payroll Foundation

New tables (14):
  - salary_grades, allowance_types, deduction_types, tax_brackets
  - staff_salary_configs, staff_allowances, staff_deductions
  - payroll_runs, payroll_items, payroll_item_earnings, payroll_item_deductions
  - payroll_approvals, bank_file_configs, payroll_audit_log

New enums (6):
  - payrollrunstatus, payrollruntype, calculationmethod
  - payrollpaymentmethod, deductioncategory, payrollapprovalaction

payroll_audit_log: GRANT SELECT, INSERT ONLY (no UPDATE, no DELETE).
  Separate SELECT (USING) and INSERT (WITH CHECK) RLS policies.

Revision ID: 20260430_0100
Revises: 20260426_0400
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

from app.db.rls_helpers import enable_rls_for_table, disable_rls_for_table


revision: str = "20260430_0100"
down_revision: Union[str, None] = "20260426_0400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All standard payroll tables (get normal RLS + full GRANT)
STANDARD_TABLES = [
    "salary_grades",
    "allowance_types",
    "deduction_types",
    "tax_brackets",
    "staff_salary_configs",
    "staff_allowances",
    "staff_deductions",
    "payroll_runs",
    "payroll_items",
    "payroll_item_earnings",
    "payroll_item_deductions",
    "payroll_approvals",
    "bank_file_configs",
]

# payroll_audit_log gets special treatment (INSERT+SELECT only)
AUDIT_TABLE = "payroll_audit_log"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enums
    # ------------------------------------------------------------------
    # Use DO block pattern for asyncpg compatibility (checkfirst=True doesn't work)
    op.execute("DO $$ BEGIN CREATE TYPE payrollrunstatus AS ENUM ('draft', 'processing', 'calculated', 'pending_approval', 'approved', 'paid', 'cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE payrollruntype AS ENUM ('regular', 'supplementary', 'bonus', 'arrears'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE calculationmethod AS ENUM ('fixed', 'percentage_basic', 'percentage_gross'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE payrollpaymentmethod AS ENUM ('bank_transfer', 'cash', 'mobile_money'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE deductioncategory AS ENUM ('statutory', 'voluntary', 'loan', 'union', 'other'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE payrollapprovalaction AS ENUM ('approve', 'reject', 'return_for_review'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # ------------------------------------------------------------------
    # 1. salary_grades
    # ------------------------------------------------------------------
    op.create_table(
        "salary_grades",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=True),
        sa.Column("basic_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_salary_grades_tenant", "salary_grades", ["tenant_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_salary_grade_code "
        "ON salary_grades(tenant_id, code) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 2. allowance_types
    # ------------------------------------------------------------------
    op.create_table(
        "allowance_types",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("calculation_method", ENUM(
            "fixed", "percentage_basic", "percentage_gross",
            name="calculationmethod", create_type=False,
        ), nullable=False),
        sa.Column("default_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_taxable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_allowance_types_tenant", "allowance_types", ["tenant_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_allowance_type_code "
        "ON allowance_types(tenant_id, code) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 3. deduction_types
    # ------------------------------------------------------------------
    op.create_table(
        "deduction_types",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("calculation_method", ENUM(
            "fixed", "percentage_basic", "percentage_gross",
            name="calculationmethod", create_type=False,
        ), nullable=False),
        sa.Column("default_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_statutory", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_employer_portion", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deduction_category", ENUM(
            "statutory", "voluntary", "loan", "union", "other",
            name="deductioncategory", create_type=False,
        ), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_deduction_types_tenant", "deduction_types", ["tenant_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_deduction_type_code "
        "ON deduction_types(tenant_id, code) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 4. tax_brackets
    # ------------------------------------------------------------------
    op.create_table(
        "tax_brackets",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("effective_year", sa.Integer(), nullable=False),
        sa.Column("band_number", sa.Integer(), nullable=False),
        sa.Column("lower_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("upper_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("cumulative_tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "effective_year", "band_number", name="uq_tax_bracket_year_band"),
    )
    op.create_index("ix_tax_brackets_tenant", "tax_brackets", ["tenant_id"])

    # ------------------------------------------------------------------
    # 5. staff_salary_configs
    # ------------------------------------------------------------------
    op.create_table(
        "staff_salary_configs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("salary_grade_id", UUID(as_uuid=True), nullable=True),
        sa.Column("basic_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("payment_method", ENUM(
            "bank_transfer", "cash", "mobile_money",
            name="payrollpaymentmethod", create_type=False,
        ), server_default="bank_transfer", nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bank_branch", sa.String(100), nullable=True),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("mobile_money_number", sa.String(20), nullable=True),
        sa.Column("mobile_money_provider", sa.String(20), nullable=True),
        sa.Column("tin_number", sa.String(20), nullable=True),
        sa.Column("ssnit_number", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["salary_grade_id"], ["salary_grades.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_staff_salary_configs_tenant", "staff_salary_configs", ["tenant_id"])
    # Partial unique: one config per staff per effective_date (soft-delete aware)
    op.execute(
        "CREATE UNIQUE INDEX uq_staff_salary_config_date "
        "ON staff_salary_configs(staff_id, tenant_id, effective_date) "
        "WHERE deleted_at IS NULL"
    )
    # Partial index: find active config for a staff member quickly
    op.execute(
        "CREATE INDEX ix_staff_salary_configs_active "
        "ON staff_salary_configs(staff_id, tenant_id, is_active) "
        "WHERE is_active AND deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 6. staff_allowances
    # ------------------------------------------------------------------
    op.create_table(
        "staff_allowances",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("staff_salary_config_id", UUID(as_uuid=True), nullable=False),
        sa.Column("allowance_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("calculation_method", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_salary_config_id"], ["staff_salary_configs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["allowance_type_id"], ["allowance_types.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("staff_salary_config_id", "allowance_type_id", name="uq_staff_allowance_config_type"),
    )
    op.create_index("ix_staff_allowances_tenant", "staff_allowances", ["tenant_id"])

    # ------------------------------------------------------------------
    # 7. staff_deductions
    # ------------------------------------------------------------------
    op.create_table(
        "staff_deductions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("staff_salary_config_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deduction_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("calculation_method", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_salary_config_id"], ["staff_salary_configs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deduction_type_id"], ["deduction_types.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("staff_salary_config_id", "deduction_type_id", name="uq_staff_deduction_config_type"),
    )
    op.create_index("ix_staff_deductions_tenant", "staff_deductions", ["tenant_id"])

    # ------------------------------------------------------------------
    # 8. payroll_runs
    # ------------------------------------------------------------------
    op.create_table(
        "payroll_runs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("run_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", ENUM(
            "draft", "processing", "calculated", "pending_approval",
            "approved", "paid", "cancelled",
            name="payrollrunstatus", create_type=False,
        ), nullable=False),
        sa.Column("run_type", ENUM(
            "regular", "supplementary", "bonus", "arrears",
            name="payrollruntype", create_type=False,
        ), server_default="regular", nullable=False),
        sa.Column("total_basic", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_allowances", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_gross", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_paye", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_ssnit_ee", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_ssnit_er", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_tier2_er", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_tier3", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_other_deductions", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_net", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_employer_cost", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("staff_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("currency", sa.String(3), server_default="GHS", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("processed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bank_file_url", sa.String(500), nullable=True),
        sa.Column("bank_file_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_payroll_runs_tenant", "payroll_runs", ["tenant_id"])
    # COALESCE unique: handles NULL school_id for single-school tenants
    op.execute(
        "CREATE UNIQUE INDEX uq_payroll_run "
        "ON payroll_runs("
        "tenant_id, COALESCE(school_id, '00000000-0000-0000-0000-000000000000'::uuid), "
        "year, month, run_number"
        ") WHERE deleted_at IS NULL"
    )
    op.create_index(
        "ix_payroll_runs_year_month_status",
        "payroll_runs",
        ["tenant_id", "year", "month", "status"],
    )

    # ------------------------------------------------------------------
    # 9. payroll_items
    # ------------------------------------------------------------------
    op.create_table(
        "payroll_items",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("staff_name", sa.String(300), nullable=False),
        sa.Column("staff_code", sa.String(50), nullable=False),
        sa.Column("department_name", sa.String(100), nullable=True),
        sa.Column("salary_grade_name", sa.String(100), nullable=True),
        sa.Column("basic_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_allowances", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("gross_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("taxable_income", sa.Numeric(12, 2), nullable=False),
        sa.Column("paye_tax", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("ssnit_employee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("ssnit_employer", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("tier2_employer", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("tier3_employee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("total_deductions", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("net_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bank_branch", sa.String(100), nullable=True),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("mobile_money_number", sa.String(20), nullable=True),
        sa.Column("ssnit_number", sa.String(20), nullable=True),
        sa.Column("tin_number", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["payroll_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("payroll_run_id", "staff_id", name="uq_payroll_item_run_staff"),
    )
    op.create_index("ix_payroll_items_tenant", "payroll_items", ["tenant_id"])
    op.create_index("ix_payroll_items_staff", "payroll_items", ["tenant_id", "staff_id"])

    # ------------------------------------------------------------------
    # 10. payroll_item_earnings
    # ------------------------------------------------------------------
    op.create_table(
        "payroll_item_earnings",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("allowance_type_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_taxable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payroll_item_id"], ["payroll_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["allowance_type_id"], ["allowance_types.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_payroll_item_earnings_tenant", "payroll_item_earnings", ["tenant_id"])

    # ------------------------------------------------------------------
    # 11. payroll_item_deductions
    # ------------------------------------------------------------------
    op.create_table(
        "payroll_item_deductions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deduction_type_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_statutory", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_employer_portion", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deduction_category", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payroll_item_id"], ["payroll_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deduction_type_id"], ["deduction_types.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_payroll_item_deductions_tenant", "payroll_item_deductions", ["tenant_id"])

    # ------------------------------------------------------------------
    # 12. payroll_approvals
    # ------------------------------------------------------------------
    op.create_table(
        "payroll_approvals",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("approver_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", ENUM(
            "approve", "reject", "return_for_review",
            name="payrollapprovalaction", create_type=False,
        ), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["payroll_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_payroll_approvals_tenant", "payroll_approvals", ["tenant_id"])

    # ------------------------------------------------------------------
    # 13. bank_file_configs
    # ------------------------------------------------------------------
    op.create_table(
        "bank_file_configs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("file_format", sa.String(20), server_default="csv", nullable=False),
        sa.Column("delimiter", sa.String(5), server_default=",", nullable=True),
        sa.Column("column_mapping", JSONB(), nullable=False),
        sa.Column("header_template", sa.Text(), nullable=True),
        sa.Column("footer_template", sa.Text(), nullable=True),
        sa.Column("include_header_row", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("date_format", sa.String(20), server_default="YYYY-MM-DD", nullable=True),
        sa.Column("amount_format", sa.String(20), server_default="decimal", nullable=True),
        sa.Column("encoding", sa.String(20), server_default="utf-8", nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_bank_file_configs_tenant", "bank_file_configs", ["tenant_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_bank_file_config_name "
        "ON bank_file_configs(tenant_id, bank_name) WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # 14. payroll_audit_log (append-only)
    # ------------------------------------------------------------------
    op.create_table(
        "payroll_audit_log",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("performed_by", UUID(as_uuid=True), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_payroll_audit_log_tenant", "payroll_audit_log", ["tenant_id"])
    op.create_index(
        "ix_payroll_audit_log_entity",
        "payroll_audit_log",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_payroll_audit_log_performed",
        "payroll_audit_log",
        ["tenant_id", "performed_at"],
    )

    # ------------------------------------------------------------------
    # RLS: standard tables (FOR ALL policy + full GRANT)
    # ------------------------------------------------------------------
    conn = op.get_bind()
    for table_name in STANDARD_TABLES:
        enable_rls_for_table(conn, table_name)

    # ------------------------------------------------------------------
    # RLS: payroll_audit_log (separate SELECT + INSERT policies, restricted GRANT)
    # ------------------------------------------------------------------
    conn.execute(sa.text(
        f"ALTER TABLE {AUDIT_TABLE} ENABLE ROW LEVEL SECURITY"
    ))
    conn.execute(sa.text(
        f"ALTER TABLE {AUDIT_TABLE} FORCE ROW LEVEL SECURITY"
    ))
    # SELECT policy (read only)
    conn.execute(sa.text(
        f"CREATE POLICY {AUDIT_TABLE}_tenant_select ON {AUDIT_TABLE} "
        f"FOR SELECT TO sims_app_user "
        f"USING (tenant_id = get_current_tenant_id())"
    ))
    # INSERT policy (write only)
    conn.execute(sa.text(
        f"CREATE POLICY {AUDIT_TABLE}_tenant_insert ON {AUDIT_TABLE} "
        f"FOR INSERT TO sims_app_user "
        f"WITH CHECK (tenant_id = get_current_tenant_id())"
    ))
    # CRITICAL: SELECT + INSERT only — NO UPDATE, NO DELETE.
    # The REVOKE is needed because init-db.sql's ALTER DEFAULT PRIVILEGES
    # grants full DML (SELECT, INSERT, UPDATE, DELETE) on all new tables.
    # We must explicitly revoke UPDATE and DELETE after the default grant.
    conn.execute(sa.text(
        f"GRANT SELECT, INSERT ON {AUDIT_TABLE} TO sims_app_user"
    ))
    conn.execute(sa.text(
        f"REVOKE UPDATE, DELETE ON {AUDIT_TABLE} FROM sims_app_user"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Drop RLS: payroll_audit_log (special policies)
    # ------------------------------------------------------------------
    conn.execute(sa.text(
        f"DROP POLICY IF EXISTS {AUDIT_TABLE}_tenant_select ON {AUDIT_TABLE}"
    ))
    conn.execute(sa.text(
        f"DROP POLICY IF EXISTS {AUDIT_TABLE}_tenant_insert ON {AUDIT_TABLE}"
    ))

    # ------------------------------------------------------------------
    # Drop RLS: standard tables
    # ------------------------------------------------------------------
    for table_name in reversed(STANDARD_TABLES):
        disable_rls_for_table(conn, table_name)

    # ------------------------------------------------------------------
    # Drop indexes (non-standard ones created via op.execute)
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS ix_payroll_audit_log_performed")
    op.execute("DROP INDEX IF EXISTS ix_payroll_audit_log_entity")
    op.execute("DROP INDEX IF EXISTS ix_payroll_audit_log_tenant")

    op.execute("DROP INDEX IF EXISTS uq_bank_file_config_name")
    op.execute("DROP INDEX IF EXISTS ix_bank_file_configs_tenant")

    op.execute("DROP INDEX IF EXISTS ix_payroll_approvals_tenant")

    op.execute("DROP INDEX IF EXISTS ix_payroll_item_deductions_tenant")

    op.execute("DROP INDEX IF EXISTS ix_payroll_item_earnings_tenant")

    op.execute("DROP INDEX IF EXISTS ix_payroll_items_staff")
    op.execute("DROP INDEX IF EXISTS ix_payroll_items_tenant")

    op.execute("DROP INDEX IF EXISTS ix_payroll_runs_year_month_status")
    op.execute("DROP INDEX IF EXISTS uq_payroll_run")
    op.execute("DROP INDEX IF EXISTS ix_payroll_runs_tenant")

    op.execute("DROP INDEX IF EXISTS ix_staff_deductions_tenant")

    op.execute("DROP INDEX IF EXISTS ix_staff_allowances_tenant")

    op.execute("DROP INDEX IF EXISTS ix_staff_salary_configs_active")
    op.execute("DROP INDEX IF EXISTS uq_staff_salary_config_date")
    op.execute("DROP INDEX IF EXISTS ix_staff_salary_configs_tenant")

    op.execute("DROP INDEX IF EXISTS ix_tax_brackets_tenant")

    op.execute("DROP INDEX IF EXISTS uq_deduction_type_code")
    op.execute("DROP INDEX IF EXISTS ix_deduction_types_tenant")

    op.execute("DROP INDEX IF EXISTS uq_allowance_type_code")
    op.execute("DROP INDEX IF EXISTS ix_allowance_types_tenant")

    op.execute("DROP INDEX IF EXISTS uq_salary_grade_code")
    op.execute("DROP INDEX IF EXISTS ix_salary_grades_tenant")

    # ------------------------------------------------------------------
    # Drop tables (reverse dependency order)
    # ------------------------------------------------------------------
    op.drop_table("payroll_audit_log")
    op.drop_table("bank_file_configs")
    op.drop_table("payroll_approvals")
    op.drop_table("payroll_item_deductions")
    op.drop_table("payroll_item_earnings")
    op.drop_table("payroll_items")
    op.drop_table("payroll_runs")
    op.drop_table("staff_deductions")
    op.drop_table("staff_allowances")
    op.drop_table("staff_salary_configs")
    op.drop_table("tax_brackets")
    op.drop_table("deduction_types")
    op.drop_table("allowance_types")
    op.drop_table("salary_grades")

    # ------------------------------------------------------------------
    # Drop enums
    # ------------------------------------------------------------------
    sa.Enum(name="payrollapprovalaction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="deductioncategory").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payrollpaymentmethod").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="calculationmethod").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payrollruntype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payrollrunstatus").drop(op.get_bind(), checkfirst=True)

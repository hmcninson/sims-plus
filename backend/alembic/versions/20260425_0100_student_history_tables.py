"""Student Management Gap Closure Phase 1: Class History & Status Changes

New tables:
  - student_class_history: Immutable audit trail of class/section assignments
  - student_status_changes: Immutable audit trail of enrollment status transitions

Backfill: Seeds student_class_history from current student assignments.

Restricted grants:
  - student_class_history: SELECT, INSERT, UPDATE (no DELETE — audit table)
  - student_status_changes: SELECT, INSERT (append-only — no UPDATE or DELETE)

Revision ID: 20260425_0100
Revises: 20260422_0100
Create Date: 2026-04-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "20260425_0100"
down_revision: Union[str, None] = "20260422_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =================================================================
    # TABLE 1: student_class_history
    # =================================================================
    op.create_table(
        "student_class_history",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", UUID(as_uuid=True), sa.ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrolled_date", sa.Date(), nullable=False),
        sa.Column("left_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # =================================================================
    # TABLE 2: student_status_changes
    # =================================================================
    op.create_table(
        "student_status_changes",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("performed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # =================================================================
    # RLS: Enable and force on both tables
    # =================================================================
    for table_name in ("student_class_history", "student_status_changes"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """)

    # =================================================================
    # GRANTS: Restricted permissions (F-9)
    # =================================================================

    # student_class_history: no DELETE (audit table)
    op.execute("GRANT SELECT, INSERT, UPDATE ON student_class_history TO sims_app_user")

    # student_status_changes: append-only (no UPDATE or DELETE)
    op.execute("GRANT SELECT, INSERT ON student_status_changes TO sims_app_user")

    # =================================================================
    # INDEXES: student_class_history
    # =================================================================

    # Student timeline lookup (most recent first)
    op.execute("""
        CREATE INDEX ix_sch_student
        ON student_class_history(student_id, created_at DESC)
    """)

    # Student + academic year lookup
    op.execute("""
        CREATE INDEX ix_sch_student_year
        ON student_class_history(student_id, academic_year_id)
    """)

    # Class roster for a given year
    op.execute("""
        CREATE INDEX ix_sch_class_year
        ON student_class_history(class_id, academic_year_id)
    """)

    # Active assignment uniqueness: one active assignment per student per class per year
    op.execute("""
        CREATE UNIQUE INDEX uq_sch_active_assignment
        ON student_class_history(student_id, class_id, academic_year_id, tenant_id)
        WHERE left_date IS NULL
    """)

    # =================================================================
    # INDEXES: student_status_changes
    # =================================================================

    # Student timeline lookup (most recent first)
    op.execute("""
        CREATE INDEX ix_ssc_student
        ON student_status_changes(student_id, created_at DESC)
    """)

    # Date-range queries scoped by tenant
    op.execute("""
        CREATE INDEX ix_ssc_effective
        ON student_status_changes(tenant_id, effective_date)
    """)

    # Status filtering scoped by tenant
    op.execute("""
        CREATE INDEX ix_ssc_to_status
        ON student_status_changes(tenant_id, to_status, effective_date)
    """)

    # =================================================================
    # BACKFILL: Seed class history from current student assignments
    # =================================================================
    op.execute("""
        INSERT INTO student_class_history (
            id, tenant_id, student_id, school_id, class_id, section_id,
            academic_year_id, enrolled_date, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            s.tenant_id,
            s.id,
            s.school_id,
            s.class_id,
            s.section_id,
            ay.id,
            COALESCE(s.admission_date, s.created_at::date),
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM students s
        INNER JOIN academic_years ay
            ON ay.tenant_id = s.tenant_id
            AND ay.school_id = s.school_id
            AND ay.status = 'active'
        WHERE s.class_id IS NOT NULL
            AND s.school_id IS NOT NULL
            AND s.status = 'active'
            AND s.deleted_at IS NULL
    """)


def downgrade() -> None:
    # --- Drop indexes ---
    op.execute("DROP INDEX IF EXISTS ix_ssc_to_status")
    op.execute("DROP INDEX IF EXISTS ix_ssc_effective")
    op.execute("DROP INDEX IF EXISTS ix_ssc_student")
    op.execute("DROP INDEX IF EXISTS uq_sch_active_assignment")
    op.execute("DROP INDEX IF EXISTS ix_sch_class_year")
    op.execute("DROP INDEX IF EXISTS ix_sch_student_year")
    op.execute("DROP INDEX IF EXISTS ix_sch_student")

    # --- Drop RLS policies and revoke grants ---
    for table_name in ("student_status_changes", "student_class_history"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")
        op.execute(f"REVOKE ALL ON {table_name} FROM sims_app_user")

    # --- Drop tables ---
    op.drop_table("student_status_changes")
    op.drop_table("student_class_history")

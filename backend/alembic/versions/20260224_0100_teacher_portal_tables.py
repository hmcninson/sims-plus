"""Add teacher portal tables: report_comments, lesson_plans; add teacher_id to class_subjects

Two new tenant-scoped tables for the teacher portal (Sprint 15-16).
All tables have RLS enabled and forced with hardened tenant isolation.

- report_comments: class teacher and head teacher comments per student per term
- lesson_plans: teacher lesson planning with topic, objectives, resources
- class_subjects.teacher_id: optional FK to staff.id for subject-teacher assignment

One new enum type: lessonplanstatus

Revision ID: 20260224_0100
Revises: 20260223_0100
Create Date: 2026-02-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgENUM, UUID


revision: str = "20260224_0100"
down_revision: Union[str, None] = "20260223_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -----------------------------------------------------------------------
# New tenant-scoped tables (must be added to conftest.py TENANT_SCOPED_TABLES)
# -----------------------------------------------------------------------
NEW_TENANT_SCOPED_TABLES = [
    "report_comments",
    "lesson_plans",
]

# -----------------------------------------------------------------------
# New enum type (lowercase values per project convention)
# -----------------------------------------------------------------------
ENUM_DEFINITIONS = {
    "lessonplanstatus": ("planned", "taught", "cancelled"),
}


def _enable_rls(table_name: str) -> None:
    """Enable and force RLS with hardened tenant isolation policy."""
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")


def _disable_rls(table_name: str) -> None:
    """Drop RLS policy and disable RLS."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 1: Create enum types (using DO block for idempotency)
    # ------------------------------------------------------------------
    for enum_name, values in ENUM_DEFINITIONS.items():
        values_str = ", ".join(f"'{v}'" for v in values)
        op.execute(f"""
            DO $$ BEGIN
                CREATE TYPE {enum_name} AS ENUM ({values_str});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$
        """)

    # ------------------------------------------------------------------
    # Phase 2: Add teacher_id to class_subjects
    # ------------------------------------------------------------------
    op.add_column(
        "class_subjects",
        sa.Column(
            "teacher_id",
            UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="SET NULL"),
            nullable=True,
            comment="Assigned teacher for this class-subject combination",
        ),
    )
    op.create_index(
        "ix_class_subjects_teacher_id",
        "class_subjects",
        ["teacher_id"],
    )

    # ------------------------------------------------------------------
    # Phase 3: Create report_comments table
    # ------------------------------------------------------------------
    op.create_table(
        "report_comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", UUID(as_uuid=True), sa.ForeignKey("terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_teacher_comment", sa.Text, nullable=True),
        sa.Column("head_teacher_comment", sa.Text, nullable=True),
        sa.Column("class_teacher_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True, comment="Staff member who wrote the class teacher comment"),
        sa.Column("head_teacher_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True, comment="Staff member who wrote the head teacher comment"),
        sa.Column("class_teacher_signed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("head_teacher_signed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial unique index: one active report comment per student per term
    # (excludes soft-deleted rows so a student can have a new comment after deletion)
    op.execute("""
        CREATE UNIQUE INDEX uq_report_comment_student_term
        ON report_comments (tenant_id, student_id, term_id)
        WHERE deleted_at IS NULL
    """)
    op.create_index("ix_report_comments_tenant_id", "report_comments", ["tenant_id"])
    op.create_index("ix_report_comments_student_id", "report_comments", ["student_id"])
    op.create_index("ix_report_comments_term_id", "report_comments", ["term_id"])

    # ------------------------------------------------------------------
    # Phase 4: Create lesson_plans table
    # ------------------------------------------------------------------
    op.create_table(
        "lesson_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("period", sa.Integer, nullable=True, comment="Period number within the day"),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("objectives", sa.Text, nullable=True),
        sa.Column("resources", sa.Text, nullable=True),
        sa.Column("activities", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", PgENUM("planned", "taught", "cancelled", name="lessonplanstatus", create_type=False), nullable=False, server_default=sa.text("'planned'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial unique indexes for lesson plans:
    # 1. When period IS specified: one plan per teacher+class+subject+date+period
    op.execute("""
        CREATE UNIQUE INDEX uq_lesson_plan_with_period
        ON lesson_plans (tenant_id, teacher_id, class_id, subject_id, date, period)
        WHERE period IS NOT NULL AND deleted_at IS NULL
    """)
    # 2. When period IS NULL: one plan per teacher+class+subject+date
    # (prevents duplicate "unscheduled" plans for the same class/subject/date)
    op.execute("""
        CREATE UNIQUE INDEX uq_lesson_plan_without_period
        ON lesson_plans (tenant_id, teacher_id, class_id, subject_id, date)
        WHERE period IS NULL AND deleted_at IS NULL
    """)
    op.create_index("ix_lesson_plans_tenant_id", "lesson_plans", ["tenant_id"])
    op.create_index("ix_lesson_plans_teacher_id", "lesson_plans", ["teacher_id"])
    op.create_index("ix_lesson_plans_class_id", "lesson_plans", ["class_id"])
    op.create_index("ix_lesson_plans_date", "lesson_plans", ["date"])

    # ------------------------------------------------------------------
    # Phase 5: Enable RLS on all new tables
    # ------------------------------------------------------------------
    for table_name in NEW_TENANT_SCOPED_TABLES:
        _enable_rls(table_name)


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 1: Disable RLS on all new tables
    # ------------------------------------------------------------------
    for table_name in reversed(NEW_TENANT_SCOPED_TABLES):
        _disable_rls(table_name)

    # ------------------------------------------------------------------
    # Phase 2: Drop tables
    # ------------------------------------------------------------------
    op.drop_table("lesson_plans")
    op.drop_table("report_comments")

    # ------------------------------------------------------------------
    # Phase 3: Remove teacher_id from class_subjects
    # ------------------------------------------------------------------
    op.drop_index("ix_class_subjects_teacher_id", table_name="class_subjects")
    op.drop_column("class_subjects", "teacher_id")

    # ------------------------------------------------------------------
    # Phase 4: Drop enum types
    # ------------------------------------------------------------------
    for enum_name in ENUM_DEFINITIONS:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

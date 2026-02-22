"""Add tenant_id foreign key constraints to all tenant-scoped tables.

The TenantMixin previously defined tenant_id as a bare UUID column without
a ForeignKey to tenants.id. While RLS enforces tenant isolation at the
database level, the lack of FK constraints meant:
1. No referential integrity -- orphaned rows could exist for deleted tenants
2. No CASCADE delete -- removing a tenant would leave stale data behind
3. No database-level guarantee that tenant_id values are valid

This migration adds FK constraints with ON DELETE CASCADE to all 48
tenant-scoped tables in batches to avoid long-running locks.

Revision ID: add_tenant_fk_constraints
Revises: fix_rls_table_names
Create Date: 2026-02-16 02:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "add_tenant_fk_constraints"
down_revision = "fix_rls_table_names"
branch_labels = None
depends_on = None

# All tenant-scoped tables that use TenantMixin.
# Grouped by module for readability and batch processing.
TENANT_SCOPED_TABLES = [
    # Core
    "schools",
    "users",
    # Students
    "students",
    "guardians",
    "student_guardians",
    # Academic
    "academic_years",
    "terms",
    "classes",
    "class_sections",
    "subjects",
    "class_subjects",
    "grading_scales",
    "grades",
    "assessment_weights",
    "academic_settings",
    "school_holidays",
    # Staff
    "departments",
    "staff",
    "staff_class_assignments",
    # Attendance
    "student_attendance",
    "staff_attendance",
    # Exams
    "exams",
    "exam_subjects",
    "exam_scores",
    "continuous_assessments",
    "term_reports",
    "score_change_logs",
    # Timetable
    "class_timetables",
    "school_periods",
    # Preschool
    "learning_areas",
    "developmental_skills",
    "preschool_rating_scales",
    "student_skill_assessments",
    "progress_observations",
    "daily_activity_logs",
    "preschool_reports",
    # Finance
    "fee_types",
    "fee_structures",
    "fee_items",
    "invoices",
    "invoice_items",
    "invoice_scholarship_items",
    "payments",
    "scholarships",
    "student_scholarships",
    "scholarship_applications",
    "credit_notes",
    "finance_audit_log",
]


def _fk_name(table: str) -> str:
    """Generate consistent FK constraint name for a table."""
    return f"fk_{table}_tenant_id_tenants"


def upgrade() -> None:
    """Add tenant_id FK constraints to all tenant-scoped tables."""
    for table in TENANT_SCOPED_TABLES:
        op.create_foreign_key(
            constraint_name=_fk_name(table),
            source_table=table,
            referent_table="tenants",
            local_cols=["tenant_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Remove tenant_id FK constraints from all tenant-scoped tables."""
    for table in reversed(TENANT_SCOPED_TABLES):
        op.drop_constraint(
            constraint_name=_fk_name(table),
            table_name=table,
            type_="foreignkey",
        )

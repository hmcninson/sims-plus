"""Fix RLS table name mismatches -- apply hardened RLS to 9 missed tables.

The hardened_rls_policies migration used wrong table names for 6 tables
(spec names vs actual __tablename__ in models) and missed 3 tables entirely.
These 9 tenant-scoped tables have been running with ZERO database-level
isolation since the hardened RLS migration was applied.

WRONG NAMES (migration applied RLS to non-existent tables, so it was a no-op):
1. developmental_domains   -> learning_areas         (LearningArea model)
2. developmental_milestones -> developmental_skills   (DevelopmentalSkill model)
3. student_observations    -> progress_observations   (ProgressObservation model)
4. preschool_assessments   -> student_skill_assessments (StudentSkillAssessment model)
5. score_change_log        -> score_change_logs       (ScoreChangeLog model)
6. timetable_periods       -> school_periods          (SchoolPeriod model)

MISSING ENTIRELY (have TenantMixin but were never listed):
7. preschool_rating_scales   (PreschoolRatingScale model)
8. staff_class_assignments   (StaffClassAssignment model)
9. invoice_scholarship_items (InvoiceScholarshipItem model)

Revision ID: fix_rls_table_names
Revises: seed_reserved_subdomains
"""
from alembic import op
from sqlalchemy import text

from app.db.rls_helpers import enable_rls_for_table, disable_rls_for_table

revision = "fix_rls_table_names"
down_revision = "seed_reserved_subdomains"
branch_labels = None
depends_on = None

# Tables that need hardened RLS applied for the first time.
# These were either listed with wrong names (no-op because the table
# didn't exist) or omitted entirely from the hardened_rls_policies migration.
TABLES_TO_FIX = [
    # Wrong name in original migration -> correct name
    "learning_areas",             # was: developmental_domains
    "developmental_skills",       # was: developmental_milestones
    "progress_observations",      # was: student_observations
    "student_skill_assessments",  # was: preschool_assessments
    "score_change_logs",          # was: score_change_log
    "school_periods",             # was: timetable_periods
    # Missing entirely from original migration
    "preschool_rating_scales",
    "staff_class_assignments",
    "invoice_scholarship_items",
]


def upgrade() -> None:
    connection = op.get_bind()

    for table_name in TABLES_TO_FIX:
        # Verify the table actually exists before applying RLS.
        # (Defensive: in case this migration runs on a database where the
        # table hasn't been created yet by an earlier migration.)
        result = connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """), {"table_name": table_name})
        table_exists = result.scalar()

        if not table_exists:
            continue

        enable_rls_for_table(connection, table_name)

        # Ensure tenant_id index exists for RLS performance
        connection.execute(text(f"""
            CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant_id
            ON {table_name} (tenant_id)
        """))

    # Grant usage on any new sequences
    connection.execute(text(
        "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user"
    ))


def downgrade() -> None:
    connection = op.get_bind()

    for table_name in TABLES_TO_FIX:
        result = connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """), {"table_name": table_name})
        table_exists = result.scalar()

        if not table_exists:
            continue

        disable_rls_for_table(connection, table_name)

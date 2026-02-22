"""Hardened RLS policies -- remove NULL bypass and platform admin bypass.

Fixes:
- F1 (CRITICAL): Removes OR (get_current_tenant_id() IS NULL) from all policies
- F5 (HIGH): Removes OR (current_setting('app.is_platform_admin', true) = 'true')
- F9 (MEDIUM): Drops old current_tenant_id() function, standardizes on get_current_tenant_id()

After this migration:
- sims_app_user without tenant context sees ZERO rows (safe default)
- sims_app_user with context sees ONLY that tenant's rows
- sims_app_user cannot INSERT with a different tenant_id (WITH CHECK)
- sims_admin (superuser) bypasses RLS for migrations (PostgreSQL built-in behavior)

Revision ID: hardened_rls_policies
Revises: 20260125_0100
"""
from alembic import op
from sqlalchemy import text

revision = "hardened_rls_policies"
down_revision = "20260125_0100"
branch_labels = None
depends_on = None

# ALL tenant-scoped tables in the database.
# This list MUST be kept in sync with backend/tests/conftest.py TENANT_SCOPED_TABLES.
# When adding a new tenant-scoped table, add it here AND in conftest.py.
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


def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: Ensure get_current_tenant_id() function is correct and canonical
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION get_current_tenant_id()
        RETURNS UUID AS $$
        DECLARE
            tenant_str TEXT;
            tenant_uuid UUID;
        BEGIN
            -- Get the setting, with empty string as default if not set
            tenant_str := current_setting('app.current_tenant_id', true);

            -- Return NULL if empty or not set
            IF tenant_str IS NULL OR tenant_str = '' THEN
                RETURN NULL;
            END IF;

            -- Try to cast to UUID safely
            BEGIN
                tenant_uuid := tenant_str::UUID;
                RETURN tenant_uuid;
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL;
            END;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))

    # Step 2: Ensure set_tenant_context() function exists
    connection.execute(text("DROP FUNCTION IF EXISTS set_tenant_context(UUID)"))
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, false);
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Step 3: Ensure clear_tenant_context() function exists
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION clear_tenant_context()
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', '', false);
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Step 4: Drop old function names (F9 fix)
    connection.execute(text("DROP FUNCTION IF EXISTS current_tenant_id()"))

    # Step 5: Drop is_platform_admin() function (F5 fix)
    connection.execute(text("DROP FUNCTION IF EXISTS is_platform_admin()"))

    # Step 6: For each tenant-scoped table, drop old policies and create hardened ones
    for table_name in TENANT_SCOPED_TABLES:
        # Check if table exists (some tables may not exist yet in all environments)
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

        # Drop ALL existing policies on this table
        connection.execute(text(f"""
            DO $$
            DECLARE
                pol RECORD;
            BEGIN
                FOR pol IN
                    SELECT policyname FROM pg_policies WHERE tablename = '{table_name}'
                LOOP
                    EXECUTE 'DROP POLICY IF EXISTS ' || pol.policyname || ' ON {table_name}';
                END LOOP;
            END $$;
        """))

        # Enable RLS
        connection.execute(text(
            f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"
        ))

        # FORCE RLS even for table owner
        connection.execute(text(
            f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"
        ))

        # Create hardened policy -- NO bypasses
        connection.execute(text(f"""
            CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """))

        # Grant table permissions to app user
        connection.execute(text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
        ))

        # Ensure tenant_id index exists for RLS performance
        connection.execute(text(f"""
            CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant_id
            ON {table_name} (tenant_id)
        """))

    # Step 7: Grant usage on sequences to sims_app_user
    connection.execute(text(
        "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user"
    ))


def downgrade() -> None:
    """Restore old policies (NOT recommended -- only for emergency rollback)."""
    connection = op.get_bind()

    for table_name in TENANT_SCOPED_TABLES:
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

        connection.execute(text(
            f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}"
        ))
        connection.execute(text(
            f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY"
        ))
        connection.execute(text(
            f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"
        ))

    # Restore old functions (for rollback only)
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION is_platform_admin()
        RETURNS BOOLEAN AS $$
        BEGIN
            RETURN COALESCE(current_setting('app.is_platform_admin', true), 'false') = 'true';
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))

"""RLS policy rework -- definitive hardened tenant isolation.

Drops ALL existing RLS policies on ALL 48 tenant-scoped tables and
recreates them with hardened policies:
- NO NULL bypass (F1 CRITICAL fix)
- NO is_platform_admin bypass (F5 HIGH fix)
- FORCE ROW LEVEL SECURITY on all tables
- Policies target sims_app_user specifically

When get_current_tenant_id() returns NULL:
  tenant_id = NULL -> NULL (treated as FALSE) -> ZERO rows.
This is the SAFE default.

Includes inline smoke tests (Deliverable 3) that run assertions at the
end of upgrade() to verify:
1. Every existing tenant-scoped table has exactly one hardened policy
2. No policy contains a NULL bypass
3. No policy references is_platform_admin

Revision ID: rls_policy_rework
Revises: add_tenant_fk_constraints
Create Date: 2026-02-16 03:00:00.000000
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "rls_policy_rework"
down_revision = "add_tenant_fk_constraints"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Authoritative list of ALL 48 tenant-scoped tables.
# Derived from every model using TenantMixin.
#
# NOT included (no tenant_id):
#   - tenants             (core, not tenant-scoped)
#   - reserved_subdomains (core, not tenant-scoped)
#   - preschool_ratings   (lookup table, not tenant-scoped)
#
# This list MUST be kept in sync with:
#   - backend/tests/conftest.py :: TENANT_SCOPED_TABLES
#   - backend/app/db/rls_helpers.py (used for future table additions)
# ---------------------------------------------------------------------------
TENANT_SCOPED_TABLES = [
    # Core
    "schools",
    "users",
    # Students
    "students",
    "guardians",
    "student_guardians",
    # Staff
    "departments",
    "staff",
    "staff_class_assignments",
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
    "school_periods",
    "class_timetables",
    # Attendance
    "student_attendance",
    "staff_attendance",
    # Exams
    "exams",
    "exam_subjects",
    "exam_scores",
    "score_change_logs",
    "continuous_assessments",
    "term_reports",
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


def _table_exists(connection, table_name: str) -> bool:
    """Check if a table exists in the public schema."""
    result = connection.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :t
            )
        """),
        {"t": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Drop all existing RLS policies and recreate hardened tenant isolation.

    This is a clean-slate rework. For each tenant-scoped table:
    1. Dynamically discover and drop ALL existing policies (any name)
    2. Disable RLS (clean slate)
    3. Re-enable and FORCE RLS
    4. Create a single hardened policy: tenant_isolation_{table}
    5. Grant CRUD permissions to sims_app_user
    6. Ensure tenant_id index exists

    After the loop, drop legacy infrastructure and run smoke tests.
    """
    connection = op.get_bind()

    # ------------------------------------------------------------------
    # Phase 1: Drop and recreate RLS on every tenant-scoped table
    # ------------------------------------------------------------------
    tables_processed = 0

    for table in TENANT_SCOPED_TABLES:
        if not _table_exists(connection, table):
            continue

        # 1a. Drop ALL existing policies (dynamic discovery from pg_policies)
        #     This catches policies with ANY name, not just our convention.
        connection.execute(
            text(f"""
                DO $$
                DECLARE pol RECORD;
                BEGIN
                    FOR pol IN
                        SELECT policyname
                        FROM pg_policies
                        WHERE tablename = '{table}'
                    LOOP
                        EXECUTE 'DROP POLICY IF EXISTS '
                            || quote_ident(pol.policyname)
                            || ' ON {table}';
                    END LOOP;
                END $$;
            """)
        )

        # 1b. Disable RLS (clean slate before re-enabling)
        connection.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

        # 1c. Enable RLS
        connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))

        # 1d. FORCE RLS even for the table owner role.
        #     This is critical: without FORCE, the table owner bypasses RLS.
        connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        # 1e. Create the hardened tenant isolation policy.
        #     - FOR ALL: covers SELECT, INSERT, UPDATE, DELETE
        #     - TO sims_app_user: only the application role; superuser (sims_admin)
        #       bypasses RLS by PostgreSQL design, so migrations are not blocked.
        #     - USING: controls which rows are visible (SELECT, UPDATE, DELETE)
        #     - WITH CHECK: controls which rows can be written (INSERT, UPDATE)
        #     - NO NULL bypass: if get_current_tenant_id() returns NULL,
        #       tenant_id = NULL evaluates to NULL (treated as FALSE). Zero rows.
        #     - NO is_platform_admin bypass: admin operations use sims_admin role.
        connection.execute(
            text(f"""
                CREATE POLICY tenant_isolation_{table} ON {table}
                FOR ALL
                TO sims_app_user
                USING (tenant_id = get_current_tenant_id())
                WITH CHECK (tenant_id = get_current_tenant_id())
            """)
        )

        # 1f. Grant CRUD permissions to sims_app_user
        connection.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO sims_app_user")
        )

        # 1g. Ensure tenant_id index exists for RLS performance.
        #     Composite queries filter by tenant_id first; this index is critical.
        connection.execute(
            text(f"""
                CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id
                ON {table} (tenant_id)
            """)
        )

        tables_processed += 1

    # ------------------------------------------------------------------
    # Phase 2: Drop legacy infrastructure
    # ------------------------------------------------------------------

    # Drop is_platform_admin() -- the F5 bypass vector
    connection.execute(text("DROP FUNCTION IF EXISTS is_platform_admin()"))

    # Drop old current_tenant_id() if it still exists (superseded by get_current_tenant_id)
    connection.execute(text("DROP FUNCTION IF EXISTS current_tenant_id()"))

    # ------------------------------------------------------------------
    # Phase 3: Grant sequence usage to sims_app_user
    # ------------------------------------------------------------------
    connection.execute(
        text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user")
    )

    # ------------------------------------------------------------------
    # Phase 4: Inline smoke tests (Deliverable 3)
    #
    # These assertions run inside the migration transaction. If any fail,
    # the entire migration rolls back -- no partial state is possible.
    # ------------------------------------------------------------------

    # Smoke test 1: Verify every existing tenant-scoped table has a policy.
    #   Count distinct table names that have our tenant_isolation_* policy.
    result = connection.execute(
        text(
            "SELECT COUNT(DISTINCT tablename) FROM pg_policies "
            "WHERE schemaname = 'public' "
            "AND policyname LIKE 'tenant_isolation_%'"
        )
    )
    policy_count = result.scalar()
    expected = sum(1 for t in TENANT_SCOPED_TABLES if _table_exists(connection, t))
    assert policy_count == expected, (
        f"RLS SMOKE TEST FAILED: Expected {expected} tables with "
        f"tenant_isolation policies, got {policy_count}. "
        f"Tables processed: {tables_processed}."
    )

    # Smoke test 2: Verify NO policy contains a NULL bypass.
    #   A NULL bypass looks like: OR (get_current_tenant_id() IS NULL)
    #   We check the qual column in pg_policies for any IS NULL reference.
    result = connection.execute(
        text(
            "SELECT tablename, policyname FROM pg_policies "
            "WHERE schemaname = 'public' "
            "AND (qual::text LIKE '%IS NULL%' OR with_check::text LIKE '%IS NULL%')"
        )
    )
    null_policies = result.fetchall()
    assert len(null_policies) == 0, (
        f"RLS SMOKE TEST FAILED: Found policies with NULL bypass: "
        f"{[(row[0], row[1]) for row in null_policies]}"
    )

    # Smoke test 3: Verify NO policy references is_platform_admin.
    #   An admin bypass looks like: OR (is_platform_admin() = true)
    #   Check both USING (qual) and WITH CHECK (with_check) clauses.
    result = connection.execute(
        text(
            "SELECT tablename, policyname FROM pg_policies "
            "WHERE schemaname = 'public' "
            "AND (qual::text LIKE '%is_platform_admin%' "
            "     OR with_check::text LIKE '%is_platform_admin%')"
        )
    )
    admin_policies = result.fetchall()
    assert len(admin_policies) == 0, (
        f"RLS SMOKE TEST FAILED: Found policies with admin bypass: "
        f"{[(row[0], row[1]) for row in admin_policies]}"
    )

    # Smoke test 4: Verify RLS is FORCE-enabled on all processed tables.
    #   pg_class.relforcerowsecurity must be true for every tenant-scoped table.
    result = connection.execute(
        text("""
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
            AND c.relname = ANY(:tables)
            AND (c.relrowsecurity = false OR c.relforcerowsecurity = false)
        """),
        {"tables": [t for t in TENANT_SCOPED_TABLES if _table_exists(connection, t)]},
    )
    unforced_tables = [row[0] for row in result.fetchall()]
    assert len(unforced_tables) == 0, (
        f"RLS SMOKE TEST FAILED: Tables without FORCE ROW LEVEL SECURITY: "
        f"{unforced_tables}"
    )

    # Smoke test 5: Verify each policy targets sims_app_user (not PUBLIC).
    result = connection.execute(
        text("""
            SELECT tablename, policyname, roles
            FROM pg_policies
            WHERE schemaname = 'public'
            AND policyname LIKE 'tenant_isolation_%'
            AND NOT (roles @> ARRAY['sims_app_user']::name[])
        """)
    )
    wrong_role_policies = result.fetchall()
    assert len(wrong_role_policies) == 0, (
        f"RLS SMOKE TEST FAILED: Policies not targeting sims_app_user: "
        f"{[(row[0], row[1], row[2]) for row in wrong_role_policies]}"
    )


def downgrade() -> None:
    """Remove all hardened RLS policies and disable RLS.

    WARNING: This leaves all tenant-scoped tables WITHOUT database-level
    isolation. Only use for emergency rollback -- the application layer
    still filters by tenant_id, but defense-in-depth is lost.
    """
    connection = op.get_bind()

    for table in TENANT_SCOPED_TABLES:
        if not _table_exists(connection, table):
            continue

        # Drop the hardened policy
        connection.execute(
            text(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        )

        # Remove FORCE
        connection.execute(
            text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        )

        # Disable RLS
        connection.execute(
            text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        )

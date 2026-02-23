#!/usr/bin/env python3
"""
SIMS Plus - RLS Policy Verification Script

Connects to the database as sims_app_user (the runtime application role)
and verifies that all tenant-scoped tables have correct, hardened RLS policies.

This script checks for:
  1. Policy existence on every tenant-scoped table
  2. Policy targets sims_app_user (not just superuser)
  3. No NULL bypass vulnerabilities (IS NULL in USING clause)
  4. No platform admin bypass (is_platform_admin in USING clause)
  5. Policy uses get_current_tenant_id() for tenant isolation
  6. FORCE ROW LEVEL SECURITY is enabled (applies RLS even to table owners)

Usage:
  cd backend
  python scripts/verify_rls.py

  # Or with explicit DATABASE_URL:
  DATABASE_URL=postgresql://sims_app_user:app_password@localhost:5432/sims_plus \
    python scripts/verify_rls.py

Exit codes:
  0 - All checks passed
  1 - One or more checks failed
  2 - Script error (connection failure, etc.)
"""

import os
import re
import sys

from sqlalchemy import create_engine, text

# ============================================================
# Authoritative list of all 48 tenant-scoped tables
# ============================================================
# Every table here has a tenant_id column and MUST have
# hardened RLS policies enforcing isolation.
TENANT_SCOPED_TABLES: list[str] = [
    "schools",
    "users",
    "students",
    "guardians",
    "student_guardians",
    "departments",
    "staff",
    "staff_class_assignments",
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
    "student_attendance",
    "staff_attendance",
    "exams",
    "exam_subjects",
    "exam_scores",
    "score_change_logs",
    "continuous_assessments",
    "term_reports",
    "learning_areas",
    "developmental_skills",
    "preschool_rating_scales",
    "preschool_ratings",
    "student_skill_assessments",
    "progress_observations",
    "daily_activity_logs",
    "preschool_reports",
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
    # Notifications & SMS
    "notifications",
    "sms_log",
    # Boarding
    "houses",
    "dormitories",
    "beds",
    "student_boarding",
    "boarding_roll_call",
    "boarding_roll_call_entries",
    "exeats",
    "boarding_incidents",
    "dining_meals",
    # Transport
    "vehicles",
    "drivers",
    "routes",
    "route_stops",
    "student_transport",
    "trip_logs",
    "vehicle_maintenance",
    # Push Notifications
    "push_subscriptions",
    # Parent Portal
    "announcements",
    "teacher_notes",
    "parent_notification_preferences",
    # Teacher Portal
    "report_comments",
    "lesson_plans",
    # User-School junction (chain support)
    "user_schools",
]

DEFAULT_DATABASE_URL = (
    "postgresql://sims_app_user:app_password@localhost:5432/sims_plus"
)


def _normalize_database_url(url: str) -> str:
    """
    Strip async driver suffixes so we get a synchronous psycopg2 URL.

    The app's DATABASE_URL often uses 'postgresql+asyncpg://...' but this
    script uses synchronous SQLAlchemy, which expects 'postgresql://...'.
    """
    # Replace async drivers with the default sync driver
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)
    url = re.sub(r"^postgresql\+aiopg://", "postgresql://", url)
    return url


def _get_database_url() -> str:
    """Resolve the database URL from environment or fall back to default.

    In CI, DATABASE_URL should always be set explicitly.
    The fallback is only for local development convenience.
    """
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        print(
            "WARNING: DATABASE_URL not set, using local development default.",
            file=sys.stderr,
        )
        return DEFAULT_DATABASE_URL
    return _normalize_database_url(raw_url)


# ============================================================
# Individual check functions
# ============================================================

def check_policy_exists(
    table: str,
    policies: list[dict],
) -> tuple[bool, str]:
    """Verify at least one RLS policy exists for the table."""
    if not policies:
        return False, "No RLS policy found"
    return True, ""


def check_policy_targets_app_user(
    table: str,
    policies: list[dict],
) -> tuple[bool, str]:
    """
    Verify at least one policy targets sims_app_user.

    Policies with roles={public} apply to all roles including sims_app_user,
    so we accept those as well.
    """
    for policy in policies:
        roles_raw = policy["roles"]
        # Hardened policies must target sims_app_user specifically (not PUBLIC)
        if "sims_app_user" in roles_raw:
            return True, ""
    role_list = ", ".join(p["roles"] for p in policies)
    return False, f"No policy targets sims_app_user (found roles: {role_list})"


def check_no_null_bypass(
    table: str,
    policies: list[dict],
) -> tuple[bool, str]:
    """
    Verify no policy USING clause contains an IS NULL check.

    A pattern like 'tenant_id IS NULL OR ...' creates a bypass where rows
    with NULL tenant_id (or when no tenant context is set) would be visible.
    """
    for policy in policies:
        qual = (policy.get("qual") or "").upper()
        with_check = (policy.get("with_check") or "").upper()
        if "IS NULL" in qual:
            return False, (
                f"Policy '{policy['policyname']}' USING clause contains "
                f"'IS NULL' (NULL bypass vulnerability)"
            )
        if "IS NULL" in with_check:
            return False, (
                f"Policy '{policy['policyname']}' WITH CHECK clause contains "
                f"'IS NULL' (NULL bypass vulnerability)"
            )
    return True, ""


def check_no_platform_admin_bypass(
    table: str,
    policies: list[dict],
) -> tuple[bool, str]:
    """
    Verify no policy references is_platform_admin.

    Platform admin bypass in RLS policies is a security risk -- admin access
    should be handled through a separate superuser connection, not by
    weakening RLS.
    """
    for policy in policies:
        qual = (policy.get("qual") or "").lower()
        with_check_val = (policy.get("with_check") or "").lower()
        if "is_platform_admin" in qual or "is_platform_admin" in with_check_val:
            return False, (
                f"Policy '{policy['policyname']}' references "
                f"'is_platform_admin' (admin bypass vulnerability)"
            )
    return True, ""


def check_uses_get_current_tenant_id(
    table: str,
    policies: list[dict],
) -> tuple[bool, str]:
    """
    Verify at least one policy uses get_current_tenant_id() in its
    USING clause for proper tenant isolation.
    """
    for policy in policies:
        qual = (policy.get("qual") or "").lower()
        with_check_val = (policy.get("with_check") or "").lower()
        if "get_current_tenant_id()" in qual and "get_current_tenant_id()" in with_check_val:
            return True, ""
    return False, "No policy has get_current_tenant_id() in both USING and WITH CHECK"


def check_force_rls(
    table: str,
    force_rls_map: dict[str, bool],
) -> tuple[bool, str]:
    """
    Verify FORCE ROW LEVEL SECURITY is enabled.

    Without FORCE RLS, the table owner can bypass policies. This must
    be ON so that even sims_admin respects RLS when querying directly.
    """
    if table not in force_rls_map:
        return False, "Table not found in pg_class (may not exist yet)"
    if not force_rls_map[table]:
        return False, "FORCE ROW LEVEL SECURITY is OFF"
    return True, ""


# ============================================================
# Main verification logic
# ============================================================

def run_verification() -> int:
    """
    Connect to the database and run all RLS checks.

    Returns 0 if all checks pass, 1 if any fail, 2 on connection error.
    """
    db_url = _get_database_url()

    # Mask password in output for safety
    display_url = re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", db_url)
    print(f"Connecting to: {display_url}")
    print()

    try:
        engine = create_engine(db_url, echo=False)
    except Exception as exc:
        print(f"ERROR: Failed to create database engine: {exc}", file=sys.stderr)
        return 2

    try:
        with engine.connect() as conn:
            # ----------------------------------------------------------
            # Fetch all RLS policies in the public schema
            # ----------------------------------------------------------
            policy_rows = conn.execute(
                text("""
                    SELECT schemaname, tablename, policyname, permissive,
                           roles::text AS roles, qual, with_check
                    FROM pg_policies
                    WHERE schemaname = 'public'
                    ORDER BY tablename, policyname
                """)
            ).fetchall()

            # Group policies by table name
            policies_by_table: dict[str, list[dict]] = {}
            for row in policy_rows:
                table = row.tablename
                policies_by_table.setdefault(table, []).append(
                    {
                        "policyname": row.policyname,
                        "permissive": row.permissive,
                        "roles": row.roles,
                        "qual": row.qual,
                        "with_check": row.with_check,
                    }
                )

            # ----------------------------------------------------------
            # Fetch FORCE RLS status for all tenant-scoped tables
            # ----------------------------------------------------------
            force_rls_rows = conn.execute(
                text("""
                    SELECT relname,
                           relrowsecurity AS rls_enabled,
                           relforcerowsecurity AS force_rls
                    FROM pg_class
                    WHERE relname = ANY(:tables)
                      AND relnamespace = (
                          SELECT oid FROM pg_namespace WHERE nspname = 'public'
                      )
                """),
                {"tables": TENANT_SCOPED_TABLES},
            ).fetchall()

            force_rls_map: dict[str, bool] = {
                row.relname: row.force_rls for row in force_rls_rows
            }
            rls_enabled_map: dict[str, bool] = {
                row.relname: row.rls_enabled for row in force_rls_rows
            }

    except Exception as exc:
        print(f"ERROR: Database query failed: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()

    # ----------------------------------------------------------
    # Run all checks
    # ----------------------------------------------------------
    print("=== SIMS Plus RLS Policy Verification ===")
    print()
    print(f"Checking {len(TENANT_SCOPED_TABLES)} tenant-scoped tables...")
    print()

    passed = 0
    failed = 0
    failures: list[tuple[str, str]] = []

    for table in TENANT_SCOPED_TABLES:
        table_policies = policies_by_table.get(table, [])
        table_errors: list[str] = []

        # Check 0: Table exists in pg_class
        if table not in rls_enabled_map:
            table_errors.append("Table not found in database")
        elif not rls_enabled_map[table]:
            # RLS not even enabled -- all other policy checks are moot
            table_errors.append("ROW LEVEL SECURITY is not enabled")
        else:
            # Run the six checks only if RLS is enabled
            checks = [
                check_policy_exists,
                check_policy_targets_app_user,
                check_no_null_bypass,
                check_no_platform_admin_bypass,
                check_uses_get_current_tenant_id,
            ]
            for check_fn in checks:
                ok, msg = check_fn(table, table_policies)
                if not ok:
                    table_errors.append(msg)

            # FORCE RLS is checked separately (different data source)
            ok, msg = check_force_rls(table, force_rls_map)
            if not ok:
                table_errors.append(msg)

        if table_errors:
            failed += 1
            error_summary = "; ".join(table_errors)
            print(f"  \u2717 {table}: {error_summary}")
            for err in table_errors:
                failures.append((table, err))
        else:
            passed += 1
            print(f"  \u2713 {table}: policy OK, FORCE RLS ON")

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    total = len(TENANT_SCOPED_TABLES)
    print()
    print("=== Summary ===")
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")

    if failures:
        print()
        print("  FAILURES:")
        for table, reason in failures:
            print(f"  - {table}: {reason}")
        print()
        print("EXIT CODE: 1 (FAIL)")
        return 1

    print()
    print("All tenant-scoped tables have correct hardened RLS policies.")
    print("EXIT CODE: 0 (PASS)")
    return 0


if __name__ == "__main__":
    sys.exit(run_verification())

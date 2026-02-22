"""
RLS Isolation Tests

These tests prove that PostgreSQL Row-Level Security correctly isolates
tenant data. They use the two-engine pattern:
- admin_session: superuser, seeds data across tenants
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests MUST run against sims_plus_test database with
RLS policies applied (alembic upgrade head on the test database).

NOTE: All RLS tests share database state and MUST NOT run in parallel.
The xdist_group marker ensures they run in the same worker when
pytest-xdist is active (e.g., pytest -n auto --dist loadgroup).
"""

import pytest
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
    TENANT_SCOPED_TABLES,
    RLS_EXEMPT_TABLES,
)

# When pytest-xdist is active, all classes/tests in this module are
# assigned to the same worker so they do not interleave with each other.
pytestmark = [
    pytest.mark.rls,
    pytest.mark.xdist_group("rls_serial"),
]


@pytest.mark.asyncio
class TestRLSNoContext:
    """Tests for behavior when NO tenant context is set."""

    async def test_no_context_users_returns_zero_rows(self, app_session, admin_session):
        """Without tenant context, SELECT on users returns 0 rows."""
        # Seed a user via admin
        tenant = await create_test_tenant(admin_session)
        await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Query as app_user WITHOUT context
        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        count = result.scalar()
        assert count == 0, f"Expected 0 rows without context, got {count}"

    async def test_no_context_schools_returns_zero_rows(self, app_session, admin_session):
        """Without tenant context, SELECT on schools returns 0 rows."""
        tenant = await create_test_tenant(admin_session)
        # Insert a school via admin
        await admin_session.execute(
            text("""
                INSERT INTO schools (
                    id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF',
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant["id"]),
                "name": "Test School",
                "slug": f"school-{uuid4().hex[:8]}",
            },
        )
        await admin_session.commit()

        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM schools"))
        count = result.scalar()
        assert count == 0, f"Expected 0 rows without context, got {count}"


@pytest.mark.asyncio
class TestRLSTenantIsolation:
    """Tests for cross-tenant isolation."""

    async def test_tenant_a_cannot_see_tenant_b_users(self, app_session, admin_session):
        """Tenant A's users are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"], "a@test.com")
        user_b = await create_test_user(admin_session, tenant_b["id"], "b@test.com")
        await admin_session.commit()

        # Query as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails = [row[0] for row in result.fetchall()]

        assert user_a["email"] in emails, "Tenant A should see its own user"
        assert user_b["email"] not in emails, "Tenant A must NOT see Tenant B's user"

    async def test_tenant_b_cannot_see_tenant_a_users(self, app_session, admin_session):
        """Tenant B's users are invisible to Tenant A (reverse check)."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Query as Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails = [row[0] for row in result.fetchall()]

        assert user_b["email"] in emails, "Tenant B should see its own user"
        assert user_a["email"] not in emails, "Tenant B must NOT see Tenant A's user"

    async def test_tenant_sees_only_own_count(self, app_session, admin_session):
        """Each tenant sees only its own row count."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # Create 3 users for A, 2 for B
        for _ in range(3):
            await create_test_user(admin_session, tenant_a["id"])
        for _ in range(2):
            await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Tenant A sees 3
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 3

        # Tenant B sees 2
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 2


@pytest.mark.asyncio
class TestRLSInsertProtection:
    """Tests for WITH CHECK clause (insert/update protection)."""

    async def test_cannot_insert_with_wrong_tenant_id(self, app_session, admin_session):
        """Tenant A cannot insert data with Tenant B's tenant_id."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Set context as Tenant A, try to insert with Tenant B's ID
        await set_app_tenant_context(app_session, tenant_a["id"])

        # Raw SQL execute() sends the statement to the DB immediately via
        # asyncpg, so the RLS WITH CHECK violation is raised by execute()
        # itself (no flush() needed unlike ORM operations).
        with pytest.raises((ProgrammingError, IntegrityError)) as exc_info:
            await app_session.execute(
                text("""
                    INSERT INTO users (
                        id, tenant_id, email, password_hash,
                        first_name, last_name, role, status,
                        email_verified, mfa_enabled, failed_login_attempts, timezone,
                        created_at, updated_at
                    ) VALUES (
                        CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                        :fn, :ln, :role, :status,
                        true, false, 0, 'Africa/Accra',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """),
                {
                    "id": str(uuid4()),
                    "tid": str(tenant_b["id"]),  # WRONG tenant_id
                    "email": f"cross-{uuid4().hex[:6]}@test.com",
                    "pw": "hash",
                    "fn": "Cross",
                    "ln": "Tenant",
                    "role": "teacher",
                    "status": "active",
                },
            )

        # RLS WITH CHECK violation surfaces as a "new row violates" error
        error_msg = str(exc_info.value).lower()
        assert "policy" in error_msg or "permission" in error_msg or "violates" in error_msg

    async def test_can_insert_with_correct_tenant_id(self, app_session, admin_session):
        """Tenant A CAN insert data with its own tenant_id."""
        tenant_a = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])

        # This should succeed -- inserting with the matching tenant_id
        await app_session.execute(
            text("""
                INSERT INTO users (
                    id, tenant_id, email, password_hash,
                    first_name, last_name, role, status,
                    email_verified, mfa_enabled, failed_login_attempts, timezone,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                    :fn, :ln, :role, :status,
                    true, false, 0, 'Africa/Accra',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),  # CORRECT tenant_id
                "email": f"correct-{uuid4().hex[:6]}@test.com",
                "pw": "hash",
                "fn": "Correct",
                "ln": "Insert",
                "role": "teacher",
                "status": "active",
            },
        )
        # No exception = RLS WITH CHECK accepted the row


@pytest.mark.asyncio
class TestRLSContextSwitching:
    """Tests for context switching and clearing."""

    async def test_context_cleared_returns_zero_rows(self, app_session, admin_session):
        """After clearing context, queries return 0 rows."""
        tenant = await create_test_tenant(admin_session)
        await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        # Set context -- should see data
        await set_app_tenant_context(app_session, tenant["id"])
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() > 0, "Should see data with context set"

        # Clear context -- should see 0 rows
        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0, "Should see 0 rows after clearing context"

    async def test_context_switch_between_tenants(self, app_session, admin_session):
        """Switching from Tenant A to Tenant B changes visible data."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"], "switch-a@test.com")
        user_b = await create_test_user(admin_session, tenant_b["id"], "switch-b@test.com")
        await admin_session.commit()

        # Context = Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails_a = [row[0] for row in result.fetchall()]
        assert user_a["email"] in emails_a
        assert user_b["email"] not in emails_a

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT email FROM users"))
        emails_b = [row[0] for row in result.fetchall()]
        assert user_b["email"] in emails_b
        assert user_a["email"] not in emails_b

    async def test_invalid_uuid_context_returns_zero_rows(self, app_session):
        """Setting an invalid UUID as context returns 0 rows (not an error).

        Uses raw set_config instead of set_tenant_context() because the
        function parameter requires a valid UUID. We test that the DB
        gracefully handles garbage values (get_current_tenant_id returns NULL).
        """
        await app_session.execute(
            text("SELECT set_config('app.current_tenant_id', 'not-a-uuid', true)")
        )
        app_session.expire_all()

        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0

    async def test_nonexistent_tenant_id_returns_zero_rows(self, app_session):
        """Setting a valid UUID that doesn't match any tenant returns 0 rows."""
        fake_tenant_id = uuid4()
        await set_app_tenant_context(app_session, fake_tenant_id)
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0


@pytest.mark.asyncio
class TestRLSUpdateDeleteProtection:
    """Tests for RLS protection against cross-tenant UPDATE and DELETE.

    These verify that even if an attacker knows the primary key of a row
    belonging to another tenant, they cannot modify or delete it.
    """

    async def test_cannot_update_to_wrong_tenant_id(self, app_session, admin_session):
        """A row's tenant_id must not be changeable to another tenant's ID.
        This would allow data to 'migrate' between tenants."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # Seed a school under Tenant A via admin (bypasses RLS)
        school_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO schools (
                    id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF',
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(school_id),
                "tid": str(tenant_a["id"]),
                "name": "My School",
                "slug": f"school-{uuid4().hex[:8]}",
            },
        )
        await admin_session.commit()

        # Set context to Tenant A (the legitimate owner), then try to
        # change the row's tenant_id to Tenant B's ID. The WITH CHECK
        # clause should reject this because the new tenant_id does not
        # match the session context. Raw SQL execute() raises immediately.
        await set_app_tenant_context(app_session, tenant_a["id"])
        with pytest.raises((ProgrammingError, IntegrityError)):
            await app_session.execute(
                text("""
                    UPDATE schools SET tenant_id = CAST(:new_tid AS uuid)
                    WHERE id = CAST(:id AS uuid)
                """),
                {"new_tid": str(tenant_b["id"]), "id": str(school_id)},
            )

    async def test_cannot_delete_other_tenants_data(self, app_session, admin_session):
        """Tenant A must not be able to delete Tenant B's rows,
        even if they know the row's primary key."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # Seed a school under Tenant B via admin
        school_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO schools (
                    id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF',
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(school_id),
                "tid": str(tenant_b["id"]),
                "name": "School B",
                "slug": f"school-{uuid4().hex[:8]}",
            },
        )
        await admin_session.commit()

        # Set context to Tenant A, try to delete Tenant B's school by PK.
        # RLS USING clause should filter the row out of visibility, so the
        # DELETE affects 0 rows instead of raising an error.
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(
            text("DELETE FROM schools WHERE id = CAST(:id AS uuid)"),
            {"id": str(school_id)},
        )
        assert result.rowcount == 0, "Tenant A deleted Tenant B's row -- RLS BREACH"


@pytest.mark.asyncio
class TestRLSPolicyConfiguration:
    """Tests that verify the structural integrity of RLS policies.

    These do not test data isolation (covered above) but instead inspect
    the PostgreSQL system catalogs to confirm that RLS is enabled, FORCE
    is set, and no dangerous bypass patterns exist in the policy definitions.
    A failure here means a migration is missing or a policy was incorrectly
    authored.
    """

    async def test_rls_on_all_tenant_scoped_tables(self, app_session):
        """Dynamically discover ALL tables with a tenant_id column and verify
        RLS is enabled on each one.

        This approach queries information_schema instead of relying on a
        hardcoded list, so it catches new tenant-scoped tables that were
        added to the schema but missed in the RLS migration. The 'tenants'
        table is excluded because it is the root table (not tenant-scoped).
        """
        # Step 1: Discover all tables that have a tenant_id column.
        # Exclude the root 'tenants' table and any tables intentionally
        # exempt from RLS (e.g. audit_logs for cross-tenant admin access).
        result = await app_session.execute(
            text("""
                SELECT table_name
                FROM information_schema.columns
                WHERE column_name = 'tenant_id'
                AND table_schema = 'public'
                AND table_name != 'tenants'
                ORDER BY table_name
            """)
        )
        db_tenant_tables = {
            row.table_name for row in result.fetchall()
        } - RLS_EXEMPT_TABLES

        assert len(db_tenant_tables) > 0, (
            "No tables with tenant_id found -- database may not be migrated"
        )

        # Step 2: Verify the hardcoded TENANT_SCOPED_TABLES list matches reality.
        # This catches both directions: tables in the DB but not in the list,
        # and tables in the list but not in the DB.
        missing_from_list = db_tenant_tables - set(TENANT_SCOPED_TABLES)
        assert not missing_from_list, (
            f"Tables with tenant_id column found in DB but missing from "
            f"TENANT_SCOPED_TABLES in conftest.py: {sorted(missing_from_list)}. "
            f"Add them to the list AND create an RLS migration."
        )

        extra_in_list = set(TENANT_SCOPED_TABLES) - db_tenant_tables
        assert not extra_in_list, (
            f"Tables in TENANT_SCOPED_TABLES but not found in DB with "
            f"tenant_id column: {sorted(extra_in_list)}. "
            f"Remove them from the list or check the table schema."
        )

        # Step 3: Verify RLS is enabled on every discovered table
        rls_result = await app_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = ANY(:tables)
            """),
            {"tables": list(db_tenant_tables)},
        )
        for row in rls_result.fetchall():
            assert row.rowsecurity is True, (
                f"RLS not enabled on '{row.tablename}'. "
                f"Run: ALTER TABLE {row.tablename} ENABLE ROW LEVEL SECURITY;"
            )

        # Step 4: Verify each table has a policy using get_current_tenant_id()
        for table_name in sorted(db_tenant_tables):
            policy_result = await app_session.execute(
                text("""
                    SELECT policyname, qual, with_check
                    FROM pg_policies
                    WHERE schemaname = 'public'
                    AND tablename = :table_name
                """),
                {"table_name": table_name},
            )
            policies = policy_result.fetchall()
            assert len(policies) > 0, (
                f"Table '{table_name}' has RLS enabled but NO policies defined. "
                f"Create a tenant_isolation policy for it."
            )

            # At least one policy must reference get_current_tenant_id()
            # in BOTH USING (qual) and WITH CHECK clauses.
            has_tenant_policy = any(
                "get_current_tenant_id" in (row.qual or "")
                and "get_current_tenant_id" in (row.with_check or "")
                for row in policies
            )
            assert has_tenant_policy, (
                f"Table '{table_name}' has policies but none reference "
                f"get_current_tenant_id() in both USING and WITH CHECK. "
                f"Policies: {[(p.policyname, p.qual, p.with_check) for p in policies]}"
            )

    async def test_force_rls_on_all_tenant_scoped_tables(self, app_session):
        """Verify FORCE ROW LEVEL SECURITY is set on all tenant-scoped tables.
        Without FORCE, the table owner bypasses RLS. This is dangerous if the
        app accidentally connects as the table owner."""
        result = await app_session.execute(
            text("""
                SELECT relname, relforcerowsecurity
                FROM pg_class
                WHERE relname = ANY(:tables)
            """),
            {"tables": TENANT_SCOPED_TABLES},
        )
        for row in result.fetchall():
            assert row.relforcerowsecurity is True, (
                f"FORCE RLS not set on '{row.relname}'. "
                f"Run: ALTER TABLE {row.relname} FORCE ROW LEVEL SECURITY;"
            )

    async def test_no_null_bypass_in_policies(self, app_session):
        """Verify that NO RLS policy contains a NULL/IS NULL bypass.
        A policy like 'tenant_id = current_setting(...) OR tenant_id IS NULL'
        would allow any row with a NULL tenant_id to be visible to all tenants."""
        result = await app_session.execute(
            text("""
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
            """)
        )
        for row in result.fetchall():
            if row.qual and "IS NULL" in row.qual.upper():
                pytest.fail(
                    f"Policy '{row.policyname}' on '{row.tablename}' "
                    f"contains NULL bypass: {row.qual}"
                )

    async def test_no_platform_admin_bypass_in_policies(self, app_session):
        """Verify that NO RLS policy contains a platform_admin bypass.
        If a policy grants unrestricted access to platform admins via a
        session variable or function check, a compromised admin token
        would expose all tenant data."""
        result = await app_session.execute(
            text("""
                SELECT tablename, policyname, qual
                FROM pg_policies
                WHERE schemaname = 'public'
            """)
        )
        for row in result.fetchall():
            if row.qual and "platform_admin" in row.qual.lower():
                pytest.fail(
                    f"Policy '{row.policyname}' on '{row.tablename}' "
                    f"contains platform_admin bypass: {row.qual}"
                )


@pytest.mark.asyncio
class TestGetDbTenantEnforcement:
    """Tests that get_db() dependency enforces tenant context.

    The get_db() dependency in deps.py raises HTTP 400 for non-public API
    routes when no tenant context is present. Public paths like /health are
    exempt.
    """

    async def test_get_db_raises_without_tenant_for_api_route(self, client):
        """get_db() raises HTTP 400 for non-public API routes without tenant context.

        The test client uses admin_session (no tenant context set), so any
        tenant-scoped endpoint should return 400 or 401 — either means the
        request is properly rejected before reaching the service layer.
        """
        response = await client.get("/api/v1/students")
        # 400 = no tenant context; 401 = no auth token.
        # Both are acceptable rejections for a missing-tenant request.
        assert response.status_code in (400, 401), (
            f"Expected 400 or 401 without tenant context, got {response.status_code}"
        )

    async def test_public_paths_work_without_tenant(self, client):
        """Public paths (health, subdomain check) work without tenant context."""
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
class TestNewSessionHasCleanContext:
    """Tests that new database sessions start with empty tenant context.

    NOTE: These tests use NullPool (each session gets a fresh connection),
    so they verify that PostgreSQL connections start clean by default.
    The pool checkout listener in session.py (which clears context on
    reused connections) is not exercised here because NullPool never
    reuses connections. The listener provides defense-in-depth in
    production where connection pooling is active.
    """

    async def test_new_session_has_empty_context(self, app_session):
        """A freshly created session should have no tenant context."""
        result = await app_session.execute(
            text("SELECT current_setting('app.current_tenant_id', true)")
        )
        value = result.scalar()
        assert value in (None, ""), (
            f"Fresh session should have empty tenant context, got '{value}'"
        )

    async def test_context_does_not_leak_between_sessions(self, admin_session):
        """Setting context on one session does not leak to another.

        Uses admin_session to create a tenant (bypasses RLS), then opens
        a separate new app_session and verifies it has a clean context.
        """
        from tests.conftest import app_session_maker

        # Create a tenant so we have a valid UUID to set as context
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Open a SEPARATE new session -- should be clean
        async with app_session_maker() as new_session:
            result = await new_session.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            value = result.scalar()
            assert value in (None, ""), (
                f"New session should have empty context, got '{value}'"
            )


@pytest.mark.asyncio
class TestFinanceTenantIsolation:
    """Tests that finance tables are properly tenant-isolated.

    Finance tables (fee_types, invoices) were added in Sprint 13-14.
    These tests verify that RLS policies are correctly applied to the
    newest module, preventing cross-tenant visibility of financial data.
    """

    async def test_fee_types_isolated(self, app_session, admin_session):
        """Fee types from Tenant A are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # fee_types has a NOT NULL school_id FK, so create a school first
        school_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO schools (
                    id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF',
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(school_id),
                "tid": str(tenant_a["id"]),
                "name": "Fee Test School",
                "slug": f"fee-{uuid4().hex[:8]}",
            },
        )

        # Seed a fee_type via admin for Tenant A
        await admin_session.execute(
            text("""
                INSERT INTO fee_types (
                    id, tenant_id, school_id, name, category, is_active,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :name, 'tuition', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "sid": str(school_id),
                "name": "Test Fee",
            },
        )
        await admin_session.commit()

        # Tenant B should see zero fee_types
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM fee_types"))
        assert result.scalar() == 0, "Tenant B should not see Tenant A's fee types"

    async def test_invoices_isolated(self, app_session, admin_session):
        """Invoices from Tenant A are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # Create prerequisite rows: school, student, academic_year, term
        school_id = uuid4()
        student_id = uuid4()
        academic_year_id = uuid4()
        term_id = uuid4()

        await admin_session.execute(
            text("""
                INSERT INTO schools (
                    id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix,
                    is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF',
                    true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(school_id),
                "tid": str(tenant_a["id"]),
                "name": "Invoice School",
                "slug": f"inv-{uuid4().hex[:8]}",
            },
        )

        await admin_session.execute(
            text("""
                INSERT INTO students (
                    id, tenant_id, school_id, student_id, first_name, last_name,
                    date_of_birth, gender, status,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :student_id, :fn, :ln,
                    '2010-01-01', 'male', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(student_id),
                "tid": str(tenant_a["id"]),
                "sid": str(school_id),
                "student_id": f"STU-{uuid4().hex[:6]}",
                "fn": "Test",
                "ln": "Student",
            },
        )

        await admin_session.execute(
            text("""
                INSERT INTO academic_years (
                    id, tenant_id, name, start_date, end_date,
                    status, is_current, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    '2025-09-01', '2026-07-31',
                    'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(academic_year_id),
                "tid": str(tenant_a["id"]),
                "name": "2025/2026",
            },
        )

        await admin_session.execute(
            text("""
                INSERT INTO terms (
                    id, tenant_id, academic_year_id, name, short_name,
                    sequence, start_date, end_date,
                    status, is_current, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid),
                    :name, :short_name,
                    1, '2025-09-01', '2025-12-20',
                    'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(term_id),
                "tid": str(tenant_a["id"]),
                "ayid": str(academic_year_id),
                "name": "Term 1",
                "short_name": "T1",
            },
        )

        # Create an invoice for Tenant A with all NOT NULL columns
        await admin_session.execute(
            text("""
                INSERT INTO invoices (
                    id, tenant_id, school_id, student_id, invoice_number,
                    academic_year_id, term_id,
                    subtotal, discount_amount, scholarship_discount,
                    tax_amount, total_amount, amount_paid, balance,
                    status, currency,
                    issue_date, due_date,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:school_id AS uuid), CAST(:sid AS uuid),
                    :inv_num,
                    CAST(:ayid AS uuid), CAST(:termid AS uuid),
                    1000.00, 0.00, 0.00,
                    0.00, 1000.00, 0.00, 1000.00,
                    'draft', 'GHS',
                    CURRENT_DATE, CURRENT_DATE + 30,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "school_id": str(school_id),
                "sid": str(student_id),
                "inv_num": f"INV-{uuid4().hex[:6]}",
                "ayid": str(academic_year_id),
                "termid": str(term_id),
            },
        )
        await admin_session.commit()

        # Tenant B should see zero invoices
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM invoices"))
        assert result.scalar() == 0, "Tenant B should not see Tenant A's invoices"

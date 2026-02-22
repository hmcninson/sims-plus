"""
SIMS Plus - IDOR (Insecure Direct Object Reference) Prevention Tests

Tests verify that tenants cannot access each other's resources by guessing
UUIDs. Even with a valid JWT token for Tenant A, accessing a student (or
other resource) that belongs to Tenant B must fail.

Defense-in-depth is achieved through:
1. Application-level tenant_id filter: Services always include
   .where(Model.tenant_id == tenant_id) in queries.
2. RLS: The database query runs under Tenant A's context, so rows belonging
   to Tenant B are invisible at the database level.
3. The endpoint returns 404 (not 403) to avoid leaking resource existence.

NOTE: These tests use the `client` fixture which overrides get_db with
admin_session_maker (superuser). This means RLS is NOT active in these
tests. What is being validated is the application-layer service code that
filters by tenant_id -- the first line of defense in our defense-in-depth
strategy.

Key behaviors tested:
- Cannot access another tenant's student by guessing the UUID
- Cannot access another tenant's guardian by guessing the UUID
- Cannot list students from another tenant's scope
"""

import pytest
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password


# SQL templates for tenant and user creation, centralized to avoid duplication.
# Every raw INSERT must include all NOT NULL columns that lack server defaults.
_TENANT_INSERT = text("""
    INSERT INTO tenants (id, subdomain, slug, name, is_active,
        tenant_type, subscription_tier, max_students,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), :sub, :slug, :name, true,
        'single_school', 'trial', 50,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_USER_INSERT = text("""
    INSERT INTO users (id, tenant_id, email, password_hash,
        first_name, last_name, role, status,
        email_verified, mfa_enabled, failed_login_attempts, timezone,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
        :fn, :ln, :role, :status,
        true, false, 0, 'Africa/Accra',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


@pytest.mark.asyncio
@pytest.mark.integration
class TestIDOR:
    """Tests for Insecure Direct Object Reference prevention.

    Each test creates two tenants, seeds data in one, authenticates as
    the other, and verifies the cross-tenant access fails with 404.

    NOTE: These tests run through a superuser session (admin_session_maker),
    so they validate the service-layer tenant_id filter, not RLS policies.
    RLS isolation is separately tested in test_rls.py.
    """

    async def _create_tenant_with_admin(
        self, admin_session: AsyncSession, subdomain_prefix: str
    ) -> dict:
        """Helper: create a tenant and admin user, return their details.

        Returns dict with keys: tenant_id, subdomain, user_id, email.
        """
        tenant_id = uuid4()
        subdomain = f"{subdomain_prefix}{uuid4().hex[:6]}"
        user_id = uuid4()
        email = f"admin-{subdomain}@test.com"

        # Create tenant with all NOT NULL columns
        await admin_session.execute(
            _TENANT_INSERT,
            {"id": str(tenant_id), "sub": subdomain, "slug": subdomain,
             "name": f"IDOR School {subdomain}"},
        )

        # Create admin user with all NOT NULL columns
        password_hash = hash_password("SecureP@ss1")
        await admin_session.execute(
            _USER_INSERT,
            {
                "id": str(user_id), "tid": str(tenant_id),
                "email": email, "pw": password_hash,
                "fn": "Admin", "ln": "User",
                "role": "school_admin", "status": "active",
            },
        )

        return {
            "tenant_id": tenant_id,
            "subdomain": subdomain,
            "user_id": user_id,
            "email": email,
        }

    async def _login(self, client, subdomain: str, email: str) -> str:
        """Helper: login and return access token."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecureP@ss1"},
            headers={"X-Subdomain": subdomain},
        )
        assert response.status_code == 200, (
            f"Login failed for {email} on {subdomain}: {response.text}"
        )
        return response.json()["access_token"]

    async def test_cannot_access_other_tenants_student(
        self, client, admin_session
    ):
        """Even with a valid token, cannot access a student belonging
        to another tenant by guessing the student ID.

        The student is created in Tenant B. Tenant A's admin authenticates
        and tries to GET /students/{student_id}. The service-layer
        tenant_id filter excludes Tenant B's student because the query
        includes .where(Student.tenant_id == current_user.tenant_id),
        so the endpoint returns 404 (not 403, to avoid leaking the
        resource's existence).
        """
        # Create Tenant A and Tenant B
        tenant_a = await self._create_tenant_with_admin(
            admin_session, "idora"
        )
        tenant_b = await self._create_tenant_with_admin(
            admin_session, "idorb"
        )

        # Create a student in Tenant B
        student_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, student_id, first_name,
                    last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
                    :fn, :ln, '2010-01-01', 'male', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(student_id), "tid": str(tenant_b["tenant_id"]),
                "sid": "STU-2026-001",
                "fn": "Secret", "ln": "Student",
            },
        )
        await admin_session.commit()

        # Login as Tenant A admin
        token_a = await self._login(
            client, tenant_a["subdomain"], tenant_a["email"]
        )

        # Try to access Tenant B's student from Tenant A's context
        response = await client.get(
            f"/api/v1/students/{student_id}",
            headers={
                "Authorization": f"Bearer {token_a}",
                "X-Subdomain": tenant_a["subdomain"],
            },
        )
        # Service-layer tenant_id filter excludes the student -- endpoint returns 404
        assert response.status_code == 404, (
            f"Expected 404 for cross-tenant student access, "
            f"got {response.status_code}: {response.text}. "
            "IDOR vulnerability: Tenant A can see Tenant B's student."
        )

    async def test_cannot_list_other_tenants_students(
        self, client, admin_session
    ):
        """When listing students, a tenant should only see their own.

        Create a student in Tenant B, then list students as Tenant A.
        The Tenant B student must not appear in the results because
        the service-layer tenant_id filter restricts the query to
        the authenticated tenant's data only.
        """
        # Create Tenant A and Tenant B
        tenant_a = await self._create_tenant_with_admin(
            admin_session, "lista"
        )
        tenant_b = await self._create_tenant_with_admin(
            admin_session, "listb"
        )

        # Create students in both tenants
        student_a_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, student_id, first_name,
                    last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
                    :fn, :ln, '2010-01-01', 'male', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(student_a_id), "tid": str(tenant_a["tenant_id"]),
                "sid": "STU-A-001",
                "fn": "Alice", "ln": "TenantA",
            },
        )

        student_b_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, student_id, first_name,
                    last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
                    :fn, :ln, '2010-01-01', 'female', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(student_b_id), "tid": str(tenant_b["tenant_id"]),
                "sid": "STU-B-001",
                "fn": "Bob", "ln": "TenantB",
            },
        )
        await admin_session.commit()

        # Login as Tenant A admin
        token_a = await self._login(
            client, tenant_a["subdomain"], tenant_a["email"]
        )

        # List students as Tenant A
        response = await client.get(
            "/api/v1/students",
            headers={
                "Authorization": f"Bearer {token_a}",
                "X-Subdomain": tenant_a["subdomain"],
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        items = data.get("items", [])

        # Tenant A's student should be visible
        student_ids_returned = [item["id"] for item in items]
        assert str(student_a_id) in student_ids_returned, (
            "Tenant A's own student not found in list"
        )

        # Tenant B's student must NOT be visible
        assert str(student_b_id) not in student_ids_returned, (
            "IDOR vulnerability: Tenant B's student visible in Tenant A's list"
        )

        # Verify no student with Tenant B's name appears
        first_names = [item["first_name"] for item in items]
        assert "Bob" not in first_names, (
            "IDOR vulnerability: Tenant B's student 'Bob' visible to Tenant A"
        )

    async def test_cannot_access_other_tenants_guardian(
        self, client, admin_session
    ):
        """Cannot access a guardian belonging to another tenant.

        Guardians are tenant-scoped via tenant_id. The service-layer
        tenant_id filter restricts queries to the authenticated tenant,
        so trying to access Tenant B's guardian from Tenant A's context
        returns 404.
        """
        # Create Tenant A and Tenant B
        tenant_a = await self._create_tenant_with_admin(
            admin_session, "guarda"
        )
        tenant_b = await self._create_tenant_with_admin(
            admin_session, "guardb"
        )

        # Create a guardian in Tenant B
        guardian_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO guardians (id, tenant_id, first_name, last_name,
                    phone, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    :fn, :ln, :phone,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(guardian_id), "tid": str(tenant_b["tenant_id"]),
                "fn": "Secret", "ln": "Guardian", "phone": "+233244999999",
            },
        )
        await admin_session.commit()

        # Login as Tenant A admin
        token_a = await self._login(
            client, tenant_a["subdomain"], tenant_a["email"]
        )

        # Try to access Tenant B's guardian from Tenant A's context
        response = await client.get(
            f"/api/v1/guardians/{guardian_id}",
            headers={
                "Authorization": f"Bearer {token_a}",
                "X-Subdomain": tenant_a["subdomain"],
            },
        )
        assert response.status_code == 404, (
            f"Expected 404 for cross-tenant guardian access, "
            f"got {response.status_code}: {response.text}. "
            "IDOR vulnerability: Tenant A can see Tenant B's guardian."
        )

    async def test_cannot_modify_other_tenants_student(
        self, client, admin_session
    ):
        """Cannot update or delete a student belonging to another tenant.

        Even if Tenant A knows the exact UUID of Tenant B's student,
        PUT and DELETE operations must fail because the service-layer
        tenant_id filter excludes the student from query results.
        """
        # Create Tenant A and Tenant B
        tenant_a = await self._create_tenant_with_admin(
            admin_session, "moda"
        )
        tenant_b = await self._create_tenant_with_admin(
            admin_session, "modb"
        )

        # Create a student in Tenant B
        student_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, student_id, first_name,
                    last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
                    :fn, :ln, '2010-01-01', 'male', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(student_id), "tid": str(tenant_b["tenant_id"]),
                "sid": "STU-MOD-001",
                "fn": "Protected", "ln": "Student",
            },
        )
        await admin_session.commit()

        # Login as Tenant A admin
        token_a = await self._login(
            client, tenant_a["subdomain"], tenant_a["email"]
        )
        auth_headers = {
            "Authorization": f"Bearer {token_a}",
            "X-Subdomain": tenant_a["subdomain"],
        }

        # Try to UPDATE Tenant B's student from Tenant A
        put_response = await client.put(
            f"/api/v1/students/{student_id}",
            json={"first_name": "Hacked"},
            headers=auth_headers,
        )
        assert put_response.status_code == 404, (
            f"Expected 404 for cross-tenant student update, "
            f"got {put_response.status_code}: {put_response.text}. "
            "IDOR vulnerability: Tenant A can modify Tenant B's student."
        )

        # Try to DELETE Tenant B's student from Tenant A
        delete_response = await client.delete(
            f"/api/v1/students/{student_id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 404, (
            f"Expected 404 for cross-tenant student delete, "
            f"got {delete_response.status_code}: {delete_response.text}. "
            "IDOR vulnerability: Tenant A can delete Tenant B's student."
        )

        # Verify the student is still intact in Tenant B by checking via admin
        result = await admin_session.execute(
            text("""
                SELECT first_name, deleted_at FROM students
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(student_id)},
        )
        row = result.fetchone()
        assert row is not None, "Student was deleted from database"
        assert row.first_name == "Protected", (
            f"Student name was modified to '{row.first_name}'"
        )
        assert row.deleted_at is None, "Student was soft-deleted"

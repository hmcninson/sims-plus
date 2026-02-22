"""
SIMS Plus - Student Management Integration Tests

Tests exercise full request-response cycles through FastAPI student endpoints
with a real PostgreSQL database. They verify CRUD operations, tenant isolation,
and proper authorization through the middleware + service layer stack.

Key behaviors tested:
- Create a student via POST /api/v1/students
- List students via GET /api/v1/students with pagination
- Get a single student by ID
- Update a student via PUT /api/v1/students/{id}
- Cross-tenant student isolation (Tenant A cannot see Tenant B's students)

NOTES:
- The `client` fixture overrides get_db with admin_session_maker (superuser),
  so RLS is NOT active. These tests validate service-layer tenant_id filtering.
- TenantMiddleware resolves X-Subdomain header via its own DB session.
- Student creation auto-generates student_id via advisory lock + sequence.
"""

import pytest
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password


# SQL templates for test data seeding.
# All NOT NULL columns without server defaults must be explicitly provided.
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

# Schools table requires: id, tenant_id, name, slug, school_type, status,
# student_id_prefix, staff_id_prefix, is_active, created_at, updated_at
_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', :student_id_prefix, 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name,
        last_name, date_of_birth, gender, status,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
        :fn, :ln, '2010-05-15', 'male', 'active',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_tenant(
    session: AsyncSession, tenant_id: UUID, subdomain: str, name: str,
) -> None:
    """Insert a tenant row with all required NOT NULL columns."""
    await session.execute(
        _TENANT_INSERT,
        {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": name},
    )


async def _seed_school(
    session: AsyncSession, school_id: UUID, tenant_id: UUID,
    name: str, slug: str, prefix: str = "STU",
) -> None:
    """Insert a school row with all required NOT NULL columns."""
    await session.execute(
        _SCHOOL_INSERT,
        {
            "id": str(school_id), "tid": str(tenant_id),
            "name": name, "slug": slug, "student_id_prefix": prefix,
        },
    )


async def _seed_user(
    session: AsyncSession,
    tenant_id: UUID,
    email: str,
    password: str,
    *,
    role: str = "school_admin",
    first_name: str = "Test",
    last_name: str = "User",
) -> UUID:
    """Insert a user row. Returns the user ID."""
    user_id = uuid4()
    password_hash = hash_password(password)
    await session.execute(
        _USER_INSERT,
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": email,
            "pw": password_hash,
            "fn": first_name,
            "ln": last_name,
            "role": role,
            "status": "active",
        },
    )
    return user_id


async def _login(client, subdomain: str, email: str, password: str = "SecureP@ss1") -> str:
    """Login and return the access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Subdomain": subdomain},
    )
    assert response.status_code == 200, (
        f"Login failed for {email} on {subdomain}: {response.text}"
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestStudentManagement:
    """Tests for student CRUD operations and tenant isolation.

    Each test creates its own isolated tenant + school + admin user to
    avoid cross-test interference. The admin user gets SCHOOL_ADMIN role
    which has students.* permissions via the RBAC system.
    """

    async def test_create_student(self, client, admin_session):
        """POST /api/v1/students creates a student and returns 201.

        The endpoint auto-generates a student_id using the school's prefix
        and an advisory-lock-protected sequence counter. We verify that
        the response contains a valid student_id, correct names, and
        matches the input gender and date_of_birth.
        """
        tenant_id = uuid4()
        subdomain = f"stucr{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Student Create School")
        await _seed_school(admin_session, school_id, tenant_id, "Create School", subdomain, "CRE")
        await _seed_user(admin_session, tenant_id, "create-stu@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "create-stu@school.com")

        response = await client.post(
            "/api/v1/students",
            json={
                "first_name": "Kwame",
                "last_name": "Asante",
                "date_of_birth": "2010-05-15",
                "gender": "male",
                "school_id": str(school_id),
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 201, (
            f"Expected 201 for student creation, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["first_name"] == "Kwame"
        assert data["last_name"] == "Asante"
        assert data["gender"] == "male"
        assert data["date_of_birth"] == "2010-05-15"
        # student_id should be auto-generated with the school prefix
        assert data["student_id"].startswith("CRE"), (
            f"Expected student_id to start with 'CRE', got '{data['student_id']}'"
        )
        assert "id" in data  # UUID should be present

    async def test_list_students(self, client, admin_session):
        """GET /api/v1/students returns paginated student list.

        Seeds two students via raw SQL and verifies both appear in
        the paginated list response with correct structure.
        """
        tenant_id = uuid4()
        subdomain = f"stuls{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Student List School")
        await _seed_school(admin_session, school_id, tenant_id, "List School", subdomain)
        await _seed_user(admin_session, tenant_id, "list-stu@school.com", "SecureP@ss1")

        # Seed two students directly via raw SQL
        student_a_id = uuid4()
        student_b_id = uuid4()
        await admin_session.execute(
            _STUDENT_INSERT,
            {"id": str(student_a_id), "tid": str(tenant_id),
             "sid": "STU-LIST-001", "fn": "Alice", "ln": "Mensah"},
        )
        await admin_session.execute(
            _STUDENT_INSERT,
            {"id": str(student_b_id), "tid": str(tenant_id),
             "sid": "STU-LIST-002", "fn": "Bob", "ln": "Owusu"},
        )
        await admin_session.commit()

        token = await _login(client, subdomain, "list-stu@school.com")

        response = await client.get(
            "/api/v1/students",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()

        # Paginated response must have items and total
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2

        # Both students should be in the list
        first_names = [item["first_name"] for item in data["items"]]
        assert "Alice" in first_names
        assert "Bob" in first_names

    async def test_get_student_by_id(self, client, admin_session):
        """GET /api/v1/students/{id} returns a single student.

        Seeds a student via raw SQL, then retrieves it by UUID.
        Verifies all expected fields are present in the response.
        """
        tenant_id = uuid4()
        subdomain = f"stugt{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Student Get School")
        await _seed_school(admin_session, school_id, tenant_id, "Get School", subdomain)
        await _seed_user(admin_session, tenant_id, "get-stu@school.com", "SecureP@ss1")

        student_id = uuid4()
        await admin_session.execute(
            _STUDENT_INSERT,
            {"id": str(student_id), "tid": str(tenant_id),
             "sid": "STU-GET-001", "fn": "Ama", "ln": "Boateng"},
        )
        await admin_session.commit()

        token = await _login(client, subdomain, "get-stu@school.com")

        response = await client.get(
            f"/api/v1/students/{student_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 200, (
            f"Expected 200 for student get, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["id"] == str(student_id)
        assert data["first_name"] == "Ama"
        assert data["last_name"] == "Boateng"
        assert data["student_id"] == "STU-GET-001"

    async def test_update_student(self, client, admin_session):
        """PUT /api/v1/students/{id} updates a student.

        Seeds a student, then sends a PUT request to change the first name.
        Verifies the response reflects the updated value while unchanged
        fields remain intact.
        """
        tenant_id = uuid4()
        subdomain = f"stuup{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Student Update School")
        await _seed_school(admin_session, school_id, tenant_id, "Update School", subdomain)
        await _seed_user(admin_session, tenant_id, "update-stu@school.com", "SecureP@ss1")

        student_id = uuid4()
        await admin_session.execute(
            _STUDENT_INSERT,
            {"id": str(student_id), "tid": str(tenant_id),
             "sid": "STU-UPD-001", "fn": "Kofi", "ln": "Asante"},
        )
        await admin_session.commit()

        token = await _login(client, subdomain, "update-stu@school.com")

        response = await client.put(
            f"/api/v1/students/{student_id}",
            json={"first_name": "Kwesi"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 200, (
            f"Expected 200 for student update, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["first_name"] == "Kwesi", (
            f"Expected first_name to be 'Kwesi', got '{data['first_name']}'"
        )
        # Last name should be unchanged
        assert data["last_name"] == "Asante"

    async def test_cross_tenant_student_isolation(self, client, admin_session):
        """Students created in Tenant A must be invisible to Tenant B.

        Creates a student in Tenant B, then authenticates as Tenant A and
        verifies that:
        1. GET /students/{id} returns 404 (not 403, to avoid leaking existence)
        2. GET /students list does not include Tenant B's student

        This validates the service-layer tenant_id filter that provides
        defense-in-depth on top of PostgreSQL RLS.
        """
        # Create Tenant A
        tenant_a_id = uuid4()
        subdomain_a = f"stisa{uuid4().hex[:6]}"
        school_a_id = uuid4()
        await _seed_tenant(admin_session, tenant_a_id, subdomain_a, "Isolation A School")
        await _seed_school(admin_session, school_a_id, tenant_a_id, "School A", subdomain_a)
        await _seed_user(admin_session, tenant_a_id, "iso-a@school.com", "SecureP@ss1")

        # Create Tenant B with a student
        tenant_b_id = uuid4()
        subdomain_b = f"stisb{uuid4().hex[:6]}"
        school_b_id = uuid4()
        await _seed_tenant(admin_session, tenant_b_id, subdomain_b, "Isolation B School")
        await _seed_school(admin_session, school_b_id, tenant_b_id, "School B", subdomain_b)

        secret_student_id = uuid4()
        await admin_session.execute(
            _STUDENT_INSERT,
            {"id": str(secret_student_id), "tid": str(tenant_b_id),
             "sid": "STU-ISO-001", "fn": "Secret", "ln": "Student"},
        )
        await admin_session.commit()

        # Login as Tenant A admin
        token_a = await _login(client, subdomain_a, "iso-a@school.com")
        auth_headers = {
            "Authorization": f"Bearer {token_a}",
            "X-Subdomain": subdomain_a,
        }

        # Direct access by ID should return 404 (IDOR protection)
        get_response = await client.get(
            f"/api/v1/students/{secret_student_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404, (
            f"Expected 404 for cross-tenant student access, "
            f"got {get_response.status_code}: {get_response.text}. "
            "SECURITY: Tenant A can see Tenant B's student."
        )

        # List endpoint should not include Tenant B's student
        list_response = await client.get(
            "/api/v1/students",
            headers=auth_headers,
        )
        assert list_response.status_code == 200, list_response.text
        items = list_response.json().get("items", [])
        student_ids = [item["id"] for item in items]
        assert str(secret_student_id) not in student_ids, (
            "SECURITY: Tenant B's student appeared in Tenant A's student list."
        )

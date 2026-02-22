"""
SIMS Plus - Academic Module Integration Tests

Tests exercise full request-response cycles through FastAPI academic endpoints
with a real PostgreSQL database. They verify CRUD operations for academic years,
classes, and subjects through the middleware + service layer stack.

Key behaviors tested:
- Create academic year with date validation
- Create class with level and capacity
- Create subject with category
- List classes (verifies response structure with section counts)
- Academic year date ordering validation

NOTES:
- The `client` fixture overrides get_db with admin_session_maker (superuser),
  so RLS is NOT active. These tests validate service-layer tenant_id filtering.
- TenantMiddleware resolves X-Subdomain header via its own DB session.
- Academic endpoints require "academics.*" or "classes.*" or "subjects.*"
  permissions; SCHOOL_ADMIN role has wildcard access.
"""

import pytest
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password


# SQL templates for test data seeding.
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

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', 'STU', 'STF', true,
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
    name: str, slug: str,
) -> None:
    """Insert a school row with all required NOT NULL columns."""
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": name, "slug": slug},
    )


async def _seed_user(
    session: AsyncSession,
    tenant_id: UUID,
    email: str,
    password: str,
    *,
    role: str = "school_admin",
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
            "fn": "Test",
            "ln": "Admin",
            "role": role,
            "status": "active",
        },
    )
    return user_id


async def _login(client, subdomain: str, email: str) -> str:
    """Login and return the access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss1"},
        headers={"X-Subdomain": subdomain},
    )
    assert response.status_code == 200, (
        f"Login failed for {email} on {subdomain}: {response.text}"
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestAcademicModule:
    """Tests for academic year, class, and subject CRUD operations.

    Each test creates its own isolated tenant + school + admin user.
    """

    async def test_create_academic_year(self, client, admin_session):
        """POST /api/v1/academic/academic-years creates an academic year.

        Verifies the response includes all required fields: id, name,
        start_date, end_date, status, is_current.
        """
        tenant_id = uuid4()
        subdomain = f"acyr{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Academic Year School")
        await _seed_school(admin_session, school_id, tenant_id, "AY School", subdomain)
        await _seed_user(admin_session, tenant_id, "acyr@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "acyr@school.com")

        response = await client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "2025/2026",
                "description": "Test academic year",
                "start_date": "2025-09-01",
                "end_date": "2026-07-31",
                "is_current": True,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 201, (
            f"Expected 201 for academic year creation, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["name"] == "2025/2026"
        assert data["start_date"] == "2025-09-01"
        assert data["end_date"] == "2026-07-31"
        assert data["is_current"] is True
        assert "id" in data
        assert "status" in data

    async def test_create_class(self, client, admin_session):
        """POST /api/v1/academic/classes creates a class.

        Verifies the response includes name, short_name, level, sequence,
        capacity, and is_active fields.
        """
        tenant_id = uuid4()
        subdomain = f"clcr{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Class Create School")
        await _seed_school(admin_session, school_id, tenant_id, "Create Class School", subdomain)
        await _seed_user(admin_session, tenant_id, "class@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "class@school.com")

        response = await client.post(
            "/api/v1/academic/classes",
            json={
                "name": "JHS 1",
                "short_name": "J1",
                "level": "jhs",
                "sequence": 1,
                "capacity": 40,
                "school_id": str(school_id),
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 201, (
            f"Expected 201 for class creation, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["name"] == "JHS 1"
        assert data["short_name"] == "J1"
        assert data["level"] == "jhs"
        assert data["sequence"] == 1
        assert data["capacity"] == 40
        assert data["is_active"] is True

    async def test_create_subject(self, client, admin_session):
        """POST /api/v1/academic/subjects creates a subject.

        Verifies the response includes name, code, category, and is_active.
        """
        tenant_id = uuid4()
        subdomain = f"subj{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Subject School")
        await _seed_school(admin_session, school_id, tenant_id, "Subject School", subdomain)
        await _seed_user(admin_session, tenant_id, "subj@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "subj@school.com")

        response = await client.post(
            "/api/v1/academic/subjects",
            json={
                "name": "Mathematics",
                "code": "MATH",
                "description": "Core mathematics",
                "category": "core",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 201, (
            f"Expected 201 for subject creation, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["name"] == "Mathematics"
        assert data["code"] == "MATH"
        assert data["category"] == "core"
        assert data["is_active"] is True

    async def test_list_classes_with_section_counts(self, client, admin_session):
        """GET /api/v1/academic/classes returns class list with sections.

        Creates a class via the API, then fetches the list and verifies
        the response structure includes the sections array (may be empty).
        """
        tenant_id = uuid4()
        subdomain = f"clls{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Class List School")
        await _seed_school(admin_session, school_id, tenant_id, "List Class School", subdomain)
        await _seed_user(admin_session, tenant_id, "classlist@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "classlist@school.com")
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "X-Subdomain": subdomain,
        }

        # Create a class first
        create_response = await client.post(
            "/api/v1/academic/classes",
            json={
                "name": "Primary 6",
                "short_name": "P6",
                "level": "primary",
                "sequence": 6,
                "capacity": 35,
                "school_id": str(school_id),
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201, create_response.text

        # List classes
        list_response = await client.get(
            "/api/v1/academic/classes",
            headers=auth_headers,
        )
        assert list_response.status_code == 200, list_response.text
        data = list_response.json()

        # Response should be a list of classes
        assert isinstance(data, list)
        assert len(data) >= 1

        # Each class should have sections array and student counts
        found_class = None
        for cls in data:
            if cls["name"] == "Primary 6":
                found_class = cls
                break

        assert found_class is not None, (
            "Created class 'Primary 6' not found in class list"
        )
        assert "sections" in found_class
        assert isinstance(found_class["sections"], list)

    async def test_academic_year_end_before_start_rejected(self, client, admin_session):
        """Academic year with end_date before start_date must be rejected.

        The AcademicYearCreate schema has a field_validator that enforces
        end_date > start_date. The endpoint should return 422.
        """
        tenant_id = uuid4()
        subdomain = f"acvl{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Date Validation School")
        await _seed_school(admin_session, school_id, tenant_id, "Date Val School", subdomain)
        await _seed_user(admin_session, tenant_id, "dateval@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "dateval@school.com")

        # end_date is before start_date -- should fail validation
        response = await client.post(
            "/api/v1/academic/academic-years",
            json={
                "name": "Invalid Year",
                "start_date": "2026-09-01",
                "end_date": "2025-07-31",  # Before start_date
                "is_current": False,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 422, (
            f"Expected 422 for invalid date range, got {response.status_code}: "
            f"{response.text}"
        )

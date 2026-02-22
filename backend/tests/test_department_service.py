"""
Department Service Integration Tests

Tests for DepartmentService CRUD operations, duplicate name prevention,
search, soft delete, staff count, and tenant isolation.

Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require `alembic upgrade head` on sims_plus_test.
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    clear_app_tenant_context,
)

from app.services.staff import DepartmentService, StaffServiceError


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("department_service"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def seed_department_via_admin(admin_session, tenant_id, name, code=None):
    """Insert a department directly via admin session. Returns dict with id, name."""
    dept_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO departments (
                id, tenant_id, name, code,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(dept_id),
            "tid": str(tenant_id),
            "name": name,
            "code": code,
        },
    )
    await admin_session.flush()
    return {"id": dept_id, "name": name, "tenant_id": tenant_id}


async def seed_staff_in_department(admin_session, tenant_id, department_id, email):
    """Insert a staff member linked to a department. Returns dict with id."""
    staff_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, staff_id, first_name, last_name,
                email, phone, gender, job_title, staff_type, status,
                employment_date, department_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
                :fn, :ln, :email, :phone,
                'male', 'Teacher', 'teaching', 'active',
                '2025-01-01', CAST(:did AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(staff_id),
            "tid": str(tenant_id),
            "sid": f"STF-{uuid4().hex[:6]}",
            "fn": "Test",
            "ln": "Staff",
            "email": email,
            "phone": "0241234567",
            "did": str(department_id),
        },
    )
    await admin_session.flush()
    return {"id": staff_id}


# ===========================================================================
# Department CRUD Tests
# ===========================================================================


class TestCreateDepartment:
    """Tests for DepartmentService.create_department."""

    async def test_create_department_success(self, app_session, admin_session):
        """Creating a department with valid data returns the record with tenant_id."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        dept = await service.create_department(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
            description="Mathematics department",
        )

        assert dept.name == "Mathematics"
        assert dept.code == "MATH"
        assert dept.description == "Mathematics department"
        assert dept.tenant_id == tenant["id"]

    async def test_create_duplicate_department_name_raises_error(self, app_session, admin_session):
        """Creating a department with an existing name raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        await service.create_department(
            tenant_id=tenant["id"],
            name="Science",
        )

        with pytest.raises(StaffServiceError) as exc_info:
            await service.create_department(
                tenant_id=tenant["id"],
                name="Science",
            )

        assert exc_info.value.code == "duplicate_department"

    async def test_same_department_name_different_tenants_ok(self, app_session, admin_session):
        """Two tenants can each have a department with the same name."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create "Science" for Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = DepartmentService(app_session)
        dept_a = await service.create_department(
            tenant_id=tenant_a["id"], name="Science"
        )
        assert dept_a.name == "Science"
        # Capture values before context switch to avoid MissingGreenlet
        dept_a_id = dept_a.id

        # Create "Science" for Tenant B -- should not raise
        await set_app_tenant_context(app_session, tenant_b["id"])
        service_b = DepartmentService(app_session)
        dept_b = await service_b.create_department(
            tenant_id=tenant_b["id"], name="Science"
        )
        assert dept_b.name == "Science"
        assert dept_a_id != dept_b.id


class TestGetDepartment:
    """Tests for DepartmentService.get_department."""

    async def test_get_department_by_id(self, app_session, admin_session):
        """Getting a department by ID with correct tenant returns the record."""
        tenant = await create_test_tenant(admin_session)
        dept_data = await seed_department_via_admin(
            admin_session, tenant["id"], "English", "ENG"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        dept = await service.get_department(tenant["id"], dept_data["id"])

        assert dept is not None
        assert dept.name == "English"
        assert dept.code == "ENG"

    async def test_get_department_wrong_tenant_returns_none(self, app_session, admin_session):
        """Getting a department by ID with wrong tenant returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        dept_a = await seed_department_via_admin(
            admin_session, tenant_a["id"], "History"
        )
        await admin_session.commit()

        # Capture ID before context switch
        dept_a_id = dept_a["id"]

        await set_app_tenant_context(app_session, tenant_b["id"])
        service = DepartmentService(app_session)

        dept = await service.get_department(tenant_b["id"], dept_a_id)
        assert dept is None


class TestListDepartments:
    """Tests for DepartmentService.list_departments."""

    async def test_list_departments_returns_tenant_data(self, app_session, admin_session):
        """Listing departments returns all departments for the tenant."""
        tenant = await create_test_tenant(admin_session)
        await seed_department_via_admin(admin_session, tenant["id"], "Alpha Dept")
        await seed_department_via_admin(admin_session, tenant["id"], "Beta Dept")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        departments = await service.list_departments(tenant["id"])

        assert len(departments) == 2
        names = [d.name for d in departments]
        assert "Alpha Dept" in names
        assert "Beta Dept" in names

    async def test_list_departments_search_by_name(self, app_session, admin_session):
        """Search parameter filters departments by name."""
        tenant = await create_test_tenant(admin_session)
        await seed_department_via_admin(admin_session, tenant["id"], "Mathematics")
        await seed_department_via_admin(admin_session, tenant["id"], "Physical Education")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        departments = await service.list_departments(tenant["id"], search="Math")

        assert len(departments) == 1
        assert departments[0].name == "Mathematics"

    async def test_list_departments_search_by_code(self, app_session, admin_session):
        """Search parameter filters departments by code."""
        tenant = await create_test_tenant(admin_session)
        await seed_department_via_admin(
            admin_session, tenant["id"], "Information Technology", "ICT"
        )
        await seed_department_via_admin(
            admin_session, tenant["id"], "Social Studies", "SOC"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        departments = await service.list_departments(tenant["id"], search="ICT")

        assert len(departments) == 1
        assert departments[0].code == "ICT"


class TestUpdateDepartment:
    """Tests for DepartmentService.update_department."""

    async def test_update_department_returns_updated_fields(self, app_session, admin_session):
        """Updating department fields returns the updated record."""
        tenant = await create_test_tenant(admin_session)
        dept_data = await seed_department_via_admin(
            admin_session, tenant["id"], "Old Name", "OLD"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        updated = await service.update_department(
            tenant["id"],
            dept_data["id"],
            name="New Name",
            code="NEW",
            description="Updated description",
        )

        assert updated is not None
        assert updated.name == "New Name"
        assert updated.code == "NEW"
        assert updated.description == "Updated description"

    async def test_update_department_duplicate_name_raises_error(self, app_session, admin_session):
        """Updating department name to an existing name raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        await seed_department_via_admin(admin_session, tenant["id"], "Existing")
        dept_b = await seed_department_via_admin(admin_session, tenant["id"], "To Rename")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        with pytest.raises(StaffServiceError) as exc_info:
            await service.update_department(
                tenant["id"], dept_b["id"], name="Existing"
            )

        assert exc_info.value.code == "duplicate_department"

    async def test_update_nonexistent_department_returns_none(self, app_session, admin_session):
        """Updating a non-existent department returns None."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        result = await service.update_department(
            tenant["id"], uuid4(), name="Ghost"
        )
        assert result is None

    async def test_set_department_head(self, app_session, admin_session):
        """Setting head_id on a department stores the staff reference."""
        tenant = await create_test_tenant(admin_session)
        dept_data = await seed_department_via_admin(
            admin_session, tenant["id"], "With Head"
        )
        # Create a staff member to be head -- use raw SQL via admin
        staff_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO staff (
                    id, tenant_id, staff_id, first_name, last_name,
                    email, phone, gender, job_title, staff_type, status,
                    employment_date, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
                    'Head', 'Person', 'head@test.com', '0241234567',
                    'male', 'Head of Department', 'teaching', 'active',
                    '2025-01-01', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(staff_id),
                "tid": str(tenant["id"]),
                "sid": f"STF-HEAD-{uuid4().hex[:4]}",
            },
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        updated = await service.update_department(
            tenant["id"], dept_data["id"], head_id=staff_id
        )

        assert updated is not None
        assert updated.head_id == staff_id


class TestDeleteDepartment:
    """Tests for DepartmentService.delete_department (soft delete)."""

    async def test_delete_department_soft_deletes(self, app_session, admin_session):
        """Deleting a department sets deleted_at (soft delete)."""
        tenant = await create_test_tenant(admin_session)
        dept_data = await seed_department_via_admin(
            admin_session, tenant["id"], "To Delete"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        result = await service.delete_department(tenant["id"], dept_data["id"])
        assert result is True

        # Department should no longer appear in get_department
        dept = await service.get_department(tenant["id"], dept_data["id"])
        assert dept is None

    async def test_delete_nonexistent_department_returns_false(self, app_session, admin_session):
        """Deleting a non-existent department returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        result = await service.delete_department(tenant["id"], uuid4())
        assert result is False


class TestDepartmentStaffCount:
    """Tests for DepartmentService.get_department_staff_count."""

    async def test_staff_count_returns_correct_number(self, app_session, admin_session):
        """Staff count returns the number of active staff in the department."""
        tenant = await create_test_tenant(admin_session)
        dept_data = await seed_department_via_admin(
            admin_session, tenant["id"], "Counting Dept"
        )
        await seed_staff_in_department(
            admin_session, tenant["id"], dept_data["id"], "count1@test.com"
        )
        await seed_staff_in_department(
            admin_session, tenant["id"], dept_data["id"], "count2@test.com"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        count = await service.get_department_staff_count(
            tenant["id"], dept_data["id"]
        )
        assert count == 2

    async def test_staff_count_empty_department(self, app_session, admin_session):
        """Staff count for an empty department returns 0."""
        tenant = await create_test_tenant(admin_session)
        dept_data = await seed_department_via_admin(
            admin_session, tenant["id"], "Empty Dept"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = DepartmentService(app_session)

        count = await service.get_department_staff_count(
            tenant["id"], dept_data["id"]
        )
        assert count == 0


# ===========================================================================
# Tenant Isolation Tests
# ===========================================================================


class TestDepartmentTenantIsolation:
    """Tenant A must NOT see Tenant B's departments. Non-negotiable."""

    async def test_list_departments_isolated_by_tenant(self, app_session, admin_session):
        """Listing departments for Tenant A does not include Tenant B's."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        await seed_department_via_admin(admin_session, tenant_a["id"], "Dept A")
        await seed_department_via_admin(admin_session, tenant_b["id"], "Dept B")
        await admin_session.commit()

        # Query as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = DepartmentService(app_session)

        departments = await service.list_departments(tenant_a["id"])

        names = [d.name for d in departments]
        assert "Dept A" in names, "Tenant A should see its own department"
        assert "Dept B" not in names, "Tenant A must NOT see Tenant B's department"

    async def test_get_department_isolated_by_tenant(self, app_session, admin_session):
        """Getting Tenant B's department from Tenant A's context returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        dept_b = await seed_department_via_admin(
            admin_session, tenant_b["id"], "Secret Dept"
        )
        await admin_session.commit()

        # Capture ID before context switch
        dept_b_id = dept_b["id"]

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = DepartmentService(app_session)

        dept = await service.get_department(tenant_a["id"], dept_b_id)
        assert dept is None, "Tenant A must NOT access Tenant B's department"

    async def test_rls_blocks_departments_without_context(self, app_session, admin_session):
        """Without tenant context, querying departments returns zero rows."""
        tenant = await create_test_tenant(admin_session)
        await seed_department_via_admin(admin_session, tenant["id"], "Invisible Dept")
        await admin_session.commit()

        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM departments"))
        assert result.scalar() == 0, "Without context, departments should return 0 rows"

    async def test_staff_count_isolated_by_tenant(self, app_session, admin_session):
        """Department staff count only counts staff from the current tenant."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        # Create department in A and B with same name (allowed, different tenants)
        dept_a = await seed_department_via_admin(
            admin_session, tenant_a["id"], "Shared Name Dept"
        )
        dept_b = await seed_department_via_admin(
            admin_session, tenant_b["id"], "Shared Name Dept"
        )

        # Add 2 staff to Tenant A's department, 3 to Tenant B's
        await seed_staff_in_department(
            admin_session, tenant_a["id"], dept_a["id"], "a-staff1@test.com"
        )
        await seed_staff_in_department(
            admin_session, tenant_a["id"], dept_a["id"], "a-staff2@test.com"
        )
        await seed_staff_in_department(
            admin_session, tenant_b["id"], dept_b["id"], "b-staff1@test.com"
        )
        await seed_staff_in_department(
            admin_session, tenant_b["id"], dept_b["id"], "b-staff2@test.com"
        )
        await seed_staff_in_department(
            admin_session, tenant_b["id"], dept_b["id"], "b-staff3@test.com"
        )
        await admin_session.commit()

        # Tenant A's department should count 2
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = DepartmentService(app_session)

        count_a = await service.get_department_staff_count(
            tenant_a["id"], dept_a["id"]
        )
        assert count_a == 2, "Tenant A department should have 2 staff"

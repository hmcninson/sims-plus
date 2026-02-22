"""
Staff Service Integration Tests

Tests for StaffService CRUD operations, search/filter, soft delete,
staff ID generation, class assignments, and tenant isolation.

Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require `alembic upgrade head` on sims_plus_test.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    clear_app_tenant_context,
)

from app.services.staff import StaffService, StaffServiceError


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("staff_service"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_test_school(admin_session, tenant_id):
    """Create a school under a tenant. Returns dict with id, name."""
    school_id = uuid4()
    slug = f"school-{uuid4().hex[:8]}"
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
            "tid": str(tenant_id),
            "name": "Test School",
            "slug": slug,
        },
    )
    await admin_session.flush()
    return {"id": school_id, "name": "Test School"}


async def seed_staff_via_admin(admin_session, tenant_id, staff_id_str, email, **overrides):
    """Insert a staff row directly via admin session (bypasses RLS).

    Returns dict with id, staff_id, email, tenant_id.
    """
    row_id = uuid4()
    params = {
        "id": str(row_id),
        "tid": str(tenant_id),
        "staff_id": staff_id_str,
        "first_name": overrides.get("first_name", "Kwame"),
        "last_name": overrides.get("last_name", "Asante"),
        "email": email,
        "phone": overrides.get("phone", "0241234567"),
        "gender": overrides.get("gender", "male"),
        "job_title": overrides.get("job_title", "Teacher"),
        "staff_type": overrides.get("staff_type", "teaching"),
        "status": overrides.get("status", "active"),
        "employment_date": overrides.get("employment_date", date(2025, 1, 15)),
    }

    await admin_session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, staff_id, first_name, last_name,
                email, phone, gender, job_title, staff_type, status,
                employment_date, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :staff_id,
                :first_name, :last_name, :email, :phone,
                :gender, :job_title, :staff_type, :status,
                CAST(:employment_date AS date),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        params,
    )
    await admin_session.flush()
    return {
        "id": row_id,
        "staff_id": staff_id_str,
        "email": email,
        "tenant_id": tenant_id,
    }


async def seed_class_and_section(admin_session, tenant_id):
    """Create a class + section via admin. Returns dict with class_id, section_id."""
    class_id = uuid4()
    section_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, sequence, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"JHS 1 {uuid4().hex[:4]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO class_sections (
                id, tenant_id, class_id, name, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), :name,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(section_id),
            "tid": str(tenant_id),
            "cid": str(class_id),
            "name": "A",
        },
    )
    await admin_session.flush()
    return {"class_id": class_id, "section_id": section_id}


# ===========================================================================
# Staff CRUD Tests
# ===========================================================================


class TestCreateStaff:
    """Tests for StaffService.create_staff."""

    async def test_create_staff_success(self, app_session, admin_session):
        """Creating staff with valid data returns the staff record."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff = await service.create_staff(
            tenant_id=tenant["id"],
            staff_id="STF-2026-001",
            first_name="Ama",
            last_name="Mensah",
            email="ama@school.edu.gh",
            phone="0241234567",
            gender="female",
            job_title="Mathematics Teacher",
            employment_date=date(2025, 9, 1),
        )

        assert staff.first_name == "Ama"
        assert staff.last_name == "Mensah"
        assert staff.staff_id == "STF-2026-001"
        assert staff.email == "ama@school.edu.gh"
        assert staff.tenant_id == tenant["id"]

    async def test_create_staff_duplicate_email_raises_error(self, app_session, admin_session):
        """Creating staff with an existing email raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        # First staff
        await service.create_staff(
            tenant_id=tenant["id"],
            staff_id="STF-2026-001",
            first_name="Ama",
            last_name="Mensah",
            email="duplicate@school.edu.gh",
            phone="0241234567",
            gender="female",
            job_title="Teacher",
            employment_date=date(2025, 9, 1),
        )

        # Second staff with same email
        with pytest.raises(StaffServiceError) as exc_info:
            await service.create_staff(
                tenant_id=tenant["id"],
                staff_id="STF-2026-002",
                first_name="Kofi",
                last_name="Boateng",
                email="duplicate@school.edu.gh",
                phone="0241234568",
                gender="male",
                job_title="Teacher",
                employment_date=date(2025, 9, 1),
            )

        assert exc_info.value.code == "duplicate_staff_email"

    async def test_create_staff_duplicate_staff_id_raises_error(self, app_session, admin_session):
        """Creating staff with an existing staff_id raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        await service.create_staff(
            tenant_id=tenant["id"],
            staff_id="STF-2026-DUP",
            first_name="Ama",
            last_name="Mensah",
            email="first@school.edu.gh",
            phone="0241234567",
            gender="female",
            job_title="Teacher",
            employment_date=date(2025, 9, 1),
        )

        with pytest.raises(StaffServiceError) as exc_info:
            await service.create_staff(
                tenant_id=tenant["id"],
                staff_id="STF-2026-DUP",
                first_name="Kofi",
                last_name="Boateng",
                email="second@school.edu.gh",
                phone="0241234568",
                gender="male",
                job_title="Teacher",
                employment_date=date(2025, 9, 1),
            )

        assert exc_info.value.code == "duplicate_staff_id"


class TestGetStaff:
    """Tests for StaffService.get_staff and get_staff_by_staff_id."""

    async def test_get_staff_by_id_returns_staff(self, app_session, admin_session):
        """Getting staff by UUID with correct tenant_id returns the record."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-GET-001", "get@school.edu.gh"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff = await service.get_staff(tenant["id"], staff_data["id"])

        assert staff is not None
        assert staff.email == "get@school.edu.gh"

    async def test_get_staff_wrong_tenant_returns_none(self, app_session, admin_session):
        """Getting staff by ID with the wrong tenant_id returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        staff_a = await seed_staff_via_admin(
            admin_session, tenant_a["id"], "STF-A-001", "staff-a@test.com"
        )
        await admin_session.commit()

        # Set context to tenant B, try to get tenant A's staff
        await set_app_tenant_context(app_session, tenant_b["id"])
        service = StaffService(app_session)

        staff = await service.get_staff(tenant_b["id"], staff_a["id"])
        assert staff is None

    async def test_get_staff_by_staff_id_string(self, app_session, admin_session):
        """Getting staff by the school-assigned staff_id string works."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-FIND-001", "find@school.edu.gh"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff = await service.get_staff_by_staff_id(tenant["id"], "STF-FIND-001")

        assert staff is not None
        assert staff.email == "find@school.edu.gh"


class TestListStaff:
    """Tests for StaffService.list_staff with filters."""

    async def test_list_staff_returns_tenant_data(self, app_session, admin_session):
        """Listing staff returns all active staff for the tenant."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-L-001", "list1@test.com",
            first_name="Alpha"
        )
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-L-002", "list2@test.com",
            first_name="Beta"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff_list, total = await service.list_staff(tenant["id"])

        assert total == 2
        assert len(staff_list) == 2

    async def test_list_staff_search_filters_by_name(self, app_session, admin_session):
        """Search parameter filters staff by first/last name."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-S-001", "search1@test.com",
            first_name="Kwabena"
        )
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-S-002", "search2@test.com",
            first_name="Adjoa"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff_list, total = await service.list_staff(tenant["id"], search="Kwabena")

        assert total == 1
        assert staff_list[0].first_name == "Kwabena"

    async def test_list_staff_filter_by_staff_type(self, app_session, admin_session):
        """Filtering by staff_type returns only matching staff."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-T-001", "teaching@test.com",
            staff_type="teaching"
        )
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-T-002", "admin@test.com",
            staff_type="administrative"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff_list, total = await service.list_staff(
            tenant["id"], staff_type="teaching"
        )

        assert total == 1
        assert staff_list[0].email == "teaching@test.com"

    async def test_list_staff_filter_by_status(self, app_session, admin_session):
        """Filtering by status returns only matching staff."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-ST-001", "active@test.com",
            status="active"
        )
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-ST-002", "leave@test.com",
            status="on_leave"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff_list, total = await service.list_staff(
            tenant["id"], status="on_leave"
        )

        assert total == 1
        assert staff_list[0].email == "leave@test.com"


class TestUpdateStaff:
    """Tests for StaffService.update_staff."""

    async def test_update_staff_returns_updated_fields(self, app_session, admin_session):
        """Updating staff fields returns the updated record."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-U-001", "update@test.com",
            job_title="Teacher"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        updated = await service.update_staff(
            tenant["id"],
            staff_data["id"],
            job_title="Senior Teacher",
            phone="0501234567",
        )

        assert updated is not None
        assert updated.job_title == "Senior Teacher"
        assert updated.phone == "0501234567"

    async def test_update_nonexistent_staff_returns_none(self, app_session, admin_session):
        """Updating a non-existent staff ID returns None."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        result = await service.update_staff(
            tenant["id"], uuid4(), job_title="Ghost"
        )
        assert result is None


class TestDeleteStaff:
    """Tests for StaffService.delete_staff (soft delete)."""

    async def test_delete_staff_soft_deletes(self, app_session, admin_session):
        """Deleting staff sets deleted_at (soft delete), not a hard delete."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-D-001", "delete@test.com"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        result = await service.delete_staff(tenant["id"], staff_data["id"])
        assert result is True

        # Staff should no longer be returned by get_staff (filters deleted_at)
        staff = await service.get_staff(tenant["id"], staff_data["id"])
        assert staff is None

    async def test_delete_nonexistent_staff_returns_false(self, app_session, admin_session):
        """Deleting a non-existent staff returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        result = await service.delete_staff(tenant["id"], uuid4())
        assert result is False


class TestGenerateStaffId:
    """Tests for StaffService.generate_staff_id."""

    async def test_generate_staff_id_format(self, app_session, admin_session):
        """Generated staff ID follows PREFIX-YEAR-SEQUENCE format."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        staff_id = await service.generate_staff_id(tenant["id"], prefix="STF")

        # Should match STF-YYYY-001
        parts = staff_id.split("-")
        assert parts[0] == "STF"
        assert len(parts) == 3
        assert parts[2] == "001"

    async def test_generate_staff_id_increments(self, app_session, admin_session):
        """Sequential calls generate incrementing IDs."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        # Create a staff with the first generated ID to advance the sequence
        first_id = await service.generate_staff_id(tenant["id"])
        await service.create_staff(
            tenant_id=tenant["id"],
            staff_id=first_id,
            first_name="First",
            last_name="Staff",
            email="gen1@test.com",
            phone="0241234567",
            gender="male",
            job_title="Teacher",
            employment_date=date(2025, 1, 1),
        )

        second_id = await service.generate_staff_id(tenant["id"])
        assert second_id.endswith("-002")


class TestStaffStats:
    """Tests for StaffService.get_staff_stats."""

    async def test_stats_reflect_staff_counts(self, app_session, admin_session):
        """Stats correctly count staff by status, type, and gender."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-STAT-001", "stat1@test.com",
            gender="male", staff_type="teaching", status="active"
        )
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-STAT-002", "stat2@test.com",
            gender="female", staff_type="administrative", status="on_leave"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        stats = await service.get_staff_stats(tenant["id"])

        assert stats["total"] == 2
        assert stats["active"] == 1
        assert stats["on_leave"] == 1
        assert stats["teaching"] == 1
        assert stats["administrative"] == 1
        assert stats["male"] == 1
        assert stats["female"] == 1


# ===========================================================================
# Staff Class Assignment Tests
# ===========================================================================


class TestStaffClassAssignment:
    """Tests for staff-to-section assignment operations."""

    async def test_assign_staff_to_section(self, app_session, admin_session):
        """Assigning staff to a section creates the assignment record."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-ASN-001", "assign@test.com"
        )
        class_data = await seed_class_and_section(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        assignment = await service.assign_staff_to_section(
            tenant_id=tenant["id"],
            staff_id=staff_data["id"],
            section_id=class_data["section_id"],
        )

        assert assignment is not None
        assert assignment.staff_id == staff_data["id"]
        assert assignment.section_id == class_data["section_id"]
        assert assignment.is_class_teacher is False

    async def test_assign_staff_as_class_teacher(self, app_session, admin_session):
        """Assigning staff with is_class_teacher=True sets the flag."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-CT-001", "classteacher@test.com"
        )
        class_data = await seed_class_and_section(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        assignment = await service.assign_staff_to_section(
            tenant_id=tenant["id"],
            staff_id=staff_data["id"],
            section_id=class_data["section_id"],
            is_class_teacher=True,
        )

        assert assignment.is_class_teacher is True

        # Verify get_class_teacher returns this staff
        class_teacher = await service.get_class_teacher(
            tenant["id"], class_data["section_id"]
        )
        assert class_teacher is not None
        assert class_teacher.id == staff_data["id"]

    async def test_duplicate_assignment_raises_error(self, app_session, admin_session):
        """Assigning same staff to same section twice raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-DUP-001", "dup-assign@test.com"
        )
        class_data = await seed_class_and_section(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        await service.assign_staff_to_section(
            tenant_id=tenant["id"],
            staff_id=staff_data["id"],
            section_id=class_data["section_id"],
        )

        with pytest.raises(StaffServiceError) as exc_info:
            await service.assign_staff_to_section(
                tenant_id=tenant["id"],
                staff_id=staff_data["id"],
                section_id=class_data["section_id"],
            )

        assert exc_info.value.code == "duplicate_assignment"

    async def test_assign_nonexistent_staff_raises_error(self, app_session, admin_session):
        """Assigning a non-existent staff to a section raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        class_data = await seed_class_and_section(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        with pytest.raises(StaffServiceError) as exc_info:
            await service.assign_staff_to_section(
                tenant_id=tenant["id"],
                staff_id=uuid4(),
                section_id=class_data["section_id"],
            )

        assert exc_info.value.code == "staff_not_found"

    async def test_assign_to_nonexistent_section_raises_error(self, app_session, admin_session):
        """Assigning staff to a non-existent section raises StaffServiceError."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-NS-001", "no-section@test.com"
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        with pytest.raises(StaffServiceError) as exc_info:
            await service.assign_staff_to_section(
                tenant_id=tenant["id"],
                staff_id=staff_data["id"],
                section_id=uuid4(),
            )

        assert exc_info.value.code == "section_not_found"

    async def test_remove_staff_from_section(self, app_session, admin_session):
        """Removing an assignment returns True and the assignment is gone."""
        tenant = await create_test_tenant(admin_session)
        staff_data = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-RM-001", "remove@test.com"
        )
        class_data = await seed_class_and_section(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        await service.assign_staff_to_section(
            tenant_id=tenant["id"],
            staff_id=staff_data["id"],
            section_id=class_data["section_id"],
        )

        removed = await service.remove_staff_from_section(
            tenant["id"], staff_data["id"], class_data["section_id"]
        )
        assert removed is True

        # Verify assignment is gone
        assignments = await service.get_staff_assignments(
            tenant["id"], staff_data["id"]
        )
        assert len(assignments) == 0

    async def test_new_class_teacher_unsets_previous(self, app_session, admin_session):
        """Setting a new class teacher unsets the previous one for that section."""
        tenant = await create_test_tenant(admin_session)
        staff_a = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-CTA-001", "ct-a@test.com"
        )
        staff_b = await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-CTB-001", "ct-b@test.com"
        )
        class_data = await seed_class_and_section(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StaffService(app_session)

        # Assign staff A as class teacher
        await service.assign_staff_to_section(
            tenant_id=tenant["id"],
            staff_id=staff_a["id"],
            section_id=class_data["section_id"],
            is_class_teacher=True,
        )

        # Assign staff B as class teacher for the same section
        await service.assign_staff_to_section(
            tenant_id=tenant["id"],
            staff_id=staff_b["id"],
            section_id=class_data["section_id"],
            is_class_teacher=True,
        )

        # The class teacher should now be staff B
        class_teacher = await service.get_class_teacher(
            tenant["id"], class_data["section_id"]
        )
        assert class_teacher is not None
        assert class_teacher.id == staff_b["id"]


# ===========================================================================
# Tenant Isolation Tests
# ===========================================================================


class TestStaffTenantIsolation:
    """Tenant A must NOT see Tenant B's staff. This is non-negotiable."""

    async def test_list_staff_isolated_by_tenant(self, app_session, admin_session):
        """Listing staff for Tenant A does not include Tenant B's staff."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        staff_a = await seed_staff_via_admin(
            admin_session, tenant_a["id"], "STF-ISO-A", "iso-a@test.com",
            first_name="TenantA"
        )
        staff_b = await seed_staff_via_admin(
            admin_session, tenant_b["id"], "STF-ISO-B", "iso-b@test.com",
            first_name="TenantB"
        )
        await admin_session.commit()

        # Capture IDs before any context switch
        staff_a_id = staff_a["id"]
        staff_b_email = staff_b["email"]

        # Query as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StaffService(app_session)

        staff_list, total = await service.list_staff(tenant_a["id"])

        emails = [s.email for s in staff_list]
        assert staff_a["email"] in emails, "Tenant A should see its own staff"
        assert staff_b_email not in emails, "Tenant A must NOT see Tenant B's staff"

    async def test_get_staff_by_id_isolated(self, app_session, admin_session):
        """Getting Tenant B's staff by UUID from Tenant A returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        staff_b = await seed_staff_via_admin(
            admin_session, tenant_b["id"], "STF-ISO-B2", "iso-b2@test.com"
        )
        await admin_session.commit()

        # Capture ID before context switch
        staff_b_id = staff_b["id"]

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StaffService(app_session)

        # Try to get Tenant B's staff using Tenant A's context
        staff = await service.get_staff(tenant_a["id"], staff_b_id)
        assert staff is None, "Tenant A must NOT access Tenant B's staff by ID"

    async def test_rls_blocks_staff_without_context(self, app_session, admin_session):
        """Without tenant context, querying staff returns zero rows."""
        tenant = await create_test_tenant(admin_session)
        await seed_staff_via_admin(
            admin_session, tenant["id"], "STF-CTX-001", "ctx@test.com"
        )
        await admin_session.commit()

        await clear_app_tenant_context(app_session)
        result = await app_session.execute(text("SELECT count(*) FROM staff"))
        assert result.scalar() == 0, "Without context, staff table should return 0 rows"

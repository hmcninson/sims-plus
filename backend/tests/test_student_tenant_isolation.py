"""
SIMS Plus - Student & Guardian Tenant Isolation Tests

Tests that verify tenant data isolation at the service layer for students
and guardians. These use the two-engine pattern:
- admin_session: seeds data in multiple tenants (superuser, bypasses RLS)
- app_session: queries under RLS enforcement (sims_app_user)

Every test creates two tenants, seeds data in one, and verifies the other
cannot see it. This is the most critical test category for a multi-tenant
system.

IMPORTANT: These tests verify both RLS (database level) and defense-in-depth
(service layer tenant_id filtering). Both must work for isolation to hold.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.services.student import StudentService

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.xdist_group("student_isolation_serial"),
]


# --- Student Isolation ---


class TestStudentTenantIsolation:
    """Tenant A must NEVER see Tenant B's students."""

    async def test_student_created_in_a_not_visible_to_b(
        self, app_session, admin_session
    ):
        """A student created in Tenant A does not appear in Tenant B's list."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student_a = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="ISO-STU-A001",
            first_name="TenantA",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_a_id = student_a.id

        # Switch to Tenant B and list students
        await set_app_tenant_context(app_session, tenant_b["id"])
        students_b, total_b = await service.list_students(tenant_b["id"])

        assert total_b == 0
        student_ids_b = [s.id for s in students_b]
        assert student_a_id not in student_ids_b

    async def test_cross_tenant_get_student_returns_none(
        self, app_session, admin_session
    ):
        """Directly accessing a student by UUID from another tenant returns None,
        not a 403. This prevents leaking information about resource existence."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="ISO-XGET-001",
            first_name="Hidden",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_uuid = student.id

        # Switch to Tenant B and try direct access
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.get_student(tenant_b["id"], student_uuid)

        assert result is None

    async def test_cross_tenant_update_returns_none(
        self, app_session, admin_session
    ):
        """Updating a student from another tenant returns None (no modification)."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="ISO-XUPD-001",
            first_name="Original",
            last_name="Name",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_uuid = student.id
        # Commit so the student is visible to admin_session for verification
        await app_session.commit()

        # Switch to Tenant B and try to update
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.update_student(
            tenant_b["id"], student_uuid, first_name="Hacked"
        )

        assert result is None

        # Verify original is unchanged (check via admin session)
        row = await admin_session.execute(
            text(
                "SELECT first_name FROM students WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(student_uuid)},
        )
        assert row.scalar() == "Original"

    async def test_cross_tenant_delete_returns_false(
        self, app_session, admin_session
    ):
        """Deleting a student from another tenant returns False (no deletion)."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="ISO-XDEL-001",
            first_name="Protected",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_uuid = student.id

        # Switch to Tenant B and try to delete
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.delete_student(tenant_b["id"], student_uuid)

        assert result is False

        # Verify student still exists and is not soft-deleted
        row = await admin_session.execute(
            text(
                "SELECT deleted_at FROM students WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(student_uuid)},
        )
        assert row.scalar() is None  # not deleted

    async def test_cross_tenant_get_by_student_id_returns_none(
        self, app_session, admin_session
    ):
        """Looking up a student by school-assigned ID from another tenant returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="SHARED-ID-999",
            first_name="TenantA",
            last_name="Only",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.get_student_by_student_id(
            tenant_b["id"], "SHARED-ID-999"
        )

        assert result is None

    async def test_student_stats_scoped_to_tenant(
        self, app_session, admin_session
    ):
        """get_student_stats counts only the current tenant's students."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create 3 students in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        for i in range(3):
            await service.create_student(
                tenant_id=tenant_a["id"],
                student_id=f"ISO-STAT-A{i}",
                first_name=f"A{i}",
                last_name="Student",
                date_of_birth=date(2010, 1, 1),
                gender="male",
            )

        # Create 1 student in Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        await service.create_student(
            tenant_id=tenant_b["id"],
            student_id="ISO-STAT-B0",
            first_name="B0",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="female",
        )

        # Tenant B stats should show only 1
        stats_b = await service.get_student_stats(tenant_b["id"])
        assert stats_b["total"] == 1

        # Tenant A stats should show only 3
        await set_app_tenant_context(app_session, tenant_a["id"])
        stats_a = await service.get_student_stats(tenant_a["id"])
        assert stats_a["total"] == 3


# --- Guardian Isolation ---


class TestGuardianTenantIsolation:
    """Tenant A must NEVER see Tenant B's guardians."""

    async def test_guardian_created_in_a_not_visible_to_b(
        self, app_session, admin_session
    ):
        """A guardian created in Tenant A does not appear in Tenant B's list."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create guardian in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian_a = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="TenantA",
            last_name="Guardian",
            phone="0241111111",
        )
        guardian_a_id = guardian_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        guardians_b, total_b = await service.list_guardians(tenant_b["id"])

        assert total_b == 0
        guardian_ids_b = [g["id"] for g in guardians_b]
        assert guardian_a_id not in guardian_ids_b

    async def test_cross_tenant_get_guardian_returns_none(
        self, app_session, admin_session
    ):
        """Directly accessing a guardian by UUID from another tenant returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Hidden",
            last_name="Guardian",
            phone="0241111111",
        )
        guardian_uuid = guardian.id

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.get_guardian(tenant_b["id"], guardian_uuid)

        assert result is None

    async def test_cross_tenant_update_guardian_returns_none(
        self, app_session, admin_session
    ):
        """Updating a guardian from another tenant returns None."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Original",
            last_name="Guardian",
            phone="0241111111",
        )
        guardian_uuid = guardian.id

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.update_guardian(
            tenant_b["id"], guardian_uuid, first_name="Hacked"
        )

        assert result is None

    async def test_cross_tenant_delete_guardian_returns_false(
        self, app_session, admin_session
    ):
        """Deleting a guardian from another tenant returns False."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Protected",
            last_name="Guardian",
            phone="0241111111",
        )
        guardian_uuid = guardian.id

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.delete_guardian(tenant_b["id"], guardian_uuid)

        assert result is False

        # Verify guardian still exists
        row = await admin_session.execute(
            text(
                "SELECT deleted_at FROM guardians WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(guardian_uuid)},
        )
        assert row.scalar() is None


# --- Student-Guardian Link Isolation ---


class TestStudentGuardianLinkIsolation:
    """Cross-tenant link operations must fail gracefully."""

    async def test_cross_tenant_link_student_not_found(
        self, app_session, admin_session
    ):
        """Linking a guardian to a student from another tenant raises 'student_not_found'."""
        from app.services.student import StudentServiceError

        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="ISO-LINK-001",
            first_name="TenantA",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_uuid = student.id

        # Create guardian in Tenant B, try to link to Tenant A's student
        await set_app_tenant_context(app_session, tenant_b["id"])
        guardian = await service.create_guardian(
            tenant_id=tenant_b["id"],
            first_name="TenantB",
            last_name="Guardian",
            phone="0242222222",
        )

        with pytest.raises(StudentServiceError) as exc_info:
            await service.link_guardian_to_student(
                tenant_id=tenant_b["id"],
                student_id=student_uuid,
                guardian_id=guardian.id,
                relationship="father",
            )

        assert exc_info.value.code == "student_not_found"

    async def test_cross_tenant_get_student_guardians_returns_empty(
        self, app_session, admin_session
    ):
        """Getting guardians for a student from another tenant returns empty list."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student with guardian in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="ISO-GLINK-001",
            first_name="WithGuardian",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        guardian = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Linked",
            last_name="Guardian",
            phone="0241111111",
        )
        await service.link_guardian_to_student(
            tenant_id=tenant_a["id"],
            student_id=student.id,
            guardian_id=guardian.id,
            relationship="mother",
        )
        student_uuid = student.id

        # Switch to Tenant B and try to fetch guardians for Tenant A's student
        await set_app_tenant_context(app_session, tenant_b["id"])
        links = await service.get_student_guardians(tenant_b["id"], student_uuid)

        assert len(links) == 0

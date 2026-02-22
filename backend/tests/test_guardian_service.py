"""
SIMS Plus - Guardian Service Integration Tests

Tests exercise the StudentService guardian methods directly against a real
PostgreSQL database with RLS enforced via the two-engine pattern.

Covers:
- Guardian CRUD (create, get, list, update, delete)
- Student-guardian linking and unlinking
- Primary guardian management
- Duplicate email detection
- Delete protection when guardian has linked students
- Soft delete behavior
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.services.student import StudentService, StudentServiceError

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
]


# --- Helpers ---

async def _create_student(service, tenant_id, suffix="001"):
    """Create a minimal student for linking tests."""
    return await service.create_student(
        tenant_id=tenant_id,
        student_id=f"STU-GRD-{suffix}-{uuid4().hex[:4]}",
        first_name=f"Student{suffix}",
        last_name="Test",
        date_of_birth=date(2010, 1, 1),
        gender="male",
    )


# --- Guardian Creation ---


class TestGuardianCreation:
    """Tests for StudentService.create_guardian."""

    async def test_create_guardian_with_required_fields(
        self, app_session, admin_session
    ):
        """Creating a guardian with required fields returns a Guardian with tenant_id."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Kofi",
            last_name="Mensah",
            phone="0241234567",
        )

        assert guardian.id is not None
        assert guardian.first_name == "Kofi"
        assert guardian.last_name == "Mensah"
        assert guardian.phone == "0241234567"
        assert guardian.tenant_id == tenant["id"]
        assert guardian.deleted_at is None

    async def test_create_guardian_with_all_fields(
        self, app_session, admin_session
    ):
        """Optional fields (email, address, occupation, etc.) are stored correctly."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Ama",
            last_name="Boateng",
            phone="0201234567",
            phone_secondary="0551234567",
            email="ama.boateng@test.com",
            address="15 Independence Ave",
            city="Accra",
            region="Greater Accra",
            occupation="Doctor",
            workplace="Korle-Bu Hospital",
            work_phone="0302345678",
            ghana_card_number="GHA-123456789",
            notes="Primary guardian for Kwame",
        )

        assert guardian.email == "ama.boateng@test.com"
        assert guardian.phone_secondary == "0551234567"
        assert guardian.occupation == "Doctor"
        assert guardian.workplace == "Korle-Bu Hospital"
        assert guardian.ghana_card_number == "GHA-123456789"

    async def test_create_guardian_duplicate_email_raises_error(
        self, app_session, admin_session
    ):
        """Creating two guardians with the same email in one tenant raises an error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="First",
            last_name="Guardian",
            phone="0241111111",
            email="duplicate@test.com",
        )

        with pytest.raises(StudentServiceError) as exc_info:
            await service.create_guardian(
                tenant_id=tenant["id"],
                first_name="Second",
                last_name="Guardian",
                phone="0242222222",
                email="duplicate@test.com",
            )

        assert exc_info.value.code == "duplicate_guardian_email"

    async def test_create_guardian_same_email_different_tenants_allowed(
        self, app_session, admin_session
    ):
        """The same guardian email can exist in different tenants."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian_a = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Tenant", last_name="A",
            phone="0241111111", email="shared@test.com",
        )
        # Capture values before context switch to avoid MissingGreenlet
        guardian_a_email = guardian_a.email
        guardian_a_tid = guardian_a.tenant_id

        await set_app_tenant_context(app_session, tenant_b["id"])
        guardian_b = await service.create_guardian(
            tenant_id=tenant_b["id"],
            first_name="Tenant", last_name="B",
            phone="0242222222", email="shared@test.com",
        )

        assert guardian_a_email == guardian_b.email
        assert guardian_a_tid != guardian_b.tenant_id

    async def test_create_guardian_without_email_no_duplicate_check(
        self, app_session, admin_session
    ):
        """Guardians without email can be created freely (no duplicate check)."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        g1 = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="No", last_name="Email1", phone="0241111111",
        )
        g2 = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="No", last_name="Email2", phone="0242222222",
        )

        assert g1.id != g2.id
        assert g1.email is None
        assert g2.email is None


# --- Guardian Retrieval ---


class TestGuardianRetrieval:
    """Tests for StudentService.get_guardian and list_guardians."""

    async def test_get_guardian_by_id(self, app_session, admin_session):
        """get_guardian returns the correct guardian for the tenant."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        created = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Yaw", last_name="Darko", phone="0241234567",
        )

        fetched = await service.get_guardian(tenant["id"], created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.first_name == "Yaw"

    async def test_get_guardian_wrong_tenant_returns_none(
        self, app_session, admin_session
    ):
        """get_guardian returns None when tenant_id does not match."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Secret", last_name="Guardian", phone="0241111111",
        )
        guardian_id = guardian.id

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.get_guardian(tenant_b["id"], guardian_id)
        assert result is None

    async def test_list_guardians_returns_all_for_tenant(
        self, app_session, admin_session
    ):
        """list_guardians returns all non-deleted guardians with student counts."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Guardian1", last_name="Test", phone="0241111111",
        )
        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Guardian2", last_name="Test", phone="0242222222",
        )

        guardians, total = await service.list_guardians(tenant["id"])

        assert total == 2
        assert len(guardians) == 2
        # list_guardians returns dicts with student_count
        assert "student_count" in guardians[0]

    async def test_list_guardians_search_by_name(self, app_session, admin_session):
        """list_guardians with search filters by name."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Kwame", last_name="Asante", phone="0241111111",
        )
        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Ama", last_name="Owusu", phone="0242222222",
        )

        guardians, total = await service.list_guardians(
            tenant["id"], search="Kwame"
        )
        assert total == 1
        assert guardians[0]["first_name"] == "Kwame"

    async def test_list_guardians_search_by_phone(self, app_session, admin_session):
        """list_guardians search also matches on phone number."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Phone", last_name="Match", phone="0559998877",
        )
        await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Other", last_name="Guardian", phone="0241111111",
        )

        guardians, total = await service.list_guardians(
            tenant["id"], search="0559998877"
        )
        assert total == 1
        assert guardians[0]["phone"] == "0559998877"


# --- Guardian Update ---


class TestGuardianUpdate:
    """Tests for StudentService.update_guardian."""

    async def test_update_guardian_changes_fields(self, app_session, admin_session):
        """update_guardian modifies specified fields."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Original", last_name="Name",
            phone="0241234567",
        )

        updated = await service.update_guardian(
            tenant["id"], guardian.id,
            first_name="Updated",
            occupation="Engineer",
        )

        assert updated is not None
        assert updated.first_name == "Updated"
        assert updated.occupation == "Engineer"
        assert updated.last_name == "Name"  # unchanged

    async def test_update_guardian_wrong_tenant_returns_none(
        self, app_session, admin_session
    ):
        """update_guardian returns None when tenant_id does not match."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant_a["id"],
            first_name="Protected", last_name="Guardian", phone="0241111111",
        )
        guardian_id = guardian.id

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.update_guardian(
            tenant_b["id"], guardian_id, first_name="Hacked"
        )
        assert result is None


# --- Guardian Deletion ---


class TestGuardianDeletion:
    """Tests for StudentService.delete_guardian (soft delete with link protection)."""

    async def test_delete_guardian_no_links_soft_deletes(
        self, app_session, admin_session
    ):
        """Deleting a guardian with no linked students sets deleted_at."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Unlinked", last_name="Guardian", phone="0241111111",
        )

        result = await service.delete_guardian(tenant["id"], guardian.id)
        assert result is True

        # Verify soft delete in DB (use app_session, same connection as the delete)
        row = await app_session.execute(
            text("SELECT deleted_at FROM guardians WHERE id = CAST(:id AS uuid)"),
            {"id": str(guardian.id)},
        )
        db_row = row.fetchone()
        assert db_row is not None
        assert db_row.deleted_at is not None

    async def test_delete_guardian_with_linked_students_raises_error(
        self, app_session, admin_session
    ):
        """Deleting a guardian that has linked students raises an error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Linked", last_name="Guardian", phone="0241111111",
        )
        student = await _create_student(service, tenant["id"])

        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id,
            guardian_id=guardian.id,
            relationship="father",
        )

        with pytest.raises(StudentServiceError) as exc_info:
            await service.delete_guardian(tenant["id"], guardian.id)

        assert exc_info.value.code == "guardian_has_linked_students"

    async def test_deleted_guardian_excluded_from_get(
        self, app_session, admin_session
    ):
        """get_guardian returns None for a soft-deleted guardian."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Gone", last_name="Guardian", phone="0241111111",
        )
        guardian_id = guardian.id

        await service.delete_guardian(tenant["id"], guardian_id)
        app_session.expire_all()

        result = await service.get_guardian(tenant["id"], guardian_id)
        assert result is None

    async def test_deleted_guardian_excluded_from_list(
        self, app_session, admin_session
    ):
        """list_guardians does not include soft-deleted guardians."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        keep = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Keeper", last_name="Guardian", phone="0241111111",
        )
        to_delete = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Deleter", last_name="Guardian", phone="0242222222",
        )

        await service.delete_guardian(tenant["id"], to_delete.id)
        app_session.expire_all()

        guardians, total = await service.list_guardians(tenant["id"])
        assert total == 1
        assert guardians[0]["id"] == keep.id


# --- Student-Guardian Links ---


class TestStudentGuardianLinks:
    """Tests for linking/unlinking guardians to students."""

    async def test_link_guardian_to_student(self, app_session, admin_session):
        """link_guardian_to_student creates a StudentGuardian junction record."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Parent", last_name="Test", phone="0241234567",
        )

        link = await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id,
            guardian_id=guardian.id,
            relationship="father",
        )

        assert link.id is not None
        assert link.student_id == student.id
        assert link.guardian_id == guardian.id
        assert link.relation_type.value == "father"
        assert link.is_emergency_contact is True  # default
        assert link.can_pickup is True  # default

    async def test_link_guardian_with_is_primary(self, app_session, admin_session):
        """Setting is_primary=True marks the link as primary."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Primary", last_name="Guardian", phone="0241234567",
        )

        link = await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id,
            guardian_id=guardian.id,
            relationship="mother",
            is_primary=True,
        )

        assert link.is_primary is True

    async def test_link_guardian_primary_unsets_previous_primary(
        self, app_session, admin_session
    ):
        """Setting a new primary guardian unsets the previous primary."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        guardian_a = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="First", last_name="Primary", phone="0241111111",
        )
        guardian_b = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Second", last_name="Primary", phone="0242222222",
        )

        # Capture scalar IDs before any expire_all() invalidates ORM state
        student_id = student.id
        guardian_a_id = guardian_a.id
        guardian_b_id = guardian_b.id

        # Link first as primary
        link_a = await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student_id,
            guardian_id=guardian_a_id,
            relationship="father",
            is_primary=True,
        )
        assert link_a.is_primary is True

        # Link second as primary -- should unset first
        link_b = await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student_id,
            guardian_id=guardian_b_id,
            relationship="mother",
            is_primary=True,
        )
        assert link_b.is_primary is True

        # Refresh link_a -- should no longer be primary
        app_session.expire_all()
        links = await service.get_student_guardians(tenant["id"], student_id)
        primaries = [lnk for lnk in links if lnk.is_primary]
        assert len(primaries) == 1
        assert primaries[0].guardian_id == guardian_b_id

    async def test_link_duplicate_raises_error(self, app_session, admin_session):
        """Linking the same guardian to the same student twice raises an error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Dup", last_name="Link", phone="0241234567",
        )

        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id,
            guardian_id=guardian.id,
            relationship="father",
        )

        with pytest.raises(StudentServiceError) as exc_info:
            await service.link_guardian_to_student(
                tenant_id=tenant["id"],
                student_id=student.id,
                guardian_id=guardian.id,
                relationship="guardian",
            )

        assert exc_info.value.code == "duplicate_link"

    async def test_link_nonexistent_student_raises_error(
        self, app_session, admin_session
    ):
        """Linking to a nonexistent student raises 'student_not_found'."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Orphan", last_name="Link", phone="0241234567",
        )

        with pytest.raises(StudentServiceError) as exc_info:
            await service.link_guardian_to_student(
                tenant_id=tenant["id"],
                student_id=uuid4(),
                guardian_id=guardian.id,
                relationship="father",
            )

        assert exc_info.value.code == "student_not_found"

    async def test_link_nonexistent_guardian_raises_error(
        self, app_session, admin_session
    ):
        """Linking a nonexistent guardian raises 'guardian_not_found'."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])

        with pytest.raises(StudentServiceError) as exc_info:
            await service.link_guardian_to_student(
                tenant_id=tenant["id"],
                student_id=student.id,
                guardian_id=uuid4(),
                relationship="father",
            )

        assert exc_info.value.code == "guardian_not_found"

    async def test_get_student_guardians(self, app_session, admin_session):
        """get_student_guardians returns all linked guardians for a student."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        g1 = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Father", last_name="Test", phone="0241111111",
        )
        g2 = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Mother", last_name="Test", phone="0242222222",
        )

        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id, guardian_id=g1.id,
            relationship="father",
        )
        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id, guardian_id=g2.id,
            relationship="mother",
        )

        links = await service.get_student_guardians(tenant["id"], student.id)
        assert len(links) == 2
        guardian_ids = {lnk.guardian_id for lnk in links}
        assert g1.id in guardian_ids
        assert g2.id in guardian_ids

    async def test_unlink_guardian_from_student(self, app_session, admin_session):
        """unlink_guardian_from_student removes the junction record (hard delete)."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Unlink", last_name="Test", phone="0241234567",
        )

        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id, guardian_id=guardian.id,
            relationship="father",
        )

        result = await service.unlink_guardian_from_student(
            tenant["id"], student.id, guardian.id
        )
        assert result is True

        # Verify link is gone
        links = await service.get_student_guardians(tenant["id"], student.id)
        assert len(links) == 0

    async def test_unlink_nonexistent_link_returns_false(
        self, app_session, admin_session
    ):
        """unlink_guardian_from_student returns False when no link exists."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.unlink_guardian_from_student(
            tenant["id"], uuid4(), uuid4()
        )
        assert result is False

    async def test_delete_guardian_after_unlink_succeeds(
        self, app_session, admin_session
    ):
        """A guardian can be deleted after all student links are removed."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await _create_student(service, tenant["id"])
        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Unlinkable", last_name="Guardian", phone="0241234567",
        )

        # Link then unlink
        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=student.id, guardian_id=guardian.id,
            relationship="father",
        )
        await service.unlink_guardian_from_student(
            tenant["id"], student.id, guardian.id
        )

        # Now delete should succeed
        result = await service.delete_guardian(tenant["id"], guardian.id)
        assert result is True

    async def test_guardian_linked_students_count(self, app_session, admin_session):
        """get_guardian_linked_students_count returns the correct count."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        guardian = await service.create_guardian(
            tenant_id=tenant["id"],
            first_name="Counter", last_name="Guardian", phone="0241234567",
        )

        # No links yet
        count = await service.get_guardian_linked_students_count(
            tenant["id"], guardian.id
        )
        assert count == 0

        # Link to two students
        s1 = await _create_student(service, tenant["id"], suffix="cnt1")
        s2 = await _create_student(service, tenant["id"], suffix="cnt2")

        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=s1.id, guardian_id=guardian.id,
            relationship="father",
        )
        await service.link_guardian_to_student(
            tenant_id=tenant["id"],
            student_id=s2.id, guardian_id=guardian.id,
            relationship="father",
        )

        count = await service.get_guardian_linked_students_count(
            tenant["id"], guardian.id
        )
        assert count == 2

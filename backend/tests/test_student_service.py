"""
SIMS Plus - Student Service Integration Tests

Tests exercise the StudentService directly against a real PostgreSQL database
with RLS enforced via the two-engine pattern:
- admin_session: superuser, seeds tenants/schools, bypasses RLS
- app_session: sims_app_user, RLS enforced, used for service-layer queries

Each test creates its own tenant/data to avoid cross-test interference.

Covers:
- Student creation (happy path, duplicate ID, auto-generated ID)
- Student retrieval (by UUID, by student_id)
- Student listing with filters (search, class, status, pagination)
- Student update
- Student soft delete (deleted_at set, excluded from queries)
- Student stats
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

async def _seed_school(admin_session, tenant_id, prefix="STU"):
    """Create a minimal school for the tenant. Returns school_id."""
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', :prefix, 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School {prefix}",
            "slug": f"school-{uuid4().hex[:8]}",
            "prefix": prefix,
        },
    )
    await admin_session.flush()
    return school_id


async def _seed_class(admin_session, tenant_id):
    """Create a minimal class for the tenant. Returns class_id."""
    class_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, short_name, level, sequence,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                :name, :short_name, 'primary', 1,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(class_id),
            "tid": str(tenant_id),
            "name": "Class 1",
            "short_name": "C1",
        },
    )
    await admin_session.flush()
    return class_id


# --- Student Creation ---


class TestStudentCreation:
    """Tests for StudentService.create_student."""

    async def test_create_student_returns_student_with_correct_fields(
        self, app_session, admin_session
    ):
        """Creating a student with valid data returns a Student object
        with matching fields and auto-assigned id."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-2026-001",
            first_name="Kwame",
            last_name="Asante",
            date_of_birth=date(2010, 5, 15),
            gender="male",
        )

        assert student.id is not None
        assert student.first_name == "Kwame"
        assert student.last_name == "Asante"
        assert student.student_id == "STU-2026-001"
        assert student.date_of_birth == date(2010, 5, 15)
        assert student.gender.value == "male"
        assert student.status.value == "active"
        assert student.tenant_id == tenant["id"]
        assert student.deleted_at is None

    async def test_create_student_with_all_optional_fields(
        self, app_session, admin_session
    ):
        """Optional fields (email, phone, address, etc.) are stored correctly."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-2026-002",
            first_name="Ama",
            middle_name="Nana",
            last_name="Boateng",
            date_of_birth=date(2011, 3, 20),
            gender="female",
            email="ama@test.com",
            phone="0241234567",
            address="123 Main St",
            city="Accra",
            region="Greater Accra",
            school_id=school_id,
            is_boarder=True,
            blood_group="O+",
            medical_conditions="Asthma",
            notes="Transfer student",
        )

        assert student.middle_name == "Nana"
        assert student.email == "ama@test.com"
        assert student.phone == "0241234567"
        assert student.city == "Accra"
        assert student.school_id == school_id
        assert student.is_boarder is True
        assert student.blood_group == "O+"
        assert student.medical_conditions == "Asthma"

    async def test_create_student_duplicate_student_id_raises_error(
        self, app_session, admin_session
    ):
        """Creating two students with the same student_id in the same tenant
        raises StudentServiceError with code 'duplicate_student_id'."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-DUP-001",
            first_name="Kofi",
            last_name="Mensah",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )

        with pytest.raises(StudentServiceError) as exc_info:
            await service.create_student(
                tenant_id=tenant["id"],
                student_id="STU-DUP-001",
                first_name="Different",
                last_name="Student",
                date_of_birth=date(2010, 2, 2),
                gender="female",
            )

        assert exc_info.value.code == "duplicate_student_id"

    async def test_create_student_same_id_different_tenants_allowed(
        self, app_session, admin_session
    ):
        """The same student_id can exist in different tenants (tenant-scoped uniqueness)."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student in tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student_a = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="STU-SHARED-001",
            first_name="Tenant",
            last_name="A",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        # Capture values before context switch to avoid MissingGreenlet
        student_a_sid = student_a.student_id
        student_a_tid = student_a.tenant_id

        # Create student with same ID in tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        student_b = await service.create_student(
            tenant_id=tenant_b["id"],
            student_id="STU-SHARED-001",
            first_name="Tenant",
            last_name="B",
            date_of_birth=date(2010, 1, 1),
            gender="female",
        )

        # Both should succeed
        assert student_a_sid == student_b.student_id
        assert student_a_tid != student_b.tenant_id


# --- Student Retrieval ---


class TestStudentRetrieval:
    """Tests for StudentService.get_student and get_student_by_student_id."""

    async def test_get_student_by_uuid(self, app_session, admin_session):
        """get_student returns the student when given correct tenant and UUID."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        created = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-GET-001",
            first_name="Akua",
            last_name="Darko",
            date_of_birth=date(2010, 6, 10),
            gender="female",
        )

        fetched = await service.get_student(tenant["id"], created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.first_name == "Akua"

    async def test_get_student_wrong_tenant_returns_none(
        self, app_session, admin_session
    ):
        """get_student returns None when the tenant_id does not match,
        even if the UUID exists. This is defense-in-depth on top of RLS."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student in tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        created = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="STU-WRONG-001",
            first_name="Secret",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        created_id = created.id

        # Switch to tenant B and try to retrieve
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.get_student(tenant_b["id"], created_id)

        assert result is None

    async def test_get_student_nonexistent_uuid_returns_none(
        self, app_session, admin_session
    ):
        """get_student returns None for a UUID that does not exist."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.get_student(tenant["id"], uuid4())
        assert result is None

    async def test_get_student_by_student_id_string(self, app_session, admin_session):
        """get_student_by_student_id returns the student matching the school-assigned ID."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_student(
            tenant_id=tenant["id"],
            student_id="ACH-2026-042",
            first_name="Yaw",
            last_name="Boateng",
            date_of_birth=date(2009, 11, 5),
            gender="male",
        )

        fetched = await service.get_student_by_student_id(tenant["id"], "ACH-2026-042")
        assert fetched is not None
        assert fetched.first_name == "Yaw"
        assert fetched.student_id == "ACH-2026-042"


# --- Student Listing ---


class TestStudentListing:
    """Tests for StudentService.list_students with filters."""

    async def test_list_students_returns_all_for_tenant(
        self, app_session, admin_session
    ):
        """list_students returns all non-deleted students for the tenant."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        for i in range(3):
            await service.create_student(
                tenant_id=tenant["id"],
                student_id=f"STU-LIST-{i:03d}",
                first_name=f"Student{i}",
                last_name="Test",
                date_of_birth=date(2010, 1, 1),
                gender="male",
            )

        students, total = await service.list_students(tenant["id"])

        assert total == 3
        assert len(students) == 3

    async def test_list_students_search_by_name(self, app_session, admin_session):
        """list_students with search parameter filters by first/last name ILIKE."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-SRCH-001",
            first_name="Kwame",
            last_name="Asante",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-SRCH-002",
            first_name="Ama",
            last_name="Owusu",
            date_of_birth=date(2010, 2, 2),
            gender="female",
        )

        # Search for "Kwame"
        students, total = await service.list_students(tenant["id"], search="Kwame")
        assert total == 1
        assert students[0].first_name == "Kwame"

        # Search for "Owusu" (last name)
        students, total = await service.list_students(tenant["id"], search="Owusu")
        assert total == 1
        assert students[0].last_name == "Owusu"

    async def test_list_students_search_by_student_id(
        self, app_session, admin_session
    ):
        """list_students search also matches on student_id."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_student(
            tenant_id=tenant["id"],
            student_id="UNIQUE-CODE-999",
            first_name="Test",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="OTHER-CODE-001",
            first_name="Another",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="female",
        )

        students, total = await service.list_students(
            tenant["id"], search="UNIQUE-CODE"
        )
        assert total == 1
        assert students[0].student_id == "UNIQUE-CODE-999"

    async def test_list_students_filter_by_class(self, app_session, admin_session):
        """list_students with class_id returns only students in that class."""
        tenant = await create_test_tenant(admin_session)
        class_id = await _seed_class(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        # Student IN the class
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-CLS-001",
            first_name="InClass",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
            class_id=class_id,
        )
        # Student NOT in the class
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-CLS-002",
            first_name="NoClass",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="female",
        )

        students, total = await service.list_students(
            tenant["id"], class_id=class_id
        )
        assert total == 1
        assert students[0].first_name == "InClass"

    async def test_list_students_filter_by_status(self, app_session, admin_session):
        """list_students with status filter returns only matching students."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-STA-001",
            first_name="Active",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
            status="active",
        )
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-STA-002",
            first_name="Inactive",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
            status="inactive",
        )

        students, total = await service.list_students(
            tenant["id"], status="inactive"
        )
        assert total == 1
        assert students[0].first_name == "Inactive"

    async def test_list_students_pagination(self, app_session, admin_session):
        """list_students respects page and page_size parameters."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        # Create 5 students
        for i in range(5):
            await service.create_student(
                tenant_id=tenant["id"],
                student_id=f"STU-PAGE-{i:03d}",
                first_name=f"Page{i}",
                last_name="Student",
                date_of_birth=date(2010, 1, 1),
                gender="male",
            )

        # Page 1, size 2
        students, total = await service.list_students(
            tenant["id"], page=1, page_size=2
        )
        assert total == 5
        assert len(students) == 2

        # Page 3, size 2 -- should have 1 student
        students, total = await service.list_students(
            tenant["id"], page=3, page_size=2
        )
        assert total == 5
        assert len(students) == 1


# --- Student Update ---


class TestStudentUpdate:
    """Tests for StudentService.update_student."""

    async def test_update_student_changes_fields(self, app_session, admin_session):
        """update_student modifies the specified fields and leaves others unchanged."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-UPD-001",
            first_name="Kofi",
            last_name="Mensah",
            date_of_birth=date(2010, 3, 15),
            gender="male",
        )

        updated = await service.update_student(
            tenant["id"],
            student.id,
            first_name="Kwesi",
            city="Kumasi",
        )

        assert updated is not None
        assert updated.first_name == "Kwesi"
        assert updated.city == "Kumasi"
        # Unchanged field
        assert updated.last_name == "Mensah"

    async def test_update_student_wrong_tenant_returns_none(
        self, app_session, admin_session
    ):
        """update_student returns None when the tenant_id does not match."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create student in tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="STU-XUPD-001",
            first_name="Secret",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_id = student.id

        # Try to update from tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.update_student(
            tenant_b["id"], student_id, first_name="Hacked"
        )

        assert result is None

    async def test_update_student_nonexistent_returns_none(
        self, app_session, admin_session
    ):
        """update_student returns None for a nonexistent student UUID."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.update_student(
            tenant["id"], uuid4(), first_name="Ghost"
        )
        assert result is None

    async def test_update_student_status_enum(self, app_session, admin_session):
        """update_student correctly converts status string to enum."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-ENUM-001",
            first_name="Enum",
            last_name="Test",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )

        updated = await service.update_student(
            tenant["id"], student.id, status="graduated"
        )

        assert updated is not None
        assert updated.status.value == "graduated"


# --- Student Deletion ---


class TestStudentDeletion:
    """Tests for StudentService.delete_student (soft delete)."""

    async def test_delete_student_sets_deleted_at(self, app_session, admin_session):
        """delete_student sets deleted_at timestamp (soft delete, not physical)."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-DEL-001",
            first_name="ToDelete",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )

        result = await service.delete_student(tenant["id"], student.id)
        assert result is True

        # Verify soft delete: row still exists in DB but has deleted_at set.
        # Use app_session (same connection) because the delete was flushed but
        # not committed, so admin_session (different connection) won't see it.
        row = await app_session.execute(
            text("SELECT deleted_at FROM students WHERE id = CAST(:id AS uuid)"),
            {"id": str(student.id)},
        )
        db_row = row.fetchone()
        assert db_row is not None, "Student row should still exist in DB"
        assert db_row.deleted_at is not None, "deleted_at should be set"

    async def test_deleted_student_excluded_from_get(
        self, app_session, admin_session
    ):
        """get_student returns None for a soft-deleted student."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-DGET-001",
            first_name="Deleted",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_id = student.id

        await service.delete_student(tenant["id"], student_id)

        # get_student should return None for deleted student
        app_session.expire_all()
        result = await service.get_student(tenant["id"], student_id)
        assert result is None

    async def test_deleted_student_excluded_from_list(
        self, app_session, admin_session
    ):
        """list_students does not include soft-deleted students."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        # Create two students, delete one
        keep = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-KEEP-001",
            first_name="Keeper",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        to_delete = await service.create_student(
            tenant_id=tenant["id"],
            student_id="STU-GONE-001",
            first_name="Gone",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="female",
        )

        await service.delete_student(tenant["id"], to_delete.id)
        app_session.expire_all()

        students, total = await service.list_students(tenant["id"])
        assert total == 1
        assert students[0].id == keep.id

    async def test_delete_student_wrong_tenant_returns_false(
        self, app_session, admin_session
    ):
        """delete_student returns False when tenant_id does not match."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        service = StudentService(app_session)

        student = await service.create_student(
            tenant_id=tenant_a["id"],
            student_id="STU-XDEL-001",
            first_name="Protected",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )
        student_id = student.id

        # Try to delete from tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await service.delete_student(tenant_b["id"], student_id)
        assert result is False

    async def test_delete_nonexistent_student_returns_false(
        self, app_session, admin_session
    ):
        """delete_student returns False for a UUID that does not exist."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.delete_student(tenant["id"], uuid4())
        assert result is False


# --- Student ID Generation ---


class TestStudentIdGeneration:
    """Tests for StudentService.generate_student_id."""

    async def test_generate_student_id_format(self, app_session, admin_session):
        """Generated ID follows PREFIX-YEAR-SEQUENCE format."""
        from datetime import datetime

        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        student_id = await service.generate_student_id(tenant["id"], prefix="ACH")
        year = datetime.now().year
        assert student_id == f"ACH-{year}-001"

    async def test_generate_student_id_increments(self, app_session, admin_session):
        """Sequential calls produce incrementing sequence numbers."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        # Create a student to occupy sequence 001
        await service.create_student(
            tenant_id=tenant["id"],
            student_id=await service.generate_student_id(tenant["id"], prefix="SEQ"),
            first_name="First",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            gender="male",
        )

        # Next generated ID should be 002
        next_id = await service.generate_student_id(tenant["id"], prefix="SEQ")
        assert next_id.endswith("-002")


# --- Student Stats ---


class TestStudentStats:
    """Tests for StudentService.get_student_stats."""

    async def test_stats_returns_correct_counts(self, app_session, admin_session):
        """get_student_stats returns accurate counts by status, gender, boarder."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        # 2 active males (1 boarder), 1 active female, 1 graduated male
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STAT-001",
            first_name="Active1", last_name="Male",
            date_of_birth=date(2010, 1, 1), gender="male",
            status="active", is_boarder=True,
        )
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STAT-002",
            first_name="Active2", last_name="Male",
            date_of_birth=date(2010, 1, 1), gender="male",
            status="active",
        )
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STAT-003",
            first_name="Active3", last_name="Female",
            date_of_birth=date(2010, 1, 1), gender="female",
            status="active",
        )
        await service.create_student(
            tenant_id=tenant["id"],
            student_id="STAT-004",
            first_name="Grad1", last_name="Male",
            date_of_birth=date(2010, 1, 1), gender="male",
            status="graduated",
        )

        stats = await service.get_student_stats(tenant["id"])

        assert stats["total"] == 4
        assert stats["active"] == 3
        assert stats["graduated"] == 1
        assert stats["male"] == 3
        assert stats["female"] == 1
        assert stats["boarders"] == 1
        assert stats["day_students"] == 3

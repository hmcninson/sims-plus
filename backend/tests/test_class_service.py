"""
Class & Section Service Tests

Tests for class and class section CRUD operations via AcademicService.
Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require a running sims_plus_test database with
RLS policies applied (alembic upgrade head).
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.services.academic import AcademicService, AcademicServiceError

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("class_serial"),
]


# =========================
# Class Tests
# =========================


class TestCreateClass:
    """Tests for creating classes."""

    async def test_create_class_returns_with_tenant_id(
        self, app_session, admin_session
    ):
        """New class is assigned to the correct tenant."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            short_name="J1",
            level="jhs_1",
            sequence=1,
            capacity=40,
        )

        assert cls is not None
        assert cls.name == "JHS 1"
        assert cls.short_name == "J1"
        assert cls.tenant_id == tenant["id"]
        assert cls.is_active is True

    async def test_create_duplicate_class_name_raises_error(
        self, app_session, admin_session
    ):
        """Duplicate class name within same tenant raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_class(
                tenant_id=tenant["id"],
                name="JHS 1",
            )

        assert exc_info.value.code == "duplicate_class"


class TestListClasses:
    """Tests for listing classes."""

    async def test_list_classes_returns_active_only_by_default(
        self, app_session, admin_session
    ):
        """List classes returns only active classes by default."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            sequence=1,
        )
        await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 2",
            sequence=2,
        )

        # Deactivate one
        await service.update_class(tenant["id"], cls.id, is_active=False)

        classes = await service.list_classes(tenant["id"], active_only=True)
        names = [c.name for c in classes]
        assert "JHS 2" in names
        assert "JHS 1" not in names

    async def test_list_classes_with_sections_included(
        self, app_session, admin_session
    ):
        """List classes with include_sections loads section data."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            sequence=1,
        )
        await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls.id,
            name="A",
            capacity=30,
        )
        await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls.id,
            name="B",
            capacity=30,
        )

        classes = await service.list_classes(
            tenant["id"], include_sections=True
        )
        assert len(classes) == 1
        assert len(classes[0].sections) == 2

    async def test_list_classes_ordered_by_sequence(
        self, app_session, admin_session
    ):
        """Classes are returned ordered by sequence."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_class(
            tenant_id=tenant["id"], name="SHS 1", sequence=3
        )
        await service.create_class(
            tenant_id=tenant["id"], name="JHS 1", sequence=1
        )
        await service.create_class(
            tenant_id=tenant["id"], name="JHS 2", sequence=2
        )

        classes = await service.list_classes(tenant["id"])
        sequences = [c.sequence for c in classes]
        assert sequences == sorted(sequences)


class TestDeleteClass:
    """Tests for soft-deleting classes."""

    async def test_soft_delete_class(self, app_session, admin_session):
        """Deleted class does not appear in list or get."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
        )

        deleted = await service.delete_class(tenant["id"], cls.id)
        assert deleted is True

        result = await service.get_class(tenant["id"], cls.id)
        assert result is None

    async def test_delete_nonexistent_class_returns_false(
        self, app_session, admin_session
    ):
        """Deleting a nonexistent class returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        result = await service.delete_class(tenant["id"], uuid4())
        assert result is False


# =========================
# Section Tests
# =========================


class TestCreateSection:
    """Tests for creating class sections."""

    async def test_create_section_within_class(
        self, app_session, admin_session
    ):
        """Section is created with correct class reference."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
        )

        section = await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls.id,
            name="A",
            capacity=35,
        )

        assert section is not None
        assert section.name == "A"
        assert section.class_id == cls.id
        assert section.tenant_id == tenant["id"]
        assert section.capacity == 35
        assert section.is_active is True

    async def test_create_duplicate_section_name_in_class_raises_error(
        self, app_session, admin_session
    ):
        """Duplicate section name within same class raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
        )

        await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls.id,
            name="A",
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_section(
                tenant_id=tenant["id"],
                class_id=cls.id,
                name="A",
            )

        assert exc_info.value.code == "duplicate_section"

    async def test_create_section_for_nonexistent_class_raises_error(
        self, app_session, admin_session
    ):
        """Creating a section for a nonexistent class raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_section(
                tenant_id=tenant["id"],
                class_id=uuid4(),
                name="A",
            )

        assert exc_info.value.code == "class_not_found"

    async def test_same_section_name_in_different_classes(
        self, app_session, admin_session
    ):
        """Same section name is allowed in different classes."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls_1 = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            sequence=1,
        )
        cls_2 = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 2",
            sequence=2,
        )

        section_1 = await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls_1.id,
            name="A",
        )
        section_2 = await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls_2.id,
            name="A",
        )

        assert section_1.id != section_2.id
        assert section_1.class_id != section_2.class_id


class TestListSections:
    """Tests for listing sections."""

    async def test_list_sections_filtered_by_class(
        self, app_session, admin_session
    ):
        """List sections returns only sections for specified class."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls_1 = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            sequence=1,
        )
        cls_2 = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 2",
            sequence=2,
        )

        await service.create_section(
            tenant_id=tenant["id"], class_id=cls_1.id, name="A"
        )
        await service.create_section(
            tenant_id=tenant["id"], class_id=cls_1.id, name="B"
        )
        await service.create_section(
            tenant_id=tenant["id"], class_id=cls_2.id, name="A"
        )

        sections_1 = await service.list_sections(
            tenant["id"], class_id=cls_1.id
        )
        sections_2 = await service.list_sections(
            tenant["id"], class_id=cls_2.id
        )

        assert len(sections_1) == 2
        assert len(sections_2) == 1


class TestDeleteSection:
    """Tests for soft-deleting sections."""

    async def test_soft_delete_section(self, app_session, admin_session):
        """Deleted section does not appear in get."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
        )
        section = await service.create_section(
            tenant_id=tenant["id"],
            class_id=cls.id,
            name="A",
        )

        deleted = await service.delete_section(tenant["id"], section.id)
        assert deleted is True

        result = await service.get_section(tenant["id"], section.id)
        assert result is None


# =========================
# Tenant Isolation
# =========================


class TestClassTenantIsolation:
    """Classes and sections must be isolated between tenants."""

    async def test_tenant_a_cannot_see_tenant_b_classes(
        self, app_session, admin_session
    ):
        """Tenant A's classes are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create class as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)

        await service.create_class(
            tenant_id=tenant_a["id"],
            name="JHS 1",
        )
        await app_session.flush()

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        classes = await service.list_classes(tenant_b["id"])
        assert len(classes) == 0, "Tenant B must not see Tenant A's classes"

    async def test_tenant_a_cannot_get_tenant_b_section(
        self, app_session, admin_session
    ):
        """Tenant A cannot fetch Tenant B's section by ID."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create class and section via admin for Tenant A
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
            {
                "id": str(class_id),
                "tid": str(tenant_a["id"]),
                "name": "JHS 1",
            },
        )
        await admin_session.execute(
            text("""
                INSERT INTO class_sections (
                    id, tenant_id, class_id, name, is_active,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                    :name, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(section_id),
                "tid": str(tenant_a["id"]),
                "cid": str(class_id),
                "name": "A",
            },
        )
        await admin_session.commit()

        # Try to fetch as Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        service = AcademicService(app_session)

        result = await service.get_section(tenant_b["id"], section_id)
        assert result is None, "Tenant B must not access Tenant A's section"

    async def test_same_class_name_allowed_in_different_tenants(
        self, app_session, admin_session
    ):
        """Two tenants can have classes with the same name."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)
        cls_a = await service.create_class(
            tenant_id=tenant_a["id"],
            name="JHS 1",
        )
        await app_session.flush()
        # Capture values before context switch to avoid MissingGreenlet
        cls_a_id = cls_a.id
        cls_a_name = cls_a.name

        # Create as Tenant B -- same name should work
        await set_app_tenant_context(app_session, tenant_b["id"])
        cls_b = await service.create_class(
            tenant_id=tenant_b["id"],
            name="JHS 1",
        )

        assert cls_a_id != cls_b.id
        assert cls_a_name == cls_b.name == "JHS 1"

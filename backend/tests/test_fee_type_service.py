"""
SIMS Plus - Fee Type Service Integration Tests

Tests exercise FeeTypeService directly with a real PostgreSQL database.
Admin session seeds data (bypasses RLS), app session runs under RLS.

Covers:
- Create fee type with tenant_id
- Duplicate name detection (case-insensitive)
- List fee types filtered by tenant
- Update fee type fields
- Delete fee type (hard delete)
- Tenant isolation: Tenant A cannot see Tenant B fee types
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from app.services.finance.fee_type_service import FeeTypeService
from app.services.finance._shared import FinanceServiceError
from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    clear_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Raw SQL helpers for seeding (admin session, bypasses RLS)
# ---------------------------------------------------------------------------

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_school(session, school_id, tenant_id, slug):
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": f"School {slug}", "slug": slug},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestFeeTypeService:
    """Service-level tests for FeeTypeService."""

    async def test_create_fee_type_returns_with_tenant_id(self, admin_session, app_session):
        """Creating a fee type assigns the correct tenant_id."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        fee_type = await svc.create_fee_type(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Tuition Fee",
            description="Annual tuition",
            category="tuition",
        )

        assert fee_type.name == "Tuition Fee"
        assert fee_type.tenant_id == tenant["id"]
        assert fee_type.school_id == school_id
        assert fee_type.is_active is True
        assert fee_type.category == "tuition"

    async def test_create_duplicate_name_raises_error(self, admin_session, app_session):
        """Creating a fee type with an existing name (case-insensitive) raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        await svc.create_fee_type(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Examination Fee",
        )

        with pytest.raises(FinanceServiceError) as exc_info:
            await svc.create_fee_type(
                tenant_id=tenant["id"],
                school_id=school_id,
                name="examination fee",  # Different case, same name
            )

        assert exc_info.value.code == "duplicate_fee_type"

    async def test_list_fee_types_filtered_by_tenant(self, admin_session, app_session):
        """list_fee_types returns only the current tenant's fee types."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Fee A")
        await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Fee B")

        fee_types, total = await svc.list_fee_types(tenant_id=tenant["id"])

        assert total == 2
        names = {ft.name for ft in fee_types}
        assert names == {"Fee A", "Fee B"}

    async def test_list_fee_types_search_filter(self, admin_session, app_session):
        """list_fee_types with search filters by name substring."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Tuition Fee")
        await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Exam Fee")
        await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Library Dues")

        fee_types, total = await svc.list_fee_types(tenant_id=tenant["id"], search="Fee")

        assert total == 2
        names = {ft.name for ft in fee_types}
        assert "Library Dues" not in names

    async def test_update_fee_type_changes_fields(self, admin_session, app_session):
        """update_fee_type updates the specified fields."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        fee_type = await svc.create_fee_type(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Old Name",
            category="tuition",
        )

        updated = await svc.update_fee_type(
            tenant_id=tenant["id"],
            fee_type_id=fee_type.id,
            name="New Name",
            category="examination",
            is_active=False,
        )

        assert updated is not None
        assert updated.name == "New Name"
        assert updated.category == "examination"
        assert updated.is_active is False

    async def test_update_fee_type_duplicate_name_raises_error(self, admin_session, app_session):
        """Renaming to an existing name (case-insensitive) raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Tuition")
        fee_type_b = await svc.create_fee_type(tenant_id=tenant["id"], school_id=school_id, name="Exam")

        with pytest.raises(FinanceServiceError) as exc_info:
            await svc.update_fee_type(
                tenant_id=tenant["id"],
                fee_type_id=fee_type_b.id,
                name="tuition",
            )

        assert exc_info.value.code == "duplicate_fee_type"

    async def test_update_nonexistent_fee_type_returns_none(self, admin_session, app_session):
        """Updating a fee type that does not exist returns None."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        result = await svc.update_fee_type(
            tenant_id=tenant["id"],
            fee_type_id=uuid4(),
            name="Anything",
        )

        assert result is None

    async def test_delete_fee_type_hard_deletes(self, admin_session, app_session):
        """delete_fee_type removes the row entirely (FeeType has no SoftDeleteMixin)."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        fee_type = await svc.create_fee_type(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Deletable Fee",
        )
        fee_type_id = fee_type.id

        deleted = await svc.delete_fee_type(tenant_id=tenant["id"], fee_type_id=fee_type_id)
        assert deleted is True

        # Should be gone
        found = await svc.get_fee_type(tenant_id=tenant["id"], fee_type_id=fee_type_id)
        assert found is None

    async def test_delete_nonexistent_fee_type_returns_false(self, admin_session, app_session):
        """Deleting a fee type that does not exist returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeTypeService(app_session)

        result = await svc.delete_fee_type(tenant_id=tenant["id"], fee_type_id=uuid4())
        assert result is False


class TestFeeTypeTenantIsolation:
    """Tenant A must NOT see Tenant B's fee types."""

    async def test_tenant_a_cannot_see_tenant_b_fee_types(self, admin_session, app_session):
        """Fee types from Tenant A are invisible to Tenant B under RLS."""
        tenant_a = await create_test_tenant(admin_session)
        school_a_id = uuid4()
        await _seed_school(admin_session, school_a_id, tenant_a["id"], tenant_a["subdomain"])

        tenant_b = await create_test_tenant(admin_session)
        school_b_id = uuid4()
        await _seed_school(admin_session, school_b_id, tenant_b["id"], tenant_b["subdomain"])
        await admin_session.commit()

        # Create fee type as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = FeeTypeService(app_session)
        ft_a = await svc.create_fee_type(
            tenant_id=tenant_a["id"],
            school_id=school_a_id,
            name="Tenant A Tuition",
        )
        ft_a_id = ft_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        # Tenant B should NOT see Tenant A's fee type
        fee_types, total = await svc.list_fee_types(tenant_id=tenant_b["id"])
        fee_type_ids = {ft.id for ft in fee_types}
        assert ft_a_id not in fee_type_ids
        assert total == 0

        # Direct get by ID should also return None
        found = await svc.get_fee_type(tenant_id=tenant_b["id"], fee_type_id=ft_a_id)
        assert found is None

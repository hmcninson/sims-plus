"""
SIMS Plus - Fee Structure Service Integration Tests

Tests exercise FeeStructureService directly with a real PostgreSQL database.
Admin session seeds data (bypasses RLS), app session runs under RLS.

Covers:
- Create fee structure with items
- Get fee structure with items and fee_type details
- List fee structures with filters
- Update fee structure fields and items
- Add/update/delete individual fee items
- Copy fee structure
- Soft delete fee structure
- Tenant isolation
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from app.services.finance.fee_structure_service import FeeStructureService
from app.services.finance.fee_type_service import FeeTypeService
from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
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

_AY_INSERT = text("""
    INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
        status, is_current, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
        :start_date, :end_date, 'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_TERM_INSERT = text("""
    INSERT INTO terms (id, tenant_id, academic_year_id, name, short_name,
        sequence, start_date, end_date, status, is_current,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay_id AS uuid),
        :name, :short_name, :seq, :start_date, :end_date,
        'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_school(session, school_id, tenant_id, slug):
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": f"School {slug}", "slug": slug},
    )


async def _seed_academic_year(session, ay_id, tenant_id):
    await session.execute(
        _AY_INSERT,
        {
            "id": str(ay_id), "tid": str(tenant_id), "name": "2025/2026",
            "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
        },
    )


async def _seed_term(session, term_id, tenant_id, ay_id):
    await session.execute(
        _TERM_INSERT,
        {
            "id": str(term_id), "tid": str(tenant_id), "ay_id": str(ay_id),
            "name": "First Term", "short_name": "T1", "seq": 1,
            "start_date": date(2025, 9, 1), "end_date": date(2025, 12, 20),
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestFeeStructureService:
    """Service-level tests for FeeStructureService."""

    async def test_create_fee_structure_with_items(self, admin_session, app_session):
        """Creating a fee structure with items returns structure and items."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id = uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="JHS Fees Term 1",
            academic_year_id=ay_id,
            term_id=term_id,
            level_category="jhs",
            items=[
                {"name": "Tuition", "amount": "500.00", "is_optional": False, "sequence": 0},
                {"name": "Exam Fee", "amount": "50.00", "is_optional": False, "sequence": 1},
                {"name": "Library", "amount": "20.00", "is_optional": True, "sequence": 2},
            ],
        )

        assert fs.name == "JHS Fees Term 1"
        assert fs.tenant_id == tenant["id"]
        assert fs.academic_year_id == ay_id
        assert len(fs.items) == 3

        # total_amount property sums non-optional items
        assert fs.total_amount == Decimal("550.00")

    async def test_get_fee_structure_includes_items(self, admin_session, app_session):
        """get_fee_structure with include_items=True loads items."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Test Structure",
            items=[
                {"name": "Item 1", "amount": "100.00", "is_optional": False},
                {"name": "Item 2", "amount": "200.00", "is_optional": False},
            ],
        )

        fetched = await svc.get_fee_structure(tenant["id"], fs.id, include_items=True)

        assert fetched is not None
        assert len(fetched.items) == 2
        amounts = {item.amount for item in fetched.items}
        assert Decimal("100.00") in amounts
        assert Decimal("200.00") in amounts

    async def test_get_fee_structure_with_fee_type_link(self, admin_session, app_session):
        """Fee items linked to a fee_type load the fee_type relationship."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        # Create a fee type
        ft_svc = FeeTypeService(app_session)
        ft = await ft_svc.create_fee_type(
            tenant_id=tenant["id"], school_id=school_id, name="Tuition", category="tuition",
        )

        # Create structure with fee_type_id
        fs_svc = FeeStructureService(app_session)
        fs = await fs_svc.create_fee_structure(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="With Fee Type",
            items=[
                {"name": "Tuition", "amount": "500.00", "fee_type_id": ft.id, "is_optional": False},
            ],
        )

        fetched = await fs_svc.get_fee_structure(tenant["id"], fs.id, include_items=True)
        assert fetched.items[0].fee_type is not None
        assert fetched.items[0].fee_type.name == "Tuition"

    async def test_list_fee_structures_with_academic_year_filter(self, admin_session, app_session):
        """list_fee_structures filters by academic_year_id."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, term_id = uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id,
            name="With AY", academic_year_id=ay_id,
            items=[{"name": "Fee", "amount": "100.00"}],
        )
        await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id,
            name="Without AY",
            items=[{"name": "Fee", "amount": "100.00"}],
        )

        results, total = await svc.list_fee_structures(
            tenant_id=tenant["id"], academic_year_id=ay_id,
        )
        assert total == 1
        assert results[0].name == "With AY"

    async def test_update_fee_structure_fields(self, admin_session, app_session):
        """update_fee_structure updates the specified fields."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id,
            name="Original Name", is_active=True,
            items=[{"name": "Fee", "amount": "100.00"}],
        )

        updated = await svc.update_fee_structure(
            tenant_id=tenant["id"], fee_structure_id=fs.id,
            name="Updated Name", is_active=False,
        )

        assert updated.name == "Updated Name"
        assert updated.is_active is False

    async def test_update_fee_structure_syncs_items(self, admin_session, app_session):
        """update_fee_structure with items replaces the item list."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id,
            name="Sync Test",
            items=[
                {"name": "Old Item", "amount": "100.00"},
            ],
        )

        # Replace items entirely
        updated = await svc.update_fee_structure(
            tenant_id=tenant["id"], fee_structure_id=fs.id,
            items=[
                {"name": "New Item A", "amount": "200.00"},
                {"name": "New Item B", "amount": "300.00"},
            ],
        )

        assert len(updated.items) == 2
        names = {item.name for item in updated.items}
        assert names == {"New Item A", "New Item B"}

    async def test_add_fee_item(self, admin_session, app_session):
        """add_fee_item adds an item to an existing fee structure."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id, name="Add Item Test",
            items=[{"name": "Existing", "amount": "100.00"}],
        )

        new_item = await svc.add_fee_item(
            tenant_id=tenant["id"],
            fee_structure_id=fs.id,
            name="Added Item",
            amount=Decimal("75.00"),
            is_optional=True,
        )

        assert new_item is not None
        assert new_item.name == "Added Item"
        assert new_item.amount == Decimal("75.00")
        assert new_item.is_optional is True

    async def test_update_fee_item(self, admin_session, app_session):
        """update_fee_item changes specified fields on an existing item."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id, name="Update Item Test",
            items=[{"name": "Original", "amount": "100.00"}],
        )
        item_id = fs.items[0].id

        updated = await svc.update_fee_item(
            tenant_id=tenant["id"],
            fee_item_id=item_id,
            name="Modified",
            amount=Decimal("250.00"),
        )

        assert updated is not None
        assert updated.name == "Modified"
        assert updated.amount == Decimal("250.00")

    async def test_delete_fee_item(self, admin_session, app_session):
        """delete_fee_item removes an item from the structure."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id, name="Delete Item Test",
            items=[
                {"name": "Keep", "amount": "100.00"},
                {"name": "Remove", "amount": "50.00"},
            ],
        )
        remove_item_id = [item for item in fs.items if item.name == "Remove"][0].id

        deleted = await svc.delete_fee_item(tenant_id=tenant["id"], fee_item_id=remove_item_id)
        assert deleted is True

        # Verify only one item remains
        fetched = await svc.get_fee_structure(tenant["id"], fs.id, include_items=True)
        assert len(fetched.items) == 1
        assert fetched.items[0].name == "Keep"

    async def test_copy_fee_structure(self, admin_session, app_session):
        """copy_fee_structure creates a new structure with the same items."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        original = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id,
            name="Original Structure",
            items=[
                {"name": "Tuition", "amount": "500.00", "is_optional": False},
                {"name": "Exam", "amount": "50.00", "is_optional": False},
            ],
        )

        copy = await svc.copy_fee_structure(
            tenant_id=tenant["id"],
            fee_structure_id=original.id,
            new_name="Copied Structure",
        )

        assert copy is not None
        assert copy.id != original.id
        assert copy.name == "Copied Structure"
        assert len(copy.items) == 2
        copy_amounts = {item.amount for item in copy.items}
        assert Decimal("500.00") in copy_amounts
        assert Decimal("50.00") in copy_amounts

    async def test_soft_delete_fee_structure(self, admin_session, app_session):
        """delete_fee_structure sets deleted_at (soft delete)."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        fs = await svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id, name="To Delete",
            items=[{"name": "Fee", "amount": "100.00"}],
        )

        deleted = await svc.delete_fee_structure(tenant_id=tenant["id"], fee_structure_id=fs.id)
        assert deleted is True

        # Should be invisible (soft deleted)
        found = await svc.get_fee_structure(tenant["id"], fs.id)
        assert found is None

    async def test_delete_nonexistent_returns_false(self, admin_session, app_session):
        """Deleting a fee structure that does not exist returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = FeeStructureService(app_session)

        result = await svc.delete_fee_structure(tenant_id=tenant["id"], fee_structure_id=uuid4())
        assert result is False


class TestFeeStructureTenantIsolation:
    """Tenant A must NOT see Tenant B's fee structures."""

    async def test_tenant_a_cannot_see_tenant_b_fee_structures(self, admin_session, app_session):
        """Fee structures from Tenant A are invisible to Tenant B under RLS."""
        tenant_a = await create_test_tenant(admin_session)
        school_a_id = uuid4()
        await _seed_school(admin_session, school_a_id, tenant_a["id"], tenant_a["subdomain"])

        tenant_b = await create_test_tenant(admin_session)
        school_b_id = uuid4()
        await _seed_school(admin_session, school_b_id, tenant_b["id"], tenant_b["subdomain"])
        await admin_session.commit()

        # Create as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = FeeStructureService(app_session)
        fs_a = await svc.create_fee_structure(
            tenant_id=tenant_a["id"], school_id=school_a_id,
            name="Tenant A Fees",
            items=[{"name": "Fee", "amount": "100.00"}],
        )
        fs_a_id = fs_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        # List should not include Tenant A's structure
        structures, total = await svc.list_fee_structures(tenant_id=tenant_b["id"])
        structure_ids = {s.id for s in structures}
        assert fs_a_id not in structure_ids
        assert total == 0

        # Direct get returns None
        found = await svc.get_fee_structure(tenant_b["id"], fs_a_id)
        assert found is None

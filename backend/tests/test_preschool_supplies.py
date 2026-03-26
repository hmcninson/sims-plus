"""
SIMS Plus - Preschool Supply Tests

Tests exercise the PreschoolSupplyService directly against a real PostgreSQL database.
Covers add, list, use (decrement), use-below-zero rejection, restock, low-stock
detection, and RLS tenant isolation.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolSupplyService, PreschoolServiceError
from app.schemas.preschool.supply import (
    PreschoolSupplyCreate,
    PreschoolSupplyUpdate,
)

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)


# ============================================================
# SQL templates for test data seeding
# ============================================================

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'preschool', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_CLASS_INSERT = text("""
    INSERT INTO classes (id, tenant_id, name, level, sequence,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :level, :seq,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
        date_of_birth, gender, status, class_id, school_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2022-03-15', 'male', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_supply_env(session: AsyncSession) -> dict:
    """Seed a complete environment for supply tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    class_id = uuid4()
    student_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Bright Stars Creche", "slug": f"bs-{uuid4().hex[:8]}",
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_id), "tid": str(tid),
        "name": "Creche", "level": "creche", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student_id), "tid": str(tid), "sid": "SUP-001",
        "fn": "Kwaku", "ln": "Mensah", "cid": str(class_id),
        "school_id": str(school_id),
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "class_id": class_id,
        "student_id": student_id,
        "user_id": user["id"],
    }


@pytest.mark.asyncio
class TestPreschoolSupplies:
    """Tests for PreschoolSupplyService CRUD and business logic."""

    async def test_add_supply(self, admin_session, app_session):
        """Adding a supply creates a record with correct fields."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        supply = await service.add_supply(
            env["tenant_id"],
            env["student_id"],
            PreschoolSupplyCreate(
                item_name="Diapers",
                quantity_remaining=10,
                low_stock_threshold=3,
                notes="Size 4, Pampers preferred",
            ),
        )

        assert supply.item_name == "Diapers"
        assert supply.quantity_remaining == 10
        assert supply.low_stock_threshold == 3
        assert supply.notes == "Size 4, Pampers preferred"
        assert supply.tenant_id == env["tenant_id"]
        assert supply.student_id == env["student_id"]

    async def test_list_supplies(self, admin_session, app_session):
        """Listing returns all active supplies for a student."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        # Create 3 supply items
        for name in ["Diapers", "Wipes", "Spare Clothes"]:
            await service.add_supply(
                env["tenant_id"],
                env["student_id"],
                PreschoolSupplyCreate(item_name=name, quantity_remaining=5),
            )

        supplies = await service.list_supplies(env["tenant_id"], env["student_id"])
        assert len(supplies) == 3
        # Ordered by item_name
        names = [s.item_name for s in supplies]
        assert names == ["Diapers", "Spare Clothes", "Wipes"]

    async def test_use_supply(self, admin_session, app_session):
        """Using a supply decrements quantity by 1."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        supply = await service.add_supply(
            env["tenant_id"],
            env["student_id"],
            PreschoolSupplyCreate(item_name="Wipes", quantity_remaining=8),
        )
        supply_id = supply.id  # capture before any potential expire

        updated = await service.use_supply(env["tenant_id"], supply_id, quantity=1)

        assert updated.quantity_remaining == 7

    async def test_use_supply_multiple(self, admin_session, app_session):
        """Using a supply decrements quantity by N."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        supply = await service.add_supply(
            env["tenant_id"],
            env["student_id"],
            PreschoolSupplyCreate(item_name="Diapers", quantity_remaining=10),
        )
        supply_id = supply.id

        updated = await service.use_supply(env["tenant_id"], supply_id, quantity=4)

        assert updated.quantity_remaining == 6

    async def test_use_supply_below_zero_rejected(self, admin_session, app_session):
        """Cannot decrement supply below zero -- raises error."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        supply = await service.add_supply(
            env["tenant_id"],
            env["student_id"],
            PreschoolSupplyCreate(item_name="Spare Clothes", quantity_remaining=2),
        )
        supply_id = supply.id

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.use_supply(env["tenant_id"], supply_id, quantity=5)

        assert exc_info.value.code == "insufficient_stock"
        # Quantity should be unchanged
        supplies = await service.list_supplies(env["tenant_id"], env["student_id"])
        assert supplies[0].quantity_remaining == 2

    async def test_restock_supply(self, admin_session, app_session):
        """Restocking increments quantity and sets last_restocked_at."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        supply = await service.add_supply(
            env["tenant_id"],
            env["student_id"],
            PreschoolSupplyCreate(item_name="Diapers", quantity_remaining=2),
        )
        supply_id = supply.id

        assert supply.last_restocked_at is None

        restocked = await service.restock_supply(env["tenant_id"], supply_id, quantity=8)

        assert restocked.quantity_remaining == 10
        assert restocked.last_restocked_at is not None

    async def test_low_stock_detection(self, admin_session, app_session):
        """is_low_stock is True when quantity is at or below threshold."""
        env = await _seed_supply_env(admin_session)

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolSupplyService(app_session)

        supply = await service.add_supply(
            env["tenant_id"],
            env["student_id"],
            PreschoolSupplyCreate(
                item_name="Wipes",
                quantity_remaining=3,
                low_stock_threshold=3,
            ),
        )
        supply_id = supply.id

        # quantity == threshold => low stock
        assert supply.is_low_stock is True

        # Restock above threshold
        restocked = await service.restock_supply(env["tenant_id"], supply_id, quantity=5)

        assert restocked.quantity_remaining == 8
        assert restocked.is_low_stock is False

    async def test_supply_rls(self, admin_session, app_session):
        """Supplies from tenant A are invisible to tenant B."""
        env_a = await _seed_supply_env(admin_session)

        # Create supply for tenant A via app_session (RLS enforced)
        await set_app_tenant_context(app_session, env_a["tenant_id"])
        service = PreschoolSupplyService(app_session)

        await service.add_supply(
            env_a["tenant_id"],
            env_a["student_id"],
            PreschoolSupplyCreate(item_name="Blanket", quantity_remaining=1),
        )

        # Verify tenant A can see it
        supplies_a = await service.list_supplies(env_a["tenant_id"], env_a["student_id"])
        assert len(supplies_a) == 1

        # Create tenant B
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Switch to tenant B and verify no supplies are visible
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM preschool_supplies")
        )
        assert result.scalar() == 0, (
            "Tenant B must not see tenant A's supply items"
        )

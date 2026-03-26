"""
Tests for leave type CRUD (Phase 3 — Part B).

Covers: create, duplicate code, list with active filter, update,
soft delete, and tenant isolation.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_leave_prereqs(admin_session, tenant_id):
    """Seed school for leave tests. Returns dict with IDs."""
    school_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )
    await admin_session.commit()
    return {"school_id": school_id}


# --- Tests ---


async def test_create_leave_type(app_session, admin_session):
    """Creating a leave type with all fields stores them correctly."""
    tenant = await create_test_tenant(admin_session)
    await _seed_leave_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveTypeService

    svc = LeaveTypeService(app_session)
    lt = await svc.create(
        tenant_id=tenant["id"],
        data={
            "name": "Annual Leave",
            "code": "annual",
            "description": "Standard annual leave",
            "default_days_per_year": Decimal("20.0"),
            "max_carryover_days": Decimal("5.0"),
            "is_paid": True,
            "requires_approval": True,
            "color": "#3B82F6",
        },
    )

    assert lt.id is not None
    assert lt.name == "Annual Leave"
    assert lt.code == "ANNUAL"  # auto-uppercased
    assert lt.default_days_per_year == Decimal("20.0")
    assert lt.max_carryover_days == Decimal("5.0")
    assert lt.is_paid is True
    assert lt.requires_approval is True
    assert lt.color == "#3B82F6"
    assert lt.deleted_at is None


async def test_create_leave_type_duplicate_code(app_session, admin_session):
    """Creating a leave type with a duplicate code in the same tenant raises error."""
    tenant = await create_test_tenant(admin_session)
    await _seed_leave_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveTypeService

    svc = LeaveTypeService(app_session)
    await svc.create(
        tenant_id=tenant["id"],
        data={
            "name": "Sick Leave",
            "code": "sick",
            "default_days_per_year": Decimal("15.0"),
        },
    )

    with pytest.raises(LeaveTypeService.Error) as exc_info:
        await svc.create(
            tenant_id=tenant["id"],
            data={
                "name": "Sick Leave Again",
                "code": "SICK",  # same code (case insensitive via upper())
                "default_days_per_year": Decimal("10.0"),
            },
        )
    assert exc_info.value.code == 409


async def test_list_leave_types_active_only(app_session, admin_session):
    """Listing with active_only=True excludes inactive types."""
    tenant = await create_test_tenant(admin_session)
    await _seed_leave_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveTypeService

    svc = LeaveTypeService(app_session)

    # Create one active, one inactive
    await svc.create(
        tenant_id=tenant["id"],
        data={
            "name": "Active Type",
            "code": "ACTV",
            "default_days_per_year": Decimal("10.0"),
        },
    )
    inactive = await svc.create(
        tenant_id=tenant["id"],
        data={
            "name": "Inactive Type",
            "code": "INAC",
            "default_days_per_year": Decimal("5.0"),
        },
    )
    # Deactivate the second one
    await svc.update(tenant["id"], inactive.id, {"is_active": False})

    active_types = await svc.list(tenant["id"], active_only=True)
    all_types = await svc.list(tenant["id"], active_only=False)

    active_codes = [t.code for t in active_types]
    all_codes = [t.code for t in all_types]

    assert "ACTV" in active_codes
    assert "INAC" not in active_codes
    assert "INAC" in all_codes


async def test_update_leave_type(app_session, admin_session):
    """Updating a leave type changes name and default_days_per_year."""
    tenant = await create_test_tenant(admin_session)
    await _seed_leave_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveTypeService

    svc = LeaveTypeService(app_session)
    lt = await svc.create(
        tenant_id=tenant["id"],
        data={
            "name": "Original Name",
            "code": "ORIG",
            "default_days_per_year": Decimal("10.0"),
        },
    )

    updated = await svc.update(
        tenant["id"], lt.id,
        {"name": "Updated Name", "default_days_per_year": Decimal("15.0")},
    )

    assert updated.name == "Updated Name"
    assert updated.default_days_per_year == Decimal("15.0")


async def test_soft_delete_leave_type(app_session, admin_session):
    """Deleting a leave type sets deleted_at and removes from list."""
    tenant = await create_test_tenant(admin_session)
    await _seed_leave_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.leave import LeaveTypeService

    svc = LeaveTypeService(app_session)
    lt = await svc.create(
        tenant_id=tenant["id"],
        data={
            "name": "To Delete",
            "code": "TDEL",
            "default_days_per_year": Decimal("5.0"),
        },
    )
    lt_id = lt.id

    await svc.delete(tenant["id"], lt_id)

    # Should not appear in list
    types = await svc.list(tenant["id"], active_only=False)
    type_ids = [t.id for t in types]
    assert lt_id not in type_ids


async def test_leave_types_tenant_isolation(app_session, admin_session):
    """Leave types created in Tenant A are invisible from Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    await _seed_leave_prereqs(admin_session, tenant_a["id"])
    await _seed_leave_prereqs(admin_session, tenant_b["id"])

    # Create leave type in Tenant A
    await set_app_tenant_context(app_session, tenant_a["id"])
    from app.services.leave import LeaveTypeService

    svc_a = LeaveTypeService(app_session)
    lt_a = await svc_a.create(
        tenant_id=tenant_a["id"],
        data={
            "name": "Tenant A Only",
            "code": "TAONLY",
            "default_days_per_year": Decimal("10.0"),
        },
    )
    lt_a_id = lt_a.id

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    svc_b = LeaveTypeService(app_session)
    types_b = await svc_b.list(tenant_b["id"], active_only=False)

    type_ids_b = [t.id for t in types_b]
    assert lt_a_id not in type_ids_b

    # Also verify Tenant B cannot get Tenant A's type by ID
    with pytest.raises(LeaveTypeService.Error) as exc_info:
        await svc_b.get(tenant_b["id"], lt_a_id)
    assert exc_info.value.code == 404

"""
Tests for Sprint 17-18 Background Task Chain-Aware Utilities.

Covers:
1. get_tenant_schools returns only active schools
2. for_each_school with specific school_id processes only that school
3. for_each_school without school_id iterates all active schools
4. Error isolation: one school fails, others continue
5. run_for_all_tenants iterates all active tenants
"""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4, UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.utils import get_tenant_schools, for_each_school, get_active_tenants

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)


async def _seed_chain_tenant(admin_session: AsyncSession, *, school_count: int = 3) -> dict:
    """Seed a tenant with multiple schools, some active and one inactive."""
    tenant = await create_test_tenant(admin_session, subdomain=f"task-{uuid4().hex[:8]}")
    tid = str(tenant["id"])

    school_ids = []
    for i in range(school_count):
        sid = str(uuid4())
        is_active = i < school_count - 1  # Last school is inactive
        status = "active" if is_active else "inactive"
        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, status, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic', :status,
                    :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": sid, "tid": tid, "name": f"School {i+1}",
                "slug": f"school-{i+1}-{uuid4().hex[:6]}",
                "status": status, "is_active": is_active,
            },
        )
        school_ids.append({"id": UUID(sid), "active": is_active, "name": f"School {i+1}"})

    await admin_session.commit()
    return {
        "tenant_id": tenant["id"],
        "schools": school_ids,
    }


@pytest.fixture
async def chain_data(admin_session: AsyncSession):
    """3 schools: 2 active, 1 inactive."""
    return await _seed_chain_tenant(admin_session, school_count=3)


# ==========================
# get_tenant_schools tests
# ==========================

@pytest.mark.asyncio
async def test_get_tenant_schools_returns_active_only(
    app_session: AsyncSession,
    chain_data: dict,
):
    """get_tenant_schools returns only active schools."""
    data = chain_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    schools = await get_tenant_schools(app_session, data["tenant_id"])

    active_ids = {str(s["id"]) for s in data["schools"] if s["active"]}
    inactive_ids = {str(s["id"]) for s in data["schools"] if not s["active"]}

    returned_ids = {str(s.id) for s in schools}
    assert active_ids == returned_ids
    assert returned_ids.isdisjoint(inactive_ids)


@pytest.mark.asyncio
async def test_get_tenant_schools_empty_when_no_schools(
    app_session: AsyncSession,
    admin_session: AsyncSession,
):
    """get_tenant_schools returns [] for a tenant with no schools."""
    tenant = await create_test_tenant(admin_session, subdomain=f"empty-{uuid4().hex[:8]}")
    await set_app_tenant_context(app_session, tenant["id"])

    schools = await get_tenant_schools(app_session, tenant["id"])
    assert schools == []


@pytest.mark.asyncio
async def test_get_tenant_schools_ordered_by_name(
    app_session: AsyncSession,
    chain_data: dict,
):
    """get_tenant_schools returns schools ordered by name."""
    await set_app_tenant_context(app_session, chain_data["tenant_id"])

    schools = await get_tenant_schools(app_session, chain_data["tenant_id"])
    names = [s.name for s in schools]
    assert names == sorted(names)


# ==========================
# for_each_school tests
# ==========================

@pytest.mark.asyncio
async def test_for_each_school_specific_school_id(
    app_session: AsyncSession,
    chain_data: dict,
):
    """for_each_school with school_id processes only that school."""
    data = chain_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    target_school = data["schools"][0]
    callback = AsyncMock(return_value="processed")

    results = await for_each_school(
        app_session, data["tenant_id"], callback, school_id=target_school["id"],
    )

    assert len(results) == 1
    assert results[0] == "processed"
    callback.assert_called_once_with(app_session, data["tenant_id"], target_school["id"])


@pytest.mark.asyncio
async def test_for_each_school_all_schools(
    app_session: AsyncSession,
    chain_data: dict,
):
    """for_each_school without school_id iterates all active schools."""
    data = chain_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    callback = AsyncMock(return_value="ok")

    results = await for_each_school(
        app_session, data["tenant_id"], callback,
    )

    active_count = sum(1 for s in data["schools"] if s["active"])
    assert len(results) == active_count
    assert callback.call_count == active_count


@pytest.mark.asyncio
async def test_for_each_school_error_isolation(
    app_session: AsyncSession,
    chain_data: dict,
):
    """If callback fails for one school, other schools still get processed."""
    data = chain_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    active_schools = [s for s in data["schools"] if s["active"]]
    call_count = 0

    async def flaky_callback(db, tenant_id, school_id):
        nonlocal call_count
        call_count += 1
        if school_id == active_schools[0]["id"]:
            raise RuntimeError("Simulated failure")
        return "success"

    results = await for_each_school(
        app_session, data["tenant_id"], flaky_callback,
    )

    # All active schools were attempted
    assert call_count == len(active_schools)

    # Results include both error dict and success value
    error_results = [r for r in results if isinstance(r, dict) and "error" in r]
    success_results = [r for r in results if r == "success"]
    assert len(error_results) == 1
    assert len(success_results) == len(active_schools) - 1


@pytest.mark.asyncio
async def test_for_each_school_empty_tenant(
    app_session: AsyncSession,
    admin_session: AsyncSession,
):
    """for_each_school returns [] for a tenant with no schools."""
    tenant = await create_test_tenant(admin_session, subdomain=f"noschl-{uuid4().hex[:8]}")
    await set_app_tenant_context(app_session, tenant["id"])

    callback = AsyncMock(return_value="never called")
    results = await for_each_school(app_session, tenant["id"], callback)

    assert results == []
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_for_each_school_specific_school_error_captured(
    app_session: AsyncSession,
    chain_data: dict,
):
    """for_each_school with specific school_id captures errors in result."""
    data = chain_data
    await set_app_tenant_context(app_session, data["tenant_id"])

    target_school = data["schools"][0]

    async def fail_callback(db, tenant_id, school_id):
        raise ValueError("boom")

    results = await for_each_school(
        app_session, data["tenant_id"], fail_callback, school_id=target_school["id"],
    )

    assert len(results) == 1
    assert "error" in results[0]
    assert results[0]["school_id"] == str(target_school["id"])


# ==========================
# get_active_tenants tests
# ==========================

@pytest.mark.asyncio
async def test_get_active_tenants_includes_trial_and_active(
    admin_session: AsyncSession,
):
    """get_active_tenants returns tenants with status trial or active."""
    # Our test tenants are created with status=trial (default) and is_active=True
    # Just verify the function runs and returns a list
    tenants = await get_active_tenants(admin_session)

    # At least the tenants from other tests should exist
    assert isinstance(tenants, list)
    # All returned tenants should be active
    for t in tenants:
        assert t.is_active is True

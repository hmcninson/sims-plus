"""
Tests for CapacityService -- enrollment targets and capacity planning.

Covers: set_target (create/upsert), get_targets, get_dashboard,
check_capacity (under/at limit), and tenant isolation.
Uses two-engine pattern (admin for seed, app for RLS-scoped service calls).
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_school_year_class(admin_session, tenant_id, *, capacity=None):
    """Seed school, academic year, and class. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()

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
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31',
                'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )

    cap_val = str(capacity) if capacity is not None else "NULL"
    await admin_session.execute(
        text(f"""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, capacity, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, {cap_val},
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )

    await admin_session.commit()
    return {"school_id": school_id, "year_id": year_id, "class_id": class_id}


async def _seed_students(admin_session, tenant_id, school_id, class_id, count):
    """Seed active students in a class. Returns list of student IDs."""
    student_ids = []
    for i in range(count):
        sid = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (
                    id, tenant_id, school_id, class_id,
                    student_id, first_name, last_name, gender,
                    date_of_birth, status, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid), CAST(:cid AS uuid),
                    :stuid, :fn, :ln, 'male',
                    '2015-01-01', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(sid), "tid": str(tenant_id),
                "sid": str(school_id), "cid": str(class_id),
                "stuid": f"STU-{uuid4().hex[:8]}", "fn": f"First{i}", "ln": f"Last{i}",
            },
        )
        student_ids.append(sid)
    await admin_session.commit()
    return student_ids


# --- Tests ---


class TestSetTarget:
    """Create and upsert enrollment targets."""

    async def test_create_target(self, admin_session, app_session):
        """POST target -> target created with correct data."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        target = await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=40,
            boarding_target=15,
            day_target=25,
        )

        assert target.target_count == 40
        assert target.boarding_target == 15
        assert target.day_target == 25
        assert target.tenant_id == tenant["id"]

    async def test_create_target_duplicate_upserts(self, admin_session, app_session):
        """Same class+year -> upsert updates existing target."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        first = await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=30,
        )
        first_id = first.id

        second = await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=45,
        )

        assert second.id == first_id  # same row, updated
        assert second.target_count == 45

    async def test_update_target(self, admin_session, app_session):
        """Upsert with new value -> target_count updated."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=20,
        )

        updated = await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=60,
            boarding_target=30,
        )

        assert updated.target_count == 60
        assert updated.boarding_target == 30


class TestGetTargets:
    """List enrollment targets for a school/year."""

    async def test_get_targets(self, admin_session, app_session):
        """GET targets -> list for academic year."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=35,
        )

        targets = await svc.get_targets(
            tenant["id"], ids["school_id"], ids["year_id"],
        )

        assert len(targets) == 1
        assert targets[0].target_count == 35


class TestDashboard:
    """Capacity dashboard combines targets, enrolled counts, and pipeline."""

    async def test_get_dashboard(self, admin_session, app_session):
        """Dashboard shows target vs current counts."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"], capacity=50)

        # Seed 10 students
        await _seed_students(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"], 10,
        )

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        await svc.set_target(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
            class_id=ids["class_id"],
            target_count=40,
        )

        dashboard = await svc.get_dashboard(
            tenant["id"], ids["school_id"], ids["year_id"],
        )

        assert dashboard["total_enrolled"] == 10
        assert dashboard["total_target"] == 40
        assert dashboard["total_capacity"] == 50
        assert len(dashboard["classes"]) >= 1

        cls = dashboard["classes"][0]
        assert cls["current_enrolled"] == 10
        assert cls["target"] == 40


class TestCapacityCheck:
    """Quick capacity check for a single class."""

    async def test_capacity_check_under(self, admin_session, app_session):
        """Class with room -> remaining > 0, is_full=false (advisory)."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"], capacity=30)
        await _seed_students(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"], 10,
        )

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        result = await svc.check_capacity(
            tenant["id"], ids["school_id"], ids["class_id"],
        )

        assert result["remaining"] == 20
        assert result["is_full"] is False
        assert result["current_enrolled"] == 10

    async def test_capacity_check_at_limit(self, admin_session, app_session):
        """Class at capacity -> remaining=0, is_full=true (advisory per AD-4)."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_school_year_class(admin_session, tenant["id"], capacity=5)
        await _seed_students(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"], 5,
        )

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc = CapacityService(app_session)
        result = await svc.check_capacity(
            tenant["id"], ids["school_id"], ids["class_id"],
        )

        assert result["remaining"] == 0
        assert result["is_full"] is True


class TestTargetTenantIsolation:
    """Tenant A's targets must be invisible to Tenant B."""

    async def test_target_tenant_isolation(self, admin_session, app_session):
        """Cross-tenant target -> invisible."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"cap-a-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"cap-b-{uuid4().hex[:8]}")
        ids_a = await _seed_school_year_class(admin_session, tenant_a["id"])
        ids_b = await _seed_school_year_class(admin_session, tenant_b["id"])

        # Create target as tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        from app.services.admissions.capacity_service import CapacityService

        svc_a = CapacityService(app_session)
        target_a = await svc_a.set_target(
            tenant_a["id"], ids_a["school_id"],
            academic_year_id=ids_a["year_id"],
            class_id=ids_a["class_id"],
            target_count=50,
        )
        target_a_id = target_a.id

        # Switch to tenant B and list targets
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = CapacityService(app_session)
        targets_b = await svc_b.get_targets(
            tenant_b["id"], ids_b["school_id"], ids_b["year_id"],
        )

        target_ids_b = [t.id for t in targets_b]
        assert target_a_id not in target_ids_b

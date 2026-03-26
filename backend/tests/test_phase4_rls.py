"""
RLS Isolation Tests for Enrollment Gap Closure Phase 4 (3 new tables).

Verifies that tenant B cannot see, modify, or delete tenant A's data
in enrollment_targets, school_events, and event_registrations.
Uses the two-engine test pattern (admin_session for seeding, app_session for RLS queries).

This is a security-critical test file. If any test here fails,
tenant data is leaking across tenants.
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
    TENANT_SCOPED_TABLES,
)

pytestmark = [
    pytest.mark.rls,
    pytest.mark.asyncio,
    pytest.mark.xdist_group("rls_serial"),
]

# The 3 Phase 4 tables that must have RLS
PHASE4_TABLES = [
    "enrollment_targets",
    "school_events",
    "event_registrations",
]


# --- Helpers ---


async def _seed_phase4_data(admin_session, tenant_id):
    """Seed prerequisite + Phase 4 data for one tenant.

    Returns dict with all row IDs.
    """
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    target_id = uuid4()
    event_id = uuid4()
    reg_id = uuid4()

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

    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )

    # enrollment_targets
    await admin_session.execute(
        text("""
            INSERT INTO enrollment_targets (
                id, tenant_id, school_id, academic_year_id, class_id,
                target_count, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), CAST(:cid AS uuid),
                30, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(target_id), "tid": str(tenant_id),
            "sid": str(school_id), "ayid": str(year_id), "cid": str(class_id),
        },
    )

    # school_events
    await admin_session.execute(
        text("""
            INSERT INTO school_events (
                id, tenant_id, school_id, event_type, name,
                event_date, status, registered_count,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'open_day', :name,
                '2026-05-15', 'upcoming', 0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(event_id), "tid": str(tenant_id),
            "sid": str(school_id), "name": f"Event-{uuid4().hex[:6]}",
        },
    )

    # event_registrations
    await admin_session.execute(
        text("""
            INSERT INTO event_registrations (
                id, tenant_id, event_id,
                registrant_name, registrant_phone,
                attended, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:eid AS uuid),
                :rname, :rphone,
                false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(reg_id), "tid": str(tenant_id),
            "eid": str(event_id),
            "rname": f"Parent-{uuid4().hex[:6]}", "rphone": f"024{uuid4().hex[:7]}",
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "year_id": year_id,
        "class_id": class_id,
        "target_id": target_id,
        "event_id": event_id,
        "reg_id": reg_id,
    }


# --- Tests ---


class TestPhase4RLSIsolation:
    """Cross-tenant visibility tests for Phase 4 tables."""

    async def test_enrollment_target_rls(self, admin_session, app_session):
        """Tenant A's enrollment targets invisible from Tenant B's context."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"rls4a-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"rls4b-{uuid4().hex[:8]}")
        ids_a = await _seed_phase4_data(admin_session, tenant_a["id"])

        # Query as Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT id FROM enrollment_targets"))
        rows = result.fetchall()

        visible_ids = {row[0] for row in rows}
        assert ids_a["target_id"] not in visible_ids

    async def test_school_event_rls(self, admin_session, app_session):
        """Tenant A's school events invisible from Tenant B's context."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"rls4c-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"rls4d-{uuid4().hex[:8]}")
        ids_a = await _seed_phase4_data(admin_session, tenant_a["id"])

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT id FROM school_events"))
        rows = result.fetchall()

        visible_ids = {row[0] for row in rows}
        assert ids_a["event_id"] not in visible_ids

    async def test_event_registration_rls(self, admin_session, app_session):
        """Tenant A's event registrations invisible from Tenant B's context."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"rls4e-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"rls4f-{uuid4().hex[:8]}")
        ids_a = await _seed_phase4_data(admin_session, tenant_a["id"])

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT id FROM event_registrations"))
        rows = result.fetchall()

        visible_ids = {row[0] for row in rows}
        assert ids_a["reg_id"] not in visible_ids


class TestPhase4RLSRegistration:
    """Verify Phase 4 tables are registered in the global TENANT_SCOPED_TABLES list."""

    async def test_rls_tables_registered(self):
        """All 3 Phase 4 tables must be in TENANT_SCOPED_TABLES."""
        for table in PHASE4_TABLES:
            assert table in TENANT_SCOPED_TABLES, (
                f"{table} is NOT in TENANT_SCOPED_TABLES -- RLS tests will miss it"
            )


class TestPhase4RLSPoliciesExist:
    """Verify that RLS is enabled and policies exist on Phase 4 tables."""

    async def test_rls_policies_exist(self, admin_session):
        """RLS enabled + policies present on all 3 tables."""
        for table in PHASE4_TABLES:
            # Check RLS is enabled
            result = await admin_session.execute(
                text("""
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname = :table_name
                """),
                {"table_name": table},
            )
            row = result.fetchone()
            assert row is not None, f"Table {table} not found in pg_class"
            assert row[0] is True, f"RLS not enabled on {table}"
            assert row[1] is True, f"FORCE RLS not enabled on {table}"

            # Check at least one policy exists
            policy_result = await admin_session.execute(
                text("""
                    SELECT COUNT(*) FROM pg_policies
                    WHERE tablename = :table_name
                """),
                {"table_name": table},
            )
            count = policy_result.scalar()
            assert count > 0, f"No RLS policy found for {table}"


class TestPhase4CrossTenantAPI:
    """Service-level cross-tenant isolation test."""

    async def test_cross_tenant_event_api(self, admin_session, app_session):
        """Tenant B cannot access Tenant A's event via service call."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"rls4g-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"rls4h-{uuid4().hex[:8]}")

        school_a = uuid4()
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
            {"id": str(school_a), "tid": str(tenant_a["id"]),
             "name": f"School-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
        )
        await admin_session.commit()

        # Create event as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        from app.services.admissions.event_service import EventService, EventServiceError

        svc_a = EventService(app_session)
        event_a = await svc_a.create_event(
            tenant_a["id"], school_a,
            event_type="tour", name="Tenant A Tour",
            event_date=date(2026, 6, 1),
        )
        event_a_id = event_a.id

        # Switch to Tenant B -- should NOT be able to access the event
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = EventService(app_session)

        with pytest.raises(EventServiceError) as exc_info:
            await svc_b._get_event(tenant_b["id"], event_a_id)
        assert exc_info.value.code == "NOT_FOUND"

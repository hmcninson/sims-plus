"""
Tests for EventService -- school tours, open days, and orientation events.

Covers: CRUD, cancel, register (capacity, duplicate), delete registration,
mark attendance, and tenant isolation.
Uses two-engine pattern (admin for seed, app for RLS-scoped service calls).
"""

import pytest
from datetime import date, time
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


async def _seed_school(admin_session, tenant_id):
    """Seed a school. Returns school_id."""
    school_id = uuid4()
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
    await admin_session.commit()
    return school_id


async def _create_event(svc, tenant_id, school_id, **overrides):
    """Helper to create an event via EventService."""
    defaults = {
        "event_type": "open_day",
        "name": f"Open Day {uuid4().hex[:6]}",
        "event_date": date(2026, 5, 15),
        "start_time": time(9, 0),
        "end_time": time(12, 0),
        "venue": "Main Hall",
        "capacity": 50,
    }
    defaults.update(overrides)
    return await svc.create_event(tenant_id, school_id, **defaults)


async def _register_for_event(svc, tenant_id, event_id, **overrides):
    """Helper to register for an event via EventService."""
    defaults = {
        "registrant_name": f"Parent {uuid4().hex[:6]}",
        "registrant_phone": f"024{uuid4().hex[:7]}",
        "registrant_email": f"parent-{uuid4().hex[:6]}@example.com",
        "student_name": f"Child {uuid4().hex[:6]}",
    }
    defaults.update(overrides)
    return await svc.register(tenant_id, event_id, **defaults)


# --- Tests ---


class TestCreateEvent:
    """Create school events."""

    async def test_create_event(self, admin_session, app_session):
        """Create event -> returned with correct data."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id)

        assert event.event_type == "open_day"
        assert event.status == "upcoming"
        assert event.registered_count == 0
        assert event.capacity == 50
        assert event.tenant_id == tenant["id"]


class TestListEvents:
    """List and filter events."""

    async def test_list_events(self, admin_session, app_session):
        """List events -> paginated list."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        await _create_event(svc, tenant["id"], school_id, event_type="open_day")
        await _create_event(svc, tenant["id"], school_id, event_type="tour")

        events, total = await svc.list_events(tenant["id"], school_id)
        assert total == 2
        assert len(events) == 2

    async def test_list_events_filter_type(self, admin_session, app_session):
        """Filter by event_type -> only matching events."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        await _create_event(svc, tenant["id"], school_id, event_type="open_day")
        await _create_event(svc, tenant["id"], school_id, event_type="tour")
        await _create_event(svc, tenant["id"], school_id, event_type="orientation")

        events, total = await svc.list_events(
            tenant["id"], school_id, event_type="tour",
        )
        assert total == 1
        assert events[0].event_type == "tour"


class TestGetUpdateEvent:
    """Get and update events."""

    async def test_get_event(self, admin_session, app_session):
        """Get event by ID -> correct detail."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        created = await _create_event(svc, tenant["id"], school_id, name="My Event")
        created_id = created.id

        fetched = await svc._get_event(tenant["id"], created_id)
        assert fetched.name == "My Event"

    async def test_update_event(self, admin_session, app_session):
        """Update upcoming event -> fields updated."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id)

        updated = await svc.update_event(
            tenant["id"], event.id, venue="Science Lab", capacity=100,
        )
        assert updated.venue == "Science Lab"
        assert updated.capacity == 100


class TestCancelEvent:
    """Cancel events."""

    async def test_cancel_event(self, admin_session, app_session):
        """Cancel upcoming event -> status=cancelled."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id)

        cancelled = await svc.cancel_event(tenant["id"], event.id)
        assert cancelled.status == "cancelled"


class TestRegistration:
    """Register, duplicate, capacity, cancel registration."""

    async def test_register_for_event(self, admin_session, app_session):
        """Register -> registered_count incremented."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id, capacity=10)
        event_id = event.id

        reg = await _register_for_event(svc, tenant["id"], event_id)
        assert reg.event_id == event_id
        assert reg.attended is False

        # Verify count incremented
        refreshed = await svc._get_event(tenant["id"], event_id)
        assert refreshed.registered_count == 1

    async def test_register_full_event(self, admin_session, app_session):
        """Register for full event -> error."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService, EventServiceError

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id, capacity=1)
        event_id = event.id

        # Fill the one spot
        await _register_for_event(svc, tenant["id"], event_id)

        # Second registration should fail
        with pytest.raises(EventServiceError) as exc_info:
            await _register_for_event(svc, tenant["id"], event_id)
        assert exc_info.value.code == "EVENT_FULL"

    async def test_register_duplicate_phone(self, admin_session, app_session):
        """Same phone for same event -> error."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService, EventServiceError

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id, capacity=10)
        event_id = event.id
        phone = "0241234567"

        await _register_for_event(
            svc, tenant["id"], event_id, registrant_phone=phone,
        )

        with pytest.raises(EventServiceError) as exc_info:
            await _register_for_event(
                svc, tenant["id"], event_id, registrant_phone=phone,
            )
        assert exc_info.value.code == "DUPLICATE_REGISTRATION"

    async def test_cancel_registration(self, admin_session, app_session):
        """Delete registration -> hard deleted, count decremented."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id, capacity=10)
        event_id = event.id

        reg = await _register_for_event(svc, tenant["id"], event_id)
        reg_id = reg.id

        # Count should be 1
        refreshed = await svc._get_event(tenant["id"], event_id)
        assert refreshed.registered_count == 1

        # Delete registration
        await svc.delete_registration(tenant["id"], event_id, reg_id)

        # Count should be back to 0
        refreshed2 = await svc._get_event(tenant["id"], event_id)
        assert refreshed2.registered_count == 0


class TestAttendance:
    """Mark attendance for registrations."""

    async def test_mark_attended(self, admin_session, app_session):
        """Mark attendance -> attended=true."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.event_service import EventService

        svc = EventService(app_session)
        event = await _create_event(svc, tenant["id"], school_id)
        event_id = event.id

        reg = await _register_for_event(svc, tenant["id"], event_id)

        marked = await svc.mark_attendance(
            tenant["id"], event_id, reg.id, attended=True,
        )
        assert marked.attended is True


class TestEventTenantIsolation:
    """Tenant A's events must be invisible to Tenant B."""

    async def test_event_tenant_isolation(self, admin_session, app_session):
        """Cross-tenant event -> invisible."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"ev-a-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"ev-b-{uuid4().hex[:8]}")
        school_a = await _seed_school(admin_session, tenant_a["id"])
        school_b = await _seed_school(admin_session, tenant_b["id"])

        # Create event as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        from app.services.admissions.event_service import EventService

        svc_a = EventService(app_session)
        event_a = await _create_event(svc_a, tenant_a["id"], school_a)
        event_a_id = event_a.id

        # Switch to Tenant B and list events
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = EventService(app_session)
        events_b, total_b = await svc_b.list_events(tenant_b["id"], school_b)

        event_ids_b = [e.id for e in events_b]
        assert event_a_id not in event_ids_b
        assert total_b == 0

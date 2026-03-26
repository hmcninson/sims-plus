"""
SIMS Plus - Preschool Incident Tests

Tests exercise the PreschoolIncidentService directly against a real PostgreSQL database.
Covers incident CRUD, status workflow transitions, severity gate, soft delete, and attachments.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import pytest
from datetime import date, time, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolIncidentService, PreschoolServiceError
from app.schemas.preschool.incident import (
    PreschoolIncidentCreate,
    PreschoolIncidentUpdate,
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

_ACADEMIC_YEAR_INSERT = text("""
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
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_incident_env(session: AsyncSession) -> dict:
    """Seed a complete environment for incident tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    student1_id = uuid4()
    student2_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Preschool Academy", "slug": f"ps-{uuid4().hex[:8]}",
    })
    await session.execute(_ACADEMIC_YEAR_INSERT, {
        "id": str(ay_id), "tid": str(tid), "name": "2025/2026",
        "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
    })
    await session.execute(_TERM_INSERT, {
        "id": str(term_id), "tid": str(tid), "ay_id": str(ay_id),
        "name": "First Term", "short_name": "T1", "seq": 1,
        "start_date": date(2025, 9, 1), "end_date": date(2025, 12, 20),
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_id), "tid": str(tid),
        "name": "KG 1", "level": "kg_1", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "PRE-001",
        "fn": "Esi", "ln": "Owusu", "cid": str(class_id),
        "school_id": str(school_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student2_id), "tid": str(tid), "sid": "PRE-002",
        "fn": "Kofi", "ln": "Boateng", "cid": str(class_id),
        "school_id": str(school_id),
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "student1_id": student1_id,
        "student2_id": student2_id,
        "user_id": user["id"],
    }


def _make_incident_data(student_id, **overrides):
    """Build a PreschoolIncidentCreate with sensible defaults."""
    params = {
        "student_id": student_id,
        "incident_type": "accident",
        "severity": "minor",
        "incident_date": date.today(),
        "description": "Child fell on the playground and scraped her knee.",
    }
    params.update(overrides)
    return PreschoolIncidentCreate(**params)


@pytest.mark.asyncio
class TestPreschoolIncidents:
    """Test incident CRUD and workflow."""

    async def test_create_incident_success(self, admin_session, app_session):
        """Create a basic incident report."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolIncidentService(app_session)
        data = _make_incident_data(env["student1_id"])
        incident = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=data,
            reported_by=env["user_id"],
        )

        assert incident.status == "reported"
        assert incident.reported_by == env["user_id"]
        assert incident.school_id == env["school_id"]
        assert incident.student_id == env["student1_id"]

    async def test_create_incident_student_not_found(self, admin_session, app_session):
        """Error when student_id doesn't belong to tenant."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolIncidentService(app_session)
        data = _make_incident_data(uuid4())  # random UUID

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.create_incident(
                tenant_id=env["tenant_id"], data=data, reported_by=env["user_id"],
            )
        assert exc_info.value.code == "STUDENT_NOT_FOUND"

    async def test_list_incidents_filter_by_student(self, admin_session, app_session):
        """List incidents filtered by student_id."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        # 2 incidents for student_1, 1 for student_2
        for _ in range(2):
            await service.create_incident(
                tenant_id=env["tenant_id"],
                data=_make_incident_data(env["student1_id"]),
                reported_by=env["user_id"],
            )
        await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student2_id"]),
            reported_by=env["user_id"],
        )

        s1 = await service.list_incidents(env["tenant_id"], student_id=env["student1_id"])
        s2 = await service.list_incidents(env["tenant_id"], student_id=env["student2_id"])

        assert len(s1) == 2
        assert len(s2) == 1

    async def test_list_incidents_filter_by_status(self, admin_session, app_session):
        """List incidents filtered by status."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"]),
            reported_by=env["user_id"],
        )
        # Transition to reviewed via raw SQL (no service method for review)
        inc_id = inc.id
        await app_session.execute(text(
            "UPDATE preschool_incidents SET status = 'reviewed' WHERE id = CAST(:id AS uuid)"
        ), {"id": str(inc_id)})
        await app_session.flush()

        reported = await service.list_incidents(env["tenant_id"], status="reported")
        reviewed = await service.list_incidents(env["tenant_id"], status="reviewed")

        assert len(reported) == 0
        assert len(reviewed) == 1

    async def test_list_incidents_filter_by_severity(self, admin_session, app_session):
        """List incidents filtered by severity."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"], severity="minor"),
            reported_by=env["user_id"],
        )
        await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"], severity="serious"),
            reported_by=env["user_id"],
        )

        minor = await service.list_incidents(env["tenant_id"], severity="minor")
        serious = await service.list_incidents(env["tenant_id"], severity="serious")

        assert len(minor) == 1
        assert len(serious) == 1

    async def test_list_incidents_filter_by_date_range(self, admin_session, app_session):
        """List incidents filtered by date range."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"], incident_date=date(2026, 3, 1)),
            reported_by=env["user_id"],
        )
        await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"], incident_date=date(2026, 3, 15)),
            reported_by=env["user_id"],
        )

        results = await service.list_incidents(
            env["tenant_id"], date_from=date(2026, 3, 10), date_to=date(2026, 3, 20),
        )
        assert len(results) == 1
        assert results[0].incident_date == date(2026, 3, 15)

    async def test_update_incident(self, admin_session, app_session):
        """Update incident description and action_taken."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"]),
            reported_by=env["user_id"],
        )

        updated = await service.update_incident(
            tenant_id=env["tenant_id"],
            incident_id=inc.id,
            data=PreschoolIncidentUpdate(
                description="Updated description with more detail.",
                action_taken="Applied ice pack.",
            ),
        )

        assert updated.description == "Updated description with more detail."
        assert updated.action_taken == "Applied ice pack."
        assert updated.status == "reported"  # Status not changed by update

    async def test_notify_parent_from_reported(self, admin_session, app_session):
        """Transition from reported to parent_notified."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"]),
            reported_by=env["user_id"],
        )

        notified = await service.notify_parent_incident(
            tenant_id=env["tenant_id"],
            incident_id=inc.id,
            notified_by=env["user_id"],
        )

        assert notified.status == "parent_notified"
        assert notified.parent_notified_at is not None
        assert notified.parent_notified_by == env["user_id"]

    async def test_notify_parent_from_reviewed(self, admin_session, app_session):
        """Transition from reviewed to parent_notified."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"]),
            reported_by=env["user_id"],
        )
        inc_id = inc.id  # capture before expire_all
        # Transition to reviewed via raw SQL
        await app_session.execute(text(
            "UPDATE preschool_incidents SET status = 'reviewed' WHERE id = CAST(:id AS uuid)"
        ), {"id": str(inc_id)})
        await app_session.flush()
        app_session.expire_all()

        notified = await service.notify_parent_incident(
            tenant_id=env["tenant_id"],
            incident_id=inc_id,
            notified_by=env["user_id"],
        )

        assert notified.status == "parent_notified"

    async def test_resolve_from_parent_notified(self, admin_session, app_session):
        """Transition from parent_notified to resolved."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"]),
            reported_by=env["user_id"],
        )
        await service.notify_parent_incident(
            env["tenant_id"], inc.id, env["user_id"],
        )

        resolved = await service.resolve_incident(
            tenant_id=env["tenant_id"],
            incident_id=inc.id,
            follow_up_notes="Child recovered fully by end of day.",
            resolved_by=env["user_id"],
        )

        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None
        assert resolved.resolved_by == env["user_id"]
        assert resolved.follow_up_notes == "Child recovered fully by end of day."

    async def test_resolve_from_reported_minor(self, admin_session, app_session):
        """Minor incidents can skip parent notification if reviewed first."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"], severity="minor"),
            reported_by=env["user_id"],
        )
        inc_id = inc.id  # capture before expire_all
        # Transition to reviewed first (reported -> resolved is NOT a valid transition)
        await app_session.execute(text(
            "UPDATE preschool_incidents SET status = 'reviewed' WHERE id = CAST(:id AS uuid)"
        ), {"id": str(inc_id)})
        await app_session.flush()
        app_session.expire_all()

        resolved = await service.resolve_incident(
            tenant_id=env["tenant_id"],
            incident_id=inc_id,
            follow_up_notes=None,
            resolved_by=env["user_id"],
        )

        assert resolved.status == "resolved"

    async def test_invalid_transition_rejected(self, admin_session, app_session):
        """Cannot transition from resolved to any other state."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"]),
            reported_by=env["user_id"],
        )
        await service.notify_parent_incident(env["tenant_id"], inc.id, env["user_id"])
        await service.resolve_incident(
            env["tenant_id"], inc.id, None, env["user_id"],
        )

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.notify_parent_incident(
                env["tenant_id"], inc.id, env["user_id"],
            )
        assert exc_info.value.code == "INVALID_TRANSITION"

    async def test_severity_gate_moderate(self, admin_session, app_session):
        """Moderate incidents MUST go through parent_notified before resolved."""
        env = await _seed_incident_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolIncidentService(app_session)

        inc = await service.create_incident(
            tenant_id=env["tenant_id"],
            data=_make_incident_data(env["student1_id"], severity="moderate"),
            reported_by=env["user_id"],
        )
        inc_id = inc.id  # capture before expire_all
        # Transition to reviewed
        await app_session.execute(text(
            "UPDATE preschool_incidents SET status = 'reviewed' WHERE id = CAST(:id AS uuid)"
        ), {"id": str(inc_id)})
        await app_session.flush()
        app_session.expire_all()

        # Try to resolve directly from reviewed -- should fail for moderate
        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.resolve_incident(
                env["tenant_id"], inc_id, "Tried to skip", env["user_id"],
            )
        assert exc_info.value.code == "PARENT_NOTIFICATION_REQUIRED"

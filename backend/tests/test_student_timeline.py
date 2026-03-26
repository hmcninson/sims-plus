"""
SIMS Plus - Student Timeline Tests (Phase 2)

Tests exercise PreschoolPortfolioService.get_student_timeline() against a real
PostgreSQL database. The timeline aggregates entries from 4 tables:
student_skill_assessments, progress_observations, preschool_incidents,
and learning_stories into a unified date-sorted list.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import pytest
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolPortfolioService, PreschoolServiceError

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

_LEARNING_AREA_INSERT = text("""
    INSERT INTO learning_areas (id, tenant_id, name, code, description,
        display_order, is_active, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code, :desc,
        :seq, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_SKILL_INSERT = text("""
    INSERT INTO developmental_skills (id, tenant_id, learning_area_id,
        name, description, age_range_months_min, display_order, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:la_id AS uuid),
        :name, :desc, 3, :seq, true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_timeline_env(session: AsyncSession) -> dict:
    """Seed a complete environment for timeline tests.

    Creates tenant, school, academic year, term, class, student,
    learning area, and skill — everything needed to insert records
    into the 4 timeline source tables.
    """
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    student_id = uuid4()
    la_id = uuid4()
    skill_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Timeline Preschool", "slug": f"tl-{uuid4().hex[:8]}",
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
        "name": "Nursery 2", "level": "nursery_2", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student_id), "tid": str(tid), "sid": "TL-001",
        "fn": "Akosua", "ln": "Annan", "cid": str(class_id),
        "school_id": str(school_id),
    })
    await session.execute(_LEARNING_AREA_INSERT, {
        "id": str(la_id), "tid": str(tid),
        "name": "Language & Literacy", "code": "LANG",
        "desc": "Language development", "seq": 1,
    })
    await session.execute(_SKILL_INSERT, {
        "id": str(skill_id), "tid": str(tid), "la_id": str(la_id),
        "name": "Recognizes own name", "desc": "Can identify name in print", "seq": 1,
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "student_id": student_id,
        "la_id": la_id,
        "skill_id": skill_id,
        "user_id": user["id"],
    }


async def _insert_assessment(session, env, assessed_at):
    """Insert a student_skill_assessment via admin session."""
    aid = uuid4()
    await session.execute(text("""
        INSERT INTO student_skill_assessments
            (id, tenant_id, student_id, skill_id, academic_year_id, term_id,
             observation_notes, assessed_by, assessed_at,
             created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
            CAST(:sk_id AS uuid), CAST(:ay_id AS uuid), CAST(:tm_id AS uuid),
            :notes, CAST(:uid AS uuid), :assessed_at,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "id": str(aid), "tid": str(env["tenant_id"]),
        "sid": str(env["student_id"]), "sk_id": str(env["skill_id"]),
        "ay_id": str(env["ay_id"]), "tm_id": str(env["term_id"]),
        "notes": "Good progress on name recognition",
        "uid": str(env["user_id"]), "assessed_at": assessed_at,
    })
    return aid


async def _insert_observation(session, env, obs_date):
    """Insert a progress_observation via admin session."""
    oid = uuid4()
    await session.execute(text("""
        INSERT INTO progress_observations
            (id, tenant_id, student_id, learning_area_id,
             observation_type, title,
             description, observation_date, share_with_parents,
             is_highlight, recorded_by,
             created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
            CAST(:la_id AS uuid),
            'anecdote', :title, :desc, :obs_date, true,
            false, CAST(:uid AS uuid),
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "id": str(oid), "tid": str(env["tenant_id"]),
        "sid": str(env["student_id"]),
        "la_id": str(env["la_id"]),
        "title": f"Observation on {obs_date}",
        "desc": "Student engaged in group play",
        "obs_date": obs_date, "uid": str(env["user_id"]),
    })
    return oid


async def _insert_incident(session, env, incident_date):
    """Insert a preschool_incident via admin session."""
    iid = uuid4()
    await session.execute(text("""
        INSERT INTO preschool_incidents
            (id, tenant_id, student_id, school_id,
             incident_type, severity, status,
             incident_date, description, reported_by,
             created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
            CAST(:school_id AS uuid),
            'accident', 'minor', 'reported',
            :inc_date, 'Minor scrape during play', CAST(:uid AS uuid),
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "id": str(iid), "tid": str(env["tenant_id"]),
        "sid": str(env["student_id"]),
        "school_id": str(env["school_id"]),
        "inc_date": incident_date, "uid": str(env["user_id"]),
    })
    return iid


async def _insert_learning_story(session, env, created_at):
    """Insert a learning_story via admin session."""
    sid = uuid4()
    await session.execute(text("""
        INSERT INTO learning_stories
            (id, tenant_id, student_id, title, narrative,
             is_shared_with_parents, created_by,
             created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
            :title, :narrative, true, CAST(:uid AS uuid),
            :created_at, CURRENT_TIMESTAMP)
    """), {
        "id": str(sid), "tid": str(env["tenant_id"]),
        "sid": str(env["student_id"]),
        "title": f"Story from {created_at.date()}",
        "narrative": "A wonderful day of building and exploring new concepts together.",
        "uid": str(env["user_id"]),
        "created_at": created_at,
    })
    return sid


@pytest.mark.asyncio
class TestStudentTimeline:
    """Test unified student timeline aggregation."""

    async def test_timeline_aggregation(self, admin_session, app_session):
        """Timeline includes entries from all 4 source tables."""
        env = await _seed_timeline_env(admin_session)

        # Insert one record in each of the 4 tables
        await _insert_assessment(admin_session, env, datetime(2026, 3, 10, 10, 0))
        await _insert_observation(admin_session, env, date(2026, 3, 11))
        await _insert_incident(admin_session, env, date(2026, 3, 12))
        await _insert_learning_story(admin_session, env, datetime(2026, 3, 13, 9, 0))
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        timeline = await service.get_student_timeline(
            env["tenant_id"], env["student_id"],
        )

        assert len(timeline) == 4

        # Verify all 4 types are present
        types = {entry["type"] for entry in timeline}
        assert types == {"assessment", "observation", "incident", "learning_story"}

    async def test_timeline_sorted_by_date_desc(self, admin_session, app_session):
        """Timeline entries are sorted by date descending (newest first)."""
        env = await _seed_timeline_env(admin_session)

        # Insert entries with specific dates to verify ordering
        await _insert_observation(admin_session, env, date(2026, 1, 5))
        await _insert_incident(admin_session, env, date(2026, 3, 20))
        await _insert_learning_story(admin_session, env, datetime(2026, 2, 15, 12, 0))
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        timeline = await service.get_student_timeline(
            env["tenant_id"], env["student_id"],
        )

        assert len(timeline) == 3
        dates = [entry["date"] for entry in timeline]
        # Verify descending order
        assert dates == sorted(dates, reverse=True)
        assert dates[0] == date(2026, 3, 20)  # incident (newest)
        assert dates[-1] == date(2026, 1, 5)   # observation (oldest)

    async def test_timeline_date_range_filter(self, admin_session, app_session):
        """Timeline respects date_from and date_to filters."""
        env = await _seed_timeline_env(admin_session)

        # Insert entries across a range of dates
        await _insert_observation(admin_session, env, date(2026, 1, 10))
        await _insert_incident(admin_session, env, date(2026, 2, 15))
        await _insert_learning_story(admin_session, env, datetime(2026, 3, 20, 8, 0))
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        # Filter to February only
        timeline = await service.get_student_timeline(
            env["tenant_id"], env["student_id"],
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
        )

        assert len(timeline) == 1
        assert timeline[0]["type"] == "incident"
        assert timeline[0]["date"] == date(2026, 2, 15)

    async def test_timeline_type_fields(self, admin_session, app_session):
        """Each timeline entry has the correct type string and required fields."""
        env = await _seed_timeline_env(admin_session)

        await _insert_assessment(admin_session, env, datetime(2026, 3, 1, 9, 0))
        await _insert_observation(admin_session, env, date(2026, 3, 2))
        await _insert_incident(admin_session, env, date(2026, 3, 3))
        await _insert_learning_story(admin_session, env, datetime(2026, 3, 4, 10, 0))
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        timeline = await service.get_student_timeline(
            env["tenant_id"], env["student_id"],
        )

        for entry in timeline:
            # Every entry must have these core fields
            assert "date" in entry
            assert "type" in entry
            assert "title" in entry
            assert "details" in entry
            assert "id" in entry
            assert entry["type"] in {"assessment", "observation", "incident", "learning_story"}

    async def test_timeline_empty_student(self, admin_session, app_session):
        """Student with no records returns an empty timeline."""
        env = await _seed_timeline_env(admin_session)
        # No records inserted — just the seed env

        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPortfolioService(app_session)

        timeline = await service.get_student_timeline(
            env["tenant_id"], env["student_id"],
        )

        assert len(timeline) == 0

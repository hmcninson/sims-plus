"""
SIMS Plus - Preschool Phase 2 RLS Tests

Verifies Row-Level Security tenant isolation for the 3 new Phase 2 tables:
learning_stories, extended_care_sessions, class_caregiver_ratios.

Pattern: insert data for tenant A via admin session (bypasses RLS), then
query as tenant B via app session (RLS enforced) — expect 0 rows visible.

Uses admin_session for seeding, app_session with RLS for verification.
"""

import pytest
from datetime import date, time
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _seed_rls_env(session: AsyncSession) -> dict:
    """Seed a complete tenant environment for RLS tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    class_id = uuid4()
    student_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "RLS Test Preschool", "slug": f"rls-{uuid4().hex[:8]}",
    })
    await session.execute(_ACADEMIC_YEAR_INSERT, {
        "id": str(ay_id), "tid": str(tid), "name": "2025/2026",
        "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_id), "tid": str(tid),
        "name": "KG 1", "level": "kg_1", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student_id), "tid": str(tid), "sid": "RLS-001",
        "fn": "Akua", "ln": "Osei", "cid": str(class_id),
        "school_id": str(school_id),
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "ay_id": ay_id,
        "class_id": class_id,
        "student_id": student_id,
        "user_id": user["id"],
    }


@pytest.mark.asyncio
class TestPreschoolPhase2RLS:
    """Verify RLS tenant isolation on Phase 2 preschool tables."""

    async def test_learning_story_tenant_isolation(self, admin_session, app_session):
        """Learning stories from tenant A are invisible to tenant B."""
        env_a = await _seed_rls_env(admin_session)

        # Insert a learning story for tenant A via admin (bypasses RLS)
        story_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO learning_stories
                (id, tenant_id, student_id, title, narrative,
                 is_shared_with_parents, created_by,
                 created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Tenant A only story', 'This story belongs to tenant A exclusively.',
                true, CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(story_id),
            "tid": str(env_a["tenant_id"]),
            "sid": str(env_a["student_id"]),
            "uid": str(env_a["user_id"]),
        })
        await admin_session.commit()

        # Verify tenant A can see it
        await set_app_tenant_context(app_session, env_a["tenant_id"])
        result_a = await app_session.execute(
            text("SELECT count(*) FROM learning_stories")
        )
        assert result_a.scalar() == 1

        # Create tenant B and verify isolation
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result_b = await app_session.execute(
            text("SELECT count(*) FROM learning_stories")
        )
        assert result_b.scalar() == 0, (
            "Tenant B must not see tenant A's learning stories"
        )

    async def test_extended_care_tenant_isolation(self, admin_session, app_session):
        """Extended care sessions from tenant A are invisible to tenant B."""
        env_a = await _seed_rls_env(admin_session)

        # Insert an extended care session for tenant A via admin
        session_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO extended_care_sessions
                (id, tenant_id, student_id, session_date, session_type,
                 check_in_time, checked_in_by,
                 created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CURRENT_DATE, 'before_care',
                '07:30:00', CAST(:uid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(session_id),
            "tid": str(env_a["tenant_id"]),
            "sid": str(env_a["student_id"]),
            "uid": str(env_a["user_id"]),
        })
        await admin_session.commit()

        # Verify tenant A can see it
        await set_app_tenant_context(app_session, env_a["tenant_id"])
        result_a = await app_session.execute(
            text("SELECT count(*) FROM extended_care_sessions")
        )
        assert result_a.scalar() == 1

        # Create tenant B and verify isolation
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result_b = await app_session.execute(
            text("SELECT count(*) FROM extended_care_sessions")
        )
        assert result_b.scalar() == 0, (
            "Tenant B must not see tenant A's extended care sessions"
        )

    async def test_caregiver_ratio_tenant_isolation(self, admin_session, app_session):
        """Caregiver ratios from tenant A are invisible to tenant B."""
        env_a = await _seed_rls_env(admin_session)

        # Insert a caregiver ratio for tenant A via admin
        ratio_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO class_caregiver_ratios
                (id, tenant_id, class_id, academic_year_id,
                 max_children_per_caregiver, current_caregiver_count,
                 created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), CAST(:ay_id AS uuid),
                10, 2,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(ratio_id),
            "tid": str(env_a["tenant_id"]),
            "cid": str(env_a["class_id"]),
            "ay_id": str(env_a["ay_id"]),
        })
        await admin_session.commit()

        # Verify tenant A can see it
        await set_app_tenant_context(app_session, env_a["tenant_id"])
        result_a = await app_session.execute(
            text("SELECT count(*) FROM class_caregiver_ratios")
        )
        assert result_a.scalar() == 1

        # Create tenant B and verify isolation
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result_b = await app_session.execute(
            text("SELECT count(*) FROM class_caregiver_ratios")
        )
        assert result_b.scalar() == 0, (
            "Tenant B must not see tenant A's caregiver ratios"
        )

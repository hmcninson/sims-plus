"""
SIMS Plus - Preschool Session-Based Fee Tests

Tests verify that session_type on fee_structures and enrollment_session
on students are stored correctly. Uses raw SQL for fee_structure inserts
(no service method for fee_structures with session_type filtering yet).

Uses admin_session for seeding, app_session with RLS for assertions.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ============================================================
# SQL templates
# ============================================================

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        :school_type, 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_CLASS_INSERT = text("""
    INSERT INTO classes (id, tenant_id, name, level, sequence,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :level, :seq,
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

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
        date_of_birth, gender, status, class_id, school_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_session_fee_env(session: AsyncSession) -> dict:
    """Seed environment for session fee tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_preschool_id = uuid4()
    class_primary_id = uuid4()
    student_preschool_id = uuid4()
    student_primary_id = uuid4()

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Test School", "slug": f"ts-{uuid4().hex[:8]}",
        "school_type": "basic",
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
        "id": str(class_preschool_id), "tid": str(tid),
        "name": "KG 1", "level": "kg_1", "seq": 1,
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_primary_id), "tid": str(tid),
        "name": "Primary 1", "level": "primary_1", "seq": 6,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student_preschool_id), "tid": str(tid), "sid": "PRE-001",
        "fn": "Esi", "ln": "Owusu", "cid": str(class_preschool_id),
        "school_id": str(school_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student_primary_id), "tid": str(tid), "sid": "PRI-001",
        "fn": "Kofi", "ln": "Mensah", "cid": str(class_primary_id),
        "school_id": str(school_id),
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_preschool_id": class_preschool_id,
        "class_primary_id": class_primary_id,
        "student_preschool_id": student_preschool_id,
        "student_primary_id": student_primary_id,
    }


@pytest.mark.asyncio
class TestSessionFees:
    """Test session-based fee structure filtering."""

    async def test_fee_structure_with_session_type(self, admin_session):
        """Create fee structure with session_type='half_day_morning'."""
        env = await _seed_session_fee_env(admin_session)

        fs_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO fee_structures (id, tenant_id, name, class_id, term_id,
                academic_year_id, school_id, session_type,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                CAST(:cid AS uuid), CAST(:term_id AS uuid),
                CAST(:ay_id AS uuid), CAST(:school_id AS uuid),
                :session_type,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(fs_id), "tid": str(env["tenant_id"]),
            "name": "KG1 Half Day Morning Fees", "cid": str(env["class_preschool_id"]),
            "term_id": str(env["term_id"]), "ay_id": str(env["ay_id"]),
            "school_id": str(env["school_id"]),
            "session_type": "half_day_morning",
        })
        await admin_session.commit()

        # Verify it's stored correctly
        result = await admin_session.execute(text(
            "SELECT session_type FROM fee_structures WHERE id = CAST(:id AS uuid)"
        ), {"id": str(fs_id)})
        row = result.one()
        assert row[0] == "half_day_morning"

    async def test_fee_structure_null_session_applies_to_all(self, admin_session):
        """Fee structure with NULL session_type applies to all students."""
        env = await _seed_session_fee_env(admin_session)

        fs_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO fee_structures (id, tenant_id, name, class_id, term_id,
                academic_year_id, school_id, session_type,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                CAST(:cid AS uuid), CAST(:term_id AS uuid),
                CAST(:ay_id AS uuid), CAST(:school_id AS uuid),
                NULL,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(fs_id), "tid": str(env["tenant_id"]),
            "name": "KG1 General Fees", "cid": str(env["class_preschool_id"]),
            "term_id": str(env["term_id"]), "ay_id": str(env["ay_id"]),
            "school_id": str(env["school_id"]),
        })
        await admin_session.commit()

        result = await admin_session.execute(text(
            "SELECT session_type FROM fee_structures WHERE id = CAST(:id AS uuid)"
        ), {"id": str(fs_id)})
        row = result.one()
        assert row[0] is None  # NULL means applies to all

    async def test_student_enrollment_session_set(self, admin_session, app_session):
        """Set enrollment_session on a preschool student."""
        env = await _seed_session_fee_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        await app_session.execute(text("""
            UPDATE students SET enrollment_session = :session
            WHERE id = CAST(:id AS uuid)
        """), {
            "session": "full_day",
            "id": str(env["student_preschool_id"]),
        })
        await app_session.flush()

        result = await app_session.execute(text(
            "SELECT enrollment_session FROM students WHERE id = CAST(:id AS uuid)"
        ), {"id": str(env["student_preschool_id"])})
        row = result.one()
        assert row[0] == "full_day"

    async def test_enrollment_session_null_for_non_preschool(self, admin_session, app_session):
        """enrollment_session remains NULL for non-preschool students."""
        env = await _seed_session_fee_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        result = await app_session.execute(text(
            "SELECT enrollment_session FROM students WHERE id = CAST(:id AS uuid)"
        ), {"id": str(env["student_primary_id"])})
        row = result.one()
        assert row[0] is None

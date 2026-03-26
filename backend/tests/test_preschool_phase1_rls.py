"""
SIMS Plus - Preschool Phase 1 RLS Isolation Tests

Verifies Row-Level Security for Phase 1 preschool tables:
preschool_incidents, authorized_pickups, pickup_logs.

Uses admin_session (superuser) for seeding data across tenants,
app_session (sims_app_user) with RLS enforced for assertions.
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
)


# ============================================================
# SQL templates
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
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_GUARDIAN_INSERT = text("""
    INSERT INTO guardians (id, tenant_id, first_name, last_name, phone,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :fn, :ln, :phone,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_GUARDIAN_INSERT = text("""
    INSERT INTO student_guardians (id, tenant_id, student_id, guardian_id,
        relationship, is_primary, can_pickup, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
        CAST(:gid AS uuid), 'mother', true, true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_two_tenants(session: AsyncSession) -> dict:
    """Seed two isolated tenants with schools, classes, and students."""
    tenant_a = await create_test_tenant(session, subdomain=f"rls-a-{uuid4().hex[:8]}")
    tenant_b = await create_test_tenant(session, subdomain=f"rls-b-{uuid4().hex[:8]}")
    tid_a = tenant_a["id"]
    tid_b = tenant_b["id"]

    school_a = uuid4()
    school_b = uuid4()
    class_a = uuid4()
    class_b = uuid4()
    student_a = uuid4()
    student_b = uuid4()
    user_a = await create_test_user(session, tid_a)
    user_b = await create_test_user(session, tid_b)
    guardian_a = uuid4()

    for tid, sid, slug, sch_id, c_id, st_id in [
        (tid_a, "A-001", f"sa-{uuid4().hex[:8]}", school_a, class_a, student_a),
        (tid_b, "B-001", f"sb-{uuid4().hex[:8]}", school_b, class_b, student_b),
    ]:
        await session.execute(_SCHOOL_INSERT, {
            "id": str(sch_id), "tid": str(tid),
            "name": f"School {slug}", "slug": slug,
        })
        await session.execute(_CLASS_INSERT, {
            "id": str(c_id), "tid": str(tid),
            "name": "KG 1", "level": "kg_1", "seq": 1,
        })
        await session.execute(_STUDENT_INSERT, {
            "id": str(st_id), "tid": str(tid), "sid": sid,
            "fn": "Child", "ln": slug[:5], "cid": str(c_id),
            "school_id": str(sch_id),
        })

    # Guardian for tenant A's student (needed for pickup log tests)
    await session.execute(_GUARDIAN_INSERT, {
        "id": str(guardian_a), "tid": str(tid_a),
        "fn": "ParentA", "ln": "Test", "phone": "+233200001111",
    })
    await session.execute(_STUDENT_GUARDIAN_INSERT, {
        "id": str(uuid4()), "tid": str(tid_a),
        "sid": str(student_a), "gid": str(guardian_a),
    })

    await session.commit()

    return {
        "tid_a": tid_a, "tid_b": tid_b,
        "school_a": school_a, "school_b": school_b,
        "class_a": class_a, "class_b": class_b,
        "student_a": student_a, "student_b": student_b,
        "user_a_id": user_a["id"], "user_b_id": user_b["id"],
        "guardian_a": guardian_a,
    }


@pytest.mark.asyncio
class TestPreschoolPhase1RLS:
    """Verify RLS isolation for Phase 1 preschool tables."""

    async def test_incident_tenant_isolation(self, admin_session, app_session):
        """Incidents from tenant A are invisible to tenant B."""
        env = await _seed_two_tenants(admin_session)

        # Insert incident for tenant A via admin (bypasses RLS)
        await admin_session.execute(text("""
            INSERT INTO preschool_incidents (id, tenant_id, student_id,
                incident_type, severity, status, incident_date, description,
                school_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'accident', 'minor', 'reported', '2026-03-20',
                'Test incident for RLS verification',
                CAST(:school_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(uuid4()), "tid": str(env["tid_a"]),
            "sid": str(env["student_a"]), "school_id": str(env["school_a"]),
        })
        await admin_session.commit()

        # Set context to tenant B
        await set_app_tenant_context(app_session, env["tid_b"])

        result = await app_session.execute(
            text("SELECT COUNT(*) FROM preschool_incidents")
        )
        count = result.scalar()
        assert count == 0, f"Expected 0 incidents for tenant B, got {count}"

    async def test_authorized_pickup_tenant_isolation(self, admin_session, app_session):
        """Authorized pickups from tenant A are invisible to tenant B."""
        env = await _seed_two_tenants(admin_session)

        await admin_session.execute(text("""
            INSERT INTO authorized_pickups (id, tenant_id, student_id,
                full_name, phone, is_active, school_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Auntie Akua', '+233241112222', true,
                CAST(:school_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(uuid4()), "tid": str(env["tid_a"]),
            "sid": str(env["student_a"]), "school_id": str(env["school_a"]),
        })
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tid_b"])

        result = await app_session.execute(
            text("SELECT COUNT(*) FROM authorized_pickups")
        )
        count = result.scalar()
        assert count == 0, f"Expected 0 authorized pickups for tenant B, got {count}"

    async def test_pickup_log_tenant_isolation(self, admin_session, app_session):
        """Pickup logs from tenant A are invisible to tenant B."""
        env = await _seed_two_tenants(admin_session)

        await admin_session.execute(text("""
            INSERT INTO pickup_logs (id, tenant_id, student_id,
                pickup_date, pickup_time, picked_up_by_type,
                picked_up_by_guardian_id, school_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                '2026-03-20', '15:00:00', 'guardian',
                CAST(:gid AS uuid), CAST(:school_id AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(uuid4()), "tid": str(env["tid_a"]),
            "sid": str(env["student_a"]), "gid": str(env["guardian_a"]),
            "school_id": str(env["school_a"]),
        })
        await admin_session.commit()

        await set_app_tenant_context(app_session, env["tid_b"])

        result = await app_session.execute(
            text("SELECT COUNT(*) FROM pickup_logs")
        )
        count = result.scalar()
        assert count == 0, f"Expected 0 pickup logs for tenant B, got {count}"

    async def test_cross_tenant_incident_insert_blocked(self, admin_session, app_session):
        """Cannot insert an incident for a different tenant via RLS WITH CHECK."""
        env = await _seed_two_tenants(admin_session)

        # Set context to tenant A
        await set_app_tenant_context(app_session, env["tid_a"])

        # Try to insert incident with tenant B's tenant_id -- RLS should block
        with pytest.raises(Exception) as exc_info:
            await app_session.execute(text("""
                INSERT INTO preschool_incidents (id, tenant_id, student_id,
                    incident_type, severity, status, incident_date, description,
                    school_id, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    'accident', 'minor', 'reported', '2026-03-20',
                    'This should be blocked by RLS',
                    CAST(:school_id AS uuid),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                "id": str(uuid4()), "tid": str(env["tid_b"]),
                "sid": str(env["student_b"]), "school_id": str(env["school_b"]),
            })

        # Should be a policy violation error
        assert "policy" in str(exc_info.value).lower() or "permission" in str(exc_info.value).lower()

    async def test_dietary_requirements_via_students_rls(self, admin_session, app_session):
        """dietary_requirements on students table inherits existing students RLS."""
        env = await _seed_two_tenants(admin_session)

        # Set dietary data for tenant A's student via admin
        await admin_session.execute(text("""
            UPDATE students SET dietary_requirements = '{"allergies": [{"allergen": "peanuts", "severity": "severe"}]}'::jsonb
            WHERE id = CAST(:id AS uuid)
        """), {"id": str(env["student_a"])})
        await admin_session.commit()

        # Set context to tenant B -- should not see tenant A's student data
        await set_app_tenant_context(app_session, env["tid_b"])

        result = await app_session.execute(text(
            "SELECT dietary_requirements FROM students WHERE dietary_requirements IS NOT NULL"
        ))
        rows = result.fetchall()
        assert len(rows) == 0, "Tenant B should not see tenant A's dietary data"

"""
SIMS Plus - Preschool Allergy Alert Tests

Tests exercise the PreschoolPickupService dietary/allergy methods directly
against a real PostgreSQL database.

Covers: update dietary requirements, clear, class-level allergy alerts,
empty alerts, restrictions-only, student not found.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolPickupService, PreschoolServiceError

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


async def _seed_allergy_env(session: AsyncSession) -> dict:
    """Seed environment for allergy tests."""
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    class_id = uuid4()
    student1_id = uuid4()
    student2_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Preschool Academy", "slug": f"ps-{uuid4().hex[:8]}",
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
        "class_id": class_id,
        "student1_id": student1_id,
        "student2_id": student2_id,
        "user_id": user["id"],
    }


@pytest.mark.asyncio
class TestAllergyAlerts:
    """Test dietary requirements and allergy alert system."""

    async def test_update_dietary_requirements(self, admin_session, app_session):
        """Set structured dietary requirements for a student."""
        env = await _seed_allergy_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        dietary_data = {
            "allergies": [
                {"allergen": "peanuts", "severity": "severe", "reaction": "anaphylaxis"},
                {"allergen": "dairy", "severity": "moderate"},
            ],
            "dietary_restrictions": ["vegetarian"],
            "notes": "Carries EpiPen in bag",
        }

        await service.update_dietary_requirements(
            env["tenant_id"], env["student1_id"], dietary_data,
        )

        result = await service.get_student_dietary_requirements(
            env["tenant_id"], env["student1_id"],
        )
        assert result is not None
        assert len(result["allergies"]) == 2
        assert result["allergies"][0]["allergen"] == "peanuts"
        assert result["dietary_restrictions"] == ["vegetarian"]
        assert result["notes"] == "Carries EpiPen in bag"

    async def test_clear_dietary_requirements(self, admin_session, app_session):
        """Clear dietary requirements by setting to None."""
        env = await _seed_allergy_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        # Set then clear
        await service.update_dietary_requirements(
            env["tenant_id"], env["student1_id"],
            {"allergies": [{"allergen": "gluten", "severity": "mild"}]},
        )
        await service.update_dietary_requirements(
            env["tenant_id"], env["student1_id"], None,
        )

        result = await service.get_student_dietary_requirements(
            env["tenant_id"], env["student1_id"],
        )
        assert result is None

    async def test_get_class_allergy_alerts(self, admin_session, app_session):
        """Get allergy alerts for a class -- only students with allergies."""
        env = await _seed_allergy_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        # Student 1 has allergies
        await service.update_dietary_requirements(
            env["tenant_id"], env["student1_id"],
            {
                "allergies": [
                    {"allergen": "peanuts", "severity": "severe"},
                    {"allergen": "dairy", "severity": "moderate"},
                ],
                "dietary_restrictions": [],
            },
        )
        # Student 2 has no dietary data

        alerts = await service.get_class_allergy_alerts(
            env["tenant_id"], env["class_id"],
        )
        assert len(alerts) == 1
        assert alerts[0]["student_name"] == "Esi Owusu"
        assert len(alerts[0]["allergies"]) == 2

    async def test_class_allergy_alerts_empty(self, admin_session, app_session):
        """Empty list when no students have allergies."""
        env = await _seed_allergy_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        alerts = await service.get_class_allergy_alerts(
            env["tenant_id"], env["class_id"],
        )
        assert len(alerts) == 0

    async def test_dietary_restrictions_only(self, admin_session, app_session):
        """Student with dietary restrictions but no allergies still shows in alerts."""
        env = await _seed_allergy_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        await service.update_dietary_requirements(
            env["tenant_id"], env["student1_id"],
            {"allergies": [], "dietary_restrictions": ["vegetarian"]},
        )

        alerts = await service.get_class_allergy_alerts(
            env["tenant_id"], env["class_id"],
        )
        assert len(alerts) == 1
        assert alerts[0]["dietary_restrictions"] == ["vegetarian"]

    async def test_student_not_found(self, admin_session, app_session):
        """Error when student doesn't belong to tenant."""
        env = await _seed_allergy_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.update_dietary_requirements(
                env["tenant_id"], uuid4(), {"allergies": []},
            )
        assert exc_info.value.code == "STUDENT_NOT_FOUND"

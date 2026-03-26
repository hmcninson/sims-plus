"""
Tests for GradeEquivalencyService.

Covers: create batch, self-mapping rejection, plan limit enforcement,
list with filters, convert grade lookup, hard delete, and school_id assignment.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

from app.services.curriculum.equivalency_service import GradeEquivalencyService
from app.services.curriculum._shared import CurriculumServiceError
from app.schemas.curriculum import (
    GradeEquivalencyCreate,
    GradeEquivalencyUpdate,
    GradeMapping,
    GradeConvertRequest,
)

pytestmark = [pytest.mark.asyncio]


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_with_tier(admin_session, tier: str):
    tenant_id = uuid4()
    sub = f"test{uuid4().hex[:8]}"
    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                true, 'single_school', :tier, 500,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub,
         "name": f"School {sub}", "tier": tier},
    )
    await admin_session.flush()
    return {"id": tenant_id, "subdomain": sub}


async def _seed_two_scales_with_grades(admin_session, tenant_id):
    """Create two grading scales each with one grade. Returns dict of IDs."""
    scale_a_id = uuid4()
    scale_b_id = uuid4()
    grade_a_id = uuid4()
    grade_b_id = uuid4()

    for scale_id, name in [(scale_a_id, "WAEC"), (scale_b_id, "Cambridge")]:
        await admin_session.execute(
            text("""
                INSERT INTO grading_scales (id, tenant_id, name, is_default,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(scale_id), "tid": str(tenant_id), "name": f"{name}-{uuid4().hex[:6]}"},
        )

    for grade_id, scale_id, grade_val, min_s, max_s in [
        (grade_a_id, scale_a_id, "A1", 80, 100),
        (grade_b_id, scale_b_id, "A*", 90, 100),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO grades (id, tenant_id, grading_scale_id,
                    grade, min_score, max_score, grade_point,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:gsid AS uuid), :grade, :min_s, :max_s, 4.0,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(grade_id), "tid": str(tenant_id),
             "gsid": str(scale_id), "grade": grade_val,
             "min_s": min_s, "max_s": max_s},
        )

    return {
        "scale_a_id": scale_a_id,
        "scale_b_id": scale_b_id,
        "grade_a_id": grade_a_id,
        "grade_b_id": grade_b_id,
    }


async def _seed_school(admin_session, tenant_id):
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"sch-{uuid4().hex[:8]}"},
    )
    return school_id


class TestCreateEquivalency:
    """Test grade equivalency batch creation."""

    async def test_create_equivalency_happy_path(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_b_id"],
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_b_id"],
                    notes="WAEC A1 = Cambridge A*",
                ),
            ],
        )
        created = await svc.create_equivalency(data, tenant["id"], school_id)

        assert len(created) == 1
        assert created[0].source_grade_id == scales["grade_a_id"]
        assert created[0].target_grade_id == scales["grade_b_id"]
        assert created[0].school_id == school_id

    async def test_self_mapping_rejected(self, app_session, admin_session):
        """Cannot map a scale to itself."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_a_id"],  # Same!
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_a_id"],
                ),
            ],
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_equivalency(data, tenant["id"])
        assert exc.value.code == "self_mapping"


class TestPlanLimits:
    """Grade equivalencies require Professional+ plan."""

    async def test_trial_tenant_blocked(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)  # trial
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_b_id"],
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_b_id"],
                ),
            ],
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_equivalency(data, tenant["id"])
        assert exc.value.code == "plan_limit"

    async def test_starter_tenant_blocked(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "starter")
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_b_id"],
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_b_id"],
                ),
            ],
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_equivalency(data, tenant["id"])
        assert exc.value.code == "plan_limit"


class TestListAndConvert:
    """Test listing equivalencies and grade conversion."""

    async def test_list_with_scale_filter(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_b_id"],
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_b_id"],
                ),
            ],
        )
        await svc.create_equivalency(data, tenant["id"])

        # Filter by source scale
        results, total = await svc.get_equivalencies(
            tenant["id"], source_scale_id=scales["scale_a_id"],
        )
        assert total == 1
        assert results[0].source_grading_scale_id == scales["scale_a_id"]

        # Filter by non-matching source scale
        results2, total2 = await svc.get_equivalencies(
            tenant["id"], source_scale_id=scales["scale_b_id"],
        )
        assert total2 == 0

    async def test_convert_grade_lookup(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_b_id"],
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_b_id"],
                ),
            ],
        )
        await svc.create_equivalency(data, tenant["id"])

        result = await svc.convert_grade(
            source_grade_id=scales["grade_a_id"],
            source_scale_id=scales["scale_a_id"],
            target_scale_id=scales["scale_b_id"],
            tenant_id=tenant["id"],
        )
        assert result is not None
        assert result.target_grade_id == scales["grade_b_id"]


class TestDeleteEquivalency:
    """Test hard deletion of equivalencies."""

    async def test_hard_delete(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        scales = await _seed_two_scales_with_grades(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = GradeEquivalencyService(app_session)

        data = GradeEquivalencyCreate(
            source_grading_scale_id=scales["scale_a_id"],
            target_grading_scale_id=scales["scale_b_id"],
            mappings=[
                GradeMapping(
                    source_grade_id=scales["grade_a_id"],
                    target_grade_id=scales["grade_b_id"],
                ),
            ],
        )
        created = await svc.create_equivalency(data, tenant["id"])
        eq_id = created[0].id

        await svc.delete_equivalency(eq_id, tenant["id"])

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.get_equivalency(eq_id, tenant["id"])
        assert exc.value.code == "not_found"

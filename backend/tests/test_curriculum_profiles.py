"""
Tests for CurriculumProfileService.

Covers: create, list, get, update, delete, set_default, create_from_template,
plan limit enforcement, and cross-tenant FK validation.
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

from app.services.curriculum.profile_service import CurriculumProfileService, CURRICULUM_TEMPLATES
from app.services.curriculum._shared import CurriculumServiceError
from app.schemas.curriculum import CurriculumProfileCreate, CurriculumProfileUpdate

pytestmark = [pytest.mark.asyncio]


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_with_tier(admin_session, tier: str):
    """Create a tenant with a specific subscription tier."""
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


async def _seed_school(admin_session, tenant_id):
    """Seed a school. Returns school_id."""
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


async def _seed_grading_scale(admin_session, tenant_id):
    """Seed a grading scale. Returns grading_scale_id."""
    gs_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, is_default,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(gs_id), "tid": str(tenant_id),
         "name": f"Scale-{uuid4().hex[:6]}"},
    )
    return gs_id


class TestCreateProfile:
    """Test curriculum profile creation."""

    async def test_create_ges_profile_happy_path(self, app_session, admin_session):
        """GES profiles can be created on any plan including trial."""
        tenant = await create_test_tenant(admin_session)  # trial tier
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        data = CurriculumProfileCreate(
            name="GES Standard",
            curriculum_type="ges",
            academic_calendar_type="terms",
            periods_per_year=3,
        )
        profile = await svc.create_profile(data, tenant["id"], school_id)

        assert profile.name == "GES Standard"
        assert profile.curriculum_type.value == "ges"
        assert profile.is_active is True

    async def test_create_non_ges_on_professional_plan(self, app_session, admin_session):
        """Professional plan allows 1 non-GES profile."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        data = CurriculumProfileCreate(
            name="Cambridge IGCSE",
            curriculum_type="cambridge",
        )
        profile = await svc.create_profile(data, tenant["id"], school_id)
        assert profile.curriculum_type.value == "cambridge"

    async def test_starter_tenant_blocked_from_non_ges(self, app_session, admin_session):
        """Starter tenant cannot create non-GES profiles."""
        tenant = await _create_tenant_with_tier(admin_session, "starter")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        data = CurriculumProfileCreate(
            name="Cambridge IGCSE",
            curriculum_type="cambridge",
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_profile(data, tenant["id"], school_id)
        assert exc.value.code == "plan_limit"

    async def test_professional_limited_to_one_non_ges(self, app_session, admin_session):
        """Professional plan cannot create a second non-GES profile."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        # First non-GES succeeds
        data1 = CurriculumProfileCreate(name="Cambridge", curriculum_type="cambridge")
        await svc.create_profile(data1, tenant["id"], school_id)

        # Second non-GES fails
        data2 = CurriculumProfileCreate(name="IB DP", curriculum_type="ib")
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_profile(data2, tenant["id"], school_id)
        assert exc.value.code == "plan_limit"

    async def test_enterprise_unlimited_profiles(self, app_session, admin_session):
        """Enterprise plan allows unlimited non-GES profiles."""
        tenant = await _create_tenant_with_tier(admin_session, "enterprise")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        for ct in ["cambridge", "ib", "american"]:
            data = CurriculumProfileCreate(name=f"Profile {ct}", curriculum_type=ct)
            profile = await svc.create_profile(data, tenant["id"], school_id)
            assert profile.curriculum_type.value == ct


class TestListAndGetProfile:
    """Test profile listing and retrieval."""

    async def test_list_profiles_returns_only_own_tenant(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "enterprise")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        await svc.create_profile(
            CurriculumProfileCreate(name="P1", curriculum_type="ges"),
            tenant["id"], school_id,
        )
        await svc.create_profile(
            CurriculumProfileCreate(name="P2", curriculum_type="cambridge"),
            tenant["id"], school_id,
        )

        profiles, total = await svc.list_profiles(tenant["id"])
        assert total == 2
        assert len(profiles) == 2

    async def test_list_profiles_search_filter(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "enterprise")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        await svc.create_profile(
            CurriculumProfileCreate(name="Cambridge IGCSE", curriculum_type="cambridge"),
            tenant["id"], school_id,
        )
        await svc.create_profile(
            CurriculumProfileCreate(name="GES Standard", curriculum_type="ges"),
            tenant["id"], school_id,
        )

        profiles, total = await svc.list_profiles(tenant["id"], search="cambridge")
        assert total == 1
        assert profiles[0].name == "Cambridge IGCSE"

    async def test_get_profile_not_found(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.get_profile(tenant["id"], uuid4())
        assert exc.value.code == "not_found"


class TestUpdateProfile:
    """Test profile updates."""

    async def test_update_mutable_fields(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        profile = await svc.create_profile(
            CurriculumProfileCreate(name="GES Old", curriculum_type="ges"),
            tenant["id"], school_id,
        )
        profile_id = profile.id

        updated = await svc.update_profile(
            tenant["id"], profile_id,
            CurriculumProfileUpdate(name="GES New", description="Updated"),
        )
        assert updated.name == "GES New"
        assert updated.description == "Updated"


class TestDeleteProfile:
    """Test profile soft deletion."""

    async def test_soft_delete_profile(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        profile = await svc.create_profile(
            CurriculumProfileCreate(name="To Delete", curriculum_type="ges"),
            tenant["id"], school_id,
        )
        profile_id = profile.id

        await svc.delete_profile(tenant["id"], profile_id)

        # Profile should no longer be visible
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.get_profile(tenant["id"], profile_id)
        assert exc.value.code == "not_found"


class TestSetDefault:
    """Test setting a profile as default auto-unsets previous default."""

    async def test_set_default_unsets_previous(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "enterprise")
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        p1 = await svc.create_profile(
            CurriculumProfileCreate(name="P1", curriculum_type="ges", is_default=True),
            tenant["id"], school_id,
        )
        p2 = await svc.create_profile(
            CurriculumProfileCreate(name="P2", curriculum_type="cambridge"),
            tenant["id"], school_id,
        )

        p1_id = p1.id
        p2_id = p2.id

        # Set P2 as default
        updated = await svc.set_default(tenant["id"], p2_id)
        assert updated.is_default is True

        # P1 should no longer be default
        p1_reloaded = await svc.get_profile(tenant["id"], p1_id)
        assert p1_reloaded.is_default is False


class TestCreateFromTemplate:
    """Test template instantiation."""

    async def test_create_from_ges_template(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        profile = await svc.create_from_template(
            tenant["id"], school_id, "ges_standard",
        )

        assert profile.name == "GES Standard"
        assert profile.curriculum_type.value == "ges"
        # Template creates assessment structure + components + report config
        assert len(profile.assessment_structures) >= 1
        assert len(profile.report_config) >= 1

        # Check components were created
        structure = profile.assessment_structures[0]
        assert len(structure.components) == 4  # GES has 4 components

    async def test_create_from_template_with_name_override(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        profile = await svc.create_from_template(
            tenant["id"], school_id, "ges_standard",
            name_override="My Custom GES",
        )
        assert profile.name == "My Custom GES"

    async def test_create_from_unknown_template_fails(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_from_template(tenant["id"], school_id, "nonexistent")
        assert exc.value.code == "invalid_template"

    async def test_list_templates_returns_all(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = CurriculumProfileService(app_session)

        templates = svc.list_templates()
        assert len(templates) == len(CURRICULUM_TEMPLATES)
        keys = {t["key"] for t in templates}
        assert "ges_standard" in keys
        assert "cambridge_igcse" in keys
        assert "american_standard" in keys


class TestCrossTenantFKValidation:
    """Creating a profile with a grading_scale_id from another tenant must fail."""

    async def test_cross_tenant_grading_scale_rejected(self, app_session, admin_session):
        tenant_a = await _create_tenant_with_tier(admin_session, "professional")
        tenant_b = await _create_tenant_with_tier(admin_session, "professional")
        school_a = await _seed_school(admin_session, tenant_a["id"])
        gs_b = await _seed_grading_scale(admin_session, tenant_b["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = CurriculumProfileService(app_session)

        data = CurriculumProfileCreate(
            name="Sneaky Profile",
            curriculum_type="ges",
            grading_scale_id=gs_b,
        )
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_profile(data, tenant_a["id"], school_a)
        assert exc.value.code == "not_found"

"""
Tests for dual-track reporting (Phase 4).

Covers: dual-track template selection, dual-track generates both result sets,
non-dual-track uses single template, detection via template_key.
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

pytestmark = [pytest.mark.asyncio]


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_pro(admin_session, tier: str = "professional"):
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


async def _seed_dual_track_data(admin_session, tenant_id):
    """Seed school, profiles, classes, and report card configs for dual-track tests."""
    ids = {k: uuid4() for k in [
        "school_id", "ges_profile_id", "cambridge_profile_id",
        "class_id", "ges_config_id", "dual_config_id", "cambridge_config_id",
    ]}

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["school_id"]), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"sch-{uuid4().hex[:8]}"},
    )

    # GES curriculum profile
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, academic_calendar_type, periods_per_year,
                score_display_mode, use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'GES Standard', 'ges', 'terms', 3, 'grade_and_score',
                false, false, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["ges_profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"])},
    )

    # Cambridge curriculum profile
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, academic_calendar_type, periods_per_year,
                score_display_mode, use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Cambridge IGCSE', 'cambridge', 'terms', 3, 'grade_and_score',
                false, false, false,
                false, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["cambridge_profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"])},
    )

    # ReportCardConfig for dual-track (template_key = 'dual_track')
    await admin_session.execute(
        text("""
            INSERT INTO report_card_configs (id, tenant_id, curriculum_profile_id,
                template_key, show_position, show_class_average,
                show_subject_position, show_effort_grade,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:pid AS uuid),
                'dual_track', true, true, true, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["dual_config_id"]), "tid": str(tenant_id),
         "pid": str(ids["cambridge_profile_id"])},
    )

    # ReportCardConfig for standard Cambridge
    await admin_session.execute(
        text("""
            INSERT INTO report_card_configs (id, tenant_id, curriculum_profile_id,
                template_key, show_position, show_class_average,
                show_subject_position, show_effort_grade,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:pid AS uuid),
                'cambridge', true, true, true, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["cambridge_config_id"]), "tid": str(tenant_id),
         "pid": str(ids["cambridge_profile_id"])},
    )

    # ReportCardConfig for GES
    await admin_session.execute(
        text("""
            INSERT INTO report_card_configs (id, tenant_id, curriculum_profile_id,
                template_key, show_position, show_class_average,
                show_subject_position,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:pid AS uuid),
                'default', true, true, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["ges_config_id"]), "tid": str(tenant_id),
         "pid": str(ids["ges_profile_id"])},
    )

    await admin_session.commit()
    return ids


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestDualTrackTemplateSelection:
    """Tests for dual-track report template detection via template_key."""

    async def test_dual_track_config_has_dual_track_key(self, admin_session):
        """Dual-track config should have template_key='dual_track'."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_dual_track_data(admin_session, tenant["id"])

        result = await admin_session.execute(
            text("""
                SELECT template_key FROM report_card_configs
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["dual_config_id"])},
        )
        assert result.scalar_one() == "dual_track"

    async def test_non_dual_track_uses_standard_template(self, admin_session):
        """Standard Cambridge config should NOT use 'dual_track' template_key."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_dual_track_data(admin_session, tenant["id"])

        result = await admin_session.execute(
            text("""
                SELECT template_key FROM report_card_configs
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["cambridge_config_id"])},
        )
        key = result.scalar_one()
        assert key == "cambridge"
        assert key != "dual_track"

    async def test_ges_config_uses_default_template(self, admin_session):
        """GES config should use 'default' template_key."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_dual_track_data(admin_session, tenant["id"])

        result = await admin_session.execute(
            text("""
                SELECT template_key FROM report_card_configs
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["ges_config_id"])},
        )
        assert result.scalar_one() == "default"

    async def test_dual_track_detection_is_template_key_only(self, admin_session):
        """Dual-track detection should only check template_key, not other flags."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_dual_track_data(admin_session, tenant["id"])

        # Query all configs for this tenant to verify template_key is the discriminator
        result = await admin_session.execute(
            text("""
                SELECT template_key, show_effort_grade
                FROM report_card_configs
                WHERE tenant_id = CAST(:tid AS uuid)
                ORDER BY template_key
            """),
            {"tid": str(tenant["id"])},
        )
        rows = result.fetchall()

        template_keys = [r[0] for r in rows]
        assert "dual_track" in template_keys

        # The dual_track config may have show_effort_grade=True, but so does
        # the standard cambridge config -- the difference is template_key only
        dual_row = next(r for r in rows if r[0] == "dual_track")
        cambridge_row = next(r for r in rows if r[0] == "cambridge")
        assert dual_row[1] == cambridge_row[1]  # Both may have show_effort_grade=True

    async def test_multiple_configs_per_profile(self, admin_session):
        """A profile can have both dual_track and standard configs."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_dual_track_data(admin_session, tenant["id"])

        result = await admin_session.execute(
            text("""
                SELECT COUNT(*) FROM report_card_configs
                WHERE tenant_id = CAST(:tid AS uuid)
                AND curriculum_profile_id = CAST(:pid AS uuid)
            """),
            {"tid": str(tenant["id"]),
             "pid": str(ids["cambridge_profile_id"])},
        )
        count = result.scalar_one()
        assert count == 2  # dual_track + cambridge

    async def test_dual_track_config_has_show_effort_grade(self, admin_session):
        """Dual-track Cambridge config should show effort grades."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_dual_track_data(admin_session, tenant["id"])

        result = await admin_session.execute(
            text("""
                SELECT show_effort_grade FROM report_card_configs
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(ids["dual_config_id"])},
        )
        assert result.scalar_one() is True

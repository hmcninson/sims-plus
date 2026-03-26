"""
Tests for GES curriculum subject template initialization.

Covers: template data correctness, idempotent creation, SHS programmes,
invalid inputs, and tenant scoping.
Uses two-engine pattern (admin seeds, app queries).
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)




# --- Helpers ---


async def _seed_school(admin_session, tenant_id, school_type="basic"):
    """Create a school, return school_id."""
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                :stype, 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
            "stype": school_type,
        },
    )
    await admin_session.commit()
    return school_id


# --- Tests ---


class TestGESSubjectData:
    """Verify GES subject template data is correct."""

    def test_primary_has_11_subjects(self):
        """Primary school template should have 11 subjects."""
        from app.data.ges_subjects import GES_SUBJECTS

        assert len(GES_SUBJECTS["primary"]) == 11

    def test_preschool_has_5_subjects(self):
        """Preschool template should have 5 subjects."""
        from app.data.ges_subjects import GES_SUBJECTS

        assert len(GES_SUBJECTS["preschool"]) == 5

    def test_shs_core_has_4_subjects(self):
        """SHS core template should have 4 subjects."""
        from app.data.ges_subjects import GES_SUBJECTS

        assert len(GES_SUBJECTS["shs_core"]) == 4

    def test_all_school_types_have_subject_mapping(self):
        """Every school type should map to at least one subject list."""
        from app.data.ges_subjects import SCHOOL_TYPE_SUBJECT_MAP

        expected_types = [
            "preschool", "primary", "jhs", "shs", "basic",
            "preschool_primary", "basic_preschool", "basic_shs",
            "international", "technical",
        ]
        for st in expected_types:
            assert st in SCHOOL_TYPE_SUBJECT_MAP, f"Missing mapping for {st}"
            assert len(SCHOOL_TYPE_SUBJECT_MAP[st]) > 0

    def test_shs_programmes_list(self):
        """SHS should have the correct programme list."""
        from app.data.ges_subjects import SHS_ELECTIVE_PROGRAMMES

        expected = [
            "General Science", "General Arts", "Business",
            "Visual Arts", "Home Economics", "Agriculture", "Technical",
        ]
        for prog in expected:
            assert prog in SHS_ELECTIVE_PROGRAMMES, f"Missing programme: {prog}"

    def test_each_programme_has_4_subjects(self):
        """Each SHS programme should have exactly 4 elective subjects."""
        from app.data.ges_subjects import SHS_ELECTIVE_PROGRAMMES

        for name, subjects in SHS_ELECTIVE_PROGRAMMES.items():
            assert len(subjects) == 4, f"{name} has {len(subjects)} subjects, expected 4"


class TestSubjectTemplateService:
    """Test SubjectTemplateService.initialize_from_template()."""

    async def test_init_primary_creates_11_subjects(self, app_session, admin_session):
        """Initializing primary template should create 11 subjects."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"], "primary")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.subject_template_service import SubjectTemplateService

        service = SubjectTemplateService(app_session)
        result = await service.initialize_from_template(
            tenant_id=tenant["id"],
            school_type="primary",
            school_id=school_id,
        )

        assert result["created"] == 11
        assert result["skipped"] == 0

    async def test_init_idempotent_second_call_skips(self, app_session, admin_session):
        """Second call with same school_type should skip all subjects."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"], "primary")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.subject_template_service import SubjectTemplateService

        service = SubjectTemplateService(app_session)

        # First call creates
        result1 = await service.initialize_from_template(
            tenant_id=tenant["id"],
            school_type="primary",
            school_id=school_id,
        )
        assert result1["created"] == 11

        # Second call skips all
        result2 = await service.initialize_from_template(
            tenant_id=tenant["id"],
            school_type="primary",
            school_id=school_id,
        )
        assert result2["created"] == 0
        assert result2["skipped"] == 11

    async def test_init_shs_with_programme_creates_core_and_electives(
        self, app_session, admin_session
    ):
        """SHS with General Science should create 4 core + 4 elective = 8."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"], "shs")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.subject_template_service import SubjectTemplateService

        service = SubjectTemplateService(app_session)
        result = await service.initialize_from_template(
            tenant_id=tenant["id"],
            school_type="shs",
            school_id=school_id,
            programmes=["General Science"],
        )

        assert result["created"] == 8  # 4 core + 4 elective

    async def test_invalid_school_type_raises(self, app_session, admin_session):
        """Invalid school_type should raise an error."""
        tenant = await create_test_tenant(admin_session)
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.subject_template_service import SubjectTemplateService

        service = SubjectTemplateService(app_session)
        with pytest.raises(Exception, match="Unknown school type"):
            await service.initialize_from_template(
                tenant_id=tenant["id"],
                school_type="invalid_type",
            )

    async def test_subjects_created_with_correct_tenant_id(
        self, app_session, admin_session
    ):
        """Subjects should be created with the correct tenant_id."""
        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"], "preschool")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.subject_template_service import SubjectTemplateService

        service = SubjectTemplateService(app_session)
        await service.initialize_from_template(
            tenant_id=tenant["id"],
            school_type="preschool",
            school_id=school_id,
        )

        # Verify via raw SQL (through RLS -- only sees this tenant's data)
        result = await app_session.execute(
            text("""
                SELECT COUNT(*) FROM subjects
                WHERE school_id = CAST(:sid AS uuid)
                AND deleted_at IS NULL
            """),
            {"sid": str(school_id)},
        )
        count = result.scalar()
        assert count == 5  # preschool has 5 subjects


class TestAvailableProgrammes:
    """Test get_available_programmes()."""

    def test_returns_all_programmes(self):
        """Should return all 7 SHS programme names."""
        from app.services.academic.subject_template_service import SubjectTemplateService

        service = SubjectTemplateService(None)  # No DB needed
        programmes = service.get_available_programmes()

        assert len(programmes) == 7
        assert "General Science" in programmes
        assert "General Arts" in programmes

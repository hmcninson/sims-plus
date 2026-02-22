"""
Subject, Grading Scale & Assessment Weight Service Tests

Tests for subject CRUD, class-subject assignments, grading scales,
and assessment weight operations via AcademicService.
Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require a running sims_plus_test database with
RLS policies applied (alembic upgrade head).
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.academic import GradingScaleType, SubjectCategory
from app.services.academic import AcademicService, AcademicServiceError

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("subject_serial"),
]


# =========================
# Subject Tests
# =========================


class TestCreateSubject:
    """Tests for creating subjects."""

    async def test_create_subject_with_category(
        self, app_session, admin_session
    ):
        """New subject is created with correct category."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
            category="core",
        )

        assert subject is not None
        assert subject.name == "Mathematics"
        assert subject.code == "MATH"
        assert subject.category == SubjectCategory.CORE
        assert subject.tenant_id == tenant["id"]
        assert subject.is_active is True

    async def test_create_elective_subject(
        self, app_session, admin_session
    ):
        """Elective subject is created correctly."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="French",
            code="FRN",
            category="elective",
        )

        assert subject.category == SubjectCategory.ELECTIVE

    async def test_subject_code_uppercased(
        self, app_session, admin_session
    ):
        """Subject code is automatically uppercased."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="English Language",
            code="eng",
        )

        assert subject.code == "ENG"

    async def test_create_duplicate_subject_code_raises_error(
        self, app_session, admin_session
    ):
        """Duplicate subject code within same tenant raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_subject(
                tenant_id=tenant["id"],
                name="Advanced Math",
                code="MATH",
            )

        assert exc_info.value.code == "duplicate_subject"


class TestListSubjects:
    """Tests for listing subjects."""

    async def test_list_subjects_filtered_by_category(
        self, app_session, admin_session
    ):
        """List subjects filters by category."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
            category="core",
        )
        await service.create_subject(
            tenant_id=tenant["id"],
            name="French",
            code="FRN",
            category="elective",
        )

        core_subjects = await service.list_subjects(
            tenant["id"], category="core"
        )
        elective_subjects = await service.list_subjects(
            tenant["id"], category="elective"
        )

        assert len(core_subjects) == 1
        assert core_subjects[0].name == "Mathematics"
        assert len(elective_subjects) == 1
        assert elective_subjects[0].name == "French"


class TestDeleteSubject:
    """Tests for soft-deleting subjects."""

    async def test_soft_delete_subject(self, app_session, admin_session):
        """Deleted subject is no longer findable."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )

        deleted = await service.delete_subject(tenant["id"], subject.id)
        assert deleted is True

        result = await service.get_subject(tenant["id"], subject.id)
        assert result is None


# =========================
# Class-Subject Assignment Tests
# =========================


class TestClassSubjectAssignment:
    """Tests for assigning and removing subjects from classes."""

    async def test_assign_subject_to_class(
        self, app_session, admin_session
    ):
        """Subject can be assigned to a class."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            level="jhs_1",
        )
        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )

        assignment = await service.assign_subject_to_class(
            tenant_id=tenant["id"],
            class_id=cls.id,
            subject_id=subject.id,
            periods_per_week=5,
            is_compulsory=True,
        )

        assert assignment is not None
        assert assignment.class_id == cls.id
        assert assignment.subject_id == subject.id
        assert assignment.periods_per_week == 5
        assert assignment.is_compulsory is True

    async def test_duplicate_assignment_raises_error(
        self, app_session, admin_session
    ):
        """Assigning the same subject to the same class twice raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            level="jhs_1",
        )
        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )

        await service.assign_subject_to_class(
            tenant_id=tenant["id"],
            class_id=cls.id,
            subject_id=subject.id,
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.assign_subject_to_class(
                tenant_id=tenant["id"],
                class_id=cls.id,
                subject_id=subject.id,
            )

        assert exc_info.value.code == "duplicate_assignment"

    async def test_remove_subject_from_class(
        self, app_session, admin_session
    ):
        """Subject assignment can be removed."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            level="jhs_1",
        )
        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )

        await service.assign_subject_to_class(
            tenant_id=tenant["id"],
            class_id=cls.id,
            subject_id=subject.id,
        )

        removed = await service.remove_subject_from_class(
            tenant_id=tenant["id"],
            class_id=cls.id,
            subject_id=subject.id,
        )
        assert removed is True

        # Verify it's gone
        assignments = await service.get_class_subjects(
            tenant["id"], cls.id
        )
        assert len(assignments) == 0

    async def test_remove_nonexistent_assignment_returns_false(
        self, app_session, admin_session
    ):
        """Removing a nonexistent assignment returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        result = await service.remove_subject_from_class(
            tenant_id=tenant["id"],
            class_id=uuid4(),
            subject_id=uuid4(),
        )
        assert result is False

    async def test_assign_subject_to_preschool_class_raises_error(
        self, app_session, admin_session
    ):
        """Subjects cannot be assigned to preschool-level classes."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="KG 1",
            level="kg_1",
        )
        subject = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.assign_subject_to_class(
                tenant_id=tenant["id"],
                class_id=cls.id,
                subject_id=subject.id,
            )

        assert exc_info.value.code == "preschool_no_subjects"

    async def test_get_class_subjects_returns_assigned(
        self, app_session, admin_session
    ):
        """Get class subjects returns all subjects for a class."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        cls = await service.create_class(
            tenant_id=tenant["id"],
            name="JHS 1",
            level="jhs_1",
        )
        math = await service.create_subject(
            tenant_id=tenant["id"],
            name="Mathematics",
            code="MATH",
        )
        eng = await service.create_subject(
            tenant_id=tenant["id"],
            name="English",
            code="ENG",
        )

        await service.assign_subject_to_class(
            tenant_id=tenant["id"],
            class_id=cls.id,
            subject_id=math.id,
        )
        await service.assign_subject_to_class(
            tenant_id=tenant["id"],
            class_id=cls.id,
            subject_id=eng.id,
        )

        assignments = await service.get_class_subjects(
            tenant["id"], cls.id
        )
        assert len(assignments) == 2


# =========================
# Grading Scale Tests
# =========================


class TestCreateGradingScale:
    """Tests for creating grading scales."""

    async def test_create_grading_scale_with_grades(
        self, app_session, admin_session
    ):
        """Grading scale with grade entries is created correctly."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        grades_data = [
            {"grade": "A1", "min_score": 80, "max_score": 100, "grade_point": 1.0, "remark": "Excellent"},
            {"grade": "B2", "min_score": 70, "max_score": 79, "grade_point": 2.0, "remark": "Very Good"},
            {"grade": "C4", "min_score": 60, "max_score": 69, "grade_point": 4.0, "remark": "Credit"},
        ]

        scale = await service.create_grading_scale(
            tenant_id=tenant["id"],
            name="WAEC Standard",
            scale_type="waec",
            is_default=True,
            grades=grades_data,
        )

        assert scale is not None
        assert scale.name == "WAEC Standard"
        assert scale.scale_type == GradingScaleType.WAEC
        assert scale.is_default is True
        assert scale.tenant_id == tenant["id"]

        # Verify grades were created by reloading with grades
        loaded = await service.get_grading_scale(
            tenant["id"], scale.id, include_grades=True
        )
        assert len(loaded.grades) == 3

    async def test_create_duplicate_grading_scale_name_raises_error(
        self, app_session, admin_session
    ):
        """Duplicate grading scale name within same tenant raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_grading_scale(
            tenant_id=tenant["id"],
            name="WAEC Standard",
            scale_type="waec",
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_grading_scale(
                tenant_id=tenant["id"],
                name="WAEC Standard",
                scale_type="waec",
            )

        assert exc_info.value.code == "duplicate_grading_scale"

    async def test_set_default_grading_scale_clears_others(
        self, app_session, admin_session
    ):
        """Setting a scale as default clears the default from others."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        scale_1 = await service.create_grading_scale(
            tenant_id=tenant["id"],
            name="WAEC Standard",
            scale_type="waec",
            is_default=True,
        )
        scale_1_id = scale_1.id

        scale_2 = await service.create_grading_scale(
            tenant_id=tenant["id"],
            name="GPA Scale",
            scale_type="gpa",
            is_default=True,
        )

        assert scale_2.is_default is True

        # Re-fetch scale_1 to check default was cleared
        scale_1_refreshed = await service.get_grading_scale(
            tenant["id"], scale_1_id
        )
        assert scale_1_refreshed.is_default is False


class TestDeleteGradingScale:
    """Tests for soft-deleting grading scales."""

    async def test_soft_delete_grading_scale(
        self, app_session, admin_session
    ):
        """Deleted grading scale is no longer findable."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        scale = await service.create_grading_scale(
            tenant_id=tenant["id"],
            name="WAEC Standard",
            scale_type="waec",
        )

        deleted = await service.delete_grading_scale(tenant["id"], scale.id)
        assert deleted is True

        result = await service.get_grading_scale(tenant["id"], scale.id)
        assert result is None


# =========================
# Assessment Weight Tests
# =========================


class TestAssessmentWeights:
    """Tests for assessment weight configuration."""

    async def test_set_assessment_weights_creates_new(
        self, app_session, admin_session
    ):
        """Setting weights for first time creates a new record."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        weights = await service.set_assessment_weights(
            tenant_id=tenant["id"],
            class_work_weight=Decimal("20"),
            homework_weight=Decimal("10"),
            midterm_weight=Decimal("20"),
            end_term_weight=Decimal("50"),
        )

        assert weights is not None
        assert weights.class_work_weight == Decimal("20")
        assert weights.homework_weight == Decimal("10")
        assert weights.midterm_weight == Decimal("20")
        assert weights.end_term_weight == Decimal("50")

    async def test_set_assessment_weights_updates_existing(
        self, app_session, admin_session
    ):
        """Setting weights again updates the existing record."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.set_assessment_weights(
            tenant_id=tenant["id"],
            class_work_weight=Decimal("20"),
            homework_weight=Decimal("10"),
            midterm_weight=Decimal("20"),
            end_term_weight=Decimal("50"),
        )

        # Update
        updated = await service.set_assessment_weights(
            tenant_id=tenant["id"],
            class_work_weight=Decimal("25"),
            homework_weight=Decimal("15"),
            midterm_weight=Decimal("10"),
            end_term_weight=Decimal("50"),
        )

        assert updated.class_work_weight == Decimal("25")
        assert updated.homework_weight == Decimal("15")

    async def test_get_assessment_weights(
        self, app_session, admin_session
    ):
        """Get returns the tenant's assessment weights."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.set_assessment_weights(
            tenant_id=tenant["id"],
            class_work_weight=Decimal("20"),
            homework_weight=Decimal("10"),
            midterm_weight=Decimal("20"),
            end_term_weight=Decimal("50"),
        )

        weights = await service.get_assessment_weights(tenant["id"])
        assert weights is not None
        assert weights.class_work_weight == Decimal("20")

    async def test_get_assessment_weights_returns_none_when_not_set(
        self, app_session, admin_session
    ):
        """Get returns None when no weights are configured."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        weights = await service.get_assessment_weights(tenant["id"])
        assert weights is None


# =========================
# Academic Settings Tests
# =========================


class TestAcademicSettings:
    """Tests for academic settings configuration."""

    async def test_update_academic_settings_creates_new(
        self, app_session, admin_session
    ):
        """First update creates a new settings record."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        settings = await service.update_academic_settings(
            tenant_id=tenant["id"],
            auto_promote_students=True,
            show_position_on_report_cards=False,
        )

        assert settings is not None
        assert settings.auto_promote_students is True
        assert settings.show_position_on_report_cards is False
        # Defaults should apply
        assert settings.allow_grade_amendments is True
        assert settings.enable_continuous_assessment is True

    async def test_update_academic_settings_preserves_unset_values(
        self, app_session, admin_session
    ):
        """Updating one setting does not change others."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        # Create initial settings
        await service.update_academic_settings(
            tenant_id=tenant["id"],
            auto_promote_students=True,
            show_position_on_report_cards=True,
        )

        # Update only auto_promote
        settings = await service.update_academic_settings(
            tenant_id=tenant["id"],
            auto_promote_students=False,
        )

        assert settings.auto_promote_students is False
        assert settings.show_position_on_report_cards is True  # Unchanged

    async def test_get_academic_settings_returns_none_when_not_set(
        self, app_session, admin_session
    ):
        """Get returns None when no settings are configured."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        settings = await service.get_academic_settings(tenant["id"])
        assert settings is None


# =========================
# Tenant Isolation
# =========================


class TestSubjectTenantIsolation:
    """Subjects and grading scales must be isolated between tenants."""

    async def test_tenant_a_cannot_see_tenant_b_subjects(
        self, app_session, admin_session
    ):
        """Tenant A's subjects are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create subject as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)

        await service.create_subject(
            tenant_id=tenant_a["id"],
            name="Mathematics",
            code="MATH",
        )
        await app_session.flush()

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        subjects = await service.list_subjects(tenant_b["id"])
        assert len(subjects) == 0, "Tenant B must not see Tenant A's subjects"

    async def test_same_subject_code_allowed_in_different_tenants(
        self, app_session, admin_session
    ):
        """Two tenants can have subjects with the same code."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)
        sub_a = await service.create_subject(
            tenant_id=tenant_a["id"],
            name="Mathematics",
            code="MATH",
        )
        await app_session.flush()
        # Capture values before context switch to avoid MissingGreenlet
        sub_a_id = sub_a.id
        sub_a_code = sub_a.code

        # Create as Tenant B -- same code should work
        await set_app_tenant_context(app_session, tenant_b["id"])
        sub_b = await service.create_subject(
            tenant_id=tenant_b["id"],
            name="Mathematics",
            code="MATH",
        )

        assert sub_a_id != sub_b.id
        assert sub_a_code == sub_b.code == "MATH"

    async def test_tenant_a_cannot_see_tenant_b_grading_scales(
        self, app_session, admin_session
    ):
        """Tenant A's grading scales are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create grading scale as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)

        await service.create_grading_scale(
            tenant_id=tenant_a["id"],
            name="WAEC Standard",
            scale_type="waec",
        )
        await app_session.flush()

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        scales = await service.list_grading_scales(tenant_b["id"])
        assert len(scales) == 0, "Tenant B must not see Tenant A's grading scales"

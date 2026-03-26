"""
SIMS Plus - Curriculum Profile Service

Business logic for curriculum profile management, built-in templates,
and template instantiation into database records.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import GradingScale
from app.models.curriculum import (
    AcademicCalendarType,
    AssessmentComponent,
    AssessmentComponentType,
    AssessmentStructure,
    CurriculumProfile,
    CurriculumType,
    ReportCardConfig,
    ScoreDisplayMode,
)
from app.models.school import School
from app.models.tenant import Tenant
from app.services.curriculum._shared import CurriculumServiceError
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


# =========================
# Built-in Curriculum Templates
# =========================
# Templates are Python dictionaries, NOT database rows. When a school
# selects a template, the system instantiates CurriculumProfile +
# AssessmentStructure + AssessmentComponents + ReportCardConfig from it.

CURRICULUM_TEMPLATES: dict[str, dict] = {
    "ges_standard": {
        "profile": {
            "name": "GES Standard",
            "curriculum_type": "ges",
            "description": "Ghana Education Service standard curriculum with 4-component assessment.",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_and_score",
            "show_position": True,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": None,
        },
        "assessment": {
            "name": "GES Assessment Structure",
            "components": [
                {"type": "class_work", "name": "Class Work", "weight": 20, "seq": 1, "ca": True, "exam": False},
                {"type": "homework", "name": "Homework", "weight": 10, "seq": 2, "ca": True, "exam": False},
                {"type": "midterm", "name": "Midterm", "weight": 20, "seq": 3, "ca": True, "exam": False},
                {"type": "end_term", "name": "End of Term", "weight": 50, "seq": 4, "ca": False, "exam": True},
            ],
        },
        "report_config": {
            "template_key": "ges",
            "show_position": True,
            "show_class_average": True,
            "show_subject_position": True,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "cambridge_igcse": {
        "profile": {
            "name": "Cambridge IGCSE",
            "curriculum_type": "cambridge",
            "description": "Cambridge International IGCSE curriculum with coursework, controlled assessment, and external exam.",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_and_score",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {"programme": "igcse"},
        },
        "assessment": {
            "name": "IGCSE Assessment Structure",
            "components": [
                {"type": "coursework", "name": "Coursework", "weight": 25, "seq": 1, "ca": False, "exam": False},
                {"type": "controlled_assessment", "name": "Controlled Assessment", "weight": 25, "seq": 2, "ca": False, "exam": False},
                {"type": "external_exam", "name": "External Exam", "weight": 50, "seq": 3, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "cambridge",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": True,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "cambridge_a_level": {
        "profile": {
            "name": "Cambridge A-Level",
            "curriculum_type": "cambridge",
            "description": "Cambridge International A-Level with coursework and external examination.",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_only",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {"programme": "a_level"},
        },
        "assessment": {
            "name": "A-Level Assessment Structure",
            "components": [
                {"type": "coursework", "name": "Coursework", "weight": 20, "seq": 1, "ca": False, "exam": False},
                {"type": "external_exam", "name": "External Exam", "weight": 80, "seq": 2, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "cambridge",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": True,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "edexcel_igcse": {
        "profile": {
            "name": "Edexcel IGCSE",
            "curriculum_type": "edexcel",
            "description": "Pearson Edexcel IGCSE curriculum with coursework and external examination.",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_and_score",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {"programme": "igcse"},
        },
        "assessment": {
            "name": "Edexcel Assessment Structure",
            "components": [
                {"type": "coursework", "name": "Coursework", "weight": 25, "seq": 1, "ca": False, "exam": False},
                {"type": "external_exam", "name": "External Exam", "weight": 75, "seq": 2, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "cambridge",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": True,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "american_standard": {
        "profile": {
            "name": "American Standard",
            "curriculum_type": "american",
            "description": "US Common Core standard curriculum with GPA, credits, and honor roll.",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "gpa",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": True,
            "use_credits": True,
            "use_criterion_grading": False,
            "config": {
                "gpa_scale": 4.0,
                "weighted_gpa": True,
                "honor_roll_threshold": 3.5,
                "ap_weight_bonus": 1.0,
                "honors_weight_bonus": 0.5,
                "graduation_credits_required": 24,
            },
        },
        "assessment": {
            "name": "American Assessment Structure",
            "components": [
                {"type": "homework", "name": "Homework", "weight": 15, "seq": 1, "ca": False, "exam": False},
                {"type": "quiz", "name": "Quizzes", "weight": 15, "seq": 2, "ca": False, "exam": False},
                {"type": "test", "name": "Tests", "weight": 25, "seq": 3, "ca": False, "exam": False},
                {"type": "project", "name": "Projects", "weight": 15, "seq": 4, "ca": False, "exam": False},
                {"type": "final", "name": "Final Exam", "weight": 30, "seq": 5, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "american",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": True,
            "show_credits": True,
            "show_honor_roll": True,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "american_ap": {
        "profile": {
            "name": "American AP",
            "curriculum_type": "american",
            "description": "US Advanced Placement curriculum with weighted GPA and college-level coursework.",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "gpa",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": True,
            "use_credits": True,
            "use_criterion_grading": False,
            "config": {
                "gpa_scale": 4.0,
                "weighted_gpa": True,
                "honor_roll_threshold": 3.5,
                "ap_weight_bonus": 1.0,
                "honors_weight_bonus": 0.5,
                "graduation_credits_required": 24,
            },
        },
        "assessment": {
            "name": "AP Assessment Structure",
            "components": [
                {"type": "participation", "name": "Participation", "weight": 10, "seq": 1, "ca": False, "exam": False},
                {"type": "homework", "name": "Homework", "weight": 15, "seq": 2, "ca": False, "exam": False},
                {"type": "test", "name": "Tests", "weight": 25, "seq": 3, "ca": False, "exam": False},
                {"type": "project", "name": "Projects", "weight": 20, "seq": 4, "ca": False, "exam": False},
                {"type": "final", "name": "Final Exam", "weight": 30, "seq": 5, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "american",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": True,
            "show_credits": True,
            "show_honor_roll": True,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "ib_myp": {
        "profile": {
            "name": "IB MYP",
            "curriculum_type": "ib",
            "description": "International Baccalaureate Middle Years Programme with criterion-based grading.",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "level",
            "show_position": False,
            "show_class_average": False,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": True,
            "config": {
                "ib_programme": "myp",
                "learner_profile_traits": [
                    "inquirers", "knowledgeable", "thinkers", "communicators",
                    "principled", "open-minded", "caring", "risk-takers",
                    "balanced", "reflective",
                ],
                "atl_skills": ["thinking", "communication", "social", "self-management", "research"],
            },
        },
        "assessment": {
            "name": "IB MYP Assessment Structure",
            "components": [
                {"type": "internal_assessment", "name": "Internal Assessment", "weight": 100, "seq": 1, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "ib",
            "show_position": False,
            "show_class_average": False,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": True,
            "show_atl_skills": True,
        },
    },
    "ib_dp": {
        "profile": {
            "name": "IB DP",
            "curriculum_type": "ib",
            "description": "International Baccalaureate Diploma Programme with IA, EA, and bonus points.",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "level",
            "show_position": False,
            "show_class_average": False,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": True,
            "config": {
                "ib_programme": "dp",
                "learner_profile_traits": [
                    "inquirers", "knowledgeable", "thinkers", "communicators",
                    "principled", "open-minded", "caring", "risk-takers",
                    "balanced", "reflective",
                ],
                "atl_skills": ["thinking", "communication", "social", "self-management", "research"],
                "max_total_points": 45,
                "bonus_points_max": 3,
                "passing_total": 24,
            },
        },
        "assessment": {
            "name": "IB DP Assessment Structure",
            "components": [
                {"type": "internal_assessment", "name": "Internal Assessment", "weight": 25, "seq": 1, "ca": False, "exam": False},
                {"type": "external_assessment", "name": "External Assessment", "weight": 75, "seq": 2, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "ib",
            "show_position": False,
            "show_class_average": False,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": True,
            "show_atl_skills": True,
        },
    },
    "french_bac": {
        "profile": {
            "name": "French Baccalaureate",
            "curriculum_type": "french",
            "description": "French Baccalaureate with controle continu, epreuve, and mention system.",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "mention",
            "show_position": True,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {
                "mention_thresholds": {
                    "tres_bien": 16,
                    "bien": 14,
                    "assez_bien": 12,
                    "passable": 10,
                },
                "max_score": 20,
                "coefficient_system": True,
            },
        },
        "assessment": {
            "name": "French Assessment Structure",
            "components": [
                {"type": "controle_continu", "name": "Controle Continu", "weight": 40, "seq": 1, "ca": False, "exam": False},
                {"type": "epreuve", "name": "Epreuve", "weight": 60, "seq": 2, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "french",
            "show_position": True,
            "show_class_average": True,
            "show_subject_position": True,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
    "montessori": {
        "profile": {
            "name": "Montessori",
            "curriculum_type": "montessori",
            "description": "Montessori narrative-based assessment with observation, portfolio, and narrative components.",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "narrative",
            "show_position": False,
            "show_class_average": False,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {
                "developmental_areas": ["practical_life", "sensorial", "language", "mathematics", "cultural"],
                "progress_levels": ["emerging", "developing", "proficient", "mastery"],
                "narrative_required": True,
            },
        },
        "assessment": {
            "name": "Montessori Assessment Structure",
            "components": [
                {"type": "observation", "name": "Observation", "weight": 40, "seq": 1, "ca": False, "exam": False},
                {"type": "portfolio", "name": "Portfolio", "weight": 30, "seq": 2, "ca": False, "exam": False},
                {"type": "narrative", "name": "Narrative Assessment", "weight": 30, "seq": 3, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "montessori",
            "show_position": False,
            "show_class_average": False,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
}


class CurriculumProfileService:
    """Service for curriculum profile management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Tenant FK Validation
    # =========================

    async def _validate_tenant_fk(
        self, model_class, id: UUID, tenant_id: UUID
    ) -> None:
        """
        Validate FK target belongs to same tenant.

        PostgreSQL FK constraints bypass RLS, so a user-supplied UUID
        could reference a row in another tenant. This helper prevents
        cross-tenant FK references for every externally-supplied UUID.
        """
        result = await self.db.execute(
            select(model_class.id).where(
                model_class.id == id,
                model_class.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise CurriculumServiceError(
                f"{model_class.__name__} not found", "not_found"
            )

    # =========================
    # Feature Flag Enforcement
    # =========================

    async def _check_plan_limits(
        self,
        tenant_id: UUID,
        curriculum_type: str,
        exclude_profile_id: UUID | None = None,
    ) -> None:
        """
        Enforce subscription tier limits on curriculum profile creation.

        - Starter/Trial: only GES profiles allowed
        - Professional: 1 non-GES profile max
        - Enterprise: unlimited
        """
        if curriculum_type == CurriculumType.GES.value:
            # GES is always allowed on all plans
            return

        # Fetch tenant to check subscription tier
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise CurriculumServiceError("Tenant not found", "not_found")

        tier = tenant.subscription_tier.value if hasattr(tenant.subscription_tier, "value") else str(tenant.subscription_tier)

        if tier in ("trial", "starter"):
            raise CurriculumServiceError(
                "Multi-curriculum not available on Starter plan. "
                "Upgrade to Professional or Enterprise.",
                "plan_limit",
            )

        if tier == "professional":
            # Allow at most 1 non-GES profile
            conditions = [
                CurriculumProfile.tenant_id == tenant_id,
                CurriculumProfile.curriculum_type != CurriculumType.GES,
                CurriculumProfile.deleted_at.is_(None),
            ]
            if exclude_profile_id:
                # When updating, exclude the current profile from the count
                conditions.append(CurriculumProfile.id != exclude_profile_id)

            count_result = await self.db.execute(
                select(func.count(CurriculumProfile.id)).where(and_(*conditions))
            )
            existing_count = count_result.scalar_one()
            if existing_count >= 1:
                raise CurriculumServiceError(
                    "Professional plan allows only 1 non-GES curriculum profile. "
                    "Upgrade to Enterprise for unlimited profiles.",
                    "plan_limit",
                )

        # Enterprise: no limit, pass through

    # =========================
    # CRUD Methods
    # =========================

    async def list_profiles(
        self,
        tenant_id: UUID,
        school_id: UUID | None = None,
        curriculum_type: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[CurriculumProfile], int]:
        """List curriculum profiles with optional filters and pagination."""
        conditions = [
            CurriculumProfile.tenant_id == tenant_id,
            CurriculumProfile.deleted_at.is_(None),
        ]

        if school_id is not None:
            conditions.append(CurriculumProfile.school_id == school_id)
        if curriculum_type is not None:
            conditions.append(
                CurriculumProfile.curriculum_type == CurriculumType(curriculum_type)
            )
        if is_active is not None:
            conditions.append(CurriculumProfile.is_active == is_active)
        if search:
            safe_search = escape_ilike(search)
            conditions.append(CurriculumProfile.name.ilike(f"%{safe_search}%"))

        # Count total
        count_result = await self.db.execute(
            select(func.count(CurriculumProfile.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        # Fetch page
        offset = (page - 1) * page_size
        query = (
            select(CurriculumProfile)
            .where(and_(*conditions))
            .order_by(CurriculumProfile.is_default.desc(), CurriculumProfile.name)
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        profiles = result.scalars().all()

        return profiles, total

    async def get_profile(
        self, tenant_id: UUID, profile_id: UUID
    ) -> CurriculumProfile:
        """
        Get a single curriculum profile with related structures, components,
        and report config eagerly loaded.
        """
        result = await self.db.execute(
            select(CurriculumProfile)
            .where(
                CurriculumProfile.tenant_id == tenant_id,
                CurriculumProfile.id == profile_id,
                CurriculumProfile.deleted_at.is_(None),
            )
            .options(
                selectinload(CurriculumProfile.assessment_structures).selectinload(
                    AssessmentStructure.components
                ),
                selectinload(CurriculumProfile.report_config),
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise CurriculumServiceError("Curriculum profile not found", "not_found")
        return profile

    async def create_profile(
        self,
        data,
        tenant_id: UUID,
        school_id: UUID,
    ) -> CurriculumProfile:
        """
        Create a new curriculum profile.

        Enforces subscription tier limits before creation.
        """
        # Feature flag check: Starter can only create GES profiles
        await self._check_plan_limits(tenant_id, data.curriculum_type)

        # Validate FK references belong to the same tenant
        await self._validate_tenant_fk(School, school_id, tenant_id)
        if data.grading_scale_id:
            await self._validate_tenant_fk(
                GradingScale, data.grading_scale_id, tenant_id
            )

        # Unset existing default if this profile should be default
        if data.is_default:
            await self._unset_default_profile(tenant_id, school_id)

        profile = CurriculumProfile(
            tenant_id=tenant_id,
            school_id=school_id,
            name=data.name,
            curriculum_type=CurriculumType(data.curriculum_type),
            description=data.description,
            grading_scale_id=data.grading_scale_id,
            academic_calendar_type=AcademicCalendarType(data.academic_calendar_type),
            periods_per_year=data.periods_per_year,
            score_display_mode=ScoreDisplayMode(data.score_display_mode),
            show_position=data.show_position,
            show_class_average=data.show_class_average,
            use_gpa=data.use_gpa,
            use_credits=data.use_credits,
            use_criterion_grading=data.use_criterion_grading,
            config=data.config,
            is_default=data.is_default,
            is_active=True,
        )
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)

        logger.info(
            "curriculum_profile_created",
            profile_id=str(profile.id),
            tenant_id=str(tenant_id),
            curriculum_type=data.curriculum_type,
        )
        return profile

    async def update_profile(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        data,
    ) -> CurriculumProfile:
        """Update an existing curriculum profile."""
        profile = await self.get_profile(tenant_id, profile_id)

        # If curriculum_type is being changed from GES to non-GES, enforce plan limits
        if (
            data.curriculum_type is not None
            and data.curriculum_type != CurriculumType.GES.value
            and profile.curriculum_type == CurriculumType.GES
        ):
            await self._check_plan_limits(
                tenant_id, data.curriculum_type, exclude_profile_id=profile_id
            )

        # Validate FK if grading_scale_id is being updated
        if data.grading_scale_id is not None:
            await self._validate_tenant_fk(
                GradingScale, data.grading_scale_id, tenant_id
            )

        # Apply updates — blocklist immutable fields to prevent mass-assignment
        _IMMUTABLE_FIELDS = {"id", "tenant_id", "school_id", "created_at", "deleted_at"}
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in _IMMUTABLE_FIELDS:
                continue
            if hasattr(profile, key):
                # Convert string enum values to proper enum instances
                if key == "curriculum_type" and value is not None:
                    value = CurriculumType(value)
                elif key == "academic_calendar_type" and value is not None:
                    value = AcademicCalendarType(value)
                elif key == "score_display_mode" and value is not None:
                    value = ScoreDisplayMode(value)
                setattr(profile, key, value)

        profile.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(profile)

        logger.info(
            "curriculum_profile_updated",
            profile_id=str(profile_id),
            tenant_id=str(tenant_id),
        )
        return profile

    async def delete_profile(self, tenant_id: UUID, profile_id: UUID) -> None:
        """
        Soft delete a curriculum profile.

        Blocks deletion if active classes reference this profile.
        """
        from app.models.academic import Class

        profile = await self.get_profile(tenant_id, profile_id)

        # Check for referencing classes
        count_result = await self.db.execute(
            select(func.count(Class.id)).where(
                Class.tenant_id == tenant_id,
                Class.curriculum_profile_id == profile_id,
                Class.deleted_at.is_(None),
            )
        )
        referencing_count = count_result.scalar_one()
        if referencing_count > 0:
            raise CurriculumServiceError(
                "Cannot delete profile referenced by active classes",
                "profile_in_use",
            )

        profile.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "curriculum_profile_deleted",
            profile_id=str(profile_id),
            tenant_id=str(tenant_id),
        )

    async def set_default(self, tenant_id: UUID, profile_id: UUID) -> CurriculumProfile:
        """Set a profile as the default, unsetting any previous default."""
        profile = await self.get_profile(tenant_id, profile_id)

        # Feature flag check: prevent setting a non-GES profile as default on restricted plans
        if profile.curriculum_type != CurriculumType.GES:
            await self._check_plan_limits(
                tenant_id,
                profile.curriculum_type.value,
                exclude_profile_id=profile_id,
            )

        await self._unset_default_profile(tenant_id, profile.school_id)

        profile.is_default = True
        profile.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(profile)

        logger.info(
            "curriculum_profile_set_default",
            profile_id=str(profile_id),
            tenant_id=str(tenant_id),
        )
        return profile

    # =========================
    # Template Methods
    # =========================

    def list_templates(self) -> list[dict]:
        """Return metadata about all built-in curriculum templates."""
        templates = []
        for key, tmpl in CURRICULUM_TEMPLATES.items():
            profile = tmpl["profile"]
            templates.append({
                "key": key,
                "name": profile["name"],
                "curriculum_type": profile["curriculum_type"],
                "description": profile.get("description", ""),
            })
        return templates

    async def create_from_template(
        self,
        tenant_id: UUID,
        school_id: UUID,
        template_key: str,
        name_override: str | None = None,
    ) -> CurriculumProfile:
        """
        Instantiate a built-in template into database records.

        Creates CurriculumProfile + AssessmentStructure + AssessmentComponents
        + ReportCardConfig in a single transaction.
        """
        if template_key not in CURRICULUM_TEMPLATES:
            raise CurriculumServiceError(
                f"Unknown template: '{template_key}'", "invalid_template"
            )

        template = CURRICULUM_TEMPLATES[template_key]
        profile_tmpl = template["profile"]
        assessment_tmpl = template["assessment"]
        report_tmpl = template["report_config"]

        # Feature flag check: ensure plan allows this curriculum type
        await self._check_plan_limits(tenant_id, profile_tmpl["curriculum_type"])

        # Validate school belongs to tenant
        await self._validate_tenant_fk(School, school_id, tenant_id)

        # Create the curriculum profile
        profile = CurriculumProfile(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name_override or profile_tmpl["name"],
            curriculum_type=CurriculumType(profile_tmpl["curriculum_type"]),
            description=profile_tmpl.get("description"),
            academic_calendar_type=AcademicCalendarType(profile_tmpl["academic_calendar_type"]),
            periods_per_year=profile_tmpl["periods_per_year"],
            score_display_mode=ScoreDisplayMode(profile_tmpl["score_display_mode"]),
            show_position=profile_tmpl["show_position"],
            show_class_average=profile_tmpl["show_class_average"],
            use_gpa=profile_tmpl["use_gpa"],
            use_credits=profile_tmpl["use_credits"],
            use_criterion_grading=profile_tmpl["use_criterion_grading"],
            config=profile_tmpl.get("config"),
            is_active=True,
        )
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)

        # Create the assessment structure (default: no academic_year_id)
        structure = AssessmentStructure(
            tenant_id=tenant_id,
            school_id=school_id,
            curriculum_profile_id=profile.id,
            academic_year_id=None,
            name=assessment_tmpl["name"],
            is_active=True,
        )
        self.db.add(structure)
        await self.db.flush()
        await self.db.refresh(structure)

        # Create assessment components
        for comp_data in assessment_tmpl["components"]:
            component = AssessmentComponent(
                tenant_id=tenant_id,
                school_id=school_id,
                assessment_structure_id=structure.id,
                component_type=AssessmentComponentType(comp_data["type"]),
                name=comp_data["name"],
                weight=Decimal(str(comp_data["weight"])),
                sequence=comp_data["seq"],
                maps_to_ca=comp_data.get("ca", False),
                maps_to_exam=comp_data.get("exam", False),
                is_external=comp_data.get("external", False),
            )
            self.db.add(component)

        # Create report card config
        report_config = ReportCardConfig(
            tenant_id=tenant_id,
            school_id=school_id,
            curriculum_profile_id=profile.id,
            template_key=report_tmpl["template_key"],
            show_position=report_tmpl["show_position"],
            show_class_average=report_tmpl["show_class_average"],
            show_subject_position=report_tmpl["show_subject_position"],
            show_effort_grade=report_tmpl["show_effort_grade"],
            show_predicted_grades=report_tmpl["show_predicted_grades"],
            show_gpa=report_tmpl["show_gpa"],
            show_credits=report_tmpl["show_credits"],
            show_honor_roll=report_tmpl["show_honor_roll"],
            show_learner_profile=report_tmpl["show_learner_profile"],
            show_atl_skills=report_tmpl["show_atl_skills"],
        )
        self.db.add(report_config)

        await self.db.flush()

        # Reload the profile with all relationships for the response
        return await self.get_profile(tenant_id, profile.id)

    # =========================
    # Report Card Config Methods
    # =========================

    async def get_report_config(
        self, tenant_id: UUID, profile_id: UUID
    ) -> ReportCardConfig | None:
        """Get the report card config for a curriculum profile."""
        # Verify profile exists and belongs to tenant
        await self.get_profile(tenant_id, profile_id)

        result = await self.db.execute(
            select(ReportCardConfig).where(
                ReportCardConfig.tenant_id == tenant_id,
                ReportCardConfig.curriculum_profile_id == profile_id,
                ReportCardConfig.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def update_report_config(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        data,
    ) -> ReportCardConfig:
        """Update the report card config for a curriculum profile."""
        # Verify profile exists and belongs to tenant
        profile = await self.get_profile(tenant_id, profile_id)

        config = await self.get_report_config(tenant_id, profile_id)
        if not config:
            # Create a new config if none exists
            config = ReportCardConfig(
                tenant_id=tenant_id,
                school_id=profile.school_id,
                curriculum_profile_id=profile_id,
            )
            self.db.add(config)
            await self.db.flush()
            await self.db.refresh(config)

        # Blocklist immutable fields to prevent mass-assignment
        _IMMUTABLE_FIELDS = {"id", "tenant_id", "school_id", "created_at", "deleted_at"}
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in _IMMUTABLE_FIELDS:
                continue
            if hasattr(config, key):
                setattr(config, key, value)

        config.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(config)
        return config

    # =========================
    # Internal Helpers
    # =========================

    async def _unset_default_profile(
        self, tenant_id: UUID, school_id: UUID | None
    ) -> None:
        """Unset the current default profile for a school (or chain-level if school_id is None)."""
        conditions = [
            CurriculumProfile.tenant_id == tenant_id,
            CurriculumProfile.is_default == True,
            CurriculumProfile.deleted_at.is_(None),
        ]
        if school_id:
            conditions.append(CurriculumProfile.school_id == school_id)
        else:
            # When school_id is None, only affect chain-level (NULL school_id) profiles
            conditions.append(CurriculumProfile.school_id.is_(None))

        result = await self.db.execute(
            select(CurriculumProfile).where(and_(*conditions))
        )
        current_defaults = result.scalars().all()
        for p in current_defaults:
            p.is_default = False
        if current_defaults:
            await self.db.flush()

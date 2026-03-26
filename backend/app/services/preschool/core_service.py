"""
SIMS Plus - Preschool Core Service

Business logic for learning areas, developmental skills, rating scales,
student skill assessments, and seed data.
"""

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.preschool import (
    LearningArea,
    DevelopmentalSkill,
    PreschoolRatingScale,
    PreschoolRating,
    StudentSkillAssessment,
)
from app.schemas.preschool import (
    LearningAreaCreate,
    LearningAreaUpdate,
    DevelopmentalSkillCreate,
    DevelopmentalSkillUpdate,
    DevelopmentalSkillBulkCreate,
    PreschoolRatingScaleCreate,
    PreschoolRatingScaleUpdate,
    StudentSkillAssessmentCreate,
    StudentSkillAssessmentBulk,
)
from app.services.preschool._shared import (
    PreschoolServiceError,
    DEFAULT_LEARNING_AREAS,
    DEFAULT_SKILLS_BY_AREA,
    DEFAULT_RATING_SCALE,
)


class PreschoolCoreService:
    """Service for learning areas, skills, rating scales, assessments, and seeding."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Learning Areas
    # =========================

    async def create_learning_area(
        self,
        tenant_id: UUID,
        data: LearningAreaCreate,
    ) -> LearningArea:
        """Create a new learning area."""
        learning_area = LearningArea(
            tenant_id=tenant_id,
            name=data.name,
            code=data.code,
            description=data.description,
            icon=data.icon,
            color=data.color,
            display_order=data.display_order,
            is_active=data.is_active,
        )
        self.db.add(learning_area)
        await self.db.flush()
        await self.db.refresh(learning_area)
        return learning_area

    async def get_learning_area(
        self,
        tenant_id: UUID,
        area_id: UUID,
    ) -> LearningArea:
        """Get a learning area by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(LearningArea)
            .options(selectinload(LearningArea.skills))
            .where(
                and_(
                    LearningArea.id == area_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    LearningArea.tenant_id == tenant_id,
                    LearningArea.deleted_at.is_(None),
                )
            )
        )
        area = result.scalar_one_or_none()
        if not area:
            raise PreschoolServiceError("Learning area not found", "not_found")
        return area

    async def list_learning_areas(
        self,
        tenant_id: UUID,
        include_inactive: bool = False,
    ) -> Sequence[LearningArea]:
        """List all learning areas for a tenant."""
        query = select(LearningArea).where(
            and_(
                LearningArea.tenant_id == tenant_id,
                LearningArea.deleted_at.is_(None),
            )
        )
        if not include_inactive:
            query = query.where(LearningArea.is_active == True)  # noqa: E712
        query = query.order_by(LearningArea.display_order)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_learning_area(
        self,
        learning_area: LearningArea,
        data: LearningAreaUpdate,
    ) -> LearningArea:
        """Update a learning area."""
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(learning_area, field, value)
        await self.db.flush()
        await self.db.refresh(learning_area)
        return learning_area

    async def delete_learning_area(
        self,
        learning_area: LearningArea,
    ) -> None:
        """Soft delete a learning area."""
        learning_area.deleted_at = datetime.utcnow()
        await self.db.flush()

    # =========================
    # Developmental Skills
    # =========================

    async def create_skill(
        self,
        tenant_id: UUID,
        data: DevelopmentalSkillCreate,
    ) -> DevelopmentalSkill:
        """Create a new developmental skill."""
        skill = DevelopmentalSkill(
            tenant_id=tenant_id,
            learning_area_id=data.learning_area_id,
            name=data.name,
            description=data.description,
            age_range_months_min=data.age_range_months_min,
            age_range_months_max=data.age_range_months_max,
            display_order=data.display_order,
            is_active=data.is_active,
            applicable_levels=data.applicable_levels,
        )
        self.db.add(skill)
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def bulk_create_skills(
        self,
        tenant_id: UUID,
        data: DevelopmentalSkillBulkCreate,
    ) -> list[DevelopmentalSkill]:
        """Bulk create skills for a learning area."""
        skills = []
        for i, skill_data in enumerate(data.skills):
            skill = DevelopmentalSkill(
                tenant_id=tenant_id,
                learning_area_id=data.learning_area_id,
                name=skill_data.name,
                description=skill_data.description,
                age_range_months_min=skill_data.age_range_months_min,
                age_range_months_max=skill_data.age_range_months_max,
                display_order=skill_data.display_order or i,
                is_active=skill_data.is_active,
                applicable_levels=skill_data.applicable_levels,
            )
            self.db.add(skill)
            skills.append(skill)
        await self.db.flush()
        for skill in skills:
            await self.db.refresh(skill)
        return skills

    async def get_skill(
        self,
        tenant_id: UUID,
        skill_id: UUID,
    ) -> DevelopmentalSkill:
        """Get a skill by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(DevelopmentalSkill)
            .options(joinedload(DevelopmentalSkill.learning_area))
            .where(
                and_(
                    DevelopmentalSkill.id == skill_id,
                    DevelopmentalSkill.tenant_id == tenant_id,
                    DevelopmentalSkill.deleted_at.is_(None),
                )
            )
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise PreschoolServiceError("Skill not found", "not_found")
        return skill

    async def list_skills(
        self,
        tenant_id: UUID,
        learning_area_id: UUID | None = None,
        class_level: str | None = None,
        include_inactive: bool = False,
    ) -> Sequence[DevelopmentalSkill]:
        """List skills with optional filters."""
        query = select(DevelopmentalSkill).where(
            and_(
                DevelopmentalSkill.tenant_id == tenant_id,
                DevelopmentalSkill.deleted_at.is_(None),
            )
        )
        if learning_area_id:
            query = query.where(DevelopmentalSkill.learning_area_id == learning_area_id)
        if not include_inactive:
            query = query.where(DevelopmentalSkill.is_active == True)  # noqa: E712
        query = query.order_by(
            DevelopmentalSkill.learning_area_id,
            DevelopmentalSkill.display_order,
        )
        result = await self.db.execute(query)
        skills = result.scalars().all()

        # Filter by class level if provided (in-memory since applicable_levels is JSONB)
        if class_level:
            skills = [
                s for s in skills
                if s.applicable_levels is None or class_level in s.applicable_levels
            ]
        return skills

    async def update_skill(
        self,
        skill: DevelopmentalSkill,
        data: DevelopmentalSkillUpdate,
    ) -> DevelopmentalSkill:
        """Update a skill."""
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(skill, field, value)
        await self.db.flush()
        await self.db.refresh(skill)
        return skill

    async def delete_skill(
        self,
        skill: DevelopmentalSkill,
    ) -> None:
        """Soft delete a skill."""
        skill.deleted_at = datetime.utcnow()
        await self.db.flush()

    # =========================
    # Rating Scales
    # =========================

    async def create_rating_scale(
        self,
        tenant_id: UUID,
        data: PreschoolRatingScaleCreate,
    ) -> PreschoolRatingScale:
        """Create a rating scale with ratings."""
        # If setting as default, unset other active defaults first
        if data.is_default:
            result = await self.db.execute(
                select(PreschoolRatingScale)
                .where(
                    and_(
                        PreschoolRatingScale.tenant_id == tenant_id,
                        PreschoolRatingScale.is_default == True,  # noqa: E712
                        PreschoolRatingScale.deleted_at.is_(None),
                    )
                )
            )
            for existing in result.scalars().all():
                existing.is_default = False

        scale = PreschoolRatingScale(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            is_default=data.is_default,
        )
        self.db.add(scale)
        await self.db.flush()  # Get the ID for child ratings

        # Add ratings -- tenant_id required for RLS isolation
        for rating_data in data.ratings:
            rating = PreschoolRating(
                tenant_id=tenant_id,
                scale_id=scale.id,
                name=rating_data.name,
                short_code=rating_data.short_code,
                description=rating_data.description,
                numeric_value=rating_data.numeric_value,
                color=rating_data.color,
                icon=rating_data.icon,
                display_order=rating_data.display_order,
            )
            self.db.add(rating)

        await self.db.flush()
        await self.db.refresh(scale)
        return scale

    async def get_rating_scale(
        self,
        tenant_id: UUID,
        scale_id: UUID,
    ) -> PreschoolRatingScale:
        """Get a rating scale by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(PreschoolRatingScale)
            .options(selectinload(PreschoolRatingScale.ratings))
            .where(
                and_(
                    PreschoolRatingScale.id == scale_id,
                    PreschoolRatingScale.tenant_id == tenant_id,
                    PreschoolRatingScale.deleted_at.is_(None),
                )
            )
        )
        scale = result.scalar_one_or_none()
        if not scale:
            raise PreschoolServiceError("Rating scale not found", "not_found")
        return scale

    async def get_default_rating_scale(
        self,
        tenant_id: UUID,
    ) -> PreschoolRatingScale:
        """Get the default rating scale for a tenant.

        Raises PreschoolServiceError if no default scale exists.
        """
        result = await self.db.execute(
            select(PreschoolRatingScale)
            .options(selectinload(PreschoolRatingScale.ratings))
            .where(
                and_(
                    PreschoolRatingScale.tenant_id == tenant_id,
                    PreschoolRatingScale.is_default == True,  # noqa: E712
                    PreschoolRatingScale.deleted_at.is_(None),
                )
            )
        )
        scale = result.scalar_one_or_none()
        if not scale:
            raise PreschoolServiceError(
                "No default rating scale found. Please seed the default scale first.",
                "not_found",
            )
        return scale

    async def list_rating_scales(
        self,
        tenant_id: UUID,
    ) -> Sequence[PreschoolRatingScale]:
        """List all rating scales for a tenant."""
        result = await self.db.execute(
            select(PreschoolRatingScale)
            .options(selectinload(PreschoolRatingScale.ratings))
            .where(
                and_(
                    PreschoolRatingScale.tenant_id == tenant_id,
                    PreschoolRatingScale.deleted_at.is_(None),
                )
            )
            .order_by(desc(PreschoolRatingScale.is_default), PreschoolRatingScale.name)
        )
        return result.scalars().all()

    async def update_rating_scale(
        self,
        scale: PreschoolRatingScale,
        data: PreschoolRatingScaleUpdate,
        tenant_id: UUID,
    ) -> PreschoolRatingScale:
        """Update a rating scale."""
        # If promoting to default, demote any existing active defaults first
        if data.is_default and not scale.is_default:
            result = await self.db.execute(
                select(PreschoolRatingScale)
                .where(
                    and_(
                        PreschoolRatingScale.tenant_id == tenant_id,
                        PreschoolRatingScale.is_default == True,  # noqa: E712
                        PreschoolRatingScale.deleted_at.is_(None),
                    )
                )
            )
            for existing in result.scalars().all():
                existing.is_default = False

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scale, field, value)
        await self.db.flush()
        await self.db.refresh(scale)
        return scale

    async def delete_rating_scale(
        self,
        scale: PreschoolRatingScale,
    ) -> None:
        """Delete a rating scale and its ratings (soft delete)."""
        # Soft-delete associated ratings first
        if scale.ratings:
            for rating in scale.ratings:
                rating.deleted_at = datetime.utcnow()
        scale.deleted_at = datetime.utcnow()
        await self.db.flush()

    # =========================
    # Student Skill Assessments
    # =========================

    async def create_or_update_assessment(
        self,
        tenant_id: UUID,
        data: StudentSkillAssessmentCreate,
        user_id: UUID,
    ) -> StudentSkillAssessment:
        """Create or update a skill assessment (upsert by student+skill+term)."""
        # Check if assessment already exists for this student+skill+term combination
        result = await self.db.execute(
            select(StudentSkillAssessment)
            .where(
                and_(
                    StudentSkillAssessment.tenant_id == tenant_id,
                    StudentSkillAssessment.student_id == data.student_id,
                    StudentSkillAssessment.skill_id == data.skill_id,
                    StudentSkillAssessment.term_id == data.term_id,
                )
            )
        )
        assessment = result.scalar_one_or_none()

        if assessment:
            # Update existing assessment
            assessment.rating_id = data.rating_id
            assessment.observation_notes = data.observation_notes
            assessment.evidence_url = data.evidence_url
            assessment.assessed_by = user_id
            assessment.assessed_at = datetime.utcnow()
        else:
            # Create new assessment
            assessment = StudentSkillAssessment(
                tenant_id=tenant_id,
                student_id=data.student_id,
                skill_id=data.skill_id,
                academic_year_id=data.academic_year_id,
                term_id=data.term_id,
                rating_id=data.rating_id,
                observation_notes=data.observation_notes,
                evidence_url=data.evidence_url,
                assessed_by=user_id,
                assessed_at=datetime.utcnow(),
            )
            self.db.add(assessment)

        await self.db.flush()
        await self.db.refresh(assessment)
        return assessment

    async def bulk_assess(
        self,
        tenant_id: UUID,
        data: StudentSkillAssessmentBulk,
        user_id: UUID,
    ) -> dict[str, int]:
        """Bulk create/update assessments for a student.

        Returns a dict with 'created' and 'updated' counts.
        """
        created_count = 0
        updated_count = 0

        for entry in data.assessments:
            # Check if assessment already exists
            result = await self.db.execute(
                select(StudentSkillAssessment)
                .where(
                    and_(
                        StudentSkillAssessment.tenant_id == tenant_id,
                        StudentSkillAssessment.student_id == data.student_id,
                        StudentSkillAssessment.skill_id == entry.skill_id,
                        StudentSkillAssessment.term_id == data.term_id,
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.rating_id = entry.rating_id
                existing.observation_notes = entry.observation_notes
                existing.assessed_by = user_id
                existing.assessed_at = datetime.utcnow()
                updated_count += 1
            else:
                assessment = StudentSkillAssessment(
                    tenant_id=tenant_id,
                    student_id=data.student_id,
                    skill_id=entry.skill_id,
                    academic_year_id=data.academic_year_id,
                    term_id=data.term_id,
                    rating_id=entry.rating_id,
                    observation_notes=entry.observation_notes,
                    assessed_by=user_id,
                    assessed_at=datetime.utcnow(),
                )
                self.db.add(assessment)
                created_count += 1

        await self.db.flush()
        return {"created": created_count, "updated": updated_count}

    async def list_assessments(
        self,
        tenant_id: UUID,
        student_id: UUID | None = None,
        term_id: UUID | None = None,
        learning_area_id: UUID | None = None,
    ) -> Sequence[StudentSkillAssessment]:
        """List assessments with filters."""
        query = select(StudentSkillAssessment).options(
            joinedload(StudentSkillAssessment.skill),
            joinedload(StudentSkillAssessment.rating),
        ).where(StudentSkillAssessment.tenant_id == tenant_id)

        if student_id:
            query = query.where(StudentSkillAssessment.student_id == student_id)
        if term_id:
            query = query.where(StudentSkillAssessment.term_id == term_id)

        result = await self.db.execute(query)
        assessments = result.scalars().all()

        # Filter by learning area if provided (in-memory since it requires join through skill)
        if learning_area_id:
            assessments = [
                a for a in assessments
                if a.skill and a.skill.learning_area_id == learning_area_id
            ]

        return assessments

    # =========================
    # Seed Data
    # =========================

    async def seed_learning_areas(
        self,
        tenant_id: UUID,
        include_skills: bool = True,
    ) -> list[LearningArea]:
        """Seed default learning areas and optionally skills.

        Returns existing areas if they already exist (idempotent).
        """
        # Check if learning areas already exist for this tenant
        existing_result = await self.db.execute(
            select(LearningArea).where(
                and_(
                    LearningArea.tenant_id == tenant_id,
                    LearningArea.deleted_at.is_(None),
                )
            )
        )
        existing_areas = existing_result.scalars().all()

        if existing_areas:
            # Idempotent: return existing areas instead of creating duplicates
            return list(existing_areas)

        areas = []
        for area_data in DEFAULT_LEARNING_AREAS:
            area = LearningArea(
                tenant_id=tenant_id,
                **area_data,
            )
            self.db.add(area)
            areas.append(area)

        await self.db.flush()

        # Add skills if requested
        if include_skills:
            for area in areas:
                skills_data = DEFAULT_SKILLS_BY_AREA.get(area.code, [])
                for i, skill_data in enumerate(skills_data):
                    skill = DevelopmentalSkill(
                        tenant_id=tenant_id,
                        learning_area_id=area.id,
                        display_order=i,
                        **skill_data,
                    )
                    self.db.add(skill)

        await self.db.flush()
        return areas

    async def seed_rating_scale(
        self,
        tenant_id: UUID,
        set_as_default: bool = True,
    ) -> PreschoolRatingScale:
        """Seed the default rating scale.

        Returns existing scale if one already exists (idempotent).
        """
        # Check if a rating scale already exists for this tenant
        existing_result = await self.db.execute(
            select(PreschoolRatingScale).where(
                and_(
                    PreschoolRatingScale.tenant_id == tenant_id,
                    PreschoolRatingScale.deleted_at.is_(None),
                )
            )
        )
        existing_scale = existing_result.scalars().first()

        if existing_scale:
            # Idempotent: return existing scale instead of creating duplicate
            return existing_scale

        scale = PreschoolRatingScale(
            tenant_id=tenant_id,
            name=DEFAULT_RATING_SCALE["name"],
            description=DEFAULT_RATING_SCALE["description"],
            is_default=set_as_default,
        )
        self.db.add(scale)
        await self.db.flush()

        for rating_data in DEFAULT_RATING_SCALE["ratings"]:
            rating = PreschoolRating(
                tenant_id=tenant_id,
                scale_id=scale.id,
                **rating_data,
            )
            self.db.add(rating)

        await self.db.flush()
        await self.db.refresh(scale)
        return scale

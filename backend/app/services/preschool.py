"""
SIMS Plus - Preschool Service

Business logic for preschool functionality.
"""

from datetime import date, datetime
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
    ProgressObservation,
    DailyActivityLog,
    PreschoolReport,
)
from app.models.student import Student
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
    ProgressObservationCreate,
    ProgressObservationUpdate,
    DailyActivityLogCreate,
    DailyActivityLogUpdate,
    PreschoolReportCreate,
    PreschoolReportUpdate,
)


# =========================
# Default Seed Data
# =========================

DEFAULT_LEARNING_AREAS = [
    {
        "name": "Social-Emotional Development",
        "code": "SED",
        "description": "Building relationships, understanding emotions, and developing social skills",
        "icon": "heart",
        "color": "#ef4444",
        "display_order": 1,
    },
    {
        "name": "Language & Literacy",
        "code": "LL",
        "description": "Communication, vocabulary, reading readiness, and early writing skills",
        "icon": "book",
        "color": "#3b82f6",
        "display_order": 2,
    },
    {
        "name": "Mathematical Thinking",
        "code": "MT",
        "description": "Numbers, counting, patterns, shapes, and early math concepts",
        "icon": "calculator",
        "color": "#8b5cf6",
        "display_order": 3,
    },
    {
        "name": "Scientific Exploration",
        "code": "SE",
        "description": "Curiosity, observation, exploration, and understanding of the natural world",
        "icon": "flask",
        "color": "#22c55e",
        "display_order": 4,
    },
    {
        "name": "Physical Development - Gross Motor",
        "code": "PD-GM",
        "description": "Large muscle movement, coordination, balance, and physical activity",
        "icon": "running",
        "color": "#f97316",
        "display_order": 5,
    },
    {
        "name": "Physical Development - Fine Motor",
        "code": "PD-FM",
        "description": "Small muscle control, hand-eye coordination, and manual dexterity",
        "icon": "hand",
        "color": "#eab308",
        "display_order": 6,
    },
    {
        "name": "Creative Arts & Expression",
        "code": "CA",
        "description": "Art, music, drama, creative expression, and imagination",
        "icon": "palette",
        "color": "#ec4899",
        "display_order": 7,
    },
    {
        "name": "Personal Hygiene & Self-Care",
        "code": "PH",
        "description": "Self-care routines, hygiene habits, and independence skills",
        "icon": "sparkles",
        "color": "#06b6d4",
        "display_order": 8,
    },
]

DEFAULT_SKILLS_BY_AREA = {
    "SED": [
        {"name": "Separates from caregiver with ease", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Plays alongside other children (parallel play)", "age_range_months_min": 24, "age_range_months_max": 36},
        {"name": "Plays cooperatively with peers", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Shares toys and materials when prompted", "age_range_months_min": 30, "age_range_months_max": 48},
        {"name": "Shares spontaneously without prompting", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Expresses emotions verbally", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Manages strong emotions appropriately", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Shows empathy towards others", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Follows classroom rules", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Takes turns in games and activities", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
    "LL": [
        {"name": "Recognizes own name in print", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Speaks in complete sentences", "age_range_months_min": 36, "age_range_months_max": 48},
        {"name": "Identifies letters of the alphabet", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Recognizes rhyming words", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Holds a book correctly", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Listens to stories with interest", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Retells a simple story in sequence", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Writes own name", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Makes marks that represent letters", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Follows two-step verbal instructions", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
    "MT": [
        {"name": "Counts to 10", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Counts to 20", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Recognizes numbers 1-10", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Identifies basic shapes (circle, square, triangle)", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Sorts objects by color", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Sorts objects by size", "age_range_months_min": 30, "age_range_months_max": 48},
        {"name": "Understands concepts of more/less", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Recognizes simple patterns", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Creates simple patterns", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Understands positional words (in, on, under)", "age_range_months_min": 30, "age_range_months_max": 48},
    ],
    "SE": [
        {"name": "Shows curiosity about surroundings", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Asks questions about the world", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Makes observations about nature", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Participates in simple experiments", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Identifies living vs non-living things", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Explores with senses (touch, smell, taste, sight, sound)", "age_range_months_min": 24, "age_range_months_max": 60},
        {"name": "Makes predictions about outcomes", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Cares for classroom plants/animals", "age_range_months_min": 48, "age_range_months_max": 72},
    ],
    "PD-GM": [
        {"name": "Walks steadily", "age_range_months_min": 12, "age_range_months_max": 24},
        {"name": "Runs with coordination", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Climbs playground equipment safely", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Jumps with both feet", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Hops on one foot", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Throws a ball overhand", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Catches a large ball", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Kicks a ball forward", "age_range_months_min": 30, "age_range_months_max": 48},
        {"name": "Balances on one foot for 5 seconds", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Pedals a tricycle", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
    "PD-FM": [
        {"name": "Holds crayon/pencil correctly", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Uses scissors to cut on a line", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Strings large beads", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Builds with blocks (stacks 6+ blocks)", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Draws recognizable pictures", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Colors within lines", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Buttons and unbuttons clothing", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Uses zippers", "age_range_months_min": 48, "age_range_months_max": 72},
        {"name": "Ties shoelaces", "age_range_months_min": 60, "age_range_months_max": 84},
        {"name": "Traces shapes and letters", "age_range_months_min": 48, "age_range_months_max": 72},
    ],
    "CA": [
        {"name": "Participates in music activities", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Sings simple songs", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Moves to music rhythmically", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Engages in pretend play", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Creates artwork using various materials", "age_range_months_min": 24, "age_range_months_max": 72},
        {"name": "Expresses ideas through art", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Participates in dramatic play", "age_range_months_min": 36, "age_range_months_max": 72},
        {"name": "Shows creativity in building/constructing", "age_range_months_min": 36, "age_range_months_max": 72},
    ],
    "PH": [
        {"name": "Washes hands properly", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Uses toilet independently", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Feeds self with utensils", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Drinks from a cup without spilling", "age_range_months_min": 24, "age_range_months_max": 36},
        {"name": "Puts on shoes (not necessarily tied)", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Puts on and removes coat", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Brushes teeth with assistance", "age_range_months_min": 24, "age_range_months_max": 48},
        {"name": "Blows nose into tissue", "age_range_months_min": 36, "age_range_months_max": 60},
        {"name": "Covers mouth when coughing", "age_range_months_min": 36, "age_range_months_max": 60},
    ],
}

DEFAULT_RATING_SCALE = {
    "name": "5-Point Developmental Scale",
    "description": "Standard developmental assessment scale for preschool",
    "ratings": [
        {
            "name": "Not Yet Observed",
            "short_code": "NYO",
            "description": "Skill not yet observed or too early for developmental stage",
            "numeric_value": 0,
            "color": "#9ca3af",
            "icon": "circle-dashed",
            "display_order": 0,
        },
        {
            "name": "Emerging",
            "short_code": "E",
            "description": "Beginning to show awareness or initial attempts",
            "numeric_value": 1,
            "color": "#ef4444",
            "icon": "circle",
            "display_order": 1,
        },
        {
            "name": "Developing",
            "short_code": "D",
            "description": "Progressing, needs support or reminders",
            "numeric_value": 2,
            "color": "#eab308",
            "icon": "circle-half",
            "display_order": 2,
        },
        {
            "name": "Proficient",
            "short_code": "P",
            "description": "Consistently demonstrates skill independently",
            "numeric_value": 3,
            "color": "#22c55e",
            "icon": "check-circle",
            "display_order": 3,
        },
        {
            "name": "Advanced",
            "short_code": "A",
            "description": "Exceeds age-appropriate expectations",
            "numeric_value": 4,
            "color": "#3b82f6",
            "icon": "star",
            "display_order": 4,
        },
    ],
}


class PreschoolServiceError(Exception):
    """Base exception for preschool service errors."""

    def __init__(self, message: str, code: str = "preschool_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class PreschoolService:
    """Service for preschool functionality."""

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
    # Progress Observations
    # =========================

    async def create_observation(
        self,
        tenant_id: UUID,
        data: ProgressObservationCreate,
        user_id: UUID,
    ) -> ProgressObservation:
        """Create a progress observation."""
        observation = ProgressObservation(
            tenant_id=tenant_id,
            student_id=data.student_id,
            learning_area_id=data.learning_area_id,
            observation_type=data.observation_type,
            title=data.title,
            description=data.description,
            observation_date=data.observation_date,
            attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
            share_with_parents=data.share_with_parents,
            is_highlight=data.is_highlight,
            recorded_by=user_id,
        )
        self.db.add(observation)
        await self.db.flush()
        await self.db.refresh(observation)
        return observation

    async def get_observation(
        self,
        tenant_id: UUID,
        observation_id: UUID,
    ) -> ProgressObservation:
        """Get an observation by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(ProgressObservation)
            .where(
                and_(
                    ProgressObservation.id == observation_id,
                    ProgressObservation.tenant_id == tenant_id,
                    ProgressObservation.deleted_at.is_(None),
                )
            )
        )
        observation = result.scalar_one_or_none()
        if not observation:
            raise PreschoolServiceError("Observation not found", "not_found")
        return observation

    async def list_observations(
        self,
        tenant_id: UUID,
        student_id: UUID | None = None,
        observation_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> Sequence[ProgressObservation]:
        """List observations with filters."""
        query = select(ProgressObservation).where(
            and_(
                ProgressObservation.tenant_id == tenant_id,
                ProgressObservation.deleted_at.is_(None),
            )
        )

        if student_id:
            query = query.where(ProgressObservation.student_id == student_id)
        if observation_type:
            query = query.where(ProgressObservation.observation_type == observation_type)
        if start_date:
            query = query.where(ProgressObservation.observation_date >= start_date)
        if end_date:
            query = query.where(ProgressObservation.observation_date <= end_date)

        query = query.order_by(desc(ProgressObservation.observation_date)).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_observation(
        self,
        observation: ProgressObservation,
        data: ProgressObservationUpdate,
    ) -> ProgressObservation:
        """Update an observation."""
        update_data = data.model_dump(exclude_unset=True)
        if "attachments" in update_data and update_data["attachments"]:
            update_data["attachments"] = [a.model_dump() if hasattr(a, "model_dump") else a for a in update_data["attachments"]]
        for field, value in update_data.items():
            setattr(observation, field, value)
        await self.db.flush()
        await self.db.refresh(observation)
        return observation

    async def delete_observation(
        self,
        observation: ProgressObservation,
    ) -> None:
        """Soft delete an observation."""
        observation.deleted_at = datetime.utcnow()
        await self.db.flush()

    # =========================
    # Daily Activity Logs
    # =========================

    async def create_or_update_daily_log(
        self,
        tenant_id: UUID,
        data: DailyActivityLogCreate,
        user_id: UUID,
    ) -> DailyActivityLog:
        """Create or update a daily activity log (upsert by student+date)."""
        # Check if log already exists for this student on this date
        result = await self.db.execute(
            select(DailyActivityLog)
            .where(
                and_(
                    DailyActivityLog.tenant_id == tenant_id,
                    DailyActivityLog.student_id == data.student_id,
                    DailyActivityLog.log_date == data.log_date,
                    DailyActivityLog.deleted_at.is_(None),
                )
            )
        )
        log = result.scalar_one_or_none()

        meals_data = [m.model_dump() for m in data.meals] if data.meals else None

        if log:
            # Update existing log
            log.arrival_time = data.arrival_time
            log.arrival_mood = data.arrival_mood
            log.departure_time = data.departure_time
            log.departure_mood = data.departure_mood
            log.meals = meals_data
            log.nap_start = data.nap_start
            log.nap_end = data.nap_end
            log.nap_quality = data.nap_quality
            log.diaper_changes = data.diaper_changes
            log.potty_successes = data.potty_successes
            log.accidents = data.accidents
            log.activities = data.activities
            log.notes = data.notes
            log.highlights = data.highlights
            log.logged_by = user_id
        else:
            # Create new log
            log = DailyActivityLog(
                tenant_id=tenant_id,
                student_id=data.student_id,
                log_date=data.log_date,
                arrival_time=data.arrival_time,
                arrival_mood=data.arrival_mood,
                departure_time=data.departure_time,
                departure_mood=data.departure_mood,
                meals=meals_data,
                nap_start=data.nap_start,
                nap_end=data.nap_end,
                nap_quality=data.nap_quality,
                diaper_changes=data.diaper_changes,
                potty_successes=data.potty_successes,
                accidents=data.accidents,
                activities=data.activities,
                notes=data.notes,
                highlights=data.highlights,
                logged_by=user_id,
            )
            self.db.add(log)

        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def get_daily_log(
        self,
        tenant_id: UUID,
        log_id: UUID,
    ) -> DailyActivityLog:
        """Get a daily log by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(DailyActivityLog)
            .where(
                and_(
                    DailyActivityLog.id == log_id,
                    DailyActivityLog.tenant_id == tenant_id,
                    DailyActivityLog.deleted_at.is_(None),
                )
            )
        )
        log = result.scalar_one_or_none()
        if not log:
            raise PreschoolServiceError("Daily log not found", "not_found")
        return log

    async def list_daily_logs(
        self,
        tenant_id: UUID,
        student_id: UUID | None = None,
        log_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        class_id: UUID | None = None,
        limit: int = 50,
    ) -> Sequence[DailyActivityLog]:
        """List daily logs with filters."""
        query = select(DailyActivityLog).options(
            joinedload(DailyActivityLog.student)
        ).where(
            and_(
                DailyActivityLog.tenant_id == tenant_id,
                DailyActivityLog.deleted_at.is_(None),
            )
        )

        if student_id:
            query = query.where(DailyActivityLog.student_id == student_id)
        if log_date:
            query = query.where(DailyActivityLog.log_date == log_date)
        if start_date:
            query = query.where(DailyActivityLog.log_date >= start_date)
        if end_date:
            query = query.where(DailyActivityLog.log_date <= end_date)

        query = query.order_by(desc(DailyActivityLog.log_date)).limit(limit)
        result = await self.db.execute(query)
        logs = result.scalars().all()

        # Filter by class if provided (in-memory since it requires join through student)
        if class_id:
            logs = [log for log in logs if log.student and log.student.class_id == class_id]

        return logs

    # =========================
    # Preschool Reports
    # =========================

    async def create_report(
        self,
        tenant_id: UUID,
        data: PreschoolReportCreate,
    ) -> PreschoolReport:
        """Create a preschool report."""
        report = PreschoolReport(
            tenant_id=tenant_id,
            student_id=data.student_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            days_present=data.days_present,
            days_absent=data.days_absent,
            total_school_days=data.total_school_days,
            # mode='json' ensures UUIDs are serialized as strings for JSONB storage
            learning_area_summaries=[s.model_dump(mode='json') for s in data.learning_area_summaries] if data.learning_area_summaries else None,
            overall_progress=data.overall_progress,
            strengths=data.strengths,
            areas_for_growth=data.areas_for_growth,
            teacher_recommendations=data.teacher_recommendations,
            highlights=data.highlights,
            next_term_goals=data.next_term_goals,
            class_teacher_remark=data.class_teacher_remark,
            head_teacher_remark=data.head_teacher_remark,
        )
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def get_report(
        self,
        tenant_id: UUID,
        report_id: UUID,
    ) -> PreschoolReport:
        """Get a report by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(PreschoolReport)
            .where(
                and_(
                    PreschoolReport.id == report_id,
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            raise PreschoolServiceError("Report not found", "not_found")
        return report

    async def list_reports(
        self,
        tenant_id: UUID,
        student_id: UUID | None = None,
        term_id: UUID | None = None,
        class_id: UUID | None = None,
        is_published: bool | None = None,
    ) -> Sequence[PreschoolReport]:
        """List reports with filters."""
        query = select(PreschoolReport).where(
            and_(
                PreschoolReport.tenant_id == tenant_id,
                PreschoolReport.deleted_at.is_(None),
            )
        )

        if student_id:
            query = query.where(PreschoolReport.student_id == student_id)
        if term_id:
            query = query.where(PreschoolReport.term_id == term_id)
        if class_id:
            query = query.where(PreschoolReport.class_id == class_id)
        if is_published is not None:
            query = query.where(PreschoolReport.is_published == is_published)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_report(
        self,
        report: PreschoolReport,
        data: PreschoolReportUpdate,
    ) -> PreschoolReport:
        """Update a report."""
        update_data = data.model_dump(exclude_unset=True)
        if "learning_area_summaries" in update_data and update_data["learning_area_summaries"]:
            update_data["learning_area_summaries"] = [
                s.model_dump() if hasattr(s, "model_dump") else s
                for s in update_data["learning_area_summaries"]
            ]
        for field, value in update_data.items():
            setattr(report, field, value)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def publish_reports(
        self,
        tenant_id: UUID,
        report_ids: list[UUID],
    ) -> list[PreschoolReport]:
        """Publish multiple reports."""
        result = await self.db.execute(
            select(PreschoolReport)
            .where(
                and_(
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.id.in_(report_ids),
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        reports = list(result.scalars().all())
        if not reports:
            raise PreschoolServiceError("No matching reports found to publish", "not_found")
        now = datetime.utcnow()
        for report in reports:
            report.is_published = True
            report.published_at = now
        await self.db.flush()
        return reports

    async def generate_reports(
        self,
        tenant_id: UUID,
        class_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
    ) -> dict:
        """Generate reports for all students in a class for a given term."""
        # Get all active students in the class
        students_result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.class_id == class_id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                )
            )
        )
        students = students_result.scalars().all()

        # Determine which students already have reports for this term
        existing_reports_result = await self.db.execute(
            select(PreschoolReport.student_id).where(
                and_(
                    PreschoolReport.tenant_id == tenant_id,
                    PreschoolReport.class_id == class_id,
                    PreschoolReport.academic_year_id == academic_year_id,
                    PreschoolReport.term_id == term_id,
                    PreschoolReport.deleted_at.is_(None),
                )
            )
        )
        existing_student_ids = set(existing_reports_result.scalars().all())

        # Create blank reports for students who don't have one yet
        generated_count = 0
        for student in students:
            if student.id not in existing_student_ids:
                report = PreschoolReport(
                    tenant_id=tenant_id,
                    student_id=student.id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    class_id=class_id,
                )
                self.db.add(report)
                generated_count += 1

        if generated_count > 0:
            await self.db.flush()

        return {"generated": generated_count, "total_students": len(students)}

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

"""
SIMS Plus - Preschool Portfolio Service

Business logic for learning stories and student timelines.
"""

from datetime import date, datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preschool import (
    DevelopmentalSkill,
    LearningArea,
    LearningStory,
    PreschoolIncident,
    ProgressObservation,
    StudentSkillAssessment,
)
from app.models.student import Student
from app.schemas.preschool import (
    LearningStoryCreate,
    LearningStoryUpdate,
)
from app.services.preschool._shared import PreschoolServiceError


class PreschoolPortfolioService:
    """Service for learning stories and student timelines."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Learning Stories
    # =========================

    async def create_learning_story(
        self,
        tenant_id: UUID,
        data: LearningStoryCreate,
        created_by: UUID,
    ) -> LearningStory:
        """Create a learning story.

        SECURITY: Validates that the student and all referenced IDs
        (learning areas, skills, observations) belong to the same tenant.
        This prevents cross-tenant reference injection via JSONB arrays.
        """
        # Validate student belongs to tenant
        student = await self._validate_student(tenant_id, data.student_id)

        # Validate referenced learning area IDs belong to tenant
        if data.learning_area_ids:
            await self._validate_learning_area_ids(tenant_id, data.learning_area_ids)

        # Validate referenced skill IDs belong to tenant
        if data.skill_ids:
            await self._validate_skill_ids(tenant_id, data.skill_ids)

        # Validate referenced observation IDs belong to tenant
        if data.observation_ids:
            await self._validate_observation_ids(tenant_id, data.observation_ids)

        story = LearningStory(
            tenant_id=tenant_id,
            student_id=data.student_id,
            term_id=data.term_id,
            title=data.title,
            narrative=data.narrative,
            # Store UUIDs as strings for JSONB compatibility
            learning_area_ids=[str(uid) for uid in data.learning_area_ids] if data.learning_area_ids else None,
            skill_ids=[str(uid) for uid in data.skill_ids] if data.skill_ids else None,
            observation_ids=[str(uid) for uid in data.observation_ids] if data.observation_ids else None,
            attachments=[a.model_dump() for a in data.attachments] if data.attachments else None,
            is_shared_with_parents=data.is_shared_with_parents,
            created_by=created_by,
        )
        self.db.add(story)
        await self.db.flush()
        await self.db.refresh(story)
        return story

    async def list_learning_stories(
        self,
        tenant_id: UUID,
        *,
        student_id: UUID | None = None,
        term_id: UUID | None = None,
        shared_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[LearningStory]:
        """List learning stories with filters.

        shared_only=True restricts to stories visible to parents (parent portal).
        """
        query = select(LearningStory).where(
            and_(
                LearningStory.tenant_id == tenant_id,
                LearningStory.deleted_at.is_(None),
            )
        )

        if student_id:
            query = query.where(LearningStory.student_id == student_id)
        if term_id:
            query = query.where(LearningStory.term_id == term_id)
        if shared_only:
            query = query.where(LearningStory.is_shared_with_parents.is_(True))

        query = query.order_by(desc(LearningStory.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_learning_story(
        self,
        tenant_id: UUID,
        story_id: UUID,
    ) -> LearningStory:
        """Get a learning story by ID.

        Raises PreschoolServiceError if not found.
        """
        result = await self.db.execute(
            select(LearningStory).where(
                and_(
                    LearningStory.id == story_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    LearningStory.tenant_id == tenant_id,
                    LearningStory.deleted_at.is_(None),
                )
            )
        )
        story = result.scalar_one_or_none()
        if not story:
            raise PreschoolServiceError("Learning story not found", "not_found")
        return story

    async def update_learning_story(
        self,
        tenant_id: UUID,
        story_id: UUID,
        data: LearningStoryUpdate,
    ) -> LearningStory:
        """Update a learning story."""
        story = await self.get_learning_story(tenant_id, story_id)
        update_data = data.model_dump(exclude_unset=True)

        # Validate referenced IDs if being updated
        if "learning_area_ids" in update_data and update_data["learning_area_ids"]:
            await self._validate_learning_area_ids(tenant_id, update_data["learning_area_ids"])
            update_data["learning_area_ids"] = [str(uid) for uid in update_data["learning_area_ids"]]

        if "skill_ids" in update_data and update_data["skill_ids"]:
            await self._validate_skill_ids(tenant_id, update_data["skill_ids"])
            update_data["skill_ids"] = [str(uid) for uid in update_data["skill_ids"]]

        if "observation_ids" in update_data and update_data["observation_ids"]:
            await self._validate_observation_ids(tenant_id, update_data["observation_ids"])
            update_data["observation_ids"] = [str(uid) for uid in update_data["observation_ids"]]

        if "attachments" in update_data and update_data["attachments"]:
            update_data["attachments"] = [
                a.model_dump() if hasattr(a, "model_dump") else a
                for a in update_data["attachments"]
            ]

        for field, value in update_data.items():
            setattr(story, field, value)

        await self.db.flush()
        await self.db.refresh(story)
        return story

    async def delete_learning_story(
        self,
        tenant_id: UUID,
        story_id: UUID,
    ) -> None:
        """Soft-delete a learning story."""
        story = await self.get_learning_story(tenant_id, story_id)
        story.deleted_at = datetime.utcnow()
        await self.db.flush()

    # =========================
    # Student Timeline
    # =========================

    async def get_student_timeline(
        self,
        tenant_id: UUID,
        student_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Aggregated timeline of a student's preschool journey.

        Queries 4 tables and merges results into a unified timeline sorted
        by date DESC. Uses 4 separate queries (not UNION ALL) because the
        columns differ. For preschool volumes this is efficient enough.
        """
        # Validate student belongs to tenant
        await self._validate_student(tenant_id, student_id)

        entries: list[dict] = []

        # 1. Skill assessments
        assessments = await self._query_assessment_entries(
            tenant_id, student_id, date_from, date_to, limit
        )
        entries.extend(assessments)

        # 2. Progress observations
        observations = await self._query_observation_entries(
            tenant_id, student_id, date_from, date_to, limit
        )
        entries.extend(observations)

        # 3. Incidents
        incidents = await self._query_incident_entries(
            tenant_id, student_id, date_from, date_to, limit
        )
        entries.extend(incidents)

        # 4. Learning stories
        stories = await self._query_learning_story_entries(
            tenant_id, student_id, date_from, date_to, limit
        )
        entries.extend(stories)

        # Sort all entries by date DESC and apply final limit
        entries.sort(key=lambda e: e["date"], reverse=True)
        return entries[:limit]

    # =========================
    # Private Helpers
    # =========================

    async def _validate_student(self, tenant_id: UUID, student_id: UUID) -> Student:
        """Validate student exists and belongs to tenant."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found", "not_found")
        return student

    async def _validate_learning_area_ids(self, tenant_id: UUID, ids: list[UUID]) -> None:
        """Validate all learning area IDs belong to this tenant."""
        result = await self.db.execute(
            select(func.count(LearningArea.id)).where(
                and_(
                    LearningArea.id.in_(ids),
                    LearningArea.tenant_id == tenant_id,
                    LearningArea.deleted_at.is_(None),
                )
            )
        )
        count = result.scalar()
        if count != len(ids):
            raise PreschoolServiceError(
                "One or more learning area IDs are invalid or belong to another tenant",
                "validation_error",
            )

    async def _validate_skill_ids(self, tenant_id: UUID, ids: list[UUID]) -> None:
        """Validate all skill IDs belong to this tenant."""
        result = await self.db.execute(
            select(func.count(DevelopmentalSkill.id)).where(
                and_(
                    DevelopmentalSkill.id.in_(ids),
                    DevelopmentalSkill.tenant_id == tenant_id,
                    DevelopmentalSkill.deleted_at.is_(None),
                )
            )
        )
        count = result.scalar()
        if count != len(ids):
            raise PreschoolServiceError(
                "One or more skill IDs are invalid or belong to another tenant",
                "validation_error",
            )

    async def _validate_observation_ids(self, tenant_id: UUID, ids: list[UUID]) -> None:
        """Validate all observation IDs belong to this tenant."""
        result = await self.db.execute(
            select(func.count(ProgressObservation.id)).where(
                and_(
                    ProgressObservation.id.in_(ids),
                    ProgressObservation.tenant_id == tenant_id,
                    ProgressObservation.deleted_at.is_(None),
                )
            )
        )
        count = result.scalar()
        if count != len(ids):
            raise PreschoolServiceError(
                "One or more observation IDs are invalid or belong to another tenant",
                "validation_error",
            )

    async def _query_assessment_entries(
        self, tenant_id: UUID, student_id: UUID,
        date_from: date | None, date_to: date | None, limit: int,
    ) -> list[dict]:
        """Query skill assessments for timeline."""
        query = select(StudentSkillAssessment).where(
            and_(
                StudentSkillAssessment.tenant_id == tenant_id,
                StudentSkillAssessment.student_id == student_id,
            )
        )
        if date_from:
            query = query.where(func.date(StudentSkillAssessment.assessed_at) >= date_from)
        if date_to:
            query = query.where(func.date(StudentSkillAssessment.assessed_at) <= date_to)

        query = query.order_by(desc(StudentSkillAssessment.assessed_at)).limit(limit)
        result = await self.db.execute(query)
        assessments = result.scalars().all()

        return [
            {
                "date": a.assessed_at.date() if a.assessed_at else a.created_at.date(),
                "type": "assessment",
                "title": f"Skill assessment recorded",
                "summary": a.observation_notes[:100] if a.observation_notes else None,
                "details": {
                    "skill_id": str(a.skill_id),
                    "rating_id": str(a.rating_id) if a.rating_id else None,
                    "term_id": str(a.term_id),
                    "observation_notes": a.observation_notes,
                },
                "id": a.id,
            }
            for a in assessments
        ]

    async def _query_observation_entries(
        self, tenant_id: UUID, student_id: UUID,
        date_from: date | None, date_to: date | None, limit: int,
    ) -> list[dict]:
        """Query progress observations for timeline."""
        query = select(ProgressObservation).where(
            and_(
                ProgressObservation.tenant_id == tenant_id,
                ProgressObservation.student_id == student_id,
                ProgressObservation.deleted_at.is_(None),
            )
        )
        if date_from:
            query = query.where(ProgressObservation.observation_date >= date_from)
        if date_to:
            query = query.where(ProgressObservation.observation_date <= date_to)

        query = query.order_by(desc(ProgressObservation.observation_date)).limit(limit)
        result = await self.db.execute(query)
        observations = result.scalars().all()

        return [
            {
                "date": o.observation_date,
                "type": "observation",
                "title": o.title,
                "summary": o.description[:100] if o.description else None,
                "details": {
                    "observation_type": o.observation_type,
                    "description": o.description,
                    "learning_area_id": str(o.learning_area_id) if o.learning_area_id else None,
                    "is_highlight": o.is_highlight,
                },
                "id": o.id,
            }
            for o in observations
        ]

    async def _query_incident_entries(
        self, tenant_id: UUID, student_id: UUID,
        date_from: date | None, date_to: date | None, limit: int,
    ) -> list[dict]:
        """Query preschool incidents for timeline."""
        query = select(PreschoolIncident).where(
            and_(
                PreschoolIncident.tenant_id == tenant_id,
                PreschoolIncident.student_id == student_id,
                PreschoolIncident.deleted_at.is_(None),
            )
        )
        if date_from:
            query = query.where(PreschoolIncident.incident_date >= date_from)
        if date_to:
            query = query.where(PreschoolIncident.incident_date <= date_to)

        query = query.order_by(desc(PreschoolIncident.incident_date)).limit(limit)
        result = await self.db.execute(query)
        incidents = result.scalars().all()

        return [
            {
                "date": i.incident_date,
                "type": "incident",
                "title": f"{i.incident_type.replace('_', ' ').title()} - {i.severity}",
                "summary": i.description[:100] if i.description else None,
                "details": {
                    "incident_type": i.incident_type,
                    "severity": i.severity,
                    "status": i.status,
                    "description": i.description,
                    "action_taken": i.action_taken,
                },
                "id": i.id,
            }
            for i in incidents
        ]

    async def _query_learning_story_entries(
        self, tenant_id: UUID, student_id: UUID,
        date_from: date | None, date_to: date | None, limit: int,
    ) -> list[dict]:
        """Query learning stories for timeline."""
        query = select(LearningStory).where(
            and_(
                LearningStory.tenant_id == tenant_id,
                LearningStory.student_id == student_id,
                LearningStory.deleted_at.is_(None),
            )
        )
        if date_from:
            query = query.where(func.date(LearningStory.created_at) >= date_from)
        if date_to:
            query = query.where(func.date(LearningStory.created_at) <= date_to)

        query = query.order_by(desc(LearningStory.created_at)).limit(limit)
        result = await self.db.execute(query)
        stories = result.scalars().all()

        return [
            {
                "date": s.created_at.date(),
                "type": "learning_story",
                "title": s.title,
                "summary": s.narrative[:100] if s.narrative else None,
                "details": {
                    "narrative": s.narrative,
                    "learning_area_ids": s.learning_area_ids,
                    "skill_ids": s.skill_ids,
                    "is_shared_with_parents": s.is_shared_with_parents,
                },
                "id": s.id,
            }
            for s in stories
        ]

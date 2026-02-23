"""
SIMS Plus - Teacher Lesson Plan Service

CRUD operations for lesson plans. Teachers create plans for their
assigned classes/subjects with topic, objectives, resources, and status.
"""

from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, Subject
from app.models.teacher import LessonPlan, LessonPlanStatus

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherLessonService:
    """
    Lesson plan CRUD scoped to the authenticated teacher.

    All queries filter by tenant_id and teacher_id for defense-in-depth.
    Teachers can only see and modify their own lesson plans.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_lesson_plans(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        class_id: UUID | None = None,
        subject_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status: LessonPlanStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        List lesson plans for this teacher with optional filters.

        Returns (plans, total_count) tuple for pagination.
        """
        base_filter = and_(
            LessonPlan.tenant_id == tenant_id,
            LessonPlan.teacher_id == staff_id,
            LessonPlan.deleted_at.is_(None),
        )

        query = select(LessonPlan).where(base_filter)
        count_query = select(func.count(LessonPlan.id)).where(base_filter)

        if class_id:
            query = query.where(LessonPlan.class_id == class_id)
            count_query = count_query.where(LessonPlan.class_id == class_id)
        if subject_id:
            query = query.where(LessonPlan.subject_id == subject_id)
            count_query = count_query.where(LessonPlan.subject_id == subject_id)
        if date_from:
            query = query.where(LessonPlan.date >= date_from)
            count_query = count_query.where(LessonPlan.date >= date_from)
        if date_to:
            query = query.where(LessonPlan.date <= date_to)
            count_query = count_query.where(LessonPlan.date <= date_to)
        if status:
            query = query.where(LessonPlan.status == status)
            count_query = count_query.where(LessonPlan.status == status)

        # Get total count
        total = (await self.db.execute(count_query)).scalar_one()

        # Get paginated results with eager loading
        query = (
            query
            .options(
                selectinload(LessonPlan.class_),
                selectinload(LessonPlan.subject),
            )
            .order_by(LessonPlan.date.desc(), LessonPlan.period)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        plans = result.scalars().all()

        return [self._format_plan(p) for p in plans], total

    async def get_lesson_plan(
        self, staff_id: UUID, tenant_id: UUID, plan_id: UUID
    ) -> dict:
        """
        Get a single lesson plan by ID.

        Verifies ownership (teacher_id matches) for defense-in-depth.
        """
        result = await self.db.execute(
            select(LessonPlan)
            .options(
                selectinload(LessonPlan.class_),
                selectinload(LessonPlan.subject),
            )
            .where(
                and_(
                    LessonPlan.id == plan_id,
                    LessonPlan.tenant_id == tenant_id,
                    LessonPlan.teacher_id == staff_id,
                    LessonPlan.deleted_at.is_(None),
                )
            )
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise TeacherServiceError("Lesson plan not found", code="not_found")
        return self._format_plan(plan)

    async def create_lesson_plan(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        data: dict,
    ) -> dict:
        """
        Create a new lesson plan.

        The teacher must be assigned to the class+subject combination
        (verified at the endpoint/context service level).
        """
        plan = LessonPlan(
            tenant_id=tenant_id,
            teacher_id=staff_id,
            class_id=data["class_id"],
            subject_id=data["subject_id"],
            date=data["date"],
            period=data.get("period"),
            topic=data["topic"],
            objectives=data.get("objectives"),
            resources=data.get("resources"),
            activities=data.get("activities"),
            notes=data.get("notes"),
            status=LessonPlanStatus.PLANNED,
        )
        self.db.add(plan)
        await self.db.flush()
        await self.db.refresh(plan)

        # Reload with relationships
        # Defense-in-depth: scope to tenant even though we just created this record
        loaded = await self.db.execute(
            select(LessonPlan)
            .options(
                selectinload(LessonPlan.class_),
                selectinload(LessonPlan.subject),
            )
            .where(
                and_(
                    LessonPlan.id == plan.id,
                    LessonPlan.tenant_id == tenant_id,
                )
            )
        )
        plan = loaded.scalar_one()

        return self._format_plan(plan)

    async def update_lesson_plan(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        plan_id: UUID,
        data: dict,
    ) -> dict:
        """
        Update an existing lesson plan.

        Only the owning teacher can update their plans. Cancelled plans
        cannot be updated (must be un-cancelled first by changing status).
        """
        result = await self.db.execute(
            select(LessonPlan)
            .where(
                and_(
                    LessonPlan.id == plan_id,
                    LessonPlan.tenant_id == tenant_id,
                    LessonPlan.teacher_id == staff_id,
                    LessonPlan.deleted_at.is_(None),
                )
            )
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise TeacherServiceError("Lesson plan not found", code="not_found")

        # Apply updates
        for field in ("topic", "objectives", "resources", "activities", "notes"):
            if field in data and data[field] is not None:
                setattr(plan, field, data[field])

        if "status" in data and data["status"] is not None:
            plan.status = LessonPlanStatus(data["status"])

        await self.db.flush()
        await self.db.refresh(plan)

        # Reload with relationships
        # Defense-in-depth: scope to tenant even though we just updated this record
        loaded = await self.db.execute(
            select(LessonPlan)
            .options(
                selectinload(LessonPlan.class_),
                selectinload(LessonPlan.subject),
            )
            .where(
                and_(
                    LessonPlan.id == plan.id,
                    LessonPlan.tenant_id == tenant_id,
                )
            )
        )
        plan = loaded.scalar_one()

        return self._format_plan(plan)

    async def delete_lesson_plan(
        self, staff_id: UUID, tenant_id: UUID, plan_id: UUID
    ) -> None:
        """
        Soft-delete a lesson plan.

        Only the owning teacher can delete their plans.
        """
        result = await self.db.execute(
            select(LessonPlan)
            .where(
                and_(
                    LessonPlan.id == plan_id,
                    LessonPlan.tenant_id == tenant_id,
                    LessonPlan.teacher_id == staff_id,
                    LessonPlan.deleted_at.is_(None),
                )
            )
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise TeacherServiceError("Lesson plan not found", code="not_found")

        plan.deleted_at = datetime.now(UTC)
        await self.db.flush()

    @staticmethod
    def _format_plan(plan: LessonPlan) -> dict:
        """Format a lesson plan for API response."""
        return {
            "id": plan.id,
            "teacher_id": plan.teacher_id,
            "class_id": plan.class_id,
            "class_name": plan.class_.name if plan.class_ else None,
            "subject_id": plan.subject_id,
            "subject_name": plan.subject.name if plan.subject else None,
            "date": plan.date,
            "period": plan.period,
            "topic": plan.topic,
            "objectives": plan.objectives,
            "resources": plan.resources,
            "activities": plan.activities,
            "notes": plan.notes,
            "status": plan.status.value if plan.status else "planned",
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

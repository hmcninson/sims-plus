"""
SIMS Plus - Interview & Screening Service

Handles interview scheduling, feedback recording, overlap detection,
and screening checklist management for the admissions module.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    Application,
    Interview,
    InterviewStatus,
    ScreeningChecklist,
    INTERVIEW_VALID_TRANSITIONS,
    TERMINAL_STATUSES,
)

logger = structlog.get_logger(__name__)


class InterviewServiceError(Exception):
    def __init__(self, message: str, code: str = "INTERVIEW_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InterviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    _PROTECTED_FIELDS = {
        "id", "tenant_id", "school_id", "created_at", "updated_at", "deleted_at",
    }

    # ---- Interview CRUD ----

    async def schedule(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        application_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        scheduled_date: date,
        scheduled_time: time | None = None,
        duration_minutes: int = 30,
        venue: str,
    ) -> Interview:
        """
        Schedule an interview for an application.

        Validations:
        1. Application exists and is not in a terminal status
        2. No existing active interview for this application
        3. Interviewer has no overlapping interview at same date/time
        """
        # Validate application exists in same tenant
        app_result = await self.db.execute(
            select(Application).filter(
                Application.id == application_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise InterviewServiceError("Application not found", "APP_NOT_FOUND")

        # Reject interviews for applications in terminal states
        if application.status in {s.value for s in TERMINAL_STATUSES}:
            raise InterviewServiceError(
                f"Cannot schedule interview for application in '{application.status}' status",
                "TERMINAL_STATUS",
            )

        # Check no existing active interview for this application
        # (partial unique index enforces this at DB level too, but validate early for better UX)
        existing = await self.db.execute(
            select(Interview).filter(
                Interview.tenant_id == tenant_id,
                Interview.application_id == application_id,
                Interview.status.in_([
                    InterviewStatus.SCHEDULED.value,
                    InterviewStatus.RESCHEDULED.value,
                ]),
                Interview.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise InterviewServiceError(
                "An active interview already exists for this application",
                "INTERVIEW_EXISTS",
            )

        # Check interviewer overlap if time is specified
        if scheduled_time:
            overlap = await self._check_interviewer_overlap(
                tenant_id, interviewer_id, scheduled_date, scheduled_time, duration_minutes
            )
            if overlap:
                raise InterviewServiceError(
                    f"Interviewer has an overlapping interview at {scheduled_time}",
                    "INTERVIEWER_CONFLICT",
                )

        interview = Interview(
            tenant_id=tenant_id,
            school_id=school_id,
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            venue=venue,
            status=InterviewStatus.SCHEDULED.value,
            scoring_criteria={},
        )
        self.db.add(interview)
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "interview_scheduled",
            interview_id=str(interview.id),
            application_id=str(application_id),
            date=str(scheduled_date),
        )
        return interview

    async def _check_interviewer_overlap(
        self,
        tenant_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        target_date: date,
        target_time: time,
        duration: int,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check if interviewer has an overlapping interview on the same date.

        Uses in-memory interval overlap check: start < other_end AND end > other_start.
        Only considers scheduled/rescheduled interviews (not cancelled/completed/no_show).
        """
        query = select(Interview).filter(
            Interview.tenant_id == tenant_id,
            Interview.interviewer_id == interviewer_id,
            Interview.scheduled_date == target_date,
            Interview.status.in_([
                InterviewStatus.SCHEDULED.value,
                InterviewStatus.RESCHEDULED.value,
            ]),
            Interview.scheduled_time.isnot(None),
            Interview.deleted_at.is_(None),
        )
        if exclude_id:
            query = query.filter(Interview.id != exclude_id)

        result = await self.db.execute(query)
        existing_interviews = result.scalars().all()

        target_start = datetime.combine(target_date, target_time)
        target_end = target_start + timedelta(minutes=duration)

        for existing in existing_interviews:
            ex_start = datetime.combine(existing.scheduled_date, existing.scheduled_time)
            ex_end = ex_start + timedelta(minutes=existing.duration_minutes)
            # Standard interval overlap: start < other_end AND end > other_start
            if target_start < ex_end and target_end > ex_start:
                return True
        return False

    async def get(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
    ) -> Interview:
        """Get interview by ID with defense-in-depth tenant check."""
        return await self._get_interview(tenant_id, interview_id)

    async def list_interviews(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        interviewer_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Interview], int]:
        """List interviews with optional filters and pagination."""
        query = select(Interview).filter(
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            Interview.tenant_id == tenant_id,
            Interview.school_id == school_id,
            Interview.deleted_at.is_(None),
        )

        if date_from:
            query = query.filter(Interview.scheduled_date >= date_from)
        if date_to:
            query = query.filter(Interview.scheduled_date <= date_to)
        if interviewer_id:
            query = query.filter(Interview.interviewer_id == interviewer_id)
        if status:
            query = query.filter(Interview.status == status)

        # Count before pagination
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply ordering and pagination
        query = query.order_by(
            Interview.scheduled_date.asc(),
            Interview.scheduled_time.asc(),
        )
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)

        return list(result.scalars().all()), total

    async def update(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
        **kwargs,
    ) -> Interview:
        """
        Update interview details (reschedule).

        Only scheduled or rescheduled interviews can be updated.
        If date/time changes, re-checks interviewer overlap and
        transitions status to 'rescheduled'.
        """
        interview = await self._get_interview(tenant_id, interview_id)

        if interview.status not in (
            InterviewStatus.SCHEDULED.value,
            InterviewStatus.RESCHEDULED.value,
        ):
            raise InterviewServiceError(
                "Can only update scheduled or rescheduled interviews",
                "NOT_SCHEDULED",
            )

        # Track whether date/time/interviewer changed for overlap re-check
        date_changed = False
        interviewer_changed = False

        # Apply updates with PROTECTED_FIELDS blocklist
        for key, value in kwargs.items():
            if key in self._PROTECTED_FIELDS:
                continue
            if value is not None and hasattr(interview, key):
                if key == "scheduled_date" and value != interview.scheduled_date:
                    date_changed = True
                if key == "scheduled_time" and value != interview.scheduled_time:
                    date_changed = True
                if key == "interviewer_id" and value != interview.interviewer_id:
                    interviewer_changed = True
                setattr(interview, key, value)

        # Re-check interviewer overlap if relevant fields changed
        if (date_changed or interviewer_changed) and interview.scheduled_time:
            overlap = await self._check_interviewer_overlap(
                tenant_id,
                interview.interviewer_id,
                interview.scheduled_date,
                interview.scheduled_time,
                interview.duration_minutes,
                exclude_id=interview.id,
            )
            if overlap:
                raise InterviewServiceError(
                    "Interviewer has an overlapping interview at the new time",
                    "INTERVIEWER_CONFLICT",
                )

        # Transition to rescheduled if date/time changed
        if date_changed:
            interview.status = InterviewStatus.RESCHEDULED.value

        await self.db.flush()
        await self.db.refresh(interview)
        return interview

    async def record_feedback(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
        *,
        status: str,
        feedback: str | None = None,
        score: Decimal | None = None,
        max_score: Decimal | None = None,
        scoring_criteria: dict | None = None,
    ) -> Interview:
        """
        Record interview outcome. Sets status to 'completed' or 'no_show'.

        If scoring_criteria is provided, auto-calculates total score and max_score
        from the per-criterion values. Otherwise uses the explicitly provided
        score/max_score.
        """
        interview = await self._get_interview(tenant_id, interview_id)

        # Only scheduled or rescheduled interviews can receive feedback
        if interview.status not in (
            InterviewStatus.SCHEDULED.value,
            InterviewStatus.RESCHEDULED.value,
        ):
            raise InterviewServiceError(
                "Can only record feedback for scheduled or rescheduled interviews",
                "NOT_SCHEDULED",
            )

        if status not in (InterviewStatus.COMPLETED.value, InterviewStatus.NO_SHOW.value):
            raise InterviewServiceError(
                f"Invalid feedback status: {status}. Must be 'completed' or 'no_show'",
                "INVALID_STATUS",
            )

        interview.status = status
        interview.feedback = feedback

        if scoring_criteria:
            interview.scoring_criteria = scoring_criteria
            # Auto-calculate total score from per-criterion values
            total_score = sum(
                c.get("score", 0) for c in scoring_criteria.values()
                if isinstance(c, dict)
            )
            total_max = sum(
                c.get("max", 0) for c in scoring_criteria.values()
                if isinstance(c, dict)
            )
            interview.score = Decimal(str(total_score))
            interview.max_score = Decimal(str(total_max))
        else:
            # Use explicitly provided scores (already validated by schema)
            interview.score = score
            interview.max_score = max_score

        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "interview_feedback_recorded",
            interview_id=str(interview_id),
            status=status,
            score=str(interview.score),
        )
        return interview

    async def cancel(
        self,
        tenant_id: uuid.UUID,
        interview_id: uuid.UUID,
    ) -> Interview:
        """Cancel an interview. Only scheduled/rescheduled interviews can be cancelled."""
        interview = await self._get_interview(tenant_id, interview_id)

        # Validate transition using the state machine
        allowed = INTERVIEW_VALID_TRANSITIONS.get(interview.status, [])
        if InterviewStatus.CANCELLED.value not in allowed:
            raise InterviewServiceError(
                f"Cannot cancel interview in '{interview.status}' status",
                "INVALID_TRANSITION",
            )

        interview.status = InterviewStatus.CANCELLED.value
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "interview_cancelled",
            interview_id=str(interview_id),
        )
        return interview

    async def get_by_application(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> Interview | None:
        """Get the active interview for an application (if any)."""
        result = await self.db.execute(
            select(Interview).filter(
                Interview.tenant_id == tenant_id,
                Interview.application_id == application_id,
                Interview.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # ---- Screening Checklist ----

    async def create_screening_item(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        item_name: str,
        item_category: str,
    ) -> ScreeningChecklist:
        """
        Add a screening checklist item to an application.

        Validates application exists and checks for duplicate item_name
        within the same application (unique constraint).
        """
        # Verify application exists in same tenant
        await self._get_application(tenant_id, application_id)

        # Check for duplicate (unique constraint will also catch this, but
        # we provide a friendlier error message)
        existing = await self.db.execute(
            select(ScreeningChecklist).filter(
                ScreeningChecklist.tenant_id == tenant_id,
                ScreeningChecklist.application_id == application_id,
                ScreeningChecklist.item_name == item_name,
                ScreeningChecklist.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise InterviewServiceError(
                f"Screening item '{item_name}' already exists for this application",
                "DUPLICATE_ITEM",
            )

        item = ScreeningChecklist(
            tenant_id=tenant_id,
            application_id=application_id,
            item_name=item_name,
            item_category=item_category,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def bulk_create_screening_items(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        *,
        items: list[dict],
    ) -> list[ScreeningChecklist]:
        """
        Bulk-add screening items (apply a template).

        Skips duplicates silently rather than failing the entire batch.
        Max 50 items per call (enforced by schema).
        """
        # Verify application exists in same tenant
        await self._get_application(tenant_id, application_id)

        # Fetch existing item names to skip duplicates
        existing_result = await self.db.execute(
            select(ScreeningChecklist.item_name).filter(
                ScreeningChecklist.tenant_id == tenant_id,
                ScreeningChecklist.application_id == application_id,
                ScreeningChecklist.deleted_at.is_(None),
            )
        )
        existing_names = {row[0] for row in existing_result.all()}

        created: list[ScreeningChecklist] = []
        for item_data in items:
            name = item_data["item_name"]
            if name in existing_names:
                # Skip duplicates silently
                continue
            item = ScreeningChecklist(
                tenant_id=tenant_id,
                application_id=application_id,
                item_name=name,
                item_category=item_data["item_category"],
            )
            self.db.add(item)
            created.append(item)
            # Track to prevent duplicates within the same batch
            existing_names.add(name)

        if created:
            await self.db.flush()
            for item in created:
                await self.db.refresh(item)

        return created

    async def complete_screening_item(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        notes: str | None = None,
    ) -> ScreeningChecklist:
        """Mark a screening item as completed."""
        result = await self.db.execute(
            select(ScreeningChecklist).filter(
                ScreeningChecklist.id == item_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                ScreeningChecklist.tenant_id == tenant_id,
                ScreeningChecklist.deleted_at.is_(None),
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise InterviewServiceError("Screening item not found", "NOT_FOUND")

        if item.is_completed:
            raise InterviewServiceError("Item already completed", "ALREADY_COMPLETED")

        item.is_completed = True
        item.completed_by = user_id
        item.completed_at = datetime.now(UTC)
        if notes:
            item.notes = notes

        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_screening_progress(
        self,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> dict:
        """
        Get screening completion progress for an application.

        Returns total_items, completed_items, progress_pct, and full item list.
        """
        # Verify application exists in same tenant
        await self._get_application(tenant_id, application_id)

        result = await self.db.execute(
            select(ScreeningChecklist).filter(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                ScreeningChecklist.tenant_id == tenant_id,
                ScreeningChecklist.application_id == application_id,
                ScreeningChecklist.deleted_at.is_(None),
            ).order_by(
                ScreeningChecklist.item_category,
                ScreeningChecklist.created_at,
            )
        )
        items = list(result.scalars().all())

        total = len(items)
        completed = sum(1 for i in items if i.is_completed)
        progress_pct = (completed / total * 100) if total > 0 else 0.0

        return {
            "application_id": application_id,
            "total_items": total,
            "completed_items": completed,
            "progress_pct": round(progress_pct, 1),
            "items": items,
        }

    # ---- Private helpers ----

    async def _get_interview(
        self, tenant_id: uuid.UUID, interview_id: uuid.UUID
    ) -> Interview:
        """Get interview with defense-in-depth tenant filtering."""
        result = await self.db.execute(
            select(Interview).filter(
                Interview.id == interview_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Interview.tenant_id == tenant_id,
                Interview.deleted_at.is_(None),
            )
        )
        interview = result.scalar_one_or_none()
        if not interview:
            raise InterviewServiceError("Interview not found", "NOT_FOUND")
        return interview

    async def _get_application(
        self, tenant_id: uuid.UUID, application_id: uuid.UUID
    ) -> Application:
        """Validate application exists in same tenant."""
        result = await self.db.execute(
            select(Application).filter(
                Application.id == application_id,
                Application.tenant_id == tenant_id,
                Application.deleted_at.is_(None),
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise InterviewServiceError("Application not found", "APP_NOT_FOUND")
        return app

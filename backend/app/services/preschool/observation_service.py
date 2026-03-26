"""
SIMS Plus - Preschool Observation Service

Business logic for progress observations and daily activity logs.
"""

from datetime import date, datetime
from typing import Sequence
from uuid import UUID

import structlog
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.preschool import (
    ProgressObservation,
    DailyActivityLog,
)
from app.models.student import Student, StudentGuardian
from app.schemas.preschool import (
    ProgressObservationCreate,
    ProgressObservationUpdate,
    DailyActivityLogCreate,
    DailyActivityLogUpdate,
)
from app.services.preschool._shared import PreschoolServiceError

logger = structlog.get_logger()


class PreschoolObservationService:
    """Service for progress observations and daily activity logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

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
    # Daily Report Sending
    # =========================

    async def send_daily_log_to_parents(
        self,
        tenant_id: UUID,
        log_id: UUID,
        sent_by: UUID,
    ) -> dict:
        """Send a single daily log summary to the student's guardians.

        1. Load daily log with student info
        2. Format SMS (brief <160 chars) and email (full detail)
        3. Use NotificationDispatcher for each guardian
        4. Respects parent notification preferences

        Returns: {sent_count: int, failed_count: int}
        """
        # Lazy import to avoid circular dependency
        from app.services.notification_dispatcher import NotificationDispatcher

        # Load daily log
        log = await self.get_daily_log(tenant_id, log_id)

        # Load student name
        student_result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.id == log.student_id,
                    Student.tenant_id == tenant_id,
                )
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise PreschoolServiceError("Student not found for log", "not_found")

        child_name = f"{student.first_name}"

        # Format human-readable summary for notification body
        body_parts = [f"Daily report for {child_name} ({log.log_date.strftime('%d/%m/%Y')}):"]
        if log.arrival_mood:
            body_parts.append(f"Mood: {log.arrival_mood}")
        if log.meals:
            meal_summary = ", ".join(
                f"{m.get('type', 'meal')}: {m.get('amount', 'ate')}"
                if isinstance(m, dict) else str(m)
                for m in log.meals[:3]
            )
            body_parts.append(f"Meals: {meal_summary}")
        if log.nap_quality:
            body_parts.append(f"Nap: {log.nap_quality}")
        if log.highlights:
            body_parts.append(f"Highlights: {log.highlights[:80]}")

        title = f"Daily Report: {child_name}"
        body = "\n".join(body_parts)

        # Dispatch to all parents of this student
        dispatcher = NotificationDispatcher(self.db)
        sent_count = 0
        failed_count = 0

        try:
            await dispatcher.dispatch_to_parents_of_student(
                student_id=log.student_id,
                tenant_id=tenant_id,
                title=title,
                body=body,
                category="academic",
                priority="normal",
            )
            sent_count = 1
        except Exception:
            logger.exception(
                "Failed to send daily log notification",
                log_id=str(log_id),
                student_id=str(log.student_id),
            )
            failed_count = 1

        return {"sent_count": sent_count, "failed_count": failed_count}

    async def bulk_send_daily_logs(
        self,
        tenant_id: UUID,
        class_id: UUID,
        log_date: date,
        sent_by: UUID,
    ) -> dict:
        """Send daily logs for all students in a class for a given date.

        Rate limit: Max 50 students per call. For larger classes,
        return error suggesting Celery task (future work).
        """
        MAX_BULK_STUDENTS = 50

        # Get all daily logs for this class and date
        logs = await self.list_daily_logs(
            tenant_id,
            log_date=log_date,
            class_id=class_id,
            limit=MAX_BULK_STUDENTS + 1,  # Fetch one extra to detect overflow
        )

        if len(logs) > MAX_BULK_STUDENTS:
            raise PreschoolServiceError(
                f"Too many students ({len(logs)}). Maximum {MAX_BULK_STUDENTS} per bulk send. "
                "Consider using a background task for larger classes.",
                "bulk_limit_exceeded",
            )

        total_students = len(logs)
        sent_count = 0
        failed_count = 0

        for log in logs:
            try:
                result = await self.send_daily_log_to_parents(
                    tenant_id, log.id, sent_by
                )
                sent_count += result["sent_count"]
                failed_count += result["failed_count"]
            except PreschoolServiceError:
                # Log not found or student not found — skip
                failed_count += 1
            except Exception:
                logger.exception(
                    "Failed to send daily log in bulk",
                    log_id=str(log.id),
                )
                failed_count += 1

        return {
            "total_students": total_students,
            "sent_count": sent_count,
            "no_log_count": 0,  # All entries are logs; students without logs aren't in the list
            "failed_count": failed_count,
        }

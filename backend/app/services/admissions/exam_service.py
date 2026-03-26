"""
SIMS Plus - Entrance Exam Service

CRUD for entrance exam sessions, applicant registration, score entry,
and attendance marking.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    AdmissionApplicationStatus,
    AdmissionPeriod,
    Application,
    ApplicationStatusHistory,
    EntranceExam,
    EntranceExamRegistration,
    EntranceExamResult,
    EntranceExamStatus,
    VALID_TRANSITIONS,
)

logger = structlog.get_logger(__name__)


class EntranceExamServiceError(Exception):
    def __init__(self, message: str, code: str = "EXAM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EntranceExamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_exam(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        admission_period_id: uuid.UUID,
        name: str,
        exam_date,
        start_time=None,
        end_time=None,
        venue: str,
        capacity: int,
        instructions: str | None = None,
    ) -> EntranceExam:
        """Create entrance exam session. Validates period exists and is not archived."""
        # Verify period exists and belongs to tenant
        period_result = await self.db.execute(
            select(AdmissionPeriod).where(
                AdmissionPeriod.id == admission_period_id,
                AdmissionPeriod.tenant_id == tenant_id,
                AdmissionPeriod.deleted_at.is_(None),
            )
        )
        period = period_result.scalar_one_or_none()
        if not period:
            raise EntranceExamServiceError(
                "Admission period not found", code="PERIOD_NOT_FOUND"
            )

        if period.status == "archived":
            raise EntranceExamServiceError(
                "Cannot create exam for archived period",
                code="PERIOD_ARCHIVED",
            )

        if capacity < 1:
            raise EntranceExamServiceError(
                "Exam capacity must be at least 1", code="INVALID_CAPACITY"
            )

        exam = EntranceExam(
            tenant_id=tenant_id,
            school_id=school_id,
            admission_period_id=admission_period_id,
            name=name,
            exam_date=exam_date,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            capacity=capacity,
            status=EntranceExamStatus.SCHEDULED.value,
            instructions=instructions,
        )
        self.db.add(exam)
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def get_exam(
        self,
        tenant_id: uuid.UUID,
        exam_id: uuid.UUID,
    ) -> EntranceExam:
        """Get a single exam by ID."""
        return await self._get_exam(tenant_id, exam_id)

    async def list_exams(
        self,
        tenant_id: uuid.UUID,
        *,
        admission_period_id: uuid.UUID | None = None,
        school_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EntranceExam], int]:
        """List exams with optional filters and pagination."""
        query = select(EntranceExam).where(
            EntranceExam.tenant_id == tenant_id,
            EntranceExam.deleted_at.is_(None),
        )

        if admission_period_id:
            query = query.where(
                EntranceExam.admission_period_id == admission_period_id
            )
        if school_id:
            query = query.where(EntranceExam.school_id == school_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(EntranceExam.exam_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update_status(
        self,
        tenant_id: uuid.UUID,
        exam_id: uuid.UUID,
        new_status: str,
    ) -> EntranceExam:
        """
        Transition exam status.

        Valid transitions:
          scheduled -> in_progress
          scheduled -> cancelled
          in_progress -> completed
          in_progress -> cancelled
        """
        valid_transitions: dict[str, list[str]] = {
            "scheduled": ["in_progress", "cancelled"],
            "in_progress": ["completed", "cancelled"],
        }

        exam = await self._get_exam(tenant_id, exam_id)
        allowed = valid_transitions.get(exam.status, [])

        if new_status not in allowed:
            raise EntranceExamServiceError(
                f"Cannot transition exam from {exam.status} to {new_status}",
                code="INVALID_TRANSITION",
            )

        exam.status = new_status
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def register_applicants(
        self,
        tenant_id: uuid.UUID,
        exam_id: uuid.UUID,
        application_ids: list[uuid.UUID],
    ) -> dict:
        """
        Register applicants for exam.

        Checks:
        - Exam capacity not exceeded
        - Applications are in SHORTLISTED status
        - Not already registered for this exam

        Transitions application status to EXAM_SCHEDULED.
        Auto-assigns seat numbers.

        Returns: { registered_count, already_registered_count, errors }
        """
        exam = await self._get_exam(tenant_id, exam_id)

        if exam.status != EntranceExamStatus.SCHEDULED.value:
            raise EntranceExamServiceError(
                "Can only register applicants for scheduled exams",
                code="EXAM_NOT_SCHEDULED",
            )

        # Count current registrations
        current_count_result = await self.db.execute(
            select(func.count(EntranceExamRegistration.id)).where(
                EntranceExamRegistration.entrance_exam_id == exam_id,
                EntranceExamRegistration.tenant_id == tenant_id,
                EntranceExamRegistration.deleted_at.is_(None),
            )
        )
        current_count = current_count_result.scalar() or 0

        registered_count = 0
        already_registered_count = 0
        errors: list[dict] = []

        for app_id in application_ids:
            # Check capacity
            if current_count + registered_count >= exam.capacity:
                errors.append({
                    "application_id": str(app_id),
                    "error": "Exam capacity reached",
                })
                continue

            # Check if already registered for this exam
            existing_result = await self.db.execute(
                select(EntranceExamRegistration).where(
                    EntranceExamRegistration.entrance_exam_id == exam_id,
                    EntranceExamRegistration.application_id == app_id,
                    EntranceExamRegistration.tenant_id == tenant_id,
                    EntranceExamRegistration.deleted_at.is_(None),
                )
            )
            if existing_result.scalar_one_or_none():
                already_registered_count += 1
                continue

            # Verify application is in SHORTLISTED status
            app_result = await self.db.execute(
                select(Application).where(
                    Application.id == app_id,
                    Application.tenant_id == tenant_id,
                    Application.deleted_at.is_(None),
                )
            )
            app = app_result.scalar_one_or_none()
            if not app:
                errors.append({
                    "application_id": str(app_id),
                    "error": "Application not found",
                })
                continue

            if app.status != AdmissionApplicationStatus.SHORTLISTED.value:
                errors.append({
                    "application_id": str(app_id),
                    "error": f"Application must be SHORTLISTED (current: {app.status})",
                })
                continue

            # Create registration with auto-assigned seat number
            seat_number = str(current_count + registered_count + 1).zfill(4)
            registration = EntranceExamRegistration(
                tenant_id=tenant_id,
                entrance_exam_id=exam_id,
                application_id=app_id,
                seat_number=seat_number,
            )
            self.db.add(registration)

            # Transition application to EXAM_SCHEDULED
            app.status = AdmissionApplicationStatus.EXAM_SCHEDULED.value
            history = ApplicationStatusHistory(
                tenant_id=tenant_id,
                application_id=app_id,
                from_status=AdmissionApplicationStatus.SHORTLISTED.value,
                to_status=AdmissionApplicationStatus.EXAM_SCHEDULED.value,
                changed_by=None,
                reason=f"Registered for entrance exam: {exam.name}",
            )
            self.db.add(history)

            registered_count += 1

        await self.db.flush()

        return {
            "registered_count": registered_count,
            "already_registered_count": already_registered_count,
            "errors": errors,
        }

    async def record_results(
        self,
        tenant_id: uuid.UUID,
        exam_id: uuid.UUID,
        results: list[dict],
        scored_by: uuid.UUID,
    ) -> int:
        """
        Enter exam results. Creates or updates EntranceExamResult records.

        Each result dict: { application_id, score, max_score, grade, passed, remarks }

        Transitions application status to EXAM_COMPLETED for each applicant
        that receives a result.

        Returns: count of results recorded.
        """
        exam = await self._get_exam(tenant_id, exam_id)

        if exam.status not in (
            EntranceExamStatus.IN_PROGRESS.value,
            EntranceExamStatus.COMPLETED.value,
        ):
            raise EntranceExamServiceError(
                "Can only record results for in-progress or completed exams",
                code="EXAM_NOT_ACTIVE",
            )

        count = 0
        for r in results:
            app_id = uuid.UUID(str(r["application_id"]))

            # Check if result already exists (upsert pattern)
            existing_result = await self.db.execute(
                select(EntranceExamResult).where(
                    EntranceExamResult.entrance_exam_id == exam_id,
                    EntranceExamResult.application_id == app_id,
                    EntranceExamResult.tenant_id == tenant_id,
                    EntranceExamResult.deleted_at.is_(None),
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Update existing result
                existing.score = r["score"]
                existing.max_score = r["max_score"]
                existing.grade = r.get("grade")
                existing.passed = r.get("passed", False)
                existing.remarks = r.get("remarks")
                existing.scored_by = scored_by
            else:
                # Create new result
                exam_result = EntranceExamResult(
                    tenant_id=tenant_id,
                    entrance_exam_id=exam_id,
                    application_id=app_id,
                    score=r["score"],
                    max_score=r["max_score"],
                    grade=r.get("grade"),
                    passed=r.get("passed", False),
                    remarks=r.get("remarks"),
                    scored_by=scored_by,
                )
                self.db.add(exam_result)

            # Transition application to EXAM_COMPLETED if currently EXAM_SCHEDULED
            app_result = await self.db.execute(
                select(Application).where(
                    Application.id == app_id,
                    Application.tenant_id == tenant_id,
                )
            )
            app = app_result.scalar_one_or_none()
            if app and app.status == AdmissionApplicationStatus.EXAM_SCHEDULED.value:
                app.status = AdmissionApplicationStatus.EXAM_COMPLETED.value
                history = ApplicationStatusHistory(
                    tenant_id=tenant_id,
                    application_id=app_id,
                    from_status=AdmissionApplicationStatus.EXAM_SCHEDULED.value,
                    to_status=AdmissionApplicationStatus.EXAM_COMPLETED.value,
                    changed_by=scored_by,
                    reason="Exam results recorded",
                )
                self.db.add(history)

            count += 1

        await self.db.flush()
        return count

    async def mark_attendance(
        self,
        tenant_id: uuid.UUID,
        exam_id: uuid.UUID,
        attendees: list[uuid.UUID],
    ) -> int:
        """
        Mark which registered applicants attended the exam.

        Args:
            attendees: List of application_ids that attended.

        Returns: count of registrations updated.
        """
        exam = await self._get_exam(tenant_id, exam_id)
        count = 0

        for app_id in attendees:
            result = await self.db.execute(
                select(EntranceExamRegistration).where(
                    EntranceExamRegistration.entrance_exam_id == exam_id,
                    EntranceExamRegistration.application_id == app_id,
                    EntranceExamRegistration.tenant_id == tenant_id,
                    EntranceExamRegistration.deleted_at.is_(None),
                )
            )
            registration = result.scalar_one_or_none()
            if registration and not registration.attended:
                registration.attended = True
                count += 1

        await self.db.flush()
        return count

    # ---- Private helpers ----

    async def _get_exam(
        self, tenant_id: uuid.UUID, exam_id: uuid.UUID
    ) -> EntranceExam:
        result = await self.db.execute(
            select(EntranceExam).where(
                EntranceExam.id == exam_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                EntranceExam.tenant_id == tenant_id,
                EntranceExam.deleted_at.is_(None),
            )
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise EntranceExamServiceError("Exam not found", code="NOT_FOUND")
        return exam

"""
SIMS Plus - Predicted Grade Service

Business logic for managing teacher-predicted and target grades,
used by Cambridge and IB schools for university application support.
"""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Subject, Term
from app.models.curriculum import PredictedGrade
from app.models.student import Student
from app.services.curriculum._shared import CurriculumServiceError, check_multi_curriculum_access

logger = structlog.get_logger()

# Maximum number of predictions allowed in a single bulk create
_MAX_BULK_PREDICTIONS = 200

# Fields that cannot be changed after creation
_IMMUTABLE_FIELDS = {
    "id", "tenant_id", "school_id", "student_id", "subject_id",
    "academic_year_id", "created_at", "deleted_at",
}


class PredictedGradeService:
    """Service for predicted and target grade management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Tenant FK Validation
    # =========================

    async def _validate_student(self, student_id: UUID, tenant_id: UUID) -> Student:
        """Validate that a student exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Student).where(
                Student.id == student_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Student.tenant_id == tenant_id,
                Student.deleted_at.is_(None),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise CurriculumServiceError("Student not found", "not_found")
        return student

    async def _validate_subject(self, subject_id: UUID, tenant_id: UUID) -> Subject:
        """Validate that a subject exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.tenant_id == tenant_id,
                Subject.deleted_at.is_(None),
            )
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise CurriculumServiceError("Subject not found", "not_found")
        return subject

    async def _validate_academic_year(
        self, academic_year_id: UUID, tenant_id: UUID
    ) -> AcademicYear:
        """Validate that an academic year exists and belongs to the tenant."""
        result = await self.db.execute(
            select(AcademicYear).where(
                AcademicYear.id == academic_year_id,
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        year = result.scalar_one_or_none()
        if not year:
            raise CurriculumServiceError("Academic year not found", "not_found")
        return year

    async def _validate_term(self, term_id: UUID, tenant_id: UUID) -> Term:
        """Validate that a term exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Term).where(
                Term.id == term_id,
                Term.tenant_id == tenant_id,
            )
        )
        term = result.scalar_one_or_none()
        if not term:
            raise CurriculumServiceError("Term not found", "not_found")
        return term

    # =========================
    # CRUD
    # =========================

    async def create_prediction(
        self,
        tenant_id: UUID,
        school_id: UUID,
        user_id: UUID,
        data,
    ) -> PredictedGrade:
        """
        Create a new predicted grade record.

        Sets predicted_by to the current user and predicted_at to now.
        """
        await check_multi_curriculum_access(self.db, tenant_id)
        await self._validate_student(data.student_id, tenant_id)
        await self._validate_subject(data.subject_id, tenant_id)
        await self._validate_academic_year(data.academic_year_id, tenant_id)
        if data.term_id:
            await self._validate_term(data.term_id, tenant_id)

        # Note: predicted_by (user_id) is sourced from JWT, not request body,
        # so it is guaranteed to belong to the current tenant. If this is ever
        # refactored to accept a user_id from the request body, add explicit
        # tenant validation: await self._validate_user(user_id, tenant_id)
        prediction = PredictedGrade(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=data.student_id,
            subject_id=data.subject_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            predicted_grade=data.predicted_grade,
            target_grade=data.target_grade,
            predicted_score=data.predicted_score,
            predicted_by=user_id,
            predicted_at=datetime.now(timezone.utc),
            notes=data.notes,
        )
        self.db.add(prediction)
        await self.db.flush()
        await self.db.refresh(prediction)

        logger.info(
            "predicted_grade_created",
            prediction_id=str(prediction.id),
            student_id=str(data.student_id),
            subject_id=str(data.subject_id),
        )
        return prediction

    async def get_predictions(
        self,
        tenant_id: UUID,
        student_id: UUID | None = None,
        subject_id: UUID | None = None,
        academic_year_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PredictedGrade], int]:
        """List predicted grades with optional filters."""
        filters = [
            PredictedGrade.tenant_id == tenant_id,
            PredictedGrade.deleted_at.is_(None),
        ]
        if student_id:
            filters.append(PredictedGrade.student_id == student_id)
        if subject_id:
            filters.append(PredictedGrade.subject_id == subject_id)
        if academic_year_id:
            filters.append(PredictedGrade.academic_year_id == academic_year_id)

        combined = and_(*filters)

        # Count
        count_result = await self.db.execute(
            select(func.count(PredictedGrade.id)).where(combined)
        )
        total = count_result.scalar_one()

        # Paginated query
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(PredictedGrade)
            .where(combined)
            .order_by(PredictedGrade.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        predictions = list(result.scalars().all())

        return predictions, total

    async def get_prediction(
        self,
        tenant_id: UUID,
        prediction_id: UUID,
    ) -> PredictedGrade:
        """Get a single predicted grade by ID."""
        result = await self.db.execute(
            select(PredictedGrade).where(
                PredictedGrade.id == prediction_id,
                PredictedGrade.tenant_id == tenant_id,
                PredictedGrade.deleted_at.is_(None),
            )
        )
        prediction = result.scalar_one_or_none()
        if not prediction:
            raise CurriculumServiceError(
                "Predicted grade not found", "not_found"
            )
        return prediction

    async def update_prediction(
        self,
        tenant_id: UUID,
        prediction_id: UUID,
        user_id: UUID,
        data,
    ) -> PredictedGrade:
        """
        Update a predicted grade.

        Immutable fields (student_id, subject_id, academic_year_id) cannot
        be changed. Updates predicted_by and predicted_at on each modification.
        """
        prediction = await self.get_prediction(tenant_id, prediction_id)

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if field in _IMMUTABLE_FIELDS:
                continue
            if hasattr(prediction, field):
                setattr(prediction, field, value)

        # Always update the predictor and timestamp on modification
        prediction.predicted_by = user_id
        prediction.predicted_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(prediction)

        logger.info(
            "predicted_grade_updated",
            prediction_id=str(prediction_id),
        )
        return prediction

    async def delete_prediction(
        self,
        tenant_id: UUID,
        prediction_id: UUID,
    ) -> None:
        """Soft delete a predicted grade."""
        prediction = await self.get_prediction(tenant_id, prediction_id)
        prediction.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "predicted_grade_deleted",
            prediction_id=str(prediction_id),
        )

    async def bulk_create_predictions(
        self,
        tenant_id: UUID,
        school_id: UUID,
        user_id: UUID,
        data,
    ) -> list[PredictedGrade]:
        """
        Bulk create predicted grades (up to 200 at a time).

        Validates all referenced students and subjects belong to the tenant
        before creating any records.
        """
        await check_multi_curriculum_access(self.db, tenant_id)
        predictions_data = data.predictions
        if len(predictions_data) > _MAX_BULK_PREDICTIONS:
            raise CurriculumServiceError(
                f"Maximum {_MAX_BULK_PREDICTIONS} predictions per bulk request",
                "validation_error",
            )

        # Collect unique IDs for batch validation
        student_ids = {p.student_id for p in predictions_data}
        subject_ids = {p.subject_id for p in predictions_data}
        year_ids = {p.academic_year_id for p in predictions_data}
        term_ids = {p.term_id for p in predictions_data if p.term_id}

        # Batch validate students
        student_result = await self.db.execute(
            select(Student.id).where(
                Student.tenant_id == tenant_id,
                Student.id.in_(student_ids),
                Student.deleted_at.is_(None),
            )
        )
        found_students = set(student_result.scalars().all())
        missing_students = student_ids - found_students
        if missing_students:
            raise CurriculumServiceError(
                f"Students not found: {[str(s) for s in missing_students]}",
                "not_found",
            )

        # Batch validate subjects
        subject_result = await self.db.execute(
            select(Subject.id).where(
                Subject.tenant_id == tenant_id,
                Subject.id.in_(subject_ids),
                Subject.deleted_at.is_(None),
            )
        )
        found_subjects = set(subject_result.scalars().all())
        missing_subjects = subject_ids - found_subjects
        if missing_subjects:
            raise CurriculumServiceError(
                f"Subjects not found: {[str(s) for s in missing_subjects]}",
                "not_found",
            )

        # Batch validate academic years
        year_result = await self.db.execute(
            select(AcademicYear.id).where(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id.in_(year_ids),
                AcademicYear.deleted_at.is_(None),
            )
        )
        found_years = set(year_result.scalars().all())
        missing_years = year_ids - found_years
        if missing_years:
            raise CurriculumServiceError(
                f"Academic years not found: {[str(y) for y in missing_years]}",
                "not_found",
            )

        # Batch validate terms
        if term_ids:
            term_result = await self.db.execute(
                select(Term.id).where(
                    Term.tenant_id == tenant_id,
                    Term.id.in_(term_ids),
                )
            )
            found_terms = set(term_result.scalars().all())
            missing_terms = term_ids - found_terms
            if missing_terms:
                raise CurriculumServiceError(
                    f"Terms not found: {[str(t) for t in missing_terms]}",
                    "not_found",
                )

        # Create all predictions
        now = datetime.now(timezone.utc)
        created = []
        for p in predictions_data:
            prediction = PredictedGrade(
                tenant_id=tenant_id,
                school_id=school_id,
                student_id=p.student_id,
                subject_id=p.subject_id,
                academic_year_id=p.academic_year_id,
                term_id=p.term_id,
                predicted_grade=p.predicted_grade,
                target_grade=p.target_grade,
                predicted_score=p.predicted_score,
                predicted_by=user_id,
                predicted_at=now,
                notes=p.notes,
            )
            self.db.add(prediction)
            created.append(prediction)

        await self.db.flush()

        # Refresh all to get generated IDs and timestamps
        for prediction in created:
            await self.db.refresh(prediction)

        logger.info(
            "predicted_grades_bulk_created",
            count=len(created),
            user_id=str(user_id),
        )
        return created

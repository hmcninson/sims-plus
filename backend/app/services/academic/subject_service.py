"""
SIMS Plus - Subject, Grading & Settings Service

Subject CRUD, class-subject assignments, grading scales, grades,
assessment weights, and academic settings.
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    Subject,
    ClassSubject,
    GradingScale,
    GradingScaleType,
    Grade,
    AssessmentWeight,
    AcademicSettings,
)

from app.services.academic._shared import AcademicServiceError


class SubjectMixin:
    """Mixin providing subject, grading, assessment, and settings methods for AcademicService."""

    # Type hints for self.db -- set by AcademicService.__init__
    db: AsyncSession

    # =========================
    # Subject Methods
    # =========================

    async def create_subject(
        self,
        tenant_id: UUID,
        name: str,
        code: str,
        category: str = "core",
        description: Optional[str] = None,
    ) -> Subject:
        """Create a new subject."""
        code = code.upper()

        # Check for duplicate code
        existing = await self.db.execute(
            select(Subject).where(
                and_(
                    Subject.tenant_id == tenant_id,
                    Subject.code == code,
                    Subject.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Subject with code '{code}' already exists",
                code="duplicate_subject",
            )

        subject = Subject(
            tenant_id=tenant_id,
            name=name,
            code=code,
            description=description,
            category=category,
            is_active=True,
        )
        self.db.add(subject)
        await self.db.flush()
        await self.db.refresh(subject)
        return subject

    async def get_subject(self, tenant_id: UUID, subject_id: UUID) -> Optional[Subject]:
        """Get subject by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(Subject).where(
                and_(
                    Subject.tenant_id == tenant_id,
                    Subject.id == subject_id,
                    Subject.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_subjects(
        self,
        tenant_id: UUID,
        category: Optional[str] = None,
        class_level: Optional[str] = None,
        active_only: bool = True,
    ) -> Sequence[Subject]:
        """List subjects, optionally filtered by class level.

        Args:
            tenant_id: The tenant ID
            category: Filter by subject category
            class_level: Filter by class level (preschool, primary, jhs, shs).
                        Returns subjects where applicable_levels contains this level,
                        or where applicable_levels is null (applies to all levels).
            active_only: Only return active subjects
        """
        conditions = [
            Subject.tenant_id == tenant_id,
            Subject.deleted_at.is_(None),
        ]
        if category:
            conditions.append(Subject.category == category)
        if active_only:
            conditions.append(Subject.is_active == True)

        # Filter by class level if specified
        # Subject applies if: applicable_levels is NULL (all levels) OR contains the specified level
        if class_level:
            from sqlalchemy import or_, text
            conditions.append(
                or_(
                    Subject.applicable_levels.is_(None),
                    Subject.applicable_levels.contains([class_level]),
                )
            )

        result = await self.db.execute(
            select(Subject).where(and_(*conditions)).order_by(Subject.name)
        )
        return result.scalars().all()

    async def update_subject(self, tenant_id: UUID, subject_id: UUID, **kwargs) -> Optional[Subject]:
        """Update a subject."""
        # Defense-in-depth: tenant_id verified in get_subject
        subject = await self.get_subject(tenant_id, subject_id)
        if not subject:
            return None

        if "code" in kwargs and kwargs["code"]:
            kwargs["code"] = kwargs["code"].upper()

        for key, value in kwargs.items():
            if value is not None and hasattr(subject, key):
                setattr(subject, key, value)

        subject.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(subject)
        return subject

    async def delete_subject(self, tenant_id: UUID, subject_id: UUID) -> bool:
        """Soft delete a subject."""
        # Defense-in-depth: tenant_id verified in get_subject
        subject = await self.get_subject(tenant_id, subject_id)
        if not subject:
            return False

        subject.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # =========================
    # Class Subject Methods
    # =========================

    async def assign_subject_to_class(
        self,
        tenant_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        periods_per_week: Optional[int] = None,
        is_compulsory: bool = True,
    ) -> ClassSubject:
        """Assign a subject to a class."""
        # Verify class and subject exist (defense-in-depth: tenant_id verified)
        class_ = await self.get_class(tenant_id, class_id)
        subject = await self.get_subject(tenant_id, subject_id)
        if not class_:
            raise AcademicServiceError("Class not found", code="class_not_found")
        if not subject:
            raise AcademicServiceError("Subject not found", code="subject_not_found")

        # Prevent subject assignment to preschool classes
        # Preschool uses Learning Areas and Developmental Skills instead
        preschool_levels = {"creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"}
        if class_.level and class_.level.value in preschool_levels:
            raise AcademicServiceError(
                "Subjects cannot be assigned to preschool classes. "
                "Preschool classes use Learning Areas and Developmental Skills instead.",
                code="preschool_no_subjects",
            )

        # Check for existing assignment
        existing = await self.db.execute(
            select(ClassSubject).where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                "Subject already assigned to this class",
                code="duplicate_assignment",
            )

        assignment = ClassSubject(
            tenant_id=tenant_id,
            class_id=class_id,
            subject_id=subject_id,
            periods_per_week=periods_per_week,
            is_compulsory=is_compulsory,
        )
        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def remove_subject_from_class(
        self, tenant_id: UUID, class_id: UUID, subject_id: UUID
    ) -> bool:
        """Remove a subject assignment from a class."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(ClassSubject).where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.flush()
        return True

    async def get_class_subjects(
        self, tenant_id: UUID, class_id: UUID
    ) -> Sequence[ClassSubject]:
        """Get all subjects assigned to a class."""
        result = await self.db.execute(
            select(ClassSubject)
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                )
            )
            .options(selectinload(ClassSubject.subject))
        )
        return result.scalars().all()

    async def get_subjects_for_classes(
        self, tenant_id: UUID, class_ids: list[UUID]
    ) -> Sequence[ClassSubject]:
        """Get all subjects assigned to multiple classes in one query."""
        if not class_ids:
            return []
        result = await self.db.execute(
            select(ClassSubject)
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id.in_(class_ids),
                )
            )
            .options(selectinload(ClassSubject.subject))
            .order_by(ClassSubject.class_id)
        )
        return result.scalars().all()

    # =========================
    # Grading Scale Methods
    # =========================

    async def create_grading_scale(
        self,
        tenant_id: UUID,
        name: str,
        scale_type: str = "waec",
        description: Optional[str] = None,
        is_default: bool = False,
        grades: Optional[list] = None,
    ) -> GradingScale:
        """Create a new grading scale with grades."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(GradingScale).where(
                and_(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.name == name,
                    GradingScale.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Grading scale '{name}' already exists",
                code="duplicate_grading_scale",
            )

        # If setting as default, unset other defaults
        if is_default:
            await self._unset_default_grading_scale(tenant_id)

        grading_scale = GradingScale(
            tenant_id=tenant_id,
            name=name,
            description=description,
            scale_type=GradingScaleType(scale_type),
            is_default=is_default,
            is_active=True,
        )
        self.db.add(grading_scale)
        await self.db.flush()  # Get the ID

        # Add grades if provided
        if grades:
            for grade_data in grades:
                grade = Grade(
                    tenant_id=tenant_id,
                    grading_scale_id=grading_scale.id,
                    grade=grade_data["grade"],
                    min_score=Decimal(str(grade_data["min_score"])),
                    max_score=Decimal(str(grade_data["max_score"])),
                    grade_point=Decimal(str(grade_data["grade_point"])) if grade_data.get("grade_point") else None,
                    remark=grade_data.get("remark"),
                )
                self.db.add(grade)

        await self.db.flush()
        await self.db.refresh(grading_scale)
        return grading_scale

    async def get_grading_scale(
        self, tenant_id: UUID, scale_id: UUID, include_grades: bool = False
    ) -> Optional[GradingScale]:
        """Get grading scale by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(GradingScale).where(
            and_(
                GradingScale.tenant_id == tenant_id,
                GradingScale.id == scale_id,
                GradingScale.deleted_at.is_(None),
            )
        )
        if include_grades:
            query = query.options(selectinload(GradingScale.grades))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_grading_scales(
        self,
        tenant_id: UUID,
        include_grades: bool = False,
        active_only: bool = True,
    ) -> Sequence[GradingScale]:
        """List grading scales."""
        conditions = [
            GradingScale.tenant_id == tenant_id,
            GradingScale.deleted_at.is_(None),
        ]
        if active_only:
            conditions.append(GradingScale.is_active == True)

        query = select(GradingScale).where(and_(*conditions)).order_by(GradingScale.name)

        if include_grades:
            query = query.options(selectinload(GradingScale.grades))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_grading_scale(
        self, scale_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[GradingScale]:
        """Update a grading scale."""
        # Defense-in-depth: tenant_id verified in get_grading_scale
        scale = await self.get_grading_scale(tenant_id, scale_id)
        if not scale:
            return None

        # Handle is_default specially
        if kwargs.get("is_default"):
            await self._unset_default_grading_scale(tenant_id)

        # Handle scale_type change
        if "scale_type" in kwargs:
            kwargs["scale_type"] = GradingScaleType(kwargs["scale_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(scale, key):
                setattr(scale, key, value)

        scale.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(scale)
        return scale

    async def delete_grading_scale(self, tenant_id: UUID, scale_id: UUID) -> bool:
        """Soft delete a grading scale."""
        # Defense-in-depth: tenant_id verified in get_grading_scale
        scale = await self.get_grading_scale(tenant_id, scale_id)
        if not scale:
            return False

        scale.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def _unset_default_grading_scale(self, tenant_id: UUID) -> None:
        """Unset default flag for all grading scales in tenant."""
        result = await self.db.execute(
            select(GradingScale).where(
                and_(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.is_default == True,
                    GradingScale.deleted_at.is_(None),
                )
            )
        )
        for scale in result.scalars().all():
            scale.is_default = False

    # =========================
    # Grade Methods
    # =========================

    async def add_grade(
        self,
        tenant_id: UUID,
        grading_scale_id: UUID,
        grade: str,
        min_score: Decimal,
        max_score: Decimal,
        grade_point: Optional[Decimal] = None,
        remark: Optional[str] = None,
    ) -> Grade:
        """Add a grade to a grading scale."""
        # Defense-in-depth: tenant_id verified in get_grading_scale
        scale = await self.get_grading_scale(tenant_id, grading_scale_id)
        if not scale:
            raise AcademicServiceError(
                "Grading scale not found",
                code="grading_scale_not_found",
            )

        grade_obj = Grade(
            tenant_id=tenant_id,
            grading_scale_id=grading_scale_id,
            grade=grade,
            min_score=min_score,
            max_score=max_score,
            grade_point=grade_point,
            remark=remark,
        )
        self.db.add(grade_obj)
        await self.db.flush()
        await self.db.refresh(grade_obj)
        return grade_obj

    async def update_grade(self, tenant_id: UUID, grade_id: UUID, **kwargs) -> Optional[Grade]:
        """Update a grade."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(Grade).where(
                and_(
                    Grade.tenant_id == tenant_id,
                    Grade.id == grade_id,
                )
            )
        )
        grade = result.scalar_one_or_none()
        if not grade:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(grade, key):
                setattr(grade, key, value)

        grade.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(grade)
        return grade

    async def delete_grade(self, tenant_id: UUID, grade_id: UUID) -> bool:
        """Delete a grade."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(Grade).where(
                and_(
                    Grade.tenant_id == tenant_id,
                    Grade.id == grade_id,
                )
            )
        )
        grade = result.scalar_one_or_none()
        if not grade:
            return False

        await self.db.delete(grade)
        await self.db.flush()
        return True

    # =========================
    # Assessment Weight Methods
    # =========================

    async def set_assessment_weights(
        self,
        tenant_id: UUID,
        class_work_weight: Decimal,
        homework_weight: Decimal,
        midterm_weight: Decimal,
        end_term_weight: Decimal,
        academic_year_id: Optional[UUID] = None,
        ca_total_weight: Optional[Decimal] = None,
        exam_total_weight: Optional[Decimal] = None,
    ) -> AssessmentWeight:
        """Set assessment weights for a tenant (optionally for specific academic year)."""
        # Check if weights exist
        conditions = [AssessmentWeight.tenant_id == tenant_id]
        if academic_year_id:
            conditions.append(AssessmentWeight.academic_year_id == academic_year_id)
        else:
            conditions.append(AssessmentWeight.academic_year_id.is_(None))

        result = await self.db.execute(
            select(AssessmentWeight).where(and_(*conditions))
        )
        weights = result.scalar_one_or_none()

        if weights:
            # Update existing
            weights.class_work_weight = class_work_weight
            weights.homework_weight = homework_weight
            weights.midterm_weight = midterm_weight
            weights.end_term_weight = end_term_weight
            if ca_total_weight is not None:
                weights.ca_total_weight = ca_total_weight
            if exam_total_weight is not None:
                weights.exam_total_weight = exam_total_weight
            weights.updated_at = datetime.now(UTC)
        else:
            # Create new
            weights = AssessmentWeight(
                tenant_id=tenant_id,
                academic_year_id=academic_year_id,
                class_work_weight=class_work_weight,
                homework_weight=homework_weight,
                midterm_weight=midterm_weight,
                end_term_weight=end_term_weight,
                ca_total_weight=ca_total_weight or Decimal("50"),
                exam_total_weight=exam_total_weight or Decimal("50"),
            )
            self.db.add(weights)

        await self.db.flush()
        await self.db.refresh(weights)
        return weights

    async def get_assessment_weights(
        self, tenant_id: UUID, academic_year_id: Optional[UUID] = None
    ) -> Optional[AssessmentWeight]:
        """Get assessment weights."""
        # First try to get year-specific weights
        if academic_year_id:
            result = await self.db.execute(
                select(AssessmentWeight).where(
                    and_(
                        AssessmentWeight.tenant_id == tenant_id,
                        AssessmentWeight.academic_year_id == academic_year_id,
                    )
                )
            )
            weights = result.scalar_one_or_none()
            if weights:
                return weights

        # Fall back to default weights (no academic year)
        result = await self.db.execute(
            select(AssessmentWeight).where(
                and_(
                    AssessmentWeight.tenant_id == tenant_id,
                    AssessmentWeight.academic_year_id.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    # =========================
    # Academic Settings
    # =========================

    async def get_academic_settings(self, tenant_id: UUID) -> Optional[AcademicSettings]:
        """Get academic settings for a tenant."""
        result = await self.db.execute(
            select(AcademicSettings).where(AcademicSettings.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_academic_settings(
        self,
        tenant_id: UUID,
        auto_promote_students: Optional[bool] = None,
        allow_grade_amendments: Optional[bool] = None,
        show_position_on_report_cards: Optional[bool] = None,
        require_attendance_for_exams: Optional[bool] = None,
        enable_continuous_assessment: Optional[bool] = None,
    ) -> AcademicSettings:
        """Update or create academic settings for a tenant."""
        settings = await self.get_academic_settings(tenant_id)

        if settings:
            # Update existing settings
            if auto_promote_students is not None:
                settings.auto_promote_students = auto_promote_students
            if allow_grade_amendments is not None:
                settings.allow_grade_amendments = allow_grade_amendments
            if show_position_on_report_cards is not None:
                settings.show_position_on_report_cards = show_position_on_report_cards
            if require_attendance_for_exams is not None:
                settings.require_attendance_for_exams = require_attendance_for_exams
            if enable_continuous_assessment is not None:
                settings.enable_continuous_assessment = enable_continuous_assessment
            settings.updated_at = datetime.now(UTC)
        else:
            # Create new settings
            settings = AcademicSettings(
                tenant_id=tenant_id,
                auto_promote_students=auto_promote_students if auto_promote_students is not None else False,
                allow_grade_amendments=allow_grade_amendments if allow_grade_amendments is not None else True,
                show_position_on_report_cards=show_position_on_report_cards if show_position_on_report_cards is not None else True,
                require_attendance_for_exams=require_attendance_for_exams if require_attendance_for_exams is not None else False,
                enable_continuous_assessment=enable_continuous_assessment if enable_continuous_assessment is not None else True,
            )
            self.db.add(settings)

        await self.db.flush()
        await self.db.refresh(settings)
        return settings

"""
SIMS Plus - Academic Service

Business logic for academic management.
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    AcademicYear,
    AcademicYearStatus,
    Term,
    TermStatus,
    Class,
    ClassSection,
    Subject,
    ClassSubject,
    GradingScale,
    GradingScaleType,
    Grade,
    AssessmentWeight,
    AcademicSettings,
)


class AcademicServiceError(Exception):
    """Base exception for academic service errors."""

    def __init__(self, message: str, code: str = "academic_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class AcademicService:
    """Service for managing academic entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Academic Year Methods
    # =========================

    async def create_academic_year(
        self,
        tenant_id: UUID,
        name: str,
        start_date,
        end_date,
        description: Optional[str] = None,
        is_current: bool = False,
    ) -> AcademicYear:
        """Create a new academic year."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.name == name,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Academic year '{name}' already exists",
                code="duplicate_academic_year",
            )

        # If setting as current, unset other current years
        if is_current:
            await self._unset_current_academic_year(tenant_id)

        academic_year = AcademicYear(
            tenant_id=tenant_id,
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=AcademicYearStatus.PLANNING,
            is_current=is_current,
        )
        self.db.add(academic_year)
        await self.db.commit()
        await self.db.refresh(academic_year)
        return academic_year

    async def get_academic_year(
        self, academic_year_id: UUID, include_terms: bool = False
    ) -> Optional[AcademicYear]:
        """Get academic year by ID."""
        query = select(AcademicYear).where(
            and_(
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if include_terms:
            query = query.options(selectinload(AcademicYear.terms))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_academic_years(
        self, tenant_id: UUID, include_terms: bool = False
    ) -> Sequence[AcademicYear]:
        """List all academic years for a tenant."""
        query = select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        ).order_by(AcademicYear.start_date.desc())

        if include_terms:
            query = query.options(selectinload(AcademicYear.terms))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_academic_year(
        self, academic_year_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[AcademicYear]:
        """Update an academic year."""
        academic_year = await self.get_academic_year(academic_year_id)
        if not academic_year:
            return None

        # Handle is_current specially
        if kwargs.get("is_current"):
            await self._unset_current_academic_year(tenant_id)

        # Handle status change
        if "status" in kwargs:
            kwargs["status"] = AcademicYearStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(academic_year, key):
                setattr(academic_year, key, value)

        academic_year.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(academic_year)
        return academic_year

    async def delete_academic_year(self, academic_year_id: UUID) -> bool:
        """Soft delete an academic year."""
        academic_year = await self.get_academic_year(academic_year_id)
        if not academic_year:
            return False

        academic_year.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def _unset_current_academic_year(self, tenant_id: UUID) -> None:
        """Unset current flag for all academic years in tenant."""
        result = await self.db.execute(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.is_current == True,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        for year in result.scalars().all():
            year.is_current = False

    # =========================
    # Term Methods
    # =========================

    async def create_term(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        name: str,
        start_date,
        end_date,
        sequence: int = 1,
        short_name: Optional[str] = None,
    ) -> Term:
        """Create a new term."""
        # Verify academic year exists
        academic_year = await self.get_academic_year(academic_year_id)
        if not academic_year:
            raise AcademicServiceError(
                "Academic year not found",
                code="academic_year_not_found",
            )

        # Check for duplicate name in same academic year
        existing = await self.db.execute(
            select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.academic_year_id == academic_year_id,
                    Term.name == name,
                    Term.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Term '{name}' already exists in this academic year",
                code="duplicate_term",
            )

        term = Term(
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            name=name,
            short_name=short_name,
            sequence=sequence,
            start_date=start_date,
            end_date=end_date,
            status=TermStatus.UPCOMING,
            is_current=False,
        )
        self.db.add(term)
        await self.db.commit()
        await self.db.refresh(term)
        return term

    async def get_term(self, term_id: UUID) -> Optional[Term]:
        """Get term by ID."""
        result = await self.db.execute(
            select(Term).where(
                and_(Term.id == term_id, Term.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def list_terms(
        self,
        tenant_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> Sequence[Term]:
        """List terms, optionally filtered by academic year."""
        conditions = [
            Term.tenant_id == tenant_id,
            Term.deleted_at.is_(None),
        ]
        if academic_year_id:
            conditions.append(Term.academic_year_id == academic_year_id)

        result = await self.db.execute(
            select(Term)
            .where(and_(*conditions))
            .order_by(Term.start_date)
        )
        return result.scalars().all()

    async def update_term(self, term_id: UUID, tenant_id: UUID, **kwargs) -> Optional[Term]:
        """Update a term."""
        term = await self.get_term(term_id)
        if not term:
            return None

        # Handle is_current specially
        if kwargs.get("is_current"):
            await self._unset_current_term(tenant_id)

        # Handle status change
        if "status" in kwargs:
            kwargs["status"] = TermStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(term, key):
                setattr(term, key, value)

        term.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(term)
        return term

    async def delete_term(self, term_id: UUID) -> bool:
        """Soft delete a term."""
        term = await self.get_term(term_id)
        if not term:
            return False

        term.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def _unset_current_term(self, tenant_id: UUID) -> None:
        """Unset current flag for all terms in tenant."""
        result = await self.db.execute(
            select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.is_current == True,
                    Term.deleted_at.is_(None),
                )
            )
        )
        for term in result.scalars().all():
            term.is_current = False

    # =========================
    # Class Methods
    # =========================

    async def create_class(
        self,
        tenant_id: UUID,
        name: str,
        short_name: Optional[str] = None,
        level: Optional[str] = None,
        sequence: int = 1,
        capacity: Optional[int] = None,
        school_id: Optional[UUID] = None,
    ) -> Class:
        """Create a new class."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(Class).where(
                and_(
                    Class.tenant_id == tenant_id,
                    Class.name == name,
                    Class.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Class '{name}' already exists",
                code="duplicate_class",
            )

        class_ = Class(
            tenant_id=tenant_id,
            name=name,
            short_name=short_name,
            level=level,
            sequence=sequence,
            capacity=capacity,
            school_id=school_id,
            is_active=True,
        )
        self.db.add(class_)
        await self.db.commit()
        await self.db.refresh(class_)
        return class_

    async def get_class(
        self, class_id: UUID, include_sections: bool = False
    ) -> Optional[Class]:
        """Get class by ID."""
        query = select(Class).where(
            and_(Class.id == class_id, Class.deleted_at.is_(None))
        )
        if include_sections:
            query = query.options(selectinload(Class.sections))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_classes(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        include_sections: bool = False,
        active_only: bool = True,
    ) -> Sequence[Class]:
        """List classes."""
        conditions = [
            Class.tenant_id == tenant_id,
            Class.deleted_at.is_(None),
        ]
        if school_id:
            conditions.append(Class.school_id == school_id)
        if active_only:
            conditions.append(Class.is_active == True)

        query = select(Class).where(and_(*conditions)).order_by(Class.sequence)

        if include_sections:
            query = query.options(selectinload(Class.sections))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_class(self, class_id: UUID, **kwargs) -> Optional[Class]:
        """Update a class."""
        class_ = await self.get_class(class_id)
        if not class_:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(class_, key):
                setattr(class_, key, value)

        class_.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(class_)
        return class_

    async def delete_class(self, class_id: UUID) -> bool:
        """Soft delete a class."""
        class_ = await self.get_class(class_id)
        if not class_:
            return False

        class_.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    # =========================
    # Class Section Methods
    # =========================

    async def create_section(
        self,
        tenant_id: UUID,
        class_id: UUID,
        name: str,
        capacity: Optional[int] = None,
        class_teacher_id: Optional[UUID] = None,
    ) -> ClassSection:
        """Create a new class section."""
        # Verify class exists
        class_ = await self.get_class(class_id)
        if not class_:
            raise AcademicServiceError("Class not found", code="class_not_found")

        # Check for duplicate name in same class
        existing = await self.db.execute(
            select(ClassSection).where(
                and_(
                    ClassSection.tenant_id == tenant_id,
                    ClassSection.class_id == class_id,
                    ClassSection.name == name,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Section '{name}' already exists in this class",
                code="duplicate_section",
            )

        section = ClassSection(
            tenant_id=tenant_id,
            class_id=class_id,
            name=name,
            capacity=capacity,
            class_teacher_id=class_teacher_id,
            is_active=True,
        )
        self.db.add(section)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    async def get_section(self, section_id: UUID) -> Optional[ClassSection]:
        """Get section by ID."""
        result = await self.db.execute(
            select(ClassSection).where(
                and_(
                    ClassSection.id == section_id,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_sections(
        self,
        tenant_id: UUID,
        class_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> Sequence[ClassSection]:
        """List sections."""
        conditions = [
            ClassSection.tenant_id == tenant_id,
            ClassSection.deleted_at.is_(None),
        ]
        if class_id:
            conditions.append(ClassSection.class_id == class_id)
        if active_only:
            conditions.append(ClassSection.is_active == True)

        result = await self.db.execute(
            select(ClassSection)
            .where(and_(*conditions))
            .order_by(ClassSection.name)
        )
        return result.scalars().all()

    async def update_section(self, section_id: UUID, **kwargs) -> Optional[ClassSection]:
        """Update a section."""
        section = await self.get_section(section_id)
        if not section:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(section, key):
                setattr(section, key, value)

        section.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    async def delete_section(self, section_id: UUID) -> bool:
        """Soft delete a section."""
        section = await self.get_section(section_id)
        if not section:
            return False

        section.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

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
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def get_subject(self, subject_id: UUID) -> Optional[Subject]:
        """Get subject by ID."""
        result = await self.db.execute(
            select(Subject).where(
                and_(Subject.id == subject_id, Subject.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def list_subjects(
        self,
        tenant_id: UUID,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> Sequence[Subject]:
        """List subjects."""
        conditions = [
            Subject.tenant_id == tenant_id,
            Subject.deleted_at.is_(None),
        ]
        if category:
            conditions.append(Subject.category == category)
        if active_only:
            conditions.append(Subject.is_active == True)

        result = await self.db.execute(
            select(Subject).where(and_(*conditions)).order_by(Subject.name)
        )
        return result.scalars().all()

    async def update_subject(self, subject_id: UUID, **kwargs) -> Optional[Subject]:
        """Update a subject."""
        subject = await self.get_subject(subject_id)
        if not subject:
            return None

        if "code" in kwargs and kwargs["code"]:
            kwargs["code"] = kwargs["code"].upper()

        for key, value in kwargs.items():
            if value is not None and hasattr(subject, key):
                setattr(subject, key, value)

        subject.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def delete_subject(self, subject_id: UUID) -> bool:
        """Soft delete a subject."""
        subject = await self.get_subject(subject_id)
        if not subject:
            return False

        subject.deleted_at = datetime.now(UTC)
        await self.db.commit()
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
        # Verify class and subject exist
        class_ = await self.get_class(class_id)
        subject = await self.get_subject(subject_id)
        if not class_:
            raise AcademicServiceError("Class not found", code="class_not_found")
        if not subject:
            raise AcademicServiceError("Subject not found", code="subject_not_found")

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
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def remove_subject_from_class(
        self, class_id: UUID, subject_id: UUID
    ) -> bool:
        """Remove a subject assignment from a class."""
        result = await self.db.execute(
            select(ClassSubject).where(
                and_(
                    ClassSubject.class_id == class_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.commit()
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

        await self.db.commit()
        await self.db.refresh(grading_scale)
        return grading_scale

    async def get_grading_scale(
        self, scale_id: UUID, include_grades: bool = False
    ) -> Optional[GradingScale]:
        """Get grading scale by ID."""
        query = select(GradingScale).where(
            and_(
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
        scale = await self.get_grading_scale(scale_id)
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
        await self.db.commit()
        await self.db.refresh(scale)
        return scale

    async def delete_grading_scale(self, scale_id: UUID) -> bool:
        """Soft delete a grading scale."""
        scale = await self.get_grading_scale(scale_id)
        if not scale:
            return False

        scale.deleted_at = datetime.now(UTC)
        await self.db.commit()
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
        scale = await self.get_grading_scale(grading_scale_id)
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
        await self.db.commit()
        await self.db.refresh(grade_obj)
        return grade_obj

    async def update_grade(self, grade_id: UUID, **kwargs) -> Optional[Grade]:
        """Update a grade."""
        result = await self.db.execute(
            select(Grade).where(Grade.id == grade_id)
        )
        grade = result.scalar_one_or_none()
        if not grade:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(grade, key):
                setattr(grade, key, value)

        grade.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(grade)
        return grade

    async def delete_grade(self, grade_id: UUID) -> bool:
        """Delete a grade."""
        result = await self.db.execute(
            select(Grade).where(Grade.id == grade_id)
        )
        grade = result.scalar_one_or_none()
        if not grade:
            return False

        await self.db.delete(grade)
        await self.db.commit()
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
            )
            self.db.add(weights)

        await self.db.commit()
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

        await self.db.commit()
        await self.db.refresh(settings)
        return settings

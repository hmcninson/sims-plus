"""
SIMS Plus - Exam Service

Business logic for exam CRUD operations and exam subject management.
"""

from datetime import datetime, UTC, date
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.exam import (
    Exam,
    ExamType,
    ExamStatus,
    ExamSubject,
    ExamSubjectStatus,
    ScoreChangeLog,
)
from app.models.academic import (
    ClassSubject,
)
from app.services.academic.guards import assert_term_year_editable


class ExamServiceError(Exception):
    """Base exception for exam service errors."""

    def __init__(self, message: str, code: str = "exam_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ExamService:
    """Service for managing examinations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Audit Trail Helper
    # =========================

    async def _log_score_change(
        self,
        tenant_id: UUID,
        exam_score_id: UUID,
        old_score: Optional[Decimal],
        new_score: Optional[Decimal],
        old_is_absent: Optional[bool],
        new_is_absent: Optional[bool],
        change_type: str,
        changed_by: Optional[UUID] = None,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a score change to the audit trail."""
        log_entry = ScoreChangeLog(
            tenant_id=tenant_id,
            exam_score_id=exam_score_id,
            old_score=old_score,
            new_score=new_score,
            old_is_absent=old_is_absent,
            new_is_absent=new_is_absent,
            change_type=change_type,
            change_reason=change_reason,
            changed_by=changed_by,
            changed_at=datetime.now(UTC),
            ip_address=ip_address,
        )
        self.db.add(log_entry)

    # =========================
    # Exam CRUD
    # =========================

    async def create_exam(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        name: str,
        exam_type: str,
        description: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        created_by: Optional[UUID] = None,
    ) -> Exam:
        """Create a new exam."""
        # Guard: cannot create exams in completed/archived years
        await assert_term_year_editable(self.db, tenant_id, term_id)

        # Check for duplicate name in same term
        existing = await self.db.execute(
            select(Exam).where(
                and_(
                    Exam.tenant_id == tenant_id,
                    Exam.academic_year_id == academic_year_id,
                    Exam.term_id == term_id,
                    Exam.name == name,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ExamServiceError(
                f"Exam '{name}' already exists in this term",
                code="duplicate_exam",
            )

        exam = Exam(
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            name=name,
            description=description,
            exam_type=ExamType(exam_type),
            start_date=start_date,
            end_date=end_date,
            status=ExamStatus.DRAFT,
            created_by=created_by,
        )
        self.db.add(exam)
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def get_exam(
        self, tenant_id: UUID, exam_id: UUID, include_subjects: bool = False
    ) -> Optional[Exam]:
        """Get exam by ID."""
        query = select(Exam).where(
            and_(
                Exam.id == exam_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Exam.tenant_id == tenant_id,
                Exam.deleted_at.is_(None),
            )
        ).options(
            joinedload(Exam.academic_year),
            joinedload(Exam.term),
            selectinload(Exam.subjects),  # Always load subjects for count
        )
        if include_subjects:
            query = query.options(
                selectinload(Exam.subjects).selectinload(ExamSubject.subject),
                selectinload(Exam.subjects).selectinload(ExamSubject.class_),
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_exams(
        self,
        tenant_id: UUID,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        exam_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Exam], int]:
        """List exams with filters."""
        query = select(Exam).where(
            and_(
                Exam.tenant_id == tenant_id,
                Exam.deleted_at.is_(None),
            )
        )

        if academic_year_id:
            query = query.where(Exam.academic_year_id == academic_year_id)
        if term_id:
            query = query.where(Exam.term_id == term_id)
        if exam_type:
            query = query.where(Exam.exam_type == ExamType(exam_type))
        if status:
            query = query.where(Exam.status == ExamStatus(status))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results with eager loading
        query = query.options(
            joinedload(Exam.academic_year),
            joinedload(Exam.term),
            selectinload(Exam.subjects),
        ).order_by(desc(Exam.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_exam(
        self, exam_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[Exam]:
        """Update an exam."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(Exam).where(
                and_(
                    Exam.id == exam_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        exam = result.scalar_one_or_none()
        if not exam:
            return None

        if "exam_type" in kwargs and kwargs["exam_type"]:
            kwargs["exam_type"] = ExamType(kwargs["exam_type"])
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = ExamStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(exam, key):
                setattr(exam, key, value)

        exam.updated_at = datetime.now(UTC)
        await self.db.flush()

        # Re-query to get fresh data with eager-loaded relationships
        return await self.get_exam(tenant_id, exam_id)

    async def update_exam_status(
        self, exam_id: UUID, tenant_id: UUID, status: str
    ) -> Optional[Exam]:
        """Update exam status."""
        return await self.update_exam(exam_id, tenant_id, status=status)

    async def delete_exam(self, exam_id: UUID, tenant_id: UUID) -> bool:
        """Soft delete an exam."""
        exam = await self.get_exam(tenant_id, exam_id)
        if not exam:
            return False

        exam.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # =========================
    # Exam Subject Methods
    # =========================

    async def add_exam_subject(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        subject_id: UUID,
        class_id: UUID,
        section_id: Optional[UUID] = None,
        max_score: Decimal = Decimal("100.00"),
        pass_mark: Decimal = Decimal("50.00"),
        exam_date: Optional[date] = None,
        exam_time=None,
        duration_minutes: Optional[int] = None,
        venue: Optional[str] = None,
        grading_scale_id: Optional[UUID] = None,
    ) -> ExamSubject:
        """Add a subject to an exam for a class/section."""
        # Check for duplicate (including section)
        query = select(ExamSubject).where(
            and_(
                ExamSubject.tenant_id == tenant_id,
                ExamSubject.exam_id == exam_id,
                ExamSubject.subject_id == subject_id,
                ExamSubject.class_id == class_id,
            )
        )
        # Handle NULL section_id comparison
        if section_id is None:
            query = query.where(ExamSubject.section_id.is_(None))
        else:
            query = query.where(ExamSubject.section_id == section_id)

        existing = await self.db.execute(query)
        if existing.scalar_one_or_none():
            raise ExamServiceError(
                "Subject already added to exam for this class/section",
                code="duplicate_exam_subject",
            )

        exam_subject = ExamSubject(
            tenant_id=tenant_id,
            exam_id=exam_id,
            subject_id=subject_id,
            class_id=class_id,
            section_id=section_id,
            grading_scale_id=grading_scale_id,
            max_score=max_score,
            pass_mark=pass_mark,
            exam_date=exam_date,
            exam_time=exam_time,
            duration_minutes=duration_minutes,
            venue=venue,
            status=ExamSubjectStatus.PENDING,
        )
        self.db.add(exam_subject)
        await self.db.flush()
        await self.db.refresh(exam_subject)
        return exam_subject

    async def add_exam_subjects_bulk(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        class_ids: list[UUID],
        subject_ids: list[UUID],
        section_ids: Optional[list[UUID]] = None,
        grading_scale_id: Optional[UUID] = None,
        max_score: Decimal = Decimal("100.00"),
        pass_mark: Decimal = Decimal("50.00"),
    ) -> list[ExamSubject]:
        """
        Bulk add subjects to exam for multiple classes/sections.

        Logic:
        - For each class, check if any of the provided sections belong to it
        - If sections are selected for a class, create exam_subject for each section
        - If no sections are selected for a class, create exam_subject for whole class (section_id=None)
        """
        from app.models.academic import ClassSection

        created = []

        # Build a map of class_id -> list of selected section_ids for that class
        class_sections_map: dict[UUID, list[UUID]] = {cid: [] for cid in class_ids}

        if section_ids:
            # Look up which class each section belongs to
            sections_result = await self.db.execute(
                select(ClassSection).where(
                    and_(
                        ClassSection.id.in_(section_ids),
                        # Defense-in-depth: filter by tenant_id
                        ClassSection.tenant_id == tenant_id,
                    )
                )
            )
            sections = sections_result.scalars().all()

            for section in sections:
                if section.class_id in class_sections_map:
                    class_sections_map[section.class_id].append(section.id)

        # Now create exam subjects
        for class_id in class_ids:
            selected_sections = class_sections_map.get(class_id, [])

            if selected_sections:
                # Create exam_subject for each selected section
                for section_id in selected_sections:
                    for subject_id in subject_ids:
                        try:
                            es = await self.add_exam_subject(
                                tenant_id=tenant_id,
                                exam_id=exam_id,
                                subject_id=subject_id,
                                class_id=class_id,
                                section_id=section_id,
                                grading_scale_id=grading_scale_id,
                                max_score=max_score,
                                pass_mark=pass_mark,
                            )
                            created.append(es)
                        except ExamServiceError:
                            # Skip duplicates
                            pass
            else:
                # No sections selected for this class - create for whole class
                for subject_id in subject_ids:
                    try:
                        es = await self.add_exam_subject(
                            tenant_id=tenant_id,
                            exam_id=exam_id,
                            subject_id=subject_id,
                            class_id=class_id,
                            section_id=None,
                            grading_scale_id=grading_scale_id,
                            max_score=max_score,
                            pass_mark=pass_mark,
                        )
                        created.append(es)
                    except ExamServiceError:
                        # Skip duplicates
                        pass

        return created

    async def auto_populate_from_curriculum(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        class_ids: list[UUID],
        max_score: Decimal = Decimal("100.00"),
        pass_mark: Decimal = Decimal("50.00"),
        grading_scale_id: Optional[UUID] = None,
    ) -> list[ExamSubject]:
        """
        Auto-populate exam subjects from curriculum (ClassSubject).

        For each selected class, fetches all subjects assigned to that class
        and creates ExamSubject records.
        """
        # Fetch all ClassSubjects for selected classes
        result = await self.db.execute(
            select(ClassSubject)
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id.in_(class_ids),
                )
            )
            .options(
                joinedload(ClassSubject.subject),
                joinedload(ClassSubject.class_),
            )
        )
        class_subjects = result.scalars().unique().all()

        if not class_subjects:
            raise ExamServiceError(
                "No subjects found in curriculum for selected classes",
                code="no_curriculum_subjects"
            )

        created = []
        for cs in class_subjects:
            try:
                es = await self.add_exam_subject(
                    tenant_id=tenant_id,
                    exam_id=exam_id,
                    subject_id=cs.subject_id,
                    class_id=cs.class_id,
                    max_score=max_score,
                    pass_mark=pass_mark,
                    grading_scale_id=grading_scale_id,
                )
                created.append(es)
            except ExamServiceError:
                # Skip duplicates (subject already added to exam for this class)
                pass

        return created

    async def get_exam_subject(self, tenant_id: UUID, exam_subject_id: UUID) -> Optional[ExamSubject]:
        """Get exam subject by ID."""
        result = await self.db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ExamSubject.tenant_id == tenant_id,
                )
            )
            .options(
                joinedload(ExamSubject.subject),
                joinedload(ExamSubject.class_),
            )
        )
        return result.scalar_one_or_none()

    async def list_exam_subjects(self, tenant_id: UUID, exam_id: UUID) -> Sequence[ExamSubject]:
        """List all subjects for an exam."""
        result = await self.db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ExamSubject.tenant_id == tenant_id,
                )
            )
            .options(
                joinedload(ExamSubject.subject),
                joinedload(ExamSubject.class_),
                joinedload(ExamSubject.section),
                joinedload(ExamSubject.grading_scale),
                selectinload(ExamSubject.scores),
            )
            .order_by(ExamSubject.class_id, ExamSubject.section_id, ExamSubject.subject_id)
        )
        return result.scalars().unique().all()

    async def update_exam_subject(
        self, exam_subject_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[ExamSubject]:
        """Update exam subject."""
        exam_subject = await self.get_exam_subject(tenant_id, exam_subject_id)
        if not exam_subject:
            return None

        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = ExamSubjectStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(exam_subject, key):
                setattr(exam_subject, key, value)

        exam_subject.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(exam_subject)
        return exam_subject

    async def delete_exam_subject(
        self, exam_subject_id: UUID, tenant_id: UUID
    ) -> bool:
        """Delete exam subject (and all related scores)."""
        exam_subject = await self.get_exam_subject(tenant_id, exam_subject_id)
        if not exam_subject:
            return False

        await self.db.delete(exam_subject)
        await self.db.flush()
        return True

    # =========================
    # Mock → Predicted Grades
    # =========================

    async def generate_predicted_grades_from_mock(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        predicted_by: UUID,
    ) -> dict:
        """Generate predicted grades from mock exam results.

        For each student-subject score in the mock exam:
        1. Look up the curriculum profile from the exam subject's class
        2. Resolve the grading scale and score strategy for that curriculum
        3. Determine the grade from the raw score
        4. Upsert a PredictedGrade record (skip manually-set predictions)

        Returns: {"created": int, "updated": int, "skipped": int}
        """
        from app.models.academic import Class, Grade, GradingScale
        from app.models.curriculum import CurriculumProfile, PredictedGrade
        from app.services.exam.score_strategies import get_score_strategy

        # 1. Fetch exam and validate it's a published mock
        exam = await self.get_exam(tenant_id, exam_id)
        if not exam:
            raise ExamServiceError("Exam not found", "not_found")
        if exam.exam_type != ExamType.MOCK:
            raise ExamServiceError(
                "Only mock exams can generate predicted grades",
                "invalid_type",
            )
        if exam.status != ExamStatus.RESULTS_PUBLISHED:
            raise ExamServiceError(
                "Results must be published before generating predicted grades",
                "invalid_status",
            )

        # 2. Load all exam subjects with their scores for this exam
        exam_subjects_result = await self.db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.tenant_id == tenant_id,
                    ExamSubject.exam_id == exam_id,
                )
            )
            .options(
                selectinload(ExamSubject.scores),
            )
        )
        exam_subjects = exam_subjects_result.scalars().unique().all()

        if not exam_subjects:
            raise ExamServiceError(
                "No subjects found for this exam",
                "no_subjects",
            )

        # 3. Collect unique class IDs and resolve their curriculum profiles
        class_ids = list({es.class_id for es in exam_subjects})
        class_result = await self.db.execute(
            select(Class).where(
                and_(
                    Class.tenant_id == tenant_id,
                    Class.id.in_(class_ids),
                )
            )
        )
        classes = {c.id: c for c in class_result.scalars().all()}

        # Resolve curriculum profiles from classes
        profile_ids = {
            c.curriculum_profile_id
            for c in classes.values()
            if c.curriculum_profile_id
        }

        if not profile_ids:
            raise ExamServiceError(
                "No curriculum profile found for the exam's classes. "
                "Predicted grades require a curriculum profile assigned to the class.",
                "no_profile",
            )

        profile_result = await self.db.execute(
            select(CurriculumProfile).where(
                and_(
                    CurriculumProfile.tenant_id == tenant_id,
                    CurriculumProfile.id.in_(profile_ids),
                    CurriculumProfile.deleted_at.is_(None),
                )
            )
        )
        profiles = {p.id: p for p in profile_result.scalars().all()}

        # 4. Load grading scales and grades for each profile
        grading_scale_ids = {
            p.grading_scale_id
            for p in profiles.values()
            if p.grading_scale_id
        }
        grades_by_scale: dict[UUID, list] = {}
        if grading_scale_ids:
            grades_result = await self.db.execute(
                select(Grade).where(
                    and_(
                        Grade.tenant_id == tenant_id,
                        Grade.grading_scale_id.in_(grading_scale_ids),
                    )
                )
            )
            for grade in grades_result.scalars().all():
                grades_by_scale.setdefault(grade.grading_scale_id, []).append(grade)

        # 5. Process each exam subject's scores
        created = 0
        updated = 0
        skipped = 0
        now = datetime.now(UTC)

        for exam_subject in exam_subjects:
            # Resolve profile for this exam subject's class
            class_obj = classes.get(exam_subject.class_id)
            if not class_obj or not class_obj.curriculum_profile_id:
                # Class has no curriculum profile — skip all its scores
                skipped += len(exam_subject.scores) if exam_subject.scores else 0
                continue

            profile = profiles.get(class_obj.curriculum_profile_id)
            if not profile or not profile.grading_scale_id:
                skipped += len(exam_subject.scores) if exam_subject.scores else 0
                continue

            strategy = get_score_strategy(profile.curriculum_type.value)
            grades_list = grades_by_scale.get(profile.grading_scale_id, [])

            if not grades_list:
                skipped += len(exam_subject.scores) if exam_subject.scores else 0
                continue

            for score_record in (exam_subject.scores or []):
                if score_record.is_absent or score_record.score is None:
                    skipped += 1
                    continue

                # Determine grade using the curriculum's strategy
                grade_label, grade_point, remark = strategy.determine_grade(
                    score_record.score, grades_list
                )

                if not grade_label:
                    skipped += 1
                    continue

                # Check for existing predicted grade (upsert logic)
                existing_result = await self.db.execute(
                    select(PredictedGrade).where(
                        and_(
                            PredictedGrade.tenant_id == tenant_id,
                            PredictedGrade.student_id == score_record.student_id,
                            PredictedGrade.subject_id == exam_subject.subject_id,
                            PredictedGrade.academic_year_id == exam.academic_year_id,
                            PredictedGrade.deleted_at.is_(None),
                        )
                    )
                )
                pg = existing_result.scalar_one_or_none()

                auto_generated_marker = "Auto-generated from mock exam"

                if pg:
                    # >>REVIEW FIX H2: Don't overwrite manually-set predictions.
                    # Only update if the existing record was auto-generated.
                    if pg.notes and auto_generated_marker not in pg.notes:
                        skipped += 1
                        continue

                    pg.predicted_grade = grade_label
                    pg.predicted_score = score_record.score
                    pg.predicted_by = predicted_by
                    pg.predicted_at = now
                    pg.notes = f"{auto_generated_marker}: {exam.name}"
                    updated += 1
                else:
                    new_pg = PredictedGrade(
                        tenant_id=tenant_id,
                        student_id=score_record.student_id,
                        subject_id=exam_subject.subject_id,
                        academic_year_id=exam.academic_year_id,
                        term_id=exam.term_id,
                        predicted_grade=grade_label,
                        predicted_score=score_record.score,
                        predicted_by=predicted_by,
                        predicted_at=now,
                        notes=f"{auto_generated_marker}: {exam.name}",
                    )
                    self.db.add(new_pg)
                    created += 1

        await self.db.flush()
        return {"created": created, "updated": updated, "skipped": skipped}

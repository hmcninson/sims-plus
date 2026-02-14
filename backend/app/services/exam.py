"""
SIMS Plus - Examination Service

Business logic for examination management, score entry, and grade calculation.
"""

from datetime import datetime, UTC, date, timedelta
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc, or_, text, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.exam import (
    Exam,
    ExamType,
    ExamStatus,
    ExamSubject,
    ExamSubjectStatus,
    ExamScore,
    ContinuousAssessment,
    AssessmentType,
    TermReport,
    ScoreChangeLog,
)
from app.models.academic import (
    AcademicYear,
    Term,
    Class,
    ClassSection,
    Subject,
    ClassSubject,
    GradingScale,
    Grade,
    AssessmentWeight,
    SchoolHoliday,
)
from app.models.student import Student
from app.models.staff import StaffClassAssignment
from app.models.attendance import StudentAttendance, AttendanceStatus


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
        await self.db.commit()
        await self.db.refresh(exam)
        return exam

    async def get_exam(
        self, exam_id: UUID, include_subjects: bool = False
    ) -> Optional[Exam]:
        """Get exam by ID."""
        query = select(Exam).where(
            and_(
                Exam.id == exam_id,
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
        # First get with basic query to check ownership
        result = await self.db.execute(
            select(Exam).where(
                and_(Exam.id == exam_id, Exam.deleted_at.is_(None))
            )
        )
        exam = result.scalar_one_or_none()
        if not exam or exam.tenant_id != tenant_id:
            return None

        if "exam_type" in kwargs and kwargs["exam_type"]:
            kwargs["exam_type"] = ExamType(kwargs["exam_type"])
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = ExamStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(exam, key):
                setattr(exam, key, value)

        exam.updated_at = datetime.now(UTC)
        await self.db.commit()

        # Re-query to get fresh data
        return await self.get_exam(exam_id)

    async def update_exam_status(
        self, exam_id: UUID, tenant_id: UUID, status: str
    ) -> Optional[Exam]:
        """Update exam status."""
        return await self.update_exam(exam_id, tenant_id, status=status)

    async def delete_exam(self, exam_id: UUID, tenant_id: UUID) -> bool:
        """Soft delete an exam."""
        exam = await self.get_exam(exam_id)
        if not exam or exam.tenant_id != tenant_id:
            return False

        exam.deleted_at = datetime.now(UTC)
        await self.db.commit()
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
        await self.db.commit()
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
                select(ClassSection).where(ClassSection.id.in_(section_ids))
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

    async def get_exam_subject(self, exam_subject_id: UUID) -> Optional[ExamSubject]:
        """Get exam subject by ID."""
        result = await self.db.execute(
            select(ExamSubject)
            .where(ExamSubject.id == exam_subject_id)
            .options(
                joinedload(ExamSubject.subject),
                joinedload(ExamSubject.class_),
            )
        )
        return result.scalar_one_or_none()

    async def list_exam_subjects(self, exam_id: UUID) -> Sequence[ExamSubject]:
        """List all subjects for an exam."""
        result = await self.db.execute(
            select(ExamSubject)
            .where(ExamSubject.exam_id == exam_id)
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
        exam_subject = await self.get_exam_subject(exam_subject_id)
        if not exam_subject or exam_subject.tenant_id != tenant_id:
            return None

        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = ExamSubjectStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(exam_subject, key):
                setattr(exam_subject, key, value)

        exam_subject.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(exam_subject)
        return exam_subject

    async def delete_exam_subject(
        self, exam_subject_id: UUID, tenant_id: UUID
    ) -> bool:
        """Delete exam subject (and all related scores)."""
        exam_subject = await self.get_exam_subject(exam_subject_id)
        if not exam_subject or exam_subject.tenant_id != tenant_id:
            return False

        await self.db.delete(exam_subject)
        await self.db.commit()
        return True


class ScoreService:
    """Service for managing exam scores."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_score_entry_form(
        self, exam_subject_id: UUID, section_id: Optional[UUID] = None
    ) -> Optional[dict]:
        """Get score entry form with exam subject details and students."""
        # Get exam subject with relations (including section)
        exam_subject_result = await self.db.execute(
            select(ExamSubject)
            .where(ExamSubject.id == exam_subject_id)
            .options(
                joinedload(ExamSubject.class_),
                joinedload(ExamSubject.subject),
                joinedload(ExamSubject.section),
            )
        )
        exam_subject = exam_subject_result.scalar_one_or_none()
        if not exam_subject:
            return None

        # Use exam_subject's section_id if no section_id provided and exam_subject has one
        effective_section_id = section_id or exam_subject.section_id

        # Get section name
        section_name = None
        if effective_section_id:
            if exam_subject.section and exam_subject.section_id == effective_section_id:
                section_name = exam_subject.section.name
            else:
                section_result = await self.db.execute(
                    select(ClassSection.name).where(ClassSection.id == effective_section_id)
                )
                section_name = section_result.scalar_one_or_none()

        # Get students in the class/section with their section info
        query = select(Student).where(
            and_(
                Student.class_id == exam_subject.class_id,
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
        ).options(joinedload(Student.section))
        if effective_section_id:
            query = query.where(Student.section_id == effective_section_id)

        query = query.order_by(Student.last_name, Student.first_name)
        students = (await self.db.execute(query)).unique().scalars().all()

        # Get existing scores
        scores_result = await self.db.execute(
            select(ExamScore).where(ExamScore.exam_subject_id == exam_subject_id)
        )
        scores_map = {s.student_id: s for s in scores_result.scalars().all()}

        # Build students list
        students_data = []
        for student in students:
            score = scores_map.get(student.id)
            students_data.append({
                "student_id": student.id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "student_number": student.student_id,
                "section_id": student.section_id,
                "section_name": student.section.name if student.section else None,
                "current_score": score.score if score else None,
                "current_grade": score.grade if score else None,
                "is_absent": score.is_absent if score else False,
                "teacher_remark": score.teacher_remark if score else None,
                "score_id": score.id if score else None,
            })

        return {
            "exam_subject_id": exam_subject.id,
            "subject_name": exam_subject.subject.name if exam_subject.subject else "",
            "subject_code": exam_subject.subject.code if exam_subject.subject else None,
            "class_id": exam_subject.class_id,
            "class_name": exam_subject.class_.name if exam_subject.class_ else "",
            "section_id": effective_section_id,
            "section_name": section_name,
            "max_score": exam_subject.max_score,
            "pass_mark": exam_subject.pass_mark,
            "grading_scale_id": exam_subject.grading_scale_id,
            "students": students_data,
        }

    async def bulk_enter_scores(
        self,
        tenant_id: UUID,
        exam_subject_id: UUID,
        scores: list[dict],
        entered_by: Optional[UUID] = None,
        grading_scale_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Bulk enter or update scores with audit logging."""
        exam_subject = await self.db.execute(
            select(ExamSubject).where(ExamSubject.id == exam_subject_id)
        )
        exam_subject = exam_subject.scalar_one_or_none()
        if not exam_subject:
            raise ExamServiceError("Exam subject not found", code="not_found")

        # Get grading scale for auto grade calculation
        # Use provided grading_scale_id, or fall back to exam_subject's grading_scale_id
        effective_grading_scale_id = grading_scale_id or exam_subject.grading_scale_id
        grading_grades = []
        if effective_grading_scale_id:
            grades_result = await self.db.execute(
                select(Grade)
                .where(Grade.grading_scale_id == effective_grading_scale_id)
                .order_by(desc(Grade.min_score))
            )
            grading_grades = grades_result.scalars().all()

        # Pre-fetch all valid students for this class/section to validate enrollment
        from app.models.student import Student
        valid_students_query = select(Student.id).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.class_id == exam_subject.class_id,
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
        )
        if exam_subject.section_id:
            valid_students_query = valid_students_query.where(
                Student.section_id == exam_subject.section_id
            )
        valid_students_result = await self.db.execute(valid_students_query)
        valid_student_ids = {row[0] for row in valid_students_result.all()}

        created_count = 0
        updated_count = 0
        failed_count = 0
        errors = []
        now = datetime.now(UTC)

        for score_entry in scores:
            try:
                student_id = score_entry["student_id"]
                raw_score = score_entry.get("score")
                is_absent = score_entry.get("is_absent", False)
                teacher_remark = score_entry.get("teacher_remark")

                # Validate student enrollment in class
                if UUID(student_id) if isinstance(student_id, str) else student_id not in valid_student_ids:
                    raise ValueError(f"Student not enrolled in this class/section")

                # Validate score is within range
                if raw_score is not None:
                    score_decimal = Decimal(str(raw_score))
                    if score_decimal < 0:
                        raise ValueError(f"Score cannot be negative: {raw_score}")
                    if score_decimal > exam_subject.max_score:
                        raise ValueError(
                            f"Score {raw_score} exceeds max score {exam_subject.max_score}"
                        )

                # Calculate grade if score provided
                grade = None
                grade_point = None
                grade_remark = None

                if raw_score is not None and not is_absent and grading_grades:
                    percentage = (Decimal(str(raw_score)) / exam_subject.max_score) * 100
                    for g in grading_grades:
                        if percentage >= g.min_score:
                            grade = g.grade
                            grade_point = g.grade_point
                            grade_remark = g.remark
                            break

                # Check if score exists
                existing = await self.db.execute(
                    select(ExamScore).where(
                        and_(
                            ExamScore.exam_subject_id == exam_subject_id,
                            ExamScore.student_id == student_id,
                        )
                    )
                )
                existing_score = existing.scalar_one_or_none()

                if existing_score:
                    # Store old values for audit log
                    old_score_value = existing_score.score
                    old_is_absent_value = existing_score.is_absent
                    new_score_value = Decimal(str(raw_score)) if raw_score is not None else None

                    # Update
                    existing_score.score = new_score_value
                    existing_score.is_absent = is_absent
                    existing_score.grade = grade
                    existing_score.grade_point = grade_point
                    existing_score.grade_remark = grade_remark
                    existing_score.teacher_remark = teacher_remark
                    existing_score.entered_by = entered_by
                    existing_score.entered_at = now
                    existing_score.updated_at = now
                    updated_count += 1

                    # Log the change if score or absent status changed
                    if old_score_value != new_score_value or old_is_absent_value != is_absent:
                        await self._log_score_change(
                            tenant_id=tenant_id,
                            exam_score_id=existing_score.id,
                            old_score=old_score_value,
                            new_score=new_score_value,
                            old_is_absent=old_is_absent_value,
                            new_is_absent=is_absent,
                            change_type="updated",
                            changed_by=entered_by,
                            ip_address=ip_address,
                        )
                else:
                    # Create
                    new_score_value = Decimal(str(raw_score)) if raw_score is not None else None
                    new_score = ExamScore(
                        tenant_id=tenant_id,
                        exam_subject_id=exam_subject_id,
                        student_id=student_id,
                        score=new_score_value,
                        is_absent=is_absent,
                        grade=grade,
                        grade_point=grade_point,
                        grade_remark=grade_remark,
                        teacher_remark=teacher_remark,
                        entered_by=entered_by,
                        entered_at=now,
                    )
                    self.db.add(new_score)
                    await self.db.flush()  # Flush to get the ID for audit log
                    created_count += 1

                    # Log the creation
                    await self._log_score_change(
                        tenant_id=tenant_id,
                        exam_score_id=new_score.id,
                        old_score=None,
                        new_score=new_score_value,
                        old_is_absent=None,
                        new_is_absent=is_absent,
                        change_type="created",
                        changed_by=entered_by,
                        ip_address=ip_address,
                    )

            except Exception as e:
                failed_count += 1
                errors.append({
                    "student_id": str(score_entry.get("student_id")),
                    "error": str(e),
                })

        await self.db.commit()

        # Update exam subject status
        if created_count > 0 or updated_count > 0:
            exam_subject.status = ExamSubjectStatus.SCORES_ENTERED
            await self.db.commit()

        return {
            "created": created_count,
            "updated": updated_count,
            "failed": failed_count,
            "errors": errors,
        }

    async def calculate_grade(
        self,
        score: Decimal,
        max_score: Decimal,
        grading_scale_id: UUID,
    ) -> tuple[Optional[str], Optional[Decimal], Optional[str]]:
        """Calculate grade from score using grading scale."""
        percentage = (score / max_score) * 100

        grades_result = await self.db.execute(
            select(Grade)
            .where(Grade.grading_scale_id == grading_scale_id)
            .order_by(desc(Grade.min_score))
        )
        grades = grades_result.scalars().all()

        for grade in grades:
            if percentage >= grade.min_score:
                return (grade.grade, grade.grade_point, grade.remark)

        return (None, None, None)

    async def get_score_change_logs(
        self,
        tenant_id: UUID,
        exam_score_id: Optional[UUID] = None,
        exam_subject_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get score change history with user names."""
        from app.models.tenant import User

        # Build base query
        query = (
            select(
                ScoreChangeLog,
                User.first_name,
                User.last_name,
            )
            .outerjoin(User, ScoreChangeLog.changed_by == User.id)
            .where(ScoreChangeLog.tenant_id == tenant_id)
            .order_by(desc(ScoreChangeLog.changed_at))
        )

        count_query = (
            select(func.count())
            .select_from(ScoreChangeLog)
            .where(ScoreChangeLog.tenant_id == tenant_id)
        )

        # Filter by specific score
        if exam_score_id:
            query = query.where(ScoreChangeLog.exam_score_id == exam_score_id)
            count_query = count_query.where(ScoreChangeLog.exam_score_id == exam_score_id)

        # Filter by exam subject (all scores in that subject)
        if exam_subject_id:
            score_ids_subquery = select(ExamScore.id).where(
                ExamScore.exam_subject_id == exam_subject_id
            )
            query = query.where(ScoreChangeLog.exam_score_id.in_(score_ids_subquery))
            count_query = count_query.where(ScoreChangeLog.exam_score_id.in_(score_ids_subquery))

        # Get total count
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        logs = []
        for row in rows:
            log = row[0]
            first_name = row[1] or ""
            last_name = row[2] or ""
            changed_by_name = f"{first_name} {last_name}".strip() if first_name or last_name else None

            logs.append({
                "id": log.id,
                "exam_score_id": log.exam_score_id,
                "old_score": log.old_score,
                "new_score": log.new_score,
                "old_is_absent": log.old_is_absent,
                "new_is_absent": log.new_is_absent,
                "change_type": log.change_type,
                "change_reason": log.change_reason,
                "changed_by": log.changed_by,
                "changed_by_name": changed_by_name,
                "changed_at": log.changed_at,
                "ip_address": log.ip_address,
            })

        return logs, total

    async def submit_scores(
        self, exam_subject_id: UUID, tenant_id: UUID
    ) -> Optional[ExamSubject]:
        """Submit scores (lock for editing)."""
        result = await self.db.execute(
            select(ExamSubject).where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        exam_subject = result.scalar_one_or_none()
        if not exam_subject:
            return None

        exam_subject.status = ExamSubjectStatus.SUBMITTED
        exam_subject.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(exam_subject)
        return exam_subject

    async def publish_results(
        self, exam_subject_id: UUID, tenant_id: UUID
    ) -> Optional[ExamSubject]:
        """Publish results (make visible)."""
        result = await self.db.execute(
            select(ExamSubject).where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        exam_subject = result.scalar_one_or_none()
        if not exam_subject:
            return None

        exam_subject.status = ExamSubjectStatus.PUBLISHED
        exam_subject.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(exam_subject)
        return exam_subject

    async def update_score(
        self,
        score_id: UUID,
        tenant_id: UUID,
        score: Optional[Decimal] = None,
        is_absent: Optional[bool] = None,
        teacher_remark: Optional[str] = None,
    ) -> Optional[ExamScore]:
        """Update a single exam score."""
        result = await self.db.execute(
            select(ExamScore)
            .where(
                and_(
                    ExamScore.id == score_id,
                    ExamScore.tenant_id == tenant_id,
                )
            )
            .options(joinedload(ExamScore.exam_subject))
        )
        exam_score = result.scalar_one_or_none()
        if not exam_score:
            return None

        # Update fields if provided
        if is_absent is not None:
            exam_score.is_absent = is_absent
            if is_absent:
                exam_score.score = None
                exam_score.grade = None
                exam_score.grade_point = None
                exam_score.grade_remark = None

        if score is not None and not exam_score.is_absent:
            # Validate score is within range
            if score < 0:
                raise ExamServiceError(f"Score cannot be negative: {score}", code="invalid_score")
            if exam_score.exam_subject and score > exam_score.exam_subject.max_score:
                raise ExamServiceError(
                    f"Score {score} exceeds max score {exam_score.exam_subject.max_score}",
                    code="invalid_score",
                )
            exam_score.score = score
            # Recalculate grade if exam_subject has grading scale
            if exam_score.exam_subject and exam_score.exam_subject.grading_scale_id:
                grade, grade_point, grade_remark = await self.calculate_grade(
                    score=score,
                    max_score=exam_score.exam_subject.max_score,
                    grading_scale_id=exam_score.exam_subject.grading_scale_id,
                )
                exam_score.grade = grade
                exam_score.grade_point = grade_point
                exam_score.grade_remark = grade_remark

        if teacher_remark is not None:
            exam_score.teacher_remark = teacher_remark

        exam_score.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(exam_score)
        return exam_score

    async def get_score(self, score_id: UUID, tenant_id: UUID) -> Optional[ExamScore]:
        """Get a single exam score by ID."""
        result = await self.db.execute(
            select(ExamScore)
            .where(
                and_(
                    ExamScore.id == score_id,
                    ExamScore.tenant_id == tenant_id,
                )
            )
            .options(
                joinedload(ExamScore.exam_subject).joinedload(ExamSubject.subject),
                joinedload(ExamScore.student),
            )
        )
        return result.scalar_one_or_none()

    async def get_class_results(
        self,
        exam_id: UUID,
        class_id: UUID,
        tenant_id: UUID,
        section_id: Optional[UUID] = None,
    ) -> dict:
        """Get exam results for a class with rankings."""
        from app.models.academic import Class, ClassSection, Subject

        # Get exam info
        exam_result = await self.db.execute(
            select(Exam)
            .where(and_(Exam.id == exam_id, Exam.tenant_id == tenant_id))
            .options(joinedload(Exam.term))
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise ExamServiceError("Exam not found", code="not_found")

        # Get class info
        class_result = await self.db.execute(
            select(Class).where(Class.id == class_id)
        )
        class_ = class_result.scalar_one_or_none()
        if not class_:
            raise ExamServiceError("Class not found", code="not_found")

        # Get exam subjects for this class
        exam_subjects_result = await self.db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.class_id == class_id,
                )
            )
            .options(joinedload(ExamSubject.subject))
        )
        exam_subjects = exam_subjects_result.scalars().unique().all()

        if not exam_subjects:
            return {
                "exam_id": exam_id,
                "exam_name": exam.name,
                "class_id": class_id,
                "class_name": class_.name,
                "term_name": exam.term.name if exam.term else "",
                "students": [],
                "class_average": Decimal("0"),
                "highest_score": Decimal("0"),
                "lowest_score": Decimal("0"),
            }

        # Map of exam_subject_id -> subject info
        subject_map = {es.id: es for es in exam_subjects}

        # Get students in the class/section
        student_query = select(Student).where(
            and_(
                Student.class_id == class_id,
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
        )
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)
        student_query = student_query.options(joinedload(Student.section))

        students_result = await self.db.execute(student_query)
        students = students_result.scalars().unique().all()

        if not students:
            return {
                "exam_id": exam_id,
                "exam_name": exam.name,
                "class_id": class_id,
                "class_name": class_.name,
                "term_name": exam.term.name if exam.term else "",
                "students": [],
                "class_average": Decimal("0"),
                "highest_score": Decimal("0"),
                "lowest_score": Decimal("0"),
            }

        student_ids = [s.id for s in students]

        # Get all scores for these students in this exam
        scores_result = await self.db.execute(
            select(ExamScore).where(
                and_(
                    ExamScore.exam_subject_id.in_([es.id for es in exam_subjects]),
                    ExamScore.student_id.in_(student_ids),
                )
            )
        )
        all_scores = scores_result.scalars().all()

        # Build score map: student_id -> {exam_subject_id: score}
        score_map = {}
        for score in all_scores:
            if score.student_id not in score_map:
                score_map[score.student_id] = {}
            score_map[score.student_id][score.exam_subject_id] = score

        # Calculate results for each student
        student_results = []
        for student in students:
            student_scores = score_map.get(student.id, {})
            subject_results = []
            total_score = Decimal("0")
            subjects_with_score = 0

            for es in exam_subjects:
                score_obj = student_scores.get(es.id)
                subject_info = {
                    "subject_id": es.subject_id,
                    "subject_name": es.subject.name if es.subject else "Unknown",
                    "subject_code": es.subject.code if es.subject else None,
                    "total_score": score_obj.score if score_obj and score_obj.score else None,
                    "grade": score_obj.grade if score_obj else None,
                    "grade_point": score_obj.grade_point if score_obj else None,
                    "grade_remark": score_obj.grade_remark if score_obj else None,
                    "teacher_remark": score_obj.teacher_remark if score_obj else None,
                    "is_absent": score_obj.is_absent if score_obj else False,
                }
                subject_results.append(subject_info)

                if score_obj and score_obj.score is not None and not score_obj.is_absent:
                    total_score += score_obj.score
                    subjects_with_score += 1

            average_score = (
                total_score / subjects_with_score if subjects_with_score > 0 else Decimal("0")
            )

            student_results.append({
                "student_id": student.id,
                "student_name": f"{student.first_name} {student.last_name}",
                "student_id_number": student.student_id,
                "class_name": class_.name,
                "section_name": student.section.name if student.section else None,
                "subjects": subject_results,
                "total_score": total_score,
                "average_score": average_score.quantize(Decimal("0.01")),
                "subjects_count": len(exam_subjects),
                "class_position": 0,  # Will be calculated below
                "section_position": None,
                "class_size": len(students),
                "section_size": None,
            })

        # Sort by total_score descending and assign positions
        student_results.sort(key=lambda x: x["total_score"], reverse=True)

        # Assign class positions (handle ties)
        position = 1
        prev_score = None
        for i, result in enumerate(student_results):
            if prev_score is not None and result["total_score"] == prev_score:
                result["class_position"] = student_results[i - 1]["class_position"]
            else:
                result["class_position"] = position
            prev_score = result["total_score"]
            position += 1

        # Calculate section positions for all students who have sections
        # Group students by section
        sections = {}
        for result in student_results:
            section_name = result.get("section_name")
            if section_name:
                if section_name not in sections:
                    sections[section_name] = []
                sections[section_name].append(result)

        # Calculate section positions for each section
        for section_name, section_students in sections.items():
            section_students.sort(key=lambda x: x["total_score"], reverse=True)
            position = 1
            prev_score = None
            for i, result in enumerate(section_students):
                if prev_score is not None and result["total_score"] == prev_score:
                    result["section_position"] = section_students[i - 1]["section_position"]
                else:
                    result["section_position"] = position
                result["section_size"] = len(section_students)
                prev_score = result["total_score"]
                position += 1

        # Calculate statistics
        scores = [s["total_score"] for s in student_results if s["total_score"] > 0]
        class_average = sum(scores) / len(scores) if scores else Decimal("0")
        highest_score = max(scores) if scores else Decimal("0")
        lowest_score = min(scores) if scores else Decimal("0")

        return {
            "exam_id": exam_id,
            "exam_name": exam.name,
            "class_id": class_id,
            "class_name": class_.name,
            "term_name": exam.term.name if exam.term else "",
            "students": student_results,
            "class_average": class_average.quantize(Decimal("0.01")) if isinstance(class_average, Decimal) else Decimal(str(class_average)).quantize(Decimal("0.01")),
            "highest_score": highest_score,
            "lowest_score": lowest_score,
        }

    async def publish_exam_results(
        self, exam_id: UUID, tenant_id: UUID
    ) -> int:
        """Publish all results for an exam (update all exam subjects to published)."""
        result = await self.db.execute(
            select(ExamSubject).where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        exam_subjects = result.scalars().all()

        count = 0
        now = datetime.now(UTC)
        for es in exam_subjects:
            if es.status != ExamSubjectStatus.PUBLISHED:
                es.status = ExamSubjectStatus.PUBLISHED
                es.updated_at = now
                count += 1

        # Update exam status too
        exam_result = await self.db.execute(
            select(Exam).where(
                and_(Exam.id == exam_id, Exam.tenant_id == tenant_id)
            )
        )
        exam = exam_result.scalar_one_or_none()
        if exam:
            exam.status = ExamStatus.RESULTS_PUBLISHED
            exam.updated_at = now

        await self.db.commit()
        return count

    async def get_student_results(
        self,
        exam_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Get a single student's exam results across all subjects."""
        # Get exam with relationships
        exam_result = await self.db.execute(
            select(Exam)
            .where(and_(Exam.id == exam_id, Exam.tenant_id == tenant_id))
            .options(joinedload(Exam.term))
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise ExamServiceError(f"Exam not found: {exam_id}")

        # Get student
        student_result = await self.db.execute(
            select(Student)
            .where(and_(Student.id == student_id, Student.tenant_id == tenant_id))
            .options(
                joinedload(Student.class_),
                joinedload(Student.section),
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise ExamServiceError(f"Student not found: {student_id}")

        # Get all exam subjects for this student's class
        exam_subjects_result = await self.db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.tenant_id == tenant_id,
                    ExamSubject.class_id == student.class_id,
                )
            )
            .options(joinedload(ExamSubject.subject))
        )
        exam_subjects = exam_subjects_result.scalars().all()

        if not exam_subjects:
            raise ExamServiceError(f"No exam subjects found for student's class")

        # Get student's scores
        scores_result = await self.db.execute(
            select(ExamScore)
            .where(
                and_(
                    ExamScore.student_id == student_id,
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.exam_subject_id.in_([es.id for es in exam_subjects]),
                )
            )
        )
        scores = scores_result.scalars().all()
        score_map = {s.exam_subject_id: s for s in scores}

        # Build subject results
        subject_results = []
        total_score = Decimal("0")
        subjects_with_score = 0

        for es in exam_subjects:
            score_obj = score_map.get(es.id)
            subject_info = {
                "subject_id": es.subject_id,
                "subject_name": es.subject.name if es.subject else "Unknown",
                "subject_code": es.subject.code if es.subject else None,
                "total_score": score_obj.score if score_obj and score_obj.score else None,
                "grade": score_obj.grade if score_obj else None,
                "grade_point": score_obj.grade_point if score_obj else None,
                "grade_remark": score_obj.grade_remark if score_obj else None,
                "teacher_remark": score_obj.teacher_remark if score_obj else None,
                "is_absent": score_obj.is_absent if score_obj else False,
            }
            subject_results.append(subject_info)

            if score_obj and score_obj.score is not None and not score_obj.is_absent:
                total_score += score_obj.score
                subjects_with_score += 1

        average_score = (
            total_score / subjects_with_score if subjects_with_score > 0 else Decimal("0")
        )

        # Get class size and student's position (need to query all students in class)
        class_results = await self.get_class_results(
            exam_id=exam_id,
            class_id=student.class_id,
            tenant_id=tenant_id,
        )

        # Find this student in class results
        class_position = 0
        section_position = None
        class_size = len(class_results["students"])
        section_size = None

        for s in class_results["students"]:
            if s["student_id"] == student_id:
                class_position = s["class_position"]
                section_position = s.get("section_position")
                section_size = s.get("section_size")
                break

        return {
            "exam_id": exam_id,
            "exam_name": exam.name,
            "class_id": student.class_id,
            "class_name": student.class_.name if student.class_ else "",
            "term_name": exam.term.name if exam.term else "",
            "students": [{
                "student_id": student.id,
                "student_name": f"{student.first_name} {student.last_name}",
                "student_id_number": student.student_id,
                "class_name": student.class_.name if student.class_ else "",
                "section_name": student.section.name if student.section else None,
                "subjects": subject_results,
                "total_score": total_score,
                "average_score": average_score.quantize(Decimal("0.01")),
                "subjects_count": len(exam_subjects),
                "class_position": class_position,
                "section_position": section_position,
                "class_size": class_size,
                "section_size": section_size,
            }],
            "class_average": class_results["class_average"],
            "highest_score": class_results["highest_score"],
            "lowest_score": class_results["lowest_score"],
        }


class CAService:
    """Service for managing continuous assessments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ca(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        student_id: UUID,
        assessment_type: str,
        title: str,
        assessment_date: date,
        max_score: Decimal = Decimal("10.00"),
        score: Optional[Decimal] = None,
        entered_by: Optional[UUID] = None,
    ) -> ContinuousAssessment:
        """Create a continuous assessment entry."""
        ca = ContinuousAssessment(
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            class_id=class_id,
            subject_id=subject_id,
            student_id=student_id,
            assessment_type=AssessmentType(assessment_type),
            title=title,
            assessment_date=assessment_date,
            max_score=max_score,
            score=score,
            entered_by=entered_by,
        )
        self.db.add(ca)
        await self.db.commit()
        await self.db.refresh(ca)
        return ca

    async def bulk_create_ca(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        assessment_type: str,
        title: str,
        assessment_date: date,
        max_score: Decimal,
        scores: list[dict],
        entered_by: Optional[UUID] = None,
    ) -> dict:
        """Bulk create CA entries for multiple students."""
        success_count = 0
        failed_count = 0
        errors = []

        for score_entry in scores:
            try:
                await self.create_ca(
                    tenant_id=tenant_id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    class_id=class_id,
                    subject_id=subject_id,
                    student_id=score_entry["student_id"],
                    assessment_type=assessment_type,
                    title=title,
                    assessment_date=assessment_date,
                    max_score=max_score,
                    score=score_entry.get("score"),
                    entered_by=entered_by,
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "student_id": str(score_entry.get("student_id")),
                    "error": str(e),
                })

        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
        }

    async def get_ca(self, ca_id: UUID) -> Optional[ContinuousAssessment]:
        """Get CA entry by ID."""
        result = await self.db.execute(
            select(ContinuousAssessment)
            .where(ContinuousAssessment.id == ca_id)
            .options(
                joinedload(ContinuousAssessment.student),
                joinedload(ContinuousAssessment.subject),
            )
        )
        return result.scalar_one_or_none()

    async def list_ca(
        self,
        tenant_id: UUID,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        subject_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        assessment_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[ContinuousAssessment], int]:
        """List CA entries with filters."""
        query = select(ContinuousAssessment).where(
            ContinuousAssessment.tenant_id == tenant_id
        )

        if term_id:
            query = query.where(ContinuousAssessment.term_id == term_id)
        if class_id:
            query = query.where(ContinuousAssessment.class_id == class_id)
        if subject_id:
            query = query.where(ContinuousAssessment.subject_id == subject_id)
        if student_id:
            query = query.where(ContinuousAssessment.student_id == student_id)
        if assessment_type:
            query = query.where(
                ContinuousAssessment.assessment_type == AssessmentType(assessment_type)
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(ContinuousAssessment.student),
            joinedload(ContinuousAssessment.subject),
            joinedload(ContinuousAssessment.class_),
        ).order_by(desc(ContinuousAssessment.assessment_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_ca(
        self, ca_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[ContinuousAssessment]:
        """Update CA entry."""
        ca = await self.get_ca(ca_id)
        if not ca or ca.tenant_id != tenant_id:
            return None

        if "assessment_type" in kwargs and kwargs["assessment_type"]:
            kwargs["assessment_type"] = AssessmentType(kwargs["assessment_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(ca, key):
                setattr(ca, key, value)

        ca.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(ca)
        return ca

    async def delete_ca(self, ca_id: UUID, tenant_id: UUID) -> bool:
        """Delete CA entry."""
        ca = await self.get_ca(ca_id)
        if not ca or ca.tenant_id != tenant_id:
            return False

        await self.db.delete(ca)
        await self.db.commit()
        return True

    async def get_ca_summary(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
    ) -> list[dict]:
        """Get CA summary totals per student for a subject."""
        # Get subject info
        from app.models.academic import Subject
        subject_result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        subject = subject_result.scalar_one_or_none()
        subject_name = subject.name if subject else "Unknown"

        # Get all CA entries
        result = await self.db.execute(
            select(ContinuousAssessment)
            .where(
                and_(
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.term_id == term_id,
                    ContinuousAssessment.class_id == class_id,
                    ContinuousAssessment.subject_id == subject_id,
                )
            )
            .options(joinedload(ContinuousAssessment.student))
        )
        ca_entries = result.scalars().unique().all()

        # Group by student
        student_totals = {}
        for ca in ca_entries:
            sid = ca.student_id
            if sid not in student_totals:
                student_totals[sid] = {
                    "student_id": sid,
                    "student_name": f"{ca.student.first_name} {ca.student.last_name}",
                    "total_max_score": Decimal("0"),
                    "total_score": Decimal("0"),
                    "count": 0,
                }
            student_totals[sid]["total_max_score"] += ca.max_score
            if ca.score is not None:
                student_totals[sid]["total_score"] += ca.score
            student_totals[sid]["count"] += 1

        # Calculate averages
        summaries = []
        for data in student_totals.values():
            avg = Decimal("0")
            if data["total_max_score"] > 0:
                avg = (data["total_score"] / data["total_max_score"]) * 100
            summaries.append({
                "student_id": data["student_id"],
                "student_name": data["student_name"],
                "subject_id": subject_id,
                "subject_name": subject_name,
                "total_assessments": data["count"],
                "total_max_score": data["total_max_score"],
                "total_score": data["total_score"],
                "average_percentage": avg.quantize(Decimal("0.01")),
            })

        return summaries


class TermReportService:
    """Service for generating and managing term reports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_student_term_scores(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
        class_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> tuple[Decimal | None, Decimal | None, int]:
        """
        Calculate a student's total score, average, and subject count for a term.

        Uses weighted scoring based on assessment weights:
        - CA (class work + homework) + midterm + end_term

        Returns (total_score, average_score, subjects_count)
        """
        from app.models.academic import AssessmentWeight

        # Get assessment weights for this academic year
        weights_result = await self.db.execute(
            select(AssessmentWeight).where(
                and_(
                    AssessmentWeight.tenant_id == tenant_id,
                    or_(
                        AssessmentWeight.academic_year_id == academic_year_id,
                        AssessmentWeight.academic_year_id.is_(None),
                    ),
                )
            )
            .order_by(AssessmentWeight.academic_year_id.desc())
        )
        weights = weights_result.scalar_one_or_none()

        # Default weights if not configured
        class_work_weight = Decimal("20") if not weights else weights.class_work_weight
        homework_weight = Decimal("10") if not weights else weights.homework_weight
        midterm_weight = Decimal("20") if not weights else weights.midterm_weight
        end_term_weight = Decimal("50") if not weights else weights.end_term_weight

        # CA weight is combined class work + homework
        ca_weight = class_work_weight + homework_weight

        # Get term info to get academic_year_id if not provided
        if not academic_year_id:
            term_result = await self.db.execute(
                select(Term.academic_year_id).where(Term.id == term_id)
            )
            term_row = term_result.scalar_one_or_none()
            if term_row:
                academic_year_id = term_row

        # Get all exams for the term
        exams_result = await self.db.execute(
            select(Exam.id, Exam.exam_type).where(
                and_(
                    Exam.tenant_id == tenant_id,
                    Exam.term_id == term_id,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        exams = exams_result.all()

        if not exams:
            return None, None, 0

        # Categorize exam IDs by type
        midterm_exam_ids = [e[0] for e in exams if e[1] == ExamType.MIDTERM]
        end_term_exam_ids = [e[0] for e in exams if e[1] == ExamType.END_TERM]
        all_exam_ids = [e[0] for e in exams]

        # Get all subjects assigned to exams for this class
        subjects_result = await self.db.execute(
            select(ExamSubject.subject_id).where(
                and_(
                    ExamSubject.exam_id.in_(all_exam_ids),
                    ExamSubject.class_id == class_id,
                )
            ).distinct()
        )
        subject_ids = [s[0] for s in subjects_result.all()]

        if not subject_ids:
            return None, None, 0

        # Calculate scores per subject
        subject_scores: dict[UUID, dict] = {}

        for subject_id in subject_ids:
            subject_scores[subject_id] = {
                "ca_score": Decimal("0"),
                "ca_max": Decimal("0"),
                "midterm_score": Decimal("0"),
                "midterm_max": Decimal("0"),
                "end_term_score": Decimal("0"),
                "end_term_max": Decimal("0"),
            }

            # Get CA scores for this subject
            ca_result = await self.db.execute(
                select(
                    func.sum(ContinuousAssessment.score),
                    func.sum(ContinuousAssessment.max_score),
                ).where(
                    and_(
                        ContinuousAssessment.tenant_id == tenant_id,
                        ContinuousAssessment.term_id == term_id,
                        ContinuousAssessment.student_id == student_id,
                        ContinuousAssessment.subject_id == subject_id,
                        ContinuousAssessment.class_id == class_id,
                        ContinuousAssessment.score.isnot(None),
                    )
                )
            )
            ca_row = ca_result.one()
            if ca_row[0] is not None and ca_row[1] is not None:
                subject_scores[subject_id]["ca_score"] = ca_row[0]
                subject_scores[subject_id]["ca_max"] = ca_row[1]

            # Get midterm exam scores
            if midterm_exam_ids:
                midterm_result = await self.db.execute(
                    select(ExamScore.score, ExamSubject.max_score)
                    .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                    .where(
                        and_(
                            ExamScore.tenant_id == tenant_id,
                            ExamScore.student_id == student_id,
                            ExamSubject.exam_id.in_(midterm_exam_ids),
                            ExamSubject.subject_id == subject_id,
                            ExamSubject.class_id == class_id,
                            ExamScore.is_absent == False,
                            ExamScore.score.isnot(None),
                        )
                    )
                )
                for score, max_score in midterm_result.all():
                    if score is not None:
                        subject_scores[subject_id]["midterm_score"] += score
                        subject_scores[subject_id]["midterm_max"] += max_score

            # Get end term exam scores
            if end_term_exam_ids:
                end_term_result = await self.db.execute(
                    select(ExamScore.score, ExamSubject.max_score)
                    .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                    .where(
                        and_(
                            ExamScore.tenant_id == tenant_id,
                            ExamScore.student_id == student_id,
                            ExamSubject.exam_id.in_(end_term_exam_ids),
                            ExamSubject.subject_id == subject_id,
                            ExamSubject.class_id == class_id,
                            ExamScore.is_absent == False,
                            ExamScore.score.isnot(None),
                        )
                    )
                )
                for score, max_score in end_term_result.all():
                    if score is not None:
                        subject_scores[subject_id]["end_term_score"] += score
                        subject_scores[subject_id]["end_term_max"] += max_score

        # Calculate weighted total per subject
        total_score = Decimal("0")
        subjects_with_scores = 0

        for subject_id, scores in subject_scores.items():
            subject_total = Decimal("0")
            has_scores = False

            # CA component
            if scores["ca_max"] > 0:
                ca_pct = (scores["ca_score"] / scores["ca_max"]) * 100
                subject_total += (ca_pct * ca_weight) / 100
                has_scores = True

            # Midterm component
            if scores["midterm_max"] > 0:
                mid_pct = (scores["midterm_score"] / scores["midterm_max"]) * 100
                subject_total += (mid_pct * midterm_weight) / 100
                has_scores = True

            # End term component
            if scores["end_term_max"] > 0:
                end_pct = (scores["end_term_score"] / scores["end_term_max"]) * 100
                subject_total += (end_pct * end_term_weight) / 100
                has_scores = True

            if has_scores:
                total_score += subject_total
                subjects_with_scores += 1

        if subjects_with_scores == 0:
            return None, None, 0

        average_score = total_score / subjects_with_scores

        return total_score, average_score, subjects_with_scores

    async def calculate_term_school_days(
        self,
        tenant_id: UUID,
        term_id: UUID,
    ) -> int:
        """
        Calculate the total number of school days in a term based on the calendar.

        This uses:
        - Term start and end dates
        - Excludes weekends (Saturday and Sunday)
        - Excludes holidays and vacations from the SchoolHoliday table

        Returns the total number of school days.
        """
        # Get the term to find start and end dates
        term_result = await self.db.execute(
            select(Term).where(Term.id == term_id)
        )
        term = term_result.scalar_one_or_none()

        if not term:
            return 0

        start_date = term.start_date
        end_date = term.end_date

        # Get holidays/vacations within the term period
        # Only exclude 'holiday' and 'vacation' types (not 'exam' or 'event')
        holidays_result = await self.db.execute(
            select(SchoolHoliday.date)
            .where(
                and_(
                    SchoolHoliday.tenant_id == tenant_id,
                    SchoolHoliday.date >= start_date,
                    SchoolHoliday.date <= end_date,
                    SchoolHoliday.holiday_type.in_(["holiday", "vacation"]),
                )
            )
        )
        holiday_dates = set(row[0] for row in holidays_result.all())

        # Count weekdays (Monday=0 to Friday=4) excluding holidays
        total_school_days = 0
        current_date = start_date

        while current_date <= end_date:
            # Check if it's a weekday (Monday=0 to Friday=4)
            if current_date.weekday() < 5:  # Not Saturday (5) or Sunday (6)
                # Check if it's not a holiday
                if current_date not in holiday_dates:
                    total_school_days += 1
            current_date += timedelta(days=1)

        return total_school_days

    async def calculate_student_attendance(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
    ) -> tuple[int | None, int | None, int | None, Decimal | None]:
        """
        Calculate a student's attendance statistics for a term.

        Uses the school calendar to determine total school days, rather than
        just counting attendance records.

        Returns (days_present, days_absent, total_school_days, attendance_percentage)
        """
        # Get total school days from calendar
        total_school_days = await self.calculate_term_school_days(tenant_id, term_id)

        if total_school_days == 0:
            return None, None, None, None

        # Count attendance by status
        attendance_result = await self.db.execute(
            select(
                StudentAttendance.status,
                func.count(StudentAttendance.id),
            )
            .where(
                and_(
                    StudentAttendance.tenant_id == tenant_id,
                    StudentAttendance.term_id == term_id,
                    StudentAttendance.student_id == student_id,
                )
            )
            .group_by(StudentAttendance.status)
        )
        attendance_counts = dict(attendance_result.all())

        # Present includes PRESENT and LATE
        days_present = (
            attendance_counts.get(AttendanceStatus.PRESENT, 0) +
            attendance_counts.get(AttendanceStatus.LATE, 0)
        )

        # Absent includes ABSENT, EXCUSED, SICK
        # Note: We count all types of absence separately for potential future use
        days_unexcused_absent = attendance_counts.get(AttendanceStatus.ABSENT, 0)
        days_excused = (
            attendance_counts.get(AttendanceStatus.EXCUSED, 0) +
            attendance_counts.get(AttendanceStatus.SICK, 0)
        )
        days_absent = days_unexcused_absent + days_excused

        # Calculate attendance percentage based on calendar days
        # Note: Days not recorded count as absent (total - present = absent)
        if total_school_days > 0:
            attendance_percentage = Decimal(str(
                (days_present / total_school_days) * 100
            )).quantize(Decimal("0.01"))
        else:
            attendance_percentage = None

        return days_present, days_absent, total_school_days, attendance_percentage

    async def _batch_get_all_scores(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_ids: list[UUID],
        student_ids: list[UUID],
        ca_exam_ids: list[UUID],
        end_term_exam_ids: list[UUID],
        section_id: Optional[UUID] = None,
    ) -> dict:
        """
        Batch fetch all scores for multiple students and subjects in a single set of queries.

        Returns a nested dict structure:
        {
            student_id: {
                subject_id: {
                    "ca_score": Decimal,
                    "ca_max": Decimal,
                    "ca_exam_score": Decimal,
                    "ca_exam_max": Decimal,
                    "end_term_score": Decimal,
                    "end_term_max": Decimal,
                }
            }
        }

        This replaces N+1 queries with just 3 queries total.
        """
        # Initialize result structure
        result: dict[UUID, dict[UUID, dict]] = {}
        for student_id in student_ids:
            result[student_id] = {}
            for subject_id in subject_ids:
                result[student_id][subject_id] = {
                    "ca_score": Decimal("0"),
                    "ca_max": Decimal("0"),
                    "ca_exam_score": Decimal("0"),
                    "ca_exam_max": Decimal("0"),
                    "end_term_score": Decimal("0"),
                    "end_term_max": Decimal("0"),
                }

        # Query 1: Batch get all CA scores from ContinuousAssessment table
        ca_result = await self.db.execute(
            select(
                ContinuousAssessment.student_id,
                ContinuousAssessment.subject_id,
                func.sum(ContinuousAssessment.score).label("total_score"),
                func.sum(ContinuousAssessment.max_score).label("total_max"),
            ).where(
                and_(
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.term_id == term_id,
                    ContinuousAssessment.student_id.in_(student_ids),
                    ContinuousAssessment.subject_id.in_(subject_ids),
                    ContinuousAssessment.class_id == class_id,
                    ContinuousAssessment.score.isnot(None),
                )
            ).group_by(
                ContinuousAssessment.student_id,
                ContinuousAssessment.subject_id,
            )
        )
        for row in ca_result.all():
            student_id, subject_id, total_score, total_max = row
            if student_id in result and subject_id in result[student_id]:
                result[student_id][subject_id]["ca_score"] = total_score or Decimal("0")
                result[student_id][subject_id]["ca_max"] = total_max or Decimal("0")

        # Query 2: Batch get all CA-type exam scores
        if ca_exam_ids:
            ca_exam_result = await self.db.execute(
                select(
                    ExamScore.student_id,
                    ExamSubject.subject_id,
                    func.sum(ExamScore.score).label("total_score"),
                    func.sum(ExamSubject.max_score).label("total_max"),
                )
                .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                .where(
                    and_(
                        ExamScore.tenant_id == tenant_id,
                        ExamScore.student_id.in_(student_ids),
                        ExamSubject.exam_id.in_(ca_exam_ids),
                        ExamSubject.subject_id.in_(subject_ids),
                        ExamSubject.class_id == class_id,
                        or_(
                            ExamSubject.section_id.is_(None),
                            ExamSubject.section_id == section_id,
                        ),
                        ExamScore.is_absent == False,
                        ExamScore.score.isnot(None),
                    )
                ).group_by(
                    ExamScore.student_id,
                    ExamSubject.subject_id,
                )
            )
            for row in ca_exam_result.all():
                student_id, subject_id, total_score, total_max = row
                if student_id in result and subject_id in result[student_id]:
                    result[student_id][subject_id]["ca_exam_score"] = total_score or Decimal("0")
                    result[student_id][subject_id]["ca_exam_max"] = total_max or Decimal("0")

        # Query 3: Batch get all end-term exam scores
        if end_term_exam_ids:
            end_term_result = await self.db.execute(
                select(
                    ExamScore.student_id,
                    ExamSubject.subject_id,
                    func.sum(ExamScore.score).label("total_score"),
                    func.sum(ExamSubject.max_score).label("total_max"),
                )
                .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                .where(
                    and_(
                        ExamScore.tenant_id == tenant_id,
                        ExamScore.student_id.in_(student_ids),
                        ExamSubject.exam_id.in_(end_term_exam_ids),
                        ExamSubject.subject_id.in_(subject_ids),
                        ExamSubject.class_id == class_id,
                        or_(
                            ExamSubject.section_id.is_(None),
                            ExamSubject.section_id == section_id,
                        ),
                        ExamScore.is_absent == False,
                        ExamScore.score.isnot(None),
                    )
                ).group_by(
                    ExamScore.student_id,
                    ExamSubject.subject_id,
                )
            )
            for row in end_term_result.all():
                student_id, subject_id, total_score, total_max = row
                if student_id in result and subject_id in result[student_id]:
                    result[student_id][subject_id]["end_term_score"] = total_score or Decimal("0")
                    result[student_id][subject_id]["end_term_max"] = total_max or Decimal("0")

        return result

    def _calculate_total_score_from_scores(
        self,
        scores: dict,
        ca_total_weight: Decimal,
        exam_total_weight: Decimal,
    ) -> tuple[Decimal, bool]:
        """
        Calculate total score from score components.
        Returns (total_score, has_scores).
        """
        total_ca_score = scores["ca_score"] + scores["ca_exam_score"]
        total_ca_max = scores["ca_max"] + scores["ca_exam_max"]

        class_score = Decimal("0")
        if total_ca_max > 0:
            class_score = (total_ca_score / total_ca_max) * ca_total_weight

        exams_score = Decimal("0")
        if scores["end_term_max"] > 0:
            exams_score = (scores["end_term_score"] / scores["end_term_max"]) * exam_total_weight

        total_score = class_score + exams_score
        has_scores = total_ca_max > 0 or scores["end_term_max"] > 0

        return total_score, has_scores

    async def _batch_calculate_subject_positions(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_ids: list[UUID],
        ca_exam_ids: list[UUID],
        end_term_exam_ids: list[UUID],
        ca_total_weight: Decimal,
        exam_total_weight: Decimal,
        section_id: Optional[UUID] = None,
    ) -> dict[UUID, dict[UUID, int]]:
        """
        Batch calculate subject position rankings for all subjects in a class/section.

        Returns a nested dict: {subject_id: {student_id: position}}
        Uses just 4 queries total instead of N*M queries.
        """
        from app.models.student import Student

        # Get all students in the class/section
        student_query = select(Student.id).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
        )
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)

        students_result = await self.db.execute(student_query)
        student_ids = [row[0] for row in students_result.all()]

        if not student_ids or not subject_ids:
            return {}

        # Batch fetch all scores
        all_scores = await self._batch_get_all_scores(
            tenant_id=tenant_id,
            term_id=term_id,
            class_id=class_id,
            subject_ids=subject_ids,
            student_ids=student_ids,
            ca_exam_ids=ca_exam_ids,
            end_term_exam_ids=end_term_exam_ids,
            section_id=section_id,
        )

        # Calculate positions for each subject
        positions: dict[UUID, dict[UUID, int]] = {}

        for subject_id in subject_ids:
            # Collect (student_id, total_score) pairs for this subject
            student_scores: list[tuple[UUID, Decimal]] = []

            for student_id in student_ids:
                scores = all_scores.get(student_id, {}).get(subject_id, {})
                if scores:
                    total_score, has_scores = self._calculate_total_score_from_scores(
                        scores, ca_total_weight, exam_total_weight
                    )
                    if has_scores:
                        student_scores.append((student_id, total_score))

            # Sort by total_score descending
            student_scores.sort(key=lambda x: x[1], reverse=True)

            # Assign positions (handling ties with same position)
            positions[subject_id] = {}
            current_position = 1
            prev_score = None

            for idx, (student_id, score) in enumerate(student_scores):
                if prev_score is not None and score < prev_score:
                    current_position = idx + 1
                positions[subject_id][student_id] = current_position
                prev_score = score

        return positions

    async def _calculate_subject_positions(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        section_id: Optional[UUID] = None,
        ca_exam_ids: list[UUID] = None,
        end_term_exam_ids: list[UUID] = None,
        ca_total_weight: Decimal = Decimal("50"),
        exam_total_weight: Decimal = Decimal("50"),
    ) -> dict[UUID, int]:
        """
        Calculate subject position rankings for all students in a class/section.

        Returns a dict mapping student_id -> position for the given subject.
        Position is based on total_score (class_score + exams_score).
        Weights are configurable (default 50/50).
        """
        # Get all students in the class/section
        student_query = select(Student).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
        )
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)

        students_result = await self.db.execute(student_query)
        students = students_result.scalars().all()

        if not students:
            return {}

        # Calculate total_score for each student in this subject
        student_scores: list[tuple[UUID, Decimal]] = []

        for student in students:
            ca_score = Decimal("0")
            ca_max = Decimal("0")
            ca_exam_score = Decimal("0")
            ca_exam_max = Decimal("0")
            end_term_score = Decimal("0")
            end_term_max = Decimal("0")

            # Get CA scores from ContinuousAssessment table
            ca_result = await self.db.execute(
                select(
                    func.sum(ContinuousAssessment.score),
                    func.sum(ContinuousAssessment.max_score),
                ).where(
                    and_(
                        ContinuousAssessment.tenant_id == tenant_id,
                        ContinuousAssessment.term_id == term_id,
                        ContinuousAssessment.student_id == student.id,
                        ContinuousAssessment.subject_id == subject_id,
                        ContinuousAssessment.class_id == class_id,
                        ContinuousAssessment.score.isnot(None),
                    )
                )
            )
            ca_row = ca_result.one()
            if ca_row[0] is not None and ca_row[1] is not None:
                ca_score = ca_row[0]
                ca_max = ca_row[1]

            # Get CA-type exam scores
            if ca_exam_ids:
                ca_exam_result = await self.db.execute(
                    select(ExamScore.score, ExamSubject.max_score)
                    .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                    .where(
                        and_(
                            ExamScore.tenant_id == tenant_id,
                            ExamScore.student_id == student.id,
                            ExamSubject.exam_id.in_(ca_exam_ids),
                            ExamSubject.subject_id == subject_id,
                            ExamSubject.class_id == class_id,
                            or_(
                                ExamSubject.section_id.is_(None),
                                ExamSubject.section_id == student.section_id,
                            ),
                            ExamScore.is_absent == False,
                            ExamScore.score.isnot(None),
                        )
                    )
                )
                for score, max_score in ca_exam_result.all():
                    if score is not None:
                        ca_exam_score += score
                        ca_exam_max += max_score

            # Get end term exam scores
            if end_term_exam_ids:
                end_term_result = await self.db.execute(
                    select(ExamScore.score, ExamSubject.max_score)
                    .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                    .where(
                        and_(
                            ExamScore.tenant_id == tenant_id,
                            ExamScore.student_id == student.id,
                            ExamSubject.exam_id.in_(end_term_exam_ids),
                            ExamSubject.subject_id == subject_id,
                            ExamSubject.class_id == class_id,
                            or_(
                                ExamSubject.section_id.is_(None),
                                ExamSubject.section_id == student.section_id,
                            ),
                            ExamScore.is_absent == False,
                            ExamScore.score.isnot(None),
                        )
                    )
                )
                for score, max_score in end_term_result.all():
                    if score is not None:
                        end_term_score += score
                        end_term_max += max_score

            # Calculate total score using configurable weights
            total_ca_score = ca_score + ca_exam_score
            total_ca_max = ca_max + ca_exam_max

            class_score = Decimal("0")
            if total_ca_max > 0:
                class_score = (total_ca_score / total_ca_max) * ca_total_weight

            exams_score = Decimal("0")
            if end_term_max > 0:
                exams_score = (end_term_score / end_term_max) * exam_total_weight

            total_score = class_score + exams_score
            has_scores = total_ca_max > 0 or end_term_max > 0

            if has_scores:
                student_scores.append((student.id, total_score))

        if not student_scores:
            return {}

        # Sort by total_score descending
        student_scores.sort(key=lambda x: x[1], reverse=True)

        # Assign positions (handle ties - students with same score get same position)
        positions: dict[UUID, int] = {}
        prev_score = None
        prev_position = 0

        for i, (student_id, score) in enumerate(student_scores):
            if prev_score is not None and score == prev_score:
                # Same score as previous student, same position
                positions[student_id] = prev_position
            else:
                # New position
                positions[student_id] = i + 1
                prev_position = i + 1
            prev_score = score

        return positions

    async def get_student_subject_results(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
        class_id: UUID,
        academic_year_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
    ) -> list[dict]:
        """
        Get detailed subject results for a student in a term.

        Returns a list of subject results with CA, midterm, end_term breakdown.
        Includes subject_position ranking at the class/section level.
        """
        from app.models.academic import AssessmentWeight, Subject, GradingScale, Grade

        # Get the student's section_id if not provided
        if section_id is None:
            from app.models.student import Student
            student_result = await self.db.execute(
                select(Student.section_id).where(Student.id == student_id)
            )
            section_id = student_result.scalar_one_or_none()

        # Get assessment weights
        weights_result = await self.db.execute(
            select(AssessmentWeight).where(
                and_(
                    AssessmentWeight.tenant_id == tenant_id,
                    or_(
                        AssessmentWeight.academic_year_id == academic_year_id,
                        AssessmentWeight.academic_year_id.is_(None),
                    ),
                )
            )
            .order_by(AssessmentWeight.academic_year_id.desc())
        )
        weights = weights_result.scalar_one_or_none()

        class_work_weight = Decimal("20") if not weights else weights.class_work_weight
        homework_weight = Decimal("10") if not weights else weights.homework_weight
        midterm_weight = Decimal("20") if not weights else weights.midterm_weight
        end_term_weight = Decimal("50") if not weights else weights.end_term_weight
        ca_weight = class_work_weight + homework_weight

        # Report card weights (configurable CA vs Exam split)
        ca_total_weight = Decimal("50") if not weights else weights.ca_total_weight
        exam_total_weight = Decimal("50") if not weights else weights.exam_total_weight

        # Get all exams for the term
        exams_result = await self.db.execute(
            select(Exam.id, Exam.exam_type).where(
                and_(
                    Exam.tenant_id == tenant_id,
                    Exam.term_id == term_id,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        exams = exams_result.all()

        if not exams:
            return []

        # Categorize exams by type
        # Ghana's assessment structure:
        # - Class Score (50%): All CA components (continuous assessments + quiz/midterm/mock/practical/project exams)
        # - Exams Score (50%): End of term examination only

        # CA-type exams (contribute to Class Score)
        ca_exam_ids = [e[0] for e in exams if e[1] in (ExamType.QUIZ, ExamType.MIDTERM, ExamType.MOCK, ExamType.PRACTICAL, ExamType.PROJECT)]
        # End of term exam only (contributes to Exams Score)
        end_term_exam_ids = [e[0] for e in exams if e[1] == ExamType.END_TERM]
        all_exam_ids = [e[0] for e in exams]

        # Get all subjects with exam assignments for this class (include section-specific and class-wide)
        subjects_result = await self.db.execute(
            select(Subject)
            .join(ExamSubject, ExamSubject.subject_id == Subject.id)
            .where(
                and_(
                    ExamSubject.exam_id.in_(all_exam_ids),
                    ExamSubject.class_id == class_id,
                    # Match either class-wide (NULL section) or student's specific section
                    or_(
                        ExamSubject.section_id.is_(None),
                        ExamSubject.section_id == section_id,
                    ),
                )
            )
            .distinct()
        )
        subjects = subjects_result.scalars().all()

        if not subjects:
            return []

        # Get default grading scale for grades
        grading_scale_result = await self.db.execute(
            select(GradingScale).where(
                and_(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.is_default == True,
                )
            )
        )
        grading_scale = grading_scale_result.scalar_one_or_none()

        grades = []
        if grading_scale:
            grades_result = await self.db.execute(
                select(Grade)
                .where(Grade.grading_scale_id == grading_scale.id)
                .order_by(Grade.min_score.desc())
            )
            grades = grades_result.scalars().all()

        # OPTIMIZED: Use batch queries instead of N+1 queries per subject
        # This reduces queries from (subjects × 4) to just 4 queries total

        subject_ids = [s.id for s in subjects]

        # Batch fetch all scores for this student across all subjects (3 queries)
        all_scores = await self._batch_get_all_scores(
            tenant_id=tenant_id,
            term_id=term_id,
            class_id=class_id,
            subject_ids=subject_ids,
            student_ids=[student_id],
            ca_exam_ids=ca_exam_ids,
            end_term_exam_ids=end_term_exam_ids,
            section_id=section_id,
        )

        # Batch calculate all subject positions (1 query + in-memory calculation)
        all_positions = await self._batch_calculate_subject_positions(
            tenant_id=tenant_id,
            term_id=term_id,
            class_id=class_id,
            subject_ids=subject_ids,
            ca_exam_ids=ca_exam_ids,
            end_term_exam_ids=end_term_exam_ids,
            ca_total_weight=ca_total_weight,
            exam_total_weight=exam_total_weight,
            section_id=section_id,
        )

        subject_results = []

        for subject in subjects:
            # Get pre-fetched scores for this subject
            scores = all_scores.get(student_id, {}).get(subject.id, {
                "ca_score": Decimal("0"),
                "ca_max": Decimal("0"),
                "ca_exam_score": Decimal("0"),
                "ca_exam_max": Decimal("0"),
                "end_term_score": Decimal("0"),
                "end_term_max": Decimal("0"),
            })

            # Assessment Structure: Class Score (CA) + Exams Score (End Term) = Total (100%)
            # Weights are configurable (default 50/50)

            # Combine all CA components (from ContinuousAssessment table + CA-type exams)
            total_ca_score = scores["ca_score"] + scores["ca_exam_score"]
            total_ca_max = scores["ca_max"] + scores["ca_exam_max"]

            # Calculate Class Score (out of configurable weight, default 50)
            class_score = Decimal("0")
            if total_ca_max > 0:
                class_score = (total_ca_score / total_ca_max) * ca_total_weight

            # Calculate Exams Score (out of configurable weight, default 50)
            exams_score = Decimal("0")
            if scores["end_term_max"] > 0:
                exams_score = (scores["end_term_score"] / scores["end_term_max"]) * exam_total_weight

            # Calculate Total Score (out of 100)
            total_score = class_score + exams_score
            has_scores = total_ca_max > 0 or scores["end_term_max"] > 0

            # Get grade for this score
            grade = None
            grade_remark = None
            if has_scores and grades:
                for g in grades:
                    if total_score >= g.min_score:
                        grade = g.grade
                        grade_remark = g.remark
                        break

            # Get pre-calculated subject position
            subject_position = None
            if has_scores:
                subject_position = all_positions.get(subject.id, {}).get(student_id)

            subject_results.append({
                "subject_id": str(subject.id),
                "subject_name": subject.name,
                "subject_code": subject.code,
                # Raw scores for reference
                "ca_score": float(total_ca_score) if total_ca_max > 0 else None,
                "ca_max": float(total_ca_max) if total_ca_max > 0 else None,
                "end_term_score": float(scores["end_term_score"]) if scores["end_term_max"] > 0 else None,
                "end_term_max": float(scores["end_term_max"]) if scores["end_term_max"] > 0 else None,
                # Normalized scores for report card
                "class_score": float(class_score.quantize(Decimal("0.01"))) if total_ca_max > 0 else None,
                "exams_score": float(exams_score.quantize(Decimal("0.01"))) if scores["end_term_max"] > 0 else None,
                "total_score": float(total_score.quantize(Decimal("0.01"))) if has_scores else None,
                "grade": grade,
                "grade_remark": grade_remark,
                "subject_position": subject_position,
            })

        return subject_results

    async def generate_term_reports(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: UUID,
        section_id: Optional[UUID] = None,
    ) -> list[TermReport]:
        """Generate term reports for all students in a class/section."""
        # Get students
        query = select(Student).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.deleted_at.is_(None),
                Student.status == "active",
            )
        )
        if section_id:
            query = query.where(Student.section_id == section_id)

        students = (await self.db.execute(query)).scalars().all()

        reports = []
        for student in students:
            # Check if report exists
            existing = await self.db.execute(
                select(TermReport).where(
                    and_(
                        TermReport.tenant_id == tenant_id,
                        TermReport.term_id == term_id,
                        TermReport.student_id == student.id,
                    )
                )
            )
            report = existing.scalar_one_or_none()

            if not report:
                report = TermReport(
                    tenant_id=tenant_id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    student_id=student.id,
                    class_id=class_id,
                    section_id=student.section_id,
                )
                self.db.add(report)

            # Calculate scores for this student
            total_score, average_score, subjects_count = await self.calculate_student_term_scores(
                tenant_id=tenant_id,
                term_id=term_id,
                student_id=student.id,
                class_id=class_id,
            )

            report.total_score = total_score
            report.average_score = average_score
            report.subjects_count = subjects_count

            # Calculate attendance for this student
            days_present, days_absent, total_school_days, attendance_pct = await self.calculate_student_attendance(
                tenant_id=tenant_id,
                term_id=term_id,
                student_id=student.id,
            )

            report.days_present = days_present
            report.days_absent = days_absent
            report.total_school_days = total_school_days
            report.attendance_percentage = attendance_pct

            reports.append(report)

        await self.db.commit()

        # Refresh all reports
        for report in reports:
            await self.db.refresh(report)

        return reports

    async def calculate_rankings(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: UUID,
    ) -> None:
        """
        Calculate and update rankings using SQL DENSE_RANK for efficiency.

        Uses PostgreSQL window functions to calculate:
        - class_position: Ranking within the entire class (DENSE_RANK)
        - class_size: Total students in the class
        - section_position: Ranking within the section (DENSE_RANK)
        - section_size: Total students in the section
        """
        # Update class rankings using DENSE_RANK window function
        # This is much more efficient than fetching all records and ranking in Python
        class_ranking_sql = text("""
            WITH ranked AS (
                SELECT
                    id,
                    DENSE_RANK() OVER (ORDER BY COALESCE(total_score, 0) DESC) as class_position,
                    COUNT(*) OVER () as class_size
                FROM term_reports
                WHERE tenant_id = :tenant_id
                  AND term_id = :term_id
                  AND class_id = :class_id
                  AND deleted_at IS NULL
            )
            UPDATE term_reports t
            SET
                class_position = r.class_position,
                class_size = r.class_size,
                updated_at = CURRENT_TIMESTAMP
            FROM ranked r
            WHERE t.id = r.id
        """)

        await self.db.execute(
            class_ranking_sql,
            {"tenant_id": str(tenant_id), "term_id": str(term_id), "class_id": str(class_id)}
        )

        # Update section rankings using DENSE_RANK partitioned by section
        section_ranking_sql = text("""
            WITH ranked AS (
                SELECT
                    id,
                    section_id,
                    DENSE_RANK() OVER (
                        PARTITION BY section_id
                        ORDER BY COALESCE(total_score, 0) DESC
                    ) as section_position,
                    COUNT(*) OVER (PARTITION BY section_id) as section_size
                FROM term_reports
                WHERE tenant_id = :tenant_id
                  AND term_id = :term_id
                  AND class_id = :class_id
                  AND section_id IS NOT NULL
                  AND deleted_at IS NULL
            )
            UPDATE term_reports t
            SET
                section_position = r.section_position,
                section_size = r.section_size,
                updated_at = CURRENT_TIMESTAMP
            FROM ranked r
            WHERE t.id = r.id
        """)

        await self.db.execute(
            section_ranking_sql,
            {"tenant_id": str(tenant_id), "term_id": str(term_id), "class_id": str(class_id)}
        )

        await self.db.commit()

    async def get_term_report(
        self, report_id: UUID
    ) -> Optional[TermReport]:
        """Get term report by ID."""
        result = await self.db.execute(
            select(TermReport)
            .where(TermReport.id == report_id)
            .options(
                joinedload(TermReport.student),
                joinedload(TermReport.class_),
                joinedload(TermReport.section),
                joinedload(TermReport.term),
                joinedload(TermReport.academic_year),
            )
        )
        return result.scalar_one_or_none()

    async def list_term_reports(
        self,
        tenant_id: UUID,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        is_published: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[TermReport], int]:
        """List term reports with filters."""
        query = select(TermReport).where(TermReport.tenant_id == tenant_id)

        if term_id:
            query = query.where(TermReport.term_id == term_id)
        if class_id:
            query = query.where(TermReport.class_id == class_id)
        if section_id:
            query = query.where(TermReport.section_id == section_id)
        if is_published is not None:
            query = query.where(TermReport.is_published == is_published)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results with eager loading for all relationships
        query = query.options(
            joinedload(TermReport.student),
            joinedload(TermReport.class_),
            joinedload(TermReport.section),
            joinedload(TermReport.term),
            joinedload(TermReport.academic_year),
        ).order_by(TermReport.class_position)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_remarks(
        self,
        report_id: UUID,
        tenant_id: UUID,
        conduct_grade: Optional[str] = None,
        interest: Optional[str] = None,
        class_teacher_remark: Optional[str] = None,
        headmaster_remark: Optional[str] = None,
    ) -> Optional[TermReport]:
        """Update term report remarks."""
        report = await self.get_term_report(report_id)
        if not report or report.tenant_id != tenant_id:
            return None

        if conduct_grade is not None:
            report.conduct_grade = conduct_grade
        if interest is not None:
            report.interest = interest
        if class_teacher_remark is not None:
            report.class_teacher_remark = class_teacher_remark
        if headmaster_remark is not None:
            report.headmaster_remark = headmaster_remark

        report.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def publish_reports(
        self,
        tenant_id: UUID,
        term_id: UUID,
        class_id: Optional[UUID] = None,
    ) -> int:
        """Publish term reports (make visible to parents)."""
        query = select(TermReport).where(
            and_(
                TermReport.tenant_id == tenant_id,
                TermReport.term_id == term_id,
                TermReport.is_published == False,
            )
        )
        if class_id:
            query = query.where(TermReport.class_id == class_id)

        result = await self.db.execute(query)
        reports = result.scalars().all()

        now = datetime.now(UTC)
        count = 0
        for report in reports:
            report.is_published = True
            report.published_at = now
            count += 1

        await self.db.commit()
        return count


# =========================
# Analytics Service
# =========================


class AnalyticsService:
    """Service for exam analytics and timetabling."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_grade_distribution(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        class_id: UUID,
        subject_id: Optional[UUID] = None,
    ) -> dict:
        """Get grade distribution for a class/subject."""
        # Get exam and class info
        exam_result = await self.db.execute(
            select(Exam).where(
                and_(Exam.id == exam_id, Exam.tenant_id == tenant_id)
            )
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            return None

        class_result = await self.db.execute(
            select(Class).where(Class.id == class_id)
        )
        class_obj = class_result.scalar_one_or_none()
        if not class_obj:
            return None

        # Build query for exam subjects
        subject_query = select(ExamSubject).where(
            and_(
                ExamSubject.exam_id == exam_id,
                ExamSubject.class_id == class_id,
            )
        )
        if subject_id:
            subject_query = subject_query.where(ExamSubject.subject_id == subject_id)

        exam_subjects_result = await self.db.execute(subject_query)
        exam_subjects = exam_subjects_result.scalars().all()

        if not exam_subjects:
            return {
                "exam_id": exam_id,
                "exam_name": exam.name,
                "class_id": class_id,
                "class_name": class_obj.name,
                "subject_id": subject_id,
                "subject_name": None,
                "total_students": 0,
                "graded_students": 0,
                "absent_students": 0,
                "grades": [],
            }

        # Get subject name if filtering by subject
        subject_name = None
        if subject_id:
            subject_result = await self.db.execute(
                select(Subject).where(Subject.id == subject_id)
            )
            subject_obj = subject_result.scalar_one_or_none()
            subject_name = subject_obj.name if subject_obj else None

        # Get all scores for the exam subjects
        exam_subject_ids = [es.id for es in exam_subjects]
        scores_result = await self.db.execute(
            select(ExamScore).where(
                and_(
                    ExamScore.exam_subject_id.in_(exam_subject_ids),
                    ExamScore.deleted_at.is_(None),
                )
            )
        )
        scores = scores_result.scalars().all()

        # Count grades
        grade_counts: dict[str, int] = {}
        total_students = 0
        graded_students = 0
        absent_students = 0

        # Get unique students
        student_grades: dict[UUID, list[str]] = {}
        for score in scores:
            if score.student_id not in student_grades:
                student_grades[score.student_id] = []
            if score.is_absent:
                absent_students += 1
            elif score.grade:
                student_grades[score.student_id].append(score.grade)
                if score.grade not in grade_counts:
                    grade_counts[score.grade] = 0
                grade_counts[score.grade] += 1
                graded_students += 1

        total_students = len(student_grades) if student_grades else len(scores)

        # Calculate percentages
        grades = []
        for grade, count in sorted(grade_counts.items()):
            percentage = (Decimal(count) / Decimal(graded_students) * 100) if graded_students > 0 else Decimal(0)
            grades.append({
                "grade": grade,
                "count": count,
                "percentage": round(percentage, 1),
            })

        return {
            "exam_id": exam_id,
            "exam_name": exam.name,
            "class_id": class_id,
            "class_name": class_obj.name,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "total_students": total_students,
            "graded_students": graded_students,
            "absent_students": absent_students,
            "grades": grades,
        }

    async def get_class_statistics(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        class_id: UUID,
        section_id: Optional[UUID] = None,
    ) -> dict:
        """Get overall class statistics for an exam."""
        import statistics

        # Get exam info
        exam_result = await self.db.execute(
            select(Exam)
            .options(joinedload(Exam.term), joinedload(Exam.academic_year))
            .where(and_(Exam.id == exam_id, Exam.tenant_id == tenant_id))
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            return None

        # Get class info
        class_result = await self.db.execute(
            select(Class).where(Class.id == class_id)
        )
        class_obj = class_result.scalar_one_or_none()
        if not class_obj:
            return None

        # Get section info if provided
        section_name = None
        if section_id:
            section_result = await self.db.execute(
                select(ClassSection).where(ClassSection.id == section_id)
            )
            section_obj = section_result.scalar_one_or_none()
            section_name = section_obj.name if section_obj else None

        # Get exam subjects for the class
        subject_query = select(ExamSubject).where(
            and_(
                ExamSubject.exam_id == exam_id,
                ExamSubject.class_id == class_id,
            )
        )
        if section_id:
            subject_query = subject_query.where(
                or_(ExamSubject.section_id == section_id, ExamSubject.section_id.is_(None))
            )

        exam_subjects_result = await self.db.execute(subject_query)
        exam_subjects = exam_subjects_result.scalars().all()

        if not exam_subjects:
            return self._empty_class_statistics(exam, class_obj, section_id, section_name)

        # Get all scores
        exam_subject_ids = [es.id for es in exam_subjects]
        scores_result = await self.db.execute(
            select(ExamScore).where(
                and_(
                    ExamScore.exam_subject_id.in_(exam_subject_ids),
                    ExamScore.deleted_at.is_(None),
                )
            )
        )
        scores = scores_result.scalars().all()

        # Calculate student totals (average across subjects)
        student_scores: dict[UUID, list[Decimal]] = {}
        student_grades: dict[UUID, list[str]] = {}
        absent_count = 0
        grade_counts: dict[str, int] = {}

        for score in scores:
            if score.is_absent:
                absent_count += 1
                continue
            if score.score is not None:
                if score.student_id not in student_scores:
                    student_scores[score.student_id] = []
                # Normalize to percentage
                exam_subject = next((es for es in exam_subjects if es.id == score.exam_subject_id), None)
                if exam_subject and exam_subject.max_score:
                    pct = (score.score / exam_subject.max_score) * 100
                    student_scores[score.student_id].append(pct)
            if score.grade:
                if score.grade not in grade_counts:
                    grade_counts[score.grade] = 0
                grade_counts[score.grade] += 1

        # Calculate averages per student
        student_averages = []
        for student_id, pcts in student_scores.items():
            if pcts:
                avg = sum(pcts) / len(pcts)
                student_averages.append(avg)

        # Calculate statistics
        total_students = len(student_scores)
        if student_averages:
            class_average = round(Decimal(str(sum(student_averages) / len(student_averages))), 2)
            highest_score = round(Decimal(str(max(student_averages))), 2)
            lowest_score = round(Decimal(str(min(student_averages))), 2)
            median_score = round(Decimal(str(statistics.median(student_averages))), 2) if len(student_averages) > 1 else class_average
        else:
            class_average = None
            highest_score = None
            lowest_score = None
            median_score = None

        # Calculate pass/fail (assuming 50% is pass mark)
        pass_mark = Decimal("50")
        passed = sum(1 for avg in student_averages if Decimal(str(avg)) >= pass_mark)
        failed = total_students - passed
        pass_rate = round((Decimal(passed) / Decimal(total_students) * 100), 1) if total_students > 0 else Decimal(0)
        fail_rate = round((Decimal(failed) / Decimal(total_students) * 100), 1) if total_students > 0 else Decimal(0)

        # Grade distribution
        grades = []
        total_graded = sum(grade_counts.values())
        for grade, count in sorted(grade_counts.items()):
            percentage = round((Decimal(count) / Decimal(total_graded) * 100), 1) if total_graded > 0 else Decimal(0)
            grades.append({
                "grade": grade,
                "count": count,
                "percentage": percentage,
            })

        return {
            "exam_id": exam_id,
            "exam_name": exam.name,
            "class_id": class_id,
            "class_name": class_obj.name,
            "section_id": section_id,
            "section_name": section_name,
            "total_students": total_students,
            "students_with_scores": len(student_averages),
            "class_average": class_average,
            "highest_score": highest_score,
            "lowest_score": lowest_score,
            "median_score": median_score,
            "pass_fail": {
                "total_students": total_students,
                "passed": passed,
                "failed": failed,
                "absent": absent_count,
                "pass_rate": pass_rate,
                "fail_rate": fail_rate,
            },
            "grade_distribution": grades,
        }

    def _empty_class_statistics(self, exam, class_obj, section_id, section_name):
        """Return empty statistics structure."""
        return {
            "exam_id": exam.id,
            "exam_name": exam.name,
            "class_id": class_obj.id,
            "class_name": class_obj.name,
            "section_id": section_id,
            "section_name": section_name,
            "total_students": 0,
            "students_with_scores": 0,
            "class_average": None,
            "highest_score": None,
            "lowest_score": None,
            "median_score": None,
            "pass_fail": {
                "total_students": 0,
                "passed": 0,
                "failed": 0,
                "absent": 0,
                "pass_rate": Decimal(0),
                "fail_rate": Decimal(0),
            },
            "grade_distribution": [],
        }

    async def get_subject_statistics(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        class_id: UUID,
        section_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Get statistics for each subject in an exam."""
        import statistics

        # Get exam subjects with subject details
        query = (
            select(ExamSubject)
            .options(joinedload(ExamSubject.subject))
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.class_id == class_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        if section_id:
            query = query.where(
                or_(ExamSubject.section_id == section_id, ExamSubject.section_id.is_(None))
            )

        result = await self.db.execute(query)
        exam_subjects = result.unique().scalars().all()

        subject_stats = []
        for es in exam_subjects:
            # Get scores for this subject
            scores_result = await self.db.execute(
                select(ExamScore).where(
                    and_(
                        ExamScore.exam_subject_id == es.id,
                        ExamScore.deleted_at.is_(None),
                    )
                )
            )
            scores = scores_result.scalars().all()

            # Calculate statistics
            score_values = []
            grade_counts: dict[str, int] = {}
            absent_count = 0

            for score in scores:
                if score.is_absent:
                    absent_count += 1
                    continue
                if score.score is not None:
                    # Normalize to percentage
                    pct = float((score.score / es.max_score) * 100) if es.max_score else 0
                    score_values.append(pct)
                if score.grade:
                    if score.grade not in grade_counts:
                        grade_counts[score.grade] = 0
                    grade_counts[score.grade] += 1

            total_students = len(scores)
            students_with_scores = len(score_values)

            if score_values:
                avg_score = round(Decimal(str(sum(score_values) / len(score_values))), 2)
                highest = round(Decimal(str(max(score_values))), 2)
                lowest = round(Decimal(str(min(score_values))), 2)
                median = round(Decimal(str(statistics.median(score_values))), 2) if len(score_values) > 1 else avg_score
                # Pass rate (assuming 50% pass mark)
                passed = sum(1 for s in score_values if s >= 50)
                pass_rate = round(Decimal(passed) / Decimal(len(score_values)) * 100, 1) if score_values else Decimal(0)
            else:
                avg_score = None
                highest = None
                lowest = None
                median = None
                pass_rate = Decimal(0)

            # Grade distribution
            grades = []
            total_graded = sum(grade_counts.values())
            for grade, count in sorted(grade_counts.items()):
                percentage = round((Decimal(count) / Decimal(total_graded) * 100), 1) if total_graded > 0 else Decimal(0)
                grades.append({
                    "grade": grade,
                    "count": count,
                    "percentage": percentage,
                })

            subject_stats.append({
                "subject_id": es.subject_id,
                "subject_name": es.subject.name if es.subject else "Unknown",
                "subject_code": es.subject.code if es.subject else None,
                "total_students": total_students,
                "students_with_scores": students_with_scores,
                "absent_students": absent_count,
                "average_score": avg_score,
                "highest_score": highest,
                "lowest_score": lowest,
                "median_score": median,
                "pass_rate": pass_rate,
                "grade_distribution": grades,
            })

        return subject_stats

    async def get_subject_rankings(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        subject_id: UUID,
        class_id: UUID,
        section_id: Optional[UUID] = None,
    ) -> dict:
        """Get student rankings for a specific subject."""
        # Get exam subject
        query = (
            select(ExamSubject)
            .options(joinedload(ExamSubject.subject))
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.subject_id == subject_id,
                    ExamSubject.class_id == class_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        if section_id:
            query = query.where(
                or_(ExamSubject.section_id == section_id, ExamSubject.section_id.is_(None))
            )

        result = await self.db.execute(query)
        exam_subject = result.scalar_one_or_none()

        if not exam_subject:
            return None

        # Get exam info
        exam_result = await self.db.execute(
            select(Exam).where(Exam.id == exam_id)
        )
        exam = exam_result.scalar_one_or_none()

        # Get class info
        class_result = await self.db.execute(
            select(Class).where(Class.id == class_id)
        )
        class_obj = class_result.scalar_one_or_none()

        # Get scores with student info
        scores_result = await self.db.execute(
            select(ExamScore)
            .options(joinedload(ExamScore.student))
            .where(
                and_(
                    ExamScore.exam_subject_id == exam_subject.id,
                    ExamScore.deleted_at.is_(None),
                )
            )
        )
        scores = scores_result.unique().scalars().all()

        # Sort by score descending and assign ranks
        sorted_scores = sorted(
            scores,
            key=lambda s: (s.score if s.score is not None else Decimal(-1)),
            reverse=True
        )

        rankings = []
        current_rank = 0
        prev_score = None

        for idx, score in enumerate(sorted_scores):
            # Handle ties
            if score.score != prev_score:
                current_rank = idx + 1
            prev_score = score.score

            student = score.student
            rankings.append({
                "student_id": score.student_id,
                "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
                "student_id_number": student.student_id if student else "",
                "score": score.score,
                "grade": score.grade,
                "position": current_rank if not score.is_absent else None,
            })

        return {
            "exam_id": exam_id,
            "exam_name": exam.name if exam else "",
            "subject_id": subject_id,
            "subject_name": exam_subject.subject.name if exam_subject.subject else "",
            "class_id": class_id,
            "class_name": class_obj.name if class_obj else "",
            "total_students": len(rankings),
            "rankings": rankings,
        }

    # =========================
    # Timetabling Methods
    # =========================

    async def get_exam_timetable(
        self,
        tenant_id: UUID,
        exam_id: UUID,
    ) -> dict:
        """Get full exam timetable."""
        # Get exam info
        exam_result = await self.db.execute(
            select(Exam).where(
                and_(Exam.id == exam_id, Exam.tenant_id == tenant_id)
            )
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            return None

        # Get all exam subjects with details
        subjects_result = await self.db.execute(
            select(ExamSubject)
            .options(
                joinedload(ExamSubject.subject),
                joinedload(ExamSubject.class_),
                joinedload(ExamSubject.section),
            )
            .where(ExamSubject.exam_id == exam_id)
            .order_by(ExamSubject.exam_date, ExamSubject.exam_time, ExamSubject.class_id)
        )
        exam_subjects = subjects_result.unique().scalars().all()

        entries = []
        scheduled = 0
        unscheduled = 0

        for es in exam_subjects:
            if es.exam_date:
                scheduled += 1
            else:
                unscheduled += 1

            entries.append({
                "exam_subject_id": es.id,
                "subject_id": es.subject_id,
                "subject_name": es.subject.name if es.subject else "Unknown",
                "subject_code": es.subject.code if es.subject else None,
                "class_id": es.class_id,
                "class_name": es.class_.name if es.class_ else "Unknown",
                "section_id": es.section_id,
                "section_name": es.section.name if es.section else None,
                "exam_date": es.exam_date,
                "exam_time": es.exam_time,
                "duration_minutes": es.duration_minutes,
                "venue": es.venue,
                "max_score": es.max_score,
                "status": es.status.value if hasattr(es.status, 'value') else str(es.status),
            })

        return {
            "exam_id": exam_id,
            "exam_name": exam.name,
            "exam_type": exam.exam_type.value if hasattr(exam.exam_type, 'value') else str(exam.exam_type),
            "start_date": exam.start_date,
            "end_date": exam.end_date,
            "entries": entries,
            "total_subjects": len(entries),
            "scheduled_subjects": scheduled,
            "unscheduled_subjects": unscheduled,
        }

    async def check_timetable_conflicts(
        self,
        tenant_id: UUID,
        exam_id: UUID,
    ) -> dict:
        """Check for scheduling conflicts in exam timetable."""
        # Get all exam subjects with scheduling info
        subjects_result = await self.db.execute(
            select(ExamSubject)
            .options(
                joinedload(ExamSubject.subject),
                joinedload(ExamSubject.class_),
            )
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.tenant_id == tenant_id,
                    ExamSubject.exam_date.isnot(None),
                )
            )
        )
        exam_subjects = subjects_result.unique().scalars().all()

        conflicts = []

        # Check venue conflicts (same venue, same date/time, different subjects)
        venue_schedule: dict[str, list] = {}
        for es in exam_subjects:
            if es.venue and es.exam_date and es.exam_time:
                key = f"{es.venue}_{es.exam_date}_{es.exam_time}"
                if key not in venue_schedule:
                    venue_schedule[key] = []
                venue_schedule[key].append(es)

        for key, subjects in venue_schedule.items():
            if len(subjects) > 1:
                for i, s1 in enumerate(subjects):
                    for s2 in subjects[i+1:]:
                        conflicts.append({
                            "conflict_type": "venue",
                            "severity": "error",
                            "message": f"Venue '{s1.venue}' double-booked on {s1.exam_date} at {s1.exam_time}",
                            "exam_subject_1_id": s1.id,
                            "exam_subject_1_name": s1.subject.name if s1.subject else "Unknown",
                            "exam_subject_2_id": s2.id,
                            "exam_subject_2_name": s2.subject.name if s2.subject else "Unknown",
                        })

        # Check class conflicts (same class, same date/time, different subjects)
        class_schedule: dict[str, list] = {}
        for es in exam_subjects:
            if es.exam_date and es.exam_time:
                key = f"{es.class_id}_{es.exam_date}_{es.exam_time}"
                if key not in class_schedule:
                    class_schedule[key] = []
                class_schedule[key].append(es)

        for key, subjects in class_schedule.items():
            if len(subjects) > 1:
                for i, s1 in enumerate(subjects):
                    for s2 in subjects[i+1:]:
                        class_name = s1.class_.name if s1.class_ else "Unknown"
                        conflicts.append({
                            "conflict_type": "time_overlap",
                            "severity": "error",
                            "message": f"Class '{class_name}' has multiple exams on {s1.exam_date} at {s1.exam_time}",
                            "exam_subject_1_id": s1.id,
                            "exam_subject_1_name": s1.subject.name if s1.subject else "Unknown",
                            "exam_subject_2_id": s2.id,
                            "exam_subject_2_name": s2.subject.name if s2.subject else "Unknown",
                        })

        # Check for unscheduled subjects (warning)
        unscheduled_result = await self.db.execute(
            select(ExamSubject)
            .options(joinedload(ExamSubject.subject))
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.tenant_id == tenant_id,
                    ExamSubject.exam_date.is_(None),
                )
            )
        )
        unscheduled = unscheduled_result.unique().scalars().all()

        for es in unscheduled:
            conflicts.append({
                "conflict_type": "unscheduled",
                "severity": "warning",
                "message": f"Subject '{es.subject.name if es.subject else 'Unknown'}' has no scheduled date/time",
                "exam_subject_1_id": es.id,
                "exam_subject_1_name": es.subject.name if es.subject else "Unknown",
                "exam_subject_2_id": None,
                "exam_subject_2_name": None,
            })

        return {
            "exam_id": exam_id,
            "has_conflicts": len([c for c in conflicts if c["severity"] == "error"]) > 0,
            "total_conflicts": len(conflicts),
            "conflicts": conflicts,
        }

    async def bulk_update_timetable(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        entries: list[dict],
    ) -> dict:
        """Bulk update timetable entries."""
        updated = 0
        failed = 0
        errors = []

        for entry in entries:
            try:
                result = await self.db.execute(
                    select(ExamSubject).where(
                        and_(
                            ExamSubject.id == entry["exam_subject_id"],
                            ExamSubject.exam_id == exam_id,
                            ExamSubject.tenant_id == tenant_id,
                        )
                    )
                )
                exam_subject = result.scalar_one_or_none()

                if not exam_subject:
                    failed += 1
                    errors.append({
                        "exam_subject_id": str(entry["exam_subject_id"]),
                        "error": "Exam subject not found",
                    })
                    continue

                if "exam_date" in entry:
                    exam_subject.exam_date = entry["exam_date"]
                if "exam_time" in entry:
                    exam_subject.exam_time = entry["exam_time"]
                if "duration_minutes" in entry:
                    exam_subject.duration_minutes = entry["duration_minutes"]
                if "venue" in entry:
                    exam_subject.venue = entry["venue"]

                exam_subject.updated_at = datetime.now(UTC)
                updated += 1

            except Exception as e:
                failed += 1
                errors.append({
                    "exam_subject_id": str(entry.get("exam_subject_id")),
                    "error": str(e),
                })

        await self.db.commit()

        # Check for conflicts after update
        conflicts_result = await self.check_timetable_conflicts(tenant_id, exam_id)

        return {
            "updated": updated,
            "failed": failed,
            "errors": errors,
            "conflicts": conflicts_result.get("conflicts", []),
        }

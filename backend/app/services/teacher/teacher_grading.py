"""
SIMS Plus - Teacher Grading Service

Handles exam score entry, pending score retrieval, and grade summaries
for the teacher portal. Teachers can only enter/view scores for
exam subjects in classes they are assigned to.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    Class,
    ClassSection,
    ClassSubject,
    GradingScale,
    Grade,
    Subject,
    Term,
)
from app.models.exam import (
    ContinuousAssessment,
    Exam,
    ExamScore,
    ExamStatus,
    ExamSubject,
    ExamSubjectStatus,
)
from app.models.student import Student, StudentStatus

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherGradingService:
    """
    Score entry and grade summary operations for teachers.

    All queries filter by tenant_id for defense-in-depth.
    Score entry respects exam subject status (cannot enter scores on
    published or submitted exam subjects).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pending_scores(
        self, staff_id: UUID, tenant_id: UUID,
        academic_year_id: UUID, term_id: UUID,
    ) -> list[dict]:
        """
        Get all exam subjects where this teacher needs to enter scores.

        An exam subject is "pending" if:
        - The teacher is assigned to the class+subject combination
        - The exam is in scheduled/ongoing/completed status
        - The exam subject status is pending or scores_entered
        - Not all student scores have been entered
        """
        # Get class-subject combinations this teacher is assigned to
        teacher_subjects = await self.db.execute(
            select(ClassSubject.class_id, ClassSubject.subject_id)
            .where(
                and_(
                    ClassSubject.teacher_id == staff_id,
                    ClassSubject.tenant_id == tenant_id,
                )
            )
        )
        teacher_class_subjects = teacher_subjects.all()

        if not teacher_class_subjects:
            return []

        # Build filter for class-subject pairs
        class_subject_pairs = [
            and_(
                ExamSubject.class_id == cs.class_id,
                ExamSubject.subject_id == cs.subject_id,
            )
            for cs in teacher_class_subjects
        ]

        # Query pending exam subjects
        result = await self.db.execute(
            select(ExamSubject)
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .options(
                selectinload(ExamSubject.exam),
                selectinload(ExamSubject.subject),
                selectinload(ExamSubject.class_),
                selectinload(ExamSubject.section),
            )
            .where(
                and_(
                    ExamSubject.tenant_id == tenant_id,
                    Exam.tenant_id == tenant_id,
                    Exam.academic_year_id == academic_year_id,
                    Exam.term_id == term_id,
                    Exam.status.in_([
                        ExamStatus.SCHEDULED,
                        ExamStatus.ONGOING,
                        ExamStatus.COMPLETED,
                    ]),
                    ExamSubject.status.in_([
                        ExamSubjectStatus.PENDING,
                        ExamSubjectStatus.SCORES_ENTERED,
                    ]),
                    or_(*class_subject_pairs),
                    Exam.deleted_at.is_(None),
                )
            )
            .order_by(Exam.start_date, ExamSubject.class_id)
        )
        exam_subjects = result.scalars().all()

        if not exam_subjects:
            return []

        # Batch query: score counts per exam_subject_id
        es_ids = [es.id for es in exam_subjects]
        score_count_result = await self.db.execute(
            select(
                ExamScore.exam_subject_id,
                func.count(ExamScore.id).label("count"),
            )
            .where(
                and_(
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.exam_subject_id.in_(es_ids),
                    ExamScore.deleted_at.is_(None),
                )
            )
            .group_by(ExamScore.exam_subject_id)
        )
        scores_entered_map = dict(score_count_result.all())

        # Batch query: student counts per section_id (for section-scoped exam subjects)
        section_ids = [es.section_id for es in exam_subjects if es.section_id]
        section_student_counts: dict[UUID, int] = {}
        if section_ids:
            sec_count_result = await self.db.execute(
                select(
                    Student.section_id,
                    func.count(Student.id).label("count"),
                )
                .where(
                    and_(
                        Student.tenant_id == tenant_id,
                        Student.section_id.in_(section_ids),
                        Student.status == StudentStatus.ACTIVE,
                        Student.deleted_at.is_(None),
                    )
                )
                .group_by(Student.section_id)
            )
            section_student_counts = dict(sec_count_result.all())

        # Batch query: student counts per class_id (for class-wide exam subjects)
        class_ids = [es.class_id for es in exam_subjects if not es.section_id]
        class_student_counts: dict[UUID, int] = {}
        if class_ids:
            cls_count_result = await self.db.execute(
                select(
                    ClassSection.class_id,
                    func.count(Student.id).label("count"),
                )
                .join(ClassSection, Student.section_id == ClassSection.id)
                .where(
                    and_(
                        Student.tenant_id == tenant_id,
                        ClassSection.class_id.in_(class_ids),
                        Student.status == StudentStatus.ACTIVE,
                        Student.deleted_at.is_(None),
                    )
                )
                .group_by(ClassSection.class_id)
            )
            class_student_counts = dict(cls_count_result.all())

        # Build results using pre-fetched counts
        pending = []
        for es in exam_subjects:
            if es.section_id:
                total_students = section_student_counts.get(es.section_id, 0)
            else:
                total_students = class_student_counts.get(es.class_id, 0)

            pending.append({
                "exam_id": es.exam.id,
                "exam_name": es.exam.name,
                "exam_subject_id": es.id,
                "subject_id": es.subject_id,
                "subject_name": es.subject.name if es.subject else None,
                "class_id": es.class_id,
                "class_name": es.class_.name if es.class_ else None,
                "section_id": es.section_id,
                "section_name": es.section.name if es.section else None,
                "max_score": es.max_score,
                "total_students": total_students,
                "scores_entered": scores_entered_map.get(es.id, 0),
                "status": es.status.value,
            })

        return pending

    async def enter_scores(
        self,
        staff_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        exam_subject_id: UUID,
        scores: list[dict],
    ) -> dict:
        """
        Bulk enter/update scores for an exam subject.

        Each item in scores should have: student_id, score, is_absent, teacher_remark.
        Returns success/failure counts and per-student results.
        """
        # Verify exam subject exists and is editable
        es_result = await self.db.execute(
            select(ExamSubject)
            .options(selectinload(ExamSubject.grading_scale))
            .where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        exam_subject = es_result.scalar_one_or_none()
        if not exam_subject:
            raise TeacherServiceError("Exam subject not found", code="not_found")

        if exam_subject.status in (ExamSubjectStatus.SUBMITTED, ExamSubjectStatus.PUBLISHED):
            raise TeacherServiceError(
                "Scores have already been submitted and cannot be modified",
                code="scores_locked",
            )

        # Pre-fetch valid student IDs enrolled in this exam subject's class/section
        # to prevent score entry for students not in the target class
        valid_students_query = select(Student.id).where(
            and_(
                Student.tenant_id == tenant_id,
                Student.status == StudentStatus.ACTIVE,
                Student.deleted_at.is_(None),
            )
        )
        if exam_subject.section_id:
            valid_students_query = valid_students_query.where(
                Student.section_id == exam_subject.section_id
            )
        else:
            valid_students_query = (
                valid_students_query
                .join(ClassSection, Student.section_id == ClassSection.id)
                .where(ClassSection.class_id == exam_subject.class_id)
            )
        valid_result = await self.db.execute(valid_students_query)
        valid_student_ids = set(valid_result.scalars().all())

        # Load grading scale if available
        grading_scale_grades = []
        if exam_subject.grading_scale_id:
            grades_result = await self.db.execute(
                select(Grade)
                .where(
                    and_(
                        Grade.grading_scale_id == exam_subject.grading_scale_id,
                        Grade.tenant_id == tenant_id,
                    )
                )
                .order_by(Grade.min_score.desc())
            )
            grading_scale_grades = list(grades_result.scalars().all())

        results = []
        successful = 0
        failed = 0

        for score_item in scores:
            student_id = score_item["student_id"]
            try:
                # Reject students not enrolled in this exam subject's class/section
                if student_id not in valid_student_ids:
                    raise ValueError(
                        "Student is not enrolled in the class for this exam subject"
                    )
                score_value = score_item.get("score")
                is_absent = score_item.get("is_absent", False)
                teacher_remark = score_item.get("teacher_remark")

                # Validate score against max_score
                if score_value is not None and not is_absent:
                    if Decimal(str(score_value)) > exam_subject.max_score:
                        raise ValueError(
                            f"Score {score_value} exceeds maximum {exam_subject.max_score}"
                        )
                    if Decimal(str(score_value)) < 0:
                        raise ValueError("Score cannot be negative")

                # Calculate grade from score
                grade_str = None
                grade_point = None
                grade_remark = None
                if score_value is not None and grading_scale_grades and not is_absent:
                    score_decimal = Decimal(str(score_value))
                    # Normalize to percentage if max_score != 100
                    if exam_subject.max_score != Decimal("100.00"):
                        normalized = (score_decimal / exam_subject.max_score) * 100
                    else:
                        normalized = score_decimal

                    for g in grading_scale_grades:
                        if normalized >= g.min_score:
                            grade_str = g.grade
                            grade_point = g.grade_point
                            grade_remark = g.remark
                            break

                # Upsert score (find existing or create new)
                existing_result = await self.db.execute(
                    select(ExamScore)
                    .where(
                        and_(
                            ExamScore.tenant_id == tenant_id,
                            ExamScore.exam_subject_id == exam_subject_id,
                            ExamScore.student_id == student_id,
                        )
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    # Update existing score
                    if not is_absent:
                        existing.score = Decimal(str(score_value)) if score_value is not None else None
                    else:
                        existing.score = None
                    existing.is_absent = is_absent
                    existing.grade = grade_str
                    existing.grade_point = grade_point
                    existing.grade_remark = grade_remark
                    existing.teacher_remark = teacher_remark
                    existing.entered_by = user_id
                    existing.entered_at = datetime.now(UTC)
                else:
                    # Create new score
                    new_score = ExamScore(
                        tenant_id=tenant_id,
                        exam_subject_id=exam_subject_id,
                        student_id=student_id,
                        score=Decimal(str(score_value)) if score_value is not None and not is_absent else None,
                        is_absent=is_absent,
                        grade=grade_str,
                        grade_point=grade_point,
                        grade_remark=grade_remark,
                        teacher_remark=teacher_remark,
                        entered_by=user_id,
                        entered_at=datetime.now(UTC),
                    )
                    self.db.add(new_score)

                await self.db.flush()
                successful += 1
                results.append({
                    "student_id": student_id,
                    "success": True,
                    "error": None,
                    "grade": grade_str,
                    "grade_remark": grade_remark,
                })

            except ValueError as e:
                # Validation errors (e.g., score exceeds max) are safe to surface
                failed += 1
                results.append({
                    "student_id": student_id,
                    "success": False,
                    "error": str(e),
                    "grade": None,
                    "grade_remark": None,
                })
                logger.warning(
                    "score_entry_validation_failed",
                    student_id=str(student_id),
                    error=str(e),
                )
            except Exception:
                # Log full error for debugging but return a sanitized message
                failed += 1
                results.append({
                    "student_id": student_id,
                    "success": False,
                    "error": "Failed to save score",
                    "grade": None,
                    "grade_remark": None,
                })
                logger.exception(
                    "score_entry_failed",
                    student_id=str(student_id),
                )

        # Update exam subject status if scores were entered
        if successful > 0:
            exam_subject.status = ExamSubjectStatus.SCORES_ENTERED
            await self.db.flush()

        return {
            "total": len(scores),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    async def get_class_grade_summary(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        term_id: UUID,
    ) -> dict:
        """
        Get a grade summary for all students in a class for a specific subject and term.

        Combines exam scores and CA averages into a unified view.
        """
        # Get class and subject info
        cls_result = await self.db.execute(
            select(Class).where(and_(Class.id == class_id, Class.tenant_id == tenant_id))
        )
        cls = cls_result.scalar_one_or_none()

        subj_result = await self.db.execute(
            select(Subject).where(and_(Subject.id == subject_id, Subject.tenant_id == tenant_id))
        )
        subj = subj_result.scalar_one_or_none()

        term_result = await self.db.execute(
            select(Term).where(and_(Term.id == term_id, Term.tenant_id == tenant_id))
        )
        term = term_result.scalar_one_or_none()

        if not cls or not subj or not term:
            raise TeacherServiceError("Class, subject, or term not found", code="not_found")

        # Get students in this class
        students_result = await self.db.execute(
            select(Student)
            .join(ClassSection, Student.section_id == ClassSection.id)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    ClassSection.class_id == class_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
            .order_by(Student.last_name, Student.first_name)
        )
        students = students_result.scalars().all()

        if not students:
            return {
                "class_id": class_id,
                "class_name": cls.name,
                "subject_id": subject_id,
                "subject_name": subj.name,
                "term_id": term_id,
                "term_name": term.name,
                "students": [],
                "class_average": None,
                "highest_score": None,
                "lowest_score": None,
                "total_students": 0,
            }

        student_ids = [s.id for s in students]

        # Get exam scores for these students in this subject for this term
        exam_scores_result = await self.db.execute(
            select(ExamScore)
            .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .where(
                and_(
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.student_id.in_(student_ids),
                    ExamSubject.subject_id == subject_id,
                    ExamSubject.class_id == class_id,
                    Exam.term_id == term_id,
                    ExamScore.deleted_at.is_(None),
                )
            )
        )
        scores_by_student: dict[UUID, ExamScore] = {}
        for score in exam_scores_result.scalars().all():
            # Take the latest score if multiple exams
            if score.student_id not in scores_by_student:
                scores_by_student[score.student_id] = score

        # Get CA averages
        ca_result = await self.db.execute(
            select(
                ContinuousAssessment.student_id,
                func.avg(ContinuousAssessment.score),
            )
            .where(
                and_(
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.student_id.in_(student_ids),
                    ContinuousAssessment.subject_id == subject_id,
                    ContinuousAssessment.class_id == class_id,
                    ContinuousAssessment.term_id == term_id,
                    ContinuousAssessment.deleted_at.is_(None),
                )
            )
            .group_by(ContinuousAssessment.student_id)
        )
        ca_averages = dict(ca_result.all())

        # Build student summaries
        student_summaries = []
        all_totals = []

        for student in students:
            exam_score_obj = scores_by_student.get(student.id)
            exam_score_val = exam_score_obj.score if exam_score_obj and exam_score_obj.score else None
            exam_grade = exam_score_obj.grade if exam_score_obj else None
            ca_avg = ca_averages.get(student.id)

            # Simple total (exam + CA)
            total = None
            if exam_score_val is not None:
                total = exam_score_val
                if ca_avg is not None:
                    total = exam_score_val + Decimal(str(ca_avg))

            if total is not None:
                all_totals.append(total)

            student_summaries.append({
                "student_id": student.id,
                "student_name": f"{student.first_name} {student.last_name}",
                "exam_score": exam_score_val,
                "exam_grade": exam_grade,
                "ca_average": Decimal(str(ca_avg)).quantize(Decimal("0.01")) if ca_avg else None,
                "total_score": total,
                "grade": exam_grade,  # Uses exam grade as the primary grade
                "grade_remark": exam_score_obj.grade_remark if exam_score_obj else None,
            })

        return {
            "class_id": class_id,
            "class_name": cls.name,
            "subject_id": subject_id,
            "subject_name": subj.name,
            "term_id": term_id,
            "term_name": term.name,
            "students": student_summaries,
            "class_average": (
                Decimal(str(sum(all_totals) / len(all_totals))).quantize(Decimal("0.01"))
                if all_totals else None
            ),
            "highest_score": max(all_totals) if all_totals else None,
            "lowest_score": min(all_totals) if all_totals else None,
            "total_students": len(students),
        }

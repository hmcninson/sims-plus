"""
SIMS Plus - Score Service

Business logic for exam score entry, grade calculation, and score management.
"""

from datetime import datetime, UTC
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
    ExamScore,
    ScoreChangeLog,
)
from app.models.academic import (
    Class,
    ClassSection,
    Grade,
)
from app.models.student import Student

from app.services.exam.exam_service import ExamServiceError
from app.services.academic.guards import assert_term_year_editable


class ScoreService:
    """Service for managing exam scores."""

    def __init__(self, db: AsyncSession):
        self.db = db

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

    async def get_score_entry_form(
        self, tenant_id: UUID, exam_subject_id: UUID, section_id: Optional[UUID] = None
    ) -> Optional[dict]:
        """Get score entry form with exam subject details and students."""
        # Get exam subject with relations (including section)
        exam_subject_result = await self.db.execute(
            select(ExamSubject)
            .where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ExamSubject.tenant_id == tenant_id,
                )
            )
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
                    select(ClassSection.name).where(
                        and_(
                            ClassSection.id == effective_section_id,
                            ClassSection.tenant_id == tenant_id,
                        )
                    )
                )
                section_name = section_result.scalar_one_or_none()

        # Get students in the class/section with their section info
        query = select(Student).where(
            and_(
                Student.tenant_id == tenant_id,
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
            select(ExamScore).where(
                and_(
                    ExamScore.exam_subject_id == exam_subject_id,
                    ExamScore.tenant_id == tenant_id,
                )
            )
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
            select(ExamSubject).where(
                and_(
                    ExamSubject.id == exam_subject_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    ExamSubject.tenant_id == tenant_id,
                )
            )
        )
        exam_subject = exam_subject.scalar_one_or_none()
        if not exam_subject:
            raise ExamServiceError("Exam subject not found", code="not_found")

        # Guard: cannot enter scores in completed/archived years.
        # Resolve the term_id through the parent exam.
        exam_term_id = await self.db.scalar(
            select(Exam.term_id).where(
                and_(
                    Exam.id == exam_subject.exam_id,
                    Exam.tenant_id == tenant_id,
                )
            )
        )
        if exam_term_id:
            await assert_term_year_editable(self.db, tenant_id, exam_term_id)

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
                student_uuid = UUID(student_id) if isinstance(student_id, str) else student_id
                if student_uuid not in valid_student_ids:
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
                            ExamScore.tenant_id == tenant_id,
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

        await self.db.flush()

        # Update exam subject status
        if created_count > 0 or updated_count > 0:
            exam_subject.status = ExamSubjectStatus.SCORES_ENTERED
            await self.db.flush()

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
        from app.models.user import User

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
                and_(
                    ExamScore.exam_subject_id == exam_subject_id,
                    ExamScore.tenant_id == tenant_id,
                )
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
        await self.db.flush()
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
        await self.db.flush()
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
                    ExamScore.deleted_at.is_(None),
                )
            )
            .options(joinedload(ExamScore.exam_subject))
        )
        exam_score = result.scalar_one_or_none()
        if not exam_score:
            return None

        # Guard: cannot update scores in completed/archived years.
        # Resolve the term_id through the parent exam.
        exam_term_id = await self.db.scalar(
            select(Exam.term_id).where(
                and_(
                    Exam.id == exam_score.exam_subject.exam_id,
                    Exam.tenant_id == tenant_id,
                )
            )
        )
        if exam_term_id:
            await assert_term_year_editable(self.db, tenant_id, exam_term_id)

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
        await self.db.flush()
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
                    ExamScore.deleted_at.is_(None),
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
        # Get exam info (filter soft-deleted)
        exam_result = await self.db.execute(
            select(Exam)
            .where(
                and_(
                    Exam.id == exam_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                )
            )
            .options(joinedload(Exam.term))
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise ExamServiceError("Exam not found", code="not_found")

        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        class_result = await self.db.execute(
            select(Class).where(
                and_(Class.id == class_id, Class.tenant_id == tenant_id)
            )
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
                    ExamSubject.tenant_id == tenant_id,
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
                Student.tenant_id == tenant_id,
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
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.exam_subject_id.in_([es.id for es in exam_subjects]),
                    ExamScore.student_id.in_(student_ids),
                    ExamScore.deleted_at.is_(None),
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

        # Update exam status too (filter soft-deleted)
        exam_result = await self.db.execute(
            select(Exam).where(
                and_(
                    Exam.id == exam_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        exam = exam_result.scalar_one_or_none()
        if exam:
            exam.status = ExamStatus.RESULTS_PUBLISHED
            exam.updated_at = now

        await self.db.flush()
        return count

    async def get_student_results(
        self,
        exam_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Get a single student's exam results across all subjects."""
        # Get exam with relationships (filter soft-deleted)
        exam_result = await self.db.execute(
            select(Exam)
            .where(
                and_(
                    Exam.id == exam_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                )
            )
            .options(joinedload(Exam.term))
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise ExamServiceError("Exam not found", code="not_found")

        # Get student (filter soft-deleted)
        student_result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.id == student_id,
                    Student.tenant_id == tenant_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                joinedload(Student.class_),
                joinedload(Student.section),
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise ExamServiceError("Student not found", code="not_found")

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
            raise ExamServiceError("No exam subjects found for student's class", code="not_found")

        # Get student's scores (filter soft-deleted)
        scores_result = await self.db.execute(
            select(ExamScore)
            .where(
                and_(
                    ExamScore.student_id == student_id,
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.exam_subject_id.in_([es.id for es in exam_subjects]),
                    ExamScore.deleted_at.is_(None),
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

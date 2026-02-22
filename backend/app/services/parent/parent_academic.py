"""
SIMS Plus - Parent Academic Service

Grade views, report card access, and continuous assessment data for parents.
All methods enforce parent-child access verification before returning any data.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.academic import Subject, Term
from app.models.exam import (
    ContinuousAssessment,
    Exam,
    ExamScore,
    ExamSubject,
    TermReport,
)
from app.models.student import Student

from app.services.parent._shared import ParentServiceError
from app.services.parent.parent_service import ParentService

logger = structlog.get_logger()


class ParentAcademicService:
    """
    Service for parent access to academic data: grades, assessments, and reports.

    Every method verifies parent-child access before returning data.
    Only published results are visible to parents (exam status must be
    results_published, term reports must have is_published=True).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._parent = ParentService(db)

    async def get_child_grades(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
        term_id: UUID,
    ) -> dict:
        """
        Get term grades for a child: per-subject scores, grades, and positions.

        Only returns scores from exams whose status is 'results_published'.
        Combines exam scores with continuous assessment scores and computes
        per-subject totals.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)
            term_id: The term to fetch grades for

        Returns:
            Dict matching TermGrades schema structure

        Raises:
            ParentServiceError: If access denied or student not found
        """
        # Security gate: verify parent has access to this child
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        # Load student with class for display
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
                selectinload(Student.class_),
                selectinload(Student.section),
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise ParentServiceError("Student not found", code="student_not_found")

        # Load term and academic year
        term_result = await self.db.execute(
            select(Term)
            .where(
                and_(
                    Term.id == term_id,
                    Term.tenant_id == tenant_id,
                    Term.deleted_at.is_(None),
                )
            )
            .options(joinedload(Term.academic_year))
        )
        term = term_result.scalar_one_or_none()
        if not term:
            raise ParentServiceError("Term not found", code="term_not_found")

        # Fetch exam scores for this student and term (only published exams)
        exam_scores_result = await self.db.execute(
            select(ExamScore)
            .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .where(
                and_(
                    ExamScore.student_id == student_id,
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.deleted_at.is_(None),
                    Exam.term_id == term_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                    # Only show published results to parents
                    Exam.status == "results_published",
                )
            )
            .options(
                joinedload(ExamScore.exam_subject).joinedload(ExamSubject.subject),
                joinedload(ExamScore.exam_subject).joinedload(ExamSubject.exam),
            )
        )
        exam_scores = exam_scores_result.scalars().unique().all()

        # Fetch continuous assessments for this student and term
        ca_result = await self.db.execute(
            select(ContinuousAssessment)
            .where(
                and_(
                    ContinuousAssessment.student_id == student_id,
                    ContinuousAssessment.term_id == term_id,
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.deleted_at.is_(None),
                )
            )
            .options(joinedload(ContinuousAssessment.subject))
        )
        ca_scores = ca_result.scalars().unique().all()

        # Aggregate CA scores by subject: sum(score) / sum(max_score) for each subject
        ca_by_subject: dict[UUID, dict] = {}
        for ca in ca_scores:
            sid = ca.subject_id
            if sid not in ca_by_subject:
                ca_by_subject[sid] = {"total_score": Decimal("0"), "total_max": Decimal("0")}
            if ca.score is not None:
                ca_by_subject[sid]["total_score"] += ca.score
                ca_by_subject[sid]["total_max"] += ca.max_score

        # Aggregate exam scores by subject (use the latest/highest-weight exam per subject)
        exam_by_subject: dict[UUID, dict] = {}
        for es in exam_scores:
            sid = es.exam_subject.subject_id
            if sid not in exam_by_subject:
                exam_by_subject[sid] = {
                    "score": es.score,
                    "max_score": es.exam_subject.max_score,
                    "grade": es.grade,
                    "remark": es.grade_remark,
                    "subject_name": es.exam_subject.subject.name,
                }
            else:
                # If multiple exam scores exist for same subject in same term,
                # keep the one from the most recent exam
                existing = exam_by_subject[sid]
                if es.score is not None and (existing["score"] is None or es.score > existing["score"]):
                    exam_by_subject[sid] = {
                        "score": es.score,
                        "max_score": es.exam_subject.max_score,
                        "grade": es.grade,
                        "remark": es.grade_remark,
                        "subject_name": es.exam_subject.subject.name,
                    }

        # Build per-subject grade list, also collecting CA subject names
        ca_subject_names: dict[UUID, str] = {}
        for ca in ca_scores:
            if ca.subject_id not in ca_subject_names:
                ca_subject_names[ca.subject_id] = ca.subject.name

        # Union of all subject IDs from both exams and CAs
        all_subject_ids = set(exam_by_subject.keys()) | set(ca_by_subject.keys())

        # Get class averages for context (from term report if available)
        class_avg_map = await self._get_class_averages_for_term(
            tenant_id, term_id, student.class_id
        )

        subjects = []
        total_marks = Decimal("0")
        subjects_with_scores = 0

        for sid in sorted(all_subject_ids, key=lambda x: str(x)):
            exam_data = exam_by_subject.get(sid)
            ca_data = ca_by_subject.get(sid)

            subject_name = (
                exam_data["subject_name"] if exam_data
                else ca_subject_names.get(sid, "Unknown")
            )

            ca_score = None
            ca_max = None
            if ca_data and ca_data["total_max"] > 0:
                ca_score = ca_data["total_score"]
                ca_max = ca_data["total_max"]

            exam_score = exam_data["score"] if exam_data else None
            exam_max = exam_data["max_score"] if exam_data else None

            # Calculate total: sum of CA + exam (raw totals, not weighted here)
            total = None
            if ca_score is not None or exam_score is not None:
                total = (ca_score or Decimal("0")) + (exam_score or Decimal("0"))
                total_marks += total
                subjects_with_scores += 1

            subjects.append({
                "subject_name": subject_name,
                "ca_score": ca_score,
                "ca_max": ca_max,
                "exam_score": exam_score,
                "exam_max": exam_max,
                "total": total,
                "grade": exam_data["grade"] if exam_data else None,
                "remark": exam_data["remark"] if exam_data else None,
                "class_average": class_avg_map.get(sid),
                "position": None,  # Filled from term report below
            })

        # Try to get position and class size from term report
        term_report = await self._get_student_term_report(
            tenant_id, term_id, student_id
        )

        class_position = None
        class_size = None
        average = None

        if term_report:
            class_position = term_report.class_position
            class_size = term_report.class_size
            average = term_report.average_score
        elif subjects_with_scores > 0:
            average = total_marks / Decimal(str(subjects_with_scores))

        child_summary = {
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "photo_url": student.photo_url,
            "class_name": student.class_.name if student.class_ else None,
            "section_name": student.section.name if student.section else None,
            "admission_number": student.admission_number,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender.value if student.gender else None,
        }

        return {
            "student": child_summary,
            "term_id": term_id,
            "term_name": term.name,
            "academic_year": term.academic_year.name if term.academic_year else None,
            "subjects": subjects,
            "overall": {
                "total_marks": total_marks if subjects_with_scores > 0 else None,
                "average": round(average, 2) if average is not None else None,
                "class_position": class_position,
                "class_size": class_size,
            },
        }

    async def _get_class_averages_for_term(
        self, tenant_id: UUID, term_id: UUID, class_id: Optional[UUID]
    ) -> dict[UUID, Decimal]:
        """
        Get per-subject class averages from exam scores for a term.

        Returns a dict of subject_id -> average_score across all students
        in the class for that term (published exams only).
        """
        if not class_id:
            return {}

        result = await self.db.execute(
            select(
                ExamSubject.subject_id,
                func.avg(ExamScore.score).label("avg_score"),
            )
            .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .where(
                and_(
                    Exam.term_id == term_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                    Exam.status == "results_published",
                    ExamSubject.class_id == class_id,
                    ExamSubject.tenant_id == tenant_id,
                    ExamScore.tenant_id == tenant_id,
                    ExamScore.deleted_at.is_(None),
                    ExamScore.is_absent == False,
                    ExamScore.score.isnot(None),
                )
            )
            .group_by(ExamSubject.subject_id)
        )
        return {
            row.subject_id: round(Decimal(str(row.avg_score)), 2)
            for row in result.all()
        }

    async def _get_student_term_report(
        self, tenant_id: UUID, term_id: UUID, student_id: UUID
    ) -> Optional[TermReport]:
        """
        Get the published term report for a student, if one exists.

        Only returns published reports (is_published=True) so parents
        cannot see draft/unpublished report data.
        """
        result = await self.db.execute(
            select(TermReport)
            .where(
                and_(
                    TermReport.tenant_id == tenant_id,
                    TermReport.term_id == term_id,
                    TermReport.student_id == student_id,
                    TermReport.deleted_at.is_(None),
                    # Only show published reports to parents
                    TermReport.is_published == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_child_grade_trend(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """
        Get grade trend across all available terms for charting.

        Returns average score and position from published term reports,
        ordered chronologically by term sequence.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)

        Returns:
            List of dicts matching GradeTrend schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        # Get all published term reports for this student, ordered by term sequence
        result = await self.db.execute(
            select(TermReport)
            .where(
                and_(
                    TermReport.student_id == student_id,
                    TermReport.tenant_id == tenant_id,
                    TermReport.deleted_at.is_(None),
                    TermReport.is_published == True,
                )
            )
            .options(
                joinedload(TermReport.term),
                joinedload(TermReport.academic_year),
            )
            .order_by(TermReport.created_at)
        )
        reports = result.scalars().unique().all()

        trend = []
        for report in reports:
            trend.append({
                "term_id": report.term_id,
                "term_name": report.term.name if report.term else "Unknown",
                "average": report.average_score,
                "position": report.class_position,
                "class_size": report.class_size,
            })

        return trend

    async def get_child_report_card_pdf(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
        term_id: UUID,
    ) -> tuple[bytes, str]:
        """
        Download term report as PDF after verifying parent access.

        Delegates PDF generation to the existing PDFService. Only
        published term reports can be downloaded by parents.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)
            term_id: The term to download the report for

        Returns:
            Tuple of (pdf_bytes, filename)

        Raises:
            ParentServiceError: If access denied, report not found, or not published
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        # Find the published term report for this student and term
        report_result = await self.db.execute(
            select(TermReport)
            .where(
                and_(
                    TermReport.student_id == student_id,
                    TermReport.term_id == term_id,
                    TermReport.tenant_id == tenant_id,
                    TermReport.deleted_at.is_(None),
                )
            )
        )
        report = report_result.scalar_one_or_none()

        if not report:
            raise ParentServiceError(
                "Term report not found for this student and term",
                code="report_not_found",
            )

        if not report.is_published:
            raise ParentServiceError(
                "This report card has not been published yet",
                code="report_not_published",
            )

        # Delegate to the existing PDF service
        from app.services.pdf import PDFService

        pdf_bytes, filename = await PDFService.generate_term_report_pdf(
            db=self.db,
            tenant_id=tenant_id,
            report_id=report.id,
        )
        return pdf_bytes, filename

    async def get_child_assessments(
        self,
        user_id: UUID,
        student_id: UUID,
        tenant_id: UUID,
        term_id: UUID,
    ) -> list[dict]:
        """
        Get continuous assessment scores for a child in a specific term.

        Returns individual CA entries (class work, homework, tests, projects)
        across all subjects for the given term.

        Args:
            user_id: The authenticated parent's user ID
            student_id: The child's student ID
            tenant_id: Tenant ID (defense-in-depth with RLS)
            term_id: The term to fetch assessments for

        Returns:
            List of dicts matching AssessmentScore schema

        Raises:
            ParentServiceError: If access denied
        """
        await self._parent.require_parent_child_access(
            user_id, student_id, tenant_id
        )

        result = await self.db.execute(
            select(ContinuousAssessment)
            .where(
                and_(
                    ContinuousAssessment.student_id == student_id,
                    ContinuousAssessment.term_id == term_id,
                    ContinuousAssessment.tenant_id == tenant_id,
                    ContinuousAssessment.deleted_at.is_(None),
                )
            )
            .options(joinedload(ContinuousAssessment.subject))
            .order_by(
                ContinuousAssessment.assessment_date.desc(),
                ContinuousAssessment.title,
            )
        )
        assessments = result.scalars().unique().all()

        return [
            {
                "id": ca.id,
                "subject_name": ca.subject.name if ca.subject else "Unknown",
                "assessment_name": ca.title,
                "score": ca.score,
                "max_score": ca.max_score,
                "date": ca.assessment_date,
            }
            for ca in assessments
        ]

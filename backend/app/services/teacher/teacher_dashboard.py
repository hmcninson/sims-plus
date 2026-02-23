"""
SIMS Plus - Teacher Dashboard Service

Aggregates data from multiple teacher services into a unified dashboard
response: class assignments, subject assignments, today's schedule,
and pending tasks (score entries, report comments).
"""

from datetime import date
from uuid import UUID

import structlog
from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicYear,
    Class,
    ClassSection,
    ClassSubject,
    ClassTimetable,
    Subject,
    Term,
)
from app.models.exam import (
    Exam,
    ExamScore,
    ExamStatus,
    ExamSubject,
    ExamSubjectStatus,
)
from app.models.staff import Staff, StaffClassAssignment
from app.models.student import Student, StudentStatus
from app.models.teacher import LessonPlan, LessonPlanStatus, ReportComment

from ._shared import TeacherServiceError
from .teacher_schedule import TeacherScheduleService

logger = structlog.get_logger()


class TeacherDashboardService:
    """
    Composes dashboard data from teacher context, schedule, and grading services.

    Provides a single method that returns all data needed for the teacher dashboard.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard(
        self,
        staff: Staff,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID | None = None,
    ) -> dict:
        """
        Build the complete teacher dashboard.

        Aggregates:
        - Teacher profile info
        - Class assignments with student counts
        - Subject assignments with class counts
        - Today's schedule from timetable
        - Pending tasks (scores to enter, report comments to write)
        """
        staff_id = staff.id

        # Get class assignments
        classes = await self._get_class_summaries(staff_id, tenant_id)

        # Get subject assignments
        subjects = await self._get_subject_summaries(staff_id, tenant_id)

        # Total students across all assigned sections
        total_students = sum(c.get("student_count", 0) for c in classes)

        # Today's schedule
        schedule_service = TeacherScheduleService(self.db)
        today_schedule = await schedule_service.get_today_schedule(
            staff_id=staff_id,
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
        )

        # Pending tasks
        pending_tasks = await self._get_pending_tasks(
            staff_id=staff_id,
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
        )

        return {
            "teacher_name": staff.full_name,
            "staff_id": staff.staff_id,
            "total_classes": len(classes),
            "total_subjects": len(subjects),
            "total_students": total_students,
            "classes": classes,
            "subjects": subjects,
            "today_schedule": today_schedule,
            "pending_tasks": pending_tasks,
        }

    async def _get_class_summaries(
        self, staff_id: UUID, tenant_id: UUID
    ) -> list[dict]:
        """Get class assignment summaries with student counts."""
        # Get section assignments
        assignments_result = await self.db.execute(
            select(
                StaffClassAssignment.section_id,
                StaffClassAssignment.is_class_teacher,
                ClassSection.class_id,
                ClassSection.name.label("section_name"),
                Class.name.label("class_name"),
            )
            .join(ClassSection, StaffClassAssignment.section_id == ClassSection.id)
            .join(Class, ClassSection.class_id == Class.id)
            .where(
                and_(
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                    ClassSection.deleted_at.is_(None),
                    Class.deleted_at.is_(None),
                )
            )
        )
        assignments = assignments_result.all()

        if not assignments:
            return []

        section_ids = [a.section_id for a in assignments]

        # Count students per section
        counts_result = await self.db.execute(
            select(Student.section_id, func.count(Student.id))
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
        counts = dict(counts_result.all())

        return [
            {
                "class_id": a.class_id,
                "class_name": a.class_name,
                "section_id": a.section_id,
                "section_name": a.section_name,
                "student_count": counts.get(a.section_id, 0),
                "is_class_teacher": a.is_class_teacher,
            }
            for a in assignments
        ]

    async def _get_subject_summaries(
        self, staff_id: UUID, tenant_id: UUID
    ) -> list[dict]:
        """Get subject assignment summaries with class counts."""
        result = await self.db.execute(
            select(
                Subject.id,
                Subject.name,
                func.count(distinct(ClassSubject.class_id)).label("class_count"),
            )
            .join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .where(
                and_(
                    ClassSubject.teacher_id == staff_id,
                    ClassSubject.tenant_id == tenant_id,
                    Subject.deleted_at.is_(None),
                )
            )
            .group_by(Subject.id, Subject.name)
        )
        subjects = result.all()

        return [
            {
                "subject_id": s.id,
                "subject_name": s.name,
                "class_count": s.class_count,
            }
            for s in subjects
        ]

    async def _get_pending_tasks(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID | None = None,
    ) -> list[dict]:
        """
        Collect pending tasks that need the teacher's attention.

        Checks for:
        - Pending exam score entries
        - Unsigned report comments (for class teachers)
        - Lesson plans not yet marked as taught
        """
        tasks = []

        # 1. Pending score entries
        pending_scores = await self._count_pending_scores(
            staff_id, tenant_id, academic_year_id, term_id,
        )
        if pending_scores > 0:
            tasks.append({
                "task_type": "score_entry",
                "description": f"{pending_scores} exam subject(s) need score entry",
                "count": pending_scores,
                "link_context": None,
            })

        # 2. Unsigned report comments (only for class teachers)
        unsigned_comments = await self._count_unsigned_comments(
            staff_id, tenant_id, term_id,
        )
        if unsigned_comments > 0:
            tasks.append({
                "task_type": "report_comment",
                "description": f"{unsigned_comments} student report(s) need your comment",
                "count": unsigned_comments,
                "link_context": None,
            })

        # 3. Lesson plans for today not yet taught
        untaught_plans = await self._count_untaught_lesson_plans(
            staff_id, tenant_id,
        )
        if untaught_plans > 0:
            tasks.append({
                "task_type": "lesson_plan",
                "description": f"{untaught_plans} lesson plan(s) for today not yet taught",
                "count": untaught_plans,
                "link_context": None,
            })

        return tasks

    async def _count_pending_scores(
        self, staff_id: UUID, tenant_id: UUID,
        academic_year_id: UUID, term_id: UUID | None,
    ) -> int:
        """Count exam subjects where this teacher has pending score entry."""
        # Get teacher's class-subject combos
        cs_result = await self.db.execute(
            select(ClassSubject.class_id, ClassSubject.subject_id)
            .where(
                and_(
                    ClassSubject.teacher_id == staff_id,
                    ClassSubject.tenant_id == tenant_id,
                )
            )
        )
        pairs = cs_result.all()
        if not pairs:
            return 0

        pair_filters = [
            and_(
                ExamSubject.class_id == p.class_id,
                ExamSubject.subject_id == p.subject_id,
            )
            for p in pairs
        ]

        query = (
            select(func.count(ExamSubject.id))
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .where(
                and_(
                    ExamSubject.tenant_id == tenant_id,
                    Exam.academic_year_id == academic_year_id,
                    Exam.status.in_([
                        ExamStatus.SCHEDULED,
                        ExamStatus.ONGOING,
                        ExamStatus.COMPLETED,
                    ]),
                    ExamSubject.status.in_([
                        ExamSubjectStatus.PENDING,
                        ExamSubjectStatus.SCORES_ENTERED,
                    ]),
                    or_(*pair_filters),
                    Exam.deleted_at.is_(None),
                )
            )
        )
        if term_id:
            query = query.where(Exam.term_id == term_id)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def _count_unsigned_comments(
        self, staff_id: UUID, tenant_id: UUID, term_id: UUID | None,
    ) -> int:
        """
        Count students in class-teacher sections that still need report comments.

        Only relevant for sections where this teacher is the class teacher.
        """
        # Get sections where this teacher is class teacher
        ct_result = await self.db.execute(
            select(StaffClassAssignment.section_id)
            .where(
                and_(
                    StaffClassAssignment.staff_id == staff_id,
                    StaffClassAssignment.tenant_id == tenant_id,
                    StaffClassAssignment.is_class_teacher.is_(True),
                )
            )
        )
        ct_sections = [r for r in ct_result.scalars().all()]
        if not ct_sections or not term_id:
            return 0

        # Count students in those sections without signed report comments
        student_count = (await self.db.execute(
            select(func.count(Student.id))
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.section_id.in_(ct_sections),
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                )
            )
        )).scalar_one()

        # Count existing signed comments
        signed_count = (await self.db.execute(
            select(func.count(ReportComment.id))
            .where(
                and_(
                    ReportComment.tenant_id == tenant_id,
                    ReportComment.term_id == term_id,
                    ReportComment.class_teacher_signed.is_(True),
                    ReportComment.deleted_at.is_(None),
                    # Only count for students in this teacher's sections
                    ReportComment.student_id.in_(
                        select(Student.id)
                        .where(
                            and_(
                                Student.tenant_id == tenant_id,
                                Student.section_id.in_(ct_sections),
                                Student.status == StudentStatus.ACTIVE,
                                Student.deleted_at.is_(None),
                            )
                        )
                    ),
                )
            )
        )).scalar_one()

        return max(0, student_count - signed_count)

    async def _count_untaught_lesson_plans(
        self, staff_id: UUID, tenant_id: UUID,
    ) -> int:
        """Count lesson plans for today that are still in 'planned' status."""
        today = date.today()
        result = await self.db.execute(
            select(func.count(LessonPlan.id))
            .where(
                and_(
                    LessonPlan.tenant_id == tenant_id,
                    LessonPlan.teacher_id == staff_id,
                    LessonPlan.date == today,
                    LessonPlan.status == LessonPlanStatus.PLANNED,
                    LessonPlan.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one()

"""
SIMS Plus - Teacher Performance Service (Head Teacher View)

Provides performance metrics for all teaching staff, visible to
head teachers (school_admin role). Tracks lesson plan completion,
score entry progress, notes created, and reports signed.
"""

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import ClassSubject
from app.models.exam import (
    Exam,
    ExamSubject,
    ExamSubjectStatus,
)
from app.models.parent import TeacherNote
from app.models.staff import Staff, StaffType
from app.models.teacher import LessonPlan, LessonPlanStatus, ReportComment

from ._shared import TeacherServiceError

logger = structlog.get_logger()


class TeacherPerformanceService:
    """
    Aggregated performance metrics for teaching staff.

    Intended for head teachers / school admins to monitor:
    - Lesson plan creation and completion rates
    - Score entry progress
    - Teacher note activity
    - Report comment sign-off rates
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_performance_summary(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID | None = None,
    ) -> dict:
        """
        Get performance metrics for all teaching staff.

        Returns per-teacher metrics and overall summary statistics.
        """
        # Get all active teaching staff
        staff_result = await self.db.execute(
            select(Staff)
            .where(
                and_(
                    Staff.tenant_id == tenant_id,
                    Staff.staff_type == StaffType.TEACHING,
                    Staff.status == "active",
                    Staff.deleted_at.is_(None),
                )
            )
            .order_by(Staff.last_name, Staff.first_name)
        )
        all_staff = staff_result.scalars().all()

        if not all_staff:
            return {
                "total_teachers": 0,
                "teachers": [],
                "overall_lesson_plan_completion": None,
                "overall_score_entry_completion": None,
            }

        staff_ids = [s.id for s in all_staff]

        # Lesson plans per teacher
        plans_result = await self.db.execute(
            select(
                LessonPlan.teacher_id,
                func.count(LessonPlan.id).label("total"),
                func.count(LessonPlan.id).filter(
                    LessonPlan.status == LessonPlanStatus.TAUGHT
                ).label("taught"),
            )
            .where(
                and_(
                    LessonPlan.tenant_id == tenant_id,
                    LessonPlan.teacher_id.in_(staff_ids),
                    LessonPlan.deleted_at.is_(None),
                )
            )
            .group_by(LessonPlan.teacher_id)
        )
        plans_by_teacher = {
            row.teacher_id: {"total": row.total, "taught": row.taught}
            for row in plans_result.all()
        }

        # Scores entered per teacher (via ClassSubject teacher assignment)
        # Batch query: join ClassSubject -> ExamSubject -> Exam, group by teacher_id
        entered_result = await self.db.execute(
            select(
                ClassSubject.teacher_id,
                func.count(distinct(ExamSubject.id)).label("entered"),
            )
            .join(
                ExamSubject,
                and_(
                    ExamSubject.class_id == ClassSubject.class_id,
                    ExamSubject.subject_id == ClassSubject.subject_id,
                    ExamSubject.tenant_id == ClassSubject.tenant_id,
                ),
            )
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.teacher_id.in_(staff_ids),
                    Exam.academic_year_id == academic_year_id,
                    ExamSubject.status.in_([
                        ExamSubjectStatus.SCORES_ENTERED,
                        ExamSubjectStatus.SUBMITTED,
                        ExamSubjectStatus.PUBLISHED,
                    ]),
                    Exam.deleted_at.is_(None),
                )
            )
            .group_by(ClassSubject.teacher_id)
        )
        entered_by_teacher = dict(entered_result.all())

        pending_result = await self.db.execute(
            select(
                ClassSubject.teacher_id,
                func.count(distinct(ExamSubject.id)).label("pending"),
            )
            .join(
                ExamSubject,
                and_(
                    ExamSubject.class_id == ClassSubject.class_id,
                    ExamSubject.subject_id == ClassSubject.subject_id,
                    ExamSubject.tenant_id == ClassSubject.tenant_id,
                ),
            )
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.teacher_id.in_(staff_ids),
                    Exam.academic_year_id == academic_year_id,
                    ExamSubject.status == ExamSubjectStatus.PENDING,
                    Exam.deleted_at.is_(None),
                )
            )
            .group_by(ClassSubject.teacher_id)
        )
        pending_by_teacher = dict(pending_result.all())

        scores_by_teacher: dict[UUID, dict] = {}
        for sid in staff_ids:
            scores_by_teacher[sid] = {
                "entered": entered_by_teacher.get(sid, 0),
                "pending": pending_by_teacher.get(sid, 0),
            }

        # Teacher notes count per teacher
        notes_result = await self.db.execute(
            select(
                TeacherNote.teacher_id,
                func.count(TeacherNote.id).label("count"),
            )
            .where(
                and_(
                    TeacherNote.tenant_id == tenant_id,
                    TeacherNote.teacher_id.in_([s.user_id for s in all_staff if s.user_id]),
                    TeacherNote.deleted_at.is_(None),
                )
            )
            .group_by(TeacherNote.teacher_id)
        )
        # Map user_id -> count for notes
        notes_by_user = dict(notes_result.all())
        # Remap to staff_id
        notes_by_staff: dict[UUID, int] = {}
        for s in all_staff:
            if s.user_id and s.user_id in notes_by_user:
                notes_by_staff[s.id] = notes_by_user[s.user_id]

        # Report comments signed per teacher (as class_teacher)
        reports_result = await self.db.execute(
            select(
                ReportComment.class_teacher_id,
                func.count(ReportComment.id).label("count"),
            )
            .where(
                and_(
                    ReportComment.tenant_id == tenant_id,
                    ReportComment.class_teacher_id.in_(staff_ids),
                    ReportComment.class_teacher_signed.is_(True),
                    ReportComment.deleted_at.is_(None),
                )
            )
            .group_by(ReportComment.class_teacher_id)
        )
        reports_by_teacher = dict(reports_result.all())

        # Batch query: class and subject counts per teacher in two grouped queries
        class_count_result = await self.db.execute(
            select(
                ClassSubject.teacher_id,
                func.count(distinct(ClassSubject.class_id)).label("class_count"),
            )
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.teacher_id.in_(staff_ids),
                )
            )
            .group_by(ClassSubject.teacher_id)
        )
        class_counts = dict(class_count_result.all())

        subject_count_result = await self.db.execute(
            select(
                ClassSubject.teacher_id,
                func.count(distinct(ClassSubject.subject_id)).label("subject_count"),
            )
            .where(
                and_(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.teacher_id.in_(staff_ids),
                )
            )
            .group_by(ClassSubject.teacher_id)
        )
        subject_counts = dict(subject_count_result.all())

        # Build per-teacher metrics
        teachers = []
        total_plans = 0
        total_taught = 0
        total_entered = 0
        total_pending = 0

        for staff in all_staff:
            plans = plans_by_teacher.get(staff.id, {"total": 0, "taught": 0})
            scores = scores_by_teacher.get(staff.id, {"entered": 0, "pending": 0})

            total_plans += plans["total"]
            total_taught += plans["taught"]
            total_entered += scores["entered"]
            total_pending += scores["pending"]

            teachers.append({
                "staff_id": staff.id,
                "teacher_name": staff.full_name,
                "total_classes": class_counts.get(staff.id, 0),
                "total_subjects": subject_counts.get(staff.id, 0),
                "total_students": 0,  # Can be computed if needed
                "lesson_plans_created": plans["total"],
                "lesson_plans_taught": plans["taught"],
                "scores_entered": scores["entered"],
                "scores_pending": scores["pending"],
                "notes_created": notes_by_staff.get(staff.id, 0),
                "reports_signed": reports_by_teacher.get(staff.id, 0),
            })

        # Overall completion rates
        overall_lp = None
        if total_plans > 0:
            overall_lp = Decimal(str(total_taught / total_plans * 100)).quantize(Decimal("0.01"))

        overall_se = None
        total_score_items = total_entered + total_pending
        if total_score_items > 0:
            overall_se = Decimal(str(total_entered / total_score_items * 100)).quantize(Decimal("0.01"))

        return {
            "total_teachers": len(all_staff),
            "teachers": teachers,
            "overall_lesson_plan_completion": overall_lp,
            "overall_score_entry_completion": overall_se,
        }

"""
SIMS Plus - Term Report Service

Business logic for generating and managing term reports (report cards).
"""

from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, desc, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.notification import NotificationCategory, NotificationType
from app.models.exam import (
    Exam,
    ExamType,
    ExamSubject,
    ExamScore,
    ContinuousAssessment,
    TermReport,
)
from app.models.academic import (
    Class,
    Term,
    Subject,
    GradingScale,
    Grade,
    AssessmentWeight,
    SchoolHoliday,
)
from app.models.student import Student
from app.models.attendance import StudentAttendance, AttendanceStatus
from app.models.curriculum import (
    AssessmentComponent,
    AssessmentStructure,
    CurriculumProfile,
)
from app.models.school import School
from app.services.exam.score_strategies import get_score_strategy, SubjectScoreResult


logger = structlog.get_logger()


class TermReportService:
    """Service for generating and managing term reports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Curriculum Resolution (Phase 1 prep for Phase 2 score engine)
    # =========================

    async def _resolve_curriculum_profile(
        self,
        tenant_id: UUID,
        class_id: UUID,
        student_id: UUID | None = None,
    ) -> CurriculumProfile | None:
        """
        Resolve the curriculum profile for a class/student.

        Resolution chain:
        1. student.curriculum_profile_id (if student_id provided)
        2. class.curriculum_profile_id
        3. school.curriculum_profile_id (via class.school_id)
        4. None (fall back to GES default logic)

        This method is added in Phase 1 but only used by the score
        engine refactor in Phase 2. Adding it now avoids merge conflicts.
        """
        # 1. Check student override
        if student_id:
            stmt = select(Student.curriculum_profile_id).where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
            )
            result = await self.db.execute(stmt)
            student_profile_id = result.scalar_one_or_none()
            if student_profile_id:
                return await self._load_profile(tenant_id, student_profile_id)

        # 2. Check class
        stmt = select(Class.curriculum_profile_id, Class.school_id).where(
            Class.tenant_id == tenant_id,
            Class.id == class_id,
        )
        result = await self.db.execute(stmt)
        row = result.one_or_none()
        if row and row.curriculum_profile_id:
            return await self._load_profile(tenant_id, row.curriculum_profile_id)

        # 3. Check school
        if row and row.school_id:
            stmt = select(School.curriculum_profile_id).where(
                School.tenant_id == tenant_id,
                School.id == row.school_id,
            )
            result = await self.db.execute(stmt)
            school_profile_id = result.scalar_one_or_none()
            if school_profile_id:
                return await self._load_profile(tenant_id, school_profile_id)

        # 4. No profile found -- fall back to GES default logic
        return None

    async def _load_profile(
        self, tenant_id: UUID, profile_id: UUID
    ) -> CurriculumProfile | None:
        """Load a curriculum profile with its grading scale."""
        stmt = (
            select(CurriculumProfile)
            .where(
                CurriculumProfile.tenant_id == tenant_id,
                CurriculumProfile.id == profile_id,
                CurriculumProfile.is_active == True,
                CurriculumProfile.deleted_at.is_(None),
            )
            .options(selectinload(CurriculumProfile.grading_scale))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_assessment_structure(
        self,
        profile: CurriculumProfile,
        academic_year_id: UUID | None,
    ) -> AssessmentStructure | None:
        """
        Resolve the active assessment structure for a curriculum profile.

        Prefers a year-specific structure when academic_year_id is provided,
        falling back to the default (NULL academic_year_id) structure.
        Components are eagerly loaded so callers can iterate immediately.
        """
        # Try year-specific structure first
        if academic_year_id:
            result = await self.db.execute(
                select(AssessmentStructure)
                .where(
                    AssessmentStructure.tenant_id == profile.tenant_id,
                    AssessmentStructure.curriculum_profile_id == profile.id,
                    AssessmentStructure.academic_year_id == academic_year_id,
                    AssessmentStructure.is_active == True,
                    AssessmentStructure.deleted_at.is_(None),
                )
                .options(selectinload(AssessmentStructure.components))
            )
            structure = result.scalar_one_or_none()
            if structure:
                return structure

        # Fall back to default structure (NULL academic_year_id)
        result = await self.db.execute(
            select(AssessmentStructure)
            .where(
                AssessmentStructure.tenant_id == profile.tenant_id,
                AssessmentStructure.curriculum_profile_id == profile.id,
                AssessmentStructure.academic_year_id.is_(None),
                AssessmentStructure.is_active == True,
                AssessmentStructure.deleted_at.is_(None),
            )
            .options(selectinload(AssessmentStructure.components))
        )
        return result.scalar_one_or_none()

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

        Dispatches to curriculum-aware strategy if a curriculum profile is
        resolved for the class/student, otherwise falls back to the legacy
        GES scoring logic unchanged.

        Returns (total_score, average_score, subjects_count)
        """
        # Resolve curriculum profile for strategy dispatch
        profile = await self._resolve_curriculum_profile(
            tenant_id, class_id, student_id
        )

        if profile is not None:
            structure = await self._get_assessment_structure(
                profile, academic_year_id
            )
            if structure is not None:
                # Curriculum-aware path -- use the score strategy
                return await self._calculate_student_term_scores_curriculum(
                    tenant_id=tenant_id,
                    term_id=term_id,
                    student_id=student_id,
                    class_id=class_id,
                    academic_year_id=academic_year_id,
                    profile=profile,
                    structure=structure,
                )

        # Legacy GES path -- unchanged scoring logic
        return await self._calculate_student_term_scores_legacy(
            tenant_id=tenant_id,
            term_id=term_id,
            student_id=student_id,
            class_id=class_id,
            academic_year_id=academic_year_id,
        )

    async def _calculate_student_term_scores_curriculum(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
        class_id: UUID,
        academic_year_id: Optional[UUID],
        profile: CurriculumProfile,
        structure: AssessmentStructure,
    ) -> tuple[Decimal | None, Decimal | None, int]:
        """
        Curriculum-aware term score calculation using the strategy pattern.

        Delegates per-subject scoring to the appropriate ScoreStrategy,
        then sums across subjects for total and average.
        """
        strategy = get_score_strategy(profile.curriculum_type.value)
        components = structure.components

        # Get term info for academic_year_id if not provided
        if not academic_year_id:
            term_result = await self.db.execute(
                select(Term.academic_year_id).where(
                    and_(Term.id == term_id, Term.tenant_id == tenant_id)
                )
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

        all_exam_ids = [e[0] for e in exams]

        # Get all subjects assigned to exams for this class
        subjects_result = await self.db.execute(
            select(ExamSubject.subject_id).where(
                and_(
                    ExamSubject.tenant_id == tenant_id,
                    ExamSubject.exam_id.in_(all_exam_ids),
                    ExamSubject.class_id == class_id,
                )
            ).distinct()
        )
        subject_ids = [s[0] for s in subjects_result.all()]
        if not subject_ids:
            return None, None, 0

        # Build max_scores from component definitions
        max_scores: dict[str, Decimal] = {}
        for comp in components:
            max_scores[comp.component_type.value] = comp.max_score or Decimal("100")

        # For each subject, gather component scores and run through strategy
        total_score = Decimal("0")
        subjects_with_scores = 0

        for subject_id in subject_ids:
            component_scores: dict[str, Decimal | None] = {}

            # Collect CA scores (mapped to CA components)
            ca_components = [c for c in components if c.maps_to_ca]
            if ca_components:
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
                if ca_row[0] is not None:
                    # Distribute CA total across CA component types
                    for comp in ca_components:
                        component_scores[comp.component_type.value] = ca_row[0]
                        max_scores[comp.component_type.value] = ca_row[1] or Decimal("10")

            # Collect exam scores (mapped to exam components)
            exam_components = [c for c in components if c.maps_to_exam]
            if exam_components:
                end_term_exam_ids = [e[0] for e in exams if e[1] == ExamType.END_TERM]
                if end_term_exam_ids:
                    exam_result = await self.db.execute(
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
                    exam_total = Decimal("0")
                    exam_max_total = Decimal("0")
                    for score, max_score in exam_result.all():
                        if score is not None:
                            exam_total += score
                            exam_max_total += max_score
                    if exam_max_total > 0:
                        for comp in exam_components:
                            component_scores[comp.component_type.value] = exam_total
                            max_scores[comp.component_type.value] = exam_max_total

            # Run through strategy
            result = strategy.calculate_subject_score(
                component_scores, components, max_scores
            )

            if result.final_score is not None:
                total_score += result.final_score
                subjects_with_scores += 1

        if subjects_with_scores == 0:
            return None, None, 0

        average_score = total_score / subjects_with_scores
        return total_score, average_score, subjects_with_scores

    async def _calculate_student_term_scores_legacy(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
        class_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> tuple[Decimal | None, Decimal | None, int]:
        """
        Legacy GES term score calculation -- UNCHANGED from original.

        Uses weighted scoring based on assessment weights:
        - CA (class work + homework) + midterm + end_term

        Returns (total_score, average_score, subjects_count)
        """
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
                select(Term.academic_year_id).where(
                    and_(Term.id == term_id, Term.tenant_id == tenant_id)
                )
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
                    ExamSubject.tenant_id == tenant_id,
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
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        term_result = await self.db.execute(
            select(Term).where(
                and_(Term.id == term_id, Term.tenant_id == tenant_id)
            )
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

        Dispatches to curriculum-aware strategy if a curriculum profile
        is resolved, otherwise falls back to the legacy GES logic.
        """
        # Resolve curriculum profile for strategy dispatch
        profile = await self._resolve_curriculum_profile(
            tenant_id, class_id, student_id
        )

        if profile is not None:
            structure = await self._get_assessment_structure(
                profile, academic_year_id
            )
            if structure is not None:
                return await self._get_student_subject_results_curriculum(
                    tenant_id=tenant_id,
                    term_id=term_id,
                    student_id=student_id,
                    class_id=class_id,
                    academic_year_id=academic_year_id,
                    section_id=section_id,
                    profile=profile,
                    structure=structure,
                )

        # Legacy GES path -- unchanged scoring logic
        return await self._get_student_subject_results_legacy(
            tenant_id=tenant_id,
            term_id=term_id,
            student_id=student_id,
            class_id=class_id,
            academic_year_id=academic_year_id,
            section_id=section_id,
        )

    async def _get_student_subject_results_curriculum(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
        class_id: UUID,
        academic_year_id: Optional[UUID],
        section_id: Optional[UUID],
        profile: CurriculumProfile,
        structure: AssessmentStructure,
    ) -> list[dict]:
        """
        Curriculum-aware subject results using the strategy pattern.

        Delegates per-subject scoring to the appropriate ScoreStrategy,
        then resolves grades from the profile's grading scale.
        """
        strategy = get_score_strategy(profile.curriculum_type.value)
        components = structure.components

        # Get the student's section_id if not provided
        if section_id is None:
            student_result = await self.db.execute(
                select(Student.section_id).where(
                    and_(Student.id == student_id, Student.tenant_id == tenant_id)
                )
            )
            section_id = student_result.scalar_one_or_none()

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

        all_exam_ids = [e[0] for e in exams]

        # Get all subjects with exam assignments for this class
        from sqlalchemy import or_
        subjects_result = await self.db.execute(
            select(Subject)
            .join(ExamSubject, ExamSubject.subject_id == Subject.id)
            .where(
                and_(
                    ExamSubject.exam_id.in_(all_exam_ids),
                    ExamSubject.class_id == class_id,
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

        # Resolve grading scale -- prefer profile's linked scale, fall back to tenant default
        grades: list[Grade] = []
        grading_scale_id = profile.grading_scale_id
        if grading_scale_id:
            grades_result = await self.db.execute(
                select(Grade)
                .where(Grade.grading_scale_id == grading_scale_id)
                .order_by(Grade.min_score.desc())
            )
            grades = list(grades_result.scalars().all())
        else:
            # Fall back to tenant default grading scale
            default_scale = await self.db.execute(
                select(GradingScale).where(
                    and_(
                        GradingScale.tenant_id == tenant_id,
                        GradingScale.is_default == True,
                    )
                )
            )
            scale = default_scale.scalar_one_or_none()
            if scale:
                grades_result = await self.db.execute(
                    select(Grade)
                    .where(Grade.grading_scale_id == scale.id)
                    .order_by(Grade.min_score.desc())
                )
                grades = list(grades_result.scalars().all())

        # Build max_scores from component definitions
        max_scores: dict[str, Decimal] = {}
        for comp in components:
            max_scores[comp.component_type.value] = comp.max_score or Decimal("100")

        subject_results: list[dict] = []

        for subject in subjects:
            component_scores: dict[str, Decimal | None] = {}

            # Collect CA scores (mapped to CA components)
            ca_components = [c for c in components if c.maps_to_ca]
            if ca_components:
                ca_result = await self.db.execute(
                    select(
                        func.sum(ContinuousAssessment.score),
                        func.sum(ContinuousAssessment.max_score),
                    ).where(
                        and_(
                            ContinuousAssessment.tenant_id == tenant_id,
                            ContinuousAssessment.term_id == term_id,
                            ContinuousAssessment.student_id == student_id,
                            ContinuousAssessment.subject_id == subject.id,
                            ContinuousAssessment.class_id == class_id,
                            ContinuousAssessment.score.isnot(None),
                        )
                    )
                )
                ca_row = ca_result.one()
                if ca_row[0] is not None:
                    for comp in ca_components:
                        component_scores[comp.component_type.value] = ca_row[0]
                        max_scores[comp.component_type.value] = ca_row[1] or Decimal("10")

            # Collect exam scores (mapped to exam components)
            exam_components = [c for c in components if c.maps_to_exam]
            if exam_components:
                end_term_exam_ids = [e[0] for e in exams if e[1] == ExamType.END_TERM]
                if end_term_exam_ids:
                    exam_result = await self.db.execute(
                        select(ExamScore.score, ExamSubject.max_score)
                        .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
                        .where(
                            and_(
                                ExamScore.tenant_id == tenant_id,
                                ExamScore.student_id == student_id,
                                ExamSubject.exam_id.in_(end_term_exam_ids),
                                ExamSubject.subject_id == subject.id,
                                ExamSubject.class_id == class_id,
                                or_(
                                    ExamSubject.section_id.is_(None),
                                    ExamSubject.section_id == section_id,
                                ),
                                ExamScore.is_absent == False,
                                ExamScore.score.isnot(None),
                            )
                        )
                    )
                    exam_total = Decimal("0")
                    exam_max_total = Decimal("0")
                    for score, max_score in exam_result.all():
                        if score is not None:
                            exam_total += score
                            exam_max_total += max_score
                    if exam_max_total > 0:
                        for comp in exam_components:
                            component_scores[comp.component_type.value] = exam_total
                            max_scores[comp.component_type.value] = exam_max_total

            # Run through strategy
            score_result = strategy.calculate_subject_score(
                component_scores, components, max_scores
            )

            # Determine grade from the score
            grade_label, grade_point, grade_remark = strategy.determine_grade(
                score_result.final_score, grades
            )

            has_scores = score_result.final_score is not None

            subject_results.append({
                "subject_id": str(subject.id),
                "subject_name": subject.name,
                "subject_code": subject.code,
                # Per-component scores for template rendering
                "component_scores": {
                    k: float(v) if v is not None else None
                    for k, v in component_scores.items()
                },
                # Strategy-computed scores
                "class_score": float(score_result.class_score.quantize(Decimal("0.01"))) if score_result.class_score else None,
                "exams_score": float(score_result.exams_score.quantize(Decimal("0.01"))) if score_result.exams_score else None,
                "total_score": float(score_result.final_score.quantize(Decimal("0.01"))) if has_scores else None,
                "grade": grade_label,
                "grade_remark": grade_remark,
                "grade_point": float(grade_point) if grade_point is not None else None,
                # Curriculum-specific extras
                "narrative": score_result.narrative,
                "effort_grade": score_result.effort_grade,
                # Position not calculated in curriculum path (yet); will be added in Phase 3
                "subject_position": None,
            })

        return subject_results

    async def _get_student_subject_results_legacy(
        self,
        tenant_id: UUID,
        term_id: UUID,
        student_id: UUID,
        class_id: UUID,
        academic_year_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
    ) -> list[dict]:
        """
        Legacy GES subject results -- UNCHANGED from original.

        Returns a list of subject results with CA, midterm, end_term breakdown.
        Includes subject_position ranking at the class/section level.
        """
        # Get the student's section_id if not provided
        if section_id is None:
            student_result = await self.db.execute(
                select(Student.section_id).where(
                    and_(Student.id == student_id, Student.tenant_id == tenant_id)
                )
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
        # This reduces queries from (subjects x 4) to just 4 queries total

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
        generated_by: Optional[UUID] = None,
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

        await self.db.flush()

        # Refresh all reports
        for report in reports:
            await self.db.refresh(report)

        # Best-effort notification for the user who generated the reports
        if generated_by and reports:
            try:
                from app.services.notification import NotificationService
                notification_svc = NotificationService(self.db)
                count = len(reports)
                report_word = "report" if count == 1 else "reports"
                await notification_svc.create(
                    tenant_id=tenant_id,
                    user_id=generated_by,
                    title="Term Reports Generated",
                    message=f"{count} term {report_word} generated successfully.",
                    type=NotificationType.SUCCESS,
                    category=NotificationCategory.EXAM,
                    reference_type="term_report",
                )
            except Exception:
                logger.warning("notification_create_failed", exc_info=True)

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

        await self.db.flush()

        # Raw SQL updates bypass the identity map, so expire all cached
        # TermReport instances to ensure subsequent queries return fresh data.
        self.db.expire_all()

    async def get_term_report(
        self, tenant_id: UUID, report_id: UUID
    ) -> Optional[TermReport]:
        """Get term report by ID."""
        result = await self.db.execute(
            select(TermReport)
            .where(
                and_(
                    TermReport.id == report_id,
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    TermReport.tenant_id == tenant_id,
                    TermReport.deleted_at.is_(None),
                )
            )
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
        query = select(TermReport).where(
            and_(
                TermReport.tenant_id == tenant_id,
                TermReport.deleted_at.is_(None),
            )
        )

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
        report = await self.get_term_report(tenant_id, report_id)
        if not report:
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
        await self.db.flush()
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
                TermReport.deleted_at.is_(None),
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

        await self.db.flush()
        return count

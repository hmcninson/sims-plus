"""
SIMS Plus - Analytics Service

Business logic for exam analytics, statistics, timetabling, and conflict detection.
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.exam import (
    Exam,
    ExamSubject,
    ExamSubjectStatus,
    ExamScore,
)
from app.models.academic import (
    Class,
    ClassSection,
    Subject,
)

from app.services.exam.exam_service import ExamServiceError


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
        # Get exam and class info (filter soft-deleted)
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
        if not exam:
            return None

        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        class_result = await self.db.execute(
            select(Class).where(
                and_(Class.id == class_id, Class.tenant_id == tenant_id)
            )
        )
        class_obj = class_result.scalar_one_or_none()
        if not class_obj:
            return None

        # Build query for exam subjects
        subject_query = select(ExamSubject).where(
            and_(
                ExamSubject.exam_id == exam_id,
                ExamSubject.class_id == class_id,
                ExamSubject.tenant_id == tenant_id,
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
                select(Subject).where(
                    and_(Subject.id == subject_id, Subject.tenant_id == tenant_id)
                )
            )
            subject_obj = subject_result.scalar_one_or_none()
            subject_name = subject_obj.name if subject_obj else None

        # Get all scores for the exam subjects
        exam_subject_ids = [es.id for es in exam_subjects]
        scores_result = await self.db.execute(
            select(ExamScore).where(
                and_(
                    ExamScore.tenant_id == tenant_id,
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

        # Get exam info (filter soft-deleted)
        exam_result = await self.db.execute(
            select(Exam)
            .options(joinedload(Exam.term), joinedload(Exam.academic_year))
            .where(
                and_(
                    Exam.id == exam_id,
                    Exam.tenant_id == tenant_id,
                    Exam.deleted_at.is_(None),
                )
            )
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            return None

        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        class_result = await self.db.execute(
            select(Class).where(
                and_(Class.id == class_id, Class.tenant_id == tenant_id)
            )
        )
        class_obj = class_result.scalar_one_or_none()
        if not class_obj:
            return None

        # Get section info if provided
        section_name = None
        if section_id:
            section_result = await self.db.execute(
                select(ClassSection).where(
                    and_(ClassSection.id == section_id, ClassSection.tenant_id == tenant_id)
                )
            )
            section_obj = section_result.scalar_one_or_none()
            section_name = section_obj.name if section_obj else None

        # Get exam subjects for the class
        subject_query = select(ExamSubject).where(
            and_(
                ExamSubject.exam_id == exam_id,
                ExamSubject.class_id == class_id,
                ExamSubject.tenant_id == tenant_id,
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
                    ExamScore.tenant_id == tenant_id,
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
                        ExamScore.tenant_id == tenant_id,
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

        # Defense-in-depth: filter by tenant_id and soft delete
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

        # Defense-in-depth: filter by tenant_id
        class_result = await self.db.execute(
            select(Class).where(
                and_(Class.id == class_id, Class.tenant_id == tenant_id)
            )
        )
        class_obj = class_result.scalar_one_or_none()

        # Get scores with student info
        scores_result = await self.db.execute(
            select(ExamScore)
            .options(joinedload(ExamScore.student))
            .where(
                and_(
                    ExamScore.tenant_id == tenant_id,
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
        # Get exam info (filter soft-deleted)
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
            .where(
                and_(
                    ExamSubject.exam_id == exam_id,
                    ExamSubject.tenant_id == tenant_id,
                )
            )
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

        await self.db.flush()

        # Check for conflicts after update
        conflicts_result = await self.check_timetable_conflicts(tenant_id, exam_id)

        return {
            "updated": updated,
            "failed": failed,
            "errors": errors,
            "conflicts": conflicts_result.get("conflicts", []),
        }

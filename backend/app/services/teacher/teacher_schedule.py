"""
SIMS Plus - Teacher Schedule Service

Provides today's and weekly timetable schedule for a teacher.
Queries ClassTimetable entries filtered by teacher_id and the
current academic year/term.
"""

from datetime import date
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    AcademicYear,
    Class,
    ClassSection,
    ClassTimetable,
    Subject,
    Term,
)

from ._shared import TeacherServiceError

logger = structlog.get_logger()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TeacherScheduleService:
    """
    Retrieves timetable-based schedule data for a teacher.

    Queries are scoped by tenant_id (defense-in-depth on top of RLS),
    filtered to the current academic year, and sorted by day + period.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_today_schedule(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID | None = None,
    ) -> list[dict]:
        """
        Get today's timetable entries for the teacher.

        Returns entries for today's day_of_week, sorted by period_number.
        Eagerly loads class, section, and subject relationships.
        """
        today = date.today()
        # Python weekday: Monday=0, Sunday=6 (matches DayOfWeek enum)
        day_of_week = today.weekday()

        query = (
            select(ClassTimetable)
            .options(
                selectinload(ClassTimetable.class_),
                selectinload(ClassTimetable.section),
                selectinload(ClassTimetable.subject),
            )
            .where(
                and_(
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.academic_year_id == academic_year_id,
                    ClassTimetable.day_of_week == day_of_week,
                    ClassTimetable.is_active.is_(True),
                )
            )
        )
        # Optionally filter by term if provided
        if term_id:
            query = query.where(
                (ClassTimetable.term_id == term_id) | (ClassTimetable.term_id.is_(None))
            )

        query = query.order_by(ClassTimetable.period_number)
        result = await self.db.execute(query)
        entries = result.scalars().all()

        return [self._format_entry(e) for e in entries]

    async def get_week_schedule(
        self,
        staff_id: UUID,
        tenant_id: UUID,
        academic_year_id: UUID,
        term_id: UUID | None = None,
    ) -> list[dict]:
        """
        Get the full weekly schedule for the teacher.

        Returns all active timetable entries grouped by day_of_week,
        sorted by day then period_number.
        """
        query = (
            select(ClassTimetable)
            .options(
                selectinload(ClassTimetable.class_),
                selectinload(ClassTimetable.section),
                selectinload(ClassTimetable.subject),
            )
            .where(
                and_(
                    ClassTimetable.tenant_id == tenant_id,
                    ClassTimetable.teacher_id == staff_id,
                    ClassTimetable.academic_year_id == academic_year_id,
                    ClassTimetable.is_active.is_(True),
                )
            )
        )
        if term_id:
            query = query.where(
                (ClassTimetable.term_id == term_id) | (ClassTimetable.term_id.is_(None))
            )

        query = query.order_by(ClassTimetable.day_of_week, ClassTimetable.period_number)
        result = await self.db.execute(query)
        entries = result.scalars().all()

        # Group by day
        days_map: dict[int, list[dict]] = {}
        for entry in entries:
            day = entry.day_of_week
            if day not in days_map:
                days_map[day] = []
            days_map[day].append(self._format_entry(entry))

        # Build sorted day list (0=Monday through 6=Sunday)
        week = []
        for day_num in sorted(days_map.keys()):
            week.append({
                "day_of_week": day_num,
                "day_name": DAY_NAMES[day_num] if day_num < len(DAY_NAMES) else f"Day {day_num}",
                "entries": days_map[day_num],
            })

        return week

    @staticmethod
    def _format_entry(entry: ClassTimetable) -> dict:
        """Format a timetable entry into a response-ready dict."""
        return {
            "id": entry.id,
            "timetable_id": entry.id,  # Alias for UpcomingLesson schema (dashboard)
            "class_id": entry.class_id,
            "class_name": entry.class_.name if entry.class_ else None,
            "section_id": entry.section_id,
            "section_name": entry.section.name if entry.section else None,
            "subject_id": entry.subject_id,
            "subject_name": entry.subject.name if entry.subject else None,
            "day_of_week": entry.day_of_week,
            "period_number": entry.period_number,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "room": entry.room,
        }

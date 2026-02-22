"""
SIMS Plus - Timetable Service

Business logic for class timetable management.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    ClassTimetable,
    Class,
    ClassSection,
    AcademicYear,
    Term,
    Subject,
    SchoolPeriod,
    SchoolHoliday,
)
from app.models.staff import Staff


class TimetableServiceError(Exception):
    """Base exception for timetable service errors."""

    def __init__(self, message: str, code: str = "timetable_error"):
        self.message = message
        self.code = code
        super().__init__(message)


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TimetableService:
    """Service for managing class timetables."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_timetable_entry(
        self,
        tenant_id: UUID,
        class_id: UUID,
        academic_year_id: UUID,
        day_of_week: int,
        period_number: int,
        start_time: str,
        end_time: str,
        section_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        subject_id: Optional[UUID] = None,
        teacher_id: Optional[UUID] = None,
        room: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ClassTimetable:
        """Create a new timetable entry.

        Args:
            term_id: Optional term ID. If set, timetable applies only to this term.
                     If None, timetable applies to the entire academic year.
        """
        # Validate day of week
        if day_of_week < 0 or day_of_week > 6:
            raise TimetableServiceError(
                "Day of week must be between 0 (Monday) and 6 (Sunday)",
                code="invalid_day_of_week",
            )

        # Check for existing entry at same period (considering term)
        conditions = [
            ClassTimetable.tenant_id == tenant_id,
            ClassTimetable.class_id == class_id,
            ClassTimetable.section_id == section_id if section_id else ClassTimetable.section_id.is_(None),
            ClassTimetable.academic_year_id == academic_year_id,
            ClassTimetable.term_id == term_id if term_id else ClassTimetable.term_id.is_(None),
            ClassTimetable.day_of_week == day_of_week,
            ClassTimetable.period_number == period_number,
        ]
        existing = await self.db.execute(
            select(ClassTimetable).where(and_(*conditions))
        )
        if existing.scalar_one_or_none():
            raise TimetableServiceError(
                f"A timetable entry already exists for this period on {DAY_NAMES[day_of_week]}",
                code="duplicate_timetable_entry",
            )

        # Validate teacher availability (check for conflicts)
        if teacher_id:
            await self._check_teacher_availability(
                tenant_id, teacher_id, academic_year_id, day_of_week, start_time, end_time,
                term_id=term_id
            )

        entry = ClassTimetable(
            tenant_id=tenant_id,
            class_id=class_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            day_of_week=day_of_week,
            period_number=period_number,
            start_time=start_time,
            end_time=end_time,
            room=room,
            notes=notes,
            is_active=True,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def get_timetable_entry(
        self, tenant_id: UUID, entry_id: UUID, include_relations: bool = True
    ) -> Optional[ClassTimetable]:
        """Get a timetable entry by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(ClassTimetable).where(
            and_(
                ClassTimetable.tenant_id == tenant_id,
                ClassTimetable.id == entry_id,
            )
        )
        if include_relations:
            query = query.options(
                selectinload(ClassTimetable.class_),
                selectinload(ClassTimetable.section),
                selectinload(ClassTimetable.subject),
                selectinload(ClassTimetable.teacher),
                selectinload(ClassTimetable.academic_year),
                selectinload(ClassTimetable.term),
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_class_timetable(
        self,
        tenant_id: UUID,
        class_id: UUID,
        academic_year_id: UUID,
        section_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> Sequence[ClassTimetable]:
        """Get all timetable entries for a class/section.

        Args:
            term_id: Optional term ID to filter by. If None, returns year-wide timetable.
        """
        conditions = [
            ClassTimetable.tenant_id == tenant_id,
            ClassTimetable.class_id == class_id,
            ClassTimetable.academic_year_id == academic_year_id,
            ClassTimetable.is_active == True,
        ]

        if section_id:
            conditions.append(ClassTimetable.section_id == section_id)
        else:
            conditions.append(ClassTimetable.section_id.is_(None))

        # Filter by term if specified, otherwise get year-wide timetable (term_id is NULL)
        if term_id:
            conditions.append(ClassTimetable.term_id == term_id)
        else:
            conditions.append(ClassTimetable.term_id.is_(None))

        query = (
            select(ClassTimetable)
            .where(and_(*conditions))
            .options(
                selectinload(ClassTimetable.class_),
                selectinload(ClassTimetable.section),
                selectinload(ClassTimetable.subject),
                selectinload(ClassTimetable.teacher),
                selectinload(ClassTimetable.academic_year),
                selectinload(ClassTimetable.term),
            )
            .order_by(ClassTimetable.day_of_week, ClassTimetable.period_number)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_teacher_timetable(
        self,
        tenant_id: UUID,
        teacher_id: UUID,
        academic_year_id: UUID,
        term_id: Optional[UUID] = None,
    ) -> Sequence[ClassTimetable]:
        """Get all timetable entries for a teacher.

        Args:
            term_id: Optional term ID to filter by. If None, returns all timetable entries.
        """
        conditions = [
            ClassTimetable.tenant_id == tenant_id,
            ClassTimetable.teacher_id == teacher_id,
            ClassTimetable.academic_year_id == academic_year_id,
            ClassTimetable.is_active == True,
        ]

        if term_id:
            conditions.append(ClassTimetable.term_id == term_id)

        query = (
            select(ClassTimetable)
            .where(and_(*conditions))
            .options(
                selectinload(ClassTimetable.class_),
                selectinload(ClassTimetable.section),
                selectinload(ClassTimetable.subject),
                selectinload(ClassTimetable.academic_year),
                selectinload(ClassTimetable.term),
            )
            .order_by(ClassTimetable.day_of_week, ClassTimetable.period_number)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_timetable_entry(
        self, entry_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[ClassTimetable]:
        """Update a timetable entry."""
        # Defense-in-depth: tenant_id verified in get_timetable_entry
        entry = await self.get_timetable_entry(tenant_id, entry_id, include_relations=False)
        if not entry:
            return None

        # Validate teacher availability if changing teacher or time
        if kwargs.get("teacher_id") and (
            kwargs.get("teacher_id") != entry.teacher_id
            or kwargs.get("start_time")
            or kwargs.get("end_time")
        ):
            await self._check_teacher_availability(
                tenant_id,
                kwargs.get("teacher_id", entry.teacher_id),
                entry.academic_year_id,
                entry.day_of_week,
                kwargs.get("start_time", entry.start_time),
                kwargs.get("end_time", entry.end_time),
                exclude_entry_id=entry_id,
            )

        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        entry.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def delete_timetable_entry(self, tenant_id: UUID, entry_id: UUID) -> bool:
        """Delete a timetable entry (hard delete)."""
        # Defense-in-depth: tenant_id verified in get_timetable_entry
        entry = await self.get_timetable_entry(tenant_id, entry_id, include_relations=False)
        if not entry:
            return False

        await self.db.delete(entry)
        await self.db.flush()
        return True

    async def bulk_update_timetable(
        self,
        tenant_id: UUID,
        class_id: UUID,
        academic_year_id: UUID,
        entries: list[dict],
        section_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> list[ClassTimetable]:
        """Bulk create/update timetable entries for a class/section.

        This replaces the entire timetable for the class/section/term.

        Args:
            term_id: Optional term ID. If set, only replaces entries for this term.
                     If None, replaces year-wide timetable entries.
        """
        # Delete existing entries
        conditions = [
            ClassTimetable.tenant_id == tenant_id,
            ClassTimetable.class_id == class_id,
            ClassTimetable.academic_year_id == academic_year_id,
        ]
        if section_id:
            conditions.append(ClassTimetable.section_id == section_id)
        else:
            conditions.append(ClassTimetable.section_id.is_(None))

        # Consider term in deletion
        if term_id:
            conditions.append(ClassTimetable.term_id == term_id)
        else:
            conditions.append(ClassTimetable.term_id.is_(None))

        await self.db.execute(
            delete(ClassTimetable).where(and_(*conditions))
        )

        # Create new entries
        created_entries = []
        for entry_data in entries:
            entry = ClassTimetable(
                tenant_id=tenant_id,
                class_id=class_id,
                section_id=section_id,
                academic_year_id=academic_year_id,
                term_id=term_id,
                subject_id=entry_data.get("subject_id"),
                teacher_id=entry_data.get("teacher_id"),
                day_of_week=entry_data["day_of_week"],
                period_number=entry_data["period_number"],
                start_time=entry_data["start_time"],
                end_time=entry_data["end_time"],
                room=entry_data.get("room"),
                notes=entry_data.get("notes"),
                is_active=True,
            )
            self.db.add(entry)
            created_entries.append(entry)

        await self.db.flush()

        # Refresh all entries to get IDs and load relations
        for entry in created_entries:
            await self.db.refresh(entry)

        return created_entries

    async def _check_teacher_availability(
        self,
        tenant_id: UUID,
        teacher_id: UUID,
        academic_year_id: UUID,
        day_of_week: int,
        start_time: str,
        end_time: str,
        exclude_entry_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> None:
        """Check if a teacher is available at the specified time.

        Term conflict rules:
        - Year-wide entries (term_id=NULL) conflict with all other entries
        - Term-specific entries only conflict with year-wide entries or same-term entries
        """
        from sqlalchemy import or_

        conditions = [
            ClassTimetable.tenant_id == tenant_id,
            ClassTimetable.teacher_id == teacher_id,
            ClassTimetable.academic_year_id == academic_year_id,
            ClassTimetable.day_of_week == day_of_week,
            ClassTimetable.is_active == True,
        ]

        if exclude_entry_id:
            conditions.append(ClassTimetable.id != exclude_entry_id)

        # Check for time overlap
        # Two periods overlap if: start1 < end2 AND start2 < end1
        conditions.extend([
            ClassTimetable.start_time < end_time,
            ClassTimetable.end_time > start_time,
        ])

        # Term conflict logic:
        # - If creating year-wide (term_id is None): check all entries
        # - If creating term-specific: check year-wide entries OR same-term entries
        if term_id:
            conditions.append(
                or_(
                    ClassTimetable.term_id.is_(None),  # Year-wide entries
                    ClassTimetable.term_id == term_id,  # Same term entries
                )
            )
        # If term_id is None (year-wide), check all entries (no additional filter)

        result = await self.db.execute(
            select(ClassTimetable)
            .where(and_(*conditions))
            .options(
                selectinload(ClassTimetable.class_),
                selectinload(ClassTimetable.section),
                selectinload(ClassTimetable.term),
            )
        )
        conflict = result.scalar_one_or_none()

        if conflict:
            class_name = conflict.class_.name if conflict.class_ else "Unknown"
            section_name = f" {conflict.section.name}" if conflict.section else ""
            term_info = f" ({conflict.term.name})" if conflict.term else " (year-wide)"
            raise TimetableServiceError(
                f"Teacher is already assigned to {class_name}{section_name}{term_info} at this time on {DAY_NAMES[day_of_week]}",
                code="teacher_conflict",
            )

    async def get_class_with_details(self, tenant_id: UUID, class_id: UUID) -> Optional[Class]:
        """Get class with sections loaded."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = (
            select(Class)
            .where(
                and_(
                    Class.tenant_id == tenant_id,
                    Class.id == class_id,
                    Class.deleted_at.is_(None),
                )
            )
            .options(selectinload(Class.sections))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_academic_year(self, tenant_id: UUID, academic_year_id: UUID) -> Optional[AcademicYear]:
        """Get academic year by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def format_timetable_week(
        self,
        entries: Sequence[ClassTimetable],
        class_data: Class,
        section_data: Optional[ClassSection],
        academic_year: AcademicYear,
        term: Optional[Term] = None,
    ) -> dict:
        """Format timetable entries into a weekly structure."""
        # Group entries by day
        days_map = {i: [] for i in range(7)}
        for entry in entries:
            days_map[entry.day_of_week].append(entry)

        days = []
        for day_num in range(7):
            day_entries = days_map[day_num]
            if day_entries:  # Only include days with entries
                days.append({
                    "day_of_week": day_num,
                    "day_name": DAY_NAMES[day_num],
                    "entries": day_entries,
                })

        return {
            "class_id": class_data.id,
            "class_name": class_data.name,
            "section_id": section_data.id if section_data else None,
            "section_name": section_data.name if section_data else None,
            "academic_year_id": academic_year.id,
            "academic_year_name": academic_year.name,
            "term_id": term.id if term else None,
            "term_name": term.name if term else None,
            "days": days,
            "total_periods": len(entries),
        }

    async def get_term(self, tenant_id: UUID, term_id: UUID) -> Optional[Term]:
        """Get term by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(Term).where(
            and_(
                Term.tenant_id == tenant_id,
                Term.id == term_id,
                Term.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    # =========================
    # School Period Methods
    # =========================

    async def get_school_periods(
        self,
        tenant_id: UUID,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> Sequence[SchoolPeriod]:
        """Get school periods with hierarchy support.

        Returns periods in order of specificity:
        1. Section-specific periods (if section_id provided and found)
        2. Class-specific periods (if class_id provided and found)
        3. School-wide periods (default)
        """
        conditions = [SchoolPeriod.tenant_id == tenant_id]
        if active_only:
            conditions.append(SchoolPeriod.is_active == True)

        # Try section-specific first
        if section_id and class_id:
            section_conditions = conditions + [
                SchoolPeriod.class_id == class_id,
                SchoolPeriod.section_id == section_id,
            ]
            query = (
                select(SchoolPeriod)
                .where(and_(*section_conditions))
                .order_by(SchoolPeriod.period_number)
            )
            result = await self.db.execute(query)
            periods = result.scalars().all()
            if periods:
                return periods

        # Try class-specific
        if class_id:
            class_conditions = conditions + [
                SchoolPeriod.class_id == class_id,
                SchoolPeriod.section_id.is_(None),
            ]
            query = (
                select(SchoolPeriod)
                .where(and_(*class_conditions))
                .order_by(SchoolPeriod.period_number)
            )
            result = await self.db.execute(query)
            periods = result.scalars().all()
            if periods:
                return periods

        # Fall back to school-wide
        school_conditions = conditions + [
            SchoolPeriod.class_id.is_(None),
            SchoolPeriod.section_id.is_(None),
        ]
        query = (
            select(SchoolPeriod)
            .where(and_(*school_conditions))
            .order_by(SchoolPeriod.period_number)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_all_school_periods(
        self,
        tenant_id: UUID,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> Sequence[SchoolPeriod]:
        """Get all school periods matching the filter (without hierarchy fallback).

        Use this for the settings page to show only periods at a specific level.
        """
        conditions = [SchoolPeriod.tenant_id == tenant_id]
        if active_only:
            conditions.append(SchoolPeriod.is_active == True)

        if class_id:
            conditions.append(SchoolPeriod.class_id == class_id)
        else:
            conditions.append(SchoolPeriod.class_id.is_(None))

        if section_id:
            conditions.append(SchoolPeriod.section_id == section_id)
        else:
            conditions.append(SchoolPeriod.section_id.is_(None))

        query = (
            select(SchoolPeriod)
            .where(and_(*conditions))
            .order_by(SchoolPeriod.period_number)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_school_period(self, tenant_id: UUID, period_id: UUID) -> Optional[SchoolPeriod]:
        """Get a school period by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(SchoolPeriod).where(
            and_(
                SchoolPeriod.tenant_id == tenant_id,
                SchoolPeriod.id == period_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_school_period(
        self,
        tenant_id: UUID,
        period_number: int,
        start_time: str,
        end_time: str,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        name: Optional[str] = None,
        is_break: bool = False,
    ) -> SchoolPeriod:
        """Create a new school period."""
        # Check if period number already exists at this level
        conditions = [
            SchoolPeriod.tenant_id == tenant_id,
            SchoolPeriod.period_number == period_number,
        ]
        if class_id:
            conditions.append(SchoolPeriod.class_id == class_id)
        else:
            conditions.append(SchoolPeriod.class_id.is_(None))

        if section_id:
            conditions.append(SchoolPeriod.section_id == section_id)
        else:
            conditions.append(SchoolPeriod.section_id.is_(None))

        existing = await self.db.execute(
            select(SchoolPeriod).where(and_(*conditions))
        )
        if existing.scalar_one_or_none():
            raise TimetableServiceError(
                f"Period {period_number} already exists at this level",
                code="duplicate_period",
            )

        period = SchoolPeriod(
            tenant_id=tenant_id,
            class_id=class_id,
            section_id=section_id,
            period_number=period_number,
            name=name,
            start_time=start_time,
            end_time=end_time,
            is_break=is_break,
            is_active=True,
        )
        self.db.add(period)
        await self.db.flush()
        await self.db.refresh(period)
        return period

    async def update_school_period(
        self, period_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[SchoolPeriod]:
        """Update a school period."""
        # Defense-in-depth: tenant_id verified in get_school_period
        period = await self.get_school_period(tenant_id, period_id)
        if not period:
            return None

        for key, value in kwargs.items():
            if hasattr(period, key) and value is not None:
                setattr(period, key, value)

        period.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(period)
        return period

    async def delete_school_period(self, period_id: UUID, tenant_id: UUID) -> bool:
        """Delete a school period."""
        # Defense-in-depth: tenant_id verified in get_school_period
        period = await self.get_school_period(tenant_id, period_id)
        if not period:
            return False

        await self.db.delete(period)
        await self.db.flush()
        return True

    async def bulk_create_school_periods(
        self,
        tenant_id: UUID,
        periods: list[dict],
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
    ) -> list[SchoolPeriod]:
        """Bulk create school periods at a specific level, replacing existing ones at that level."""
        # Delete existing periods at this level
        conditions = [SchoolPeriod.tenant_id == tenant_id]
        if class_id:
            conditions.append(SchoolPeriod.class_id == class_id)
        else:
            conditions.append(SchoolPeriod.class_id.is_(None))

        if section_id:
            conditions.append(SchoolPeriod.section_id == section_id)
        else:
            conditions.append(SchoolPeriod.section_id.is_(None))

        await self.db.execute(
            delete(SchoolPeriod).where(and_(*conditions))
        )

        # Create new periods
        created_periods = []
        for period_data in periods:
            period = SchoolPeriod(
                tenant_id=tenant_id,
                class_id=class_id,
                section_id=section_id,
                period_number=period_data["period_number"],
                name=period_data.get("name"),
                start_time=period_data["start_time"],
                end_time=period_data["end_time"],
                is_break=period_data.get("is_break", False),
                is_active=True,
            )
            self.db.add(period)
            created_periods.append(period)

        await self.db.flush()
        for period in created_periods:
            await self.db.refresh(period)

        return created_periods

    # =========================
    # School Holiday Methods
    # =========================

    async def get_school_holidays(
        self,
        tenant_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> Sequence[SchoolHoliday]:
        """Get all school holidays for a tenant."""
        conditions = [SchoolHoliday.tenant_id == tenant_id]
        if academic_year_id:
            conditions.append(SchoolHoliday.academic_year_id == academic_year_id)

        query = (
            select(SchoolHoliday)
            .where(and_(*conditions))
            .order_by(SchoolHoliday.date)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_school_holiday(self, tenant_id: UUID, holiday_id: UUID) -> Optional[SchoolHoliday]:
        """Get a school holiday by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(SchoolHoliday).where(
            and_(
                SchoolHoliday.tenant_id == tenant_id,
                SchoolHoliday.id == holiday_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_school_holiday(
        self,
        tenant_id: UUID,
        date: "date",
        name: str,
        description: Optional[str] = None,
        holiday_type: str = "holiday",
        academic_year_id: Optional[UUID] = None,
        is_recurring: bool = False,
    ) -> SchoolHoliday:
        """Create a new school holiday."""
        from datetime import date as date_type

        # Check if holiday already exists on this date
        existing = await self.db.execute(
            select(SchoolHoliday).where(
                and_(
                    SchoolHoliday.tenant_id == tenant_id,
                    SchoolHoliday.date == date,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise TimetableServiceError(
                f"A holiday already exists on {date}",
                code="duplicate_holiday",
            )

        holiday = SchoolHoliday(
            tenant_id=tenant_id,
            date=date,
            name=name,
            description=description,
            holiday_type=holiday_type,
            academic_year_id=academic_year_id,
            is_recurring=is_recurring,
        )
        self.db.add(holiday)
        await self.db.flush()
        await self.db.refresh(holiday)
        return holiday

    async def update_school_holiday(
        self, holiday_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[SchoolHoliday]:
        """Update a school holiday."""
        # Defense-in-depth: tenant_id verified in get_school_holiday
        holiday = await self.get_school_holiday(tenant_id, holiday_id)
        if not holiday:
            return None

        for key, value in kwargs.items():
            if hasattr(holiday, key) and value is not None:
                setattr(holiday, key, value)

        holiday.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(holiday)
        return holiday

    async def delete_school_holiday(self, holiday_id: UUID, tenant_id: UUID) -> bool:
        """Delete a school holiday."""
        # Defense-in-depth: tenant_id verified in get_school_holiday
        holiday = await self.get_school_holiday(tenant_id, holiday_id)
        if not holiday:
            return False

        await self.db.delete(holiday)
        await self.db.flush()
        return True

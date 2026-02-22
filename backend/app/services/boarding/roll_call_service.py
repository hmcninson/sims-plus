"""
SIMS Plus - Boarding Roll Call Service

Business logic for conducting roll calls in boarding houses and
generating attendance reports for boarders.
"""

from datetime import date
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.boarding import (
    BoardingRollCall,
    BoardingRollCallEntry,
    RollCallType,
    RollCallEntryStatus,
    StudentBoarding,
    BoardingStatus,
    House,
)
from app.models.student import Student

from app.services.boarding._shared import BoardingServiceError

logger = structlog.get_logger()


class RollCallService:
    """Service for managing boarding roll calls."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_roll_call(
        self,
        tenant_id: UUID,
        school_id: UUID,
        house_id: UUID,
        roll_call_date: date,
        roll_call_type: str,
        conducted_by_id: UUID,
        entries: list[dict],
        notes: Optional[str] = None,
    ) -> BoardingRollCall:
        """
        Create a roll call with all student entries in one transaction.

        Validates that:
        - The house exists
        - All students in the entries are currently assigned to the house
        - No duplicate roll call exists for the same house/date/type
        """
        # Verify house exists
        await self._get_house_or_raise(tenant_id, house_id)

        # Validate all students belong to this house
        student_ids = [entry["student_id"] for entry in entries]
        await self._validate_students_in_house(tenant_id, house_id, student_ids)

        # Create the roll call record
        roll_call = BoardingRollCall(
            tenant_id=tenant_id,
            school_id=school_id,
            house_id=house_id,
            date=roll_call_date,
            roll_call_type=RollCallType(roll_call_type),
            conducted_by_id=conducted_by_id,
            notes=notes,
        )
        self.db.add(roll_call)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_boarding_roll_call_tenant_house_date_type" in error_msg:
                raise BoardingServiceError(
                    f"A {roll_call_type} roll call already exists for this house on {roll_call_date}",
                    code="duplicate_roll_call",
                )
            logger.error("database_integrity_error", operation="create_roll_call", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred while creating roll call",
                code="database_error",
            )

        # Create all entries
        for entry_data in entries:
            entry = BoardingRollCallEntry(
                tenant_id=tenant_id,
                roll_call_id=roll_call.id,
                student_id=entry_data["student_id"],
                status=RollCallEntryStatus(entry_data["status"]),
                notes=entry_data.get("notes"),
            )
            self.db.add(entry)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_boarding_roll_call_entries_tenant_roll_call_student" in error_msg:
                raise BoardingServiceError(
                    "Duplicate student entry in roll call",
                    code="duplicate_entry",
                )
            logger.error("database_integrity_error", operation="create_roll_call_entries", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred while creating roll call entries",
                code="database_error",
            )

        await self.db.refresh(roll_call)

        # Reload with entries for the response
        return await self.get_roll_call(tenant_id, roll_call.id)

    async def get_roll_calls(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        house_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        roll_call_type: Optional[str] = None,
    ) -> Sequence[BoardingRollCall]:
        """List roll calls with optional filters."""
        conditions = [
            BoardingRollCall.tenant_id == tenant_id,
            BoardingRollCall.deleted_at.is_(None),
        ]

        if school_id:
            conditions.append(BoardingRollCall.school_id == school_id)

        if house_id:
            conditions.append(BoardingRollCall.house_id == house_id)
        if date_from:
            conditions.append(BoardingRollCall.date >= date_from)
        if date_to:
            conditions.append(BoardingRollCall.date <= date_to)
        if roll_call_type:
            conditions.append(
                BoardingRollCall.roll_call_type == RollCallType(roll_call_type)
            )

        query = (
            select(BoardingRollCall)
            .where(and_(*conditions))
            .options(
                selectinload(BoardingRollCall.house),
                selectinload(BoardingRollCall.conducted_by),
            )
            .order_by(BoardingRollCall.date.desc(), BoardingRollCall.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_roll_call(
        self,
        tenant_id: UUID,
        roll_call_id: UUID,
    ) -> BoardingRollCall:
        """Get a single roll call with all entries and student names loaded."""
        query = (
            select(BoardingRollCall)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    BoardingRollCall.tenant_id == tenant_id,
                    BoardingRollCall.id == roll_call_id,
                    BoardingRollCall.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(BoardingRollCall.house),
                selectinload(BoardingRollCall.conducted_by),
                selectinload(BoardingRollCall.entries)
                .selectinload(BoardingRollCallEntry.student),
            )
        )
        result = await self.db.execute(query)
        roll_call = result.scalar_one_or_none()
        if not roll_call:
            raise BoardingServiceError("Roll call not found", code="not_found")
        return roll_call

    async def get_roll_call_report(
        self,
        tenant_id: UUID,
        house_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """
        Generate a roll call attendance report for a house over a date range.

        Aggregates all roll call entries by student to produce per-student
        counts of present, absent, and AWOL statuses along with percentages.
        """
        # Verify house exists
        await self._get_house_or_raise(tenant_id, house_id)

        # Get all entries for the house in the date range
        # Join through BoardingRollCall to filter by house and date range
        query = (
            select(
                BoardingRollCallEntry.student_id,
                func.count(BoardingRollCallEntry.id).label("total_entries"),
                func.count(
                    case(
                        (BoardingRollCallEntry.status == RollCallEntryStatus.PRESENT, 1),
                    )
                ).label("present_count"),
                func.count(
                    case(
                        (BoardingRollCallEntry.status == RollCallEntryStatus.ABSENT, 1),
                    )
                ).label("absent_count"),
                func.count(
                    case(
                        (BoardingRollCallEntry.status == RollCallEntryStatus.AWOL, 1),
                    )
                ).label("awol_count"),
                func.count(
                    case(
                        (BoardingRollCallEntry.status == RollCallEntryStatus.SICK_BAY, 1),
                    )
                ).label("sick_bay_count"),
                func.count(
                    case(
                        (BoardingRollCallEntry.status == RollCallEntryStatus.EXEAT, 1),
                    )
                ).label("exeat_count"),
            )
            .join(
                BoardingRollCall,
                BoardingRollCallEntry.roll_call_id == BoardingRollCall.id,
            )
            .where(
                and_(
                    BoardingRollCall.tenant_id == tenant_id,
                    BoardingRollCall.house_id == house_id,
                    BoardingRollCall.date >= start_date,
                    BoardingRollCall.date <= end_date,
                    BoardingRollCall.deleted_at.is_(None),
                )
            )
            .group_by(BoardingRollCallEntry.student_id)
        )
        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Fetch student names for all student_ids in the report
        student_ids = [row.student_id for row in rows]
        students_result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id.in_(student_ids),
                )
            )
        )
        student_map = {
            s.id: f"{s.first_name} {s.last_name}"
            for s in students_result.scalars().all()
        }

        report = []
        for row in rows:
            total = row.total_entries or 1  # Avoid division by zero
            present_pct = round((row.present_count / total) * 100, 1)

            report.append({
                "student_id": row.student_id,
                "student_name": student_map.get(row.student_id, "Unknown"),
                "total_roll_calls": row.total_entries,
                "present_count": row.present_count,
                "absent_count": row.absent_count,
                "awol_count": row.awol_count,
                "sick_bay_count": row.sick_bay_count,
                "exeat_count": row.exeat_count,
                "present_percentage": present_pct,
            })

        # Sort by student name for consistent output
        report.sort(key=lambda x: x["student_name"])
        return report

    # =========================
    # Internal Helpers
    # =========================

    async def _get_house_or_raise(self, tenant_id: UUID, house_id: UUID) -> House:
        """Fetch a house or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(House).where(
                and_(
                    House.tenant_id == tenant_id,
                    House.id == house_id,
                    House.deleted_at.is_(None),
                )
            )
        )
        house = result.scalar_one_or_none()
        if not house:
            raise BoardingServiceError("House not found", code="not_found")
        return house

    async def _validate_students_in_house(
        self,
        tenant_id: UUID,
        house_id: UUID,
        student_ids: list[UUID],
    ) -> None:
        """
        Verify all students are currently assigned to the specified house.

        This prevents roll call entries for students who are not boarders
        in this house, which would produce incorrect attendance records.
        """
        # Get students currently assigned to this house
        result = await self.db.execute(
            select(StudentBoarding.student_id).where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.house_id == house_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
        )
        assigned_ids = set(result.scalars().all())

        # Check for students not in the house
        submitted_ids = set(student_ids)
        not_in_house = submitted_ids - assigned_ids
        if not_in_house:
            raise BoardingServiceError(
                f"{len(not_in_house)} student(s) are not assigned to this house",
                code="students_not_in_house",
            )

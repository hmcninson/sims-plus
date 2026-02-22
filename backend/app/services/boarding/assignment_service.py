"""
SIMS Plus - Boarding Assignment Service

Business logic for assigning students to boarding houses, dormitories, and beds.
Handles check-in, check-out, transfers, and bulk assignment operations.
"""

from datetime import date, datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.boarding import (
    House,
    Dormitory,
    Bed,
    BedStatus,
    StudentBoarding,
    BoardingStatus,
)
from app.models.student import Student, StudentStatus

from app.services.boarding._shared import BoardingServiceError

logger = structlog.get_logger()


class BoardingAssignmentService:
    """Service for managing student boarding assignments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def assign_student(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        house_id: UUID,
        dormitory_id: Optional[UUID],
        bed_id: Optional[UUID],
        academic_year_id: UUID,
        check_in_date: date,
    ) -> StudentBoarding:
        """
        Assign a student to a boarding house for an academic year.

        Enforces that:
        - The student is not already assigned for the same academic year
        - The specified bed (if any) is available and not occupied
        - The bed's status is updated to 'occupied' upon assignment
        """
        # Verify student exists and belongs to tenant
        student = await self._get_student_or_raise(tenant_id, student_id)

        # Verify house exists and belongs to tenant
        await self._get_house_or_raise(tenant_id, house_id)

        # Verify dormitory exists and belongs to the house (if provided)
        if dormitory_id:
            await self._verify_dormitory_belongs_to_house(
                tenant_id, dormitory_id, house_id
            )

        # Verify bed exists and belongs to the dormitory (if provided)
        if bed_id:
            bed = await self._get_bed_or_raise(tenant_id, bed_id)
            if dormitory_id and bed.dormitory_id != dormitory_id:
                raise BoardingServiceError(
                    "Bed does not belong to the specified dormitory",
                    code="bed_dormitory_mismatch",
                )
            if bed.status == BedStatus.OCCUPIED:
                raise BoardingServiceError(
                    "Bed is already occupied",
                    code="bed_occupied",
                )
            if bed.status == BedStatus.MAINTENANCE:
                raise BoardingServiceError(
                    "Bed is under maintenance and cannot be assigned",
                    code="bed_maintenance",
                )

        # Check student is not already assigned for this academic year
        existing = await self.db.execute(
            select(StudentBoarding).where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.student_id == student_id,
                    StudentBoarding.academic_year_id == academic_year_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise BoardingServiceError(
                "Student is already assigned to a boarding house for this academic year",
                code="already_assigned",
            )

        # Create the assignment
        assignment = StudentBoarding(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_id,
            house_id=house_id,
            dormitory_id=dormitory_id,
            bed_id=bed_id,
            academic_year_id=academic_year_id,
            boarding_status=BoardingStatus.ACTIVE,
            check_in_date=check_in_date,
        )
        self.db.add(assignment)

        # Mark bed as occupied if a specific bed was assigned
        if bed_id:
            bed = await self._get_bed_or_raise(tenant_id, bed_id)
            bed.status = BedStatus.OCCUPIED

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_student_boarding_tenant_student_year" in error_msg:
                raise BoardingServiceError(
                    "Student is already assigned for this academic year (concurrent assignment)",
                    code="already_assigned",
                )
            if "uq_student_boarding_tenant_bed_year" in error_msg:
                raise BoardingServiceError(
                    "Bed is already assigned for this academic year (concurrent assignment)",
                    code="bed_occupied",
                )
            logger.error("database_integrity_error", operation="assign_student", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred during assignment",
                code="database_error",
            )

        await self.db.refresh(assignment)
        return assignment

    async def unassign_student(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
    ) -> StudentBoarding:
        """
        Unassign a student from boarding (check out).

        Sets the check_out_date to today and boarding_status to withdrawn.
        Releases the assigned bed back to available status.
        """
        assignment = await self._get_assignment_or_raise(tenant_id, assignment_id)

        if assignment.boarding_status != BoardingStatus.ACTIVE:
            raise BoardingServiceError(
                f"Cannot unassign: assignment is already '{assignment.boarding_status.value}'",
                code="invalid_status",
            )

        assignment.check_out_date = date.today()
        assignment.boarding_status = BoardingStatus.WITHDRAWN

        # Release the bed back to available
        if assignment.bed_id:
            bed = await self._get_bed_or_raise(tenant_id, assignment.bed_id)
            bed.status = BedStatus.AVAILABLE

        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def update_assignment(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
        data: dict,
    ) -> StudentBoarding:
        """
        Update a boarding assignment (e.g., move to different bed/dormitory/house).

        If moving to a new bed, the old bed is released and the new bed
        is marked as occupied. Validates ownership at each level.
        """
        assignment = await self._get_assignment_or_raise(tenant_id, assignment_id)

        if assignment.boarding_status != BoardingStatus.ACTIVE:
            raise BoardingServiceError(
                "Cannot update: assignment is not active",
                code="invalid_status",
            )

        new_house_id = data.get("house_id")
        new_dormitory_id = data.get("dormitory_id")
        new_bed_id = data.get("bed_id")
        new_status = data.get("boarding_status")
        new_check_out = data.get("check_out_date")

        # Validate new house if changing
        if new_house_id and new_house_id != assignment.house_id:
            await self._get_house_or_raise(tenant_id, new_house_id)
            assignment.house_id = new_house_id

        # Validate new dormitory if changing
        if new_dormitory_id and new_dormitory_id != assignment.dormitory_id:
            target_house = new_house_id or assignment.house_id
            await self._verify_dormitory_belongs_to_house(
                tenant_id, new_dormitory_id, target_house
            )
            assignment.dormitory_id = new_dormitory_id

        # Handle bed change: release old bed, occupy new bed
        if new_bed_id is not None and new_bed_id != assignment.bed_id:
            # Release old bed
            if assignment.bed_id:
                old_bed = await self._get_bed_or_raise(tenant_id, assignment.bed_id)
                old_bed.status = BedStatus.AVAILABLE

            # Validate and occupy new bed
            new_bed = await self._get_bed_or_raise(tenant_id, new_bed_id)
            if new_bed.status == BedStatus.OCCUPIED:
                raise BoardingServiceError(
                    "New bed is already occupied",
                    code="bed_occupied",
                )
            if new_bed.status == BedStatus.MAINTENANCE:
                raise BoardingServiceError(
                    "New bed is under maintenance",
                    code="bed_maintenance",
                )
            new_bed.status = BedStatus.OCCUPIED
            assignment.bed_id = new_bed_id

        if new_status:
            assignment.boarding_status = BoardingStatus(new_status)

        if new_check_out:
            assignment.check_out_date = new_check_out

        assignment.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def get_assignments(
        self,
        tenant_id: UUID,
        school_id: UUID,
        house_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Sequence[StudentBoarding]:
        """List boarding assignments with student, house, and bed info loaded."""
        conditions = [
            StudentBoarding.tenant_id == tenant_id,
            StudentBoarding.school_id == school_id,
            StudentBoarding.deleted_at.is_(None),
        ]

        if house_id:
            conditions.append(StudentBoarding.house_id == house_id)
        if academic_year_id:
            conditions.append(StudentBoarding.academic_year_id == academic_year_id)
        if status:
            conditions.append(
                StudentBoarding.boarding_status == BoardingStatus(status)
            )

        query = (
            select(StudentBoarding)
            .where(and_(*conditions))
            .options(
                selectinload(StudentBoarding.student),
                selectinload(StudentBoarding.house),
                selectinload(StudentBoarding.dormitory),
                selectinload(StudentBoarding.bed),
                selectinload(StudentBoarding.academic_year),
            )
            .order_by(StudentBoarding.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_assignment(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
    ) -> StudentBoarding:
        """Get a single assignment with all related data loaded."""
        query = (
            select(StudentBoarding)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.id == assignment_id,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(StudentBoarding.student),
                selectinload(StudentBoarding.house),
                selectinload(StudentBoarding.dormitory),
                selectinload(StudentBoarding.bed),
                selectinload(StudentBoarding.academic_year),
            )
        )
        result = await self.db.execute(query)
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise BoardingServiceError(
                "Boarding assignment not found", code="not_found"
            )
        return assignment

    async def bulk_assign(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_ids: list[UUID],
        house_id: UUID,
        academic_year_id: UUID,
        check_in_date: date,
    ) -> dict:
        """
        Assign multiple students to a house without specific bed assignments.

        This is useful for initial house allocation at the start of a term.
        Students can be assigned individual beds later via update_assignment.

        Returns a summary dict with created, skipped, and failed counts.
        """
        # Verify house exists
        await self._get_house_or_raise(tenant_id, house_id)

        created = 0
        skipped = 0
        failed = 0
        errors: list[dict] = []

        for student_id in student_ids:
            try:
                # Check if already assigned for this academic year
                existing = await self.db.execute(
                    select(StudentBoarding).where(
                        and_(
                            StudentBoarding.tenant_id == tenant_id,
                            StudentBoarding.student_id == student_id,
                            StudentBoarding.academic_year_id == academic_year_id,
                            StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                            StudentBoarding.deleted_at.is_(None),
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                assignment = StudentBoarding(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    student_id=student_id,
                    house_id=house_id,
                    academic_year_id=academic_year_id,
                    boarding_status=BoardingStatus.ACTIVE,
                    check_in_date=check_in_date,
                )
                self.db.add(assignment)
                created += 1

            except BoardingServiceError as e:
                failed += 1
                errors.append({
                    "student_id": str(student_id),
                    "error": e.message,
                })
            except Exception as e:
                failed += 1
                logger.error(
                    "bulk_assign_unexpected_error",
                    student_id=str(student_id),
                    error=str(e),
                )
                errors.append({
                    "student_id": str(student_id),
                    "error": "Unexpected error during assignment",
                })

        await self.db.flush()

        return {
            "created": created,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
        }

    async def get_unassigned_boarders(
        self,
        tenant_id: UUID,
        school_id: UUID,
        academic_year_id: UUID,
    ) -> Sequence[Student]:
        """
        Get students who are enrolled as boarders but not yet assigned
        to a boarding house for the given academic year.

        Uses a subquery to exclude students who already have an active
        boarding assignment.
        """
        # Subquery: students who already have an active assignment this year
        assigned_subquery = (
            select(StudentBoarding.student_id)
            .where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.academic_year_id == academic_year_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
            .scalar_subquery()
        )

        # Query boarder students not in the assigned list
        query = (
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.school_id == school_id,
                    Student.is_boarder == True,  # noqa: E712 -- SQLAlchemy requires == for boolean
                    Student.status == StudentStatus.ACTIVE,
                    Student.deleted_at.is_(None),
                    Student.id.notin_(assigned_subquery),
                )
            )
            .order_by(Student.last_name, Student.first_name)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    # =========================
    # Internal Helpers
    # =========================

    async def _get_student_or_raise(self, tenant_id: UUID, student_id: UUID) -> Student:
        """Fetch a student or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise BoardingServiceError("Student not found", code="not_found")
        return student

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

    async def _get_bed_or_raise(self, tenant_id: UUID, bed_id: UUID) -> Bed:
        """Fetch a bed or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(Bed).where(
                and_(
                    Bed.tenant_id == tenant_id,
                    Bed.id == bed_id,
                    Bed.deleted_at.is_(None),
                )
            )
        )
        bed = result.scalar_one_or_none()
        if not bed:
            raise BoardingServiceError("Bed not found", code="not_found")
        return bed

    async def _get_assignment_or_raise(
        self, tenant_id: UUID, assignment_id: UUID
    ) -> StudentBoarding:
        """Fetch an assignment or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(StudentBoarding).where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.id == assignment_id,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise BoardingServiceError(
                "Boarding assignment not found", code="not_found"
            )
        return assignment

    async def _verify_dormitory_belongs_to_house(
        self, tenant_id: UUID, dormitory_id: UUID, house_id: UUID
    ) -> Dormitory:
        """
        Verify that a dormitory belongs to the specified house (IDOR prevention).

        Raises BoardingServiceError if not found or if it belongs to a different house.
        """
        result = await self.db.execute(
            select(Dormitory).where(
                and_(
                    Dormitory.tenant_id == tenant_id,
                    Dormitory.id == dormitory_id,
                    Dormitory.house_id == house_id,
                    Dormitory.deleted_at.is_(None),
                )
            )
        )
        dormitory = result.scalar_one_or_none()
        if not dormitory:
            raise BoardingServiceError(
                "Dormitory not found in the specified house",
                code="dormitory_house_mismatch",
            )
        return dormitory

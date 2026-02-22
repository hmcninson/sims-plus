"""
SIMS Plus - Transport Assignment Service

Business logic for assigning students to transport routes and stops.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transport import (
    StudentTransport,
    TransportAssignmentStatus,
    Route,
    RouteStop,
    Vehicle,
)
from app.models.student import Student
from app.models.academic import AcademicYear
from app.services.transport._shared import TransportServiceError

logger = structlog.get_logger()


class TransportAssignmentService:
    """Service for managing student transport assignments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def assign_student(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        route_id: UUID,
        stop_id: UUID,
        academic_year_id: UUID,
        status: str = "active",
        pickup_guardian_phone: Optional[str] = None,
        special_instructions: Optional[str] = None,
    ) -> StudentTransport:
        """
        Assign a student to a transport route and stop for an academic year.

        Validates:
        - Student, route, stop, and academic year all exist and belong to tenant
        - Stop belongs to the specified route (IDOR prevention)
        - Student is not already assigned for this academic year
        - Route has capacity (vehicle.capacity > current active assignments)
        """
        # Verify student belongs to tenant
        student = await self.db.execute(
            select(Student).where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        if not student.scalar_one_or_none():
            raise TransportServiceError("Student not found", code="student_not_found")

        # Verify academic year belongs to tenant
        ay = await self.db.execute(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.id == academic_year_id,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        if not ay.scalar_one_or_none():
            raise TransportServiceError(
                "Academic year not found", code="academic_year_not_found"
            )

        # Verify route belongs to tenant and is active
        route_result = await self.db.execute(
            select(Route)
            .where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.id == route_id,
                    Route.deleted_at.is_(None),
                )
            )
            .options(selectinload(Route.vehicle))
        )
        route = route_result.scalar_one_or_none()
        if not route:
            raise TransportServiceError("Route not found", code="route_not_found")
        if not route.is_active:
            raise TransportServiceError(
                "Cannot assign student to an inactive route",
                code="route_inactive",
            )

        # IDOR check: verify stop belongs to the specified route
        stop_result = await self.db.execute(
            select(RouteStop).where(
                and_(
                    RouteStop.tenant_id == tenant_id,
                    RouteStop.id == stop_id,
                    RouteStop.route_id == route_id,
                )
            )
        )
        if not stop_result.scalar_one_or_none():
            raise TransportServiceError(
                "Stop not found on the specified route",
                code="stop_not_on_route",
            )

        # Check for existing active/suspended assignment for this student+year
        existing = await self.db.execute(
            select(StudentTransport).where(
                and_(
                    StudentTransport.tenant_id == tenant_id,
                    StudentTransport.student_id == student_id,
                    StudentTransport.academic_year_id == academic_year_id,
                    StudentTransport.status.in_([
                        TransportAssignmentStatus.ACTIVE,
                        TransportAssignmentStatus.SUSPENDED,
                    ]),
                    StudentTransport.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise TransportServiceError(
                "Student already has a transport assignment for this academic year",
                code="duplicate_assignment",
            )

        # Check route capacity if vehicle is assigned
        if route.vehicle:
            capacity_info = await self.get_route_capacity(
                tenant_id, route_id, academic_year_id
            )
            if capacity_info["assigned_students"] >= capacity_info["vehicle_capacity"]:
                raise TransportServiceError(
                    f"Route is at full capacity ({capacity_info['vehicle_capacity']} seats)",
                    code="route_full",
                )

        assignment = StudentTransport(
            tenant_id=tenant_id,
            school_id=school_id,
            student_id=student_id,
            route_id=route_id,
            stop_id=stop_id,
            academic_year_id=academic_year_id,
            status=TransportAssignmentStatus(status),
            pickup_guardian_phone=pickup_guardian_phone,
            special_instructions=special_instructions,
        )
        self.db.add(assignment)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_student_transport_tenant_student_year" in error_msg:
                raise TransportServiceError(
                    "Student already has a transport assignment for this academic year (concurrent creation)",
                    code="duplicate_assignment",
                )
            raise TransportServiceError(
                "Database error while creating assignment",
                code="database_error",
            )

        await self.db.refresh(assignment)

        logger.info(
            "student_transport_assigned",
            student_id=str(student_id),
            route_id=str(route_id),
            stop_id=str(stop_id),
            tenant_id=str(tenant_id),
        )

        return assignment

    async def get_assignment(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
    ) -> StudentTransport:
        """Get a transport assignment by ID with related entities."""
        result = await self.db.execute(
            select(StudentTransport)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentTransport.tenant_id == tenant_id,
                    StudentTransport.id == assignment_id,
                    StudentTransport.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(StudentTransport.student),
                selectinload(StudentTransport.route),
                selectinload(StudentTransport.stop),
                selectinload(StudentTransport.academic_year),
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise TransportServiceError(
                "Transport assignment not found", code="not_found"
            )
        return assignment

    async def get_assignments(
        self,
        tenant_id: UUID,
        school_id: UUID,
        route_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[StudentTransport], int]:
        """
        List transport assignments with filters.

        Eagerly loads student, route, stop, and academic year for the list view.
        """
        conditions = [
            StudentTransport.tenant_id == tenant_id,
            StudentTransport.school_id == school_id,
            StudentTransport.deleted_at.is_(None),
        ]

        if route_id:
            conditions.append(StudentTransport.route_id == route_id)
        if academic_year_id:
            conditions.append(StudentTransport.academic_year_id == academic_year_id)
        if status:
            conditions.append(
                StudentTransport.status == TransportAssignmentStatus(status)
            )

        # Count
        count_query = select(func.count(StudentTransport.id)).where(
            and_(*conditions)
        )
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginated results with related entities
        query = (
            select(StudentTransport)
            .where(and_(*conditions))
            .options(
                selectinload(StudentTransport.student),
                selectinload(StudentTransport.route),
                selectinload(StudentTransport.stop),
                selectinload(StudentTransport.academic_year),
            )
            .order_by(StudentTransport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        assignments = result.scalars().all()

        return assignments, total

    async def update_assignment(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
        route_id: Optional[UUID] = None,
        stop_id: Optional[UUID] = None,
        status: Optional[str] = None,
        pickup_guardian_phone: Optional[str] = None,
        special_instructions: Optional[str] = None,
    ) -> StudentTransport:
        """
        Update a transport assignment (change route, stop, or status).

        When route changes, validates the new route has capacity.
        When stop changes, validates the stop belongs to the (possibly new) route.
        """
        assignment = await self.get_assignment(tenant_id, assignment_id)

        # Determine the effective route_id (new or existing)
        effective_route_id = route_id if route_id else assignment.route_id

        # If route is changing, verify new route and check capacity
        if route_id and route_id != assignment.route_id:
            route_result = await self.db.execute(
                select(Route)
                .where(
                    and_(
                        Route.tenant_id == tenant_id,
                        Route.id == route_id,
                        Route.deleted_at.is_(None),
                    )
                )
                .options(selectinload(Route.vehicle))
            )
            new_route = route_result.scalar_one_or_none()
            if not new_route:
                raise TransportServiceError("Route not found", code="route_not_found")
            if not new_route.is_active:
                raise TransportServiceError(
                    "Cannot assign student to an inactive route",
                    code="route_inactive",
                )

            # Check capacity on the new route
            if new_route.vehicle:
                capacity_info = await self.get_route_capacity(
                    tenant_id, route_id, assignment.academic_year_id
                )
                if capacity_info["assigned_students"] >= capacity_info["vehicle_capacity"]:
                    raise TransportServiceError(
                        f"Route is at full capacity ({capacity_info['vehicle_capacity']} seats)",
                        code="route_full",
                    )

            assignment.route_id = route_id

        # If stop is changing, verify it belongs to the effective route
        if stop_id and stop_id != assignment.stop_id:
            stop_result = await self.db.execute(
                select(RouteStop).where(
                    and_(
                        RouteStop.tenant_id == tenant_id,
                        RouteStop.id == stop_id,
                        RouteStop.route_id == effective_route_id,
                    )
                )
            )
            if not stop_result.scalar_one_or_none():
                raise TransportServiceError(
                    "Stop not found on the specified route",
                    code="stop_not_on_route",
                )
            assignment.stop_id = stop_id

        if status:
            assignment.status = TransportAssignmentStatus(status)
        if pickup_guardian_phone is not None:
            assignment.pickup_guardian_phone = pickup_guardian_phone
        if special_instructions is not None:
            assignment.special_instructions = special_instructions

        assignment.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def unassign_student(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
    ) -> StudentTransport:
        """
        Cancel a student's transport assignment by setting status to cancelled.

        Uses status change rather than soft delete so the assignment history
        is preserved for reporting purposes.
        """
        assignment = await self.get_assignment(tenant_id, assignment_id)

        if assignment.status == TransportAssignmentStatus.CANCELLED:
            raise TransportServiceError(
                "Assignment is already cancelled",
                code="already_cancelled",
            )

        assignment.status = TransportAssignmentStatus.CANCELLED
        assignment.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(assignment)

        logger.info(
            "student_transport_unassigned",
            assignment_id=str(assignment_id),
            student_id=str(assignment.student_id),
            tenant_id=str(tenant_id),
        )

        return assignment

    async def get_route_capacity(
        self,
        tenant_id: UUID,
        route_id: UUID,
        academic_year_id: UUID,
    ) -> dict:
        """
        Get route capacity info: vehicle capacity vs number of active assignments.

        Returns a dict with vehicle_capacity, assigned_students, and available_seats
        so the frontend can show capacity utilization.
        """
        # Get route with vehicle
        result = await self.db.execute(
            select(Route)
            .where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.id == route_id,
                    Route.deleted_at.is_(None),
                )
            )
            .options(selectinload(Route.vehicle))
        )
        route = result.scalar_one_or_none()
        if not route:
            raise TransportServiceError("Route not found", code="not_found")

        # Count active assignments for this route and academic year
        count_result = await self.db.execute(
            select(func.count(StudentTransport.id)).where(
                and_(
                    StudentTransport.tenant_id == tenant_id,
                    StudentTransport.route_id == route_id,
                    StudentTransport.academic_year_id == academic_year_id,
                    StudentTransport.status == TransportAssignmentStatus.ACTIVE,
                    StudentTransport.deleted_at.is_(None),
                )
            )
        )
        assigned_count = count_result.scalar_one()

        vehicle_capacity = route.vehicle.capacity if route.vehicle else 0

        return {
            "route_id": route.id,
            "route_name": route.name,
            "vehicle_id": route.vehicle.id if route.vehicle else None,
            "vehicle_registration": (
                route.vehicle.registration_number if route.vehicle else None
            ),
            "vehicle_capacity": vehicle_capacity,
            "assigned_students": assigned_count,
            "available_seats": max(0, vehicle_capacity - assigned_count),
        }

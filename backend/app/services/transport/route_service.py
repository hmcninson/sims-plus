"""
SIMS Plus - Route Service

Business logic for transport route management, route stops, and route manifests.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, or_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.transport import (
    Route,
    RouteType,
    RouteStop,
    StudentTransport,
    TransportAssignmentStatus,
    Vehicle,
    Driver,
)
from app.models.student import Student, Guardian, StudentGuardian
from app.services.transport._shared import TransportServiceError
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class RouteService:
    """Service for managing transport routes and stops."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Route CRUD
    # =========================

    async def create_route(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        route_code: str,
        route_type: str,
        description: Optional[str] = None,
        distance_km: Optional[float] = None,
        estimated_duration_minutes: Optional[int] = None,
        vehicle_id: Optional[UUID] = None,
        driver_id: Optional[UUID] = None,
        is_active: bool = True,
        transport_fee_per_term: Optional[float] = None,
    ) -> Route:
        """
        Create a new route.

        Validates that route_code is unique within the tenant. If vehicle_id
        or driver_id are provided, verifies they belong to the same tenant.
        """
        # Check for duplicate route code within tenant
        existing = await self.db.execute(
            select(Route).where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.route_code == route_code,
                    Route.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise TransportServiceError(
                f"Route with code '{route_code}' already exists",
                code="duplicate_route_code",
            )

        # Verify vehicle belongs to tenant if provided
        if vehicle_id:
            await self._verify_vehicle(tenant_id, vehicle_id)

        # Verify driver belongs to tenant if provided
        if driver_id:
            await self._verify_driver(tenant_id, driver_id)

        route = Route(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            route_code=route_code,
            route_type=RouteType(route_type),
            description=description,
            distance_km=distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            is_active=is_active,
            transport_fee_per_term=transport_fee_per_term,
        )
        self.db.add(route)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_routes_tenant_route_code" in error_msg:
                raise TransportServiceError(
                    f"Route with code '{route_code}' already exists (concurrent creation)",
                    code="duplicate_route_code",
                )
            raise TransportServiceError(
                "Database error while creating route",
                code="database_error",
            )

        await self.db.refresh(route)
        return route

    async def create_route_with_stops(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        route_code: str,
        route_type: str,
        stops_data: list[dict],
        description: Optional[str] = None,
        distance_km: Optional[float] = None,
        estimated_duration_minutes: Optional[int] = None,
        vehicle_id: Optional[UUID] = None,
        driver_id: Optional[UUID] = None,
        is_active: bool = True,
        transport_fee_per_term: Optional[float] = None,
    ) -> Route:
        """
        Create a route and its stops in a single transaction.

        This is the preferred method when the UI collects route + stops together,
        ensuring atomicity -- either everything is created or nothing is.
        """
        route = await self.create_route(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            route_code=route_code,
            route_type=route_type,
            description=description,
            distance_km=distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            is_active=is_active,
            transport_fee_per_term=transport_fee_per_term,
        )

        # Create stops in order
        for stop_data in stops_data:
            stop = RouteStop(
                tenant_id=tenant_id,
                route_id=route.id,
                stop_name=stop_data["stop_name"],
                stop_order=stop_data["stop_order"],
                pickup_time=stop_data.get("pickup_time"),
                dropoff_time=stop_data.get("dropoff_time"),
                latitude=stop_data.get("latitude"),
                longitude=stop_data.get("longitude"),
                landmark=stop_data.get("landmark"),
            )
            self.db.add(stop)

        await self.db.flush()

        # Reload the route with stops eagerly loaded
        result = await self.db.execute(
            select(Route)
            .where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.id == route.id,
                )
            )
            .options(selectinload(Route.stops))
        )
        return result.scalar_one()

    async def get_route(
        self,
        tenant_id: UUID,
        route_id: UUID,
    ) -> Route:
        """
        Get a route by ID with stops, vehicle, and driver eagerly loaded.

        Used for the route detail view where all related information is needed.
        """
        result = await self.db.execute(
            select(Route)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Route.tenant_id == tenant_id,
                    Route.id == route_id,
                    Route.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Route.stops),
                selectinload(Route.vehicle),
                selectinload(Route.driver),
            )
        )
        route = result.scalar_one_or_none()
        if not route:
            raise TransportServiceError("Route not found", code="not_found")
        return route

    async def get_routes(
        self,
        tenant_id: UUID,
        school_id: UUID,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Route], int]:
        """
        List routes with student count and vehicle/driver info.

        Eagerly loads vehicle and driver relationships so the list view
        can display assignment details without extra queries.
        """
        conditions = [
            Route.tenant_id == tenant_id,
            Route.school_id == school_id,
            Route.deleted_at.is_(None),
        ]

        if is_active is not None:
            conditions.append(Route.is_active == is_active)

        if search:
            safe_search = escape_ilike(search)
            search_term = f"%{safe_search}%"
            conditions.append(
                or_(
                    Route.name.ilike(search_term),
                    Route.route_code.ilike(search_term),
                )
            )

        # Count
        count_query = select(func.count(Route.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginated results with vehicle and driver eagerly loaded
        query = (
            select(Route)
            .where(and_(*conditions))
            .options(
                selectinload(Route.vehicle),
                selectinload(Route.driver),
            )
            .order_by(Route.route_code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        routes = result.scalars().all()

        return routes, total

    async def update_route(
        self,
        tenant_id: UUID,
        route_id: UUID,
        **kwargs,
    ) -> Route:
        """Update a route."""
        route = await self.get_route(tenant_id, route_id)

        # If route code is changing, check uniqueness
        new_code = kwargs.get("route_code")
        if new_code and new_code != route.route_code:
            existing = await self.db.execute(
                select(Route).where(
                    and_(
                        Route.tenant_id == tenant_id,
                        Route.route_code == new_code,
                        Route.id != route_id,
                        Route.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise TransportServiceError(
                    f"Route with code '{new_code}' already exists",
                    code="duplicate_route_code",
                )

        # Verify vehicle and driver belong to tenant if changing
        if "vehicle_id" in kwargs and kwargs["vehicle_id"]:
            await self._verify_vehicle(tenant_id, kwargs["vehicle_id"])
        if "driver_id" in kwargs and kwargs["driver_id"]:
            await self._verify_driver(tenant_id, kwargs["driver_id"])

        # Convert enum strings to enum values
        if "route_type" in kwargs and kwargs["route_type"]:
            kwargs["route_type"] = RouteType(kwargs["route_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(route, key):
                setattr(route, key, value)

        route.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(route)
        return route

    async def delete_route(
        self,
        tenant_id: UUID,
        route_id: UUID,
    ) -> bool:
        """
        Soft delete a route.

        Prevents deletion if the route has active student assignments.
        """
        route = await self.get_route(tenant_id, route_id)

        # Check for active student assignments
        active_assignments = await self.db.execute(
            select(func.count(StudentTransport.id)).where(
                and_(
                    StudentTransport.tenant_id == tenant_id,
                    StudentTransport.route_id == route_id,
                    StudentTransport.status == TransportAssignmentStatus.ACTIVE,
                    StudentTransport.deleted_at.is_(None),
                )
            )
        )
        if active_assignments.scalar_one() > 0:
            raise TransportServiceError(
                "Cannot delete route with active student assignments",
                code="route_in_use",
            )

        route.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # =========================
    # Route Stops
    # =========================

    async def add_stop(
        self,
        tenant_id: UUID,
        route_id: UUID,
        stop_name: str,
        stop_order: int,
        pickup_time=None,
        dropoff_time=None,
        latitude=None,
        longitude=None,
        landmark: Optional[str] = None,
    ) -> RouteStop:
        """
        Add a stop to a route.

        Verifies route belongs to the tenant (IDOR prevention).
        """
        # IDOR check: verify route belongs to tenant
        await self._get_route_basic(tenant_id, route_id)

        stop = RouteStop(
            tenant_id=tenant_id,
            route_id=route_id,
            stop_name=stop_name,
            stop_order=stop_order,
            pickup_time=pickup_time,
            dropoff_time=dropoff_time,
            latitude=latitude,
            longitude=longitude,
            landmark=landmark,
        )
        self.db.add(stop)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_route_stops_tenant_route_order" in error_msg:
                raise TransportServiceError(
                    f"A stop with order {stop_order} already exists on this route",
                    code="duplicate_stop_order",
                )
            raise TransportServiceError(
                "Database error while adding stop",
                code="database_error",
            )

        await self.db.refresh(stop)
        return stop

    async def update_stop(
        self,
        tenant_id: UUID,
        stop_id: UUID,
        **kwargs,
    ) -> RouteStop:
        """
        Update a route stop.

        RouteStop has TenantMixin (no SoftDeleteMixin), so we only check tenant_id.
        """
        result = await self.db.execute(
            select(RouteStop).where(
                and_(
                    # Defense-in-depth: filter by tenant_id
                    RouteStop.tenant_id == tenant_id,
                    RouteStop.id == stop_id,
                )
            )
        )
        stop = result.scalar_one_or_none()
        if not stop:
            raise TransportServiceError("Route stop not found", code="not_found")

        for key, value in kwargs.items():
            if value is not None and hasattr(stop, key):
                setattr(stop, key, value)

        stop.updated_at = datetime.now(UTC)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_route_stops_tenant_route_order" in error_msg:
                raise TransportServiceError(
                    f"A stop with this order already exists on the route",
                    code="duplicate_stop_order",
                )
            raise TransportServiceError(
                "Database error while updating stop",
                code="database_error",
            )

        await self.db.refresh(stop)
        return stop

    async def delete_stop(
        self,
        tenant_id: UUID,
        stop_id: UUID,
    ) -> bool:
        """
        Hard delete a route stop.

        RouteStop is a junction-style table (no SoftDeleteMixin), so we use
        hard delete. Checks for active student assignments at this stop first.
        """
        # Verify stop exists and belongs to tenant
        result = await self.db.execute(
            select(RouteStop).where(
                and_(
                    RouteStop.tenant_id == tenant_id,
                    RouteStop.id == stop_id,
                )
            )
        )
        stop = result.scalar_one_or_none()
        if not stop:
            raise TransportServiceError("Route stop not found", code="not_found")

        # Check for active student assignments at this stop
        active_at_stop = await self.db.execute(
            select(func.count(StudentTransport.id)).where(
                and_(
                    StudentTransport.tenant_id == tenant_id,
                    StudentTransport.stop_id == stop_id,
                    StudentTransport.status == TransportAssignmentStatus.ACTIVE,
                    StudentTransport.deleted_at.is_(None),
                )
            )
        )
        if active_at_stop.scalar_one() > 0:
            raise TransportServiceError(
                "Cannot delete stop with active student assignments",
                code="stop_in_use",
            )

        await self.db.delete(stop)
        await self.db.flush()
        return True

    async def reorder_stops(
        self,
        tenant_id: UUID,
        route_id: UUID,
        stop_ids_in_order: list[UUID],
    ) -> list[RouteStop]:
        """
        Reorder stops on a route by assigning new stop_order values.

        All stop IDs for the route must be provided. This ensures the caller
        has a complete view of the route and prevents partial reorderings
        that could leave gaps in the sequence.
        """
        # IDOR check: verify route belongs to tenant
        await self._get_route_basic(tenant_id, route_id)

        # Get all stops for this route
        result = await self.db.execute(
            select(RouteStop).where(
                and_(
                    RouteStop.tenant_id == tenant_id,
                    RouteStop.route_id == route_id,
                )
            )
        )
        stops = result.scalars().all()
        stop_map = {stop.id: stop for stop in stops}

        # Validate all stop IDs are present
        existing_ids = set(stop_map.keys())
        provided_ids = set(stop_ids_in_order)
        if existing_ids != provided_ids:
            raise TransportServiceError(
                "All stop IDs for the route must be provided for reordering",
                code="incomplete_stop_list",
            )

        # Temporarily set all orders to negative values to avoid unique constraint
        # violations during reordering (the constraint is on tenant_id + route_id + stop_order)
        for i, stop in enumerate(stops):
            stop.stop_order = -(i + 1)
        await self.db.flush()

        # Now assign the correct order
        for new_order, stop_id in enumerate(stop_ids_in_order, start=1):
            stop_map[stop_id].stop_order = new_order

        await self.db.flush()

        # Return stops in new order
        return [stop_map[sid] for sid in stop_ids_in_order]

    # =========================
    # Route Manifest
    # =========================

    async def get_route_manifest(
        self,
        tenant_id: UUID,
        route_id: UUID,
        academic_year_id: UUID,
    ) -> dict:
        """
        Get a route manifest: list of assigned students with their stops
        and guardian contact information.

        Used for generating printable manifests for drivers and for the
        route detail view showing who is at each stop.
        """
        # Get route with stops
        route = await self.get_route(tenant_id, route_id)

        # Get active student assignments for this route and academic year
        result = await self.db.execute(
            select(StudentTransport)
            .where(
                and_(
                    StudentTransport.tenant_id == tenant_id,
                    StudentTransport.route_id == route_id,
                    StudentTransport.academic_year_id == academic_year_id,
                    StudentTransport.status == TransportAssignmentStatus.ACTIVE,
                    StudentTransport.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(StudentTransport.student),
                selectinload(StudentTransport.stop),
            )
        )
        assignments = result.scalars().all()

        # Get guardian info for all assigned students
        student_ids = [a.student_id for a in assignments]
        guardian_map: dict[UUID, list[dict]] = {}

        if student_ids:
            guardian_result = await self.db.execute(
                select(StudentGuardian)
                .where(
                    and_(
                        StudentGuardian.tenant_id == tenant_id,
                        StudentGuardian.student_id.in_(student_ids),
                    )
                )
                .options(selectinload(StudentGuardian.guardian_rel))
            )
            student_guardians = guardian_result.scalars().all()

            for sg in student_guardians:
                if sg.student_id not in guardian_map:
                    guardian_map[sg.student_id] = []
                guardian = sg.guardian_rel
                guardian_map[sg.student_id].append({
                    "name": f"{guardian.first_name} {guardian.last_name}",
                    "phone": guardian.phone,
                    "relationship": sg.relation_type.value if sg.relation_type else None,
                    "is_emergency_contact": sg.is_emergency_contact,
                    "can_pickup": sg.can_pickup,
                })

        # Build manifest grouped by stop
        stop_map: dict[UUID, list[dict]] = {}
        for assignment in assignments:
            stop_id = assignment.stop_id
            if stop_id not in stop_map:
                stop_map[stop_id] = []

            student = assignment.student
            stop_map[stop_id].append({
                "student_id": student.id,
                "student_name": f"{student.first_name} {student.last_name}",
                "student_number": student.student_id,
                "pickup_guardian_phone": assignment.pickup_guardian_phone,
                "special_instructions": assignment.special_instructions,
                "guardians": guardian_map.get(student.id, []),
            })

        # Build ordered manifest
        manifest_stops = []
        for stop in sorted(route.stops, key=lambda s: s.stop_order):
            manifest_stops.append({
                "stop_id": stop.id,
                "stop_name": stop.stop_name,
                "stop_order": stop.stop_order,
                "pickup_time": stop.pickup_time.isoformat() if stop.pickup_time else None,
                "dropoff_time": stop.dropoff_time.isoformat() if stop.dropoff_time else None,
                "landmark": stop.landmark,
                "students": stop_map.get(stop.id, []),
            })

        return {
            "route_id": route.id,
            "route_name": route.name,
            "route_code": route.route_code,
            "vehicle_registration": route.vehicle.registration_number if route.vehicle else None,
            "driver_name": route.driver.full_name if route.driver else None,
            "driver_phone": route.driver.phone if route.driver else None,
            "total_students": len(assignments),
            "stops": manifest_stops,
        }

    # =========================
    # Helper Methods
    # =========================

    async def _get_route_basic(self, tenant_id: UUID, route_id: UUID) -> Route:
        """Get a route without eager loading (for IDOR checks)."""
        result = await self.db.execute(
            select(Route).where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.id == route_id,
                    Route.deleted_at.is_(None),
                )
            )
        )
        route = result.scalar_one_or_none()
        if not route:
            raise TransportServiceError("Route not found", code="not_found")
        return route

    async def _verify_vehicle(self, tenant_id: UUID, vehicle_id: UUID) -> None:
        """Verify a vehicle exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.id == vehicle_id,
                    Vehicle.deleted_at.is_(None),
                )
            )
        )
        if not result.scalar_one_or_none():
            raise TransportServiceError(
                "Vehicle not found",
                code="vehicle_not_found",
            )

    async def _verify_driver(self, tenant_id: UUID, driver_id: UUID) -> None:
        """Verify a driver exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Driver).where(
                and_(
                    Driver.tenant_id == tenant_id,
                    Driver.id == driver_id,
                    Driver.deleted_at.is_(None),
                )
            )
        )
        if not result.scalar_one_or_none():
            raise TransportServiceError(
                "Driver not found",
                code="driver_not_found",
            )

    async def get_student_count_for_route(
        self,
        tenant_id: UUID,
        route_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> int:
        """Get the number of active student assignments for a route."""
        conditions = [
            StudentTransport.tenant_id == tenant_id,
            StudentTransport.route_id == route_id,
            StudentTransport.status == TransportAssignmentStatus.ACTIVE,
            StudentTransport.deleted_at.is_(None),
        ]
        if academic_year_id:
            conditions.append(
                StudentTransport.academic_year_id == academic_year_id
            )

        result = await self.db.execute(
            select(func.count(StudentTransport.id)).where(and_(*conditions))
        )
        return result.scalar_one()

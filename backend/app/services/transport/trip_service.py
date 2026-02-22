"""
SIMS Plus - Trip Service

Business logic for trip logging, lifecycle management, and trip statistics.
"""

from datetime import date, datetime, time, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, extract
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transport import (
    TripLog,
    TripType,
    TripStatus,
    Route,
    Vehicle,
    Driver,
)
from app.services.transport._shared import TransportServiceError

logger = structlog.get_logger()


class TripService:
    """Service for managing transport trip logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_trip(
        self,
        tenant_id: UUID,
        school_id: UUID,
        route_id: UUID,
        vehicle_id: UUID,
        driver_id: UUID,
        trip_date: date,
        trip_type: str,
        student_count: int,
        logged_by_id: UUID,
        departure_time: Optional[time] = None,
        arrival_time: Optional[time] = None,
        odometer_start: Optional[int] = None,
        odometer_end: Optional[int] = None,
        status: str = "scheduled",
        incidents: Optional[str] = None,
    ) -> TripLog:
        """
        Create a new trip log entry.

        Validates that route, vehicle, and driver all exist and belong to the
        tenant. The unique constraint prevents duplicate trip entries for the
        same route + date + trip_type combination.
        """
        # Verify route belongs to tenant
        route_result = await self.db.execute(
            select(Route).where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.id == route_id,
                    Route.deleted_at.is_(None),
                )
            )
        )
        if not route_result.scalar_one_or_none():
            raise TransportServiceError("Route not found", code="route_not_found")

        # Verify vehicle belongs to tenant
        vehicle_result = await self.db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.id == vehicle_id,
                    Vehicle.deleted_at.is_(None),
                )
            )
        )
        if not vehicle_result.scalar_one_or_none():
            raise TransportServiceError("Vehicle not found", code="vehicle_not_found")

        # Verify driver belongs to tenant
        driver_result = await self.db.execute(
            select(Driver).where(
                and_(
                    Driver.tenant_id == tenant_id,
                    Driver.id == driver_id,
                    Driver.deleted_at.is_(None),
                )
            )
        )
        if not driver_result.scalar_one_or_none():
            raise TransportServiceError("Driver not found", code="driver_not_found")

        trip = TripLog(
            tenant_id=tenant_id,
            school_id=school_id,
            route_id=route_id,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            trip_date=trip_date,
            trip_type=TripType(trip_type),
            student_count=student_count,
            logged_by_id=logged_by_id,
            departure_time=departure_time,
            arrival_time=arrival_time,
            odometer_start=odometer_start,
            odometer_end=odometer_end,
            status=TripStatus(status),
            incidents=incidents,
        )
        self.db.add(trip)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_trip_logs_tenant_route_date_type" in error_msg:
                raise TransportServiceError(
                    f"A trip already exists for this route on {trip_date} ({trip_type})",
                    code="duplicate_trip",
                )
            raise TransportServiceError(
                "Database error while creating trip",
                code="database_error",
            )

        await self.db.refresh(trip)

        logger.info(
            "trip_created",
            trip_id=str(trip.id),
            route_id=str(route_id),
            trip_date=str(trip_date),
            trip_type=trip_type,
            tenant_id=str(tenant_id),
        )

        return trip

    async def get_trip(
        self,
        tenant_id: UUID,
        trip_id: UUID,
    ) -> TripLog:
        """Get a trip by ID with route, vehicle, and driver loaded."""
        result = await self.db.execute(
            select(TripLog)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    TripLog.tenant_id == tenant_id,
                    TripLog.id == trip_id,
                    TripLog.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(TripLog.route),
                selectinload(TripLog.vehicle),
                selectinload(TripLog.driver),
                selectinload(TripLog.logged_by),
            )
        )
        trip = result.scalar_one_or_none()
        if not trip:
            raise TransportServiceError("Trip not found", code="not_found")
        return trip

    async def get_trips(
        self,
        tenant_id: UUID,
        school_id: UUID,
        route_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[TripLog], int]:
        """
        List trips with optional filters for route, date range, and status.

        Eagerly loads route, vehicle, and driver for the list view.
        """
        conditions = [
            TripLog.tenant_id == tenant_id,
            TripLog.school_id == school_id,
            TripLog.deleted_at.is_(None),
        ]

        if route_id:
            conditions.append(TripLog.route_id == route_id)
        if date_from:
            conditions.append(TripLog.trip_date >= date_from)
        if date_to:
            conditions.append(TripLog.trip_date <= date_to)
        if status:
            conditions.append(TripLog.status == TripStatus(status))

        # Count
        count_query = select(func.count(TripLog.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginated results
        query = (
            select(TripLog)
            .where(and_(*conditions))
            .options(
                selectinload(TripLog.route),
                selectinload(TripLog.vehicle),
                selectinload(TripLog.driver),
                selectinload(TripLog.logged_by),
            )
            .order_by(TripLog.trip_date.desc(), TripLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        trips = result.scalars().all()

        return trips, total

    # =========================
    # Trip Lifecycle
    # =========================

    async def start_trip(
        self,
        tenant_id: UUID,
        trip_id: UUID,
        departure_time: Optional[time] = None,
    ) -> TripLog:
        """
        Start a trip by setting status to in_progress and recording departure time.

        Only scheduled trips can be started.
        """
        trip = await self._get_trip_basic(tenant_id, trip_id)

        if trip.status != TripStatus.SCHEDULED:
            raise TransportServiceError(
                f"Cannot start trip with status '{trip.status.value}'. Only scheduled trips can be started.",
                code="invalid_status_transition",
            )

        trip.status = TripStatus.IN_PROGRESS
        # Use provided departure time or current time
        trip.departure_time = departure_time or datetime.now(UTC).time()
        trip.updated_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(trip)

        logger.info(
            "trip_started",
            trip_id=str(trip_id),
            tenant_id=str(tenant_id),
        )

        return trip

    async def complete_trip(
        self,
        tenant_id: UUID,
        trip_id: UUID,
        arrival_time: Optional[time] = None,
        odometer_end: Optional[int] = None,
        incidents: Optional[str] = None,
    ) -> TripLog:
        """
        Complete a trip by setting status to completed and recording arrival details.

        Only in_progress trips can be completed.
        """
        trip = await self._get_trip_basic(tenant_id, trip_id)

        if trip.status != TripStatus.IN_PROGRESS:
            raise TransportServiceError(
                f"Cannot complete trip with status '{trip.status.value}'. Only in-progress trips can be completed.",
                code="invalid_status_transition",
            )

        trip.status = TripStatus.COMPLETED
        trip.arrival_time = arrival_time or datetime.now(UTC).time()

        if odometer_end is not None:
            # Validate odometer end is greater than start if both are present
            if trip.odometer_start is not None and odometer_end < trip.odometer_start:
                raise TransportServiceError(
                    "Odometer end reading must be greater than or equal to start reading",
                    code="invalid_odometer",
                )
            trip.odometer_end = odometer_end

        if incidents is not None:
            trip.incidents = incidents

        trip.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(trip)

        logger.info(
            "trip_completed",
            trip_id=str(trip_id),
            tenant_id=str(tenant_id),
        )

        return trip

    async def cancel_trip(
        self,
        tenant_id: UUID,
        trip_id: UUID,
    ) -> TripLog:
        """
        Cancel a trip.

        Only scheduled or in-progress trips can be cancelled. Completed trips
        cannot be cancelled (use a correction/notes process instead).
        """
        trip = await self._get_trip_basic(tenant_id, trip_id)

        if trip.status == TripStatus.COMPLETED:
            raise TransportServiceError(
                "Cannot cancel a completed trip",
                code="invalid_status_transition",
            )
        if trip.status == TripStatus.CANCELLED:
            raise TransportServiceError(
                "Trip is already cancelled",
                code="already_cancelled",
            )

        trip.status = TripStatus.CANCELLED
        trip.updated_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(trip)

        logger.info(
            "trip_cancelled",
            trip_id=str(trip_id),
            tenant_id=str(tenant_id),
        )

        return trip

    # =========================
    # Trip Statistics
    # =========================

    async def get_trip_stats(
        self,
        tenant_id: UUID,
        school_id: UUID,
        month: int,
        year: int,
    ) -> dict:
        """
        Get aggregate trip statistics for a given month.

        Returns total trips, completed trips, average student count, and
        per-route breakdowns for fleet management dashboards.
        """
        conditions = [
            TripLog.tenant_id == tenant_id,
            TripLog.school_id == school_id,
            TripLog.deleted_at.is_(None),
            extract("month", TripLog.trip_date) == month,
            extract("year", TripLog.trip_date) == year,
        ]

        # Total trips
        total_result = await self.db.execute(
            select(func.count(TripLog.id)).where(and_(*conditions))
        )
        total_trips = total_result.scalar_one()

        # Completed trips
        completed_result = await self.db.execute(
            select(func.count(TripLog.id)).where(
                and_(*conditions, TripLog.status == TripStatus.COMPLETED)
            )
        )
        completed_trips = completed_result.scalar_one()

        # Cancelled trips
        cancelled_result = await self.db.execute(
            select(func.count(TripLog.id)).where(
                and_(*conditions, TripLog.status == TripStatus.CANCELLED)
            )
        )
        cancelled_trips = cancelled_result.scalar_one()

        # Average student count (only for completed trips to get meaningful data)
        avg_result = await self.db.execute(
            select(func.avg(TripLog.student_count)).where(
                and_(*conditions, TripLog.status == TripStatus.COMPLETED)
            )
        )
        avg_students = avg_result.scalar()
        avg_student_count = round(float(avg_students), 1) if avg_students else 0.0

        # Per-route breakdown
        route_stats_result = await self.db.execute(
            select(
                TripLog.route_id,
                func.count(TripLog.id).label("trip_count"),
                func.sum(TripLog.student_count).label("total_students"),
                func.avg(TripLog.student_count).label("avg_students"),
            )
            .where(
                and_(*conditions, TripLog.status == TripStatus.COMPLETED)
            )
            .group_by(TripLog.route_id)
        )
        route_rows = route_stats_result.all()

        # Get route names for the breakdown
        route_ids = [row.route_id for row in route_rows]
        route_names: dict[UUID, str] = {}
        if route_ids:
            routes_result = await self.db.execute(
                select(Route.id, Route.name, Route.route_code).where(
                    and_(
                        Route.tenant_id == tenant_id,
                        Route.id.in_(route_ids),
                    )
                )
            )
            for r in routes_result.all():
                route_names[r.id] = f"{r.name} ({r.route_code})"

        by_route = [
            {
                "route_id": row.route_id,
                "route_name": route_names.get(row.route_id, "Unknown"),
                "trip_count": row.trip_count,
                "total_students": row.total_students or 0,
                "avg_students": round(float(row.avg_students), 1) if row.avg_students else 0.0,
            }
            for row in route_rows
        ]

        return {
            "month": month,
            "year": year,
            "total_trips": total_trips,
            "completed_trips": completed_trips,
            "cancelled_trips": cancelled_trips,
            "avg_student_count": avg_student_count,
            "by_route": by_route,
        }

    # =========================
    # Helper Methods
    # =========================

    async def _get_trip_basic(self, tenant_id: UUID, trip_id: UUID) -> TripLog:
        """Get a trip without eager loading (for status transitions)."""
        result = await self.db.execute(
            select(TripLog).where(
                and_(
                    TripLog.tenant_id == tenant_id,
                    TripLog.id == trip_id,
                    TripLog.deleted_at.is_(None),
                )
            )
        )
        trip = result.scalar_one_or_none()
        if not trip:
            raise TransportServiceError("Trip not found", code="not_found")
        return trip

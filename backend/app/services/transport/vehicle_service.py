"""
SIMS Plus - Vehicle Service

Business logic for vehicle management, maintenance tracking, and document expiry alerts.
"""

from datetime import date, datetime, timedelta, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transport import (
    Vehicle,
    VehicleStatus,
    VehicleType,
    VehicleMaintenance,
    MaintenanceType,
    Route,
)
from app.services.transport._shared import TransportServiceError
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class VehicleService:
    """Service for managing transport vehicles and maintenance records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Vehicle CRUD
    # =========================

    async def create_vehicle(
        self,
        tenant_id: UUID,
        school_id: UUID,
        registration_number: str,
        vehicle_type: str,
        capacity: int,
        make: Optional[str] = None,
        model_name: Optional[str] = None,
        year: Optional[int] = None,
        status: str = "active",
        insurance_expiry: Optional[date] = None,
        roadworthy_expiry: Optional[date] = None,
        gps_tracker_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Vehicle:
        """
        Create a new vehicle.

        Validates that registration_number is unique within the tenant before
        creating to provide a clear error instead of a database constraint violation.
        """
        # Check for duplicate registration number within tenant
        existing = await self.db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.registration_number == registration_number,
                    Vehicle.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise TransportServiceError(
                f"Vehicle with registration number '{registration_number}' already exists",
                code="duplicate_registration",
            )

        vehicle = Vehicle(
            tenant_id=tenant_id,
            school_id=school_id,
            registration_number=registration_number,
            vehicle_type=VehicleType(vehicle_type),
            capacity=capacity,
            make=make,
            model_name=model_name,
            year=year,
            status=VehicleStatus(status),
            insurance_expiry=insurance_expiry,
            roadworthy_expiry=roadworthy_expiry,
            gps_tracker_id=gps_tracker_id,
            notes=notes,
        )
        self.db.add(vehicle)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_vehicles_tenant_registration" in error_msg:
                raise TransportServiceError(
                    f"Vehicle with registration number '{registration_number}' already exists (concurrent creation)",
                    code="duplicate_registration",
                )
            raise TransportServiceError(
                "Database error while creating vehicle",
                code="database_error",
            )

        await self.db.refresh(vehicle)
        return vehicle

    async def get_vehicle(
        self,
        tenant_id: UUID,
        vehicle_id: UUID,
    ) -> Vehicle:
        """Get a vehicle by ID."""
        result = await self.db.execute(
            select(Vehicle).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.id == vehicle_id,
                    Vehicle.deleted_at.is_(None),
                )
            )
        )
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise TransportServiceError("Vehicle not found", code="not_found")
        return vehicle

    async def get_vehicles(
        self,
        tenant_id: UUID,
        school_id: UUID,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Vehicle], int]:
        """
        List vehicles with optional status filter and search.

        Returns vehicles along with maintenance alerts for documents
        (insurance, roadworthy) expiring within 30 days.
        """
        conditions = [
            Vehicle.tenant_id == tenant_id,
            Vehicle.school_id == school_id,
            Vehicle.deleted_at.is_(None),
        ]

        if status:
            conditions.append(Vehicle.status == VehicleStatus(status))

        if search:
            safe_search = escape_ilike(search)
            search_term = f"%{safe_search}%"
            conditions.append(
                func.concat(
                    Vehicle.registration_number, " ",
                    func.coalesce(Vehicle.make, ""), " ",
                    func.coalesce(Vehicle.model_name, ""),
                ).ilike(search_term)
            )

        # Count
        count_query = select(func.count(Vehicle.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginated results
        query = (
            select(Vehicle)
            .where(and_(*conditions))
            .order_by(Vehicle.registration_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        vehicles = result.scalars().all()

        return vehicles, total

    async def update_vehicle(
        self,
        tenant_id: UUID,
        vehicle_id: UUID,
        **kwargs,
    ) -> Vehicle:
        """Update a vehicle."""
        vehicle = await self.get_vehicle(tenant_id, vehicle_id)

        # If registration number is changing, check uniqueness
        new_reg = kwargs.get("registration_number")
        if new_reg and new_reg != vehicle.registration_number:
            existing = await self.db.execute(
                select(Vehicle).where(
                    and_(
                        Vehicle.tenant_id == tenant_id,
                        Vehicle.registration_number == new_reg,
                        Vehicle.id != vehicle_id,
                        Vehicle.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise TransportServiceError(
                    f"Vehicle with registration number '{new_reg}' already exists",
                    code="duplicate_registration",
                )

        # Convert enum strings to enum values
        if "vehicle_type" in kwargs and kwargs["vehicle_type"]:
            kwargs["vehicle_type"] = VehicleType(kwargs["vehicle_type"])
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = VehicleStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(vehicle, key):
                setattr(vehicle, key, value)

        vehicle.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(vehicle)
        return vehicle

    async def delete_vehicle(
        self,
        tenant_id: UUID,
        vehicle_id: UUID,
    ) -> bool:
        """
        Soft delete a vehicle.

        Prevents deletion if the vehicle is currently assigned to active routes.
        """
        vehicle = await self.get_vehicle(tenant_id, vehicle_id)

        # Check for active route assignments
        active_routes = await self.db.execute(
            select(func.count(Route.id)).where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.vehicle_id == vehicle_id,
                    Route.is_active.is_(True),
                    Route.deleted_at.is_(None),
                )
            )
        )
        if active_routes.scalar_one() > 0:
            raise TransportServiceError(
                "Cannot delete vehicle that is assigned to active routes",
                code="vehicle_in_use",
            )

        vehicle.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_vehicles_with_alerts(
        self,
        tenant_id: UUID,
        school_id: UUID,
    ) -> list[dict]:
        """
        Get vehicles with expiring documents (insurance or roadworthy
        certificates expiring within the next 30 days).

        Returns a list of dicts with vehicle info and alert details so the
        frontend can display warnings.
        """
        alert_threshold = date.today() + timedelta(days=30)
        today = date.today()

        result = await self.db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.school_id == school_id,
                    Vehicle.deleted_at.is_(None),
                    Vehicle.status != VehicleStatus.RETIRED,
                    # At least one document is expiring or already expired
                    func.or_(
                        and_(
                            Vehicle.insurance_expiry.isnot(None),
                            Vehicle.insurance_expiry <= alert_threshold,
                        ),
                        and_(
                            Vehicle.roadworthy_expiry.isnot(None),
                            Vehicle.roadworthy_expiry <= alert_threshold,
                        ),
                    ),
                )
            ).order_by(
                # Most urgent first
                func.least(
                    func.coalesce(Vehicle.insurance_expiry, alert_threshold),
                    func.coalesce(Vehicle.roadworthy_expiry, alert_threshold),
                )
            )
        )
        vehicles = result.scalars().all()

        alerts = []
        for v in vehicles:
            vehicle_alerts = []
            if v.insurance_expiry and v.insurance_expiry <= alert_threshold:
                if v.insurance_expiry < today:
                    vehicle_alerts.append({
                        "type": "insurance",
                        "status": "expired",
                        "expiry_date": v.insurance_expiry.isoformat(),
                    })
                else:
                    vehicle_alerts.append({
                        "type": "insurance",
                        "status": "expiring_soon",
                        "expiry_date": v.insurance_expiry.isoformat(),
                        "days_remaining": (v.insurance_expiry - today).days,
                    })

            if v.roadworthy_expiry and v.roadworthy_expiry <= alert_threshold:
                if v.roadworthy_expiry < today:
                    vehicle_alerts.append({
                        "type": "roadworthy",
                        "status": "expired",
                        "expiry_date": v.roadworthy_expiry.isoformat(),
                    })
                else:
                    vehicle_alerts.append({
                        "type": "roadworthy",
                        "status": "expiring_soon",
                        "expiry_date": v.roadworthy_expiry.isoformat(),
                        "days_remaining": (v.roadworthy_expiry - today).days,
                    })

            alerts.append({
                "vehicle_id": v.id,
                "registration_number": v.registration_number,
                "make": v.make,
                "model_name": v.model_name,
                "status": v.status.value,
                "alerts": vehicle_alerts,
            })

        return alerts

    # =========================
    # Vehicle Maintenance
    # =========================

    async def create_maintenance(
        self,
        tenant_id: UUID,
        school_id: UUID,
        vehicle_id: UUID,
        logged_by_id: UUID,
        maintenance_type: str,
        description: str,
        service_date: date,
        cost: Optional[float] = None,
        next_service_date: Optional[date] = None,
        odometer_reading: Optional[int] = None,
        service_provider: Optional[str] = None,
        invoice_number: Optional[str] = None,
    ) -> VehicleMaintenance:
        """
        Log a maintenance record for a vehicle.

        Optionally updates the vehicle's next_service_date if provided, giving
        fleet managers a single place to track upcoming service needs.
        """
        # IDOR check: verify vehicle belongs to this tenant
        vehicle = await self.get_vehicle(tenant_id, vehicle_id)

        maintenance = VehicleMaintenance(
            tenant_id=tenant_id,
            school_id=school_id,
            vehicle_id=vehicle_id,
            logged_by_id=logged_by_id,
            maintenance_type=MaintenanceType(maintenance_type),
            description=description,
            service_date=service_date,
            cost=cost,
            next_service_date=next_service_date,
            odometer_reading=odometer_reading,
            service_provider=service_provider,
            invoice_number=invoice_number,
        )
        self.db.add(maintenance)
        await self.db.flush()
        await self.db.refresh(maintenance)

        # If vehicle is currently in maintenance status and this is a completed
        # routine/repair, consider keeping it in maintenance until explicit status change.
        # We do NOT auto-change vehicle status here to avoid unintended side effects.

        logger.info(
            "vehicle_maintenance_logged",
            vehicle_id=str(vehicle_id),
            maintenance_type=maintenance_type,
            tenant_id=str(tenant_id),
        )

        return maintenance

    async def get_maintenance_history(
        self,
        tenant_id: UUID,
        vehicle_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[VehicleMaintenance], int]:
        """
        Get maintenance history for a vehicle, ordered by most recent first.

        Verifies vehicle belongs to tenant before querying (IDOR prevention).
        """
        # IDOR check: verify vehicle belongs to this tenant
        await self.get_vehicle(tenant_id, vehicle_id)

        conditions = [
            VehicleMaintenance.tenant_id == tenant_id,
            VehicleMaintenance.vehicle_id == vehicle_id,
            VehicleMaintenance.deleted_at.is_(None),
        ]

        count_query = select(func.count(VehicleMaintenance.id)).where(
            and_(*conditions)
        )
        total = (await self.db.execute(count_query)).scalar_one()

        query = (
            select(VehicleMaintenance)
            .where(and_(*conditions))
            .order_by(desc(VehicleMaintenance.service_date))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        records = result.scalars().all()

        return records, total

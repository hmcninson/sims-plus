"""
SIMS Plus - Driver Service

Business logic for driver management and license expiry tracking.
"""

from datetime import date, datetime, timedelta, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transport import (
    Driver,
    DriverStatus,
    Route,
)
from app.services.transport._shared import TransportServiceError
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class DriverService:
    """Service for managing transport drivers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_driver(
        self,
        tenant_id: UUID,
        school_id: UUID,
        first_name: str,
        last_name: str,
        phone: str,
        license_number: str,
        license_expiry: date,
        license_class: str,
        staff_id: Optional[UUID] = None,
        status: str = "active",
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
    ) -> Driver:
        """
        Create a new driver.

        Validates that license_number is unique within the tenant to prevent
        duplicate driver records for the same physical person.
        """
        # Check for duplicate license number within tenant
        existing = await self.db.execute(
            select(Driver).where(
                and_(
                    Driver.tenant_id == tenant_id,
                    Driver.license_number == license_number,
                    Driver.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise TransportServiceError(
                f"Driver with license number '{license_number}' already exists",
                code="duplicate_license",
            )

        driver = Driver(
            tenant_id=tenant_id,
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            license_number=license_number,
            license_expiry=license_expiry,
            license_class=license_class,
            staff_id=staff_id,
            status=DriverStatus(status),
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
        )
        self.db.add(driver)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_drivers_tenant_license" in error_msg:
                raise TransportServiceError(
                    f"Driver with license number '{license_number}' already exists (concurrent creation)",
                    code="duplicate_license",
                )
            raise TransportServiceError(
                "Database error while creating driver",
                code="database_error",
            )

        await self.db.refresh(driver)
        return driver

    async def get_driver(
        self,
        tenant_id: UUID,
        driver_id: UUID,
    ) -> Driver:
        """Get a driver by ID."""
        result = await self.db.execute(
            select(Driver).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Driver.tenant_id == tenant_id,
                    Driver.id == driver_id,
                    Driver.deleted_at.is_(None),
                )
            )
        )
        driver = result.scalar_one_or_none()
        if not driver:
            raise TransportServiceError("Driver not found", code="not_found")
        return driver

    async def get_drivers(
        self,
        tenant_id: UUID,
        school_id: UUID,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Driver], int]:
        """
        List drivers with optional status filter, search, and license expiry alerts.

        Search matches against first name, last name, phone, and license number.
        """
        conditions = [
            Driver.tenant_id == tenant_id,
            Driver.school_id == school_id,
            Driver.deleted_at.is_(None),
        ]

        if status:
            conditions.append(Driver.status == DriverStatus(status))

        if search:
            safe_search = escape_ilike(search)
            search_term = f"%{safe_search}%"
            conditions.append(
                or_(
                    Driver.first_name.ilike(search_term),
                    Driver.last_name.ilike(search_term),
                    Driver.phone.ilike(search_term),
                    Driver.license_number.ilike(search_term),
                )
            )

        # Count
        count_query = select(func.count(Driver.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginated results
        query = (
            select(Driver)
            .where(and_(*conditions))
            .order_by(Driver.last_name, Driver.first_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        drivers = result.scalars().all()

        return drivers, total

    async def update_driver(
        self,
        tenant_id: UUID,
        driver_id: UUID,
        **kwargs,
    ) -> Driver:
        """Update a driver."""
        driver = await self.get_driver(tenant_id, driver_id)

        # If license number is changing, check uniqueness
        new_license = kwargs.get("license_number")
        if new_license and new_license != driver.license_number:
            existing = await self.db.execute(
                select(Driver).where(
                    and_(
                        Driver.tenant_id == tenant_id,
                        Driver.license_number == new_license,
                        Driver.id != driver_id,
                        Driver.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise TransportServiceError(
                    f"Driver with license number '{new_license}' already exists",
                    code="duplicate_license",
                )

        # Convert enum strings to enum values
        if "status" in kwargs and kwargs["status"]:
            kwargs["status"] = DriverStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(driver, key):
                setattr(driver, key, value)

        driver.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(driver)
        return driver

    async def delete_driver(
        self,
        tenant_id: UUID,
        driver_id: UUID,
    ) -> bool:
        """
        Soft delete a driver.

        Prevents deletion if the driver is currently assigned to active routes.
        """
        driver = await self.get_driver(tenant_id, driver_id)

        # Check for active route assignments
        active_routes = await self.db.execute(
            select(func.count(Route.id)).where(
                and_(
                    Route.tenant_id == tenant_id,
                    Route.driver_id == driver_id,
                    Route.is_active.is_(True),
                    Route.deleted_at.is_(None),
                )
            )
        )
        if active_routes.scalar_one() > 0:
            raise TransportServiceError(
                "Cannot delete driver that is assigned to active routes",
                code="driver_in_use",
            )

        driver.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

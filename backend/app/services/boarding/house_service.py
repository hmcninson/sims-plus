"""
SIMS Plus - House & Dormitory Service

Business logic for managing boarding houses, dormitories, and beds.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.boarding import (
    House,
    Dormitory,
    Bed,
    BedStatus,
    StudentBoarding,
    BoardingStatus,
)
from app.utils.sanitize import escape_ilike

from app.services.boarding._shared import BoardingServiceError

logger = structlog.get_logger()


class HouseService:
    """Service for managing boarding houses, dormitories, and beds."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # House Methods
    # =========================

    async def create_house(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data: dict,
    ) -> House:
        """
        Create a new boarding house.

        Validates that the house name and code are unique within the tenant
        before creation to provide a clear error message.
        """
        # Check for duplicate name within tenant
        existing_name = await self.db.execute(
            select(House).where(
                and_(
                    House.tenant_id == tenant_id,
                    House.name == data["name"],
                    House.deleted_at.is_(None),
                )
            )
        )
        if existing_name.scalar_one_or_none():
            raise BoardingServiceError(
                f"A house named '{data['name']}' already exists",
                code="duplicate_house_name",
            )

        # Check for duplicate code within tenant
        existing_code = await self.db.execute(
            select(House).where(
                and_(
                    House.tenant_id == tenant_id,
                    House.house_code == data["house_code"],
                    House.deleted_at.is_(None),
                )
            )
        )
        if existing_code.scalar_one_or_none():
            raise BoardingServiceError(
                f"House code '{data['house_code']}' already exists",
                code="duplicate_house_code",
            )

        house = House(
            tenant_id=tenant_id,
            school_id=school_id,
            name=data["name"],
            house_code=data["house_code"],
            gender=data["gender"],
            capacity=data["capacity"],
            house_parent_id=data.get("house_parent_id"),
            description=data.get("description"),
            is_active=data.get("is_active", True),
        )
        self.db.add(house)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_houses_tenant_name" in error_msg:
                raise BoardingServiceError(
                    f"A house named '{data['name']}' already exists (concurrent creation)",
                    code="duplicate_house_name",
                )
            if "uq_houses_tenant_house_code" in error_msg:
                raise BoardingServiceError(
                    f"House code '{data['house_code']}' already exists (concurrent creation)",
                    code="duplicate_house_code",
                )
            logger.error("database_integrity_error", operation="create_house", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred while creating house",
                code="database_error",
            )

        await self.db.refresh(house)
        return house

    async def get_houses(
        self,
        tenant_id: UUID,
        school_id: UUID,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[dict]:
        """
        List all houses for a school with current occupancy stats.

        Occupancy is calculated by counting active StudentBoarding records
        per house, giving an accurate real-time view.
        """
        conditions = [
            House.tenant_id == tenant_id,
            House.school_id == school_id,
            House.deleted_at.is_(None),
        ]

        if search:
            safe_search = escape_ilike(search)
            search_term = f"%{safe_search}%"
            conditions.append(
                House.name.ilike(search_term)
            )

        if is_active is not None:
            conditions.append(House.is_active == is_active)

        # Query houses
        query = (
            select(House)
            .where(and_(*conditions))
            .order_by(House.name)
        )
        result = await self.db.execute(query)
        houses = result.scalars().all()

        # Build occupancy stats per house in a single query
        occupancy_query = (
            select(
                StudentBoarding.house_id,
                func.count(StudentBoarding.id).label("occupancy"),
            )
            .where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.school_id == school_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
            .group_by(StudentBoarding.house_id)
        )
        occupancy_result = await self.db.execute(occupancy_query)
        occupancy_map = {
            row.house_id: row.occupancy for row in occupancy_result.all()
        }

        return [
            {
                "house": house,
                "current_occupancy": occupancy_map.get(house.id, 0),
            }
            for house in houses
        ]

    async def get_house(
        self,
        tenant_id: UUID,
        house_id: UUID,
    ) -> House:
        """Get a single house with dormitories loaded."""
        query = (
            select(House)
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    House.tenant_id == tenant_id,
                    House.id == house_id,
                    House.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(House.dormitories),
                selectinload(House.house_parent),
            )
        )
        result = await self.db.execute(query)
        house = result.scalar_one_or_none()
        if not house:
            raise BoardingServiceError("House not found", code="not_found")
        return house

    async def update_house(
        self,
        tenant_id: UUID,
        house_id: UUID,
        data: dict,
    ) -> House:
        """Update an existing house, validating uniqueness of name/code."""
        house = await self._get_house_or_raise(tenant_id, house_id)

        # Validate unique name if changing
        if data.get("name") and data["name"] != house.name:
            existing = await self.db.execute(
                select(House).where(
                    and_(
                        House.tenant_id == tenant_id,
                        House.name == data["name"],
                        House.id != house_id,
                        House.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise BoardingServiceError(
                    f"A house named '{data['name']}' already exists",
                    code="duplicate_house_name",
                )

        # Validate unique code if changing
        if data.get("house_code") and data["house_code"] != house.house_code:
            existing = await self.db.execute(
                select(House).where(
                    and_(
                        House.tenant_id == tenant_id,
                        House.house_code == data["house_code"],
                        House.id != house_id,
                        House.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise BoardingServiceError(
                    f"House code '{data['house_code']}' already exists",
                    code="duplicate_house_code",
                )

        for key, value in data.items():
            if value is not None and hasattr(house, key):
                setattr(house, key, value)

        house.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(house)
        return house

    async def delete_house(
        self,
        tenant_id: UUID,
        house_id: UUID,
    ) -> bool:
        """Soft delete a house."""
        house = await self._get_house_or_raise(tenant_id, house_id)
        house.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_house_occupancy(
        self,
        tenant_id: UUID,
        house_id: UUID,
    ) -> dict:
        """
        Get occupancy details for a house: current students vs capacity.

        Returns a dict with capacity, current_occupancy, and available_spaces.
        """
        house = await self._get_house_or_raise(tenant_id, house_id)

        # Count active boarders in this house
        occupancy_result = await self.db.execute(
            select(func.count(StudentBoarding.id)).where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.house_id == house_id,
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
        )
        current_occupancy = occupancy_result.scalar_one()

        return {
            "house_id": house.id,
            "house_name": house.name,
            "capacity": house.capacity,
            "current_occupancy": current_occupancy,
            "available_spaces": max(0, house.capacity - current_occupancy),
        }

    # =========================
    # Dormitory Methods
    # =========================

    async def create_dormitory(
        self,
        tenant_id: UUID,
        school_id: UUID,
        house_id: UUID,
        data: dict,
    ) -> Dormitory:
        """
        Create a new dormitory within a house.

        Validates the house exists and the dormitory name is unique within the house.
        """
        # Verify the house exists and belongs to this tenant
        await self._get_house_or_raise(tenant_id, house_id)

        # Check for duplicate name within house
        existing = await self.db.execute(
            select(Dormitory).where(
                and_(
                    Dormitory.tenant_id == tenant_id,
                    Dormitory.house_id == house_id,
                    Dormitory.name == data["name"],
                    Dormitory.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise BoardingServiceError(
                f"Dormitory '{data['name']}' already exists in this house",
                code="duplicate_dormitory_name",
            )

        dormitory = Dormitory(
            tenant_id=tenant_id,
            school_id=school_id,
            house_id=house_id,
            name=data["name"],
            floor=data.get("floor"),
            capacity=data["capacity"],
            dormitory_type=data["dormitory_type"],
            is_active=data.get("is_active", True),
        )
        self.db.add(dormitory)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_dormitories_tenant_house_name" in error_msg:
                raise BoardingServiceError(
                    f"Dormitory '{data['name']}' already exists in this house (concurrent creation)",
                    code="duplicate_dormitory_name",
                )
            logger.error("database_integrity_error", operation="create_dormitory", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred while creating dormitory",
                code="database_error",
            )

        await self.db.refresh(dormitory)
        return dormitory

    async def get_dormitories(
        self,
        tenant_id: UUID,
        house_id: UUID,
    ) -> list[dict]:
        """
        List all dormitories for a house with bed counts.

        Returns each dormitory along with total, occupied, and available bed counts.
        """
        # Verify house exists
        await self._get_house_or_raise(tenant_id, house_id)

        dormitories_result = await self.db.execute(
            select(Dormitory)
            .where(
                and_(
                    Dormitory.tenant_id == tenant_id,
                    Dormitory.house_id == house_id,
                    Dormitory.deleted_at.is_(None),
                )
            )
            .order_by(Dormitory.name)
        )
        dormitories = dormitories_result.scalars().all()

        # Get bed counts per dormitory in batch
        bed_stats_query = (
            select(
                Bed.dormitory_id,
                func.count(Bed.id).label("total_beds"),
                func.count(Bed.id).filter(Bed.status == BedStatus.OCCUPIED).label("occupied_beds"),
                func.count(Bed.id).filter(Bed.status == BedStatus.AVAILABLE).label("available_beds"),
            )
            .where(
                and_(
                    Bed.tenant_id == tenant_id,
                    Bed.dormitory_id.in_([d.id for d in dormitories]),
                    Bed.deleted_at.is_(None),
                )
            )
            .group_by(Bed.dormitory_id)
        )
        bed_stats_result = await self.db.execute(bed_stats_query)
        bed_stats_map = {
            row.dormitory_id: {
                "total_beds": row.total_beds,
                "occupied_beds": row.occupied_beds,
                "available_beds": row.available_beds,
            }
            for row in bed_stats_result.all()
        }

        return [
            {
                "dormitory": dorm,
                "bed_count": bed_stats_map.get(dorm.id, {}).get("total_beds", 0),
                "occupied_beds": bed_stats_map.get(dorm.id, {}).get("occupied_beds", 0),
                "available_beds": bed_stats_map.get(dorm.id, {}).get("available_beds", 0),
            }
            for dorm in dormitories
        ]

    async def update_dormitory(
        self,
        tenant_id: UUID,
        dormitory_id: UUID,
        data: dict,
    ) -> Dormitory:
        """Update a dormitory."""
        dormitory = await self._get_dormitory_or_raise(tenant_id, dormitory_id)

        # Validate unique name within house if changing
        if data.get("name") and data["name"] != dormitory.name:
            existing = await self.db.execute(
                select(Dormitory).where(
                    and_(
                        Dormitory.tenant_id == tenant_id,
                        Dormitory.house_id == dormitory.house_id,
                        Dormitory.name == data["name"],
                        Dormitory.id != dormitory_id,
                        Dormitory.deleted_at.is_(None),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise BoardingServiceError(
                    f"Dormitory '{data['name']}' already exists in this house",
                    code="duplicate_dormitory_name",
                )

        for key, value in data.items():
            if value is not None and hasattr(dormitory, key):
                setattr(dormitory, key, value)

        dormitory.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(dormitory)
        return dormitory

    async def delete_dormitory(
        self,
        tenant_id: UUID,
        dormitory_id: UUID,
    ) -> bool:
        """Soft delete a dormitory."""
        dormitory = await self._get_dormitory_or_raise(tenant_id, dormitory_id)
        dormitory.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # =========================
    # Bed Methods
    # =========================

    async def create_beds(
        self,
        tenant_id: UUID,
        school_id: UUID,
        dormitory_id: UUID,
        beds_data: list[dict],
    ) -> list[Bed]:
        """
        Bulk create beds for a dormitory.

        Validates the dormitory exists and that bed numbers are unique within
        the dormitory. Rolls back cleanly on duplicate detection.
        """
        dormitory = await self._get_dormitory_or_raise(tenant_id, dormitory_id)

        # Collect all bed numbers to check for duplicates within the batch
        bed_numbers = [b["bed_number"] for b in beds_data]
        if len(bed_numbers) != len(set(bed_numbers)):
            raise BoardingServiceError(
                "Duplicate bed numbers in the request",
                code="duplicate_bed_number",
            )

        # Check for existing bed numbers in this dormitory
        existing_result = await self.db.execute(
            select(Bed.bed_number).where(
                and_(
                    Bed.tenant_id == tenant_id,
                    Bed.dormitory_id == dormitory_id,
                    Bed.bed_number.in_(bed_numbers),
                    Bed.deleted_at.is_(None),
                )
            )
        )
        existing_numbers = set(existing_result.scalars().all())
        if existing_numbers:
            raise BoardingServiceError(
                f"Bed numbers already exist: {', '.join(sorted(existing_numbers))}",
                code="duplicate_bed_number",
            )

        created_beds = []
        for bed_data in beds_data:
            bed = Bed(
                tenant_id=tenant_id,
                school_id=school_id,
                dormitory_id=dormitory_id,
                bed_number=bed_data["bed_number"],
                bed_type=bed_data["bed_type"],
                status=bed_data.get("status", BedStatus.AVAILABLE),
                is_active=bed_data.get("is_active", True),
            )
            self.db.add(bed)
            created_beds.append(bed)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_beds_tenant_dormitory_bed_number" in error_msg:
                raise BoardingServiceError(
                    "One or more bed numbers already exist (concurrent creation)",
                    code="duplicate_bed_number",
                )
            logger.error("database_integrity_error", operation="create_beds", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred while creating beds",
                code="database_error",
            )

        # Refresh all created beds to get generated IDs and defaults
        for bed in created_beds:
            await self.db.refresh(bed)

        return created_beds

    async def get_beds(
        self,
        tenant_id: UUID,
        dormitory_id: UUID,
        status: Optional[str] = None,
    ) -> list[dict]:
        """
        List beds for a dormitory with current student assignment info.

        Joins with active StudentBoarding records to show which student
        occupies each bed.
        """
        conditions = [
            Bed.tenant_id == tenant_id,
            Bed.dormitory_id == dormitory_id,
            Bed.deleted_at.is_(None),
        ]

        if status:
            conditions.append(Bed.status == BedStatus(status))

        beds_result = await self.db.execute(
            select(Bed)
            .where(and_(*conditions))
            .order_by(Bed.bed_number)
        )
        beds = beds_result.scalars().all()

        # Get current occupants for all beds in one query
        occupant_query = (
            select(
                StudentBoarding.bed_id,
                StudentBoarding.student_id,
            )
            .where(
                and_(
                    StudentBoarding.tenant_id == tenant_id,
                    StudentBoarding.bed_id.in_([b.id for b in beds]),
                    StudentBoarding.boarding_status == BoardingStatus.ACTIVE,
                    StudentBoarding.deleted_at.is_(None),
                )
            )
        )
        occupant_result = await self.db.execute(occupant_query)
        occupant_map = {
            row.bed_id: row.student_id for row in occupant_result.all()
        }

        return [
            {
                "bed": bed,
                "occupant_id": occupant_map.get(bed.id),
            }
            for bed in beds
        ]

    async def update_bed(
        self,
        tenant_id: UUID,
        bed_id: UUID,
        data: dict,
    ) -> Bed:
        """Update a bed's details (number, type, status, etc.)."""
        bed = await self._get_bed_or_raise(tenant_id, bed_id)

        for key, value in data.items():
            if value is not None and hasattr(bed, key):
                # Convert string status to enum if needed
                if key == "status" and isinstance(value, str):
                    value = BedStatus(value)
                setattr(bed, key, value)

        bed.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(bed)
        return bed

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

    async def _get_dormitory_or_raise(self, tenant_id: UUID, dormitory_id: UUID) -> Dormitory:
        """Fetch a dormitory or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(Dormitory).where(
                and_(
                    Dormitory.tenant_id == tenant_id,
                    Dormitory.id == dormitory_id,
                    Dormitory.deleted_at.is_(None),
                )
            )
        )
        dormitory = result.scalar_one_or_none()
        if not dormitory:
            raise BoardingServiceError("Dormitory not found", code="not_found")
        return dormitory

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

"""
SIMS Plus - Dining Service

Business logic for managing boarding dining hall meals and statistics.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, extract
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boarding import (
    DiningMeal,
    MealType,
)

from app.services.boarding._shared import BoardingServiceError

logger = structlog.get_logger()


class DiningService:
    """Service for managing dining hall meals and meal statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_meal(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data: dict,
    ) -> DiningMeal:
        """
        Create a new meal record.

        Enforces the unique constraint on (tenant, school, date, meal_type)
        so each meal type can only be logged once per day per school.
        """
        meal = DiningMeal(
            tenant_id=tenant_id,
            school_id=school_id,
            date=data["date"],
            meal_type=MealType(data["meal_type"]),
            menu_description=data.get("menu_description"),
            head_count=data.get("head_count"),
            prepared_by=data.get("prepared_by"),
            notes=data.get("notes"),
        )
        self.db.add(meal)

        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if e.orig else str(e)
            if "uq_dining_meals_tenant_school_date_meal" in error_msg:
                raise BoardingServiceError(
                    f"A {data['meal_type']} meal record already exists for {data['date']}",
                    code="duplicate_meal",
                )
            logger.error("database_integrity_error", operation="log_meal", error=error_msg)
            raise BoardingServiceError(
                "An unexpected database error occurred while logging meal",
                code="database_error",
            )

        await self.db.refresh(meal)
        return meal

    async def get_meals(
        self,
        tenant_id: UUID,
        school_id: UUID,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Sequence[DiningMeal]:
        """
        List meal records for a school, optionally filtered by date range.

        Results are ordered by date descending, then by meal type, so the
        most recent meals appear first.
        """
        conditions = [
            DiningMeal.tenant_id == tenant_id,
            DiningMeal.school_id == school_id,
            DiningMeal.deleted_at.is_(None),
        ]

        if date_from:
            conditions.append(DiningMeal.date >= date_from)
        if date_to:
            conditions.append(DiningMeal.date <= date_to)

        query = (
            select(DiningMeal)
            .where(and_(*conditions))
            .order_by(DiningMeal.date.desc(), DiningMeal.meal_type)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_meal(
        self,
        tenant_id: UUID,
        meal_id: UUID,
        data: dict,
    ) -> DiningMeal:
        """Update a meal record."""
        meal = await self._get_meal_or_raise(tenant_id, meal_id)

        for key, value in data.items():
            if value is not None and hasattr(meal, key):
                # Convert string meal_type to enum if needed
                if key == "meal_type" and isinstance(value, str):
                    value = MealType(value)
                setattr(meal, key, value)

        meal.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(meal)
        return meal

    async def delete_meal(
        self,
        tenant_id: UUID,
        meal_id: UUID,
    ) -> bool:
        """Soft delete a meal record."""
        meal = await self._get_meal_or_raise(tenant_id, meal_id)
        meal.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_dining_stats(
        self,
        tenant_id: UUID,
        school_id: UUID,
        month: int,
        year: int,
    ) -> dict:
        """
        Get dining statistics for a specific month.

        Aggregates total meals served, average head count, and per-meal-type
        breakdowns for the specified month and year.
        """
        conditions = [
            DiningMeal.tenant_id == tenant_id,
            DiningMeal.school_id == school_id,
            DiningMeal.deleted_at.is_(None),
            extract("month", DiningMeal.date) == month,
            extract("year", DiningMeal.date) == year,
        ]

        # Total meals count
        total_result = await self.db.execute(
            select(func.count(DiningMeal.id)).where(and_(*conditions))
        )
        total_meals = total_result.scalar_one()

        # Average head count (exclude meals with no head count recorded)
        avg_result = await self.db.execute(
            select(func.avg(DiningMeal.head_count)).where(
                and_(
                    *conditions,
                    DiningMeal.head_count.isnot(None),
                )
            )
        )
        avg_head_count = avg_result.scalar_one()

        # Per-meal-type breakdown
        type_breakdown_query = (
            select(
                DiningMeal.meal_type,
                func.count(DiningMeal.id).label("count"),
                func.avg(DiningMeal.head_count).label("avg_head_count"),
            )
            .where(and_(*conditions))
            .group_by(DiningMeal.meal_type)
        )
        type_result = await self.db.execute(type_breakdown_query)
        by_meal_type = {
            row.meal_type.value: {
                "count": row.count,
                "avg_head_count": round(float(row.avg_head_count), 1) if row.avg_head_count else None,
            }
            for row in type_result.all()
        }

        return {
            "month": month,
            "year": year,
            "total_meals": total_meals,
            "avg_head_count": round(float(avg_head_count), 1) if avg_head_count else None,
            "by_meal_type": by_meal_type,
        }

    # =========================
    # Internal Helpers
    # =========================

    async def _get_meal_or_raise(self, tenant_id: UUID, meal_id: UUID) -> DiningMeal:
        """Fetch a meal or raise BoardingServiceError if not found."""
        result = await self.db.execute(
            select(DiningMeal).where(
                and_(
                    DiningMeal.tenant_id == tenant_id,
                    DiningMeal.id == meal_id,
                    DiningMeal.deleted_at.is_(None),
                )
            )
        )
        meal = result.scalar_one_or_none()
        if not meal:
            raise BoardingServiceError("Meal not found", code="not_found")
        return meal

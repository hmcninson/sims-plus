"""
SIMS Plus - Dining Endpoints

CRUD endpoints for managing boarding dining hall meals and statistics.
"""

import math
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.boarding import (
    DiningMealCreate,
    DiningMealListResponse,
    DiningMealResponse,
    DiningMealUpdate,
)
from app.services.boarding import BoardingServiceError, DiningService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


@router.post(
    "/dining/meals",
    response_model=DiningMealResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log meal",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def log_meal(
    data: DiningMealCreate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DiningMealResponse:
    """Log a new dining meal record."""
    school_id = _get_school_id(user)
    service = DiningService(db)

    try:
        meal = await service.log_meal(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            data=data.model_dump(),
        )
        return DiningMealResponse(
            id=meal.id,
            tenant_id=meal.tenant_id,
            school_id=meal.school_id,
            date=meal.date,
            meal_type=meal.meal_type.value
            if hasattr(meal.meal_type, "value")
            else meal.meal_type,
            menu_description=meal.menu_description,
            head_count=meal.head_count,
            prepared_by=meal.prepared_by,
            notes=meal.notes,
            created_at=meal.created_at,
            updated_at=meal.updated_at,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/dining/meals",
    response_model=DiningMealListResponse,
    summary="List meals",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_meals(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    date_from: date | None = Query(None, description="Start date filter"),
    date_to: date | None = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> DiningMealListResponse:
    """List dining meal records with optional date range filtering."""
    school_id = _get_school_id(user)
    service = DiningService(db)

    meals = await service.get_meals(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
    )

    # Manual pagination
    total = len(meals)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = meals[start:end]

    items = []
    for meal in page_items:
        items.append(
            DiningMealResponse(
                id=meal.id,
                tenant_id=meal.tenant_id,
                school_id=meal.school_id,
                date=meal.date,
                meal_type=meal.meal_type.value
                if hasattr(meal.meal_type, "value")
                else meal.meal_type,
                menu_description=meal.menu_description,
                head_count=meal.head_count,
                prepared_by=meal.prepared_by,
                notes=meal.notes,
                created_at=meal.created_at,
                updated_at=meal.updated_at,
            )
        )

    return DiningMealListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.put(
    "/dining/meals/{meal_id}",
    response_model=DiningMealResponse,
    summary="Update meal",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def update_meal(
    meal_id: UUID,
    data: DiningMealUpdate,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> DiningMealResponse:
    """Update a meal record."""
    service = DiningService(db)

    try:
        meal = await service.update_meal(
            tenant_id=tenant.tenant_id,
            meal_id=meal_id,
            data=data.model_dump(exclude_unset=True),
        )
        return DiningMealResponse(
            id=meal.id,
            tenant_id=meal.tenant_id,
            school_id=meal.school_id,
            date=meal.date,
            meal_type=meal.meal_type.value
            if hasattr(meal.meal_type, "value")
            else meal.meal_type,
            menu_description=meal.menu_description,
            head_count=meal.head_count,
            prepared_by=meal.prepared_by,
            notes=meal.notes,
            created_at=meal.created_at,
            updated_at=meal.updated_at,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.delete(
    "/dining/meals/{meal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete meal",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def delete_meal(
    meal_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft delete a meal record."""
    service = DiningService(db)

    try:
        await service.delete_meal(
            tenant_id=tenant.tenant_id,
            meal_id=meal_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/dining/stats",
    summary="Dining statistics",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_dining_stats(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    month: int = Query(..., ge=1, le=12, description="Month number (1-12)"),
    year: int = Query(..., ge=2020, le=2099, description="Year"),
) -> dict:
    """
    Get dining statistics for a specific month.

    Returns total meals, average head count, and per-meal-type breakdown.
    """
    school_id = _get_school_id(user)
    service = DiningService(db)

    return await service.get_dining_stats(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        month=month,
        year=year,
    )

"""
SIMS Plus - Preschool Supply Schemas

Pydantic schemas for per-student supply inventory tracking.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID as StdUUID

from pydantic import ConfigDict, Field

from app.schemas.preschool.core import BaseSchema

UUID = StdUUID


# =========================
# Request Schemas
# =========================


class PreschoolSupplyCreate(BaseSchema):
    """Schema for creating a new supply item for a student."""

    item_name: Annotated[str, Field(min_length=1, max_length=100)]
    quantity_remaining: Annotated[int, Field(ge=0)] = 0
    low_stock_threshold: Annotated[int, Field(ge=0)] = 3
    notes: Annotated[str | None, Field(max_length=500)] = None


class PreschoolSupplyUpdate(BaseSchema):
    """Schema for updating supply metadata (name, threshold, notes)."""

    item_name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    low_stock_threshold: Annotated[int | None, Field(ge=0)] = None
    notes: Annotated[str | None, Field(max_length=500)] = None


class SupplyUseRequest(BaseSchema):
    """Schema for decrementing supply quantity."""

    quantity: Annotated[int, Field(ge=1)] = 1


class SupplyRestockRequest(BaseSchema):
    """Schema for incrementing supply quantity."""

    quantity: Annotated[int, Field(ge=1)]


# =========================
# Response Schemas
# =========================


class PreschoolSupplyResponse(BaseSchema):
    """Schema for supply item response with computed is_low_stock flag."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    student_id: UUID
    item_name: str
    quantity_remaining: int
    low_stock_threshold: int
    is_low_stock: bool
    last_restocked_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

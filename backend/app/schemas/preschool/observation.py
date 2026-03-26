"""
SIMS Plus - Preschool Observation Schemas

Pydantic schemas for progress observations and daily activity logs.
"""

from datetime import date, datetime, time
from typing import Annotated
from uuid import UUID as StdUUID

from pydantic import BaseModel, Field

from app.schemas.preschool.core import BaseSchema

# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Progress Observation Schemas
# =========================


class AttachmentSchema(BaseModel):
    """Schema for observation attachments."""

    url: str
    type: str  # image, video, document
    thumbnail: str | None = None
    filename: str | None = None


class ProgressObservationBase(BaseSchema):
    """Base schema for progress observations."""

    observation_type: str = "anecdote"  # anecdote, milestone, photo, video, incident
    title: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    observation_date: date
    share_with_parents: bool = True
    is_highlight: bool = False


class ProgressObservationCreate(ProgressObservationBase):
    """Schema for creating an observation."""

    student_id: UUID
    learning_area_id: UUID | None = None
    attachments: list[AttachmentSchema] | None = None


class ProgressObservationUpdate(BaseModel):
    """Schema for updating an observation."""

    observation_type: str | None = None
    title: Annotated[str | None, Field(min_length=1, max_length=255)] = None
    description: str | None = None
    observation_date: date | None = None
    learning_area_id: UUID | None = None
    attachments: list[AttachmentSchema] | None = None
    share_with_parents: bool | None = None
    is_highlight: bool | None = None


class ProgressObservationResponse(ProgressObservationBase):
    """Schema for observation response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    learning_area_id: UUID | None = None
    attachments: list[AttachmentSchema] | None = None
    recorded_by: UUID | None = None
    created_at: datetime
    updated_at: datetime



# =========================
# Daily Activity Log Schemas
# =========================


class MealEntry(BaseModel):
    """Schema for a meal entry."""

    type: str  # breakfast, snack, lunch, dinner
    time: str | None = None  # HH:MM format
    amount: str = "all"  # none, little, some, most, all
    notes: str | None = None


class DailyActivityLogBase(BaseSchema):
    """Base schema for daily activity logs."""

    log_date: date
    arrival_time: time | None = None
    arrival_mood: str | None = None  # happy, tired, upset, excited, calm, sick
    departure_time: time | None = None
    departure_mood: str | None = None
    nap_start: time | None = None
    nap_end: time | None = None
    nap_quality: str | None = None  # good, restless, didnt_sleep
    diaper_changes: int | None = None
    potty_successes: int | None = None
    accidents: int | None = None
    notes: str | None = None
    highlights: str | None = None


class DailyActivityLogCreate(DailyActivityLogBase):
    """Schema for creating a daily log."""

    student_id: UUID
    meals: list[MealEntry] | None = None
    activities: list[str] | None = None


class DailyActivityLogUpdate(BaseModel):
    """Schema for updating a daily log."""

    arrival_time: time | None = None
    arrival_mood: str | None = None
    departure_time: time | None = None
    departure_mood: str | None = None
    meals: list[MealEntry] | None = None
    nap_start: time | None = None
    nap_end: time | None = None
    nap_quality: str | None = None
    diaper_changes: int | None = None
    potty_successes: int | None = None
    accidents: int | None = None
    activities: list[str] | None = None
    notes: str | None = None
    highlights: str | None = None


class DailyActivityLogResponse(DailyActivityLogBase):
    """Schema for daily log response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    meals: list[MealEntry] | None = None
    activities: list[str] | None = None
    logged_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

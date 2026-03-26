"""
SIMS Plus - School Event Schemas

Pydantic schemas for school tours, open days, and orientation events.
"""

from datetime import date, datetime, time
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Enums for schema validation ---


class EventTypeEnum(str, Enum):
    OPEN_DAY = "open_day"
    TOUR = "tour"
    ORIENTATION = "orientation"


class EventStatusEnum(str, Enum):
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# --- Event Schemas ---


class EventCreate(BaseSchema):
    """Create a school event."""

    event_type: EventTypeEnum
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    event_date: date
    start_time: time | None = None
    end_time: time | None = None
    venue: str | None = Field(None, max_length=255)
    capacity: int | None = Field(None, ge=1)
    guide_id: UUID | None = None


class EventUpdate(BaseSchema):
    """Update event details. Only upcoming events can be updated."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    event_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    venue: str | None = Field(None, max_length=255)
    capacity: int | None = Field(None, ge=1)
    guide_id: UUID | None = None


class EventResponse(BaseSchema):
    """Full event detail response."""

    id: UUID
    school_id: UUID
    event_type: str
    name: str
    description: str | None
    event_date: date
    start_time: time | None
    end_time: time | None
    venue: str | None
    capacity: int | None
    registered_count: int
    status: str
    guide_id: UUID | None
    guide_name: str | None = None
    created_at: datetime
    updated_at: datetime


class EventListResponse(BaseSchema):
    """Paginated event list."""

    items: list[EventResponse]
    total: int
    page: int
    page_size: int
    pages: int


# --- Registration Schemas ---


class RegistrationCreate(BaseSchema):
    """Register for a school event."""

    registrant_name: str = Field(..., min_length=1, max_length=200)
    registrant_phone: str = Field(..., min_length=1, max_length=20)
    registrant_email: EmailStr | None = None
    student_name: str | None = Field(None, max_length=200)
    notes: str | None = None


class RegistrationResponse(BaseSchema):
    """Registration detail."""

    id: UUID
    event_id: UUID
    registrant_name: str
    registrant_phone: str
    registrant_email: str | None
    student_name: str | None
    attended: bool
    registered_at: datetime
    notes: str | None
    created_at: datetime


class AttendanceUpdate(BaseSchema):
    """Mark attendance for a registration."""

    attended: bool


# --- Event Stats ---


class EventStatsResponse(BaseSchema):
    """Statistics for a single event."""

    event_id: UUID
    event_name: str
    total_registered: int
    total_attended: int
    attendance_rate: float
    capacity: int | None
    fill_rate: float | None  # registered / capacity * 100

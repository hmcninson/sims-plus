"""
SIMS Plus - Preschool Portfolio Schemas

Pydantic schemas for learning stories and student timeline.
"""

from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID as StdUUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.preschool.core import BaseSchema
from app.schemas.preschool.observation import AttachmentSchema

# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Learning Story Schemas
# =========================


class LearningStoryCreate(BaseSchema):
    """Schema for creating a learning story."""

    student_id: UUID
    term_id: UUID | None = None
    title: Annotated[str, Field(min_length=3, max_length=255)]
    narrative: Annotated[str, Field(min_length=10, max_length=10000)]
    learning_area_ids: list[UUID] | None = None
    skill_ids: list[UUID] | None = None
    observation_ids: list[UUID] | None = None
    attachments: list[AttachmentSchema] | None = None
    is_shared_with_parents: bool = True


class LearningStoryUpdate(BaseModel):
    """Schema for updating a learning story."""

    title: Annotated[str | None, Field(min_length=3, max_length=255)] = None
    narrative: Annotated[str | None, Field(min_length=10, max_length=10000)] = None
    learning_area_ids: list[UUID] | None = None
    skill_ids: list[UUID] | None = None
    observation_ids: list[UUID] | None = None
    attachments: list[AttachmentSchema] | None = None
    is_shared_with_parents: bool | None = None


class LearningStoryResponse(BaseSchema):
    """Schema for learning story response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    student_id: UUID
    term_id: UUID | None = None
    title: str
    narrative: str
    learning_area_ids: list[UUID] | None = None
    skill_ids: list[UUID] | None = None
    observation_ids: list[UUID] | None = None
    attachments: list[AttachmentSchema] | None = None
    is_shared_with_parents: bool
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


# =========================
# Timeline Schemas
# =========================


class TimelineEntry(BaseSchema):
    """Unified timeline entry aggregated from multiple tables."""

    date: date
    type: str  # "assessment", "observation", "incident", "learning_story"
    title: str
    summary: str | None = None
    details: dict  # Type-specific payload
    id: UUID

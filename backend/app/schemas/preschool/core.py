"""
SIMS Plus - Preschool Core Schemas

Pydantic schemas for learning areas, developmental skills, rating scales,
and student skill assessments.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID as StdUUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def convert_uuid(value: Any) -> StdUUID | None:
    """Convert any UUID-like object to standard UUID."""
    if value is None:
        return None
    # Check exact type, not isinstance, because asyncpg.UUID is a subclass of uuid.UUID
    if type(value) is StdUUID:
        return value
    if hasattr(value, "hex"):
        # asyncpg UUID or other UUID-like object - convert via hex
        return StdUUID(value.hex)
    if isinstance(value, str):
        return StdUUID(value)
    return value


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Learning Area Schemas
# =========================


class LearningAreaBase(BaseSchema):
    """Base schema for learning areas."""

    name: Annotated[str, Field(min_length=1, max_length=100)]
    code: Annotated[str, Field(min_length=1, max_length=20)]
    description: str | None = None
    icon: Annotated[str | None, Field(max_length=50)] = None
    color: Annotated[str | None, Field(max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")] = None
    display_order: int = 0
    is_active: bool = True


class LearningAreaCreate(LearningAreaBase):
    """Schema for creating a learning area."""

    pass


class LearningAreaUpdate(BaseModel):
    """Schema for updating a learning area."""

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    code: Annotated[str | None, Field(min_length=1, max_length=20)] = None
    description: str | None = None
    icon: Annotated[str | None, Field(max_length=50)] = None
    color: Annotated[str | None, Field(max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")] = None
    display_order: int | None = None
    is_active: bool | None = None


class LearningAreaResponse(LearningAreaBase):
    """Schema for learning area response."""

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class LearningAreaWithSkills(LearningAreaResponse):
    """Learning area with its skills."""

    skills: list["DevelopmentalSkillResponse"] = []


# =========================
# Developmental Skill Schemas
# =========================


class DevelopmentalSkillBase(BaseSchema):
    """Base schema for developmental skills."""

    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    age_range_months_min: int | None = None
    age_range_months_max: int | None = None
    display_order: int = 0
    is_active: bool = True
    applicable_levels: list[str] | None = None


class DevelopmentalSkillCreate(DevelopmentalSkillBase):
    """Schema for creating a developmental skill."""

    learning_area_id: UUID


class DevelopmentalSkillUpdate(BaseModel):
    """Schema for updating a developmental skill."""

    name: Annotated[str | None, Field(min_length=1, max_length=255)] = None
    description: str | None = None
    age_range_months_min: int | None = None
    age_range_months_max: int | None = None
    display_order: int | None = None
    is_active: bool | None = None
    applicable_levels: list[str] | None = None


class DevelopmentalSkillResponse(DevelopmentalSkillBase):
    """Schema for developmental skill response."""

    id: UUID
    tenant_id: UUID
    learning_area_id: UUID
    created_at: datetime
    updated_at: datetime



class DevelopmentalSkillBulkCreate(BaseModel):
    """Schema for bulk creating skills."""

    learning_area_id: UUID
    skills: list[DevelopmentalSkillBase]


# =========================
# Rating Scale Schemas
# =========================


class PreschoolRatingBase(BaseSchema):
    """Base schema for preschool ratings."""

    name: Annotated[str, Field(min_length=1, max_length=50)]
    short_code: Annotated[str, Field(min_length=1, max_length=5)]
    description: str | None = None
    numeric_value: int
    color: Annotated[str | None, Field(max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")] = None
    icon: Annotated[str | None, Field(max_length=50)] = None
    display_order: int = 0


class PreschoolRatingCreate(PreschoolRatingBase):
    """Schema for creating a rating."""

    pass


class PreschoolRatingResponse(PreschoolRatingBase):
    """Schema for rating response."""

    id: UUID
    tenant_id: UUID
    scale_id: UUID
    created_at: datetime
    updated_at: datetime



class PreschoolRatingScaleBase(BaseSchema):
    """Base schema for rating scales."""

    name: Annotated[str, Field(min_length=1, max_length=100)]
    description: str | None = None
    is_default: bool = False


class PreschoolRatingScaleCreate(PreschoolRatingScaleBase):
    """Schema for creating a rating scale with ratings."""

    ratings: list[PreschoolRatingCreate] = []


class PreschoolRatingScaleUpdate(BaseModel):
    """Schema for updating a rating scale."""

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    description: str | None = None
    is_default: bool | None = None


class PreschoolRatingScaleResponse(PreschoolRatingScaleBase):
    """Schema for rating scale response."""

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime



class PreschoolRatingScaleWithRatings(PreschoolRatingScaleResponse):
    """Rating scale with its ratings."""

    ratings: list[PreschoolRatingResponse] = []


# =========================
# Student Skill Assessment Schemas
# =========================


class StudentSkillAssessmentBase(BaseSchema):
    """Base schema for skill assessments."""

    rating_id: UUID | None = None
    observation_notes: str | None = None
    evidence_url: Annotated[str | None, Field(max_length=500)] = None


class StudentSkillAssessmentCreate(StudentSkillAssessmentBase):
    """Schema for creating/updating a skill assessment."""

    student_id: UUID
    skill_id: UUID
    academic_year_id: UUID
    term_id: UUID


class StudentSkillAssessmentBulk(BaseModel):
    """Schema for bulk assessment update."""

    student_id: UUID
    academic_year_id: UUID
    term_id: UUID
    assessments: list["SkillAssessmentEntry"]


class SkillAssessmentEntry(BaseModel):
    """Single skill assessment entry for bulk operations."""

    skill_id: UUID
    rating_id: UUID | None = None
    observation_notes: str | None = None


class BulkAssessmentResult(BaseModel):
    """Result of bulk assessment operation."""

    created: int
    updated: int


class StudentSkillAssessmentResponse(StudentSkillAssessmentBase):
    """Schema for skill assessment response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    skill_id: UUID
    academic_year_id: UUID
    term_id: UUID
    assessed_by: UUID | None = None
    assessed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Nested objects
    rating: PreschoolRatingResponse | None = None



class StudentSkillAssessmentWithDetails(StudentSkillAssessmentResponse):
    """Assessment with skill and student details."""

    skill: DevelopmentalSkillResponse | None = None


# =========================
# Seed Data Schemas
# =========================


class SeedLearningAreasRequest(BaseModel):
    """Request to seed default learning areas for a tenant."""

    include_skills: bool = True


class SeedRatingScaleRequest(BaseModel):
    """Request to seed default rating scale for a tenant."""

    set_as_default: bool = True


# Update forward references
LearningAreaWithSkills.model_rebuild()
StudentSkillAssessmentBulk.model_rebuild()

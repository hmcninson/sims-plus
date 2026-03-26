"""
SIMS Plus - Preschool Incident Schemas

Pydantic schemas for preschool incidents and allergy/dietary management.
"""

from datetime import date, datetime, time
from typing import Annotated, Any
from uuid import UUID as StdUUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.preschool.core import BaseSchema, convert_uuid

# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Attachment Schema (HTTPS-only)
# =========================


class AttachmentSchema(BaseSchema):
    """Typed attachment entry for observations, incidents, and learning stories."""

    url: Annotated[str, Field(max_length=500)]
    type: Annotated[str, Field(pattern=r"^(image|video|document)$")]
    thumbnail: Annotated[str | None, Field(max_length=500)] = None
    filename: Annotated[str | None, Field(max_length=255)] = None

    @field_validator("url", "thumbnail", mode="before")
    @classmethod
    def validate_url_scheme(cls, v: str | None) -> str | None:
        """Only allow HTTPS URLs to prevent SSRF attacks."""
        if v is None:
            return None
        if not v.startswith("https://"):
            raise ValueError("URL must use HTTPS")
        return v


# =========================
# Allergy / Dietary Schemas
# =========================


class AllergyEntry(BaseSchema):
    """Single allergy entry within dietary_requirements."""

    allergen: Annotated[str, Field(min_length=1, max_length=100)]
    severity: Annotated[str, Field(pattern=r"^(mild|moderate|severe)$")]
    reaction: Annotated[str | None, Field(max_length=500)] = None
    medication: Annotated[str | None, Field(max_length=500)] = None


class DietaryRequirements(BaseSchema):
    """Structured dietary requirements for a student."""

    allergies: list[AllergyEntry] = []
    dietary_restrictions: list[Annotated[str, Field(max_length=50)]] = []
    notes: Annotated[str | None, Field(max_length=2000)] = None


class DietaryRequirementsUpdate(BaseSchema):
    """Update schema -- replaces entire dietary_requirements JSONB."""

    dietary_requirements: DietaryRequirements | None = None


class AllergyAlertResponse(BaseSchema):
    """Student allergy summary for teacher alerts."""

    student_id: UUID
    student_name: str
    allergies: list[AllergyEntry]
    dietary_restrictions: list[str]
    notes: str | None = None


# =========================
# Preschool Incident Schemas
# =========================


class PreschoolIncidentCreate(BaseSchema):
    """Create a new preschool incident report."""

    student_id: UUID
    incident_type: Annotated[
        str, Field(pattern=r"^(accident|illness|behavioral|allergic_reaction|other)$")
    ]
    severity: Annotated[str, Field(pattern=r"^(minor|moderate|serious)$")]
    incident_date: date
    incident_time: time | None = None
    location: Annotated[str | None, Field(max_length=255)] = None
    description: Annotated[str, Field(min_length=10, max_length=5000)]
    action_taken: Annotated[str | None, Field(max_length=5000)] = None
    first_aid_given: bool = False
    medical_attention_required: bool = False
    witnesses: list[Annotated[str, Field(max_length=200)]] | None = None
    attachments: list[AttachmentSchema] | None = None

    @field_validator("incident_date")
    @classmethod
    def incident_date_not_future(cls, v: date) -> date:
        """Incidents cannot be reported for future dates."""
        if v > date.today():
            raise ValueError("Incident date cannot be in the future")
        return v


class PreschoolIncidentUpdate(BaseSchema):
    """Update an existing incident. All fields optional.

    PROTECTED_FIELDS (id, tenant_id, school_id, student_id, status,
    reported_by, parent_notified_at, parent_notified_by, resolved_at,
    resolved_by, created_at, deleted_at) are enforced in the service layer.
    """

    incident_type: Annotated[
        str | None,
        Field(pattern=r"^(accident|illness|behavioral|allergic_reaction|other)$"),
    ] = None
    severity: Annotated[
        str | None, Field(pattern=r"^(minor|moderate|serious)$")
    ] = None
    location: Annotated[str | None, Field(max_length=255)] = None
    description: Annotated[
        str | None, Field(min_length=10, max_length=5000)
    ] = None
    action_taken: Annotated[str | None, Field(max_length=5000)] = None
    first_aid_given: bool | None = None
    medical_attention_required: bool | None = None
    witnesses: list[Annotated[str, Field(max_length=200)]] | None = None
    attachments: list[AttachmentSchema] | None = None
    follow_up_notes: Annotated[str | None, Field(max_length=5000)] = None


class PreschoolIncidentResponse(BaseSchema):
    """Incident response with all fields."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    incident_type: str
    severity: str
    status: str
    incident_date: date
    incident_time: time | None = None
    location: str | None = None
    description: str
    action_taken: str | None = None
    first_aid_given: bool
    medical_attention_required: bool
    parent_notified_at: datetime | None = None
    parent_notified_by: UUID | None = None
    witnesses: list[str] | None = None
    attachments: list[AttachmentSchema] | None = None
    follow_up_notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    reported_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids(cls, data: Any) -> Any:
        """Convert asyncpg UUIDs to standard UUIDs."""
        if not isinstance(data, dict):
            # ORM model -- convert known UUID fields
            for field_name in [
                "id", "tenant_id", "student_id", "parent_notified_by",
                "resolved_by", "reported_by",
            ]:
                val = getattr(data, field_name, None)
                if val is not None:
                    setattr(data, field_name, convert_uuid(val))
        return data


class IncidentResolveRequest(BaseSchema):
    """Request body for resolving an incident."""

    follow_up_notes: Annotated[str | None, Field(max_length=5000)] = None

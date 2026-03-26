"""
SIMS Plus - Preschool Pickup Schemas

Pydantic schemas for authorized pickup persons and pickup logs.
"""

from datetime import date, datetime, time
from typing import Annotated, Any
from uuid import UUID as StdUUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.preschool.core import BaseSchema, convert_uuid

# Use standard UUID with alias for clarity
UUID = StdUUID


# =========================
# Authorized Pickup Schemas
# =========================


class AuthorizedPickupCreate(BaseSchema):
    """Add a new authorized pickup person for a student."""

    full_name: Annotated[str, Field(min_length=2, max_length=200)]
    phone: Annotated[str, Field(min_length=10, max_length=20)]
    relationship_to_student: Annotated[str | None, Field(max_length=100)] = None
    photo_url: Annotated[str | None, Field(max_length=500)] = None
    id_document_url: Annotated[str | None, Field(max_length=500)] = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @field_validator("photo_url", "id_document_url", mode="before")
    @classmethod
    def validate_s3_url(cls, v: str | None) -> str | None:
        """Only allow HTTPS URLs to prevent SSRF. Must be S3 presigned URLs."""
        if v is None:
            return None
        if not v.startswith("https://"):
            raise ValueError("URL must use HTTPS (S3 presigned URL)")
        return v


class AuthorizedPickupUpdate(BaseSchema):
    """Update authorized pickup person. All fields optional."""

    full_name: Annotated[str | None, Field(min_length=2, max_length=200)] = None
    phone: Annotated[str | None, Field(min_length=10, max_length=20)] = None
    relationship_to_student: Annotated[str | None, Field(max_length=100)] = None
    photo_url: Annotated[str | None, Field(max_length=500)] = None
    id_document_url: Annotated[str | None, Field(max_length=500)] = None
    is_active: bool | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @field_validator("photo_url", "id_document_url", mode="before")
    @classmethod
    def validate_s3_url(cls, v: str | None) -> str | None:
        """Only allow HTTPS URLs to prevent SSRF. Must be S3 presigned URLs."""
        if v is None:
            return None
        if not v.startswith("https://"):
            raise ValueError("URL must use HTTPS (S3 presigned URL)")
        return v


class AuthorizedPickupResponse(BaseSchema):
    """Authorized pickup person response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    full_name: str
    phone: str
    relationship_to_student: str | None = None
    photo_url: str | None = None
    id_document_url: str | None = None
    is_active: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids(cls, data: Any) -> Any:
        """Convert asyncpg UUIDs to standard UUIDs."""
        if not isinstance(data, dict):
            for field_name in ["id", "tenant_id", "student_id"]:
                val = getattr(data, field_name, None)
                if val is not None:
                    setattr(data, field_name, convert_uuid(val))
        return data


# =========================
# Pickup Log Schemas
# =========================


class PickupLogCreate(BaseSchema):
    """Record a student pickup event."""

    student_id: UUID
    pickup_time: time
    picked_up_by_type: Annotated[str, Field(pattern=r"^(guardian|authorized_person)$")]
    picked_up_by_guardian_id: UUID | None = None
    picked_up_by_authorized_id: UUID | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @model_validator(mode="after")
    def validate_pickup_person(self) -> "PickupLogCreate":
        """Ensure exactly one pickup person ID is provided based on type."""
        if self.picked_up_by_type == "guardian":
            if not self.picked_up_by_guardian_id:
                raise ValueError(
                    "picked_up_by_guardian_id is required when type is 'guardian'"
                )
            if self.picked_up_by_authorized_id:
                raise ValueError(
                    "picked_up_by_authorized_id must be null when type is 'guardian'"
                )
        elif self.picked_up_by_type == "authorized_person":
            if not self.picked_up_by_authorized_id:
                raise ValueError(
                    "picked_up_by_authorized_id is required when type is 'authorized_person'"
                )
            if self.picked_up_by_guardian_id:
                raise ValueError(
                    "picked_up_by_guardian_id must be null when type is 'authorized_person'"
                )
        return self


class PickupLogResponse(BaseSchema):
    """Pickup log entry response."""

    id: UUID
    tenant_id: UUID
    student_id: UUID
    pickup_date: date
    pickup_time: time
    picked_up_by_type: str
    picked_up_by_guardian_id: UUID | None = None
    picked_up_by_authorized_id: UUID | None = None
    verified_by: UUID | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids(cls, data: Any) -> Any:
        """Convert asyncpg UUIDs to standard UUIDs."""
        if not isinstance(data, dict):
            for field_name in [
                "id", "tenant_id", "student_id", "picked_up_by_guardian_id",
                "picked_up_by_authorized_id", "verified_by",
            ]:
                val = getattr(data, field_name, None)
                if val is not None:
                    setattr(data, field_name, convert_uuid(val))
        return data

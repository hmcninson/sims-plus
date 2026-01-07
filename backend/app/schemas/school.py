"""
SIMS Plus - School Schemas

Pydantic schemas for school profile management.
"""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# School Profile
# =========================

class SchoolProfileResponse(BaseSchema):
    """School profile response."""

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    code: Optional[str] = None
    school_type: str

    # Contact Information
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None

    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    gps_address: Optional[str] = None

    # Branding
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    motto: Optional[str] = None
    description: Optional[str] = None
    year_established: Optional[int] = None

    # Features
    uses_boarding: bool = False
    uses_transport: bool = False

    # Student ID Settings
    student_id_prefix: str = "STU"

    # Status
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class SchoolProfileUpdate(BaseSchema):
    """Update school profile request."""

    # Basic Info (name cannot be changed easily - requires admin)
    motto: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    year_established: Optional[int] = Field(None, ge=1800, le=2100)

    # Contact Information
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=255)

    # Address
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    gps_address: Optional[str] = Field(None, max_length=50)

    # Branding
    logo_url: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, max_length=7)

    # Features
    uses_boarding: Optional[bool] = None
    uses_transport: Optional[bool] = None

    # Student ID Settings
    student_id_prefix: Optional[str] = Field(None, min_length=1, max_length=10)

    @field_validator("student_id_prefix")
    @classmethod
    def validate_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Only allow alphanumeric characters
        if not re.match(r"^[A-Za-z0-9]+$", v):
            raise ValueError("Prefix must contain only letters and numbers")
        return v.upper()

    @field_validator("primary_color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Invalid hex color format (use #RRGGBB)")
        return v.upper()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        phone = re.sub(r"\s+", "", v)
        # Allow Ghana format or international
        if not re.match(r"^(\+233|0)[0-9]{9}$|^\+[0-9]{10,15}$", phone):
            raise ValueError("Invalid phone number format")
        return phone

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class SchoolBrandingUpdate(BaseSchema):
    """Update school branding only."""

    logo_url: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, max_length=7)

    @field_validator("primary_color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Invalid hex color format (use #RRGGBB)")
        return v.upper()

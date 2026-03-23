"""
SIMS Plus - School Schemas

Pydantic schemas for school profile management.
"""

import re
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =========================
# Preschool Settings
# =========================

class PreschoolSettings(BaseModel):
    """Preschool configuration settings."""

    enabled: bool = False
    daily_logs_enabled: bool = True
    meal_tracking: bool = True
    nap_tracking: bool = True
    diaper_tracking: bool = True
    potty_training_tracking: bool = True
    observation_photos_enabled: bool = True
    parent_daily_updates: bool = True
    default_rating_scale_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("default_rating_scale_id", mode="before")
    @classmethod
    def parse_uuid(cls, v: Any) -> Optional[UUID]:
        """Convert string UUID to UUID object."""
        if v is None or v == "":
            return None
        if isinstance(v, UUID):
            return v
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                return None
        return None


class PreschoolSettingsUpdate(BaseModel):
    """Update preschool settings request."""

    enabled: Optional[bool] = None
    daily_logs_enabled: Optional[bool] = None
    meal_tracking: Optional[bool] = None
    nap_tracking: Optional[bool] = None
    diaper_tracking: Optional[bool] = None
    potty_training_tracking: Optional[bool] = None
    observation_photos_enabled: Optional[bool] = None
    parent_daily_updates: Optional[bool] = None
    default_rating_scale_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


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

    # School Classification
    category: Optional[str] = None
    boarding_type: Optional[str] = None

    # ID Prefix Settings
    student_id_prefix: str = "STU"
    staff_id_prefix: str = "STF"

    # Preschool Settings
    preschool_settings: Optional[PreschoolSettings] = None

    # GES Registration
    ges_registration_number: Optional[str] = None

    # Setup Wizard
    setup_completed: bool = False
    setup_wizard_step: int = 0

    # Calendar
    calendar_type: str = "term"

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

    # School Classification
    category: Optional[str] = None
    boarding_type: Optional[str] = None

    # ID Prefix Settings
    student_id_prefix: Optional[str] = Field(None, min_length=1, max_length=10)
    staff_id_prefix: Optional[str] = Field(None, min_length=1, max_length=10)

    # School Type (changeable by school admin)
    school_type: Optional[str] = Field(None, max_length=30)

    # GES Registration
    ges_registration_number: Optional[str] = Field(None, max_length=100)

    # Calendar
    calendar_type: Optional[str] = Field(None, max_length=20)

    # Preschool Settings
    preschool_settings: Optional[PreschoolSettingsUpdate] = None

    @field_validator("school_type")
    @classmethod
    def validate_school_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = [
            "preschool", "primary", "preschool_primary", "jhs", "shs",
            "basic", "basic_preschool", "basic_shs", "international", "technical",
        ]
        if v not in valid:
            raise ValueError(f"Invalid school type. Must be one of: {', '.join(valid)}")
        return v

    @field_validator("calendar_type")
    @classmethod
    def validate_calendar_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = ["term", "semester", "quarter"]
        if v not in valid:
            raise ValueError(f"Invalid calendar type. Must be one of: {', '.join(valid)}")
        return v

    @field_validator("student_id_prefix", "staff_id_prefix")
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

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = ["public", "private", "international", "faith_based"]
        if v not in valid:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(valid)}")
        return v

    @field_validator("boarding_type")
    @classmethod
    def validate_boarding_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid = ["day_only", "boarding_only", "mixed"]
        if v not in valid:
            raise ValueError(f"Invalid boarding type. Must be one of: {', '.join(valid)}")
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


class WizardStepUpdate(BaseSchema):
    """Update the setup wizard progress for the current school."""

    step: int = Field(..., ge=0, le=7, description="The wizard step just completed (0-7)")
    completed: Optional[bool] = Field(
        None,
        description="If true, marks the entire setup wizard as completed",
    )


class WizardStepResponse(BaseSchema):
    """Response after updating wizard step."""

    setup_wizard_step: int
    setup_completed: bool

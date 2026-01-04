"""
SIMS Plus - Onboarding Schemas

Pydantic schemas for school registration and onboarding.
"""

import re
from datetime import date, datetime
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
# School Registration
# =========================

class SchoolRegistrationRequest(BaseSchema):
    """
    School registration request.

    Creates a new tenant, school, and admin user.
    """

    # School Information
    school_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Official school name",
    )
    subdomain: str = Field(
        ...,
        min_length=4,
        max_length=63,
        description="Unique subdomain for the school",
    )
    school_type: str = Field(
        ...,
        description="Type of school (primary, jhs, shs, basic, international, technical)",
    )

    # Administrator Information
    admin_email: EmailStr = Field(
        ...,
        description="Admin email address",
    )
    admin_first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Admin first name",
    )
    admin_last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Admin last name",
    )
    admin_phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Admin phone number",
    )
    admin_password: str = Field(
        ...,
        min_length=8,
        description="Admin password",
    )

    # Optional
    plan: str = Field(
        default="trial",
        description="Subscription plan (trial, starter, professional, enterprise)",
    )

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        """Validate subdomain format."""
        subdomain = v.lower()

        # Only lowercase letters, numbers, hyphens
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$", subdomain):
            raise ValueError(
                "Subdomain can only contain lowercase letters, numbers, and hyphens"
            )

        if subdomain.startswith("-") or subdomain.endswith("-"):
            raise ValueError("Subdomain cannot start or end with a hyphen")

        return subdomain

    @field_validator("school_type")
    @classmethod
    def validate_school_type(cls, v: str) -> str:
        """Validate school type."""
        valid_types = [
            "preschool",          # Preschool only
            "primary",            # Primary School
            "preschool_primary",  # Preschool + Primary
            "jhs",                # Junior High School
            "shs",                # Senior High School
            "basic",              # Primary + JHS
            "basic_preschool",    # Preschool to JHS
            "basic_shs",          # Preschool to SHS (full K-12)
            "international",
            "technical",
        ]
        if v.lower() not in valid_types:
            raise ValueError(f"Invalid school type. Must be one of: {', '.join(valid_types)}")
        return v.lower()

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        """Validate subscription plan."""
        valid_plans = ["trial", "starter", "professional", "enterprise"]
        if v.lower() not in valid_plans:
            raise ValueError(f"Invalid plan. Must be one of: {', '.join(valid_plans)}")
        return v.lower()

    @field_validator("admin_phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        phone = re.sub(r"\s+", "", v)
        if not re.match(r"^(\+233|0)[0-9]{9}$", phone):
            raise ValueError("Invalid Ghana phone number format")
        return phone

    @field_validator("admin_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength (same rules as auth schema)."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class SchoolRegistrationResponse(BaseSchema):
    """School registration response."""

    success: bool = True
    message: str

    # Created entities
    tenant_id: UUID
    school_id: UUID
    admin_user_id: UUID

    # Access info
    subdomain: str
    portal_url: str
    admin_email: str

    # Trial info
    trial_ends_at: Optional[datetime] = None


# =========================
# Onboarding Setup Wizard
# =========================

class SetupWizardProgress(BaseSchema):
    """Setup wizard progress tracking."""

    step: int = Field(ge=1, le=5)
    completed_steps: list[str] = []
    current_step: str
    next_step: Optional[str] = None


class SchoolProfileUpdate(BaseSchema):
    """Update school profile during onboarding."""

    # Contact
    email: Optional[EmailStr] = None
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

    # Features
    uses_boarding: bool = False
    uses_transport: bool = False

    @field_validator("primary_color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Invalid hex color format (use #RRGGBB)")
        return v.upper()


class AcademicYearSetup(BaseSchema):
    """Academic year configuration."""

    name: str = Field(..., description="e.g., '2025/2026 Academic Year'")
    start_date: date
    end_date: date
    is_current: bool = True


class TermSetup(BaseSchema):
    """Term/semester configuration."""

    name: str = Field(..., description="e.g., 'First Term'")
    start_date: date
    end_date: date
    term_number: int = Field(ge=1, le=4)


class ClassSetup(BaseSchema):
    """Class configuration."""

    name: str = Field(..., description="e.g., 'Class 1' or 'JHS 1'")
    level: int = Field(ge=1, le=15, description="Grade level")
    sections: list[str] = Field(
        default=["A"],
        description="Section names (e.g., ['A', 'B', 'C'])",
    )


class OnboardingCompleteRequest(BaseSchema):
    """Mark onboarding as complete."""

    skip_remaining: bool = False


class OnboardingStatus(BaseSchema):
    """Onboarding status response."""

    is_complete: bool
    current_step: int
    total_steps: int = 5
    completed_steps: list[str]
    school_profile_complete: bool
    academic_year_configured: bool
    terms_configured: bool
    classes_configured: bool
    first_user_added: bool

"""
SIMS Plus - Tenant Schemas

Pydantic models for tenant-related API requests and responses.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubdomainCheckRequest(BaseModel):
    """Request to check subdomain availability."""

    subdomain: str = Field(
        ...,
        min_length=4,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$",
        description="Subdomain to check (lowercase letters, numbers, hyphens)",
    )


class SubdomainCheckResponse(BaseModel):
    """Response for subdomain availability check."""

    subdomain: str
    available: bool
    reason: str | None = None


class TenantBranding(BaseModel):
    """Tenant branding information."""

    logo_url: str | None = None
    primary_color: str | None = "#1B4F72"


class TenantPublic(BaseModel):
    """Public tenant information (no sensitive data)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    subdomain: str
    tenant_type: str
    is_active: bool
    branding: TenantBranding | None = None


class TenantResponse(BaseModel):
    """Full tenant response for authenticated users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    subdomain: str
    slug: str
    tenant_type: str
    subscription_tier: str
    subscription_start: date | None = None
    subscription_end: date | None = None
    max_students: int
    email: str | None = None
    phone: str | None = None
    is_active: bool
    logo_url: str | None = None
    primary_color: str | None = None
    created_at: datetime


class TenantValidationResponse(BaseModel):
    """Response for tenant validation by subdomain."""

    valid: bool
    tenant: TenantPublic | None = None
    error: str | None = None

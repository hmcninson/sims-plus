"""
Pydantic schemas for platform admin endpoints.

These schemas define the request/response shapes for the platform admin API,
which operates outside normal tenant-scoped context.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Auth schemas
# ============================================================


class PlatformLoginRequest(BaseModel):
    """Platform admin login credentials."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class PlatformLoginResponse(BaseModel):
    """Successful platform admin login (after MFA verification)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "PlatformUserResponse"


class PlatformMFARequiredResponse(BaseModel):
    """Returned when platform admin has MFA enabled — needs TOTP verification."""

    mfa_required: bool = True
    mfa_pending_token: str


class PlatformMFASetupRequiredResponse(BaseModel):
    """Returned on first login when MFA not yet configured."""

    mfa_setup_required: bool = True
    access_token: str  # Temporary token to access MFA setup only
    message: str = "MFA setup is required for platform admin accounts"


class PlatformUserResponse(BaseModel):
    """Platform admin user profile."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str = "platform_admin"
    mfa_enabled: bool


class PlatformRefreshRequest(BaseModel):
    """Refresh token request for platform admin."""

    refresh_token: str = Field(..., min_length=1)


class MFAVerifyRequest(BaseModel):
    """Request body for MFA verification during login."""

    mfa_pending_token: str = Field(..., min_length=1)
    totp_code: str = Field(..., min_length=6, max_length=8)


class MFASetupRequest(BaseModel):
    """Request body for completing MFA setup on first login."""

    setup_token: str = Field(..., min_length=1)
    totp_code: str = Field(..., min_length=6, max_length=6)
    mfa_secret: str = Field(..., min_length=16)


# ============================================================
# Tenant management schemas
# ============================================================


class TenantSummary(BaseModel):
    """Tenant summary for list view."""

    id: UUID
    name: str
    subdomain: str
    tenant_type: str | None = None
    status: str | None = None
    subscription_tier: str | None = None
    is_active: bool
    max_students: int
    max_staff: int
    created_at: datetime
    # Computed from superuser engine cross-tenant counts
    student_count: int = 0
    staff_count: int = 0
    school_count: int = 0


class TenantListResponse(BaseModel):
    """Paginated tenant list."""

    items: list[TenantSummary]
    total: int
    page: int
    page_size: int


class TenantDetail(TenantSummary):
    """Full tenant details including subscription and branding info."""

    email: str | None = None
    phone: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    features: dict | None = None
    subscription_start: datetime | None = None
    subscription_end: datetime | None = None
    trial_ends_at: datetime | None = None
    updated_at: datetime


class TenantUpdateRequest(BaseModel):
    """Update tenant details (platform admin).

    SECURITY: `status` is deliberately excluded. Status changes must go through
    the dedicated /suspend and /activate endpoints which have proper validation,
    state machine enforcement, and specific audit logging.
    """

    name: str | None = None
    subscription_tier: str | None = None
    max_students: int | None = Field(None, ge=0)
    max_staff: int | None = Field(None, ge=0)
    features: dict | None = None


class TenantSuspendRequest(BaseModel):
    """Suspend a tenant — requires a reason for the audit log."""

    reason: str = Field(..., min_length=1, max_length=500)


# ============================================================
# Impersonation schemas
# ============================================================


class ImpersonationResponse(BaseModel):
    """Short-lived token scoped to the target tenant."""

    access_token: str
    tenant_id: UUID
    tenant_name: str
    tenant_subdomain: str
    expires_in: int  # Seconds


# ============================================================
# Analytics schemas
# ============================================================


class PlatformAnalytics(BaseModel):
    """Platform-wide analytics."""

    total_tenants: int
    active_tenants: int
    trial_tenants: int
    suspended_tenants: int
    total_students: int
    total_staff: int
    total_schools: int
    tenants_by_plan: dict[str, int]
    recent_registrations: list[TenantSummary]


# ============================================================
# Audit log schemas
# ============================================================


class PlatformAuditEntry(BaseModel):
    """Single audit log entry."""

    id: UUID
    actor_user_id: UUID
    actor_email: str | None = None
    action: str
    target_tenant_id: UUID | None = None
    target_tenant_name: str | None = None
    target_entity_type: str | None = None
    target_entity_id: UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime


class PlatformAuditLogResponse(BaseModel):
    """Paginated audit log."""

    items: list[PlatformAuditEntry]
    total: int
    page: int
    page_size: int

"""
Platform admin API endpoints.

All protected endpoints require PlatformAdmin dependency (validates is_platform
JWT claim). These endpoints operate OUTSIDE normal tenant-scoped context.

Rate limits:
- Login/MFA: 5/min (auth tier)
- Impersonation: 10/min (bulk tier)
- Tenant CRUD: 100/min (default tier)
- Analytics: 10/min (bulk tier)

IMPORTANT: Do NOT use `from __future__ import annotations` — breaks 204 responses.
"""

from typing import Annotated
from uuid import UUID

import pyotp
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt as jose_jwt
from sqlalchemy import select

from app.api.deps import (
    PlatformAdmin,
    UnscopedDatabaseSession,
    oauth2_scheme,
)
from app.config import settings
from app.schemas.platform import (
    ImpersonationResponse,
    MFASetupRequest,
    MFAVerifyRequest,
    PlatformAuditLogResponse,
    PlatformLoginRequest,
    PlatformLoginResponse,
    PlatformRefreshRequest,
    PlatformUserResponse,
    TenantDetail,
    TenantListResponse,
    TenantSuspendRequest,
    TenantUpdateRequest,
)
from app.services.platform import PlatformService, PlatformServiceError
from app.services.token_blacklist import get_token_blacklist_service

router = APIRouter(prefix="/platform", tags=["Platform Admin"])

logger = structlog.get_logger()


# ============================================================
# Auth endpoints (no PlatformAdmin dependency — login is public)
# ============================================================


@router.post("/login", summary="Platform admin login")
async def platform_login(
    data: PlatformLoginRequest,
    request: Request,
    db: UnscopedDatabaseSession,
):
    """
    Authenticate a platform admin.

    Returns one of:
    - PlatformLoginResponse (full tokens) — after MFA verification (via /mfa/verify)
    - PlatformMFARequiredResponse — if MFA enabled, needs verification
    - PlatformMFASetupRequiredResponse — if first login, MFA not configured
    """
    service = PlatformService(db)
    try:
        result = await service.authenticate(
            email=data.email,
            password=data.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except PlatformServiceError as e:
        if e.code == "account_locked":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again later.",
            )
        # SECURITY: Always return the same generic message for all auth failures
        # (invalid credentials, suspended, deactivated, nonexistent) to prevent
        # account enumeration. The specific reason is logged server-side.
        logger.warning(
            "platform_login_failed",
            error_code=e.code,
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # MFA required (already set up)
    if result.get("mfa_required"):
        # Extract user_id from the mfa_pending_token for audit logging (BUG-3 fix)
        from jose import jwt as jose_jwt

        try:
            pending_payload = jose_jwt.decode(
                result["mfa_pending_token"],
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            audit_user_id = UUID(
                pending_payload.get("sub", "00000000-0000-0000-0000-000000000000")
            )
        except Exception:
            audit_user_id = UUID("00000000-0000-0000-0000-000000000000")

        await service.log_action(
            actor_user_id=audit_user_id,
            action="platform_login_mfa_pending",
            ip_address=request.client.host if request.client else None,
        )
        return JSONResponse(
            content={
                "mfa_required": True,
                "mfa_pending_token": result["mfa_pending_token"],
            }
        )

    # MFA setup required (first login)
    if result.get("mfa_setup_required"):
        return JSONResponse(
            content={
                "mfa_setup_required": True,
                "access_token": result["access_token"],
                "message": result["message"],
            }
        )

    # authenticate() ALWAYS returns mfa_required or mfa_setup_required (BUG-1).
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected auth response",
    )


@router.post("/mfa/verify", summary="Verify MFA code during login")
async def platform_mfa_verify(
    data: MFAVerifyRequest,
    request: Request,
    db: UnscopedDatabaseSession,
):
    """
    Called after /platform/login returns mfa_required=True.
    Validates the mfa_pending_token and TOTP code, issues full tokens.
    """
    service = PlatformService(db)
    try:
        result = await service.verify_mfa(data.mfa_pending_token, data.totp_code)
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message
        )

    user = result["user"]
    tokens = result["tokens"]

    await service.log_action(
        actor_user_id=user.id,
        action="platform_login",
        details={"method": "mfa_verified"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return PlatformLoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=PlatformUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            mfa_enabled=user.mfa_enabled,
        ),
    )


@router.post("/mfa/setup", summary="Complete MFA setup on first login")
async def platform_mfa_setup(
    data: MFASetupRequest,
    request: Request,
    db: UnscopedDatabaseSession,
):
    """
    Called after /platform/login returns mfa_setup_required=True.
    The frontend generates a TOTP secret (via /mfa/generate), shows the QR code,
    and the user enters the code here to complete setup.
    """
    service = PlatformService(db)
    try:
        result = await service.complete_mfa_setup(
            data.setup_token, data.totp_code, data.mfa_secret
        )
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message
        )

    user = result["user"]
    tokens = result["tokens"]

    await service.log_action(
        actor_user_id=user.id,
        action="platform_login",
        details={"method": "mfa_setup_completed"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return PlatformLoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=PlatformUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            mfa_enabled=user.mfa_enabled,
        ),
    )


@router.get("/mfa/generate", summary="Generate MFA secret for setup")
async def platform_mfa_generate(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: UnscopedDatabaseSession,
):
    """
    Returns a TOTP secret and provisioning URI for QR code generation.

    Called during first login MFA setup flow. The setup_token from
    /platform/login (mfa_setup_required response) must be passed as
    the Bearer token in the Authorization header.

    SECURITY: Validates the Bearer token is a valid MFA setup token
    (mfa_setup_required=True, is_platform=True) to prevent unauthenticated
    secret generation. Does NOT use PlatformAdmin dependency because
    the user only has a setup_token (not a full platform token).
    """
    # Validate the setup token — reject requests without valid MFA setup context
    try:
        payload = jose_jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Accept both the new type="mfa_setup" tokens and legacy tokens with
    # mfa_setup_required=True claim (defense-in-depth: check both)
    is_mfa_setup_token = (
        payload.get("type") == "mfa_setup" or payload.get("mfa_setup_required")
    )
    if not is_mfa_setup_token or not payload.get("is_platform"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid MFA setup token required",
        )

    # Look up the user to include their email in the provisioning URI
    user_id = payload.get("sub")
    user_email = "Platform Admin"
    if user_id:
        from app.models.user import User

        user = await db.get(User, UUID(user_id))
        if user:
            user_email = user.email

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user_email,
        issuer_name=settings.MFA_ISSUER_NAME,
    )
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
    }


@router.post("/refresh", summary="Refresh platform admin tokens")
async def platform_refresh(
    data: PlatformRefreshRequest,
    request: Request,
    db: UnscopedDatabaseSession,
):
    """
    Refresh access token using a platform admin refresh token.

    This endpoint does NOT require PlatformAdmin dependency because the
    caller's access token may be expired — they only have a valid refresh token.

    Validates:
    - Token is a valid refresh token (type="refresh")
    - Token's tenant_id matches the platform tenant
    - User still exists and is active in the platform tenant

    Implements token rotation: old refresh token is blacklisted,
    new access + refresh tokens are issued.
    """
    from app.models.user import User, UserRole, UserStatus

    platform_tenant_id = str(settings.PLATFORM_TENANT_ID)

    # 1. Decode and validate the refresh token
    try:
        payload = jose_jwt.decode(
            data.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # 2. Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # 3. Verify it belongs to the platform tenant
    if payload.get("tenant_id") != platform_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token scope",
        )

    # 4. Check the token is not blacklisted (token rotation security)
    blacklist_service = await get_token_blacklist_service()
    if await blacklist_service.is_blacklisted(data.refresh_token):
        logger.warning(
            "platform_refresh_blacklisted_token",
            user_id=payload.get("sub"),
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    # 5. Look up the user and verify they are still active
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(User).where(
            User.id == UUID(user_id),
            User.tenant_id == UUID(platform_tenant_id),
            User.role == UserRole.PLATFORM_ADMIN,  # Verify role on refresh
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active",
        )

    # 6. Blacklist the old refresh token to prevent reuse (token rotation)
    await blacklist_service.blacklist_token(data.refresh_token)

    # 7. Issue new tokens using the same pattern as _issue_tokens
    service = PlatformService(db)
    token_result = await service._issue_tokens(user)
    tokens = token_result["tokens"]

    await service.log_action(
        actor_user_id=user.id,
        action="platform_token_refresh",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return PlatformLoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=PlatformUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            mfa_enabled=user.mfa_enabled,
        ),
    )


# ============================================================
# Protected endpoints (require PlatformAdmin)
# ============================================================


@router.get("/me", summary="Get platform admin profile")
async def platform_me(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
):
    """Get the current platform admin's profile."""
    from app.models.user import User

    user = await db.get(User, UUID(admin["user_id"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return PlatformUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        mfa_enabled=user.mfa_enabled,
    )


@router.get("/tenants", summary="List all tenants")
async def list_tenants(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status: str | None = None,
    tier: str | None = None,
):
    """List all tenants with student/staff/school counts."""
    if page_size > 100:
        page_size = 100
    service = PlatformService(db)
    return await service.list_tenants(
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status,
        tier_filter=tier,
    )


@router.get("/tenants/{tenant_id}", summary="Get tenant details")
async def get_tenant(
    tenant_id: UUID,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
):
    """Get detailed information about a specific tenant."""
    service = PlatformService(db)
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Get counts for this single tenant
    counts = await service._get_tenant_counts([tenant_id])
    tc = counts.get(str(tenant_id), {})

    return TenantDetail(
        id=tenant.id,
        name=tenant.name,
        subdomain=tenant.subdomain,
        tenant_type=tenant.tenant_type.value if tenant.tenant_type else None,
        status=tenant.status.value if tenant.status else None,
        subscription_tier=(
            tenant.subscription_tier.value if tenant.subscription_tier else None
        ),
        is_active=tenant.is_active,
        max_students=tenant.max_students,
        max_staff=tenant.max_staff,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        email=tenant.email,
        phone=tenant.phone,
        logo_url=tenant.logo_url,
        primary_color=tenant.primary_color,
        features=tenant.features,
        subscription_start=tenant.subscription_start,
        subscription_end=tenant.subscription_end,
        trial_ends_at=tenant.trial_ends_at,
        student_count=tc.get("students", 0),
        staff_count=tc.get("staff", 0),
        school_count=tc.get("schools", 0),
    )


@router.patch("/tenants/{tenant_id}", summary="Update tenant")
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdateRequest,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Update tenant details (subscription tier, limits, etc.)."""
    service = PlatformService(db)
    try:
        tenant = await service.update_tenant(
            tenant_id, data.model_dump(exclude_none=True)
        )
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        )

    # Invalidate cached tenant data so changes (e.g. name) take effect immediately
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        from app.middleware.tenant import invalidate_tenant_cache

        await invalidate_tenant_cache(redis_client, tenant.subdomain)

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="tenant_update",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        details=data.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Tenant updated", "tenant_id": str(tenant_id)}


@router.post("/tenants/{tenant_id}/suspend", summary="Suspend tenant")
async def suspend_tenant(
    tenant_id: UUID,
    data: TenantSuspendRequest,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Suspend a tenant (blocks all access)."""
    service = PlatformService(db)
    try:
        tenant = await service.suspend_tenant(tenant_id, data.reason)
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == "not_found"
                else status.HTTP_409_CONFLICT
            ),
            detail=e.message,
        )

    # Invalidate cached tenant data so suspension takes effect immediately
    # (without this, users could access the system for up to 10 minutes)
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        from app.middleware.tenant import invalidate_tenant_cache

        await invalidate_tenant_cache(redis_client, tenant.subdomain)

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="tenant_suspend",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        details={"reason": data.reason},
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Tenant suspended", "tenant_id": str(tenant_id)}


@router.post("/tenants/{tenant_id}/activate", summary="Activate tenant")
async def activate_tenant(
    tenant_id: UUID,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Activate a suspended tenant."""
    service = PlatformService(db)
    try:
        tenant = await service.activate_tenant(tenant_id)
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        )

    # Invalidate cached tenant data so reactivation takes effect immediately
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        from app.middleware.tenant import invalidate_tenant_cache

        await invalidate_tenant_cache(redis_client, tenant.subdomain)

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="tenant_activate",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Tenant activated", "tenant_id": str(tenant_id)}


@router.post(
    "/impersonate/{tenant_id}",
    summary="Impersonate a tenant",
    response_model=ImpersonationResponse,
)
async def impersonate_tenant(
    tenant_id: UUID,
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """
    Get a short-lived impersonation token scoped to a target tenant.

    The token:
    - Has tenant_id set to the TARGET tenant
    - Works with all existing school endpoints unchanged
    - Expires in 30 minutes (configurable)
    - Cannot be refreshed
    - Is fully audited
    """
    service = PlatformService(db)
    try:
        result = await service.create_impersonation_token(admin, tenant_id)
    except PlatformServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        )

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="impersonate_start",
        target_tenant_id=tenant_id,
        target_entity_type="tenant",
        target_entity_id=tenant_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return result


@router.get("/analytics", summary="Platform-wide analytics")
async def platform_analytics(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    request: Request,
):
    """Get platform-wide analytics (total tenants, students, staff, etc.)."""
    service = PlatformService(db)
    result = await service.get_analytics()

    await service.log_action(
        actor_user_id=UUID(admin["user_id"]),
        action="analytics_view",
        ip_address=request.client.host if request.client else None,
    )

    return result


@router.get("/audit-log", summary="Platform audit log")
async def platform_audit_log(
    admin: PlatformAdmin,
    db: UnscopedDatabaseSession,
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
):
    """View the platform admin audit log."""
    if page_size > 100:
        page_size = 100
    service = PlatformService(db)
    return await service.get_audit_log(
        page=page,
        page_size=page_size,
        action_filter=action,
    )

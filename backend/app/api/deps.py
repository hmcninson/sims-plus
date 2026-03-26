"""
SIMS Plus - API Dependencies

Common dependencies injected into API endpoints.
"""

import dataclasses
from collections.abc import AsyncGenerator
from datetime import datetime, time, timedelta, timezone
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_maker
from app.middleware.tenant import TenantContext
from app.models.school import School
from app.services.token_blacklist import get_token_blacklist_service

logger = structlog.get_logger()

# OAuth2 scheme for JWT token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Paths that don't require tenant context (subset of middleware PUBLIC_PATHS)
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/onboarding/register",
    "/api/v1/onboarding/suggest-subdomain",
    "/api/v1/tenant/check-subdomain",
    "/api/v1/tenant/validate",
}

_PUBLIC_PATH_PREFIXES = (
    "/api/v1/tenant/validate/",
    "/api/v1/tenant/check-subdomain/",
    "/api/v1/onboarding/",
    "/api/v1/auth/register",
    "/api/v1/auth/validate-reset-token",
    "/api/v1/auth/reset-password",
    "/api/v1/parent/webhook/",  # Paystack webhook (no subdomain; signature-verified)
    "/api/v1/admissions/public/",  # Public application form — no JWT, tenant from subdomain
    "/api/v1/subscription/webhook/",  # Subscription webhook — tenant from metadata, not subdomain
    "/api/v1/platform/login",  # Platform admin login (no tenant context)
    "/api/v1/platform/refresh",  # Platform admin token refresh
    "/api/v1/platform/mfa/",  # MFA verify/setup/generate (no tenant context)
)


def _is_public_path(path: str) -> bool:
    """Check if path doesn't require tenant context."""
    if path in _PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Tenant-scoped database session.

    Sets the PostgreSQL session variable for RLS based on tenant_id
    from request.state (set by TenantMiddleware).

    SECURITY:
    - Raises HTTP 400 if tenant context is missing for non-public API routes.
    - This prevents accidental unscoped queries that would return zero rows
      (silent data loss) with hardened RLS.
    - Always clears tenant context in finally block.
    """
    async with async_session_maker() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)

            if tenant_id:
                await session.execute(
                    text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                    {"tenant_id": str(tenant_id)},
                )
            else:
                # CRITICAL: Reject non-public API routes without tenant context.
                # This prevents silent zero-row queries with hardened RLS.
                path = request.url.path
                if path.startswith("/api/") and not _is_public_path(path):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tenant context required but not set. Access via school subdomain.",
                    )

            yield session
            await session.commit()
        except HTTPException:
            raise  # Don't rollback for HTTP exceptions we raised intentionally
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                logger.warning(
                    "clear_tenant_context_failed",
                    tenant_id=str(tenant_id) if tenant_id else None,
                    exc_info=True,
                )
            await session.close()


async def get_unscoped_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session WITHOUT tenant RLS context.

    Use ONLY for:
    - Tenant lookup in middleware (tenants table has no RLS)
    - Onboarding (creating new tenant + school + admin user)
    - Audit log insertion (audit_logs table has no RLS)
    - Reserved subdomain queries

    SECURITY WARNING:
    With FORCE ROW LEVEL SECURITY and sims_app_user, this session
    CANNOT read/write tenant-scoped tables because tenant_id = NULL
    evaluates to FALSE. It only works for non-RLS tables (tenants,
    reserved_subdomains, audit_logs).
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            # Commit before re-raising HTTP exceptions so that side effects
            # (e.g. incrementing failed_login_attempts in platform admin login)
            # are persisted even when the endpoint returns an error response.
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_public_tenant_db(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Tenant-scoped DB session for public (unauthenticated) endpoints.

    Used by the Admissions Portal public form endpoints. Reads tenant_id
    from request.state (set by TenantMiddleware from subdomain resolution).

    Unlike get_db(), this does NOT require JWT authentication.
    Unlike get_unscoped_db(), this DOES set RLS tenant context.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School not found. Please check the URL.",
        )

    async with async_session_maker() as session:
        try:
            # Set RLS context — all queries will be filtered by this tenant
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                {"tid": str(tenant_id)},
            )
            yield session
            await session.commit()
        except HTTPException:
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                # Clear tenant context to prevent leaking to next connection user
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                logger.warning(
                    "clear_tenant_context_failed",
                    tenant_id=str(tenant_id),
                    exc_info=True,
                )
            await session.close()


# Type aliases for dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
UnscopedDatabaseSession = Annotated[AsyncSession, Depends(get_unscoped_db)]
PublicTenantSession = Annotated[AsyncSession, Depends(get_public_tenant_db)]


async def get_current_user_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> str:
    """
    Validate JWT token and extract user ID.

    Args:
        token: JWT access token from Authorization header

    Returns:
        User ID from token payload

    Raises:
        HTTPException: If token is invalid, expired, or blacklisted
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Reject non-access tokens (e.g., refresh tokens must not be used as access tokens)
        if payload.get("type") != "access":
            raise credentials_exception

        # Check if token is blacklisted
        blacklist_service = await get_token_blacklist_service()
        if await blacklist_service.is_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user's tokens were mass-revoked
        token_iat = payload.get("iat")
        if token_iat and await blacklist_service.is_user_token_revoked(user_id, token_iat):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user_id
    except JWTError:
        raise credentials_exception


# Type alias for current user dependency
CurrentUserId = Annotated[str, Depends(get_current_user_id)]


async def get_current_tenant_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> str:
    """
    Extract tenant ID from JWT token.

    Args:
        token: JWT access token

    Returns:
        Tenant ID from token payload

    Raises:
        HTTPException: If tenant_id is missing from token
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        tenant_id: str | None = payload.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found",
            )
        return tenant_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# Type alias for current tenant dependency
CurrentTenantId = Annotated[str, Depends(get_current_tenant_id)]


async def get_tenant_from_request(request: Request) -> TenantContext:
    """
    Get tenant context from request state.

    This is set by TenantMiddleware based on the subdomain.

    Args:
        request: FastAPI request object

    Returns:
        TenantContext with tenant info

    Raises:
        HTTPException: If no tenant context is available
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant context. Access via school subdomain.",
        )

    return TenantContext(
        tenant_id=tenant_id,
        subdomain=getattr(request.state, "tenant_subdomain", ""),
        name=getattr(request.state, "tenant_name", ""),
        is_active=True,  # If we got here, tenant is active
    )


# Type alias for tenant from request
RequestTenant = Annotated[TenantContext, Depends(get_tenant_from_request)]


async def validate_token_tenant(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> None:
    """
    Validate that JWT token tenant matches request subdomain.

    This is a critical security check to prevent cross-tenant access.

    Args:
        request: FastAPI request object
        token: JWT access token

    Raises:
        HTTPException: If token tenant doesn't match request subdomain
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        token_tenant_id = payload.get("tenant_id")
        request_tenant_id = getattr(request.state, "tenant_id", None)

        if not token_tenant_id or not request_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing tenant context",
            )

        # Compare tenant IDs (convert to string for comparison)
        if str(token_tenant_id) != str(request_tenant_id):
            # Audit log cross-tenant access attempt for security monitoring
            try:
                from app.services.audit import AuditService, AuditEventType

                audit = AuditService(None)
                await audit.log(
                    event_type=AuditEventType.CROSS_TENANT_REJECTED,
                    tenant_id=UUID(str(request_tenant_id)),
                    user_id=UUID(payload["sub"]) if payload.get("sub") else None,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details={
                        "token_tenant_id": str(token_tenant_id),
                        "request_tenant_id": str(request_tenant_id),
                        "outcome": "rejected",
                    },
                )
            except Exception:
                pass  # Audit failure must not block security response
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token not valid for this school",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# Type alias for validated token tenant
ValidatedTokenTenant = Annotated[None, Depends(validate_token_tenant)]


async def get_validated_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Get current user with full validation including cross-tenant check.

    This is the recommended dependency for protected endpoints as it:
    1. Validates the JWT token
    2. Checks if token is blacklisted
    3. Extracts user claims
    4. Validates token tenant matches request subdomain

    Args:
        request: FastAPI request object
        token: JWT access token

    Returns:
        Dict with user info from token claims

    Raises:
        HTTPException: If token is invalid, blacklisted, or tenant mismatch
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Validate token type
        if payload.get("type") != "access":
            raise credentials_exception

        # Check if token is blacklisted
        blacklist_service = await get_token_blacklist_service()
        if await blacklist_service.is_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user's tokens were mass-revoked
        token_iat = payload.get("iat")
        if token_iat and await blacklist_service.is_user_token_revoked(user_id, token_iat):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Cross-tenant validation
        token_tenant_id = payload.get("tenant_id")
        request_tenant_id = getattr(request.state, "tenant_id", None)

        if request_tenant_id and token_tenant_id:
            if str(token_tenant_id) != str(request_tenant_id):
                # Audit log cross-tenant access attempt for security monitoring
                try:
                    from app.services.audit import AuditService, AuditEventType

                    audit = AuditService(None)
                    await audit.log(
                        event_type=AuditEventType.CROSS_TENANT_REJECTED,
                        tenant_id=UUID(str(request_tenant_id)),
                        user_id=UUID(user_id) if user_id else None,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        details={
                            "token_tenant_id": str(token_tenant_id),
                            "request_tenant_id": str(request_tenant_id),
                            "outcome": "rejected",
                        },
                    )
                except Exception:
                    pass  # Audit failure must not block security response
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token not valid for this school. Please login again.",
                )

        # Store user info in request state for other dependencies
        request.state.user_id = user_id
        request.state.user_role = payload.get("role")
        request.state.user_permissions = payload.get("permissions", [])

        return {
            "user_id": user_id,
            "tenant_id": token_tenant_id,
            "school_id": payload.get("school_id"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
            "email": payload.get("email"),
            # Chain support: tenant_type and accessible schools from JWT
            "tenant_type": payload.get("tenant_type", "single_school"),
            "accessible_school_ids": payload.get("accessible_school_ids", []),
            # Per-school role mapping for chain tenants (WP-2.1)
            "school_roles": payload.get("school_roles", {}),
        }

    except JWTError:
        raise credentials_exception


# Type alias for validated current user (recommended for protected endpoints)
ValidatedUser = Annotated[dict, Depends(get_validated_current_user)]


# =========================
# Subscription Enforcement (C1 — dependency, not middleware)
# =========================

# Paths exempt from subscription enforcement even when authenticated.
# The subscription management page must remain accessible so users can upgrade.
_SUBSCRIPTION_EXEMPT_PATHS = (
    "/api/v1/subscription/",
    "/api/v1/auth/",
    "/api/v1/tenant/",
    "/api/v1/onboarding/",
    "/api/v1/settings/subscription",
    "/api/v1/platform/",  # Platform admin endpoints are not tenant-subscription-gated
)

# HTTP methods allowed during grace period (read-only access)
_GRACE_PERIOD_METHODS = {"GET", "HEAD", "OPTIONS"}


async def enforce_subscription(
    request: Request,
) -> None:
    """
    Enforce subscription/trial status on all API requests.

    This is added as a global dependency on api_router. It reads
    tenant status from request.state (set by TenantMiddleware) and
    only enforces on requests that have both a tenant context and
    an authenticated user (indicated by presence of user_id on
    request.state, set by get_validated_current_user).

    Unauthenticated routes are implicitly exempt because they won't
    have user_id on request.state.

    Enforcement rules:
    - Suspended/cancelled tenants: 403 hard block
    - Trial expired (within grace period): read-only (GET/HEAD/OPTIONS only)
    - Trial expired (past grace period): 403 hard block
    - Subscription expired: same grace/block pattern
    - Active/trial not expired: pass through
    """
    path = request.url.path

    # Exempt subscription-related paths so users can upgrade (H3)
    if any(path.startswith(prefix) for prefix in _SUBSCRIPTION_EXEMPT_PATHS):
        return

    # Only enforce for requests with tenant context — public paths skip
    tenant_status = getattr(request.state, "tenant_status", None)
    if not tenant_status:
        return

    # Only enforce for authenticated requests — unauthenticated routes
    # (login, register, webhook, etc.) won't have an Authorization header.
    # We check the header directly rather than request.state.user_id because
    # this runs as a router-level dependency BEFORE endpoint-level deps like
    # get_validated_current_user have a chance to set request.state.
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return

    trial_ends_at = getattr(request.state, "tenant_trial_ends_at", None)
    subscription_end = getattr(request.state, "tenant_subscription_end", None)

    now = datetime.now(timezone.utc)

    # 1. Suspended or cancelled — hard block (differentiated codes for frontend)
    if tenant_status in ("cancelled", "suspended"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your school account is no longer active. Contact support.",
            headers={
                "X-Subscription-Code": "TENANT_CANCELLED"
                if tenant_status == "cancelled"
                else "TENANT_SUSPENDED"
            },
        )

    # 2. Trial tenant — check expiration
    if tenant_status == "trial" and trial_ends_at:
        # Ensure trial_ends_at is a datetime for comparison
        if isinstance(trial_ends_at, datetime):
            trial_dt = trial_ends_at
        else:
            return

        if now > trial_dt:
            grace_end = trial_dt + timedelta(days=settings.TRIAL_GRACE_PERIOD_DAYS)

            if now > grace_end:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your trial has expired. Upgrade to continue.",
                    headers={"X-Subscription-Code": "TRIAL_EXPIRED"},
                )
            else:
                # Within grace period — read-only
                if request.method not in _GRACE_PERIOD_METHODS:
                    days_left = max(0, (grace_end - now).days)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Your trial has expired. You have {days_left} days of "
                            f"read-only access remaining. Upgrade to continue."
                        ),
                        headers={"X-Subscription-Code": "TRIAL_GRACE_PERIOD"},
                    )

    # 3. Active subscription — check expiration
    if tenant_status == "active" and subscription_end:
        from datetime import date as date_type

        if isinstance(subscription_end, date_type):
            sub_expires = datetime.combine(subscription_end, time.max, tzinfo=timezone.utc)
        elif isinstance(subscription_end, datetime):
            sub_expires = subscription_end
        else:
            return

        if now > sub_expires:
            grace_end = sub_expires + timedelta(days=settings.TRIAL_GRACE_PERIOD_DAYS)

            if now > grace_end:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your subscription has expired. Renew to continue.",
                    headers={"X-Subscription-Code": "SUBSCRIPTION_EXPIRED"},
                )
            else:
                if request.method not in _GRACE_PERIOD_METHODS:
                    days_left = max(0, (grace_end - now).days)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Your subscription has expired. You have {days_left} days "
                            f"of read-only access. Renew to continue."
                        ),
                        headers={"X-Subscription-Code": "SUBSCRIPTION_GRACE_PERIOD"},
                    )


def require_feature(feature: str):
    """
    Dependency factory that checks if a feature is available on the tenant's plan.

    Handles three states from PLAN_FEATURES:
    - True: feature included in plan -> access granted
    - "addon": feature available as add-on -> check tenant.features JSONB
    - False: feature not available on this plan -> 403

    Usage:
        @router.get("/endpoint", dependencies=[Depends(require_feature("boarding"))])
    """
    async def _check_feature(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(get_validated_current_user),
    ) -> None:
        tenant_id = UUID(current_user["tenant_id"])
        from app.services.subscription import SubscriptionService
        sub_service = SubscriptionService(db)
        await sub_service.check_feature_access(tenant_id, feature)

    return _check_feature


def require_permissions(*required_permissions: str):
    """
    Dependency factory to require specific permissions.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_permissions("users.*"))])
        async def admin_endpoint(): ...

    Args:
        required_permissions: Permission strings required for access

    Returns:
        Dependency function
    """
    async def check_permissions(
        request: Request,
        user: ValidatedUser,
    ) -> None:
        user_permissions = user.get("permissions", [])

        # Platform admin has all permissions
        if "*" in user_permissions:
            return

        # Self-contained school-scoped permission resolution: for chain tenants
        # where the user has a different role at the active school, override
        # permissions from the JWT with that school-specific role's permissions.
        # This avoids a dependency-ordering bug where get_school_context() runs
        # AFTER require_permissions() in FastAPI's dependency graph.
        school_roles = user.get("school_roles", {})
        active_school = request.headers.get("X-Active-School")
        if active_school and school_roles:
            role_at_school = school_roles.get(active_school)
            if role_at_school and role_at_school != user.get("role"):
                from app.services.auth import AuthService
                # Only allow known system roles — prevents a stored "platform_admin"
                # value in user_schools from granting wildcard permissions.
                if role_at_school not in AuthService.ROLE_PERMISSIONS:
                    role_at_school = None
                else:
                    user_permissions = AuthService.get_role_permissions(role_at_school)

        for required in required_permissions:
            # Check for exact match
            if required in user_permissions:
                continue

            # Check for wildcard match (e.g., "users.*" matches "users.read")
            required_parts = required.split(".")
            matched = False
            for perm in user_permissions:
                perm_parts = perm.split(".")
                if len(perm_parts) >= 2 and perm_parts[1] == "*":
                    if perm_parts[0] == required_parts[0]:
                        matched = True
                        break
            if matched:
                continue

            # Permission not found
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {required}",
            )

    return check_permissions


# =========================
# School Context (Chain Support)
# =========================


@dataclasses.dataclass(frozen=True, slots=True)
class SchoolContext:
    """
    Resolved school context for the current request.

    For single-school tenants, auto-resolves to the lone school.
    For chain tenants, resolved from the X-Active-School header
    after validating against the JWT's accessible_school_ids.
    """

    school_id: UUID
    tenant_id: UUID
    school_name: str
    # The user's role at this specific school (from JWT school_roles claim).
    # None means the user uses their global role at this school.
    role_at_school: str | None = None

    @classmethod
    def from_explicit(
        cls,
        school_id: UUID,
        tenant_id: UUID,
        school_name: str = "",
        role_at_school: str | None = None,
    ) -> "SchoolContext":
        """
        Create a SchoolContext from explicit values (for Celery tasks
        and other non-HTTP contexts where no request header exists).
        """
        return cls(
            school_id=school_id,
            tenant_id=tenant_id,
            school_name=school_name,
            role_at_school=role_at_school,
        )


async def get_school_context(
    request: Request,
    db: DatabaseSession,
    user: ValidatedUser,
    x_active_school: str | None = Header(None, alias="X-Active-School"),
) -> SchoolContext:
    """
    Resolve the active school for the current request.

    Resolution logic:
    1. If X-Active-School header is present, validate it against
       the JWT's accessible_school_ids and return it.
    2. If the tenant is single-school and no header is provided,
       auto-resolve to the only school in the tenant.
    3. If the tenant is a chain and no header is provided, return 400.

    SECURITY:
    - The header value is validated against the JWT claim to prevent
      a user from accessing schools they are not authorized for.
    - Defense-in-depth: the school is also verified to belong to
      the tenant via a DB query.
    """
    tenant_id_str = user.get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    tenant_id = UUID(tenant_id_str)
    tenant_type = user.get("tenant_type", "single_school")
    accessible_ids: list[str] = user.get("accessible_school_ids", [])
    # Per-school role mapping from JWT (WP-2.1): {school_id_str: role_name}
    school_roles: dict[str, str] = user.get("school_roles", {})

    # Wildcard sentinel: ["*"] means the user has access to ALL schools in this
    # tenant but the full list was too large for the JWT.  The DB query below
    # still validates that the requested school belongs to the tenant, so
    # security is preserved.
    has_full_chain_access = accessible_ids == ["*"]

    if x_active_school:
        # Validate the header value against JWT claims
        try:
            active_school_id = UUID(x_active_school)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Active-School header: not a valid UUID",
            )

        # For chain tenants, verify the user has access to this school.
        # SECURITY: Must check even when accessible_ids is empty — an empty
        # list means the user has NO school access (not "all schools").
        if tenant_type == "school_chain":
            if not has_full_chain_access:
                # Normal path: check the specific list from the JWT
                if not accessible_ids or str(active_school_id) not in accessible_ids:
                    # Audit log unauthorized school access attempt
                    try:
                        from app.services.audit import AuditService, AuditEventType

                        audit = AuditService(None)
                        await audit.log(
                            event_type=AuditEventType.SCHOOL_ACCESS_DENIED,
                            tenant_id=tenant_id,
                            user_id=UUID(user.get("user_id")) if user.get("user_id") else None,
                            ip_address=request.client.host if request.client else None,
                            details={
                                "requested_school_id": str(active_school_id),
                                "tenant_type": tenant_type,
                                "outcome": "rejected",
                            },
                        )
                    except Exception:
                        pass  # Audit failure must not block security response
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have access to the requested school",
                    )
            # When has_full_chain_access is True, skip the list check.
            # The defense-in-depth DB query below validates tenant membership.
        elif accessible_ids and str(active_school_id) not in accessible_ids:
            # Single-school tenants with explicit accessible_ids: validate too
            # Audit log unauthorized school access attempt
            try:
                from app.services.audit import AuditService, AuditEventType

                audit = AuditService(None)
                await audit.log(
                    event_type=AuditEventType.SCHOOL_ACCESS_DENIED,
                    tenant_id=tenant_id,
                    user_id=UUID(user.get("user_id")) if user.get("user_id") else None,
                    ip_address=request.client.host if request.client else None,
                    details={
                        "requested_school_id": str(active_school_id),
                        "tenant_type": tenant_type,
                        "outcome": "rejected",
                    },
                )
            except Exception:
                pass  # Audit failure must not block security response
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to the requested school",
            )

        # Defense-in-depth: verify school belongs to this tenant and is not deleted
        result = await db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.id == active_school_id)
            .where(School.deleted_at.is_(None))
        )
        school = result.scalar_one_or_none()
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found in this tenant",
            )

        ctx = SchoolContext(
            school_id=school.id,
            tenant_id=tenant_id,
            school_name=school.name,
            # Resolve the user's role at this specific school from the JWT claim
            role_at_school=school_roles.get(str(school.id)),
        )
        return ctx

    # No header -- auto-resolve for single-school tenants
    if tenant_type == "school_chain":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Active-School header is required for chain tenants",
        )

    # Single-school tenant: find the one school
    result = await db.execute(
        select(School)
        .where(School.tenant_id == tenant_id)
        .where(School.deleted_at.is_(None))
        .limit(1)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No school found for this tenant",
        )

    ctx = SchoolContext(
        school_id=school.id,
        tenant_id=tenant_id,
        school_name=school.name,
        # For single-school tenants, look up role too (backward-compatible: defaults to None)
        role_at_school=school_roles.get(str(school.id)),
    )
    return ctx


async def get_optional_school_context(
    request: Request,
    db: DatabaseSession,
    user: ValidatedUser,
    x_active_school: str | None = Header(None, alias="X-Active-School"),
) -> SchoolContext | None:
    """
    Optional school context -- returns None instead of raising
    when no school can be resolved.

    Use for endpoints that work with or without school filtering
    (e.g., cross-school reports for chain admins).
    """
    try:
        return await get_school_context(request, db, user, x_active_school)
    except HTTPException as exc:
        # Only swallow "header required" errors (chain tenant without header).
        # Let 403 (unauthorized) and 404 (not found) propagate.
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            return None
        raise


# Type aliases for school context dependency injection
SchoolCtx = Annotated[SchoolContext, Depends(get_school_context)]
OptionalSchoolCtx = Annotated[SchoolContext | None, Depends(get_optional_school_context)]


# =========================
# Applicant User (Role-Validated)
# =========================


async def get_applicant_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Validate JWT and ensure user has the 'applicant' role.

    This dependency is used for all authenticated applicant endpoints.
    It performs the same validation as get_validated_current_user() plus
    an additional role check.

    Rejects:
    - Invalid/expired tokens
    - Blacklisted tokens
    - Cross-tenant tokens
    - Non-applicant roles (staff, parent, student, etc.)

    Returns:
        Dict with user claims: user_id, tenant_id, email, role, permissions.

    Raises:
        HTTPException 401: Invalid token
        HTTPException 403: Cross-tenant or wrong role
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Validate token type
        if payload.get("type") != "access":
            raise credentials_exception

        # Check if token is blacklisted
        blacklist_service = await get_token_blacklist_service()
        if await blacklist_service.is_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user's tokens were mass-revoked
        token_iat = payload.get("iat")
        if token_iat and await blacklist_service.is_user_token_revoked(
            user_id, token_iat
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Cross-tenant validation
        token_tenant_id = payload.get("tenant_id")
        request_tenant_id = getattr(request.state, "tenant_id", None)

        if request_tenant_id and token_tenant_id:
            if str(token_tenant_id) != str(request_tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token not valid for this school.",
                )

        # Role check: must be applicant
        role = payload.get("role")
        if role != "applicant":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access restricted to applicant accounts.",
            )

        return {
            "user_id": user_id,
            "tenant_id": token_tenant_id,
            "email": payload.get("email"),
            "role": role,
            "permissions": payload.get("permissions", []),
        }

    except JWTError:
        raise credentials_exception


# Type alias for applicant user dependency
ApplicantUser = Annotated[dict, Depends(get_applicant_user)]


# =========================
# Platform Admin User (Role-Validated)
# =========================


async def get_platform_admin_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Dependency that validates the caller is a platform admin.

    Validates:
    1. JWT is valid, not expired, not blacklisted
    2. Token type is "access" (rejects mfa_pending tokens)
    3. role == "platform_admin"
    4. is_platform == true claim exists
    5. tenant_id matches PLATFORM_TENANT_ID
    6. is_impersonation is NOT set (impersonation tokens cannot access /platform/*)
    7. mfa_setup_required is NOT set (setup tokens can only access MFA setup endpoints)
    8. User still exists and is active in the database (cached 60s in Redis)

    Does NOT check ValidatedTokenTenant (no subdomain-based tenant context
    for platform admin requests).

    Returns:
        dict with user_id, email, role, tenant_id
    """
    from app.models.user import User, UserRole, UserStatus

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Platform admin authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        raise credentials_exception

    # Validate token type — reject refresh/mfa_pending tokens
    if payload.get("type") != "access":
        raise credentials_exception

    # Validate platform admin claims
    if payload.get("role") != "platform_admin":
        raise credentials_exception
    if not payload.get("is_platform"):
        raise credentials_exception
    if str(payload.get("tenant_id")) != str(settings.PLATFORM_TENANT_ID):
        raise credentials_exception

    # SECURITY: Reject impersonation tokens at /platform/* endpoints.
    # Impersonation tokens have tenant_id=<target>, so they would fail the
    # PLATFORM_TENANT_ID check above. But defense-in-depth: explicitly reject.
    if payload.get("is_impersonation"):
        raise credentials_exception

    # SECURITY: Reject MFA setup tokens. These are issued on first login
    # before MFA is configured. They must ONLY be used at MFA setup endpoints,
    # not for full platform admin access.
    if payload.get("mfa_setup_required"):
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # Check token blacklist
    blacklist_service = await get_token_blacklist_service()
    if await blacklist_service.is_blacklisted(token):
        raise credentials_exception

    # Check mass-revocation
    token_iat = payload.get("iat")
    if token_iat and await blacklist_service.is_user_token_revoked(user_id, token_iat):
        raise credentials_exception

    # SECURITY: Verify user still exists and is active in the database.
    # Uses Redis cache (60s TTL) to avoid hitting DB on every request.
    redis_client = getattr(request.app.state, "redis", None)
    is_active = None
    cache_key = f"platform_admin_active:{user_id}"

    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                is_active = cached == "1"
        except Exception:
            pass

    if is_active is None:
        # DB check — use app session with platform tenant context
        async with async_session_maker() as check_session:
            await check_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(settings.PLATFORM_TENANT_ID)},
            )
            result = await check_session.execute(
                select(User.status).where(
                    User.id == UUID(user_id),
                    User.role == UserRole.PLATFORM_ADMIN,
                    User.deleted_at.is_(None),
                )
            )
            user_status = result.scalar_one_or_none()
            is_active = user_status == UserStatus.ACTIVE if user_status else False

            # Cache the result for 60 seconds
            if redis_client:
                try:
                    await redis_client.set(cache_key, "1" if is_active else "0", ex=60)
                except Exception:
                    pass

    if not is_active:
        raise credentials_exception

    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": "platform_admin",
        "tenant_id": str(settings.PLATFORM_TENANT_ID),
    }


# Type alias for use in endpoint signatures
PlatformAdmin = Annotated[dict, Depends(get_platform_admin_user)]

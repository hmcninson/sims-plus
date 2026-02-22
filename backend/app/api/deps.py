"""
SIMS Plus - API Dependencies

Common dependencies injected into API endpoints.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_maker
from app.middleware.tenant import TenantContext
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
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type aliases for dependency injection
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
UnscopedDatabaseSession = Annotated[AsyncSession, Depends(get_unscoped_db)]


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
        }

    except JWTError:
        raise credentials_exception


# Type alias for validated current user (recommended for protected endpoints)
ValidatedUser = Annotated[dict, Depends(get_validated_current_user)]


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
        user: ValidatedUser,
    ) -> None:
        user_permissions = user.get("permissions", [])

        # Platform admin has all permissions
        if "*" in user_permissions:
            return

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

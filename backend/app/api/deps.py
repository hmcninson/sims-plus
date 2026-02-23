"""
SIMS Plus - API Dependencies

Common dependencies injected into API endpoints.
"""

import dataclasses
from collections.abc import AsyncGenerator
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
            # Chain support: tenant_type and accessible schools from JWT
            "tenant_type": payload.get("tenant_type", "single_school"),
            "accessible_school_ids": payload.get("accessible_school_ids", []),
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

    @classmethod
    def from_explicit(cls, school_id: UUID, tenant_id: UUID, school_name: str = "") -> "SchoolContext":
        """
        Create a SchoolContext from explicit values (for Celery tasks
        and other non-HTTP contexts where no request header exists).
        """
        return cls(school_id=school_id, tenant_id=tenant_id, school_name=school_name)


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
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have access to the requested school",
                    )
            # When has_full_chain_access is True, skip the list check.
            # The defense-in-depth DB query below validates tenant membership.
        elif accessible_ids and str(active_school_id) not in accessible_ids:
            # Single-school tenants with explicit accessible_ids: validate too
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

        return SchoolContext(
            school_id=school.id,
            tenant_id=tenant_id,
            school_name=school.name,
        )

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

    return SchoolContext(
        school_id=school.id,
        tenant_id=tenant_id,
        school_name=school.name,
    )


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

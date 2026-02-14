"""
SIMS Plus - Tenant Context Middleware

Middleware to extract tenant from request and set database RLS context.

This middleware:
1. Extracts subdomain from request (X-Subdomain header or host)
2. Validates the tenant exists and is active
3. Sets PostgreSQL session variables for Row-Level Security
4. Makes tenant info available to request state
"""

import re
from contextvars import ContextVar
from typing import Optional
from uuid import UUID

from fastapi import Request, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.db.session import async_session_maker

# Context variable to store current tenant info
_tenant_context: ContextVar[Optional[dict]] = ContextVar("tenant_context", default=None)


class TenantContext:
    """Tenant context data."""

    def __init__(
        self,
        tenant_id: UUID,
        subdomain: str,
        name: str,
        is_active: bool,
    ):
        self.tenant_id = tenant_id
        self.subdomain = subdomain
        self.name = name
        self.is_active = is_active


def get_tenant_context() -> Optional[TenantContext]:
    """
    Get the current tenant context.

    Returns:
        TenantContext if set, None otherwise
    """
    ctx = _tenant_context.get()
    if ctx:
        return TenantContext(**ctx)
    return None


def set_tenant_context(tenant_id: UUID, subdomain: str, name: str, is_active: bool) -> None:
    """
    Set the current tenant context.

    Args:
        tenant_id: Tenant UUID
        subdomain: Tenant subdomain
        name: Tenant name
        is_active: Whether tenant is active
    """
    _tenant_context.set({
        "tenant_id": tenant_id,
        "subdomain": subdomain,
        "name": name,
        "is_active": is_active,
    })


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    _tenant_context.set(None)


# Subdomain validation pattern
SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$")

# Reserved subdomains
RESERVED_SUBDOMAINS = {
    "www", "app", "api", "admin", "mail", "ftp", "status", "blog",
    "help", "support", "docs", "cdn", "assets", "staging", "dev",
    "test", "demo", "sandbox",
}

# Paths that don't require tenant context
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/status",
    "/api/v1/tenant/check-subdomain",
}

# Path prefixes that don't require tenant context
PUBLIC_PATH_PREFIXES = (
    "/api/v1/tenant/",  # Tenant validation endpoints are public
    "/api/v1/auth/register",  # Registration is public
    "/api/v1/auth/validate-reset-token",  # Token validation doesn't need tenant
    "/api/v1/auth/reset-password",  # Password reset uses token for tenant context
    "/api/v1/onboarding/",  # Onboarding is public
)


def extract_subdomain_from_host(host: str) -> Optional[str]:
    """
    Extract subdomain from host header.

    Args:
        host: Host header value (e.g., "presec.simsplus.io:8000")

    Returns:
        Subdomain or None
    """
    # Remove port
    host_without_port = host.split(":")[0]

    # Development: support presec.localhost
    if host_without_port.endswith(".localhost"):
        subdomain = host_without_port.replace(".localhost", "").lower()
        if subdomain and subdomain not in RESERVED_SUBDOMAINS:
            return subdomain
        return None

    # Skip localhost without subdomain
    if host_without_port in ("localhost", "127.0.0.1"):
        return None

    # Split host
    parts = host_without_port.split(".")

    # Need at least 3 parts (subdomain.domain.tld)
    if len(parts) < 3:
        return None

    subdomain = parts[0].lower()

    # Check reserved
    if subdomain in RESERVED_SUBDOMAINS:
        return None

    # Validate format
    if not SUBDOMAIN_PATTERN.match(subdomain):
        return None

    if len(subdomain) < 4 or len(subdomain) > 63:
        return None

    return subdomain


def is_public_path(path: str) -> bool:
    """Check if path is public (doesn't require tenant context)."""
    if path in PUBLIC_PATHS:
        return True

    for prefix in PUBLIC_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle tenant context for multi-tenancy.

    Extracts subdomain from request and sets database RLS context.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request and set tenant context."""

        # Clear any previous context
        clear_tenant_context()

        # Skip OPTIONS requests (CORS preflight) - they don't carry auth headers
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Skip tenant context for public paths
        if is_public_path(path):
            return await call_next(request)

        # Get subdomain from X-Subdomain header first (set by frontend proxy)
        subdomain = request.headers.get("x-subdomain")

        # Fallback to extracting from host
        if not subdomain:
            host = request.headers.get("host", "")
            subdomain = extract_subdomain_from_host(host)

        # If no subdomain found and path requires tenant, return error
        if not subdomain:
            # For API routes that require tenant context
            if path.startswith("/api/v1/") and not is_public_path(path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant context required. Access via school subdomain.",
                )
            return await call_next(request)

        # Validate tenant exists and is active
        async with async_session_maker() as db:
            tenant = await self._get_tenant_by_subdomain(db, subdomain)

            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"School '{subdomain}' not found",
                )

            if not tenant["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This school account is currently suspended",
                )

            # Set tenant context in context variable
            set_tenant_context(
                tenant_id=tenant["id"],
                subdomain=tenant["subdomain"],
                name=tenant["name"],
                is_active=tenant["is_active"],
            )

            # Store tenant info in request state for easy access
            request.state.tenant_id = tenant["id"]
            request.state.tenant_subdomain = tenant["subdomain"]
            request.state.tenant_name = tenant["name"]

        # Process request
        try:
            response = await call_next(request)
            return response
        finally:
            # Clean up context
            clear_tenant_context()

    async def _get_tenant_by_subdomain(
        self,
        db: AsyncSession,
        subdomain: str,
    ) -> Optional[dict]:
        """
        Get tenant by subdomain.

        Args:
            db: Database session
            subdomain: Tenant subdomain

        Returns:
            Tenant dict or None
        """
        result = await db.execute(
            text("""
                SELECT id, subdomain, name, is_active
                FROM tenants
                WHERE subdomain = :subdomain
                AND deleted_at IS NULL
            """),
            {"subdomain": subdomain.lower()},
        )
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row.id,
            "subdomain": row.subdomain,
            "name": row.name,
            "is_active": row.is_active,
        }


async def set_db_tenant_context(db: AsyncSession, tenant_id: UUID) -> None:
    """
    Set tenant context in PostgreSQL session for RLS.

    This must be called at the start of each database transaction
    to enable Row-Level Security filtering.

    Args:
        db: Database session
        tenant_id: Tenant UUID
    """
    await db.execute(
        text("SELECT set_tenant_context(:tenant_id)"),
        {"tenant_id": str(tenant_id)},
    )


async def clear_db_tenant_context(db: AsyncSession) -> None:
    """
    Clear tenant context in PostgreSQL session.

    Args:
        db: Database session
    """
    await db.execute(text("SELECT clear_tenant_context()"))

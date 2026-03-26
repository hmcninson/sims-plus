"""
SIMS Plus - Tenant Context Middleware

Middleware to extract tenant from request and set database RLS context.

This middleware:
1. Extracts subdomain from request (X-Subdomain header or host)
2. Validates the tenant exists and is active
3. Sets PostgreSQL session variables for Row-Level Security
4. Makes tenant info available to request state
"""

import json
import re
from contextvars import ContextVar
from datetime import date, datetime
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

import structlog

from app.db.session import async_session_maker
from app.utils.cache_keys import CacheKeys

logger = structlog.get_logger()

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

# Reserved subdomains -- MUST match database seed data AND frontend/proxy.ts
# NOTE: "admin" removed from this set — admin.simsplus.io is now routed to
# the platform admin portal by proxy.ts (Phase 3). The "admin" row in the
# reserved_subdomains DB table is kept so schools cannot register it.
RESERVED_SUBDOMAINS = {
    "www", "app", "api", "mail", "ftp", "status", "blog",
    "help", "support", "docs", "cdn", "assets", "staging", "dev",
    "test", "demo", "sandbox", "beta", "alpha", "portal", "login",
    "register", "signup", "dashboard", "billing", "payments",
    "webhooks", "graphql", "ws", "static", "media", "images",
    "files", "downloads", "uploads",
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
    "/api/v1/auth/reset-password",  # Email-based password reset (uses token, not tenant context)
    "/api/v1/auth/validate-reset-token",  # Token validation doesn't need tenant
}

# Path prefixes that don't require tenant context
PUBLIC_PATH_PREFIXES = (
    "/api/v1/tenant/",  # Tenant validation endpoints are public
    "/api/v1/auth/register",  # Registration is public
    # NOTE: /api/v1/auth/reset-password and /api/v1/auth/validate-reset-token
    # moved to PUBLIC_PATHS (exact match) to avoid prefix-matching
    # /api/v1/auth/reset-password-sms which REQUIRES tenant context.
    "/api/v1/onboarding/",  # Onboarding is public
    "/api/v1/parent/webhook/",  # Paystack webhook (no subdomain; signature-verified)
    "/api/v1/admissions/public/webhook/",  # Paystack webhook — tenant from metadata, not subdomain
    "/api/v1/subscription/webhook/",  # Subscription webhook — tenant from metadata, not subdomain
    "/api/v1/platform/",  # Platform admin endpoints bypass tenant resolution
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

    # Reject consecutive hyphens (not caught by regex)
    if "--" in subdomain:
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
    Tenant lookups are cached in Redis (10-minute TTL) using the shared
    app.state.redis client created at startup, reducing database load
    under high concurrency.
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
                # Return JSONResponse directly -- raising HTTPException inside
                # BaseHTTPMiddleware.dispatch() does not get converted to a
                # proper HTTP response in newer Starlette versions.
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Tenant context required. Access via school subdomain."},
                )
            return await call_next(request)

        # Use the shared Redis client from app lifespan (never create per-request connections)
        redis_client = getattr(request.app.state, "redis", None)

        # Validate tenant exists and is active
        async with async_session_maker() as db:
            tenant = await self._get_tenant_by_subdomain(db, subdomain, redis_client)

            if not tenant:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": f"School '{subdomain}' not found"},
                )

            # Status-aware tenant validation: differentiate cancelled vs suspended
            tenant_status = tenant.get("status")
            if tenant_status == "cancelled":
                # Cancelled tenants appear as "not found" to prevent enumeration
                return JSONResponse(
                    status_code=404,
                    content={"detail": "School not found"},
                )

            if tenant_status == "suspended":
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "This school account has been suspended. Contact your administrator.",
                        "code": "TENANT_SUSPENDED",
                    },
                )

            if not tenant["is_active"]:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "This school account is currently suspended"},
                )

            # Set tenant context in context variable
            tenant_uuid = UUID(tenant["id"])
            set_tenant_context(
                tenant_id=tenant_uuid,
                subdomain=tenant["subdomain"],
                name=tenant["name"],
                is_active=tenant["is_active"],
            )

            # Store tenant info in request state for easy access
            request.state.tenant_id = tenant_uuid
            request.state.tenant_subdomain = tenant["subdomain"]
            request.state.tenant_name = tenant["name"]

            # Subscription enforcement fields — used by enforce_subscription dependency
            request.state.tenant_status = tenant.get("status")
            request.state.tenant_trial_ends_at = tenant.get("trial_ends_at")
            request.state.tenant_subscription_end = tenant.get("subscription_end")

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
        redis_client: Optional[aioredis.Redis],
    ) -> Optional[dict]:
        """Get tenant by subdomain with Redis cache.

        Flow:
        1. Check Redis for cached tenant data
        2. If cache hit AND is_active: return cached data
        3. If cache miss: query PostgreSQL, cache result, return it
        4. If cached but is_active=false: caller handles 403

        Cache TTL: 10 minutes (CacheKeys.TENANT_LOOKUP_TTL).
        Cache is invalidated via invalidate_tenant_cache() when tenant
        data changes (name update, deactivation, subdomain change, etc.).

        Args:
            db: Database session (used on cache miss)
            subdomain: Tenant subdomain
            redis_client: Shared Redis client from app.state.redis (may be None during tests)

        Returns:
            Tenant dict {id, subdomain, name, is_active, settings} or None
        """
        subdomain_lower = subdomain.lower()
        cache_key = CacheKeys.tenant_by_subdomain(subdomain_lower)

        # Try cache first
        if redis_client is not None:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Deserialize ISO datetime strings back to native types (C5)
                    if data.get("trial_ends_at"):
                        data["trial_ends_at"] = datetime.fromisoformat(data["trial_ends_at"])
                    if data.get("subscription_end"):
                        data["subscription_end"] = date.fromisoformat(data["subscription_end"])
                    return data
            except Exception:
                # Redis failure should not break tenant lookup.
                # Fall through to database query.
                logger.warning("redis_cache_read_failed", action="tenant_lookup")

        # Cache miss -- query database (includes subscription fields for enforcement)
        result = await db.execute(
            text("""
                SELECT id, subdomain, name, is_active,
                       status, trial_ends_at, subscription_end
                FROM tenants
                WHERE subdomain = :subdomain
                AND deleted_at IS NULL
            """),
            {"subdomain": subdomain_lower},
        )
        row = result.fetchone()

        if not row:
            return None

        tenant_data = {
            "id": str(row.id),
            "subdomain": row.subdomain,
            "name": row.name,
            "is_active": row.is_active,
            "status": row.status,
            # Serialize datetimes as ISO strings for Redis cache compatibility (C5)
            "trial_ends_at": row.trial_ends_at.isoformat() if row.trial_ends_at else None,
            "subscription_end": row.subscription_end.isoformat() if row.subscription_end else None,
        }

        # Write to cache (best effort -- don't fail request if Redis is down)
        if redis_client is not None:
            try:
                await redis_client.setex(
                    cache_key,
                    CacheKeys.TENANT_LOOKUP_TTL,
                    json.dumps(tenant_data),
                )
            except Exception:
                logger.warning("redis_cache_write_failed", action="tenant_lookup")

        return tenant_data


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
        text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
        {"tenant_id": str(tenant_id)},
    )


async def clear_db_tenant_context(db: AsyncSession) -> None:
    """
    Clear tenant context in PostgreSQL session.

    Args:
        db: Database session
    """
    await db.execute(text("SELECT clear_tenant_context()"))


async def invalidate_tenant_cache(
    redis_client: aioredis.Redis,
    subdomain: str,
    old_subdomain: Optional[str] = None,
) -> None:
    """Invalidate the cached tenant lookup for a subdomain.

    Call this when tenant data changes (name update, deactivation, etc.).
    If the subdomain itself was changed, pass the previous value as
    old_subdomain so the stale cache entry is also removed.

    Args:
        redis_client: Shared Redis client (app.state.redis)
        subdomain: Current subdomain to invalidate
        old_subdomain: Previous subdomain to invalidate (if subdomain changed)
    """
    try:
        cache_key = CacheKeys.tenant_by_subdomain(subdomain.lower())
        await redis_client.delete(cache_key)

        # If subdomain was changed, also delete the old key so stale data
        # doesn't keep resolving to the old tenant record.
        if old_subdomain and old_subdomain.lower() != subdomain.lower():
            old_cache_key = CacheKeys.tenant_by_subdomain(old_subdomain.lower())
            await redis_client.delete(old_cache_key)
    except Exception:
        logger.warning(
            "tenant_cache_invalidation_failed",
            subdomain=subdomain,
            old_subdomain=old_subdomain,
        )

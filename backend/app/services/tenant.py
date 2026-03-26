"""
SIMS Plus - Tenant Service

Business logic for tenant operations including cache invalidation.
"""

import re
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.tenant import invalidate_tenant_cache
from app.models import Tenant, ReservedSubdomain
from app.models.tenant import TenantStatus

logger = structlog.get_logger()


class TenantService:
    """Service for tenant-related operations.

    When a Redis client is provided, tenant mutations (update, deactivate)
    automatically invalidate the middleware's lookup cache so subsequent
    requests see the fresh data.
    """

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    # Subdomain validation regex
    SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$")

    def __init__(
        self,
        db: AsyncSession,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.db = db
        self._redis = redis_client

    def validate_subdomain_format(self, subdomain: str) -> tuple[bool, str | None]:
        """
        Validate subdomain format.

        Args:
            subdomain: Subdomain to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(subdomain) < 4:
            return False, "Subdomain must be at least 4 characters"

        if len(subdomain) > 63:
            return False, "Subdomain must be at most 63 characters"

        if not self.SUBDOMAIN_PATTERN.match(subdomain):
            return False, "Subdomain can only contain lowercase letters, numbers, and hyphens"

        if subdomain.startswith("-") or subdomain.endswith("-"):
            return False, "Subdomain cannot start or end with a hyphen"

        if "--" in subdomain:
            return False, "Subdomain cannot contain consecutive hyphens"

        return True, None

    async def is_subdomain_reserved(self, subdomain: str) -> bool:
        """
        Check if subdomain is in the reserved list.

        Args:
            subdomain: Subdomain to check

        Returns:
            True if reserved, False otherwise
        """
        result = await self.db.execute(
            select(ReservedSubdomain).where(
                ReservedSubdomain.subdomain == subdomain.lower()
            )
        )
        return result.scalar_one_or_none() is not None

    async def is_subdomain_taken(self, subdomain: str) -> bool:
        """
        Check if subdomain is already taken by a tenant.

        Args:
            subdomain: Subdomain to check

        Returns:
            True if taken, False otherwise
        """
        result = await self.db.execute(
            select(Tenant).where(Tenant.subdomain == subdomain.lower())
        )
        return result.scalar_one_or_none() is not None

    async def check_subdomain_availability(
        self, subdomain: str
    ) -> tuple[bool, str | None]:
        """
        Check if a subdomain is available for registration.

        Args:
            subdomain: Subdomain to check

        Returns:
            Tuple of (is_available, reason_if_not_available)
        """
        subdomain = subdomain.lower()

        # Validate format
        is_valid, error = self.validate_subdomain_format(subdomain)
        if not is_valid:
            return False, error

        # Check reserved list
        if await self.is_subdomain_reserved(subdomain):
            return False, "This subdomain is reserved for system use"

        # Check if taken
        if await self.is_subdomain_taken(subdomain):
            return False, "This subdomain is already registered"

        return True, None

    async def get_tenant_by_subdomain(self, subdomain: str) -> Tenant | None:
        """
        Get tenant by subdomain.

        Args:
            subdomain: Tenant subdomain

        Returns:
            Tenant if found, None otherwise
        """
        result = await self.db.execute(
            select(Tenant).where(Tenant.subdomain == subdomain.lower())
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_id(self, tenant_id: UUID) -> Tenant | None:
        """
        Get tenant by ID.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Tenant if found, None otherwise
        """
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def search_tenants(
        self, query: str, limit: int = 10
    ) -> list[Tenant]:
        """
        Search active tenants by name or subdomain for the public school finder.

        Only returns tenants that are active/trial and not soft-deleted.
        Excludes the internal platform tenant.

        Args:
            query: Search string (min 2 chars, enforced at endpoint level)
            limit: Maximum number of results to return

        Returns:
            List of matching Tenant objects (caller should project safe fields only)
        """
        from app.utils.sanitize import escape_ilike

        safe_query = escape_ilike(query.strip())

        result = await self.db.execute(
            select(Tenant)
            .where(
                Tenant.is_active.is_(True),
                Tenant.deleted_at.is_(None),
                # Only show tenants with active or trial status --
                # suspended/cancelled tenants should not appear in search
                Tenant.status.in_([TenantStatus.TRIAL, TenantStatus.ACTIVE]),
                # Exclude the internal platform tenant
                Tenant.subdomain != "_platform",
            )
            .where(
                or_(
                    Tenant.name.ilike(f"%{safe_query}%"),
                    Tenant.subdomain.ilike(f"%{safe_query}%"),
                )
            )
            .order_by(Tenant.name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def validate_tenant(
        self, subdomain: str
    ) -> tuple[bool, Tenant | None, str | None, str | None]:
        """
        Validate tenant by subdomain.

        Checks if tenant exists, is active, and has a valid status.

        Args:
            subdomain: Tenant subdomain

        Returns:
            Tuple of (is_valid, tenant, error_message, error_code)
        """
        tenant = await self.get_tenant_by_subdomain(subdomain)

        if tenant is None:
            return False, None, "School not found", None

        if tenant.deleted_at is not None:
            return False, None, "School not found", None

        # Cancelled tenants are treated as non-existent (same as middleware)
        if tenant.status == TenantStatus.CANCELLED:
            return False, None, "School not found", None

        # Suspended tenants get a specific code so the frontend can show
        # a suspension notice instead of a generic "not found" page
        if tenant.status == TenantStatus.SUSPENDED:
            return (
                False,
                None,
                "This school account has been suspended. Contact your administrator.",
                "TENANT_SUSPENDED",
            )

        if not tenant.is_active:
            return False, None, "This school account is currently inactive", None

        return True, tenant, None, None

    async def update_tenant(
        self,
        tenant_id: UUID,
        *,
        name: Optional[str] = None,
        subdomain: Optional[str] = None,
        is_active: Optional[bool] = None,
        settings: Optional[str] = None,
    ) -> Tenant:
        """
        Update tenant fields and invalidate the Redis cache.

        If the subdomain is changed, both old and new cache keys are deleted
        so stale lookups don't resolve to the old record.

        Args:
            tenant_id: Tenant UUID
            name: New tenant name (optional)
            subdomain: New subdomain (optional)
            is_active: New active status (optional)
            settings: New settings JSON (optional)

        Returns:
            Updated Tenant model

        Raises:
            TenantService.Error: If tenant not found or subdomain conflict
        """
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise self.Error("Tenant not found", 404)

        old_subdomain = tenant.subdomain

        if name is not None:
            tenant.name = name

        if subdomain is not None:
            subdomain = subdomain.lower()
            # Validate format
            is_valid, error = self.validate_subdomain_format(subdomain)
            if not is_valid:
                raise self.Error(error, 422)
            # Check availability (only if actually changing)
            if subdomain != old_subdomain:
                if await self.is_subdomain_taken(subdomain):
                    raise self.Error("This subdomain is already registered", 409)
                if await self.is_subdomain_reserved(subdomain):
                    raise self.Error("This subdomain is reserved for system use", 409)
            tenant.subdomain = subdomain

        if is_active is not None:
            tenant.is_active = is_active

        if settings is not None:
            tenant.settings = settings

        await self.db.flush()
        await self.db.refresh(tenant)

        # Invalidate cache so the middleware picks up the changes on next request
        await self._invalidate_cache(
            tenant.subdomain,
            old_subdomain=old_subdomain if subdomain and subdomain != old_subdomain else None,
        )

        return tenant

    async def deactivate_tenant(self, tenant_id: UUID) -> Tenant:
        """
        Deactivate a tenant (suspend their account).

        Invalidates the cache so subsequent requests immediately see
        is_active=false and return 403.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Updated Tenant model

        Raises:
            TenantService.Error: If tenant not found
        """
        return await self.update_tenant(tenant_id, is_active=False)

    async def _invalidate_cache(
        self,
        subdomain: str,
        old_subdomain: Optional[str] = None,
    ) -> None:
        """Invalidate tenant lookup cache in Redis.

        Best-effort: logs a warning if Redis is unavailable but does not
        raise, since the cache has a short TTL and will self-heal.
        """
        if self._redis is None:
            logger.debug(
                "tenant_cache_invalidation_skipped",
                reason="no_redis_client",
                subdomain=subdomain,
            )
            return

        await invalidate_tenant_cache(
            self._redis,
            subdomain,
            old_subdomain=old_subdomain,
        )

"""
SIMS Plus - Tenant Service

Business logic for tenant operations.
"""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, ReservedSubdomain


class TenantService:
    """Service for tenant-related operations."""

    # Subdomain validation regex
    SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$")

    def __init__(self, db: AsyncSession):
        self.db = db

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

    async def validate_tenant(
        self, subdomain: str
    ) -> tuple[bool, Tenant | None, str | None]:
        """
        Validate tenant by subdomain.

        Checks if tenant exists and is active.

        Args:
            subdomain: Tenant subdomain

        Returns:
            Tuple of (is_valid, tenant, error_message)
        """
        tenant = await self.get_tenant_by_subdomain(subdomain)

        if tenant is None:
            return False, None, "School not found"

        if not tenant.is_active:
            return False, None, "This school account is currently inactive"

        if tenant.deleted_at is not None:
            return False, None, "This school account no longer exists"

        return True, tenant, None

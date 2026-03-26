"""Shared utilities for curriculum services."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CurriculumServiceError(Exception):
    """Custom exception for curriculum operations."""

    def __init__(self, message: str, code: str = "curriculum_error"):
        self.message = message
        self.code = code
        super().__init__(message)


async def check_multi_curriculum_access(db: AsyncSession, tenant_id: UUID) -> None:
    """
    Verify the tenant's subscription plan allows multi-curriculum features.

    Starter/Trial plans are restricted to GES-only. This check gates
    features like grade equivalencies and predicted grades that don't
    require a curriculum_profile_id FK (and thus bypass indirect gating).

    Raises CurriculumServiceError with code 'plan_limit' if not allowed.
    """
    from app.models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise CurriculumServiceError("Tenant not found", "not_found")

    tier = (
        tenant.subscription_tier.value
        if hasattr(tenant.subscription_tier, "value")
        else str(tenant.subscription_tier)
    )

    if tier in ("trial", "starter"):
        raise CurriculumServiceError(
            "This feature requires a Professional or Enterprise plan.",
            "plan_limit",
        )

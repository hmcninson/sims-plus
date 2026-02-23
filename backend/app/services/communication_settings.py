"""
SIMS Plus - Communication Settings Service

Manages the communication_settings JSONB column on the schools table.
Settings cover SMS gateway config, email defaults, and notification toggles.
"""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.schemas.communication import (
    CommunicationSettings,
    CommunicationSettingsUpdate,
)

logger = structlog.get_logger()

# Default settings returned when a school has no stored configuration
_DEFAULT_SETTINGS = CommunicationSettings()


class CommunicationSettingsService:
    """Read and update per-school communication preferences."""

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_school(self, tenant_id: UUID, school_id: UUID) -> School:
        """Fetch a school with defense-in-depth tenant scoping."""
        result = await self.db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.id == school_id)
            .where(School.deleted_at.is_(None))
        )
        school = result.scalar_one_or_none()
        if not school:
            raise self.Error("School not found", 404)
        return school

    async def get_settings(
        self, tenant_id: UUID, school_id: UUID
    ) -> CommunicationSettings:
        """
        Return the communication settings for a school.

        Falls back to defaults when the JSONB column is NULL (new schools
        that have not configured messaging yet).
        """
        school = await self._get_school(tenant_id, school_id)

        if school.communication_settings is None:
            return _DEFAULT_SETTINGS

        # Parse stored JSON through the Pydantic model so any missing
        # keys are filled in with defaults automatically.
        try:
            return CommunicationSettings.model_validate(school.communication_settings)
        except Exception:
            logger.warning(
                "communication_settings_parse_failed",
                school_id=str(school_id),
                exc_info=True,
            )
            return _DEFAULT_SETTINGS

    async def update_settings(
        self,
        tenant_id: UUID,
        school_id: UUID,
        update_data: CommunicationSettingsUpdate,
    ) -> CommunicationSettings:
        """
        Merge partial settings update into the school's communication_settings.

        Only sections present in update_data are overwritten; others are preserved.
        """
        school = await self._get_school(tenant_id, school_id)

        # Start from stored settings (or defaults for fresh schools)
        current = (
            CommunicationSettings.model_validate(school.communication_settings)
            if school.communication_settings
            else _DEFAULT_SETTINGS
        )

        # Merge only the sections that the caller provided
        merged = current.model_copy(
            update={
                k: v
                for k, v in update_data.model_dump(exclude_none=True).items()
                if v is not None
            }
        )

        # Persist back as plain dict so it serializes to JSONB
        school.communication_settings = merged.model_dump()
        await self.db.flush()
        await self.db.refresh(school)

        logger.info(
            "communication_settings_updated",
            school_id=str(school_id),
            tenant_id=str(tenant_id),
        )

        return merged

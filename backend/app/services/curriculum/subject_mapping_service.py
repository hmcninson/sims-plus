"""
SIMS Plus - Subject Curriculum Mapping Service

Business logic for managing mappings between internal subjects and
curriculum-specific codes, names, and metadata (e.g., Cambridge IGCSE
code "0580" for Mathematics, IB Higher Level flag, French coefficients).
"""

from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import GradingScale, Subject
from app.models.curriculum import CurriculumProfile, SubjectCurriculumMapping
from app.services.curriculum._shared import CurriculumServiceError

logger = structlog.get_logger()


class SubjectMappingService:
    """Service for subject-to-curriculum mapping management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Tenant FK Validation
    # =========================

    async def _validate_subject(
        self, subject_id: UUID, tenant_id: UUID
    ) -> Subject:
        """Validate a subject exists and belongs to the tenant."""
        result = await self.db.execute(
            select(Subject).where(
                Subject.id == subject_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Subject.tenant_id == tenant_id,
                Subject.deleted_at.is_(None),
            )
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise CurriculumServiceError("Subject not found", "not_found")
        return subject

    async def _validate_profile(
        self, profile_id: UUID, tenant_id: UUID
    ) -> CurriculumProfile:
        """Validate a curriculum profile exists and belongs to the tenant."""
        result = await self.db.execute(
            select(CurriculumProfile).where(
                CurriculumProfile.id == profile_id,
                # Defense-in-depth: filter by tenant_id
                CurriculumProfile.tenant_id == tenant_id,
                CurriculumProfile.deleted_at.is_(None),
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise CurriculumServiceError(
                "Curriculum profile not found", "not_found"
            )
        return profile

    async def _validate_grading_scale(
        self, scale_id: UUID, tenant_id: UUID
    ) -> GradingScale:
        """Validate a grading scale exists and belongs to the tenant."""
        result = await self.db.execute(
            select(GradingScale).where(
                GradingScale.id == scale_id,
                GradingScale.tenant_id == tenant_id,
                GradingScale.deleted_at.is_(None),
            )
        )
        scale = result.scalar_one_or_none()
        if not scale:
            raise CurriculumServiceError("Grading scale not found", "not_found")
        return scale

    # =========================
    # CRUD Methods
    # =========================

    async def create_mapping(
        self,
        data,
        tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> SubjectCurriculumMapping:
        """
        Create a subject-to-curriculum mapping.

        Validates that the subject, curriculum profile, and optional
        grading scale all belong to the same tenant.
        """
        # Validate FK references belong to the tenant
        await self._validate_subject(data.subject_id, tenant_id)
        await self._validate_profile(data.curriculum_profile_id, tenant_id)
        if data.grading_scale_id:
            await self._validate_grading_scale(data.grading_scale_id, tenant_id)

        mapping = SubjectCurriculumMapping(
            tenant_id=tenant_id,
            school_id=school_id,
            subject_id=data.subject_id,
            curriculum_profile_id=data.curriculum_profile_id,
            external_code=data.external_code,
            external_name=data.external_name,
            level=data.level,
            credits=data.credits,
            coefficient=data.coefficient,
            is_hl=data.is_hl,
            grading_scale_id=data.grading_scale_id,
            config=data.config,
        )
        self.db.add(mapping)
        await self.db.flush()
        await self.db.refresh(mapping)

        logger.info(
            "subject_curriculum_mapping_created",
            mapping_id=str(mapping.id),
            subject_id=str(data.subject_id),
            profile_id=str(data.curriculum_profile_id),
            tenant_id=str(tenant_id),
        )
        return mapping

    async def get_mappings(
        self,
        tenant_id: UUID,
        curriculum_profile_id: UUID | None = None,
        subject_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SubjectCurriculumMapping], int]:
        """List subject mappings with optional filters and pagination."""
        conditions = [
            # Defense-in-depth: always filter by tenant_id
            SubjectCurriculumMapping.tenant_id == tenant_id,
        ]

        if curriculum_profile_id is not None:
            conditions.append(
                SubjectCurriculumMapping.curriculum_profile_id == curriculum_profile_id
            )
        if subject_id is not None:
            conditions.append(
                SubjectCurriculumMapping.subject_id == subject_id
            )

        # Count total
        count_result = await self.db.execute(
            select(func.count(SubjectCurriculumMapping.id)).where(
                and_(*conditions)
            )
        )
        total = count_result.scalar_one()

        # Fetch page with eagerly loaded relationships
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(SubjectCurriculumMapping)
            .where(and_(*conditions))
            .options(
                selectinload(SubjectCurriculumMapping.subject),
                selectinload(SubjectCurriculumMapping.curriculum_profile),
            )
            .order_by(SubjectCurriculumMapping.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        mappings = list(result.scalars().all())

        return mappings, total

    async def get_mapping(
        self, mapping_id: UUID, tenant_id: UUID
    ) -> SubjectCurriculumMapping:
        """Get a single subject mapping by ID."""
        result = await self.db.execute(
            select(SubjectCurriculumMapping)
            .where(
                SubjectCurriculumMapping.id == mapping_id,
                # Defense-in-depth: filter by tenant_id
                SubjectCurriculumMapping.tenant_id == tenant_id,
            )
            .options(
                selectinload(SubjectCurriculumMapping.subject),
                selectinload(SubjectCurriculumMapping.curriculum_profile),
            )
        )
        mapping = result.scalar_one_or_none()
        if not mapping:
            raise CurriculumServiceError(
                "Subject curriculum mapping not found", "not_found"
            )
        return mapping

    async def update_mapping(
        self, mapping_id: UUID, data, tenant_id: UUID
    ) -> SubjectCurriculumMapping:
        """Update an existing subject-to-curriculum mapping."""
        mapping = await self.get_mapping(mapping_id, tenant_id)

        # Validate optional FK if grading_scale_id is being updated
        update_data = data.model_dump(exclude_unset=True)
        if "grading_scale_id" in update_data and update_data["grading_scale_id"]:
            await self._validate_grading_scale(
                update_data["grading_scale_id"], tenant_id
            )

        # Apply updates -- blocklist immutable fields to prevent mass-assignment
        _IMMUTABLE_FIELDS = {
            "id", "tenant_id", "subject_id", "curriculum_profile_id", "created_at"
        }
        for key, value in update_data.items():
            if key in _IMMUTABLE_FIELDS:
                continue
            if hasattr(mapping, key):
                setattr(mapping, key, value)

        await self.db.flush()
        await self.db.refresh(mapping)

        logger.info(
            "subject_curriculum_mapping_updated",
            mapping_id=str(mapping_id),
            tenant_id=str(tenant_id),
        )
        return mapping

    async def delete_mapping(
        self, mapping_id: UUID, tenant_id: UUID
    ) -> None:
        """
        Hard delete a subject-to-curriculum mapping.

        Mappings are configuration data, not user content,
        so they use hard delete instead of soft delete.
        """
        mapping = await self.get_mapping(mapping_id, tenant_id)
        await self.db.delete(mapping)
        await self.db.flush()

        logger.info(
            "subject_curriculum_mapping_deleted",
            mapping_id=str(mapping_id),
            tenant_id=str(tenant_id),
        )

    async def get_mappings_for_profile(
        self,
        tenant_id: UUID,
        profile_id: UUID,
    ) -> list[SubjectCurriculumMapping]:
        """
        Convenience method: get all subject mappings for a curriculum profile.

        Returns all mappings without pagination (for internal use by the
        report engine and score strategies).
        """
        # Validate profile belongs to tenant
        await self._validate_profile(profile_id, tenant_id)

        result = await self.db.execute(
            select(SubjectCurriculumMapping)
            .where(
                # Defense-in-depth: always filter by tenant_id
                SubjectCurriculumMapping.tenant_id == tenant_id,
                SubjectCurriculumMapping.curriculum_profile_id == profile_id,
            )
            .options(
                selectinload(SubjectCurriculumMapping.subject),
            )
            .order_by(SubjectCurriculumMapping.created_at)
        )
        return list(result.scalars().all())

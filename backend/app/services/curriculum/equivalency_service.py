"""
SIMS Plus - Grade Equivalency Service

Business logic for managing cross-curriculum grade mappings.
Allows converting grades between different grading scales (e.g.,
WAEC A1 -> Cambridge A*, IB 7 -> American A+).
"""

from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Grade, GradingScale
from app.models.curriculum import GradeEquivalency
from app.services.curriculum._shared import CurriculumServiceError, check_multi_curriculum_access

logger = structlog.get_logger()


class GradeEquivalencyService:
    """Service for cross-curriculum grade equivalency management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Tenant FK Validation
    # =========================

    async def _validate_grading_scale(
        self, scale_id: UUID, tenant_id: UUID
    ) -> GradingScale:
        """
        Validate a grading scale exists and belongs to the tenant.

        PostgreSQL FK constraints bypass RLS, so user-supplied UUIDs
        must be verified against the tenant boundary.
        """
        result = await self.db.execute(
            select(GradingScale).where(
                GradingScale.id == scale_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                GradingScale.tenant_id == tenant_id,
                GradingScale.deleted_at.is_(None),
            )
        )
        scale = result.scalar_one_or_none()
        if not scale:
            raise CurriculumServiceError("Grading scale not found", "not_found")
        return scale

    async def _validate_grade(
        self, grade_id: UUID, scale_id: UUID, tenant_id: UUID
    ) -> Grade:
        """Validate a grade belongs to the given scale and tenant."""
        result = await self.db.execute(
            select(Grade).where(
                Grade.id == grade_id,
                Grade.grading_scale_id == scale_id,
                # Defense-in-depth: filter by tenant_id
                Grade.tenant_id == tenant_id,
            )
        )
        grade = result.scalar_one_or_none()
        if not grade:
            raise CurriculumServiceError(
                "Grade not found in the specified grading scale", "not_found"
            )
        return grade

    # =========================
    # CRUD Methods
    # =========================

    async def create_equivalency(
        self,
        data,
        tenant_id: UUID,
        school_id: UUID | None = None,
    ) -> list[GradeEquivalency]:
        """
        Create a batch of grade equivalency mappings.

        Validates that source and target scales are different and that
        all referenced grades belong to the correct scales within the
        tenant boundary.
        """
        # Feature flag: grade equivalencies require Professional+ plan
        await check_multi_curriculum_access(self.db, tenant_id)

        # Prevent self-mapping
        if data.source_grading_scale_id == data.target_grading_scale_id:
            raise CurriculumServiceError(
                "Source and target grading scales must be different",
                "self_mapping",
            )

        # Validate both scales belong to the tenant
        await self._validate_grading_scale(data.source_grading_scale_id, tenant_id)
        await self._validate_grading_scale(data.target_grading_scale_id, tenant_id)

        created: list[GradeEquivalency] = []

        for mapping in data.mappings:
            # Validate that each grade belongs to the correct scale
            await self._validate_grade(
                mapping.source_grade_id, data.source_grading_scale_id, tenant_id
            )
            await self._validate_grade(
                mapping.target_grade_id, data.target_grading_scale_id, tenant_id
            )

            equivalency = GradeEquivalency(
                tenant_id=tenant_id,
                school_id=school_id,
                source_grading_scale_id=data.source_grading_scale_id,
                target_grading_scale_id=data.target_grading_scale_id,
                source_grade_id=mapping.source_grade_id,
                target_grade_id=mapping.target_grade_id,
                notes=mapping.notes,
            )
            self.db.add(equivalency)
            created.append(equivalency)

        await self.db.flush()
        for eq in created:
            await self.db.refresh(eq)

        logger.info(
            "grade_equivalencies_created",
            count=len(created),
            tenant_id=str(tenant_id),
            source_scale_id=str(data.source_grading_scale_id),
            target_scale_id=str(data.target_grading_scale_id),
        )
        return created

    async def get_equivalencies(
        self,
        tenant_id: UUID,
        source_scale_id: UUID | None = None,
        target_scale_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GradeEquivalency], int]:
        """List grade equivalencies with optional scale filters and pagination."""
        conditions = [
            # Defense-in-depth: always filter by tenant_id
            GradeEquivalency.tenant_id == tenant_id,
        ]

        if source_scale_id is not None:
            conditions.append(
                GradeEquivalency.source_grading_scale_id == source_scale_id
            )
        if target_scale_id is not None:
            conditions.append(
                GradeEquivalency.target_grading_scale_id == target_scale_id
            )

        # Count total
        count_result = await self.db.execute(
            select(func.count(GradeEquivalency.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        # Fetch page with eagerly loaded grade relationships
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(GradeEquivalency)
            .where(and_(*conditions))
            .options(
                selectinload(GradeEquivalency.source_grade),
                selectinload(GradeEquivalency.target_grade),
                selectinload(GradeEquivalency.source_grading_scale),
                selectinload(GradeEquivalency.target_grading_scale),
            )
            .order_by(GradeEquivalency.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        equivalencies = list(result.scalars().all())

        return equivalencies, total

    async def get_equivalency(
        self, equivalency_id: UUID, tenant_id: UUID
    ) -> GradeEquivalency:
        """Get a single grade equivalency by ID."""
        result = await self.db.execute(
            select(GradeEquivalency)
            .where(
                GradeEquivalency.id == equivalency_id,
                # Defense-in-depth: filter by tenant_id
                GradeEquivalency.tenant_id == tenant_id,
            )
            .options(
                selectinload(GradeEquivalency.source_grade),
                selectinload(GradeEquivalency.target_grade),
                selectinload(GradeEquivalency.source_grading_scale),
                selectinload(GradeEquivalency.target_grading_scale),
            )
        )
        equivalency = result.scalar_one_or_none()
        if not equivalency:
            raise CurriculumServiceError(
                "Grade equivalency not found", "not_found"
            )
        return equivalency

    async def update_equivalency(
        self, equivalency_id: UUID, data, tenant_id: UUID
    ) -> GradeEquivalency:
        """Update an existing grade equivalency (notes only)."""
        equivalency = await self.get_equivalency(equivalency_id, tenant_id)

        update_data = data.model_dump(exclude_unset=True)
        if "notes" in update_data:
            equivalency.notes = update_data["notes"]

        await self.db.flush()
        await self.db.refresh(equivalency)

        logger.info(
            "grade_equivalency_updated",
            equivalency_id=str(equivalency_id),
            tenant_id=str(tenant_id),
        )
        return equivalency

    async def delete_equivalency(
        self, equivalency_id: UUID, tenant_id: UUID
    ) -> None:
        """
        Hard delete a grade equivalency.

        Equivalencies are configuration data, not user content,
        so they use hard delete instead of soft delete.
        """
        equivalency = await self.get_equivalency(equivalency_id, tenant_id)
        await self.db.delete(equivalency)
        await self.db.flush()

        logger.info(
            "grade_equivalency_deleted",
            equivalency_id=str(equivalency_id),
            tenant_id=str(tenant_id),
        )

    async def convert_grade(
        self,
        source_grade_id: UUID,
        source_scale_id: UUID,
        target_scale_id: UUID,
        tenant_id: UUID,
    ) -> GradeEquivalency | None:
        """
        Look up the equivalent grade in a target scale.

        Returns the equivalency mapping if found, None otherwise.
        """
        # Prevent self-mapping
        if source_scale_id == target_scale_id:
            raise CurriculumServiceError(
                "Source and target grading scales must be different",
                "self_mapping",
            )

        # Validate inputs belong to tenant
        await self._validate_grading_scale(source_scale_id, tenant_id)
        await self._validate_grading_scale(target_scale_id, tenant_id)
        await self._validate_grade(source_grade_id, source_scale_id, tenant_id)

        result = await self.db.execute(
            select(GradeEquivalency)
            .where(
                # Defense-in-depth: filter by tenant_id
                GradeEquivalency.tenant_id == tenant_id,
                GradeEquivalency.source_grade_id == source_grade_id,
                GradeEquivalency.source_grading_scale_id == source_scale_id,
                GradeEquivalency.target_grading_scale_id == target_scale_id,
            )
            .options(
                selectinload(GradeEquivalency.source_grade),
                selectinload(GradeEquivalency.target_grade),
                selectinload(GradeEquivalency.source_grading_scale),
                selectinload(GradeEquivalency.target_grading_scale),
            )
        )
        return result.scalar_one_or_none()

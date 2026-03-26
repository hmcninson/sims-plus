"""
SIMS Plus - Assessment Structure Service

Business logic for managing assessment structures and their components
within curriculum profiles.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Sequence
from uuid import UUID

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicYear
from app.models.curriculum import (
    AssessmentComponent,
    AssessmentComponentType,
    AssessmentStructure,
    CurriculumProfile,
)
from app.services.curriculum._shared import CurriculumServiceError

logger = structlog.get_logger()


class AssessmentStructureService:
    """Service for assessment structure and component management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Tenant FK Validation
    # =========================

    async def _validate_tenant_fk(
        self, model_class, id: UUID, tenant_id: UUID
    ) -> None:
        """
        Validate FK target belongs to same tenant.

        PostgreSQL FK constraints bypass RLS, so a user-supplied UUID
        could reference a row in another tenant.
        """
        result = await self.db.execute(
            select(model_class.id).where(
                model_class.id == id,
                model_class.tenant_id == tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise CurriculumServiceError(
                f"{model_class.__name__} not found", "not_found"
            )

    # =========================
    # Structure Methods
    # =========================

    async def get_structure(
        self, tenant_id: UUID, structure_id: UUID
    ) -> AssessmentStructure:
        """Get a single assessment structure with components loaded."""
        result = await self.db.execute(
            select(AssessmentStructure)
            .where(
                AssessmentStructure.tenant_id == tenant_id,
                AssessmentStructure.id == structure_id,
                AssessmentStructure.deleted_at.is_(None),
            )
            .options(selectinload(AssessmentStructure.components))
        )
        structure = result.scalar_one_or_none()
        if not structure:
            raise CurriculumServiceError(
                "Assessment structure not found", "not_found"
            )
        return structure

    async def get_structure_for_profile(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        academic_year_id: UUID | None = None,
    ) -> AssessmentStructure | None:
        """
        Resolve the active assessment structure for a profile.

        Priority: year-specific > default (academic_year_id IS NULL).
        """
        # Validate profile belongs to tenant
        await self._validate_tenant_fk(CurriculumProfile, profile_id, tenant_id)

        # Validate academic year if provided
        if academic_year_id:
            await self._validate_tenant_fk(AcademicYear, academic_year_id, tenant_id)

            # Try year-specific first
            stmt = (
                select(AssessmentStructure)
                .where(
                    AssessmentStructure.tenant_id == tenant_id,
                    AssessmentStructure.curriculum_profile_id == profile_id,
                    AssessmentStructure.academic_year_id == academic_year_id,
                    AssessmentStructure.is_active == True,
                    AssessmentStructure.deleted_at.is_(None),
                )
                .options(selectinload(AssessmentStructure.components))
            )
            result = await self.db.execute(stmt)
            structure = result.scalar_one_or_none()
            if structure:
                return structure

        # Fall back to default (NULL academic_year_id)
        stmt = (
            select(AssessmentStructure)
            .where(
                AssessmentStructure.tenant_id == tenant_id,
                AssessmentStructure.curriculum_profile_id == profile_id,
                AssessmentStructure.academic_year_id.is_(None),
                AssessmentStructure.is_active == True,
                AssessmentStructure.deleted_at.is_(None),
            )
            .options(selectinload(AssessmentStructure.components))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_structure(
        self,
        tenant_id: UUID,
        school_id: UUID,
        profile_id: UUID,
        data,
    ) -> AssessmentStructure:
        """Create an assessment structure with optional components."""
        # Validate profile and optional academic year belong to tenant
        await self._validate_tenant_fk(CurriculumProfile, profile_id, tenant_id)
        if data.academic_year_id:
            await self._validate_tenant_fk(
                AcademicYear, data.academic_year_id, tenant_id
            )

        structure = AssessmentStructure(
            tenant_id=tenant_id,
            school_id=school_id,
            curriculum_profile_id=profile_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            description=data.description,
            is_active=True,
        )
        self.db.add(structure)
        await self.db.flush()
        await self.db.refresh(structure)

        # Create components if provided
        if data.components:
            for comp_data in data.components:
                component = AssessmentComponent(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    assessment_structure_id=structure.id,
                    component_type=AssessmentComponentType(comp_data.component_type),
                    name=comp_data.name,
                    weight=comp_data.weight,
                    max_score=comp_data.max_score,
                    is_external=comp_data.is_external,
                    sequence=comp_data.sequence,
                    maps_to_ca=comp_data.maps_to_ca,
                    maps_to_exam=comp_data.maps_to_exam,
                    config=comp_data.config,
                )
                self.db.add(component)
            await self.db.flush()

        # Reload with components
        return await self.get_structure(tenant_id, structure.id)

    async def update_structure(
        self,
        tenant_id: UUID,
        structure_id: UUID,
        data,
    ) -> AssessmentStructure:
        """Update assessment structure metadata (not components)."""
        structure = await self.get_structure(tenant_id, structure_id)

        # Blocklist immutable fields to prevent mass-assignment
        _IMMUTABLE_FIELDS = {"id", "tenant_id", "school_id", "created_at", "deleted_at"}
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in _IMMUTABLE_FIELDS:
                continue
            if hasattr(structure, key) and key != "components":
                setattr(structure, key, value)

        structure.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(structure)
        return structure

    async def delete_structure(
        self, tenant_id: UUID, structure_id: UUID
    ) -> None:
        """
        Soft delete an assessment structure.

        Blocks deletion if it is the only active structure for its profile.
        """
        structure = await self.get_structure(tenant_id, structure_id)

        # Check if this is the only active structure for the profile
        count_result = await self.db.execute(
            select(func.count(AssessmentStructure.id)).where(
                AssessmentStructure.tenant_id == tenant_id,
                AssessmentStructure.curriculum_profile_id == structure.curriculum_profile_id,
                AssessmentStructure.is_active == True,
                AssessmentStructure.deleted_at.is_(None),
                AssessmentStructure.id != structure_id,
            )
        )
        other_active_count = count_result.scalar_one()
        if other_active_count == 0:
            raise CurriculumServiceError(
                "Cannot delete the only assessment structure for this profile",
                "profile_in_use",
            )

        structure.deleted_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "assessment_structure_deleted",
            structure_id=str(structure_id),
            tenant_id=str(tenant_id),
        )

    # =========================
    # Component Methods
    # =========================

    async def add_component(
        self,
        tenant_id: UUID,
        structure_id: UUID,
        data,
    ) -> AssessmentComponent:
        """Add a single component to an assessment structure."""
        structure = await self.get_structure(tenant_id, structure_id)

        component = AssessmentComponent(
            tenant_id=tenant_id,
            school_id=structure.school_id,
            assessment_structure_id=structure_id,
            component_type=AssessmentComponentType(data.component_type),
            name=data.name,
            weight=data.weight,
            max_score=data.max_score,
            is_external=data.is_external,
            sequence=data.sequence,
            maps_to_ca=data.maps_to_ca,
            maps_to_exam=data.maps_to_exam,
            config=data.config,
        )
        self.db.add(component)
        await self.db.flush()
        await self.db.refresh(component)

        logger.info(
            "assessment_component_added",
            component_id=str(component.id),
            structure_id=str(structure_id),
            tenant_id=str(tenant_id),
        )
        return component

    async def update_component(
        self,
        tenant_id: UUID,
        component_id: UUID,
        data,
    ) -> AssessmentComponent:
        """Update a single assessment component."""
        result = await self.db.execute(
            select(AssessmentComponent).where(
                AssessmentComponent.tenant_id == tenant_id,
                AssessmentComponent.id == component_id,
            )
        )
        component = result.scalar_one_or_none()
        if not component:
            raise CurriculumServiceError(
                "Assessment component not found", "not_found"
            )

        # Blocklist immutable fields to prevent mass-assignment
        _IMMUTABLE_FIELDS = {"id", "tenant_id", "school_id", "created_at", "deleted_at"}
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in _IMMUTABLE_FIELDS:
                continue
            if hasattr(component, key):
                if key == "component_type" and value is not None:
                    value = AssessmentComponentType(value)
                setattr(component, key, value)

        component.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(component)
        return component

    async def delete_component(
        self, tenant_id: UUID, component_id: UUID
    ) -> None:
        """Hard delete an assessment component (junction-style entity)."""
        result = await self.db.execute(
            select(AssessmentComponent).where(
                AssessmentComponent.tenant_id == tenant_id,
                AssessmentComponent.id == component_id,
            )
        )
        component = result.scalar_one_or_none()
        if not component:
            raise CurriculumServiceError(
                "Assessment component not found", "not_found"
            )

        await self.db.delete(component)
        await self.db.flush()

        logger.info(
            "assessment_component_deleted",
            component_id=str(component_id),
            tenant_id=str(tenant_id),
        )

    async def sync_components(
        self,
        tenant_id: UUID,
        structure_id: UUID,
        components_data,
    ) -> AssessmentStructure:
        """
        Replace all components of a structure in a single transaction.

        Accepts the full desired list of components. Components with an `id`
        are treated as updates; those without are created. Any existing
        component whose id is absent from the input list is hard-deleted.

        This eliminates N individual API calls that previously triggered
        rate limiting when saving the assessment tab.
        """
        structure = await self.get_structure(tenant_id, structure_id)

        existing_by_id = {c.id: c for c in structure.components}
        incoming_ids: set[UUID] = set()

        for comp_data in components_data:
            if comp_data.id is not None:
                incoming_ids.add(comp_data.id)

        # 1. Hard-delete components that are no longer in the list
        for comp_id, comp in existing_by_id.items():
            if comp_id not in incoming_ids:
                await self.db.delete(comp)

        # 2. Update existing / create new
        for comp_data in components_data:
            if comp_data.id is not None and comp_data.id in existing_by_id:
                # Update — verify the component belongs to this structure (IDOR check)
                component = existing_by_id[comp_data.id]
                if component.assessment_structure_id != structure_id:
                    raise CurriculumServiceError(
                        "Component does not belong to this structure",
                        "not_found",
                    )
                component.component_type = AssessmentComponentType(comp_data.component_type)
                component.name = comp_data.name
                component.weight = comp_data.weight
                component.max_score = comp_data.max_score
                component.is_external = comp_data.is_external
                component.sequence = comp_data.sequence
                component.maps_to_ca = comp_data.maps_to_ca
                component.maps_to_exam = comp_data.maps_to_exam
                component.config = comp_data.config
                component.updated_at = datetime.now(UTC)
            elif comp_data.id is not None and comp_data.id not in existing_by_id:
                # Client sent an id that doesn't exist in this structure
                raise CurriculumServiceError(
                    f"Component {comp_data.id} not found in this structure",
                    "not_found",
                )
            else:
                # New component (no id)
                new_component = AssessmentComponent(
                    tenant_id=tenant_id,
                    school_id=structure.school_id,
                    assessment_structure_id=structure_id,
                    component_type=AssessmentComponentType(comp_data.component_type),
                    name=comp_data.name,
                    weight=comp_data.weight,
                    max_score=comp_data.max_score,
                    is_external=comp_data.is_external,
                    sequence=comp_data.sequence,
                    maps_to_ca=comp_data.maps_to_ca,
                    maps_to_exam=comp_data.maps_to_exam,
                    config=comp_data.config,
                )
                self.db.add(new_component)

        await self.db.flush()

        logger.info(
            "assessment_components_synced",
            structure_id=str(structure_id),
            tenant_id=str(tenant_id),
            component_count=len(components_data),
        )

        # Reload with fresh components
        return await self.get_structure(tenant_id, structure_id)

    async def validate_structure(
        self, tenant_id: UUID, structure_id: UUID
    ) -> dict:
        """
        Validate that component weights in a structure sum to exactly 100.

        Returns a dict with is_valid, total_weight, and message.
        """
        structure = await self.get_structure(tenant_id, structure_id)

        total_weight = sum(
            c.weight for c in structure.components
        ) if structure.components else Decimal("0")

        is_valid = total_weight == Decimal("100")
        if is_valid:
            message = "Component weights sum to 100%. Structure is valid."
        else:
            message = (
                f"Component weights sum to {total_weight}%. "
                f"Expected 100%. Please adjust component weights."
            )

        return {
            "is_valid": is_valid,
            "total_weight": total_weight,
            "message": message,
        }

    async def reorder_components(
        self,
        tenant_id: UUID,
        structure_id: UUID,
        component_ids: list[UUID],
    ) -> list[AssessmentComponent]:
        """Reorder components within a structure by setting sequence values."""
        structure = await self.get_structure(tenant_id, structure_id)

        # Build a lookup of existing component IDs for validation
        existing_ids = {c.id for c in structure.components}
        provided_ids = set(component_ids)

        if existing_ids != provided_ids:
            raise CurriculumServiceError(
                "Provided component IDs do not match the structure's components",
                "weight_mismatch",
            )

        # Update sequence values
        id_to_component = {c.id: c for c in structure.components}
        for seq, comp_id in enumerate(component_ids, start=1):
            id_to_component[comp_id].sequence = seq

        await self.db.flush()

        # Reload to get updated order
        reloaded = await self.get_structure(tenant_id, structure_id)
        return list(reloaded.components)

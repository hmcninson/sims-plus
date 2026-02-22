"""
SIMS Plus - Class & Section Service

Class and class section CRUD operations.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    Class,
    ClassSection,
)

from app.services.academic._shared import AcademicServiceError

logger = structlog.get_logger()


class ClassMixin:
    """Mixin providing class and section methods for AcademicService."""

    # Type hints for self.db -- set by AcademicService.__init__
    db: AsyncSession

    # =========================
    # Class Methods
    # =========================

    async def create_class(
        self,
        tenant_id: UUID,
        name: str,
        short_name: Optional[str] = None,
        level: Optional[str] = None,
        sequence: int = 1,
        capacity: Optional[int] = None,
        school_id: Optional[UUID] = None,
    ) -> Class:
        """Create a new class."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(Class).where(
                and_(
                    Class.tenant_id == tenant_id,
                    Class.name == name,
                    Class.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Class '{name}' already exists",
                code="duplicate_class",
            )

        class_ = Class(
            tenant_id=tenant_id,
            name=name,
            short_name=short_name,
            level=level,
            sequence=sequence,
            capacity=capacity,
            school_id=school_id,
            is_active=True,
        )
        self.db.add(class_)
        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            # Unique constraint violation from partial index uq_class_name_active
            logger.warning(
                "class_create_integrity_error",
                name=name,
                tenant_id=str(tenant_id),
                error=str(e.orig),
            )
            raise AcademicServiceError(
                f"Class '{name}' already exists",
                code="duplicate_class",
            ) from e
        await self.db.refresh(class_)
        return class_

    async def get_class(
        self, tenant_id: UUID, class_id: UUID, include_sections: bool = False
    ) -> Optional[Class]:
        """Get class by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(Class).where(
            and_(
                Class.tenant_id == tenant_id,
                Class.id == class_id,
                Class.deleted_at.is_(None),
            )
        )
        if include_sections:
            query = query.options(selectinload(Class.sections))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_classes(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        include_sections: bool = False,
        active_only: bool = True,
    ) -> Sequence[Class]:
        """List classes."""
        conditions = [
            Class.tenant_id == tenant_id,
            Class.deleted_at.is_(None),
        ]
        if school_id:
            conditions.append(Class.school_id == school_id)
        if active_only:
            conditions.append(Class.is_active == True)

        query = select(Class).where(and_(*conditions)).order_by(Class.sequence)

        if include_sections:
            query = query.options(selectinload(Class.sections))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_class(self, tenant_id: UUID, class_id: UUID, **kwargs) -> Optional[Class]:
        """Update a class."""
        # Defense-in-depth: tenant_id verified in get_class
        class_ = await self.get_class(tenant_id, class_id)
        if not class_:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(class_, key):
                setattr(class_, key, value)

        class_.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(class_)
        return class_

    async def delete_class(self, tenant_id: UUID, class_id: UUID) -> bool:
        """Soft delete a class."""
        # Defense-in-depth: tenant_id verified in get_class
        class_ = await self.get_class(tenant_id, class_id)
        if not class_:
            return False

        class_.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # =========================
    # Class Section Methods
    # =========================

    async def create_section(
        self,
        tenant_id: UUID,
        class_id: UUID,
        name: str,
        capacity: Optional[int] = None,
        class_teacher_id: Optional[UUID] = None,
    ) -> ClassSection:
        """Create a new class section."""
        # Verify class exists (defense-in-depth: tenant_id verified)
        class_ = await self.get_class(tenant_id, class_id)
        if not class_:
            raise AcademicServiceError("Class not found", code="class_not_found")

        # Check for duplicate name in same class
        existing = await self.db.execute(
            select(ClassSection).where(
                and_(
                    ClassSection.tenant_id == tenant_id,
                    ClassSection.class_id == class_id,
                    ClassSection.name == name,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Section '{name}' already exists in this class",
                code="duplicate_section",
            )

        section = ClassSection(
            tenant_id=tenant_id,
            class_id=class_id,
            name=name,
            capacity=capacity,
            class_teacher_id=class_teacher_id,
            is_active=True,
        )
        self.db.add(section)
        try:
            await self.db.flush()
        except IntegrityError as e:
            await self.db.rollback()
            logger.warning(
                "section_create_integrity_error",
                name=name,
                class_id=str(class_id),
                tenant_id=str(tenant_id),
                error=str(e.orig),
            )
            raise AcademicServiceError(
                f"Section '{name}' already exists in this class",
                code="duplicate_section",
            ) from e
        await self.db.refresh(section)
        return section

    async def get_section(self, tenant_id: UUID, section_id: UUID) -> Optional[ClassSection]:
        """Get section by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(ClassSection).where(
                and_(
                    ClassSection.tenant_id == tenant_id,
                    ClassSection.id == section_id,
                    ClassSection.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_sections(
        self,
        tenant_id: UUID,
        class_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> Sequence[ClassSection]:
        """List sections."""
        conditions = [
            ClassSection.tenant_id == tenant_id,
            ClassSection.deleted_at.is_(None),
        ]
        if class_id:
            conditions.append(ClassSection.class_id == class_id)
        if active_only:
            conditions.append(ClassSection.is_active == True)

        result = await self.db.execute(
            select(ClassSection)
            .where(and_(*conditions))
            .order_by(ClassSection.name)
        )
        return result.scalars().all()

    async def update_section(self, tenant_id: UUID, section_id: UUID, **kwargs) -> Optional[ClassSection]:
        """Update a section."""
        # Defense-in-depth: tenant_id verified in get_section
        section = await self.get_section(tenant_id, section_id)
        if not section:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(section, key):
                setattr(section, key, value)

        section.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(section)
        return section

    async def delete_section(self, tenant_id: UUID, section_id: UUID) -> bool:
        """Soft delete a section."""
        # Defense-in-depth: tenant_id verified in get_section
        section = await self.get_section(tenant_id, section_id)
        if not section:
            return False

        section.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

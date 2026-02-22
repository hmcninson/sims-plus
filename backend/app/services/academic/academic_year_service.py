"""
SIMS Plus - Academic Year & Term Service

Academic year and term CRUD operations.
"""

from datetime import datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import (
    AcademicYear,
    AcademicYearStatus,
    Term,
    TermStatus,
)

from app.services.academic._shared import AcademicServiceError


class AcademicYearMixin:
    """Mixin providing academic year and term methods for AcademicService."""

    # Type hints for self.db -- set by AcademicService.__init__
    db: AsyncSession

    # =========================
    # Academic Year Methods
    # =========================

    async def create_academic_year(
        self,
        tenant_id: UUID,
        name: str,
        start_date,
        end_date,
        description: Optional[str] = None,
        is_current: bool = False,
    ) -> AcademicYear:
        """Create a new academic year."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.name == name,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Academic year '{name}' already exists",
                code="duplicate_academic_year",
            )

        # If setting as current, unset other current years
        if is_current:
            await self._unset_current_academic_year(tenant_id)

        academic_year = AcademicYear(
            tenant_id=tenant_id,
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=AcademicYearStatus.PLANNING,
            is_current=is_current,
        )
        self.db.add(academic_year)
        await self.db.flush()
        await self.db.refresh(academic_year)
        return academic_year

    async def get_academic_year(
        self, tenant_id: UUID, academic_year_id: UUID, include_terms: bool = False
    ) -> Optional[AcademicYear]:
        """Get academic year by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        query = select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if include_terms:
            query = query.options(selectinload(AcademicYear.terms))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_academic_years(
        self, tenant_id: UUID, include_terms: bool = False
    ) -> Sequence[AcademicYear]:
        """List all academic years for a tenant."""
        query = select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        ).order_by(AcademicYear.start_date.desc())

        if include_terms:
            query = query.options(selectinload(AcademicYear.terms))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_academic_year(
        self, academic_year_id: UUID, tenant_id: UUID, **kwargs
    ) -> Optional[AcademicYear]:
        """Update an academic year."""
        # Defense-in-depth: tenant_id verified in get_academic_year
        academic_year = await self.get_academic_year(tenant_id, academic_year_id)
        if not academic_year:
            return None

        # Handle is_current specially
        if kwargs.get("is_current"):
            await self._unset_current_academic_year(tenant_id)

        # Handle status change
        if "status" in kwargs:
            kwargs["status"] = AcademicYearStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(academic_year, key):
                setattr(academic_year, key, value)

        academic_year.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(academic_year)
        return academic_year

    async def delete_academic_year(self, tenant_id: UUID, academic_year_id: UUID) -> bool:
        """Soft delete an academic year."""
        # Defense-in-depth: tenant_id verified in get_academic_year
        academic_year = await self.get_academic_year(tenant_id, academic_year_id)
        if not academic_year:
            return False

        academic_year.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def _unset_current_academic_year(self, tenant_id: UUID) -> None:
        """Unset current flag for all academic years in tenant."""
        result = await self.db.execute(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.is_current == True,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        for year in result.scalars().all():
            year.is_current = False

    # =========================
    # Term Methods
    # =========================

    async def create_term(
        self,
        tenant_id: UUID,
        academic_year_id: UUID,
        name: str,
        start_date,
        end_date,
        sequence: int = 1,
        short_name: Optional[str] = None,
    ) -> Term:
        """Create a new term."""
        # Verify academic year exists (defense-in-depth: tenant_id verified)
        academic_year = await self.get_academic_year(tenant_id, academic_year_id)
        if not academic_year:
            raise AcademicServiceError(
                "Academic year not found",
                code="academic_year_not_found",
            )

        # Check for duplicate name in same academic year
        existing = await self.db.execute(
            select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.academic_year_id == academic_year_id,
                    Term.name == name,
                    Term.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AcademicServiceError(
                f"Term '{name}' already exists in this academic year",
                code="duplicate_term",
            )

        term = Term(
            tenant_id=tenant_id,
            academic_year_id=academic_year_id,
            name=name,
            short_name=short_name,
            sequence=sequence,
            start_date=start_date,
            end_date=end_date,
            status=TermStatus.UPCOMING,
            is_current=False,
        )
        self.db.add(term)
        await self.db.flush()
        await self.db.refresh(term)
        return term

    async def get_term(self, tenant_id: UUID, term_id: UUID) -> Optional[Term]:
        """Get term by ID."""
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.id == term_id,
                    Term.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_terms(
        self,
        tenant_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> Sequence[Term]:
        """List terms, optionally filtered by academic year."""
        conditions = [
            Term.tenant_id == tenant_id,
            Term.deleted_at.is_(None),
        ]
        if academic_year_id:
            conditions.append(Term.academic_year_id == academic_year_id)

        result = await self.db.execute(
            select(Term)
            .where(and_(*conditions))
            .order_by(Term.start_date)
        )
        return result.scalars().all()

    async def update_term(self, term_id: UUID, tenant_id: UUID, **kwargs) -> Optional[Term]:
        """Update a term."""
        # Defense-in-depth: tenant_id verified in get_term
        term = await self.get_term(tenant_id, term_id)
        if not term:
            return None

        # Handle is_current specially
        if kwargs.get("is_current"):
            await self._unset_current_term(tenant_id)

        # Handle status change
        if "status" in kwargs:
            kwargs["status"] = TermStatus(kwargs["status"])

        for key, value in kwargs.items():
            if value is not None and hasattr(term, key):
                setattr(term, key, value)

        term.updated_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(term)
        return term

    async def delete_term(self, tenant_id: UUID, term_id: UUID) -> bool:
        """Soft delete a term."""
        # Defense-in-depth: tenant_id verified in get_term
        term = await self.get_term(tenant_id, term_id)
        if not term:
            return False

        term.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def _unset_current_term(self, tenant_id: UUID) -> None:
        """Unset current flag for all terms in tenant."""
        result = await self.db.execute(
            select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.is_current == True,
                    Term.deleted_at.is_(None),
                )
            )
        )
        for term in result.scalars().all():
            term.is_current = False

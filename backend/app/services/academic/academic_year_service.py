"""
SIMS Plus - Academic Year & Term Service

Academic year and term CRUD operations.
"""

from datetime import date, datetime, UTC
from typing import Optional, Sequence
from uuid import UUID

import structlog
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
from app.services.academic.guards import assert_year_editable

logger = structlog.get_logger()


class AcademicYearMixin:
    """Mixin providing academic year and term methods for AcademicService."""

    # Type hints for self.db -- set by AcademicService.__init__
    db: AsyncSession

    # =========================
    # Academic Year Methods
    # =========================

    async def _validate_no_date_overlap(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
        school_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        """
        Ensure no other non-archived academic year has overlapping dates.

        Two date ranges [A_start, A_end] and [B_start, B_end] overlap if:
            A_start <= B_end AND A_end >= B_start

        Archived years are excluded — they represent historical data that
        should not block new year creation.

        Args:
            tenant_id: Tenant UUID for defense-in-depth filtering
            start_date: Proposed start date
            end_date: Proposed end date
            school_id: Optional school UUID (for chain tenants, scopes check to one school)
            exclude_id: Academic year ID to exclude (for updates — don't overlap with self)

        Raises:
            AcademicServiceError: If overlap detected (code=DATE_OVERLAP)
        """
        query = select(AcademicYear).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
                # Archived years don't conflict — they're historical
                AcademicYear.status != AcademicYearStatus.ARCHIVED,
                # Overlap condition: ranges overlap iff each starts before the other ends
                AcademicYear.start_date <= end_date,
                AcademicYear.end_date >= start_date,
            )
        )

        # For chain tenants, scope overlap check to the same school
        if school_id:
            query = query.where(AcademicYear.school_id == school_id)

        # Exclude the year being updated so it doesn't conflict with itself
        if exclude_id:
            query = query.where(AcademicYear.id != exclude_id)

        # M10: Use scalars().first(), NOT scalar_one_or_none() —
        # scalar_one_or_none() crashes if multiple overlapping years exist
        result = await self.db.execute(query)
        overlapping = result.scalars().first()

        if overlapping:
            raise AcademicServiceError(
                f"Date range ({start_date} to {end_date}) overlaps with "
                f"'{overlapping.name}' ({overlapping.start_date} to {overlapping.end_date}). "
                f"Academic years cannot have overlapping date ranges.",
                code="DATE_OVERLAP",
            )

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

        # Validate date ordering
        if start_date >= end_date:
            raise AcademicServiceError(
                "Start date must be before end date.",
                code="INVALID_DATES",
            )

        # Prevent overlapping date ranges with other non-archived years
        await self._validate_no_date_overlap(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
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

        # Block field edits on completed/archived years.
        # Status transitions (e.g. completed->archived) are handled by
        # dedicated endpoints, so we only guard non-status field changes.
        non_status_changes = {k: v for k, v in kwargs.items() if k != "status"}
        if non_status_changes and academic_year.status in (
            AcademicYearStatus.COMPLETED,
            AcademicYearStatus.ARCHIVED,
        ):
            raise AcademicServiceError(
                f"Cannot modify a {academic_year.status.value} academic year. "
                "Completed and archived years are read-only.",
                code="READ_ONLY_YEAR",
            )

        # If dates are being changed, validate ordering and overlap
        new_start = kwargs.get("start_date", academic_year.start_date)
        new_end = kwargs.get("end_date", academic_year.end_date)

        if new_start != academic_year.start_date or new_end != academic_year.end_date:
            if new_start >= new_end:
                raise AcademicServiceError(
                    "Start date must be before end date.",
                    code="INVALID_DATES",
                )

            # Prevent overlapping date ranges (exclude self so we don't conflict with our own dates)
            await self._validate_no_date_overlap(
                tenant_id=tenant_id,
                start_date=new_start,
                end_date=new_end,
                school_id=academic_year.school_id,
                exclude_id=academic_year_id,
            )

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
        # Guard: cannot delete completed/archived years
        await assert_year_editable(self.db, tenant_id, academic_year_id)

        # Defense-in-depth: tenant_id verified in get_academic_year
        academic_year = await self.get_academic_year(tenant_id, academic_year_id)
        if not academic_year:
            return False

        academic_year.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def archive_academic_year(
        self, tenant_id: UUID, academic_year_id: UUID
    ) -> AcademicYear:
        """
        Transition an academic year from 'completed' to 'archived'.

        Validates:
        - Year exists and belongs to tenant
        - Status is 'completed' (only completed years can be archived)
        - is_current is False (cannot archive the active year)
        - All terms within the year are 'completed'
        """
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        year = await self.db.scalar(
            select(AcademicYear).where(
                and_(
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.id == academic_year_id,
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )

        if not year:
            raise AcademicServiceError("Academic year not found", code="NOT_FOUND")

        if year.status != AcademicYearStatus.COMPLETED:
            raise AcademicServiceError(
                "Only completed academic years can be archived. "
                f"Current status: {year.status.value}",
                code="INVALID_STATUS",
            )

        if year.is_current:
            raise AcademicServiceError(
                "Cannot archive the current academic year. "
                "Set another year as current first.",
                code="IS_CURRENT",
            )

        # Verify all terms in this year are completed
        terms = await self.db.scalars(
            select(Term).where(
                and_(
                    Term.tenant_id == tenant_id,
                    Term.academic_year_id == academic_year_id,
                    Term.deleted_at.is_(None),
                )
            )
        )
        incomplete_terms = [
            t for t in terms.all()
            if t.status != TermStatus.COMPLETED
        ]
        if incomplete_terms:
            names = ", ".join(t.name for t in incomplete_terms)
            raise AcademicServiceError(
                f"All terms must be completed before archiving. "
                f"Incomplete: {names}",
                code="INCOMPLETE_TERMS",
            )

        year.status = AcademicYearStatus.ARCHIVED
        await self.db.flush()
        await self.db.refresh(year)

        logger.info(
            "academic_year_archived",
            tenant_id=str(tenant_id),
            academic_year_id=str(academic_year_id),
            year_name=year.name,
        )

        return year

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
        # Guard: cannot add terms to completed/archived years
        await assert_year_editable(self.db, tenant_id, academic_year_id)

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

        # Guard: cannot modify terms in completed/archived years
        await assert_year_editable(self.db, tenant_id, term.academic_year_id)

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

        # Guard: cannot delete terms in completed/archived years
        await assert_year_editable(self.db, tenant_id, term.academic_year_id)

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

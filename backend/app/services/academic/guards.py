"""
SIMS Plus - Academic Year Guard Checks

Shared utility to enforce read-only status on completed/archived academic years.
Used by academic, exam, and other services that modify data within an academic year.
"""

from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic.year_models import AcademicYear, AcademicYearStatus, Term


class ReadOnlyYearError(Exception):
    """Raised when attempting to modify data in a completed or archived academic year."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def assert_year_editable(
    db: AsyncSession,
    tenant_id: UUID,
    academic_year_id: UUID,
) -> None:
    """
    Raise ReadOnlyYearError if the academic year is completed or archived.

    Use this before any write operation that modifies data within an
    academic year (terms, exams, scores, attendance, etc.).
    Defense-in-depth: filters by tenant_id even though RLS handles isolation.
    """
    status = await db.scalar(
        select(AcademicYear.status).where(
            and_(
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.id == academic_year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
    )

    if status in (AcademicYearStatus.COMPLETED, AcademicYearStatus.ARCHIVED):
        raise ReadOnlyYearError(
            f"Cannot modify data in a {status.value} academic year. "
            "Completed and archived years are read-only."
        )


async def assert_term_year_editable(
    db: AsyncSession,
    tenant_id: UUID,
    term_id: UUID,
) -> None:
    """
    Look up a term's academic year and check if it's editable.

    Convenience wrapper: pass a term_id and it resolves the parent year.
    The variable is named academic_year_id (not term) because the scalar
    query returns a UUID, not a Term object (M11 review finding).
    """
    # Resolve the term's parent academic year
    academic_year_id = await db.scalar(
        select(Term.academic_year_id).where(
            and_(
                Term.tenant_id == tenant_id,
                Term.id == term_id,
                Term.deleted_at.is_(None),
            )
        )
    )

    if academic_year_id:
        await assert_year_editable(db, tenant_id, academic_year_id)

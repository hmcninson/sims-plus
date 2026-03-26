"""
SIMS Plus - Enrollment Target Models

Per-class enrollment targets for capacity planning dashboards.
Allows schools to set target enrollment counts per class per academic year,
with optional boarding/day breakdowns.

Table:
  - enrollment_targets: One active target per class per academic year
    (enforced by partial unique index WHERE deleted_at IS NULL)
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear, Class
    from app.models.school import School


class EnrollmentTarget(Base, TenantMixin, SoftDeleteMixin):
    """
    Enrollment Target model.

    Per-class enrollment target for a given academic year, used to power
    capacity planning dashboards and enrollment progress tracking.

    One active target per (academic_year, class) combination, enforced
    by a partial unique index WHERE deleted_at IS NULL.
    """

    __tablename__ = "enrollment_targets"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total enrollment target for this class",
    )
    boarding_target: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Boarding places target (null if not applicable)",
    )
    day_target: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Day student target (null if not applicable)",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    class_: Mapped["Class"] = relationship(lazy="raise")

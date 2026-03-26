"""
SIMS Plus - Admission Decision Model
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import DecisionType
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.admissions.application import Application
    from app.models.tenant import User


class AdmissionDecision(Base, TenantMixin, SoftDeleteMixin):
    """
    Admission Decision model.

    Records the formal admission decision for an application.
    One decision per application (enforced by unique constraint).
    """

    __tablename__ = "admission_decisions"

    __table_args__ = (
        UniqueConstraint("tenant_id", "application_id", name="uq_decisions_tenant_application"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="One decision per application",
    )
    decision_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="accepted, rejected, waitlisted, deferred",
    )
    decided_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    offered_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="SET NULL"),
        nullable=True,
        comment="May differ from application's target_class_id",
    )
    conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Conditional offer terms",
    )
    decision_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    response_deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Deadline for applicant to accept the offer",
    )
    decision_letter_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Generated PDF letter S3 URL",
    )
    interview_score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        default=None,
        comment="Persisted interview score for decision audit",
    )
    screening_score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        default=None,
        comment="Composite screening checklist score",
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Structured reason for rejection letter",
    )
    rejection_letter_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Generated rejection letter PDF S3 URL",
    )
    waitlist_rank: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Priority ranking on waitlist (1 = highest priority)",
    )
    waitlist_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes for waitlist ordering decisions",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="decision",
        lazy="raise",
    )
    decided_by_user: Mapped["User"] = relationship(lazy="raise")
    offered_class: Mapped["Class | None"] = relationship(lazy="raise")

"""
SIMS Plus - Enrollment Checklist Models

Per-application enrollment checklist that tracks completion of all
required pre-enrollment steps (documents, payments, forms, medical, boarding).

Tables:
  - enrollment_checklists: One checklist per application
  - enrollment_checklist_items: Individual tasks within a checklist
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.admissions.application import Application
    from app.models.tenant import User


class EnrollmentChecklist(Base, TenantMixin, SoftDeleteMixin):
    """
    Enrollment Checklist model.

    Tracks the overall completion state of pre-enrollment requirements
    for a single application. One active checklist per application
    (enforced by partial unique index WHERE deleted_at IS NULL).
    """

    __tablename__ = "enrollment_checklists"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="One checklist per application (partial unique index)",
    )
    checklist_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        server_default="standard",
        comment="ChecklistType enum value: standard, boarding",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when all required items are completed",
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff who marked the final required item",
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        back_populates="enrollment_checklist",
        lazy="raise",
    )
    items: Mapped[list["EnrollmentChecklistItem"]] = relationship(
        back_populates="checklist",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    completed_by_user: Mapped["User | None"] = relationship(
        lazy="raise",
        foreign_keys=[completed_by],
    )


class EnrollmentChecklistItem(Base, TenantMixin, SoftDeleteMixin):
    """
    Enrollment Checklist Item model.

    Individual tasks within an enrollment checklist. Each item represents
    a requirement the school or parent must complete before enrollment
    (e.g., submit birth certificate, pay deposit, complete medical form).
    """

    __tablename__ = "enrollment_checklist_items"

    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enrollment_checklists.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="ChecklistItemType enum value: document, payment, form, boarding, medical",
    )
    item_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable description of the checklist item",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extended instructions for completing this item",
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Required items block enrollment completion",
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff who verified completion",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes from staff",
    )
    # REVIEW FIX E4: Named item_metadata (not metadata) to avoid
    # SQLAlchemy Declarative API collision with Model.metadata
    item_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Flexible data: document_url, payment_ref, etc.",
    )

    # Relationships
    checklist: Mapped["EnrollmentChecklist"] = relationship(
        back_populates="items",
        lazy="raise",
    )
    completed_by_user: Mapped["User | None"] = relationship(
        lazy="raise",
        foreign_keys=[completed_by],
    )

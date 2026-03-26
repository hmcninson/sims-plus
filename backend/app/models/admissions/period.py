"""
SIMS Plus - Admission Period Models

AdmissionPeriod: Intake windows for applications.
AdmissionFormConfig: Custom form field definitions per period.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.admissions.enums import AdmissionPeriodStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.admissions.application import Application
    from app.models.admissions.exam import EntranceExam
    from app.models.school import School


class AdmissionPeriod(Base, TenantMixin, SoftDeleteMixin):
    """
    Admission Period model.

    Represents an intake window (e.g., "2026/2027 Admissions for Form 1").
    Controls when applications are accepted, fee requirements, and target classes.
    """

    __tablename__ = "admission_periods"

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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Period name, e.g., '2026/2027 Admissions'",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Applications open date",
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Applications close date",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AdmissionPeriodStatus.DRAFT.value,
        server_default="draft",
        comment="draft, open, closed, archived",
    )
    application_fee_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Fee amount in tenant currency (null = free)",
    )
    application_fee_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    entrance_exam_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    max_applications: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of applications (null = unlimited)",
    )
    target_classes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of class UUIDs this period accepts applications for",
    )

    # Reminder configuration (Enrollment Gap Closure Phase 2)
    reminder_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Enable auto-reminders for incomplete applications before close date",
    )
    reminder_days_before_close: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Days before end_date to send reminder to applicants with DRAFT status",
    )

    # Applicant account requirement toggle
    require_applicant_account: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, applicants must register/login before submitting",
    )

    # Enrollment confirmation config (Phase 3)
    enrollment_deposit_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether enrollment deposit is required before enrollment",
    )
    enrollment_deposit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Required deposit amount (null if not required)",
    )
    # REVIEW FIX D10/B6: list type, not dict -- template is a JSON array
    enrollment_checklist_template: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Template items auto-populated when checklist is created",
    )

    # Relationships
    school: Mapped["School"] = relationship(lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship(lazy="raise")
    form_config: Mapped["AdmissionFormConfig | None"] = relationship(
        back_populates="admission_period",
        lazy="raise",
        uselist=False,
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="admission_period",
        lazy="raise",
    )
    entrance_exams: Mapped[list["EntranceExam"]] = relationship(
        back_populates="admission_period",
        lazy="raise",
    )


class AdmissionFormConfig(Base, TenantMixin, SoftDeleteMixin):
    """
    Admission Form Configuration model.

    Stores JSON Schema for custom form fields per admission period.
    Schools use this to add fields like "Previous School", "Medical Info", etc.
    """

    __tablename__ = "admission_form_configs"

    __table_args__ = (
        UniqueConstraint("tenant_id", "admission_period_id", name="uq_form_configs_tenant_period"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    admission_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admission_periods.id", ondelete="CASCADE"),
        nullable=False,
        comment="One form config per period",
    )
    form_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="JSON Schema defining custom form fields",
    )
    required_documents: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Array of required document types, e.g., ['birth_certificate', 'passport_photo']",
    )

    # Relationships
    admission_period: Mapped["AdmissionPeriod"] = relationship(
        back_populates="form_config",
        lazy="raise",
    )

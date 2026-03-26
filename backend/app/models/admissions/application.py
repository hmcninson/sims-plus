"""
SIMS Plus - Application Models

Core application record and related tables:
Application, ApplicationGuardian, ApplicationDocument,
ApplicationPayment, ApplicationStatusHistory, ApplicationNote.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.models.admissions.enums import AdmissionApplicationStatus
from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import Class
    from app.models.admissions.decision import AdmissionDecision
    from app.models.admissions.enrollment_checklist import EnrollmentChecklist
    from app.models.admissions.exam import (
        EntranceExamRegistration,
        EntranceExamResult,
    )
    from app.models.admissions.inquiry import Inquiry
    from app.models.admissions.interview import Interview, ScreeningChecklist
    from app.models.admissions.period import AdmissionPeriod
    from app.models.school import School
    from app.models.student import Student
    from app.models.tenant import User


class Application(Base, TenantMixin, SoftDeleteMixin):
    """
    Application model -- the central entity of the admissions module.

    Tracks a prospective student's application from submission through
    enrollment. The tracking_code is the public identifier; the UUID id
    is used internally.
    """

    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint("tenant_id", "tracking_code", name="uq_applications_tenant_tracking"),
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
    )
    tracking_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Public identifier -- secrets.token_urlsafe(48), 384-bit entropy",
    )
    applicant_first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    applicant_last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    applicant_other_names: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    gender: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="male or female",
    )
    nationality: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    target_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,
        comment="Class the applicant is applying to",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AdmissionApplicationStatus.DRAFT.value,
        server_default="draft",
    )
    custom_fields: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Dynamic fields validated against form_schema",
    )
    fee_waived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, application fee payment is not required",
    )
    exam_waived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, entrance exam is not required",
    )
    converted_student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set on enrollment -- serves as idempotency guard",
    )

    # Inquiry conversion link (null for direct applications)
    inquiry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inquiries.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="Links to the inquiry that was converted to this application",
    )

    # Applicant account link (null for anonymous applications)
    applicant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Owning applicant account (null for anonymous submissions)",
    )

    applicant_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    previous_school: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    medical_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when moved from draft to submitted",
    )
    offer_responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When applicant accepted/declined the offer",
    )
    offer_response: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="OfferResponse enum value: accepted, declined",
    )
    offer_response_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Applicant's notes on their offer response",
    )

    # Enrollment confirmation fields (Phase 3)
    enrollment_deposit_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether enrollment deposit has been received",
    )
    enrollment_deposit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Deposit amount in tenant currency",
    )
    enrollment_deposit_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Payment reference (receipt number, bank ref, etc.)",
    )
    enrollment_deposit_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the enrollment deposit was paid",
    )
    boarding_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="boarding or day -- set during enrollment confirmation",
    )
    enrollment_confirmation_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 URL for generated enrollment confirmation PDF",
    )
    welcome_pack_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether welcome/orientation info has been sent",
    )
    welcome_pack_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the welcome pack was sent",
    )

    # Relationships
    school: Mapped["School"] = sa_relationship(lazy="raise")
    admission_period: Mapped["AdmissionPeriod"] = sa_relationship(
        back_populates="applications",
        lazy="raise",
    )
    # target_class_id is nullable (applicant may not have chosen a class yet
    # at draft stage), so the relationship must also be Optional
    target_class: Mapped["Class | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[target_class_id],
    )
    converted_student: Mapped["Student | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[converted_student_id],
    )

    # Applicant account relationship
    applicant_user: Mapped["User | None"] = sa_relationship(
        lazy="raise",
        foreign_keys=[applicant_user_id],
    )

    guardians: Mapped[list["ApplicationGuardian"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["ApplicationDocument"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["ApplicationPayment"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list["ApplicationStatusHistory"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list["ApplicationNote"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    decision: Mapped["AdmissionDecision | None"] = sa_relationship(
        back_populates="application",
        lazy="raise",
        uselist=False,
    )
    exam_registrations: Mapped[list["EntranceExamRegistration"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
    )
    exam_results: Mapped[list["EntranceExamResult"]] = sa_relationship(
        back_populates="application",
        lazy="raise",
    )
    inquiry: Mapped["Inquiry | None"] = sa_relationship(
        "Inquiry",
        foreign_keys=[inquiry_id],
        lazy="raise",
    )
    interview: Mapped["Interview | None"] = sa_relationship(
        lazy="raise",
        uselist=False,
    )
    screening_items: Mapped[list["ScreeningChecklist"]] = sa_relationship(
        lazy="raise",
    )
    enrollment_checklist: Mapped["EnrollmentChecklist | None"] = sa_relationship(
        "EnrollmentChecklist",
        back_populates="application",
        lazy="raise",
        uselist=False,
    )


class ApplicationGuardian(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Guardian model.

    Stores guardian/parent info as submitted with the application.
    These are NOT the same as Guardian records -- conversion happens
    during enrollment with deduplication.
    """

    __tablename__ = "application_guardians"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Primary contact phone",
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="father, mother, guardian, other",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Primary contact for this application",
    )
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    application: Mapped["Application"] = sa_relationship(
        back_populates="guardians",
        lazy="raise",
    )


class ApplicationDocument(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Document model.

    Stores metadata for uploaded files (actual files live in S3).
    S3 key format: admissions/{tenant_id}/{application_id}/{uuid}.{ext}
    """

    __tablename__ = "application_documents"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="birth_certificate, passport_photo, transcript, medical_report, etc.",
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original uploaded filename",
    )
    s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="S3 object key: admissions/{tenant_id}/{app_id}/{uuid}.{ext}",
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes (max 5MB = 5242880)",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="application/pdf, image/jpeg, image/png",
    )

    # Relationships
    application: Mapped["Application"] = sa_relationship(
        back_populates="documents",
        lazy="raise",
    )


class ApplicationPayment(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Payment model.

    Tracks application fee payments via Paystack.
    Separate from the main payments table since applicants are not students yet.
    """

    __tablename__ = "application_payments"

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_reference", name="uq_payments_tenant_reference"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="GHS",
        server_default="GHS",
    )
    payment_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="mobile_money, card, bank_transfer",
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Paystack transaction reference",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="pending, completed, failed, refunded",
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payment_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Provider-specific response data",
    )

    # Relationships
    application: Mapped["Application"] = sa_relationship(
        back_populates="payments",
        lazy="raise",
    )


class ApplicationStatusHistory(Base, TenantMixin):
    """
    Application Status History model.

    Append-only audit log of all status transitions.
    No SoftDeleteMixin -- audit records are never deleted.
    No updated_at -- records are immutable.
    """

    __tablename__ = "application_status_history"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="NULL for initial creation",
    )
    to_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL for public actions (e.g., applicant submission)",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why the status was changed",
    )

    # Relationships
    application: Mapped["Application"] = sa_relationship(
        back_populates="status_history",
        lazy="raise",
    )
    changed_by_user: Mapped["User | None"] = sa_relationship(lazy="raise")


class ApplicationNote(Base, TenantMixin, SoftDeleteMixin):
    """
    Application Note model.

    Internal reviewer notes on applications. Not shown to applicants.
    """

    __tablename__ = "application_notes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="If true, only visible to admin (not applicant)",
    )

    # Relationships
    application: Mapped["Application"] = sa_relationship(
        back_populates="notes",
        lazy="raise",
    )
    author: Mapped["User"] = sa_relationship(lazy="raise")

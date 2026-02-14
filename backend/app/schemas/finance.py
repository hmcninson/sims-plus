"""
SIMS Plus - Finance Schemas

Pydantic schemas for finance endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Fee Type Schemas
# =========================


class FeeTypeCreate(BaseSchema):
    """Create fee type request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = Field(None, pattern="^(tuition|examination|facilities|activities|other)$")
    is_active: bool = True


class FeeTypeUpdate(BaseSchema):
    """Update fee type request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = Field(None, pattern="^(tuition|examination|facilities|activities|other)$")
    is_active: Optional[bool] = None


class FeeTypeResponse(BaseSchema):
    """Fee type response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FeeTypeListResponse(BaseSchema):
    """Paginated fee type list."""

    items: list[FeeTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Fee Structure Schemas
# =========================


class FeeItemCreate(BaseSchema):
    """Create fee item request."""

    fee_type_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    amount: Decimal = Field(..., ge=0)
    is_optional: bool = False
    sequence: int = Field(default=0, ge=0)


class FeeItemUpdate(BaseSchema):
    """Update fee item request."""

    fee_type_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    is_optional: Optional[bool] = None
    sequence: Optional[int] = Field(None, ge=0)


class FeeItemResponse(BaseSchema):
    """Fee item response."""

    id: UUID
    tenant_id: UUID
    fee_structure_id: UUID
    fee_type_id: Optional[UUID] = None
    fee_type_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    amount: Decimal
    is_optional: bool
    sequence: int
    created_at: datetime
    updated_at: datetime


class FeeStructureCreate(BaseSchema):
    """Create fee structure request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    academic_year_id: Optional[UUID] = None
    term_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    level: Optional[str] = Field(None, max_length=20)
    level_category: Optional[str] = Field(None, max_length=20, pattern="^(preschool|primary|jhs|shs)$")
    student_type: str = Field(default="all", pattern="^(all|boarding|day)$")
    is_active: bool = True
    items: list[FeeItemCreate] = Field(default_factory=list)


class FeeItemUpdateInStructure(BaseSchema):
    """Fee item update within fee structure update."""

    id: Optional[UUID] = None  # If provided, update existing; if not, create new
    fee_type_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    amount: Decimal = Field(..., ge=0)
    is_optional: bool = False
    sequence: int = Field(default=0, ge=0)


class FeeStructureUpdate(BaseSchema):
    """Update fee structure request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    academic_year_id: Optional[UUID] = None
    term_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    level: Optional[str] = Field(None, max_length=20)
    level_category: Optional[str] = Field(None, max_length=20, pattern="^(preschool|primary|jhs|shs)$")
    student_type: Optional[str] = Field(None, pattern="^(all|boarding|day)$")
    is_active: Optional[bool] = None
    items: Optional[list[FeeItemUpdateInStructure]] = None  # If provided, sync items


class FeeStructureResponse(BaseSchema):
    """Fee structure response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    name: str
    description: Optional[str] = None
    academic_year_id: Optional[UUID] = None
    term_id: Optional[UUID] = None
    class_id: Optional[UUID] = None
    level: Optional[str] = None
    level_category: Optional[str] = None
    student_type: str = "all"
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FeeStructureWithItemsResponse(FeeStructureResponse):
    """Fee structure with items."""

    items: list[FeeItemResponse] = []
    total_amount: Decimal = Decimal("0.00")
    academic_year_name: Optional[str] = None
    term_name: Optional[str] = None
    class_name: Optional[str] = None


class FeeStructureListResponse(BaseSchema):
    """Paginated fee structure list."""

    items: list[FeeStructureWithItemsResponse]
    total: int
    page: int
    page_size: int
    pages: int


class FeeStructureCopy(BaseSchema):
    """Copy fee structure request."""

    new_name: str = Field(..., min_length=1, max_length=100)
    new_academic_year_id: Optional[UUID] = None
    new_term_id: Optional[UUID] = None


# =========================
# Invoice Schemas
# =========================


class InvoiceItemCreate(BaseSchema):
    """Create invoice item request."""

    fee_item_id: Optional[UUID] = None
    description: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(..., ge=0)


class InvoiceItemResponse(BaseSchema):
    """Invoice item response."""

    id: UUID
    tenant_id: UUID
    invoice_id: UUID
    fee_item_id: Optional[UUID] = None
    description: str
    quantity: int
    unit_price: Decimal
    amount: Decimal
    created_at: datetime


class InvoiceScholarshipItemResponse(BaseSchema):
    """Invoice scholarship item response - tracks scholarship discounts on invoices."""

    id: UUID
    tenant_id: UUID
    invoice_id: UUID
    student_scholarship_id: Optional[UUID] = None
    scholarship_id: Optional[UUID] = None
    scholarship_name: str
    scholarship_code: Optional[str] = None
    coverage_type: str
    coverage_value: Decimal
    calculated_amount: Decimal
    applicable_subtotal: Decimal
    created_at: datetime


class InvoiceCreate(BaseSchema):
    """Create invoice request."""

    student_id: UUID
    fee_structure_id: Optional[UUID] = None
    academic_year_id: UUID
    term_id: UUID
    due_date: Optional[date] = None
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: Optional[str] = None
    items: list[InvoiceItemCreate] = Field(default_factory=list)


class InvoiceUpdate(BaseSchema):
    """Update invoice request (only for draft invoices)."""

    due_date: Optional[date] = None
    discount_amount: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class InvoiceResponse(BaseSchema):
    """Invoice response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    invoice_number: str
    student_id: UUID
    fee_structure_id: Optional[UUID] = None
    academic_year_id: UUID
    term_id: UUID
    subtotal: Decimal
    discount_amount: Decimal
    scholarship_discount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    status: str
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: str
    notes: Optional[str] = None
    # Adjustment tracking
    adjustment_for_invoice_id: Optional[UUID] = None
    adjustment_type: Optional[str] = None
    adjustment_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InvoiceWithDetailsResponse(InvoiceResponse):
    """Invoice with student and item details."""

    student_name: str
    student_id_number: str
    class_name: Optional[str] = None
    academic_year_name: str
    term_name: str
    items: list[InvoiceItemResponse] = []
    scholarship_items: list[InvoiceScholarshipItemResponse] = []
    payments: list["PaymentResponse"] = []


class InvoiceListResponse(BaseSchema):
    """Paginated invoice list."""

    items: list[InvoiceWithDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int


class InvoiceBulkGenerate(BaseSchema):
    """Bulk generate invoices request."""

    fee_structure_id: UUID
    academic_year_id: UUID
    term_id: UUID
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    due_date: Optional[date] = None
    student_ids: Optional[list[UUID]] = Field(None, description="Specific students to invoice; if None, all enrolled students")
    issue_immediately: bool = Field(default=False, description="If True, invoices are issued immediately instead of created as draft")


class InvoiceBulkResult(BaseSchema):
    """Result of bulk invoice generation."""

    created: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = []
    invoice_ids: list[UUID] = []

    @property
    def success_count(self) -> int:
        """Alias for created (frontend compatibility)."""
        return self.created

    @property
    def failed_count(self) -> int:
        """Alias for failed (frontend compatibility)."""
        return self.failed

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        # Include computed properties in serialization
        json_schema_extra={"properties": {"success_count": {"type": "integer"}, "failed_count": {"type": "integer"}}}
    )


class InvoiceSyncRequest(BaseSchema):
    """Request to sync invoices with fee structure."""

    fee_structure_id: UUID
    academic_year_id: UUID
    term_id: UUID


class InvoiceSyncPreview(BaseSchema):
    """Preview of invoice sync operation."""

    draft_count: int = Field(..., description="Number of draft invoices that can be synced")
    issued_count: int = Field(..., description="Number of issued invoices (cannot be synced)")
    partial_count: int = Field(..., description="Number of partially paid invoices (cannot be synced)")
    paid_count: int = Field(..., description="Number of paid invoices (cannot be synced)")
    total_invoices: int = Field(..., description="Total invoices for this fee structure/term")
    can_sync_count: int = Field(..., description="Total invoices that can be synced")
    cannot_sync_count: int = Field(..., description="Total invoices that cannot be synced")
    new_fee_structure_total: float = Field(..., description="Current fee structure total amount")


class InvoiceSyncSkippedReasons(BaseSchema):
    """Reasons why invoices were skipped during sync."""

    issued: int = 0
    partial: int = 0
    paid: int = 0


class InvoiceSyncResult(BaseSchema):
    """Result of invoice sync operation."""

    updated: int = Field(0, description="Number of invoices updated")
    skipped: int = Field(0, description="Number of invoices skipped (non-draft)")
    failed: int = Field(0, description="Number of invoices that failed to update")
    errors: list[str] = Field(default_factory=list)
    skipped_reasons: InvoiceSyncSkippedReasons = Field(default_factory=InvoiceSyncSkippedReasons)


class InvoiceIssue(BaseSchema):
    """Issue invoice request."""

    issue_date: Optional[date] = None


class InvoiceCancel(BaseSchema):
    """Cancel invoice request."""

    reason: str = Field(..., min_length=1, max_length=500)


class InvoiceWriteOff(BaseSchema):
    """Write off invoice request."""

    reason: str = Field(..., min_length=1, max_length=500, description="Reason for writing off the invoice")


# =========================
# Payment Schemas
# =========================


class PaymentCreate(BaseSchema):
    """Record payment request."""

    invoice_id: Optional[UUID] = None
    student_id: UUID
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., pattern="^(cash|momo_mtn|momo_vodafone|momo_airteltigo|bank_transfer|cheque|card|other)$")
    payment_date: Optional[datetime] = None
    payer_name: Optional[str] = Field(None, max_length=100)
    payer_phone: Optional[str] = Field(None, max_length=20)
    payer_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    # MoMo details
    momo_phone: Optional[str] = Field(None, max_length=20)
    momo_transaction_id: Optional[str] = Field(None, max_length=100)
    # Bank details
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_reference: Optional[str] = Field(None, max_length=100)
    cheque_number: Optional[str] = Field(None, max_length=50)


class PaymentResponse(BaseSchema):
    """Payment response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    receipt_number: str
    invoice_id: Optional[UUID] = None
    student_id: UUID
    amount: Decimal
    currency: str
    payment_method: str
    momo_phone: Optional[str] = None
    momo_transaction_id: Optional[str] = None
    momo_provider: Optional[str] = None
    bank_name: Optional[str] = None
    bank_reference: Optional[str] = None
    cheque_number: Optional[str] = None
    payer_name: Optional[str] = None
    payer_phone: Optional[str] = None
    payer_email: Optional[str] = None
    status: str
    payment_date: datetime
    notes: Optional[str] = None
    is_voided: bool
    created_at: datetime
    updated_at: datetime


class PaymentWithDetailsResponse(PaymentResponse):
    """Payment with student and invoice details."""

    student_name: str
    student_id_number: str
    invoice_number: Optional[str] = None
    recorded_by_name: Optional[str] = None


class PaymentListResponse(BaseSchema):
    """Paginated payment list."""

    items: list[PaymentWithDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PaymentVoid(BaseSchema):
    """Void payment request."""

    reason: str = Field(..., min_length=1, max_length=500)


class MoMoInitiate(BaseSchema):
    """Initiate Mobile Money payment request."""

    invoice_id: UUID
    phone_number: str = Field(..., min_length=10, max_length=20)
    provider: str = Field(..., pattern="^(mtn|vodafone|airteltigo)$")
    amount: Optional[Decimal] = Field(None, gt=0, description="Amount to pay; if None, pays full invoice balance")


class MoMoCallback(BaseSchema):
    """Mobile Money callback from provider."""

    transaction_id: str
    status: str
    provider: str
    phone_number: str
    amount: Decimal
    reference: str
    metadata: Optional[dict] = None


# =========================
# Scholarship Schemas
# =========================


class ScholarshipCreate(BaseSchema):
    """Create scholarship request."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    scholarship_type: str = Field(..., pattern="^(full|partial|merit|need_based|athletic|special)$")
    coverage_type: str = Field(..., pattern="^(percentage|fixed_amount)$")
    coverage_value: Decimal = Field(..., ge=0)
    applicable_fees: Optional[list[str]] = Field(None, description='Fee item names to cover: ["tuition", "all"]')
    max_recipients: Optional[int] = Field(None, ge=1)
    academic_year_id: Optional[UUID] = None
    eligibility_criteria: Optional[dict] = None
    is_active: bool = True

    @field_validator("coverage_value")
    @classmethod
    def validate_coverage(cls, v: Decimal, info) -> Decimal:
        coverage_type = info.data.get("coverage_type")
        if coverage_type == "percentage" and v > 100:
            raise ValueError("Percentage coverage cannot exceed 100")
        return v


class ScholarshipUpdate(BaseSchema):
    """Update scholarship request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    scholarship_type: Optional[str] = Field(None, pattern="^(full|partial|merit|need_based|athletic|special)$")
    coverage_type: Optional[str] = Field(None, pattern="^(percentage|fixed_amount)$")
    coverage_value: Optional[Decimal] = Field(None, ge=0)
    applicable_fees: Optional[list[str]] = None
    max_recipients: Optional[int] = Field(None, ge=1)
    academic_year_id: Optional[UUID] = None
    eligibility_criteria: Optional[dict] = None
    is_active: Optional[bool] = None


class ScholarshipResponse(BaseSchema):
    """Scholarship response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    name: str
    code: str
    description: Optional[str] = None
    scholarship_type: str
    coverage_type: str
    coverage_value: Decimal
    applicable_fees: Optional[list[str]] = None
    max_recipients: Optional[int] = None
    academic_year_id: Optional[UUID] = None
    eligibility_criteria: Optional[dict] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScholarshipWithStatsResponse(ScholarshipResponse):
    """Scholarship with recipient stats."""

    recipients_count: int = 0
    active_recipients_count: int = 0
    academic_year_name: Optional[str] = None
    total_discount_given: Decimal = Decimal("0.00")


class ScholarshipListResponse(BaseSchema):
    """Paginated scholarship list."""

    items: list[ScholarshipWithStatsResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Student Scholarship Schemas
# =========================


class ScholarshipAward(BaseSchema):
    """Award scholarship to student request."""

    student_id: UUID
    effective_from: date
    effective_to: Optional[date] = None
    coverage_override: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    # Enhanced award settings
    justification: Optional[str] = Field(None, max_length=1000, description="Reason/justification for awarding (recommended)")
    renewal_type: str = Field(default="one_time", pattern="^(one_time|annual|until_graduation)$")
    is_provisional: bool = Field(default=False, description="Whether this is a provisional/conditional award")
    provisional_conditions: Optional[str] = Field(None, max_length=500, description="Conditions for provisional awards")
    # Reinstatement (for re-awarding after revocation)
    reinstated_from: Optional[UUID] = Field(None, description="ID of previously revoked StudentScholarship to reinstate")


class ScholarshipBulkAward(BaseSchema):
    """Award scholarship to multiple students."""

    student_ids: list[UUID] = Field(..., min_length=1)
    effective_from: date
    effective_to: Optional[date] = None
    coverage_override: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    # Enhanced award settings
    justification: Optional[str] = Field(None, max_length=1000, description="Reason/justification for awarding (recommended)")
    renewal_type: str = Field(default="one_time", pattern="^(one_time|annual|until_graduation)$")
    is_provisional: bool = Field(default=False, description="Whether this is a provisional/conditional award")
    provisional_conditions: Optional[str] = Field(None, max_length=500, description="Conditions for provisional awards")
    # Note: reinstated_from is not supported in bulk award - use individual award for reinstatements


class ScholarshipBulkAwardResult(BaseSchema):
    """Result of bulk scholarship award."""

    awarded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = []
    student_scholarship_ids: list[UUID] = []

    @property
    def success_count(self) -> int:
        return self.awarded

    @property
    def failed_count(self) -> int:
        return self.failed


class ScholarshipRevoke(BaseSchema):
    """Revoke scholarship request."""

    reason: str = Field(..., min_length=1, max_length=500)


class StudentScholarshipResponse(BaseSchema):
    """Student scholarship response."""

    id: UUID
    tenant_id: UUID
    scholarship_id: UUID
    student_id: UUID
    academic_year_id: UUID
    awarded_by: Optional[UUID] = None
    awarded_at: datetime
    status: str
    effective_from: date
    effective_to: Optional[date] = None
    coverage_override: Optional[Decimal] = None
    notes: Optional[str] = None
    # Enhanced award settings
    justification: Optional[str] = None
    renewal_type: str = "one_time"
    is_provisional: bool = False
    provisional_conditions: Optional[str] = None
    # Revocation info
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[UUID] = None
    revoke_reason: Optional[str] = None
    # Reinstatement tracking
    reinstated_from: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class StudentScholarshipWithDetailsResponse(StudentScholarshipResponse):
    """Student scholarship with related details."""

    scholarship_name: str
    scholarship_code: str
    scholarship_type: str
    coverage_type: str
    coverage_value: Decimal
    student_name: str
    student_id_number: str
    academic_year_name: str
    awarded_by_name: Optional[str] = None


class StudentScholarshipListResponse(BaseSchema):
    """Paginated student scholarship list."""

    items: list[StudentScholarshipWithDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Scholarship Application Schemas
# =========================


class ApplicationDocument(BaseSchema):
    """Supporting document for application."""

    name: str
    url: str
    type: Optional[str] = None


class ScholarshipApplicationCreate(BaseSchema):
    """Submit scholarship application request."""

    scholarship_id: UUID
    academic_year_id: UUID
    supporting_documents: Optional[list[ApplicationDocument]] = None
    application_notes: Optional[str] = None


class ScholarshipApplicationReview(BaseSchema):
    """Review scholarship application request."""

    reviewer_notes: Optional[str] = None


class ScholarshipApplicationResponse(BaseSchema):
    """Scholarship application response."""

    id: UUID
    tenant_id: UUID
    scholarship_id: UUID
    student_id: UUID
    academic_year_id: UUID
    applied_at: datetime
    status: str
    supporting_documents: Optional[list[dict]] = None
    application_notes: Optional[str] = None
    reviewer_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScholarshipApplicationWithDetailsResponse(ScholarshipApplicationResponse):
    """Application with scholarship and student details."""

    scholarship_name: str
    scholarship_code: str
    student_name: str
    student_id_number: str
    academic_year_name: str
    reviewer_name: Optional[str] = None


class ScholarshipApplicationListResponse(BaseSchema):
    """Paginated application list."""

    items: list[ScholarshipApplicationWithDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Dashboard/Analytics Schemas
# =========================


class FinanceDashboardStats(BaseSchema):
    """Finance dashboard statistics."""

    expected_revenue: Decimal = Decimal("0.00")
    collected_revenue: Decimal = Decimal("0.00")
    outstanding_balance: Decimal = Decimal("0.00")
    total_invoices: int = 0
    paid_invoices: int = 0
    partial_invoices: int = 0
    overdue_invoices: int = 0
    total_payments: int = 0
    total_scholarships_value: Decimal = Decimal("0.00")
    scholarship_recipients: int = 0


class RecentPayment(BaseSchema):
    """Recent payment for dashboard."""

    id: UUID
    receipt_number: str
    student_name: str
    amount: Decimal
    payment_method: str
    payment_date: datetime


class OutstandingByClass(BaseSchema):
    """Outstanding balance by class."""

    class_id: UUID
    class_name: str
    student_count: int
    total_outstanding: Decimal


class FinanceDashboardResponse(BaseSchema):
    """Complete finance dashboard response."""

    stats: FinanceDashboardStats
    recent_payments: list[RecentPayment]
    outstanding_by_class: list[OutstandingByClass]


class PaymentReceiptResponse(BaseSchema):
    """Payment receipt data for printing."""

    school_name: str
    school_address: Optional[str] = None
    school_phone: Optional[str] = None
    school_email: Optional[str] = None
    school_logo_url: Optional[str] = None
    receipt_number: str
    payment_date: datetime
    student_name: str
    student_id_number: str
    class_name: Optional[str] = None
    amount: Decimal
    amount_in_words: str
    currency: str
    payment_method: str
    payer_name: Optional[str] = None
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    recorded_by_name: Optional[str] = None


# =========================
# Invoice Email Schemas
# =========================


class InvoiceEmailRequest(BaseSchema):
    """Request to send invoice via email."""

    email: str = Field(..., description="Recipient email address")
    recipient_name: Optional[str] = Field(None, description="Recipient name (defaults to guardian name)")
    cc_emails: Optional[list[str]] = Field(None, description="CC email addresses")


class InvoiceEmailResponse(BaseSchema):
    """Response after sending invoice email."""

    success: bool
    message: str
    email: str


# =========================
# Missing Invoice Schemas
# =========================


class StudentMissingInvoice(BaseSchema):
    """Student who is missing an invoice."""

    id: UUID
    student_id: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    class_id: Optional[UUID] = None
    class_name: Optional[str] = None
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"


class StudentsMissingInvoicesResponse(BaseSchema):
    """Response for students missing invoices."""

    students: list[StudentMissingInvoice]
    total: int
    fee_structure_name: str
    academic_year_name: str
    term_name: str


# =========================
# Finance Audit Log Schemas
# =========================


class FinanceAuditLogResponse(BaseSchema):
    """Finance audit log entry response."""

    id: UUID
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[dict] = None
    performed_by: UUID
    performed_by_name: Optional[str] = None
    performed_at: datetime
    ip_address: Optional[str] = None


class FinanceAuditLogListResponse(BaseSchema):
    """Paginated finance audit log list."""

    items: list[FinanceAuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Credit Note Schemas
# =========================


class CreditNoteCreate(BaseSchema):
    """Create credit note request."""

    credit_note_type: str = Field(
        ...,
        pattern="^(overpayment|fee_reduction|error_correction|scholarship_adjustment|other)$",
    )
    student_id: UUID
    original_invoice_id: Optional[UUID] = None
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="GHS", max_length=3)
    reason: str = Field(..., min_length=1, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)


class CreditNoteUpdate(BaseSchema):
    """Update credit note request (only draft notes can be updated)."""

    credit_note_type: Optional[str] = Field(
        None,
        pattern="^(overpayment|fee_reduction|error_correction|scholarship_adjustment|other)$",
    )
    amount: Optional[Decimal] = Field(None, gt=0)
    reason: Optional[str] = Field(None, min_length=1, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)


class CreditNoteIssue(BaseSchema):
    """Issue credit note request."""

    pass  # No additional fields needed, just the action


class CreditNoteApply(BaseSchema):
    """Apply credit note to an invoice."""

    invoice_id: UUID
    amount: Optional[Decimal] = Field(None, gt=0, description="Amount to apply (defaults to full credit)")


class CreditNoteRefund(BaseSchema):
    """Refund credit note to student/guardian."""

    refund_method: str = Field(
        ...,
        pattern="^(cash|momo_mtn|momo_vodafone|momo_airteltigo|bank_transfer|cheque|other)$",
    )
    refund_reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class CreditNoteCancel(BaseSchema):
    """Cancel credit note request."""

    reason: str = Field(..., min_length=1, max_length=500)


class CreditNoteResponse(BaseSchema):
    """Credit note response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    credit_note_number: str
    credit_note_type: str
    original_invoice_id: Optional[UUID] = None
    student_id: UUID
    amount: Decimal
    currency: str
    reason: str
    status: str
    issued_by: Optional[UUID] = None
    issued_at: Optional[datetime] = None
    applied_to_invoice_id: Optional[UUID] = None
    applied_amount: Optional[Decimal] = None
    applied_by: Optional[UUID] = None
    applied_at: Optional[datetime] = None
    refund_method: Optional[str] = None
    refund_reference: Optional[str] = None
    refunded_by: Optional[UUID] = None
    refunded_at: Optional[datetime] = None
    cancelled_by: Optional[UUID] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    notes: Optional[str] = None
    remaining_amount: Decimal
    created_at: datetime
    updated_at: datetime


class CreditNoteWithDetailsResponse(CreditNoteResponse):
    """Credit note with related details."""

    student_name: str
    student_id_number: str
    original_invoice_number: Optional[str] = None
    applied_to_invoice_number: Optional[str] = None
    issued_by_name: Optional[str] = None
    applied_by_name: Optional[str] = None
    refunded_by_name: Optional[str] = None


class CreditNoteListResponse(BaseSchema):
    """Paginated credit note list."""

    items: list[CreditNoteWithDetailsResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StudentCreditBalance(BaseSchema):
    """Student's available credit balance."""

    student_id: UUID
    student_name: str
    student_id_number: str
    total_credits: Decimal
    applied_credits: Decimal
    refunded_credits: Decimal
    available_balance: Decimal
    pending_credits: int  # Count of draft credit notes

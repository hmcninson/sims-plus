"""
SIMS Plus - Finance Models Package

Re-exports all finance model classes and enums for backward compatibility.
All external code can continue to use:
    from app.models.finance import Invoice, Payment, ...
"""

# Fee models
from .fee_models import FeeType, FeeTypeCategory, FeeStructure, FeeItem

# Invoice models
from .invoice_models import (
    Invoice,
    InvoiceItem,
    InvoiceScholarshipItem,
    InvoiceStatus,
    INVOICE_STATUS_TRANSITIONS,
    is_valid_invoice_transition,
    get_valid_next_statuses,
)

# Payment models
from .payment_models import Payment, PaymentMethod, PaymentStatus

# Scholarship models
from .scholarship_models import (
    Scholarship,
    ScholarshipType,
    CoverageType,
    StudentScholarship,
    ScholarshipStatus,
    ScholarshipApplication,
    ApplicationStatus,
    RenewalType,
)

# Credit note models
from .credit_note_models import CreditNote, CreditNoteStatus, CreditNoteType

# Audit models
from .audit_models import FinanceAuditLog, FinanceAuditAction

__all__ = [
    # Fee models
    "FeeType",
    "FeeTypeCategory",
    "FeeStructure",
    "FeeItem",
    # Invoice models
    "Invoice",
    "InvoiceItem",
    "InvoiceScholarshipItem",
    "InvoiceStatus",
    "INVOICE_STATUS_TRANSITIONS",
    "is_valid_invoice_transition",
    "get_valid_next_statuses",
    # Payment models
    "Payment",
    "PaymentMethod",
    "PaymentStatus",
    # Scholarship models
    "Scholarship",
    "ScholarshipType",
    "CoverageType",
    "StudentScholarship",
    "ScholarshipStatus",
    "ScholarshipApplication",
    "ApplicationStatus",
    "RenewalType",
    # Credit note models
    "CreditNote",
    "CreditNoteStatus",
    "CreditNoteType",
    # Audit models
    "FinanceAuditLog",
    "FinanceAuditAction",
]

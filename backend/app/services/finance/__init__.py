"""
SIMS Plus - Finance Services Package

Re-exports all service classes for backward compatibility.
Existing imports like `from app.services.finance import InvoiceService` continue to work.
"""

from app.services.finance._shared import (
    FinanceServiceError,
    ScholarshipDiscountDetail,
    ScholarshipDiscountResult,
)
from app.services.finance.fee_type_service import FeeTypeService
from app.services.finance.fee_structure_service import FeeStructureService
from app.services.finance.invoice_service import InvoiceService
from app.services.finance.payment_service import PaymentService
from app.services.finance.scholarship_service import ScholarshipService
from app.services.finance.dashboard_service import FinanceDashboardService
from app.services.finance.audit_service import FinanceAuditService
from app.services.finance.credit_note_service import CreditNoteService
from app.services.finance.reports import FinanceReportService, FinanceReportError
from app.services.finance.sibling_service import SiblingService

__all__ = [
    "FinanceServiceError",
    "ScholarshipDiscountDetail",
    "ScholarshipDiscountResult",
    "FeeTypeService",
    "FeeStructureService",
    "InvoiceService",
    "PaymentService",
    "ScholarshipService",
    "FinanceDashboardService",
    "FinanceAuditService",
    "CreditNoteService",
    "FinanceReportService",
    "FinanceReportError",
    "SiblingService",
]

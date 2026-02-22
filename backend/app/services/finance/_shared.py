"""
SIMS Plus - Finance Shared Classes

Shared error class and helper data classes used across multiple finance service modules.
"""

from decimal import Decimal
from uuid import UUID


class FinanceServiceError(Exception):
    """Base exception for finance service errors."""

    def __init__(self, message: str, code: str = "finance_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ScholarshipDiscountDetail:
    """Details of a scholarship discount applied to an invoice."""

    def __init__(
        self,
        student_scholarship_id: UUID,
        scholarship_id: UUID,
        scholarship_name: str,
        scholarship_code: str,
        coverage_type: str,
        coverage_value: Decimal,
        applicable_subtotal: Decimal,
        calculated_amount: Decimal,
    ):
        self.student_scholarship_id = student_scholarship_id
        self.scholarship_id = scholarship_id
        self.scholarship_name = scholarship_name
        self.scholarship_code = scholarship_code
        self.coverage_type = coverage_type
        self.coverage_value = coverage_value
        self.applicable_subtotal = applicable_subtotal
        self.calculated_amount = calculated_amount


class ScholarshipDiscountResult:
    """Result of scholarship discount calculation."""

    def __init__(self, total_discount: Decimal, details: list[ScholarshipDiscountDetail]):
        self.total_discount = total_discount
        self.details = details

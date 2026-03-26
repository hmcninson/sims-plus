"""
SIMS Plus - Payroll Services Package

Re-exports all payroll service classes.
"""

from app.services.payroll.audit_service import PayrollAuditService
from app.services.payroll.bank_file_service import BankFileService
from app.services.payroll.calculation_service import (
    calculate_paye,
    calculate_ssnit,
    calculate_staff_payroll,
    validate_bracket_contiguity,
)
from app.services.payroll.config_service import PayrollConfigService
from app.services.payroll.loan_calculation_service import (
    calculate_flat_rate_loan,
    calculate_reducing_balance_loan,
)
from app.services.payroll.loan_service import LoanService
from app.services.payroll.loan_statement_service import LoanStatementService
from app.services.payroll.payslip_service import PayslipService
from app.services.payroll.report_service import PayrollReportService
from app.services.payroll.run_service import PayrollRunService
from app.services.payroll.salary_service import SalaryService

__all__ = [
    "BankFileService",
    "LoanService",
    "LoanStatementService",
    "PayrollAuditService",
    "PayrollConfigService",
    "PayrollReportService",
    "PayrollRunService",
    "PayslipService",
    "SalaryService",
    "calculate_flat_rate_loan",
    "calculate_paye",
    "calculate_reducing_balance_loan",
    "calculate_ssnit",
    "calculate_staff_payroll",
    "validate_bracket_contiguity",
]

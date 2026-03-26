"""
SIMS Plus - Loan Statement PDF Service

Generates A4 loan statement PDFs using WeasyPrint + Jinja2, uploads to S3,
and returns presigned download URLs.

All queries filter by tenant_id (defense-in-depth on top of RLS).
"""

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.payroll import LoanInstallment, StaffLoan
from app.models.school import School
from app.services.s3 import get_s3_service

logger = structlog.get_logger()

# Templates directory (same as PayslipService)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "reports"

# Presigned URL expiry for statement downloads (5 minutes)
_PRESIGNED_EXPIRY_SECONDS = 300


class LoanStatementService:
    """Service for generating loan statement PDFs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def generate_statement(
        self,
        tenant_id: UUID,
        loan_id: UUID,
    ) -> dict:
        """
        Generate a loan statement PDF and upload to S3.

        Returns {url: presigned_url, loan_number: str, generated_at: date}.
        """
        # Fetch loan with staff, loan_type, and installments
        loan_result = await self.db.execute(
            select(StaffLoan)
            .options(
                selectinload(StaffLoan.staff),
                selectinload(StaffLoan.loan_type),
                selectinload(StaffLoan.installments),
            )
            .where(StaffLoan.id == loan_id)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.deleted_at.is_(None))
        )
        loan = loan_result.scalar_one_or_none()
        if not loan:
            raise self.Error("Loan not found", 404)

        if loan.status.value == "draft":
            raise self.Error("Cannot generate statement for a draft loan", 400)

        # Fetch school for branding
        school: Optional[School] = None
        if loan.school_id:
            school_result = await self.db.execute(
                select(School)
                .where(School.id == loan.school_id)
                .where(School.tenant_id == tenant_id)
            )
            school = school_result.scalar_one_or_none()

        # Build template context
        staff = loan.staff
        staff_name = f"{staff.first_name} {staff.last_name}"
        staff_code = staff.staff_id

        # Sort installments by number
        installments = sorted(loan.installments, key=lambda i: i.installment_number)

        context = {
            "loan": loan,
            "loan_number": loan.loan_number,
            "status": loan.status.value.upper().replace("_", " "),
            "staff_name": staff_name,
            "staff_code": staff_code,
            "loan_type_name": loan.loan_type.name if loan.loan_type else "N/A",
            "principal_amount": loan.principal_amount,
            "interest_rate": loan.interest_rate,
            "interest_method": (
                loan.interest_method.value.replace("_", " ").title()
                if hasattr(loan.interest_method, "value")
                else str(loan.interest_method).replace("_", " ").title()
            ),
            "tenure_months": loan.tenure_months,
            "total_interest": loan.total_interest,
            "total_repayable": loan.total_repayable,
            "monthly_installment": loan.monthly_installment,
            "total_paid": loan.total_paid,
            "outstanding_balance": loan.outstanding_balance,
            "application_date": loan.application_date,
            "disbursement_date": loan.disbursement_date,
            "installments": installments,
            "generated_date": date.today(),
            "school": school,
        }

        # Render HTML from template
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template("loan_statement.html")
        html_content = template.render(**context)

        # Generate PDF
        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)

        # Upload to S3
        s3 = get_s3_service()
        s3_key = f"loan-statements/{tenant_id}/{loan.loan_number}.pdf"
        await s3.upload_fileobj(
            pdf_buffer,
            s3_key,
            content_type="application/pdf",
        )

        # Generate presigned URL for download
        url = await s3.generate_presigned_url(s3_key, expiry=_PRESIGNED_EXPIRY_SECONDS)

        logger.info(
            "loan_statement_generated",
            loan_id=str(loan_id),
            loan_number=loan.loan_number,
            tenant_id=str(tenant_id),
        )

        return {
            "url": url,
            "loan_number": loan.loan_number,
            "generated_at": date.today(),
        }

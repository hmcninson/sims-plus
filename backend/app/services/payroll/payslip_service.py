"""
SIMS Plus - Payslip PDF Generation Service

Generates individual payslip PDFs using WeasyPrint + Jinja2, uploads to S3,
and returns presigned download URLs. Calculates YTD totals from prior
payroll items in the same calendar year.

SECURITY:
- Account numbers masked in template (last 4 digits only)
- Payslips stored in private S3 path, accessed via presigned URL (5-min expiry)
- All queries filter by tenant_id (defense-in-depth on top of RLS)
"""

import calendar
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.payroll import PayrollItem, PayrollRun, PayrollRunStatus
from app.models.school import School
from app.services.s3 import get_s3_service

logger = structlog.get_logger()

# Templates directory (same as PDFService)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "reports"

# Presigned URL expiry for payslip downloads (5 minutes per spec Section 9.3)
_PRESIGNED_EXPIRY_SECONDS = 300


def _mask_account_number(account_number: Optional[str]) -> str:
    """Mask account number, showing only last 4 digits: ****5678."""
    if not account_number:
        return "N/A"
    if len(account_number) <= 4:
        return "****"
    return "****" + account_number[-4:]


class PayslipService:
    """Service for generating payslip PDFs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def generate_payslip_pdf(
        self,
        tenant_id: UUID,
        run_id: UUID,
        staff_id: UUID,
    ) -> dict:
        """
        Generate a payslip PDF for one staff member in a payroll run.

        Fetches the PayrollItem with earnings/deductions, calculates YTD,
        renders the HTML template, converts to PDF with WeasyPrint, uploads
        to S3, and returns a presigned download URL.

        Returns:
            dict with download_url, staff_name, staff_code, month, year,
            and expires_in_seconds.
        """
        # Fetch the payroll run (validates tenant ownership)
        run = await self._get_run(tenant_id, run_id)

        # Only calculated, approved, or paid runs can produce payslips
        allowed_statuses = {
            PayrollRunStatus.CALCULATED,
            PayrollRunStatus.PENDING_APPROVAL,
            PayrollRunStatus.APPROVED,
            PayrollRunStatus.PAID,
        }
        if run.status not in allowed_statuses:
            raise self.Error(
                f"Cannot generate payslip: run is in '{run.status.value}' status. "
                f"The run must be at least calculated.",
                409,
            )

        # Fetch the payroll item with earnings and deductions
        item = await self._get_item(tenant_id, run_id, staff_id)

        # Fetch school branding
        school = await self._get_school(tenant_id, run.school_id)

        # Calculate YTD totals for same staff in same calendar year
        ytd = await self._calculate_ytd(tenant_id, staff_id, run.year, run.month)

        # Render HTML
        html_content = self._render_payslip_html(item, school, run, ytd)

        # Generate PDF
        pdf_bytes = HTML(string=html_content).write_pdf()

        # Upload to S3
        month_str = f"{run.month:02d}"
        s3_key = (
            f"tenants/{tenant_id}/payroll/{run.year}/{month_str}"
            f"/payslips/{item.staff_code}.pdf"
        )

        s3_service = get_s3_service()
        s3_service.upload_file(
            file_content=pdf_bytes,
            key=s3_key,
            content_type="application/pdf",
        )

        # Generate presigned URL for secure download
        download_url = s3_service.generate_presigned_url(
            key=s3_key,
            expires_in=_PRESIGNED_EXPIRY_SECONDS,
        )

        logger.info(
            "payslip_generated",
            run_id=str(run_id),
            staff_id=str(staff_id),
            staff_code=item.staff_code,
            s3_key=s3_key,
            tenant_id=str(tenant_id),
        )

        return {
            "download_url": download_url,
            "staff_name": item.staff_name,
            "staff_code": item.staff_code,
            "month": run.month,
            "year": run.year,
            "expires_in_seconds": _PRESIGNED_EXPIRY_SECONDS,
        }

    def _render_payslip_html(
        self,
        item: PayrollItem,
        school: Optional[School],
        run: PayrollRun,
        ytd: dict,
    ) -> str:
        """
        Render the Jinja2 payslip template to HTML.

        Passes all payslip data including earnings breakdown, deductions,
        employer contributions, and YTD totals.
        """
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template("payslip.html")

        month_name = calendar.month_name[run.month]

        # Separate employee deductions from employer contributions
        employee_deductions = []
        employer_contributions = []
        for d in item.deductions:
            if d.is_employer_portion:
                employer_contributions.append(d)
            else:
                employee_deductions.append(d)

        context = {
            # School branding
            "school_name": school.name if school else "School",
            "school_logo_url": getattr(school, "logo_url", None) if school else None,
            "primary_color": getattr(school, "primary_color", "#1B4F72") if school else "#1B4F72",
            # Pay period
            "month_name": month_name,
            "year": run.year,
            "currency": run.currency,
            # Staff details
            "staff_name": item.staff_name,
            "staff_code": item.staff_code,
            "department_name": item.department_name or "N/A",
            "salary_grade_name": item.salary_grade_name or "N/A",
            "tin_number": item.tin_number or "N/A",
            "ssnit_number": item.ssnit_number or "N/A",
            "bank_name": item.bank_name or "N/A",
            "bank_branch": item.bank_branch or "",
            # Account number masked for security
            "account_number_masked": _mask_account_number(item.account_number),
            "payment_method": item.payment_method or "N/A",
            # Earnings
            "basic_salary": item.basic_salary,
            "earnings": item.earnings,
            "total_allowances": item.total_allowances,
            "gross_salary": item.gross_salary,
            # Deductions (employee portion only)
            "ssnit_employee": item.ssnit_employee,
            "paye_tax": item.paye_tax,
            "employee_deductions": employee_deductions,
            "total_deductions": item.total_deductions,
            "net_salary": item.net_salary,
            # Employer contributions (informational, not deducted)
            "ssnit_employer": item.ssnit_employer,
            "tier2_employer": item.tier2_employer,
            "employer_contributions": employer_contributions,
            # YTD totals
            "ytd_gross": ytd.get("gross", Decimal("0.00")),
            "ytd_tax": ytd.get("tax", Decimal("0.00")),
            "ytd_ssnit": ytd.get("ssnit", Decimal("0.00")),
            "ytd_net": ytd.get("net", Decimal("0.00")),
        }

        return template.render(**context)

    async def _get_run(self, tenant_id: UUID, run_id: UUID) -> PayrollRun:
        """Fetch payroll run, validating tenant ownership."""
        result = await self.db.execute(
            select(PayrollRun)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollRun.tenant_id == tenant_id)
            .where(PayrollRun.id == run_id)
            .where(PayrollRun.deleted_at.is_(None))
        )
        run = result.scalar_one_or_none()
        if not run:
            raise self.Error("Payroll run not found", 404)
        return run

    async def _get_item(
        self, tenant_id: UUID, run_id: UUID, staff_id: UUID
    ) -> PayrollItem:
        """Fetch payroll item with earnings and deductions eagerly loaded."""
        result = await self.db.execute(
            select(PayrollItem)
            .options(
                selectinload(PayrollItem.earnings),
                selectinload(PayrollItem.deductions),
            )
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollItem.tenant_id == tenant_id)
            # IDOR check: item must belong to the specified run
            .where(PayrollItem.payroll_run_id == run_id)
            .where(PayrollItem.staff_id == staff_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise self.Error(
                "Payroll item not found for this staff member in this run", 404
            )
        return item

    async def _get_school(
        self, tenant_id: UUID, school_id: Optional[UUID]
    ) -> Optional[School]:
        """Fetch school branding data. Returns None if no school_id."""
        if not school_id:
            # For single-school tenants, try to fetch the first active school
            result = await self.db.execute(
                select(School)
                .where(School.tenant_id == tenant_id)
                .where(School.deleted_at.is_(None))
                .where(School.is_active.is_(True))
                .limit(1)
            )
            return result.scalar_one_or_none()

        result = await self.db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.id == school_id)
            .where(School.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def _calculate_ytd(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        year: int,
        up_to_month: int,
    ) -> dict:
        """
        Calculate year-to-date totals for a staff member.

        Sums all PayrollItems for the same staff in the same calendar year,
        from approved or paid runs, up to and including the specified month.
        """
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(PayrollItem.gross_salary), 0).label("gross"),
                func.coalesce(func.sum(PayrollItem.paye_tax), 0).label("tax"),
                func.coalesce(func.sum(PayrollItem.ssnit_employee), 0).label("ssnit"),
                func.coalesce(func.sum(PayrollItem.net_salary), 0).label("net"),
            )
            .join(
                PayrollRun,
                and_(
                    PayrollRun.id == PayrollItem.payroll_run_id,
                    PayrollRun.tenant_id == tenant_id,
                ),
            )
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItem.staff_id == staff_id)
            .where(PayrollRun.year == year)
            .where(PayrollRun.month <= up_to_month)
            .where(PayrollRun.deleted_at.is_(None))
            # Only include runs that have been at least calculated
            .where(
                PayrollRun.status.in_([
                    PayrollRunStatus.CALCULATED,
                    PayrollRunStatus.PENDING_APPROVAL,
                    PayrollRunStatus.APPROVED,
                    PayrollRunStatus.PAID,
                ])
            )
        )
        row = result.one()

        return {
            "gross": Decimal(str(row.gross)),
            "tax": Decimal(str(row.tax)),
            "ssnit": Decimal(str(row.ssnit)),
            "net": Decimal(str(row.net)),
        }

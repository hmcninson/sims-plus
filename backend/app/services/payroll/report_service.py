"""
SIMS Plus - Payroll Report Service

Generates statutory reports (SSNIT returns, PAYE returns), department
summaries, monthly summaries, and year-to-date breakdowns. Supports
Excel export via openpyxl.

All queries filter by tenant_id (defense-in-depth on top of RLS).
Uses flush()/refresh() — the endpoint middleware handles commit.
"""

import calendar
from decimal import Decimal
from io import BytesIO
from typing import Optional
from uuid import UUID

import structlog
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, numbers
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import PayrollItem, PayrollRun, PayrollRunStatus

logger = structlog.get_logger()

# Only runs in these statuses contribute to reports
_REPORTABLE_STATUSES = (
    PayrollRunStatus.CALCULATED,
    PayrollRunStatus.PENDING_APPROVAL,
    PayrollRunStatus.APPROVED,
    PayrollRunStatus.PAID,
)


class PayrollReportService:
    """Service for payroll reporting and statutory returns."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    # ==================================================================
    # Monthly Summary
    # ==================================================================

    async def get_monthly_summary(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Generate a monthly payroll summary with department and payment
        method breakdowns.
        """
        # Base join condition for PayrollItem -> PayrollRun
        base_conditions = [
            PayrollRun.id == PayrollItem.payroll_run_id,
            PayrollRun.tenant_id == tenant_id,
            PayrollRun.year == year,
            PayrollRun.month == month,
            PayrollRun.deleted_at.is_(None),
            PayrollRun.status.in_(_REPORTABLE_STATUSES),
            PayrollItem.tenant_id == tenant_id,
        ]
        if school_id:
            base_conditions.append(PayrollRun.school_id == school_id)

        # Overall totals
        totals_result = await self.db.execute(
            select(
                func.count(PayrollItem.id).label("staff_count"),
                func.coalesce(func.sum(PayrollItem.basic_salary), 0).label("total_basic"),
                func.coalesce(func.sum(PayrollItem.total_allowances), 0).label("total_allowances"),
                func.coalesce(func.sum(PayrollItem.gross_salary), 0).label("total_gross"),
                func.coalesce(func.sum(PayrollItem.paye_tax), 0).label("total_paye"),
                func.coalesce(func.sum(PayrollItem.ssnit_employee), 0).label("total_ssnit_ee"),
                func.coalesce(func.sum(PayrollItem.ssnit_employer), 0).label("total_ssnit_er"),
                func.coalesce(func.sum(PayrollItem.tier2_employer), 0).label("total_tier2_er"),
                func.coalesce(func.sum(PayrollItem.tier3_employee), 0).label("total_tier3"),
                func.coalesce(func.sum(PayrollItem.total_deductions), 0).label("total_other_deductions"),
                func.coalesce(func.sum(PayrollItem.net_salary), 0).label("total_net"),
            )
            .join(PayrollRun, and_(*base_conditions))
        )
        row = totals_result.one()

        total_gross = Decimal(str(row.total_gross))
        total_ssnit_er = Decimal(str(row.total_ssnit_er))
        total_tier2_er = Decimal(str(row.total_tier2_er))

        # By department
        dept_result = await self.db.execute(
            select(
                func.coalesce(PayrollItem.department_name, "Unassigned").label("department"),
                func.count(PayrollItem.id).label("count"),
                func.coalesce(func.sum(PayrollItem.gross_salary), 0).label("gross"),
                func.coalesce(func.sum(PayrollItem.net_salary), 0).label("net"),
            )
            .join(PayrollRun, and_(*base_conditions))
            .group_by(PayrollItem.department_name)
            .order_by(func.coalesce(PayrollItem.department_name, "Unassigned"))
        )
        by_department = [
            {
                "department": r.department,
                "staff_count": r.count,
                "total_gross": Decimal(str(r.gross)),
                "total_net": Decimal(str(r.net)),
            }
            for r in dept_result.all()
        ]

        # By payment method
        method_result = await self.db.execute(
            select(
                func.coalesce(PayrollItem.payment_method, "unspecified").label("method"),
                func.count(PayrollItem.id).label("count"),
                func.coalesce(func.sum(PayrollItem.net_salary), 0).label("total"),
            )
            .join(PayrollRun, and_(*base_conditions))
            .group_by(PayrollItem.payment_method)
            .order_by(func.coalesce(PayrollItem.payment_method, "unspecified"))
        )
        by_payment_method = [
            {
                "payment_method": r.method,
                "staff_count": r.count,
                "total": Decimal(str(r.total)),
            }
            for r in method_result.all()
        ]

        return {
            "month": month,
            "year": year,
            "currency": "GHS",
            "staff_count": row.staff_count,
            "total_basic": Decimal(str(row.total_basic)),
            "total_allowances": Decimal(str(row.total_allowances)),
            "total_gross": total_gross,
            "total_paye": Decimal(str(row.total_paye)),
            "total_ssnit_ee": Decimal(str(row.total_ssnit_ee)),
            "total_ssnit_er": total_ssnit_er,
            "total_tier2_er": total_tier2_er,
            "total_tier3": Decimal(str(row.total_tier3)),
            "total_other_deductions": Decimal(str(row.total_other_deductions)),
            "total_net": Decimal(str(row.total_net)),
            "total_employer_cost": total_gross + total_ssnit_er + total_tier2_er,
            "by_department": by_department,
            "by_payment_method": by_payment_method,
        }

    # ==================================================================
    # SSNIT Returns
    # ==================================================================

    async def get_ssnit_returns(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Generate SSNIT contribution report showing per-staff employee and
        employer contributions based on basic salary.
        """
        conditions = self._build_conditions(tenant_id, year, month, school_id)

        result = await self.db.execute(
            select(
                PayrollItem.staff_name,
                PayrollItem.staff_code,
                PayrollItem.ssnit_number,
                PayrollItem.basic_salary,
                PayrollItem.ssnit_employee,
                PayrollItem.ssnit_employer,
                PayrollItem.tier2_employer,
            )
            .join(PayrollRun, and_(*conditions))
            .order_by(PayrollItem.staff_name)
        )
        rows = result.all()

        items = []
        total_ee = Decimal("0")
        total_er = Decimal("0")
        total_tier2 = Decimal("0")

        for r in rows:
            ee = Decimal(str(r.ssnit_employee))
            er = Decimal(str(r.ssnit_employer))
            t2 = Decimal(str(r.tier2_employer))
            items.append({
                "staff_name": r.staff_name,
                "staff_code": r.staff_code,
                "ssnit_number": r.ssnit_number,
                "basic_salary": Decimal(str(r.basic_salary)),
                "employee_contribution": ee,
                "employer_contribution": er,
                "tier2_contribution": t2,
                "total_contribution": ee + er + t2,
            })
            total_ee += ee
            total_er += er
            total_tier2 += t2

        return {
            "month": month,
            "year": year,
            "currency": "GHS",
            "total_employee": total_ee,
            "total_employer": total_er,
            "total_tier2": total_tier2,
            "grand_total": total_ee + total_er + total_tier2,
            "staff_count": len(items),
            "items": items,
        }

    # ==================================================================
    # PAYE Returns
    # ==================================================================

    async def get_paye_returns(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Generate PAYE tax report showing per-staff taxable income and
        tax deducted.
        """
        conditions = self._build_conditions(tenant_id, year, month, school_id)

        result = await self.db.execute(
            select(
                PayrollItem.staff_name,
                PayrollItem.staff_code,
                PayrollItem.tin_number,
                PayrollItem.gross_salary,
                PayrollItem.taxable_income,
                PayrollItem.paye_tax,
            )
            .join(PayrollRun, and_(*conditions))
            .order_by(PayrollItem.staff_name)
        )
        rows = result.all()

        items = []
        total_taxable = Decimal("0")
        total_paye = Decimal("0")

        for r in rows:
            taxable = Decimal(str(r.taxable_income))
            paye = Decimal(str(r.paye_tax))
            items.append({
                "staff_name": r.staff_name,
                "staff_code": r.staff_code,
                "tin_number": r.tin_number,
                "gross_salary": Decimal(str(r.gross_salary)),
                "taxable_income": taxable,
                "paye_tax": paye,
            })
            total_taxable += taxable
            total_paye += paye

        return {
            "month": month,
            "year": year,
            "currency": "GHS",
            "total_taxable": total_taxable,
            "total_paye": total_paye,
            "staff_count": len(items),
            "items": items,
        }

    # ==================================================================
    # Department Summary
    # ==================================================================

    async def get_department_summary(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Generate payroll cost summary grouped by department.
        """
        conditions = self._build_conditions(tenant_id, year, month, school_id)

        result = await self.db.execute(
            select(
                func.coalesce(PayrollItem.department_name, "Unassigned").label("department"),
                func.count(PayrollItem.id).label("staff_count"),
                func.coalesce(func.sum(PayrollItem.basic_salary), 0).label("total_basic"),
                func.coalesce(func.sum(PayrollItem.gross_salary), 0).label("total_gross"),
                func.coalesce(func.sum(PayrollItem.net_salary), 0).label("total_net"),
                func.coalesce(func.sum(PayrollItem.ssnit_employer), 0).label("ssnit_er"),
                func.coalesce(func.sum(PayrollItem.tier2_employer), 0).label("tier2_er"),
            )
            .join(PayrollRun, and_(*conditions))
            .group_by(PayrollItem.department_name)
            .order_by(func.coalesce(PayrollItem.department_name, "Unassigned"))
        )
        rows = result.all()

        departments = []
        for r in rows:
            gross = Decimal(str(r.total_gross))
            ssnit_er = Decimal(str(r.ssnit_er))
            tier2_er = Decimal(str(r.tier2_er))
            departments.append({
                "department_name": r.department,
                "staff_count": r.staff_count,
                "total_basic": Decimal(str(r.total_basic)),
                "total_gross": gross,
                "total_net": Decimal(str(r.total_net)),
                "total_employer_cost": gross + ssnit_er + tier2_er,
            })

        return {
            "month": month,
            "year": year,
            "currency": "GHS",
            "departments": departments,
        }

    # ==================================================================
    # Year-to-Date
    # ==================================================================

    async def get_year_to_date(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        year: int,
    ) -> dict:
        """
        Generate year-to-date payroll breakdown for a single staff member.
        Shows monthly entries and cumulative totals.
        """
        result = await self.db.execute(
            select(
                PayrollRun.month,
                func.coalesce(func.sum(PayrollItem.gross_salary), 0).label("gross"),
                func.coalesce(func.sum(PayrollItem.paye_tax), 0).label("paye"),
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
            .where(PayrollRun.deleted_at.is_(None))
            .where(PayrollRun.status.in_(_REPORTABLE_STATUSES))
            .group_by(PayrollRun.month)
            .order_by(PayrollRun.month)
        )
        rows = result.all()

        months = []
        total_gross = Decimal("0")
        total_paye = Decimal("0")
        total_ssnit = Decimal("0")
        total_net = Decimal("0")

        for r in rows:
            gross = Decimal(str(r.gross))
            paye = Decimal(str(r.paye))
            ssnit = Decimal(str(r.ssnit))
            net = Decimal(str(r.net))
            months.append({
                "month": r.month,
                "month_name": calendar.month_name[r.month],
                "gross_salary": gross,
                "paye_tax": paye,
                "ssnit_employee": ssnit,
                "net_salary": net,
            })
            total_gross += gross
            total_paye += paye
            total_ssnit += ssnit
            total_net += net

        # Fetch staff name from the most recent payroll item
        name_result = await self.db.execute(
            select(PayrollItem.staff_name)
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItem.staff_id == staff_id)
            .order_by(PayrollItem.created_at.desc())
            .limit(1)
        )
        staff_name_row = name_result.scalar_one_or_none()

        return {
            "staff_id": staff_id,
            "staff_name": staff_name_row or "Unknown",
            "year": year,
            "currency": "GHS",
            "months": months,
            "total_gross": total_gross,
            "total_paye": total_paye,
            "total_ssnit": total_ssnit,
            "total_net": total_net,
        }

    # ==================================================================
    # Excel Export
    # ==================================================================

    def export_ssnit_to_excel(self, data: dict) -> bytes:
        """
        Generate an Excel file from SSNIT returns data.

        Returns openpyxl workbook bytes.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "SSNIT Returns"

        # Title
        month_name = calendar.month_name[data["month"]]
        ws.merge_cells("A1:G1")
        ws["A1"] = f"SSNIT RETURNS - {month_name} {data['year']}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        # Headers
        headers = [
            "Staff Name", "Staff Code", "SSNIT Number", "Basic Salary",
            "Employee (5.5%)", "Employer (13%)", "Tier 2 (5%)", "Total",
        ]
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font

        # Data rows
        for idx, item in enumerate(data["items"], 4):
            ws.cell(row=idx, column=1, value=item["staff_name"])
            ws.cell(row=idx, column=2, value=item["staff_code"])
            ws.cell(row=idx, column=3, value=item.get("ssnit_number", ""))
            ws.cell(row=idx, column=4, value=float(item["basic_salary"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
            ws.cell(row=idx, column=5, value=float(item["employee_contribution"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
            ws.cell(row=idx, column=6, value=float(item["employer_contribution"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
            ws.cell(row=idx, column=7, value=float(item["tier2_contribution"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
            ws.cell(row=idx, column=8, value=float(item["total_contribution"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1

        # Totals row
        total_row = len(data["items"]) + 4
        ws.cell(row=total_row, column=1, value="TOTALS").font = Font(bold=True)
        ws.cell(row=total_row, column=5, value=float(data["total_employee"])).font = Font(bold=True)
        ws.cell(row=total_row, column=5).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
        ws.cell(row=total_row, column=6, value=float(data["total_employer"])).font = Font(bold=True)
        ws.cell(row=total_row, column=6).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
        ws.cell(row=total_row, column=7, value=float(data["total_tier2"])).font = Font(bold=True)
        ws.cell(row=total_row, column=7).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
        ws.cell(row=total_row, column=8, value=float(data["grand_total"])).font = Font(bold=True)
        ws.cell(row=total_row, column=8).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1

        # Auto-size columns
        for col in range(1, 9):
            ws.column_dimensions[chr(64 + col)].width = 18

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def export_paye_to_excel(self, data: dict) -> bytes:
        """
        Generate an Excel file from PAYE returns data.

        Returns openpyxl workbook bytes.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "PAYE Returns"

        # Title
        month_name = calendar.month_name[data["month"]]
        ws.merge_cells("A1:F1")
        ws["A1"] = f"PAYE RETURNS - {month_name} {data['year']}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        # Headers
        headers = [
            "Staff Name", "Staff Code", "TIN", "Gross Salary",
            "Taxable Income", "PAYE Tax",
        ]
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font

        # Data rows
        for idx, item in enumerate(data["items"], 4):
            ws.cell(row=idx, column=1, value=item["staff_name"])
            ws.cell(row=idx, column=2, value=item["staff_code"])
            ws.cell(row=idx, column=3, value=item.get("tin_number", ""))
            ws.cell(row=idx, column=4, value=float(item["gross_salary"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
            ws.cell(row=idx, column=5, value=float(item["taxable_income"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
            ws.cell(row=idx, column=6, value=float(item["paye_tax"])).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1

        # Totals row
        total_row = len(data["items"]) + 4
        ws.cell(row=total_row, column=1, value="TOTALS").font = Font(bold=True)
        ws.cell(row=total_row, column=5, value=float(data["total_taxable"])).font = Font(bold=True)
        ws.cell(row=total_row, column=5).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1
        ws.cell(row=total_row, column=6, value=float(data["total_paye"])).font = Font(bold=True)
        ws.cell(row=total_row, column=6).number_format = numbers.FORMAT_NUMBER_COMMA_SEPARATED1

        # Auto-size columns
        for col in range(1, 7):
            ws.column_dimensions[chr(64 + col)].width = 18

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ==================================================================
    # Helpers
    # ==================================================================

    def _build_conditions(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
        school_id: Optional[UUID] = None,
    ) -> list:
        """Build common join conditions for PayrollItem -> PayrollRun."""
        conditions = [
            PayrollRun.id == PayrollItem.payroll_run_id,
            PayrollRun.tenant_id == tenant_id,
            PayrollRun.year == year,
            PayrollRun.month == month,
            PayrollRun.deleted_at.is_(None),
            PayrollRun.status.in_(_REPORTABLE_STATUSES),
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            PayrollItem.tenant_id == tenant_id,
        ]
        if school_id:
            conditions.append(PayrollRun.school_id == school_id)
        return conditions

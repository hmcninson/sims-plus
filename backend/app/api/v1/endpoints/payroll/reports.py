"""
SIMS Plus - Payroll Reports & Bank File Endpoints

10 endpoints for bank file generation, statutory reports (SSNIT, PAYE),
department summaries, year-to-date, and audit log.

All endpoints gated by hr_payroll feature flag and payroll.* permissions.

IMPORTANT: Do NOT use `from __future__ import annotations` here.
It breaks 204 No Content responses with AssertionError.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.schemas.payroll import (
    AuditLogListResponse,
    BankFileResponse,
    DepartmentSummaryResponse,
    DepartmentSummaryItem,
    MonthlySummaryResponse,
    PAYEReturnItem,
    PAYEReturnResponse,
    PayrollAuditLogResponse,
    SSNITReturnItem,
    SSNITReturnResponse,
    YearToDateMonthEntry,
    YearToDateResponse,
)
from app.services.payroll import (
    BankFileService,
    PayrollAuditService,
    PayrollReportService,
)

router = APIRouter()


# ======================================================================
# Bank File Generation
# ======================================================================


@router.get(
    "/runs/{run_id}/bank-file",
    response_model=BankFileResponse,
    summary="Generate bank file (default config)",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def generate_bank_file(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> BankFileResponse:
    """
    Generate a bank payment file using the default bank file configuration.

    The file is uploaded to S3 and a 5-minute presigned download URL is returned.
    """
    service = BankFileService(db)
    try:
        result = await service.generate_bank_file(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
        )

        # Audit trail
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="bank_file",
            entity_id=run_id,
            action="bank_file_generated",
            performed_by=UUID(current_user["user_id"]),
            metadata={
                "bank_name": result["bank_name"],
                "record_count": result["record_count"],
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return BankFileResponse(**result)
    except BankFileService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/runs/{run_id}/bank-file/{config_id}",
    response_model=BankFileResponse,
    summary="Generate bank file for specific config",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def generate_bank_file_by_config(
    run_id: UUID,
    config_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> BankFileResponse:
    """
    Generate a bank payment file using a specific bank file configuration.
    """
    service = BankFileService(db)
    try:
        result = await service.generate_bank_file(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            config_id=config_id,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="bank_file",
            entity_id=run_id,
            action="bank_file_generated",
            performed_by=UUID(current_user["user_id"]),
            metadata={
                "bank_name": result["bank_name"],
                "config_id": str(config_id),
                "record_count": result["record_count"],
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return BankFileResponse(**result)
    except BankFileService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Monthly Summary
# ======================================================================


@router.get(
    "/reports/monthly-summary",
    response_model=MonthlySummaryResponse,
    summary="Monthly payroll summary",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_monthly_summary(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    school_id: Optional[UUID] = Query(None),
) -> MonthlySummaryResponse:
    """Get monthly payroll summary with department and payment method breakdowns."""
    service = PayrollReportService(db)
    result = await service.get_monthly_summary(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        school_id=school_id,
    )
    return MonthlySummaryResponse(**result)


# ======================================================================
# SSNIT Returns
# ======================================================================


@router.get(
    "/reports/ssnit-returns",
    response_model=SSNITReturnResponse,
    summary="SSNIT contribution report",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_ssnit_returns(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    school_id: Optional[UUID] = Query(None),
) -> SSNITReturnResponse:
    """Get SSNIT contribution report with per-staff breakdowns."""
    service = PayrollReportService(db)
    result = await service.get_ssnit_returns(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        school_id=school_id,
    )
    return SSNITReturnResponse(
        month=result["month"],
        year=result["year"],
        currency=result["currency"],
        total_employee=result["total_employee"],
        total_employer=result["total_employer"],
        total_tier2=result["total_tier2"],
        grand_total=result["grand_total"],
        staff_count=result["staff_count"],
        items=[SSNITReturnItem(**i) for i in result["items"]],
    )


@router.post(
    "/reports/ssnit-returns/export",
    summary="Export SSNIT returns as Excel",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def export_ssnit_returns(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    school_id: Optional[UUID] = Query(None),
) -> StreamingResponse:
    """Export SSNIT returns as an Excel (.xlsx) file."""
    service = PayrollReportService(db)
    data = await service.get_ssnit_returns(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        school_id=school_id,
    )

    excel_bytes = service.export_ssnit_to_excel(data)

    filename = f"SSNIT_Returns_{year}_{month:02d}.xlsx"
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ======================================================================
# PAYE Returns
# ======================================================================


@router.get(
    "/reports/paye-returns",
    response_model=PAYEReturnResponse,
    summary="PAYE tax report",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_paye_returns(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    school_id: Optional[UUID] = Query(None),
) -> PAYEReturnResponse:
    """Get PAYE tax report with per-staff breakdowns."""
    service = PayrollReportService(db)
    result = await service.get_paye_returns(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        school_id=school_id,
    )
    return PAYEReturnResponse(
        month=result["month"],
        year=result["year"],
        currency=result["currency"],
        total_taxable=result["total_taxable"],
        total_paye=result["total_paye"],
        staff_count=result["staff_count"],
        items=[PAYEReturnItem(**i) for i in result["items"]],
    )


@router.post(
    "/reports/paye-returns/export",
    summary="Export PAYE returns as Excel",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def export_paye_returns(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    school_id: Optional[UUID] = Query(None),
) -> StreamingResponse:
    """Export PAYE returns as an Excel (.xlsx) file."""
    service = PayrollReportService(db)
    data = await service.get_paye_returns(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        school_id=school_id,
    )

    excel_bytes = service.export_paye_to_excel(data)

    filename = f"PAYE_Returns_{year}_{month:02d}.xlsx"
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ======================================================================
# Department Summary
# ======================================================================


@router.get(
    "/reports/department-summary",
    response_model=DepartmentSummaryResponse,
    summary="Payroll cost by department",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_department_summary(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    school_id: Optional[UUID] = Query(None),
) -> DepartmentSummaryResponse:
    """Get payroll cost breakdown by department."""
    service = PayrollReportService(db)
    result = await service.get_department_summary(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        school_id=school_id,
    )
    return DepartmentSummaryResponse(
        month=result["month"],
        year=result["year"],
        currency=result["currency"],
        departments=[DepartmentSummaryItem(**d) for d in result["departments"]],
    )


# ======================================================================
# Year-to-Date
# ======================================================================


@router.get(
    "/reports/year-to-date/{staff_id}",
    response_model=YearToDateResponse,
    summary="Staff year-to-date payroll",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_year_to_date(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: int = Query(..., ge=2020, le=2100),
) -> YearToDateResponse:
    """Get year-to-date payroll breakdown for a staff member."""
    service = PayrollReportService(db)
    result = await service.get_year_to_date(
        tenant_id=tenant.tenant_id,
        staff_id=staff_id,
        year=year,
    )
    return YearToDateResponse(
        staff_id=result["staff_id"],
        staff_name=result["staff_name"],
        year=result["year"],
        currency=result["currency"],
        months=[YearToDateMonthEntry(**m) for m in result["months"]],
        total_gross=result["total_gross"],
        total_paye=result["total_paye"],
        total_ssnit=result["total_ssnit"],
        total_net=result["total_net"],
    )


# ======================================================================
# Audit Log
# ======================================================================


@router.get(
    "/audit-log",
    response_model=AuditLogListResponse,
    summary="Payroll audit trail",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.audit")),
    ],
)
async def get_audit_log(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AuditLogListResponse:
    """
    Query the payroll audit trail with optional filters.

    The audit log is append-only (no UPDATE/DELETE at DB level) and
    records every payroll mutation for compliance and accountability.
    """
    service = PayrollAuditService(db)
    items = await service.list_audit_log(
        tenant_id=tenant.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=[PayrollAuditLogResponse.model_validate(i) for i in items],
        total=len(items),
        limit=limit,
        offset=offset,
    )

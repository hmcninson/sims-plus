"""
SIMS Plus - Payslip Endpoints

2 endpoints for payslip generation: individual PDF download and bulk
generation via Celery.

All endpoints gated by hr_payroll feature flag and payroll.* permissions.

IMPORTANT: Do NOT use `from __future__ import annotations` here.
It breaks 204 No Content responses with AssertionError.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.schemas.payroll import (
    BulkPayslipResponse,
    PayslipResponse,
)
from app.services.payroll import PayrollAuditService, PayslipService
from app.services.payroll.run_service import PayrollRunService

router = APIRouter()


@router.get(
    "/runs/{run_id}/payslips/{staff_id}",
    response_model=PayslipResponse,
    summary="Download individual payslip PDF",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_payslip(
    run_id: UUID,
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> PayslipResponse:
    """
    Generate and return a presigned URL for an individual payslip PDF.

    The PDF is generated on-demand, uploaded to S3, and a 5-minute
    presigned download URL is returned. Subsequent requests will
    overwrite the existing file (idempotent).
    """
    service = PayslipService(db)
    try:
        result = await service.generate_payslip_pdf(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            staff_id=staff_id,
        )

        # Audit trail
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payslip",
            entity_id=run_id,
            action="payslip_generated",
            performed_by=UUID(current_user["user_id"]),
            metadata={
                "staff_id": str(staff_id),
                "staff_code": result["staff_code"],
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return PayslipResponse(**result)
    except PayslipService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/runs/{run_id}/payslips/bulk",
    response_model=BulkPayslipResponse,
    summary="Bulk generate payslips (Celery)",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def bulk_generate_payslips(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> BulkPayslipResponse:
    """
    Trigger background generation of payslip PDFs for all staff in a
    payroll run. Returns a Celery task ID for polling progress.

    Progress can be tracked via Redis key: payroll:payslips:{run_id}:progress
    """
    # Verify run exists, belongs to tenant, and is in a valid state
    run_service = PayrollRunService(db)
    try:
        run = await run_service.get_run(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
        )
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    from app.models.payroll import PayrollRunStatus
    allowed = {
        PayrollRunStatus.CALCULATED,
        PayrollRunStatus.PENDING_APPROVAL,
        PayrollRunStatus.APPROVED,
        PayrollRunStatus.PAID,
    }
    if run.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot generate payslips: run is in '{run.status.value}' status. "
                f"The run must be at least calculated."
            ),
        )

    # Import the task here to avoid circular imports
    from app.tasks.payroll import generate_bulk_payslips

    task = generate_bulk_payslips.delay(
        str(run_id), str(tenant.tenant_id)
    )

    # Audit trail
    audit = PayrollAuditService(db)
    await audit.log_event(
        tenant_id=tenant.tenant_id,
        entity_type="payroll_run",
        entity_id=run_id,
        action="bulk_payslips_triggered",
        performed_by=UUID(current_user["user_id"]),
        metadata={"task_id": task.id, "staff_count": run.staff_count},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return BulkPayslipResponse(
        task_id=task.id,
        message="Bulk payslip generation started. Track progress via Redis.",
        staff_count=run.staff_count,
    )

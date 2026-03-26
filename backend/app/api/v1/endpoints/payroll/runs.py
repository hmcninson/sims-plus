"""
SIMS Plus - Payroll Run Endpoints

14 endpoints for the payroll run lifecycle: create, calculate, submit,
approve/reject, mark paid, cancel, list items, manual adjustments,
and summary statistics.

All endpoints gated by hr_payroll feature flag and payroll.* permissions.

IMPORTANT: Do NOT use `from __future__ import annotations` here.
It breaks 204 No Content responses with AssertionError.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.schemas.payroll import (
    CalculationTriggerResponse,
    ManualAdjustmentRequest,
    PayrollApprovalRequest,
    PayrollItemDetailResponse,
    PayrollItemDeductionResponse,
    PayrollItemEarningResponse,
    PayrollItemListResponse,
    PayrollItemResponse,
    PayrollRejectRequest,
    PayrollRunCreate,
    PayrollRunResponse,
    PayrollRunSummary,
)
from app.services.payroll import PayrollAuditService
from app.services.payroll.run_service import PayrollRunService

router = APIRouter()


def _build_item_response(item) -> PayrollItemResponse:
    """Build a PayrollItemResponse from an ORM PayrollItem."""
    return PayrollItemResponse.model_validate(item)


def _build_item_detail_response(item) -> PayrollItemDetailResponse:
    """Build a PayrollItemDetailResponse with earnings and deductions."""
    earnings = [
        PayrollItemEarningResponse.model_validate(e) for e in item.earnings
    ]
    deductions = [
        PayrollItemDeductionResponse.model_validate(d) for d in item.deductions
    ]
    return PayrollItemDetailResponse(
        **PayrollItemResponse.model_validate(item).model_dump(),
        earnings=earnings,
        deductions=deductions,
    )


# ======================================================================
# Payroll Runs
# ======================================================================


@router.get(
    "/runs",
    response_model=list[PayrollRunResponse],
    summary="List payroll runs",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_payroll_runs(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    year: Optional[int] = Query(None, ge=2020, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    run_status: Optional[str] = Query(None, alias="status"),
    school_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PayrollRunResponse]:
    """List payroll runs with optional filters."""
    service = PayrollRunService(db)
    runs = await service.list_runs(
        tenant_id=tenant.tenant_id,
        year=year,
        month=month,
        status=run_status,
        school_id=school_id,
        limit=limit,
        offset=offset,
    )
    return [PayrollRunResponse.model_validate(r) for r in runs]


@router.post(
    "/runs",
    response_model=PayrollRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payroll run",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def create_payroll_run(
    data: PayrollRunCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> PayrollRunResponse:
    """Create a new payroll run in draft status."""
    service = PayrollRunService(db)
    try:
        run = await service.create_run(
            tenant_id=tenant.tenant_id,
            month=data.month,
            year=data.year,
            run_type=data.run_type,
            school_id=data.school_id,
            created_by=UUID(current_user["user_id"]),
        )

        # Audit trail
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run.id,
            action="created",
            performed_by=UUID(current_user["user_id"]),
            new_value=f"{data.month}/{data.year} ({data.run_type})",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return PayrollRunResponse.model_validate(run)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/runs/{run_id}",
    response_model=PayrollRunResponse,
    summary="Get payroll run detail",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_payroll_run(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> PayrollRunResponse:
    """Get a payroll run by ID."""
    service = PayrollRunService(db)
    try:
        run = await service.get_run(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
        )
        return PayrollRunResponse.model_validate(run)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/runs/{run_id}/calculate",
    response_model=CalculationTriggerResponse,
    summary="Trigger payroll calculation",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def calculate_payroll_run(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> CalculationTriggerResponse:
    """Trigger background payroll calculation via Celery."""
    service = PayrollRunService(db)
    try:
        task_id = await service.trigger_calculation(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            user_id=UUID(current_user["user_id"]),
        )

        # Audit trail
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run_id,
            action="calculation_triggered",
            performed_by=UUID(current_user["user_id"]),
            metadata={"task_id": task_id},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return CalculationTriggerResponse(
            task_id=task_id,
            message="Payroll calculation started. Poll the run status for completion.",
        )
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/runs/{run_id}/submit",
    response_model=PayrollRunResponse,
    summary="Submit for approval",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def submit_payroll_run(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> PayrollRunResponse:
    """Submit a calculated payroll run for approval."""
    service = PayrollRunService(db)
    try:
        run = await service.submit_for_approval(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            user_id=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run_id,
            action="submitted_for_approval",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return PayrollRunResponse.model_validate(run)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/runs/{run_id}/approve",
    response_model=PayrollRunResponse,
    summary="Approve payroll run",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.approve")),
    ],
)
async def approve_payroll_run(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
    data: PayrollApprovalRequest = None,
) -> PayrollRunResponse:
    """
    Approve a payroll run. Enforces separation of duties: the approver
    cannot be the same person who submitted the run.
    """
    service = PayrollRunService(db)
    try:
        run = await service.approve_run(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            approver_id=UUID(current_user["user_id"]),
            comments=data.comments if data else None,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run_id,
            action="approved",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return PayrollRunResponse.model_validate(run)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/runs/{run_id}/reject",
    response_model=PayrollRunResponse,
    summary="Reject payroll run",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.approve")),
    ],
)
async def reject_payroll_run(
    run_id: UUID,
    data: PayrollRejectRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> PayrollRunResponse:
    """Reject a payroll run, returning it to draft for revision."""
    service = PayrollRunService(db)
    try:
        run = await service.reject_run(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            approver_id=UUID(current_user["user_id"]),
            reason=data.reason,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run_id,
            action="rejected",
            performed_by=UUID(current_user["user_id"]),
            new_value=data.reason,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return PayrollRunResponse.model_validate(run)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/runs/{run_id}/mark-paid",
    response_model=PayrollRunResponse,
    summary="Mark payroll as paid",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.approve")),
    ],
)
async def mark_payroll_paid(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> PayrollRunResponse:
    """Mark an approved payroll run as paid. Items become immutable."""
    service = PayrollRunService(db)
    try:
        run = await service.mark_paid(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            user_id=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run_id,
            action="marked_paid",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return PayrollRunResponse.model_validate(run)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel payroll run",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def cancel_payroll_run(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> None:
    """Cancel a draft or calculated payroll run."""
    service = PayrollRunService(db)
    try:
        await service.cancel_run(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            user_id=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_run",
            entity_id=run_id,
            action="cancelled",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Payroll Items
# ======================================================================


@router.get(
    "/runs/{run_id}/items",
    response_model=list[PayrollItemListResponse],
    summary="List payroll items",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_payroll_items(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[PayrollItemListResponse]:
    """List all payroll items for a run. Excludes PII — use item detail for full data."""
    service = PayrollRunService(db)
    try:
        items = await service.get_run_items(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            limit=limit,
            offset=offset,
        )
        # Use PayrollItemListResponse to exclude sensitive fields (TIN, SSNIT, bank details)
        return [PayrollItemListResponse.model_validate(item) for item in items]
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/runs/{run_id}/items/{item_id}",
    response_model=PayrollItemDetailResponse,
    summary="Get payroll item detail",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_payroll_item(
    run_id: UUID,
    item_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> PayrollItemDetailResponse:
    """Get a single payroll item with full earnings and deductions breakdown."""
    service = PayrollRunService(db)
    try:
        item = await service.get_run_item(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            item_id=item_id,
        )
        return _build_item_detail_response(item)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/runs/{run_id}/items/{item_id}",
    response_model=PayrollItemDetailResponse,
    summary="Manual adjustment",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.process")),
    ],
)
async def adjust_payroll_item(
    run_id: UUID,
    item_id: UUID,
    data: ManualAdjustmentRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> PayrollItemDetailResponse:
    """
    Apply manual adjustments to a payroll item. Only allowed on
    calculated runs — approved and paid runs are immutable.
    """
    service = PayrollRunService(db)
    try:
        item, old_values, new_values = await service.manual_adjustment(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            item_id=item_id,
            adjustments=data.model_dump(exclude_unset=True),
            user_id=UUID(current_user["user_id"]),
        )

        # Audit trail for manual adjustments with old/new values
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="payroll_item",
            entity_id=item_id,
            action="manual_adjustment",
            performed_by=UUID(current_user["user_id"]),
            old_value=str(old_values) if old_values else None,
            new_value=str(new_values) if new_values else None,
            metadata={
                "run_id": str(run_id),
                "fields_adjusted": list(data.model_dump(exclude_unset=True).keys()),
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Reload with earnings/deductions
        item = await service.get_run_item(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
            item_id=item_id,
        )
        return _build_item_detail_response(item)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Run Summary
# ======================================================================


@router.get(
    "/runs/{run_id}/summary",
    response_model=PayrollRunSummary,
    summary="Run summary statistics",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_payroll_run_summary(
    run_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> PayrollRunSummary:
    """Get aggregate summary statistics for a payroll run."""
    service = PayrollRunService(db)
    try:
        summary = await service.get_run_summary(
            tenant_id=tenant.tenant_id,
            run_id=run_id,
        )
        return PayrollRunSummary(**summary)
    except PayrollRunService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# NOTE: The /staff/{staff_id}/salary/history endpoint is defined in config.py
# (Phase 4A). It is not duplicated here to avoid route conflicts.

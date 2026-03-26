"""
SIMS Plus - Loan Management Endpoints

28 endpoints for loan lifecycle, operations, installments, payments,
guarantors, staff view, and analytics.

All endpoints gated by hr_payroll feature flag and payroll.loans.* permissions.

IMPORTANT: Do NOT use `from __future__ import annotations` here.
It breaks 204 No Content responses with AssertionError.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.schemas.loan import (
    EarlyRepaymentRequest,
    LoanAgingResponse,
    LoanCreate,
    LoanEligibilityResponse,
    LoanGuarantorConsentRequest,
    LoanGuarantorCreate,
    LoanGuarantorResponse,
    LoanInstallmentResponse,
    LoanListItem,
    LoanListResponse,
    LoanPaymentResponse,
    LoanPortfolioResponse,
    LoanRejectRequest,
    LoanResponse,
    LoanRestructureRequest,
    LoanTypeBreakdown,
    LoanTypeCreate,
    LoanTypeResponse,
    LoanTypeUpdate,
    LoanUpdate,
    LoanWriteOffRequest,
)
from app.services.payroll import PayrollAuditService
from app.services.payroll.loan_service import LoanService
from app.services.payroll.loan_statement_service import LoanStatementService

router = APIRouter()


# ======================================================================
# Helpers
# ======================================================================


def _build_loan_list_item(loan) -> LoanListItem:
    """Build a LoanListItem from an ORM StaffLoan with loaded relations."""
    staff = loan.staff
    staff_name = f"{staff.first_name} {staff.last_name}" if staff else None
    loan_type_name = loan.loan_type.name if loan.loan_type else None

    return LoanListItem(
        id=loan.id,
        loan_number=loan.loan_number,
        staff_id=loan.staff_id,
        staff_name=staff_name,
        loan_type_name=loan_type_name,
        status=loan.status,
        principal_amount=loan.principal_amount,
        total_repayable=loan.total_repayable,
        total_paid=loan.total_paid,
        outstanding_balance=loan.outstanding_balance,
        tenure_months=loan.tenure_months,
        installments_paid=loan.installments_paid,
        installments_remaining=loan.installments_remaining,
        application_date=loan.application_date,
        first_deduction_date=loan.first_deduction_date,
    )


def _build_loan_response(loan) -> LoanResponse:
    """Build a full LoanResponse from an ORM StaffLoan with loaded relations."""
    staff = loan.staff
    staff_name = f"{staff.first_name} {staff.last_name}" if staff else None

    # Build guarantor responses
    guarantors = []
    if hasattr(loan, "guarantors") and loan.guarantors:
        for g in loan.guarantors:
            g_staff = g.guarantor_staff if hasattr(g, "guarantor_staff") else None
            g_name = (
                f"{g_staff.first_name} {g_staff.last_name}"
                if g_staff else None
            )
            guarantors.append(LoanGuarantorResponse(
                id=g.id,
                loan_id=g.loan_id,
                guarantor_staff_id=g.guarantor_staff_id,
                guarantor_staff_name=g_name,
                relationship=g.relationship_desc,
                guaranteed_amount=g.guaranteed_amount,
                consent_given=g.consent_given,
                consent_date=g.consent_date,
                notes=g.notes,
                created_at=g.created_at,
            ))

    # Build loan type response
    loan_type_resp = None
    if loan.loan_type:
        loan_type_resp = LoanTypeResponse.model_validate(loan.loan_type)

    return LoanResponse(
        id=loan.id,
        tenant_id=loan.tenant_id,
        school_id=loan.school_id,
        loan_number=loan.loan_number,
        staff_id=loan.staff_id,
        staff_name=staff_name,
        loan_type=loan_type_resp,
        status=loan.status,
        principal_amount=loan.principal_amount,
        interest_rate=loan.interest_rate,
        interest_method=loan.interest_method,
        total_interest=loan.total_interest,
        total_repayable=loan.total_repayable,
        tenure_months=loan.tenure_months,
        monthly_installment=loan.monthly_installment,
        total_paid=loan.total_paid,
        outstanding_balance=loan.outstanding_balance,
        installments_paid=loan.installments_paid,
        installments_remaining=loan.installments_remaining,
        application_date=loan.application_date,
        approval_date=loan.approval_date,
        disbursement_date=loan.disbursement_date,
        first_deduction_date=loan.first_deduction_date,
        expected_completion_date=loan.expected_completion_date,
        actual_completion_date=loan.actual_completion_date,
        purpose=loan.purpose,
        notes=loan.notes,
        guarantors=guarantors,
        created_at=loan.created_at,
        updated_at=loan.updated_at,
    )


# ======================================================================
# 6.1 Loan Type Configuration (4 endpoints)
# ======================================================================


@router.get(
    "/loan-types",
    response_model=list[LoanTypeResponse],
    summary="List loan types",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_loan_types(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
) -> list[LoanTypeResponse]:
    """List all loan type configurations."""
    service = LoanService(db)
    types = await service.list_loan_types(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        is_active=is_active,
    )
    return [LoanTypeResponse.model_validate(t) for t in types]


@router.post(
    "/loan-types",
    response_model=LoanTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create loan type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def create_loan_type(
    data: LoanTypeCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanTypeResponse:
    """Create a new loan type configuration."""
    service = LoanService(db)
    try:
        lt = await service.create_loan_type(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="loan_type",
            entity_id=lt.id,
            action="created",
            performed_by=UUID(current_user["user_id"]),
            new_value=f"{data.name} ({data.code})",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return LoanTypeResponse.model_validate(lt)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/loan-types/{loan_type_id}",
    response_model=LoanTypeResponse,
    summary="Update loan type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def update_loan_type(
    loan_type_id: UUID,
    data: LoanTypeUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanTypeResponse:
    """Update a loan type configuration."""
    service = LoanService(db)
    try:
        lt = await service.update_loan_type(
            tenant_id=tenant.tenant_id,
            loan_type_id=loan_type_id,
            data=data.model_dump(exclude_unset=True),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="loan_type",
            entity_id=lt.id,
            action="updated",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return LoanTypeResponse.model_validate(lt)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/loan-types/{loan_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete loan type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def delete_loan_type(
    loan_type_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
):
    """Soft-delete a loan type."""
    service = LoanService(db)
    try:
        await service.delete_loan_type(
            tenant_id=tenant.tenant_id,
            loan_type_id=loan_type_id,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="loan_type",
            entity_id=loan_type_id,
            action="deleted",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# 6.2 Loan Lifecycle (9 endpoints)
# ======================================================================


@router.get(
    "/loans",
    response_model=LoanListResponse,
    summary="List loans",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def list_loans(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    loan_status: Optional[str] = Query(None, alias="status"),
    staff_id: Optional[UUID] = Query(None),
    loan_type_id: Optional[UUID] = Query(None),
    school_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> LoanListResponse:
    """List loans with optional filters."""
    service = LoanService(db)
    loans, total = await service.list_loans(
        tenant_id=tenant.tenant_id,
        status=loan_status,
        staff_id=staff_id,
        loan_type_id=loan_type_id,
        school_id=school_id,
        limit=limit,
        offset=offset,
    )
    return LoanListResponse(
        items=[_build_loan_list_item(l) for l in loans],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/loans",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.request")),
    ],
)
async def create_loan(
    data: LoanCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Create a new loan in draft status."""
    service = LoanService(db)
    try:
        loan = await service.create_loan(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
            created_by=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan.id,
            action="created",
            performed_by=UUID(current_user["user_id"]),
            new_value=f"{loan.loan_number} - {data.principal_amount}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# 6.7 Analytics & Reports (4 endpoints)
# IMPORTANT: These MUST be registered before /loans/{loan_id} routes
# so that FastAPI doesn't try to match "portfolio" as a UUID.
# ======================================================================


@router.get(
    "/loans/portfolio",
    response_model=LoanPortfolioResponse,
    summary="Loan portfolio summary",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def get_portfolio(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None),
) -> LoanPortfolioResponse:
    """Get loan portfolio summary with breakdowns."""
    service = LoanService(db)
    result = await service.get_portfolio(tenant.tenant_id, school_id)
    return LoanPortfolioResponse(**result)


@router.get(
    "/loans/portfolio/export",
    summary="Export loan portfolio",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def export_portfolio(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None),
) -> StreamingResponse:
    """Export loan portfolio as CSV."""
    import csv
    from io import StringIO

    service = LoanService(db)
    loans, _ = await service.list_loans(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        limit=200,
        offset=0,
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Loan Number", "Staff Name", "Loan Type", "Status",
        "Principal", "Total Repayable", "Total Paid", "Outstanding",
        "Tenure", "Installments Paid", "Application Date",
    ])
    for loan in loans:
        staff_name = (
            f"{loan.staff.first_name} {loan.staff.last_name}"
            if loan.staff else "N/A"
        )
        writer.writerow([
            loan.loan_number,
            staff_name,
            loan.loan_type.name if loan.loan_type else "N/A",
            loan.status.value if hasattr(loan.status, "value") else loan.status,
            str(loan.principal_amount),
            str(loan.total_repayable),
            str(loan.total_paid),
            str(loan.outstanding_balance),
            loan.tenure_months,
            loan.installments_paid,
            loan.application_date.isoformat() if loan.application_date else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=loan_portfolio.csv"},
    )


@router.get(
    "/loans/{loan_id}",
    response_model=LoanResponse,
    summary="Get loan detail",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def get_loan(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LoanResponse:
    """Get full loan detail with schedule and guarantors."""
    service = LoanService(db)
    try:
        loan = await service.get_loan(tenant.tenant_id, loan_id)
        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/loans/{loan_id}",
    response_model=LoanResponse,
    summary="Update draft loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.request")),
    ],
)
async def update_loan(
    loan_id: UUID,
    data: LoanUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Update a draft loan."""
    service = LoanService(db)
    try:
        loan = await service.update_loan(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            data=data.model_dump(exclude_unset=True),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="updated",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/loans/{loan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel draft loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.request")),
    ],
)
async def delete_loan(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
):
    """Soft-delete (cancel) a draft loan."""
    service = LoanService(db)
    try:
        await service.delete_loan(tenant.tenant_id, loan_id)

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="cancelled",
            performed_by=UUID(current_user["user_id"]),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/loans/{loan_id}/submit",
    response_model=LoanResponse,
    summary="Submit loan for approval",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.request")),
    ],
)
async def submit_loan(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Submit a draft loan for approval."""
    service = LoanService(db)
    try:
        loan = await service.submit_loan(tenant.tenant_id, loan_id)

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="submitted",
            performed_by=UUID(current_user["user_id"]),
            new_value="pending_approval",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/loans/{loan_id}/approve",
    response_model=LoanResponse,
    summary="Approve loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.approve")),
    ],
)
async def approve_loan(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Approve a pending loan. Self-approval is prevented."""
    service = LoanService(db)
    try:
        # Determine approver's staff_id for self-approval check
        approver_staff_id = current_user.get("staff_id")
        if approver_staff_id:
            approver_staff_id = UUID(approver_staff_id)

        loan = await service.approve_loan(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            approver_id=UUID(current_user["user_id"]),
            approver_staff_id=approver_staff_id,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="approved",
            performed_by=UUID(current_user["user_id"]),
            new_value="approved",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/loans/{loan_id}/reject",
    response_model=LoanResponse,
    summary="Reject loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.approve")),
    ],
)
async def reject_loan(
    loan_id: UUID,
    data: LoanRejectRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Reject a pending loan with reason."""
    service = LoanService(db)
    try:
        loan = await service.reject_loan(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            rejector_id=UUID(current_user["user_id"]),
            reason=data.reason,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="rejected",
            performed_by=UUID(current_user["user_id"]),
            new_value="rejected",
            reason=data.reason,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/loans/{loan_id}/disburse",
    response_model=LoanResponse,
    summary="Disburse loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.disburse")),
    ],
)
async def disburse_loan(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Disburse an approved loan and generate the installment schedule."""
    service = LoanService(db)
    try:
        loan = await service.disburse_loan(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            disbursed_by=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="disbursed",
            performed_by=UUID(current_user["user_id"]),
            new_value="active",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# 6.3 Loan Operations (4 endpoints)
# ======================================================================


@router.post(
    "/loans/{loan_id}/early-repayment",
    response_model=LoanResponse,
    summary="Record early repayment",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.manage")),
    ],
)
async def early_repayment(
    loan_id: UUID,
    data: EarlyRepaymentRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Record an early/lump-sum payment on an active loan."""
    service = LoanService(db)
    try:
        loan = await service.early_repayment(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            amount=data.amount,
            payment_date=data.payment_date,
            payment_method=data.payment_method,
            recorded_by=UUID(current_user["user_id"]),
            reference=data.reference,
            is_full_settlement=data.is_full_settlement,
            notes=data.notes,
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="early_repayment",
            performed_by=UUID(current_user["user_id"]),
            new_value=f"{data.amount} via {data.payment_method}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/loans/{loan_id}/restructure",
    response_model=LoanResponse,
    summary="Restructure loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.manage")),
    ],
)
async def restructure_loan(
    loan_id: UUID,
    data: LoanRestructureRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Restructure an active loan with new terms. Creates a new loan."""
    service = LoanService(db)
    try:
        new_loan = await service.restructure_loan(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            new_interest_rate=data.new_interest_rate,
            new_interest_method=data.new_interest_method,
            new_tenure_months=data.new_tenure_months,
            new_first_deduction_date=data.new_first_deduction_date,
            reason=data.reason,
            performed_by=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="restructured",
            performed_by=UUID(current_user["user_id"]),
            new_value=f"New loan: {new_loan.loan_number}",
            reason=data.reason,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(new_loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/loans/{loan_id}/write-off",
    response_model=LoanResponse,
    summary="Write off loan",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.write_off")),
    ],
)
async def write_off_loan(
    loan_id: UUID,
    data: LoanWriteOffRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> LoanResponse:
    """Write off the remaining balance of an active loan."""
    service = LoanService(db)
    try:
        loan = await service.write_off_loan(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            reason=data.reason,
            written_off_by=UUID(current_user["user_id"]),
        )

        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_loan",
            entity_id=loan_id,
            action="written_off",
            performed_by=UUID(current_user["user_id"]),
            reason=data.reason,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_loan_response(loan)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/loans/{loan_id}/statement",
    summary="Generate loan statement PDF",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def get_loan_statement(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> dict:
    """Generate and return a presigned URL for the loan statement PDF."""
    stmt_service = LoanStatementService(db)
    try:
        result = await stmt_service.generate_statement(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
        )
        return result
    except LoanStatementService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# 6.4 Installments & Payments (2 endpoints)
# ======================================================================


@router.get(
    "/loans/{loan_id}/installments",
    response_model=list[LoanInstallmentResponse],
    summary="List loan installments",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def list_installments(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[LoanInstallmentResponse]:
    """List all installments for a loan."""
    service = LoanService(db)
    try:
        installments = await service.get_installments(tenant.tenant_id, loan_id)
        return [LoanInstallmentResponse.model_validate(i) for i in installments]
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.get(
    "/loans/{loan_id}/payments",
    response_model=list[LoanPaymentResponse],
    summary="List loan payments",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def list_payments(
    loan_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[LoanPaymentResponse]:
    """List all payments for a loan."""
    service = LoanService(db)
    try:
        payments = await service.get_payments(tenant.tenant_id, loan_id)
        return [LoanPaymentResponse.model_validate(p) for p in payments]
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# 6.5 Guarantors (3 endpoints)
# ======================================================================


@router.post(
    "/loans/{loan_id}/guarantors",
    response_model=LoanGuarantorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add guarantor",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.request")),
    ],
)
async def add_guarantor(
    loan_id: UUID,
    data: LoanGuarantorCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LoanGuarantorResponse:
    """Add a guarantor to a loan."""
    service = LoanService(db)
    try:
        guarantor = await service.add_guarantor(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            data=data.model_dump(),
        )
        return LoanGuarantorResponse(
            id=guarantor.id,
            loan_id=guarantor.loan_id,
            guarantor_staff_id=guarantor.guarantor_staff_id,
            relationship=guarantor.relationship_desc,
            guaranteed_amount=guarantor.guaranteed_amount,
            consent_given=guarantor.consent_given,
            consent_date=guarantor.consent_date,
            notes=guarantor.notes,
            created_at=guarantor.created_at,
        )
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/loans/{loan_id}/guarantors/{guarantor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove guarantor",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.request")),
    ],
)
async def remove_guarantor(
    loan_id: UUID,
    guarantor_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
):
    """Remove a guarantor from a draft loan."""
    service = LoanService(db)
    try:
        await service.remove_guarantor(tenant.tenant_id, loan_id, guarantor_id)
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/loans/{loan_id}/guarantors/{guarantor_id}/consent",
    response_model=LoanGuarantorResponse,
    summary="Record guarantor consent",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.approve")),
    ],
)
async def update_guarantor_consent(
    loan_id: UUID,
    guarantor_id: UUID,
    data: LoanGuarantorConsentRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> LoanGuarantorResponse:
    """Record or revoke guarantor consent."""
    service = LoanService(db)
    try:
        guarantor = await service.update_guarantor_consent(
            tenant_id=tenant.tenant_id,
            loan_id=loan_id,
            guarantor_id=guarantor_id,
            consent_given=data.consent_given,
            notes=data.notes,
        )
        return LoanGuarantorResponse(
            id=guarantor.id,
            loan_id=guarantor.loan_id,
            guarantor_staff_id=guarantor.guarantor_staff_id,
            relationship=guarantor.relationship_desc,
            guaranteed_amount=guarantor.guaranteed_amount,
            consent_given=guarantor.consent_given,
            consent_date=guarantor.consent_date,
            notes=guarantor.notes,
            created_at=guarantor.created_at,
        )
    except LoanService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# 6.6 Staff View (2 endpoints)
# ======================================================================


@router.get(
    "/staff/{staff_id}/loans",
    response_model=list[LoanListItem],
    summary="List staff loans",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def get_staff_loans(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[LoanListItem]:
    """Get all loans for a staff member."""
    service = LoanService(db)
    loans = await service.get_staff_loans(tenant.tenant_id, staff_id)
    return [_build_loan_list_item(l) for l in loans]


@router.get(
    "/staff/{staff_id}/loan-eligibility",
    response_model=LoanEligibilityResponse,
    summary="Check loan eligibility",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def check_eligibility(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    loan_type_id: Optional[UUID] = Query(None),
) -> LoanEligibilityResponse:
    """Check if a staff member is eligible for a loan."""
    service = LoanService(db)
    result = await service.check_eligibility(
        tenant_id=tenant.tenant_id,
        staff_id=staff_id,
        loan_type_id=loan_type_id,
    )
    return LoanEligibilityResponse(**result)


# ======================================================================
# 6.7 Reports (aging report endpoints — portfolio routes registered above)
# ======================================================================


@router.get(
    "/reports/loan-aging",
    response_model=LoanAgingResponse,
    summary="Loan aging report",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def get_aging_report(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None),
) -> LoanAgingResponse:
    """Get loan aging report with 30/60/90/120+ day buckets."""
    service = LoanService(db)
    result = await service.get_aging_report(tenant.tenant_id, school_id)
    return LoanAgingResponse(**result)


@router.get(
    "/reports/loan-aging/export",
    summary="Export loan aging report",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.loans.read")),
    ],
)
async def export_aging_report(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    school_id: Optional[UUID] = Query(None),
) -> StreamingResponse:
    """Export loan aging report as CSV."""
    import csv
    from io import StringIO

    service = LoanService(db)
    result = await service.get_aging_report(tenant.tenant_id, school_id)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Bucket", "Loan Number", "Staff Name", "Principal",
        "Outstanding", "Overdue Amount", "Days Overdue",
    ])
    for bucket in result["buckets"]:
        for loan_data in bucket["loans"]:
            writer.writerow([
                bucket["bucket"],
                loan_data.get("loan_number", ""),
                loan_data.get("staff_name", ""),
                str(loan_data.get("principal_amount", "")),
                str(loan_data.get("outstanding_balance", "")),
                str(loan_data.get("overdue_amount", "")),
                loan_data.get("max_days_overdue", ""),
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=loan_aging_report.csv"},
    )

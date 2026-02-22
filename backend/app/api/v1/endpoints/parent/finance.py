"""
SIMS Plus - Parent Portal Finance Endpoints

Endpoints for parents to view their children's invoices, payment history,
and fee statements. Parents can only see issued/active invoices (not drafts)
and completed, non-voided payments.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.parent import (
    FeeStatement,
    ParentInvoiceDetail,
    ParentInvoiceSummary,
    ParentPaymentSummary,
)
from app.services.parent import (
    ParentFinanceService,
    ParentServiceError,
)

from ._helpers import _get_user_id, _handle_parent_error

router = APIRouter()


@router.get(
    "/children/{student_id}/invoices",
    response_model=list[ParentInvoiceSummary],
    summary="List child invoices",
    dependencies=[Depends(require_permissions("parent.finance.read"))],
)
async def list_child_invoices(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ParentInvoiceSummary]:
    """
    Get all non-draft invoices for a child.

    Draft invoices are internal workflow state and not visible to parents.
    Returns invoices ordered by creation date, most recent first.
    """
    user_id = _get_user_id(user)
    service = ParentFinanceService(db)

    try:
        results = await service.get_child_invoices(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return [ParentInvoiceSummary(**item) for item in results]


@router.get(
    "/children/{student_id}/invoices/{invoice_id}",
    response_model=ParentInvoiceDetail,
    summary="Get invoice detail",
    dependencies=[Depends(require_permissions("parent.finance.read"))],
)
async def get_child_invoice_detail(
    student_id: UUID,
    invoice_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ParentInvoiceDetail:
    """
    Get full invoice detail with line items, payments, and scholarship info.

    Includes IDOR check to verify the invoice belongs to the specified student.
    """
    user_id = _get_user_id(user)
    service = ParentFinanceService(db)

    try:
        result = await service.get_child_invoice_detail(
            user_id=user_id,
            student_id=student_id,
            invoice_id=invoice_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return ParentInvoiceDetail(**result)


@router.get(
    "/children/{student_id}/fee-statement",
    response_model=FeeStatement,
    summary="Get fee statement",
    dependencies=[Depends(require_permissions("parent.finance.read"))],
)
async def get_child_fee_statement(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    term_id: UUID | None = Query(
        None, description="Optional term filter. Omit for all-term aggregate."
    ),
) -> FeeStatement:
    """
    Get a complete fee statement: total billed, paid, credits, and outstanding.

    If term_id is provided, scopes to that term only. Otherwise, aggregates
    across all terms for a comprehensive financial view.
    """
    user_id = _get_user_id(user)
    service = ParentFinanceService(db)

    try:
        result = await service.get_child_fee_statement(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
            term_id=term_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return FeeStatement(**result)


@router.get(
    "/children/{student_id}/payments",
    response_model=list[ParentPaymentSummary],
    summary="Get payment history",
    dependencies=[Depends(require_permissions("parent.finance.read"))],
)
async def get_child_payment_history(
    student_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[ParentPaymentSummary]:
    """
    Get all completed, non-voided payments for a child.

    Returns payments ordered by date, most recent first.
    Voided and failed payments are excluded from the parent view.
    """
    user_id = _get_user_id(user)
    service = ParentFinanceService(db)

    try:
        results = await service.get_child_payment_history(
            user_id=user_id,
            student_id=student_id,
            tenant_id=tenant.tenant_id,
        )
    except ParentServiceError as e:
        raise _handle_parent_error(e)

    return [ParentPaymentSummary(**item) for item in results]

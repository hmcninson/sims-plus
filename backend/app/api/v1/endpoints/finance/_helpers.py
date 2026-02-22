"""
SIMS Plus - Finance Endpoint Helpers

Shared helper functions used across finance endpoint modules.
"""

from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.schemas.finance import (
    CreditNoteWithDetailsResponse,
    FeeItemResponse,
    FeeStructureWithItemsResponse,
    InvoiceItemResponse,
    InvoiceResponse,
    InvoiceScholarshipItemResponse,
    InvoiceWithDetailsResponse,
    PaymentResponse,
    PaymentWithDetailsResponse,
    ScholarshipWithStatsResponse,
    StudentScholarshipWithDetailsResponse,
)


async def get_school_for_tenant(db: AsyncSession, tenant_id: UUID) -> School:
    """
    Fetch the first school for a tenant.

    Raises ValueError if no school is found.
    """
    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant_id).limit(1)
    )
    school = school_result.scalar_one_or_none()
    if not school:
        raise ValueError("No school found for this tenant")
    return school


def _build_fee_structure_response(fs) -> FeeStructureWithItemsResponse:
    """Build fee structure response with items."""
    total = sum(item.amount for item in fs.items if not item.is_optional)

    # Build fee item responses with fee_type_name
    fee_items = []
    for item in fs.items:
        fee_item_response = FeeItemResponse(
            id=item.id,
            tenant_id=item.tenant_id,
            fee_structure_id=item.fee_structure_id,
            fee_type_id=item.fee_type_id,
            fee_type_name=item.fee_type.name if item.fee_type else None,
            name=item.name,
            description=item.description,
            amount=item.amount,
            is_optional=item.is_optional,
            sequence=item.sequence,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        fee_items.append(fee_item_response)

    return FeeStructureWithItemsResponse(
        id=fs.id,
        tenant_id=fs.tenant_id,
        school_id=fs.school_id,
        name=fs.name,
        description=fs.description,
        academic_year_id=fs.academic_year_id,
        term_id=fs.term_id,
        class_id=fs.class_id,
        level=fs.level,
        level_category=fs.level_category,
        student_type=fs.student_type,
        is_active=fs.is_active,
        created_at=fs.created_at,
        updated_at=fs.updated_at,
        items=fee_items,
        total_amount=total,
        academic_year_name=fs.academic_year.name if fs.academic_year else None,
        term_name=fs.term.name if fs.term else None,
        class_name=fs.class_.name if fs.class_ else None,
    )


def _build_invoice_response_basic(inv) -> InvoiceResponse:
    """Build basic invoice response."""
    return InvoiceResponse(
        id=inv.id,
        tenant_id=inv.tenant_id,
        school_id=inv.school_id,
        invoice_number=inv.invoice_number,
        student_id=inv.student_id,
        fee_structure_id=inv.fee_structure_id,
        academic_year_id=inv.academic_year_id,
        term_id=inv.term_id,
        subtotal=inv.subtotal,
        discount_amount=inv.discount_amount,
        scholarship_discount=inv.scholarship_discount,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        amount_paid=inv.amount_paid,
        balance=inv.balance,
        status=inv.status.value,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        currency=inv.currency,
        notes=inv.notes,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


def _is_relationship_loaded(obj, attr_name: str) -> bool:
    """Check if a SQLAlchemy relationship is loaded without triggering lazy load."""
    insp = inspect(obj)
    return attr_name in insp.dict


def _build_invoice_response(inv) -> InvoiceWithDetailsResponse:
    """Build invoice response with details."""
    # Build payment responses for completed payments (only if loaded)
    payments = []
    # Only access payments if the relationship was eagerly loaded
    if _is_relationship_loaded(inv, "payments"):
        for p in inv.payments:
            if not p.is_voided:  # Only include non-voided payments
                payments.append(
                    PaymentResponse(
                        id=p.id,
                        tenant_id=p.tenant_id,
                        school_id=p.school_id,
                        receipt_number=p.receipt_number,
                        invoice_id=p.invoice_id,
                        student_id=p.student_id,
                        amount=p.amount,
                        currency=p.currency,
                        payment_method=p.payment_method.value,
                        momo_phone=p.momo_phone,
                        momo_transaction_id=p.momo_transaction_id,
                        momo_provider=p.momo_provider,
                        bank_name=p.bank_name,
                        bank_reference=p.bank_reference,
                        cheque_number=p.cheque_number,
                        payer_name=p.payer_name,
                        payer_phone=p.payer_phone,
                        payer_email=p.payer_email,
                        status=p.status.value,
                        payment_date=p.payment_date,
                        notes=p.notes,
                        is_voided=p.is_voided,
                        created_at=p.created_at,
                        updated_at=p.updated_at,
                    )
                )

    # Build scholarship item responses (only if loaded)
    scholarship_items = []
    if _is_relationship_loaded(inv, "scholarship_items"):
        for si in inv.scholarship_items:
            scholarship_items.append(
                InvoiceScholarshipItemResponse(
                    id=si.id,
                    tenant_id=si.tenant_id,
                    invoice_id=si.invoice_id,
                    student_scholarship_id=si.student_scholarship_id,
                    scholarship_id=si.scholarship_id,
                    scholarship_name=si.scholarship_name,
                    scholarship_code=si.scholarship_code,
                    coverage_type=si.coverage_type,
                    coverage_value=si.coverage_value,
                    calculated_amount=si.calculated_amount,
                    applicable_subtotal=si.applicable_subtotal,
                    created_at=si.created_at,
                )
            )

    return InvoiceWithDetailsResponse(
        id=inv.id,
        tenant_id=inv.tenant_id,
        school_id=inv.school_id,
        invoice_number=inv.invoice_number,
        student_id=inv.student_id,
        fee_structure_id=inv.fee_structure_id,
        academic_year_id=inv.academic_year_id,
        term_id=inv.term_id,
        subtotal=inv.subtotal,
        discount_amount=inv.discount_amount,
        scholarship_discount=inv.scholarship_discount,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        amount_paid=inv.amount_paid,
        balance=inv.balance,
        status=inv.status.value,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        currency=inv.currency,
        notes=inv.notes,
        # Adjustment tracking
        adjustment_for_invoice_id=inv.adjustment_for_invoice_id
        if hasattr(inv, "adjustment_for_invoice_id")
        else None,
        adjustment_type=inv.adjustment_type
        if hasattr(inv, "adjustment_type")
        else None,
        adjustment_reason=inv.adjustment_reason
        if hasattr(inv, "adjustment_reason")
        else None,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        student_name=f"{inv.student.first_name} {inv.student.last_name}"
        if inv.student
        else "Unknown",
        student_id_number=inv.student.student_id if inv.student else "",
        class_name=inv.student.class_.name
        if inv.student and inv.student.class_
        else None,
        academic_year_name=inv.academic_year.name if inv.academic_year else "",
        term_name=inv.term.name if inv.term else "",
        items=[
            InvoiceItemResponse.model_validate(item) for item in inv.items
        ]
        if hasattr(inv, "items")
        else [],
        scholarship_items=scholarship_items,
        payments=payments,
    )


def _build_payment_response(p) -> PaymentWithDetailsResponse:
    """Build payment response with details."""
    return PaymentWithDetailsResponse(
        id=p.id,
        tenant_id=p.tenant_id,
        school_id=p.school_id,
        receipt_number=p.receipt_number,
        invoice_id=p.invoice_id,
        student_id=p.student_id,
        amount=p.amount,
        currency=p.currency,
        payment_method=p.payment_method.value,
        momo_phone=p.momo_phone,
        momo_transaction_id=p.momo_transaction_id,
        momo_provider=p.momo_provider,
        bank_name=p.bank_name,
        bank_reference=p.bank_reference,
        cheque_number=p.cheque_number,
        payer_name=p.payer_name,
        payer_phone=p.payer_phone,
        payer_email=p.payer_email,
        status=p.status.value,
        payment_date=p.payment_date,
        notes=p.notes,
        is_voided=p.is_voided,
        created_at=p.created_at,
        updated_at=p.updated_at,
        student_name=f"{p.student.first_name} {p.student.last_name}"
        if p.student
        else "Unknown",
        student_id_number=p.student.student_id if p.student else "",
        invoice_number=p.invoice.invoice_number if p.invoice else None,
        recorded_by_name=f"{p.recorded_by_user.first_name} {p.recorded_by_user.last_name}"
        if p.recorded_by_user
        else None,
    )


def _build_scholarship_response(s) -> ScholarshipWithStatsResponse:
    """Build scholarship response with stats."""
    from app.models.finance import ScholarshipStatus

    active_count = (
        len([r for r in s.recipients if r.status == ScholarshipStatus.ACTIVE])
        if hasattr(s, "recipients")
        else 0
    )
    total_count = len(s.recipients) if hasattr(s, "recipients") else 0

    return ScholarshipWithStatsResponse(
        id=s.id,
        tenant_id=s.tenant_id,
        school_id=s.school_id,
        name=s.name,
        code=s.code,
        description=s.description,
        scholarship_type=s.scholarship_type.value,
        coverage_type=s.coverage_type.value,
        coverage_value=s.coverage_value,
        applicable_fees=s.applicable_fees,
        max_recipients=s.max_recipients,
        academic_year_id=s.academic_year_id,
        eligibility_criteria=s.eligibility_criteria,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
        recipients_count=total_count,
        active_recipients_count=active_count,
        academic_year_name=s.academic_year.name if s.academic_year else None,
    )


def _build_student_scholarship_response(ss) -> StudentScholarshipWithDetailsResponse:
    """Build student scholarship response with details."""
    return StudentScholarshipWithDetailsResponse(
        id=ss.id,
        tenant_id=ss.tenant_id,
        scholarship_id=ss.scholarship_id,
        student_id=ss.student_id,
        academic_year_id=ss.academic_year_id,
        awarded_by=ss.awarded_by,
        awarded_at=ss.awarded_at,
        status=ss.status.value,
        effective_from=ss.effective_from,
        effective_to=ss.effective_to,
        coverage_override=ss.coverage_override,
        notes=ss.notes,
        # Enhanced award settings
        justification=ss.justification,
        renewal_type=ss.renewal_type or "one_time",
        is_provisional=ss.is_provisional or False,
        provisional_conditions=ss.provisional_conditions,
        # Revocation info
        revoked_at=ss.revoked_at,
        revoked_by=ss.revoked_by,
        revoke_reason=ss.revoke_reason,
        # Reinstatement tracking
        reinstated_from=ss.reinstated_from,
        created_at=ss.created_at,
        updated_at=ss.updated_at,
        scholarship_name=ss.scholarship.name if ss.scholarship else "",
        scholarship_code=ss.scholarship.code if ss.scholarship else "",
        scholarship_type=ss.scholarship.scholarship_type.value
        if ss.scholarship
        else "",
        coverage_type=ss.scholarship.coverage_type.value if ss.scholarship else "",
        coverage_value=ss.scholarship.coverage_value if ss.scholarship else 0,
        student_name=f"{ss.student.first_name} {ss.student.last_name}"
        if ss.student
        else "Unknown",
        student_id_number=ss.student.student_id if ss.student else "",
        academic_year_name=ss.academic_year.name if ss.academic_year else "",
        awarded_by_name=f"{ss.awarded_by_user.first_name} {ss.awarded_by_user.last_name}"
        if ss.awarded_by_user
        else None,
    )


def _build_credit_note_response(cn) -> CreditNoteWithDetailsResponse:
    """Build credit note response with details."""
    # Calculate remaining amount
    remaining = cn.amount - (cn.applied_amount or 0)

    return CreditNoteWithDetailsResponse(
        id=cn.id,
        tenant_id=cn.tenant_id,
        school_id=cn.school_id,
        credit_note_number=cn.credit_note_number,
        credit_note_type=cn.credit_note_type.value,
        original_invoice_id=cn.original_invoice_id,
        student_id=cn.student_id,
        amount=cn.amount,
        currency=cn.currency,
        reason=cn.reason,
        status=cn.status.value,
        issued_by=cn.issued_by,
        issued_at=cn.issued_at,
        applied_to_invoice_id=cn.applied_to_invoice_id,
        applied_amount=cn.applied_amount,
        applied_by=cn.applied_by,
        applied_at=cn.applied_at,
        refund_method=cn.refund_method,
        refund_reference=cn.refund_reference,
        refunded_by=cn.refunded_by,
        refunded_at=cn.refunded_at,
        cancelled_by=cn.cancelled_by,
        cancelled_at=cn.cancelled_at,
        cancel_reason=cn.cancel_reason,
        notes=cn.notes,
        remaining_amount=remaining,
        created_at=cn.created_at,
        updated_at=cn.updated_at,
        student_name=f"{cn.student.first_name} {cn.student.last_name}"
        if cn.student
        else "Unknown",
        student_id_number=cn.student.student_id if cn.student else "",
        original_invoice_number=cn.original_invoice.invoice_number
        if cn.original_invoice
        else None,
        applied_to_invoice_number=cn.applied_to_invoice.invoice_number
        if cn.applied_to_invoice
        else None,
        issued_by_name=f"{cn.issued_by_user.first_name} {cn.issued_by_user.last_name}"
        if cn.issued_by_user
        else None,
        applied_by_name=f"{cn.applied_by_user.first_name} {cn.applied_by_user.last_name}"
        if hasattr(cn, "applied_by_user") and cn.applied_by_user
        else None,
        refunded_by_name=f"{cn.refunded_by_user.first_name} {cn.refunded_by_user.last_name}"
        if hasattr(cn, "refunded_by_user") and cn.refunded_by_user
        else None,
    )


def amount_to_words(amount: float, currency: str = "Ghana Cedis") -> str:
    """Convert numeric amount to words."""
    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = [
        "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty",
        "Ninety",
    ]

    def convert_less_than_thousand(n: int) -> str:
        if n == 0:
            return ""
        elif n < 20:
            return ones[n]
        elif n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
        else:
            return (
                ones[n // 100]
                + " Hundred"
                + (
                    " and " + convert_less_than_thousand(n % 100)
                    if n % 100 != 0
                    else ""
                )
            )

    def convert(n: int) -> str:
        if n == 0:
            return "Zero"

        result = ""
        if n >= 1000000:
            result += convert_less_than_thousand(n // 1000000) + " Million "
            n %= 1000000
        if n >= 1000:
            result += convert_less_than_thousand(n // 1000) + " Thousand "
            n %= 1000
        if n > 0:
            if result:
                result += "and "
            result += convert_less_than_thousand(n)

        return result.strip()

    # Split into cedis and pesewas
    cedis = int(amount)
    pesewas = round((amount - cedis) * 100)

    result = convert(cedis) + f" {currency}"
    if pesewas > 0:
        result += " and " + convert(pesewas) + " Pesewas"
    result += " Only"

    return result

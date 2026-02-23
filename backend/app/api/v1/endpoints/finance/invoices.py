"""
SIMS Plus - Invoice Endpoints

Endpoints for invoice management: CRUD, bulk generation, sync, email, PDF, overdue.
"""

import csv
import io
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse

from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from app.api.deps import (
    CurrentUserId,
    DatabaseSession,
    OptionalSchoolCtx,
    RequestTenant,
    SchoolCtx,
    require_permissions,
)
from app.models.finance import FeeStructure, Invoice
from app.models.academic import AcademicYear, Term, Class, ClassSection
from app.models.school import School
from app.models.student import Student, Guardian, StudentGuardian
from app.schemas.finance import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceWithDetailsResponse,
    InvoiceListResponse,
    InvoiceBulkGenerate,
    InvoiceBulkResult,
    InvoiceIssue,
    InvoiceCancel,
    InvoiceWriteOff,
    InvoiceEmailRequest,
    InvoiceEmailResponse,
    StudentMissingInvoice,
    StudentsMissingInvoicesResponse,
    InvoiceSyncRequest,
    InvoiceSyncPreview,
    InvoiceSyncResult,
)
from app.services.finance import InvoiceService, FinanceAuditService, FinanceServiceError

from ._helpers import (
    _build_invoice_response,
    _build_invoice_response_basic,
)

router = APIRouter()


@router.post(
    "/invoices",
    response_model=InvoiceWithDetailsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invoice",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def create_invoice(
    data: InvoiceCreate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceWithDetailsResponse:
    """Create a new invoice."""
    service = InvoiceService(db)
    try:
        invoice = await service.create_invoice(
            tenant_id=school_ctx.tenant_id,
            school_id=school_ctx.school_id,
            student_id=data.student_id,
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            fee_structure_id=data.fee_structure_id,
            due_date=data.due_date,
            discount_amount=data.discount_amount,
            notes=data.notes,
            items=[item.model_dump() for item in data.items] if data.items else None,
            created_by=UUID(user_id),
        )
        # Reload with details
        invoice = await service.get_invoice(school_ctx.tenant_id, invoice.id)
        # Log audit trail for invoice creation
        audit_service = FinanceAuditService(db)
        await audit_service.log_create(
            tenant_id=school_ctx.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            performed_by=UUID(user_id),
            metadata={"invoice_number": invoice.invoice_number, "student_id": str(data.student_id)},
        )
        return _build_invoice_response(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def list_invoices(
    tenant: RequestTenant,
    db: DatabaseSession,
    school_ctx: OptionalSchoolCtx,
    student_id: Optional[UUID] = Query(None),
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    invoice_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    """List all invoices with filters and search."""
    # Chain support: scope to active school when header is present
    school_id = school_ctx.school_id if school_ctx else None
    service = InvoiceService(db)
    invoices, total = await service.list_invoices(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        status=invoice_status,
        search=search,
        page=page,
        page_size=page_size,
    )

    return InvoiceListResponse(
        items=[_build_invoice_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


# --- Specific invoice routes (must come before {invoice_id} routes) ---


@router.post(
    "/invoices/bulk-generate",
    response_model=InvoiceBulkResult,
    summary="Bulk generate invoices",
    dependencies=[Depends(require_permissions("finance.create"))],
)
async def bulk_generate_invoices(
    data: InvoiceBulkGenerate,
    school_ctx: SchoolCtx,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceBulkResult:
    """Bulk generate invoices for students."""
    service = InvoiceService(db)
    result = await service.bulk_generate_invoices(
        tenant_id=school_ctx.tenant_id,
        school_id=school_ctx.school_id,
        fee_structure_id=data.fee_structure_id,
        academic_year_id=data.academic_year_id,
        term_id=data.term_id,
        class_id=data.class_id,
        section_id=data.section_id,
        due_date=data.due_date,
        student_ids=data.student_ids,
        created_by=UUID(user_id),
        issue_immediately=data.issue_immediately,
    )
    return InvoiceBulkResult(**result)


@router.get(
    "/invoices/sync-preview",
    response_model=InvoiceSyncPreview,
    summary="Preview invoice sync with fee structure",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_invoice_sync_preview(
    tenant: RequestTenant,
    db: DatabaseSession,
    fee_structure_id: UUID = Query(..., description="Fee structure ID"),
    academic_year_id: UUID = Query(..., description="Academic year ID"),
    term_id: UUID = Query(..., description="Term ID"),
) -> InvoiceSyncPreview:
    """
    Get preview of how many invoices would be affected by syncing with fee structure.

    Returns counts of:
    - Draft invoices (can be synced)
    - Issued/Partial/Paid invoices (cannot be synced)
    - New fee structure total amount
    """
    service = InvoiceService(db)
    result = await service.get_invoices_sync_preview(
        tenant_id=tenant.tenant_id,
        fee_structure_id=fee_structure_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
    )
    return InvoiceSyncPreview(**result)


@router.post(
    "/invoices/sync",
    response_model=InvoiceSyncResult,
    summary="Sync draft invoices with fee structure",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def sync_invoices_with_fee_structure(
    data: InvoiceSyncRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> InvoiceSyncResult:
    """
    Sync draft invoices with the current fee structure.

    This will:
    - Update all DRAFT invoices to match the current fee structure items and amounts
    - Recalculate totals including scholarship discounts
    - Skip issued, partial, and paid invoices (they are not modified)

    Use this after updating a fee structure to apply changes to existing draft invoices.
    """
    service = InvoiceService(db)
    result = await service.sync_invoices_with_fee_structure(
        tenant_id=tenant.tenant_id,
        fee_structure_id=data.fee_structure_id,
        academic_year_id=data.academic_year_id,
        term_id=data.term_id,
    )
    return InvoiceSyncResult(**result)


@router.get(
    "/invoices/missing",
    response_model=StudentsMissingInvoicesResponse,
    summary="Get students missing invoices",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_students_missing_invoices(
    tenant: RequestTenant,
    db: DatabaseSession,
    fee_structure_id: UUID = Query(..., description="Fee structure to check against"),
    academic_year_id: UUID = Query(..., description="Academic year"),
    term_id: UUID = Query(..., description="Term"),
    class_id: Optional[UUID] = Query(None, description="Filter by specific class"),
    section_id: Optional[UUID] = Query(None, description="Filter by specific section"),
) -> StudentsMissingInvoicesResponse:
    """
    Get students who match the fee structure criteria but don't have
    an invoice for the specified academic year and term.

    Useful for finding late enrollees or students who were missed during bulk generation.
    """
    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
    fee_structure_result = await db.execute(
        select(FeeStructure).where(
            FeeStructure.id == fee_structure_id,
            FeeStructure.tenant_id == tenant.tenant_id,
            FeeStructure.deleted_at.is_(None),
        )
    )
    fee_structure = fee_structure_result.scalar_one_or_none()
    if not fee_structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fee structure not found",
        )

    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
    year_result = await db.execute(
        select(AcademicYear).where(
            AcademicYear.id == academic_year_id,
            AcademicYear.tenant_id == tenant.tenant_id,
        )
    )
    academic_year = year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic year not found",
        )

    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
    term_result = await db.execute(
        select(Term).where(
            Term.id == term_id,
            Term.tenant_id == tenant.tenant_id,
        )
    )
    term = term_result.scalar_one_or_none()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Term not found",
        )

    service = InvoiceService(db)
    students = await service.get_students_missing_invoices(
        tenant_id=tenant.tenant_id,
        fee_structure_id=fee_structure_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        class_id=class_id,
        section_id=section_id,
    )

    # Build response with class/section names
    student_items = []
    for student in students:
        class_name = None
        section_name = None

        if student.class_id:
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            class_result = await db.execute(
                select(Class).where(
                    Class.id == student.class_id,
                    Class.tenant_id == tenant.tenant_id,
                )
            )
            cls = class_result.scalar_one_or_none()
            if cls:
                class_name = cls.name

        if student.section_id:
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            section_result = await db.execute(
                select(ClassSection).where(
                    ClassSection.id == student.section_id,
                    ClassSection.tenant_id == tenant.tenant_id,
                )
            )
            section = section_result.scalar_one_or_none()
            if section:
                section_name = section.name

        student_items.append(
            StudentMissingInvoice(
                id=student.id,
                student_id=student.student_id,
                first_name=student.first_name,
                middle_name=student.middle_name,
                last_name=student.last_name,
                class_id=student.class_id,
                class_name=class_name,
                section_id=student.section_id,
                section_name=section_name,
            )
        )

    return StudentsMissingInvoicesResponse(
        students=student_items,
        total=len(student_items),
        fee_structure_name=fee_structure.name,
        academic_year_name=academic_year.name,
        term_name=term.name,
    )


@router.post(
    "/invoices/update-overdue",
    summary="Update overdue invoices",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_overdue_invoices(
    tenant: RequestTenant,
    db: DatabaseSession,
) -> dict:
    """
    Update status of invoices that have passed their due date.

    Marks ISSUED or PARTIAL invoices as OVERDUE if their due date has passed.
    This endpoint can be called manually or scheduled via a cron job/Celery task.

    Returns count of invoices updated.
    """
    service = InvoiceService(db)
    result = await service.update_overdue_invoices(tenant.tenant_id)
    return {
        "message": f"Updated {result['updated']} invoices to OVERDUE status",
        "updated": result["updated"],
        "checked": result["checked"],
    }


@router.get(
    "/invoices/export",
    summary="Export invoices as CSV",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def export_invoices_csv(
    tenant: RequestTenant,
    db: DatabaseSession,
    school_ctx: OptionalSchoolCtx,
    academic_year_id: Optional[UUID] = Query(None),
    term_id: Optional[UUID] = Query(None),
    invoice_status: Optional[str] = Query(None, alias="status"),
    class_id: Optional[UUID] = Query(None),
) -> StreamingResponse:
    """Export invoices as CSV file."""
    # Chain support: scope to active school when header is present
    school_id = school_ctx.school_id if school_ctx else None
    service = InvoiceService(db)
    rows = await service.export_invoices_csv(
        tenant_id=tenant.tenant_id,
        academic_year_id=academic_year_id,
        term_id=term_id,
        status=invoice_status,
        class_id=class_id,
        school_id=school_id,
    )

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    else:
        writer = csv.DictWriter(
            output,
            fieldnames=["invoice_number", "student_name", "student_id_number",
                        "total_amount", "amount_paid", "balance", "status",
                        "due_date", "created_at"],
        )
        writer.writeheader()

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="invoices_export.csv"'},
    )


# --- Parameterized invoice routes ---


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceWithDetailsResponse,
    summary="Get invoice",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_invoice(
    invoice_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> InvoiceWithDetailsResponse:
    """Get invoice by ID."""
    service = InvoiceService(db)
    invoice = await service.get_invoice(tenant.tenant_id, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return _build_invoice_response(invoice)


@router.put(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """Update invoice (draft only)."""
    service = InvoiceService(db)
    try:
        invoice = await service.update_invoice(
            tenant.tenant_id,
            invoice_id,
            **data.model_dump(exclude_unset=True),
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        # Log audit trail for invoice update
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action="update",
            performed_by=UUID(user_id),
            metadata=data.model_dump(exclude_unset=True),
        )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete invoice",
    dependencies=[Depends(require_permissions("finance.delete"))],
)
async def delete_invoice(
    invoice_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> None:
    """Delete invoice (draft only)."""
    service = InvoiceService(db)
    try:
        if not await service.delete_invoice(tenant.tenant_id, invoice_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        # Log audit trail for invoice deletion (soft delete)
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="invoice",
            entity_id=invoice_id,
            action="delete",
            performed_by=UUID(user_id),
        )
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/invoices/{invoice_id}/issue",
    response_model=InvoiceResponse,
    summary="Issue invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def issue_invoice(
    invoice_id: UUID,
    data: InvoiceIssue,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """Issue a draft invoice."""
    service = InvoiceService(db)
    try:
        invoice = await service.issue_invoice(
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
            issued_by=UUID(user_id),
            issue_date=data.issue_date,
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        # Log audit trail for invoice issuance
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action="issue",
            performed_by=UUID(user_id),
            metadata={"invoice_number": invoice.invoice_number},
        )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel invoice",
    dependencies=[Depends(require_permissions("finance.update"))],
)
async def cancel_invoice(
    invoice_id: UUID,
    data: InvoiceCancel,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """Cancel an invoice."""
    service = InvoiceService(db)
    try:
        invoice = await service.cancel_invoice(
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
            cancelled_by=UUID(user_id),
            reason=data.reason,
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        # Log audit trail for invoice cancellation
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action="cancel",
            performed_by=UUID(user_id),
            reason=data.reason,
        )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post(
    "/invoices/{invoice_id}/write-off",
    response_model=InvoiceResponse,
    summary="Write off invoice",
    description="Write off an overdue invoice as uncollectible. This is a terminal state.",
    dependencies=[Depends(require_permissions("finance.delete"))],  # Higher permission required
)
async def write_off_invoice(
    invoice_id: UUID,
    data: InvoiceWriteOff,
    tenant: RequestTenant,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> InvoiceResponse:
    """
    Write off an overdue invoice as uncollectible.

    Only OVERDUE invoices can be written off. This is a terminal state -
    the invoice cannot be recovered after write-off.
    """
    service = InvoiceService(db)
    try:
        invoice = await service.write_off_invoice(
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
            written_off_by=UUID(user_id),
            reason=data.reason,
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        # Log audit trail for invoice write-off
        audit_service = FinanceAuditService(db)
        await audit_service.log(
            tenant_id=tenant.tenant_id,
            entity_type="invoice",
            entity_id=invoice.id,
            action="write_off",
            performed_by=UUID(user_id),
            reason=data.reason,
        )
        return _build_invoice_response_basic(invoice)
    except FinanceServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/invoices/{invoice_id}/pdf",
    summary="Download invoice PDF",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def download_invoice_pdf(
    invoice_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> Response:
    """Download invoice as PDF."""
    from app.services.pdf import PDFService

    try:
        pdf_bytes, filename = await PDFService.generate_invoice_pdf(
            db=db,
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/invoices/{invoice_id}/email",
    response_model=InvoiceEmailResponse,
    summary="Send invoice via email",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def email_invoice(
    invoice_id: UUID,
    data: InvoiceEmailRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
) -> InvoiceEmailResponse:
    """Send invoice via email with PDF attachment."""
    from app.services.pdf import PDFService
    from app.services.email import email_service

    # Fetch the invoice with related data
    invoice_result = await db.execute(
        select(Invoice)
        .where(
            and_(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant.tenant_id,
                Invoice.deleted_at.is_(None),
            )
        )
        .options(
            joinedload(Invoice.student),
            joinedload(Invoice.academic_year),
            joinedload(Invoice.term),
        )
    )
    invoice = invoice_result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    student = invoice.student
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Fetch school
    school_result = await db.execute(
        select(School).where(School.tenant_id == tenant.tenant_id)
    )
    school = school_result.scalar_one_or_none()
    school_name = school.name if school else "School"

    # Get recipient name - use provided name or try to get guardian name
    recipient_name = data.recipient_name
    if not recipient_name:
        # Try to get primary guardian
        guardian_link_result = await db.execute(
            select(StudentGuardian)
            .where(
                and_(
                    StudentGuardian.student_id == student.id,
                    StudentGuardian.is_primary == True,
                )
            )
        )
        guardian_link = guardian_link_result.scalar_one_or_none()
        if guardian_link:
            guardian_result = await db.execute(
                select(Guardian).where(Guardian.id == guardian_link.guardian_id)
            )
            guardian = guardian_result.scalar_one_or_none()
            if guardian:
                recipient_name = f"{guardian.first_name} {guardian.last_name}"

        if not recipient_name:
            recipient_name = "Parent/Guardian"

    # Generate PDF
    try:
        pdf_bytes, pdf_filename = await PDFService.generate_invoice_pdf(
            db=db,
            tenant_id=tenant.tenant_id,
            invoice_id=invoice_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}",
        )

    # Format student name
    student_name = f"{student.first_name}"
    if student.middle_name:
        student_name += f" {student.middle_name}"
    student_name += f" {student.last_name}"

    # Format due date
    due_date = invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else None

    # Calculate balance
    balance_due = float(invoice.total_amount) - float(invoice.amount_paid)

    # Send email
    success = await email_service.send_invoice_email(
        to_email=data.email,
        recipient_name=recipient_name,
        student_name=student_name,
        invoice_number=invoice.invoice_number,
        total_amount=float(invoice.total_amount),
        balance_due=balance_due,
        currency=invoice.currency or "GHS",
        due_date=due_date,
        school_name=school_name,
        pdf_data=pdf_bytes,
        pdf_filename=pdf_filename,
        cc_emails=data.cc_emails,
    )

    cc_info = f" (CC: {', '.join(data.cc_emails)})" if data.cc_emails else ""
    if success:
        return InvoiceEmailResponse(
            success=True,
            message=f"Invoice sent successfully to {data.email}{cc_info}",
            email=data.email,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email. Please check email configuration.",
        )


@router.get(
    "/students/{student_id}/invoices",
    response_model=InvoiceListResponse,
    summary="Get student invoices",
    dependencies=[Depends(require_permissions("finance.read"))],
)
async def get_student_invoices(
    student_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    academic_year_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    """Get all invoices for a student."""
    service = InvoiceService(db)
    invoices, total = await service.list_invoices(
        tenant_id=tenant.tenant_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        page=page,
        page_size=page_size,
    )

    return InvoiceListResponse(
        items=[_build_invoice_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )

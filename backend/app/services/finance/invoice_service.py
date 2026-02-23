"""
SIMS Plus - Invoice Service

Business logic for invoice management including generation, syncing, and status workflows.
"""

from datetime import datetime, UTC, date
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, and_, func, desc, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.notification import NotificationCategory, NotificationType
from app.models.finance import (
    FeeStructure,
    FeeItem,
    Invoice,
    InvoiceStatus,
    InvoiceItem,
    InvoiceScholarshipItem,
    StudentScholarship,
    ScholarshipStatus,
    CoverageType,
    Scholarship,
    # Invoice status workflow validation
    is_valid_invoice_transition,
    get_valid_next_statuses,
)
from app.models.academic import Class, ClassLevel
from app.models.student import Student
from app.services.finance._shared import (
    FinanceServiceError,
    ScholarshipDiscountDetail,
    ScholarshipDiscountResult,
)
from app.services.finance.fee_structure_service import FeeStructureService
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()


class InvoiceService:
    """Service for managing invoices."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _validate_status_transition(
        self,
        invoice: Invoice,
        new_status: InvoiceStatus,
        operation: str = "update",
    ) -> None:
        """
        Validate that a status transition is allowed.

        Raises FinanceServiceError if the transition is not valid.

        Args:
            invoice: The invoice to validate
            new_status: The desired new status
            operation: Description of the operation for error messages
        """
        current_status = invoice.status
        if not is_valid_invoice_transition(current_status, new_status):
            valid_statuses = get_valid_next_statuses(current_status)
            valid_names = [s.value for s in valid_statuses] if valid_statuses else ["none (terminal state)"]
            raise FinanceServiceError(
                f"Cannot {operation} invoice: invalid status transition from '{current_status.value}' to '{new_status.value}'. "
                f"Valid transitions from '{current_status.value}': {', '.join(valid_names)}",
                code="invalid_status_transition",
            )

    def _set_invoice_status(
        self,
        invoice: Invoice,
        new_status: InvoiceStatus,
        operation: str = "update",
    ) -> None:
        """
        Validate and set the invoice status.

        Args:
            invoice: The invoice to update
            new_status: The desired new status
            operation: Description of the operation for error messages

        Raises:
            FinanceServiceError: If the transition is not valid
        """
        self._validate_status_transition(invoice, new_status, operation)
        invoice.status = new_status

    async def _generate_invoice_number(self, tenant_id: UUID) -> str:
        """
        Generate unique invoice number for the tenant.

        Queries the max existing invoice number for this tenant and year,
        then increments to ensure uniqueness.
        """
        year = datetime.now().year
        prefix = f"INV-{year}-"

        # Query max invoice number for this tenant and year
        result = await self.db.execute(
            select(func.max(Invoice.invoice_number))
            .where(
                and_(
                    Invoice.tenant_id == tenant_id,
                    Invoice.invoice_number.like(f"{prefix}%"),
                )
            )
        )
        max_invoice_number = result.scalar()

        if max_invoice_number:
            # Extract the sequence number from the invoice number
            try:
                seq_num = int(max_invoice_number.replace(prefix, "")) + 1
            except ValueError:
                seq_num = 1
        else:
            seq_num = 1

        return f"{prefix}{seq_num:05d}"

    async def create_invoice(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        fee_structure_id: Optional[UUID] = None,
        due_date: Optional[date] = None,
        discount_amount: Decimal = Decimal("0.00"),
        notes: Optional[str] = None,
        items: list[dict] = None,
        created_by: Optional[UUID] = None,
    ) -> Invoice:
        """Create a new invoice."""
        invoice_number = await self._generate_invoice_number(tenant_id)

        invoice = Invoice(
            tenant_id=tenant_id,
            school_id=school_id,
            invoice_number=invoice_number,
            student_id=student_id,
            fee_structure_id=fee_structure_id,
            academic_year_id=academic_year_id,
            term_id=term_id,
            due_date=due_date,
            discount_amount=discount_amount,
            notes=notes,
            status=InvoiceStatus.DRAFT,
            created_by=created_by,
        )
        self.db.add(invoice)
        await self.db.flush()

        subtotal = Decimal("0.00")
        fee_items_for_scholarship = []  # Track fee items for scholarship calculation

        # Add items if provided directly
        if items:
            # Look up fee items for scholarship calculation if fee_item_id is provided
            fee_item_ids = [
                item_data.get("fee_item_id")
                for item_data in items
                if item_data.get("fee_item_id")
            ]
            if fee_item_ids:
                fee_item_result = await self.db.execute(
                    select(FeeItem)
                    .options(joinedload(FeeItem.fee_type))
                    .where(FeeItem.id.in_(fee_item_ids))
                )
                fee_items_map = {
                    str(fi.id): fi for fi in fee_item_result.scalars().all()
                }

            for item_data in items:
                quantity = item_data.get("quantity", 1)
                unit_price = Decimal(str(item_data["unit_price"]))
                amount = unit_price * quantity

                invoice_item = InvoiceItem(
                    tenant_id=tenant_id,
                    invoice_id=invoice.id,
                    fee_item_id=item_data.get("fee_item_id"),
                    description=item_data["description"],
                    quantity=quantity,
                    unit_price=unit_price,
                    amount=amount,
                )
                self.db.add(invoice_item)
                subtotal += amount

                # Track fee item for scholarship calculation
                fee_item_id = item_data.get("fee_item_id")
                if fee_item_id and str(fee_item_id) in fee_items_map:
                    fee_items_for_scholarship.append(fee_items_map[str(fee_item_id)])

        # Or use fee structure items
        elif fee_structure_id:
            fee_structure = await FeeStructureService(self.db).get_fee_structure(
                tenant_id, fee_structure_id, include_items=True
            )
            if fee_structure:
                for item in fee_structure.items:
                    if not item.is_optional:  # Only include mandatory items
                        invoice_item = InvoiceItem(
                            tenant_id=tenant_id,
                            invoice_id=invoice.id,
                            fee_item_id=item.id,
                            description=item.name,
                            quantity=1,
                            unit_price=item.amount,
                            amount=item.amount,
                        )
                        self.db.add(invoice_item)
                        subtotal += item.amount
                        fee_items_for_scholarship.append(item)

        # Calculate scholarship discount (pass fee items for component-specific filtering)
        scholarship_result = await self._calculate_scholarship_discount(
            student_id, academic_year_id, subtotal, fee_items_for_scholarship
        )

        # Update totals
        invoice.subtotal = subtotal
        invoice.scholarship_discount = scholarship_result.total_discount
        invoice.total_amount = subtotal - discount_amount - scholarship_result.total_discount + invoice.tax_amount
        invoice.update_balance()  # Keep balance column in sync

        # Create InvoiceScholarshipItem records for traceability
        for detail in scholarship_result.details:
            scholarship_item = InvoiceScholarshipItem(
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                student_scholarship_id=detail.student_scholarship_id,
                scholarship_id=detail.scholarship_id,
                scholarship_name=detail.scholarship_name,
                scholarship_code=detail.scholarship_code,
                coverage_type=detail.coverage_type,
                coverage_value=detail.coverage_value,
                calculated_amount=detail.calculated_amount,
                applicable_subtotal=detail.applicable_subtotal,
            )
            self.db.add(scholarship_item)

        await self.db.flush()
        await self.db.refresh(invoice)

        # Best-effort notification for the user who created the invoice
        if created_by:
            try:
                from app.services.notification import NotificationService
                notification_svc = NotificationService(self.db)
                await notification_svc.create(
                    tenant_id=invoice.tenant_id,
                    user_id=created_by,
                    title="Invoice Generated",
                    message=f"Invoice #{invoice.invoice_number} for {invoice.total_amount:.2f} has been generated.",
                    type=NotificationType.SUCCESS,
                    category=NotificationCategory.FINANCE,
                    reference_id=invoice.id,
                    reference_type="invoice",
                )
            except Exception:
                logger.warning("notification_create_failed", invoice_id=str(invoice.id), exc_info=True)

        return invoice

    async def _calculate_scholarship_discount(
        self,
        student_id: UUID,
        academic_year_id: UUID,
        subtotal: Decimal,
        invoice_items: Optional[list] = None,
    ) -> ScholarshipDiscountResult:
        """
        Calculate scholarship discount for a student.

        Args:
            student_id: The student's ID
            academic_year_id: The academic year ID
            subtotal: Total invoice subtotal
            invoice_items: Optional list of invoice items to filter by applicable fees

        Returns:
            ScholarshipDiscountResult with total discount and breakdown details
        """
        # Get active scholarships for student
        result = await self.db.execute(
            select(StudentScholarship)
            .options(joinedload(StudentScholarship.scholarship))
            .where(
                and_(
                    StudentScholarship.student_id == student_id,
                    StudentScholarship.academic_year_id == academic_year_id,
                    StudentScholarship.status == ScholarshipStatus.ACTIVE,
                )
            )
        )
        student_scholarships = result.scalars().all()

        total_discount = Decimal("0.00")
        details: list[ScholarshipDiscountDetail] = []

        for ss in student_scholarships:
            scholarship = ss.scholarship
            coverage_value = ss.coverage_override or scholarship.coverage_value

            # Determine eligible subtotal based on applicable_fees
            eligible_subtotal = await self._get_eligible_subtotal(
                scholarship, subtotal, invoice_items
            )

            if eligible_subtotal <= 0:
                continue

            if scholarship.coverage_type == CoverageType.PERCENTAGE:
                discount = eligible_subtotal * (coverage_value / Decimal("100"))
            else:
                discount = min(coverage_value, eligible_subtotal)

            total_discount += discount

            # Track details for creating InvoiceScholarshipItem records
            details.append(ScholarshipDiscountDetail(
                student_scholarship_id=ss.id,
                scholarship_id=scholarship.id,
                scholarship_name=scholarship.name,
                scholarship_code=scholarship.code,
                coverage_type=scholarship.coverage_type.value,
                coverage_value=coverage_value,
                applicable_subtotal=eligible_subtotal,
                calculated_amount=discount,
            ))

        # Don't exceed subtotal - adjust last discount if needed
        if total_discount > subtotal and details:
            excess = total_discount - subtotal
            details[-1].calculated_amount -= excess
            total_discount = subtotal

        return ScholarshipDiscountResult(total_discount=total_discount, details=details)

    async def _get_eligible_subtotal(
        self,
        scholarship: Scholarship,
        subtotal: Decimal,
        fee_items: Optional[list] = None,
    ) -> Decimal:
        """
        Calculate the eligible subtotal for a scholarship based on applicable_fees.

        Scholarships can specify which fee components they cover via applicable_fees:
        - ["all"] or None: Applies to entire subtotal
        - ["<fee_type_id>", ...]: Applies only to items with matching fee type IDs
        - ["tuition", "examination", ...]: Matches by fee type name (case-insensitive)
        - ["tuition", "facilities", ...]: Matches by fee type category (case-insensitive)

        Args:
            scholarship: The scholarship with applicable_fees configuration
            subtotal: Full invoice subtotal
            fee_items: List of FeeItem objects (from fee structure) with fee_type relationship

        Returns:
            Eligible subtotal for this scholarship
        """
        applicable_fees = scholarship.applicable_fees

        # If no applicable_fees specified or "all" is in the list, apply to entire subtotal
        if not applicable_fees or "all" in applicable_fees:
            return subtotal

        # If no fee items provided, we can't filter - apply to full subtotal
        if not fee_items:
            return subtotal

        # Normalize applicable_fees to lowercase for comparison
        applicable_fees_lower = [f.lower() for f in applicable_fees]

        # Calculate subtotal for only applicable fee types
        eligible_subtotal = Decimal("0.00")
        for item in fee_items:
            # Skip optional items that wouldn't be in the invoice
            if hasattr(item, 'is_optional') and item.is_optional:
                continue

            # Get fee type info
            fee_type_id = str(item.fee_type_id) if item.fee_type_id else None
            fee_type = item.fee_type if hasattr(item, 'fee_type') else None

            # Check by fee type ID
            if fee_type_id and fee_type_id in applicable_fees:
                eligible_subtotal += item.amount
                continue

            # Check by fee type name or category
            if fee_type:
                if fee_type.name.lower() in applicable_fees_lower:
                    eligible_subtotal += item.amount
                    continue
                if fee_type.category and fee_type.category.lower() in applicable_fees_lower:
                    eligible_subtotal += item.amount
                    continue

            # Also check by item name as fallback
            if item.name.lower() in applicable_fees_lower:
                eligible_subtotal += item.amount

        return eligible_subtotal

    async def get_invoice(self, tenant_id: UUID, invoice_id: UUID) -> Optional[Invoice]:
        """Get invoice by ID with details."""
        query = select(Invoice).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Invoice.tenant_id == tenant_id,
                Invoice.id == invoice_id,
                Invoice.deleted_at.is_(None),
            )
        ).options(
            selectinload(Invoice.items),
            selectinload(Invoice.payments),
            selectinload(Invoice.scholarship_items),
            # Chain class_ loading for endpoints that access inv.student.class_.name
            joinedload(Invoice.student).selectinload(Student.class_),
            joinedload(Invoice.academic_year),
            joinedload(Invoice.term),
            joinedload(Invoice.fee_structure),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_invoices(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Invoice], int]:
        """List invoices with filters and search."""
        query = select(Invoice).where(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.deleted_at.is_(None),
            )
        )

        if school_id:
            query = query.where(Invoice.school_id == school_id)
        if student_id:
            query = query.where(Invoice.student_id == student_id)
        if academic_year_id:
            query = query.where(Invoice.academic_year_id == academic_year_id)
        if term_id:
            query = query.where(Invoice.term_id == term_id)
        if status:
            query = query.where(Invoice.status == InvoiceStatus(status))

        # Search across invoice number, student name, and student ID
        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            search_term = f"%{escape_ilike(search).lower()}%"
            query = query.join(Invoice.student).where(
                or_(
                    Invoice.invoice_number.ilike(search_term),
                    func.lower(Student.first_name).like(search_term),
                    func.lower(Student.last_name).like(search_term),
                    func.lower(Student.middle_name).like(search_term),
                    func.lower(Student.student_id).like(search_term),
                    # Search concatenated name
                    func.lower(
                        func.concat(Student.first_name, ' ', Student.last_name)
                    ).like(search_term),
                    func.lower(
                        func.concat(Student.first_name, ' ', Student.middle_name, ' ', Student.last_name)
                    ).like(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results (use outerjoin to avoid duplicate join if search was used)
        if search:
            query = query.options(
                selectinload(Invoice.items),
                selectinload(Invoice.scholarship_items),
                joinedload(Invoice.academic_year),
                joinedload(Invoice.term),
            ).order_by(desc(Invoice.created_at))
        else:
            query = query.options(
                selectinload(Invoice.items),
                selectinload(Invoice.scholarship_items),
                # Chain class_ loading for endpoints that access inv.student.class_.name
                joinedload(Invoice.student).selectinload(Student.class_),
                joinedload(Invoice.academic_year),
                joinedload(Invoice.term),
            ).order_by(desc(Invoice.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_invoice(
        self, tenant_id: UUID, invoice_id: UUID, **kwargs
    ) -> Optional[Invoice]:
        """Update invoice (only draft status)."""
        invoice = await self.get_invoice(tenant_id, invoice_id)
        if not invoice:
            return None

        if invoice.status != InvoiceStatus.DRAFT:
            raise FinanceServiceError(
                "Only draft invoices can be updated",
                code="invalid_status",
            )

        for key, value in kwargs.items():
            if value is not None and hasattr(invoice, key):
                setattr(invoice, key, value)

        # Recalculate total if discount changed
        if "discount_amount" in kwargs:
            invoice.total_amount = (
                invoice.subtotal
                - invoice.discount_amount
                - invoice.scholarship_discount
                + invoice.tax_amount
            )
            invoice.update_balance()  # Keep balance column in sync

        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def issue_invoice(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        issued_by: UUID,
        issue_date: Optional[date] = None,
    ) -> Optional[Invoice]:
        """Issue a draft invoice."""
        invoice = await self.get_invoice(tenant_id, invoice_id)
        if not invoice:
            return None

        # Validate status transition using state machine
        self._set_invoice_status(invoice, InvoiceStatus.ISSUED, operation="issue")

        invoice.issue_date = issue_date or date.today()
        invoice.issued_by = issued_by
        invoice.issued_at = datetime.now(UTC)

        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def cancel_invoice(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        cancelled_by: UUID,
        reason: str,
    ) -> Optional[Invoice]:
        """Cancel an invoice."""
        invoice = await self.get_invoice(tenant_id, invoice_id)
        if not invoice:
            return None

        if invoice.amount_paid > 0:
            raise FinanceServiceError(
                "Cannot cancel invoice with payments. Void payments first.",
                code="has_payments",
            )

        # Validate status transition using state machine
        self._set_invoice_status(invoice, InvoiceStatus.CANCELLED, operation="cancel")

        invoice.cancelled_by = cancelled_by
        invoice.cancelled_at = datetime.now(UTC)
        invoice.cancel_reason = reason

        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def delete_invoice(self, tenant_id: UUID, invoice_id: UUID) -> bool:
        """Soft delete invoice (only draft)."""
        invoice = await self.get_invoice(tenant_id, invoice_id)
        if not invoice:
            return False

        if invoice.status != InvoiceStatus.DRAFT:
            raise FinanceServiceError(
                "Only draft invoices can be deleted",
                code="invalid_status",
            )

        invoice.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_students_missing_invoices(
        self,
        tenant_id: UUID,
        fee_structure_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
    ) -> Sequence[Student]:
        """
        Get students who match fee structure criteria but don't have an invoice
        for the specified academic year and term.
        """
        # Get the fee structure to apply its filters
        fee_structure_result = await self.db.execute(
            select(FeeStructure).where(
                and_(
                    FeeStructure.id == fee_structure_id,
                    FeeStructure.tenant_id == tenant_id,
                    FeeStructure.deleted_at.is_(None),
                )
            )
        )
        fee_structure = fee_structure_result.scalar_one_or_none()
        if not fee_structure:
            return []

        # Subquery: students who already have an invoice for this term/year
        existing_invoice_subquery = (
            select(Invoice.student_id)
            .where(
                and_(
                    Invoice.tenant_id == tenant_id,
                    Invoice.academic_year_id == academic_year_id,
                    Invoice.term_id == term_id,
                    Invoice.deleted_at.is_(None),
                    Invoice.status != InvoiceStatus.CANCELLED,
                )
            )
            .scalar_subquery()
        )

        # Main query: active students who match fee structure criteria
        student_query = (
            select(Student)
            .join(Class, Student.class_id == Class.id, isouter=True)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                    # Exclude students who already have invoices
                    Student.id.notin_(existing_invoice_subquery),
                )
            )
        )

        # Apply filters from fee structure
        if fee_structure.class_id:
            student_query = student_query.where(Student.class_id == fee_structure.class_id)
        elif fee_structure.level_category:
            level_category_map = {
                "preschool": [
                    ClassLevel.CRECHE,
                    ClassLevel.NURSERY_1,
                    ClassLevel.NURSERY_2,
                    ClassLevel.KG_1,
                    ClassLevel.KG_2,
                ],
                "primary": [
                    ClassLevel.PRIMARY_1,
                    ClassLevel.PRIMARY_2,
                    ClassLevel.PRIMARY_3,
                    ClassLevel.PRIMARY_4,
                    ClassLevel.PRIMARY_5,
                    ClassLevel.PRIMARY_6,
                ],
                "jhs": [
                    ClassLevel.JHS_1,
                    ClassLevel.JHS_2,
                    ClassLevel.JHS_3,
                ],
                "shs": [
                    ClassLevel.SHS_1,
                    ClassLevel.SHS_2,
                    ClassLevel.SHS_3,
                ],
            }
            matching_levels = level_category_map.get(fee_structure.level_category, [])
            if matching_levels:
                student_query = student_query.where(Class.level.in_(matching_levels))

        # Filter by student type (day/boarding)
        if fee_structure.student_type == "day":
            student_query = student_query.where(Student.is_boarder == False)
        elif fee_structure.student_type == "boarding":
            student_query = student_query.where(Student.is_boarder == True)

        # Apply additional filters
        if class_id:
            student_query = student_query.where(Student.class_id == class_id)
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)

        # Order by name for consistent display
        student_query = student_query.order_by(Student.last_name, Student.first_name)

        result = await self.db.execute(student_query)
        return result.scalars().all()

    async def bulk_generate_invoices(
        self,
        tenant_id: UUID,
        school_id: UUID,
        fee_structure_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
        class_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
        due_date: Optional[date] = None,
        student_ids: Optional[list[UUID]] = None,
        created_by: Optional[UUID] = None,
        issue_immediately: bool = False,
    ) -> dict:
        """Bulk generate invoices for students."""
        result = {"created": 0, "skipped": 0, "failed": 0, "errors": [], "invoice_ids": []}

        # Get the fee structure to apply its filters
        fee_structure_result = await self.db.execute(
            select(FeeStructure).where(
                and_(
                    FeeStructure.id == fee_structure_id,
                    FeeStructure.tenant_id == tenant_id,
                    FeeStructure.deleted_at.is_(None),
                )
            )
        )
        fee_structure = fee_structure_result.scalar_one_or_none()
        if not fee_structure:
            result["errors"].append("Fee structure not found")
            return result

        # Get students to invoice - join with Class to filter by level
        student_query = (
            select(Student)
            .join(Class, Student.class_id == Class.id, isouter=True)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.status == "active",
                    Student.deleted_at.is_(None),
                )
            )
        )

        # Apply filters from fee structure
        # 1. Specific class from fee structure takes priority
        if fee_structure.class_id:
            student_query = student_query.where(Student.class_id == fee_structure.class_id)
        # 2. Otherwise filter by level_category
        elif fee_structure.level_category:
            # Map level_category to list of matching ClassLevel enum values
            level_category_map = {
                "preschool": [
                    ClassLevel.CRECHE,
                    ClassLevel.NURSERY_1,
                    ClassLevel.NURSERY_2,
                    ClassLevel.KG_1,
                    ClassLevel.KG_2,
                ],
                "primary": [
                    ClassLevel.PRIMARY_1,
                    ClassLevel.PRIMARY_2,
                    ClassLevel.PRIMARY_3,
                    ClassLevel.PRIMARY_4,
                    ClassLevel.PRIMARY_5,
                    ClassLevel.PRIMARY_6,
                ],
                "jhs": [
                    ClassLevel.JHS_1,
                    ClassLevel.JHS_2,
                    ClassLevel.JHS_3,
                ],
                "shs": [
                    ClassLevel.SHS_1,
                    ClassLevel.SHS_2,
                    ClassLevel.SHS_3,
                ],
            }
            matching_levels = level_category_map.get(fee_structure.level_category, [])
            if matching_levels:
                student_query = student_query.where(Class.level.in_(matching_levels))

        # 3. Filter by student type (day/boarding)
        if fee_structure.student_type == "day":
            student_query = student_query.where(Student.is_boarder == False)
        elif fee_structure.student_type == "boarding":
            student_query = student_query.where(Student.is_boarder == True)

        # Apply additional filters from request (override/narrow down)
        if student_ids:
            student_query = student_query.where(Student.id.in_(student_ids))
        if class_id:
            student_query = student_query.where(Student.class_id == class_id)
        if section_id:
            student_query = student_query.where(Student.section_id == section_id)

        students_result = await self.db.execute(student_query)
        students = students_result.scalars().all()

        for student in students:
            try:
                # Check for existing invoice
                existing = await self.db.execute(
                    select(Invoice).where(
                        and_(
                            Invoice.tenant_id == tenant_id,
                            Invoice.student_id == student.id,
                            Invoice.academic_year_id == academic_year_id,
                            Invoice.term_id == term_id,
                            Invoice.deleted_at.is_(None),
                            Invoice.status != InvoiceStatus.CANCELLED,
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    result["skipped"] += 1
                    continue

                invoice = await self.create_invoice(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    student_id=student.id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    fee_structure_id=fee_structure_id,
                    due_date=due_date,
                    created_by=created_by,
                )

                # Issue immediately if requested
                if issue_immediately and created_by:
                    await self.issue_invoice(
                        invoice_id=invoice.id,
                        issued_by=created_by,
                    )

                result["created"] += 1
                result["invoice_ids"].append(invoice.id)

            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"Student {student.id}: {str(e)}")

        return result

    async def get_invoices_sync_preview(
        self,
        tenant_id: UUID,
        fee_structure_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
    ) -> dict:
        """
        Get preview of invoices that would be affected by syncing with fee structure.
        Returns counts of draft vs issued/paid invoices.
        """
        # Get all invoices for this fee structure/term
        query = select(Invoice).where(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.fee_structure_id == fee_structure_id,
                Invoice.academic_year_id == academic_year_id,
                Invoice.term_id == term_id,
                Invoice.deleted_at.is_(None),
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        )
        result = await self.db.execute(query)
        invoices = result.scalars().all()

        draft_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.DRAFT)
        issued_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.ISSUED)
        partial_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.PARTIAL)
        paid_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.PAID)

        # Get fee structure to show new total
        fee_structure = await FeeStructureService(self.db).get_fee_structure(
            tenant_id, fee_structure_id, include_items=True
        )
        new_total = sum(
            item.amount for item in (fee_structure.items if fee_structure else [])
            if not item.is_optional
        )

        return {
            "draft_count": draft_count,
            "issued_count": issued_count,
            "partial_count": partial_count,
            "paid_count": paid_count,
            "total_invoices": len(invoices),
            "can_sync_count": draft_count,
            "cannot_sync_count": issued_count + partial_count + paid_count,
            "new_fee_structure_total": float(new_total),
        }

    async def sync_invoices_with_fee_structure(
        self,
        tenant_id: UUID,
        fee_structure_id: UUID,
        academic_year_id: UUID,
        term_id: UUID,
    ) -> dict:
        """
        Sync draft invoices with the current fee structure.
        Only updates DRAFT invoices - issued/paid invoices are not modified.

        Returns:
            dict with updated, skipped, and failed counts
        """
        result = {
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
            "skipped_reasons": {
                "issued": 0,
                "partial": 0,
                "paid": 0,
            }
        }

        # Get the fee structure with items
        fee_structure = await FeeStructureService(self.db).get_fee_structure(
            tenant_id, fee_structure_id, include_items=True
        )
        if not fee_structure:
            result["errors"].append("Fee structure not found")
            return result

        # Get all draft invoices for this fee structure/term
        query = select(Invoice).where(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.fee_structure_id == fee_structure_id,
                Invoice.academic_year_id == academic_year_id,
                Invoice.term_id == term_id,
                Invoice.deleted_at.is_(None),
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        ).options(selectinload(Invoice.items))

        invoices_result = await self.db.execute(query)
        invoices = invoices_result.scalars().all()

        for invoice in invoices:
            try:
                # Only sync draft invoices
                if invoice.status != InvoiceStatus.DRAFT:
                    result["skipped"] += 1
                    if invoice.status == InvoiceStatus.ISSUED:
                        result["skipped_reasons"]["issued"] += 1
                    elif invoice.status == InvoiceStatus.PARTIAL:
                        result["skipped_reasons"]["partial"] += 1
                    elif invoice.status == InvoiceStatus.PAID:
                        result["skipped_reasons"]["paid"] += 1
                    continue

                # Delete existing invoice items
                await self.db.execute(
                    delete(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)
                )

                # Recreate items from fee structure
                subtotal = Decimal("0.00")
                mandatory_fee_items = []  # Track for scholarship calculation
                for item in fee_structure.items:
                    if not item.is_optional:  # Only include mandatory items
                        invoice_item = InvoiceItem(
                            tenant_id=tenant_id,
                            invoice_id=invoice.id,
                            fee_item_id=item.id,
                            description=item.name,
                            quantity=1,
                            unit_price=item.amount,
                            amount=item.amount,
                        )
                        self.db.add(invoice_item)
                        subtotal += item.amount
                        mandatory_fee_items.append(item)

                # Recalculate scholarship discount (pass fee items for component filtering)
                scholarship_result = await self._calculate_scholarship_discount(
                    invoice.student_id, academic_year_id, subtotal, mandatory_fee_items
                )

                # Update invoice totals
                invoice.subtotal = subtotal
                invoice.scholarship_discount = scholarship_result.total_discount
                invoice.total_amount = (
                    subtotal
                    - invoice.discount_amount
                    - scholarship_result.total_discount
                    + invoice.tax_amount
                )
                invoice.update_balance()  # Keep balance column in sync

                # Delete existing scholarship items and recreate
                await self.db.execute(
                    delete(InvoiceScholarshipItem).where(
                        InvoiceScholarshipItem.invoice_id == invoice.id
                    )
                )

                # Create new InvoiceScholarshipItem records
                for detail in scholarship_result.details:
                    scholarship_item = InvoiceScholarshipItem(
                        tenant_id=invoice.tenant_id,
                        invoice_id=invoice.id,
                        student_scholarship_id=detail.student_scholarship_id,
                        scholarship_id=detail.scholarship_id,
                        scholarship_name=detail.scholarship_name,
                        scholarship_code=detail.scholarship_code,
                        coverage_type=detail.coverage_type,
                        coverage_value=detail.coverage_value,
                        calculated_amount=detail.calculated_amount,
                        applicable_subtotal=detail.applicable_subtotal,
                    )
                    self.db.add(scholarship_item)

                result["updated"] += 1

            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"Invoice {invoice.invoice_number}: {str(e)}")

        await self.db.flush()
        return result

    def _update_invoice_status(self, invoice: Invoice) -> None:
        """
        Update invoice status and balance based on payments.

        NOTE: This method handles automatic status updates triggered by payment
        changes. Unlike user-initiated status changes (issue, cancel, write-off),
        these automatic transitions are allowed even if they don't follow the
        strict state machine rules. This is necessary because:
        - Voiding a payment on a PAID invoice needs to revert to PARTIAL/ISSUED
        - Payment adjustments may require status recalculations

        The state machine validation (is_valid_invoice_transition) is applied
        to explicit user actions, not automatic payment-based updates.
        """
        # Update balance column
        invoice.update_balance()

        # Don't update terminal states (cancelled, write-off) or draft invoices
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT, InvoiceStatus.WRITE_OFF):
            return

        # Calculate new status based on payment state
        if invoice.amount_paid >= invoice.total_amount:
            new_status = InvoiceStatus.PAID
        elif invoice.amount_paid > 0:
            new_status = InvoiceStatus.PARTIAL
        else:
            # amount_paid == 0: reset to ISSUED or OVERDUE based on due date
            if invoice.due_date and invoice.due_date < date.today():
                new_status = InvoiceStatus.OVERDUE
            else:
                new_status = InvoiceStatus.ISSUED

        # Apply the calculated status (automatic transition, no validation)
        invoice.status = new_status

    async def update_overdue_invoices(self, tenant_id: UUID) -> dict:
        """
        Update status of invoices that have passed their due date.

        This method should be called periodically (e.g., daily via Celery task)
        to ensure ISSUED or PARTIAL invoices are marked as OVERDUE when their
        due date has passed.

        NOTE: The transitions here (ISSUED -> OVERDUE, PARTIAL -> OVERDUE) are
        valid according to the invoice state machine.

        Returns:
            dict with count of updated invoices
        """
        today = date.today()

        # Find invoices that are past due but not yet marked as overdue
        query = select(Invoice).where(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.deleted_at.is_(None),
                Invoice.due_date < today,
                Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIAL]),
            )
        )

        result = await self.db.execute(query)
        invoices = result.scalars().all()

        updated_count = 0
        for invoice in invoices:
            # Only update if not fully paid
            if invoice.amount_paid < invoice.total_amount:
                # These transitions are valid: ISSUED -> OVERDUE, PARTIAL -> OVERDUE
                invoice.status = InvoiceStatus.OVERDUE
                updated_count += 1

        await self.db.flush()

        return {
            "updated": updated_count,
            "checked": len(invoices),
        }

    async def write_off_invoice(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        written_off_by: UUID,
        reason: str,
    ) -> Optional[Invoice]:
        """
        Write off an overdue invoice as uncollectible.

        This is a terminal state - the invoice cannot be recovered after write-off.
        Only OVERDUE invoices can be written off.

        Args:
            tenant_id: The tenant ID (defense-in-depth)
            invoice_id: The invoice to write off
            written_off_by: User ID performing the write-off
            reason: Reason for writing off the invoice

        Returns:
            The updated invoice or None if not found
        """
        invoice = await self.get_invoice(tenant_id, invoice_id)
        if not invoice:
            return None

        # Validate status transition using state machine
        self._set_invoice_status(invoice, InvoiceStatus.WRITE_OFF, operation="write off")

        # Store write-off metadata in notes
        write_off_note = f"[WRITE-OFF] Reason: {reason}"
        if invoice.notes:
            invoice.notes = f"{invoice.notes}\n\n{write_off_note}"
        else:
            invoice.notes = write_off_note

        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def export_invoices_csv(
        self,
        tenant_id: UUID,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        status: Optional[str] = None,
        class_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Export invoices as list of dicts for CSV writer."""
        conditions = [
            Invoice.tenant_id == tenant_id,
            Invoice.deleted_at.is_(None),
        ]
        # Chain support: scope to active school when provided
        if school_id:
            conditions.append(Invoice.school_id == school_id)
        if academic_year_id:
            conditions.append(Invoice.academic_year_id == academic_year_id)
        if term_id:
            conditions.append(Invoice.term_id == term_id)
        if status:
            conditions.append(Invoice.status == InvoiceStatus(status))
        if class_id:
            conditions.append(Invoice.student.has(Student.class_id == class_id))

        query = (
            select(Invoice)
            .where(and_(*conditions))
            .options(
                joinedload(Invoice.student),
            )
            .order_by(desc(Invoice.created_at))
        )
        result = await self.db.execute(query)
        invoices = result.scalars().unique().all()

        return [
            {
                "invoice_number": inv.invoice_number,
                "student_name": f"{inv.student.first_name} {inv.student.last_name}" if inv.student else "",
                "student_id_number": inv.student.student_id if inv.student else "",
                "total_amount": str(inv.total_amount),
                "amount_paid": str(inv.amount_paid),
                "balance": str(inv.total_amount - inv.amount_paid),
                "status": inv.status.value,
                "due_date": str(inv.due_date) if inv.due_date else "",
                "created_at": str(inv.created_at) if inv.created_at else "",
            }
            for inv in invoices
        ]

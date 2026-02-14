"""
SIMS Plus - Finance Service

Business logic for finance management: fee structures, invoices, payments, scholarships.
"""

from datetime import datetime, UTC, date, timezone
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc, or_, case, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.finance import (
    FeeType,
    FeeStructure,
    FeeItem,
    Invoice,
    InvoiceStatus,
    InvoiceItem,
    InvoiceScholarshipItem,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Scholarship,
    ScholarshipType,
    CoverageType,
    StudentScholarship,
    ScholarshipStatus,
    ScholarshipApplication,
    ApplicationStatus,
    FinanceAuditLog,
    FinanceAuditAction,
    CreditNote,
    CreditNoteStatus,
    CreditNoteType,
    # Invoice status workflow validation
    is_valid_invoice_transition,
    get_valid_next_statuses,
)
from app.models.academic import AcademicYear, Term, Class, ClassSection, ClassLevel
from app.models.student import Student
from app.models.school import School


class FinanceServiceError(Exception):
    """Base exception for finance service errors."""

    def __init__(self, message: str, code: str = "finance_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ScholarshipDiscountDetail:
    """Details of a scholarship discount applied to an invoice."""

    def __init__(
        self,
        student_scholarship_id: UUID,
        scholarship_id: UUID,
        scholarship_name: str,
        scholarship_code: str,
        coverage_type: str,
        coverage_value: Decimal,
        applicable_subtotal: Decimal,
        calculated_amount: Decimal,
    ):
        self.student_scholarship_id = student_scholarship_id
        self.scholarship_id = scholarship_id
        self.scholarship_name = scholarship_name
        self.scholarship_code = scholarship_code
        self.coverage_type = coverage_type
        self.coverage_value = coverage_value
        self.applicable_subtotal = applicable_subtotal
        self.calculated_amount = calculated_amount


class ScholarshipDiscountResult:
    """Result of scholarship discount calculation."""

    def __init__(self, total_discount: Decimal, details: list[ScholarshipDiscountDetail]):
        self.total_discount = total_discount
        self.details = details


# =========================
# Fee Type Service
# =========================


class FeeTypeService:
    """Service for managing fee types."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_fee_type(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: bool = True,
    ) -> FeeType:
        """Create a new fee type."""
        # Check for duplicate name (case insensitive)
        existing = await self.db.execute(
            select(FeeType).where(
                and_(
                    FeeType.tenant_id == tenant_id,
                    func.lower(FeeType.name) == name.lower(),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise FinanceServiceError(
                f"Fee type '{name}' already exists",
                "duplicate_fee_type",
            )

        fee_type = FeeType(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            description=description,
            category=category,
            is_active=is_active,
        )
        self.db.add(fee_type)
        await self.db.commit()
        await self.db.refresh(fee_type)
        return fee_type

    async def get_fee_type(self, fee_type_id: UUID) -> Optional[FeeType]:
        """Get a fee type by ID."""
        result = await self.db.execute(
            select(FeeType).where(FeeType.id == fee_type_id)
        )
        return result.scalar_one_or_none()

    async def update_fee_type(
        self,
        fee_type_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[FeeType]:
        """Update a fee type."""
        fee_type = await self.get_fee_type(fee_type_id)
        if not fee_type:
            return None

        if name is not None:
            # Check for duplicate name
            existing = await self.db.execute(
                select(FeeType).where(
                    and_(
                        FeeType.tenant_id == fee_type.tenant_id,
                        func.lower(FeeType.name) == name.lower(),
                        FeeType.id != fee_type_id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise FinanceServiceError(
                    f"Fee type '{name}' already exists",
                    "duplicate_fee_type",
                )
            fee_type.name = name

        if description is not None:
            fee_type.description = description
        if category is not None:
            fee_type.category = category
        if is_active is not None:
            fee_type.is_active = is_active

        await self.db.commit()
        await self.db.refresh(fee_type)
        return fee_type

    async def delete_fee_type(self, fee_type_id: UUID) -> bool:
        """Delete a fee type."""
        fee_type = await self.get_fee_type(fee_type_id)
        if not fee_type:
            return False

        await self.db.delete(fee_type)
        await self.db.commit()
        return True

    async def list_fee_types(
        self,
        tenant_id: UUID,
        search: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[FeeType], int]:
        """List fee types with optional filtering."""
        query = select(FeeType).where(FeeType.tenant_id == tenant_id)

        if search:
            query = query.where(
                or_(
                    FeeType.name.ilike(f"%{search}%"),
                    FeeType.description.ilike(f"%{search}%"),
                )
            )
        if category:
            query = query.where(FeeType.category == category)
        if is_active is not None:
            query = query.where(FeeType.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(FeeType.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def search_fee_types(
        self,
        tenant_id: UUID,
        query: str,
        limit: int = 10,
    ) -> Sequence[FeeType]:
        """Quick search for fee types (for autocomplete)."""
        stmt = (
            select(FeeType)
            .where(
                and_(
                    FeeType.tenant_id == tenant_id,
                    FeeType.is_active == True,
                    FeeType.name.ilike(f"%{query}%"),
                )
            )
            .order_by(FeeType.name)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()


# =========================
# Fee Structure Service
# =========================


class FeeStructureService:
    """Service for managing fee structures."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_fee_structure(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        description: Optional[str] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        class_id: Optional[UUID] = None,
        level: Optional[str] = None,
        level_category: Optional[str] = None,
        student_type: str = "all",
        is_active: bool = True,
        items: list[dict] = None,
    ) -> FeeStructure:
        """Create a new fee structure with optional items."""
        fee_structure = FeeStructure(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            description=description,
            academic_year_id=academic_year_id,
            term_id=term_id,
            class_id=class_id,
            level=level,
            level_category=level_category,
            student_type=student_type,
            is_active=is_active,
        )
        self.db.add(fee_structure)
        await self.db.flush()

        # Add items if provided
        if items:
            for i, item_data in enumerate(items):
                fee_item = FeeItem(
                    tenant_id=tenant_id,
                    fee_structure_id=fee_structure.id,
                    fee_type_id=item_data.get("fee_type_id"),
                    name=item_data["name"],
                    description=item_data.get("description"),
                    amount=Decimal(str(item_data["amount"])),
                    is_optional=item_data.get("is_optional", False),
                    sequence=item_data.get("sequence", i),
                )
                self.db.add(fee_item)

        await self.db.commit()
        # Reload with relationships
        return await self.get_fee_structure(fee_structure.id, include_items=True)

    async def get_fee_structure(
        self, fee_structure_id: UUID, include_items: bool = True
    ) -> Optional[FeeStructure]:
        """Get fee structure by ID."""
        query = select(FeeStructure).where(
            and_(
                FeeStructure.id == fee_structure_id,
                FeeStructure.deleted_at.is_(None),
            )
        )
        if include_items:
            query = query.options(
                selectinload(FeeStructure.items),
                joinedload(FeeStructure.academic_year),
                joinedload(FeeStructure.term),
                joinedload(FeeStructure.class_),
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_fee_structures(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[FeeStructure], int]:
        """List fee structures with filters."""
        query = select(FeeStructure).where(
            and_(
                FeeStructure.tenant_id == tenant_id,
                FeeStructure.deleted_at.is_(None),
            )
        )

        if school_id:
            query = query.where(FeeStructure.school_id == school_id)
        if academic_year_id:
            query = query.where(FeeStructure.academic_year_id == academic_year_id)
        if term_id:
            query = query.where(FeeStructure.term_id == term_id)
        if is_active is not None:
            query = query.where(FeeStructure.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results with eager loading
        query = query.options(
            selectinload(FeeStructure.items),
            joinedload(FeeStructure.academic_year),
            joinedload(FeeStructure.term),
            joinedload(FeeStructure.class_),
        ).order_by(desc(FeeStructure.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_fee_structure(
        self, fee_structure_id: UUID, items: list[dict] = None, **kwargs
    ) -> Optional[FeeStructure]:
        """Update fee structure, optionally syncing items."""
        fee_structure = await self.get_fee_structure(fee_structure_id, include_items=True)
        if not fee_structure:
            return None

        # Update fee structure fields
        for key, value in kwargs.items():
            if value is not None and hasattr(fee_structure, key):
                setattr(fee_structure, key, value)

        # Sync items if provided
        if items is not None:
            # Get existing item IDs
            existing_item_ids = {str(item.id) for item in fee_structure.items}
            new_item_ids = {str(item.get("id")) for item in items if item.get("id")}

            # Delete items not in the new list
            for item in fee_structure.items:
                if str(item.id) not in new_item_ids:
                    await self.db.delete(item)

            # Update or create items
            for i, item_data in enumerate(items):
                item_id = item_data.get("id")
                if item_id and str(item_id) in existing_item_ids:
                    # Update existing item
                    for existing_item in fee_structure.items:
                        if str(existing_item.id) == str(item_id):
                            existing_item.fee_type_id = item_data.get("fee_type_id")
                            existing_item.name = item_data["name"]
                            existing_item.description = item_data.get("description")
                            existing_item.amount = Decimal(str(item_data["amount"]))
                            existing_item.is_optional = item_data.get("is_optional", False)
                            existing_item.sequence = item_data.get("sequence", i)
                            break
                else:
                    # Create new item
                    new_item = FeeItem(
                        tenant_id=fee_structure.tenant_id,
                        fee_structure_id=fee_structure.id,
                        fee_type_id=item_data.get("fee_type_id"),
                        name=item_data["name"],
                        description=item_data.get("description"),
                        amount=Decimal(str(item_data["amount"])),
                        is_optional=item_data.get("is_optional", False),
                        sequence=item_data.get("sequence", i),
                    )
                    self.db.add(new_item)

        await self.db.commit()
        # Reload with relationships
        return await self.get_fee_structure(fee_structure_id, include_items=True)

    async def delete_fee_structure(self, fee_structure_id: UUID) -> bool:
        """Soft delete fee structure."""
        fee_structure = await self.get_fee_structure(fee_structure_id, include_items=False)
        if not fee_structure:
            return False

        fee_structure.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def add_fee_item(
        self,
        tenant_id: UUID,
        fee_structure_id: UUID,
        name: str,
        amount: Decimal,
        description: Optional[str] = None,
        fee_type_id: Optional[UUID] = None,
        is_optional: bool = False,
        sequence: int = 0,
    ) -> FeeItem:
        """Add item to fee structure."""
        fee_item = FeeItem(
            tenant_id=tenant_id,
            fee_structure_id=fee_structure_id,
            fee_type_id=fee_type_id,
            name=name,
            description=description,
            amount=amount,
            is_optional=is_optional,
            sequence=sequence,
        )
        self.db.add(fee_item)
        await self.db.commit()
        # Reload with fee_type relationship
        result = await self.db.execute(
            select(FeeItem)
            .where(FeeItem.id == fee_item.id)
            .options(joinedload(FeeItem.fee_type))
        )
        return result.scalar_one_or_none()

    async def update_fee_item(self, fee_item_id: UUID, **kwargs) -> Optional[FeeItem]:
        """Update fee item."""
        result = await self.db.execute(
            select(FeeItem)
            .where(FeeItem.id == fee_item_id)
            .options(joinedload(FeeItem.fee_type))
        )
        fee_item = result.scalar_one_or_none()
        if not fee_item:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(fee_item, key):
                setattr(fee_item, key, value)

        await self.db.commit()
        # Reload with fee_type relationship
        result = await self.db.execute(
            select(FeeItem)
            .where(FeeItem.id == fee_item_id)
            .options(joinedload(FeeItem.fee_type))
        )
        return result.scalar_one_or_none()

    async def delete_fee_item(self, fee_item_id: UUID) -> bool:
        """Delete fee item."""
        result = await self.db.execute(
            select(FeeItem).where(FeeItem.id == fee_item_id)
        )
        fee_item = result.scalar_one_or_none()
        if not fee_item:
            return False

        await self.db.delete(fee_item)
        await self.db.commit()
        return True

    async def copy_fee_structure(
        self,
        fee_structure_id: UUID,
        new_name: str,
        new_academic_year_id: Optional[UUID] = None,
        new_term_id: Optional[UUID] = None,
    ) -> Optional[FeeStructure]:
        """Copy fee structure with items to a new one."""
        original = await self.get_fee_structure(fee_structure_id, include_items=True)
        if not original:
            return None

        new_structure = FeeStructure(
            tenant_id=original.tenant_id,
            school_id=original.school_id,
            name=new_name,
            description=original.description,
            academic_year_id=new_academic_year_id or original.academic_year_id,
            term_id=new_term_id or original.term_id,
            class_id=original.class_id,
            level=original.level,
            is_active=True,
        )
        self.db.add(new_structure)
        await self.db.flush()

        # Copy items
        for item in original.items:
            new_item = FeeItem(
                tenant_id=original.tenant_id,
                fee_structure_id=new_structure.id,
                name=item.name,
                description=item.description,
                amount=item.amount,
                is_optional=item.is_optional,
                sequence=item.sequence,
            )
            self.db.add(new_item)

        await self.db.commit()
        # Reload with relationships
        return await self.get_fee_structure(new_structure.id, include_items=True)


# =========================
# Invoice Service
# =========================


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
                fee_structure_id, include_items=True
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

        await self.db.commit()
        await self.db.refresh(invoice)
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

    async def get_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        """Get invoice by ID with details."""
        query = select(Invoice).where(
            and_(
                Invoice.id == invoice_id,
                Invoice.deleted_at.is_(None),
            )
        ).options(
            selectinload(Invoice.items),
            selectinload(Invoice.payments),
            selectinload(Invoice.scholarship_items),
            joinedload(Invoice.student),
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
            search_term = f"%{search.lower()}%"
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
                joinedload(Invoice.student),
                joinedload(Invoice.academic_year),
                joinedload(Invoice.term),
            ).order_by(desc(Invoice.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_invoice(
        self, invoice_id: UUID, **kwargs
    ) -> Optional[Invoice]:
        """Update invoice (only draft status)."""
        invoice = await self.get_invoice(invoice_id)
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

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def issue_invoice(
        self,
        invoice_id: UUID,
        issued_by: UUID,
        issue_date: Optional[date] = None,
    ) -> Optional[Invoice]:
        """Issue a draft invoice."""
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            return None

        # Validate status transition using state machine
        self._set_invoice_status(invoice, InvoiceStatus.ISSUED, operation="issue")

        invoice.issue_date = issue_date or date.today()
        invoice.issued_by = issued_by
        invoice.issued_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def cancel_invoice(
        self,
        invoice_id: UUID,
        cancelled_by: UUID,
        reason: str,
    ) -> Optional[Invoice]:
        """Cancel an invoice."""
        invoice = await self.get_invoice(invoice_id)
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

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def delete_invoice(self, invoice_id: UUID) -> bool:
        """Soft delete invoice (only draft)."""
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            return False

        if invoice.status != InvoiceStatus.DRAFT:
            raise FinanceServiceError(
                "Only draft invoices can be deleted",
                code="invalid_status",
            )

        invoice.deleted_at = datetime.now(UTC)
        await self.db.commit()
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
            fee_structure_id, include_items=True
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
            fee_structure_id, include_items=True
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

        await self.db.commit()
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

        NOTE: The transitions here (ISSUED → OVERDUE, PARTIAL → OVERDUE) are
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
                # These transitions are valid: ISSUED → OVERDUE, PARTIAL → OVERDUE
                invoice.status = InvoiceStatus.OVERDUE
                updated_count += 1

        await self.db.commit()

        return {
            "updated": updated_count,
            "checked": len(invoices),
        }

    async def write_off_invoice(
        self,
        invoice_id: UUID,
        written_off_by: UUID,
        reason: str,
    ) -> Optional[Invoice]:
        """
        Write off an overdue invoice as uncollectible.

        This is a terminal state - the invoice cannot be recovered after write-off.
        Only OVERDUE invoices can be written off.

        Args:
            invoice_id: The invoice to write off
            written_off_by: User ID performing the write-off
            reason: Reason for writing off the invoice

        Returns:
            The updated invoice or None if not found
        """
        invoice = await self.get_invoice(invoice_id)
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

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice


# =========================
# Payment Service
# =========================


class PaymentService:
    """Service for managing payments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_receipt_number(self, tenant_id: UUID) -> str:
        """
        Generate unique receipt number using database sequence.

        Uses a PostgreSQL sequence to ensure thread-safe, race-condition-free
        generation of unique receipt numbers even under concurrent access.
        """
        year = datetime.now().year
        prefix = f"RCP-{year}-"

        # Use database sequence to get next value atomically
        result = await self.db.execute(text("SELECT nextval('receipt_number_seq')"))
        seq_num = result.scalar()

        return f"{prefix}{seq_num:05d}"

    async def record_payment(
        self,
        tenant_id: UUID,
        school_id: UUID,
        student_id: UUID,
        amount: Decimal,
        payment_method: str,
        invoice_id: Optional[UUID] = None,
        payment_date: Optional[datetime] = None,
        payer_name: Optional[str] = None,
        payer_phone: Optional[str] = None,
        payer_email: Optional[str] = None,
        notes: Optional[str] = None,
        momo_phone: Optional[str] = None,
        momo_transaction_id: Optional[str] = None,
        bank_name: Optional[str] = None,
        bank_reference: Optional[str] = None,
        cheque_number: Optional[str] = None,
        recorded_by: Optional[UUID] = None,
    ) -> Payment:
        """Record a payment."""
        receipt_number = await self._generate_receipt_number(tenant_id)

        # Determine MoMo provider from payment method
        momo_provider = None
        if payment_method == "momo_mtn":
            momo_provider = "MTN"
        elif payment_method == "momo_vodafone":
            momo_provider = "Vodafone"
        elif payment_method == "momo_airteltigo":
            momo_provider = "AirtelTigo"

        payment = Payment(
            tenant_id=tenant_id,
            school_id=school_id,
            receipt_number=receipt_number,
            invoice_id=invoice_id,
            student_id=student_id,
            amount=amount,
            payment_method=PaymentMethod(payment_method),
            payment_date=payment_date or datetime.now(UTC),
            payer_name=payer_name,
            payer_phone=payer_phone,
            payer_email=payer_email,
            notes=notes,
            momo_phone=momo_phone,
            momo_transaction_id=momo_transaction_id,
            momo_provider=momo_provider,
            bank_name=bank_name,
            bank_reference=bank_reference,
            cheque_number=cheque_number,
            status=PaymentStatus.COMPLETED,
            recorded_by=recorded_by,
        )
        self.db.add(payment)

        # Update invoice if linked
        if invoice_id:
            invoice_result = await self.db.execute(
                select(Invoice).where(Invoice.id == invoice_id)
            )
            invoice = invoice_result.scalar_one_or_none()
            if invoice:
                invoice.amount_paid += amount
                InvoiceService(self.db)._update_invoice_status(invoice)

        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_payment(self, payment_id: UUID) -> Optional[Payment]:
        """Get payment by ID."""
        query = select(Payment).where(Payment.id == payment_id).options(
            joinedload(Payment.student),
            joinedload(Payment.invoice),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_payments(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        invoice_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Payment], int]:
        """List payments with filters."""
        query = select(Payment).where(Payment.tenant_id == tenant_id)

        if school_id:
            query = query.where(Payment.school_id == school_id)
        if student_id:
            query = query.where(Payment.student_id == student_id)
        if invoice_id:
            query = query.where(Payment.invoice_id == invoice_id)
        # Filter by academic year and term through the invoice
        if academic_year_id or term_id:
            query = query.join(Invoice, Payment.invoice_id == Invoice.id, isouter=True)
            if academic_year_id:
                query = query.where(Invoice.academic_year_id == academic_year_id)
            if term_id:
                query = query.where(Invoice.term_id == term_id)
        if status:
            query = query.where(Payment.status == PaymentStatus(status))
        if payment_method:
            query = query.where(Payment.payment_method == PaymentMethod(payment_method))
        if start_date:
            query = query.where(func.date(Payment.payment_date) >= start_date)
        if end_date:
            query = query.where(func.date(Payment.payment_date) <= end_date)
        if search:
            # Search by receipt number, payer name, or student name
            search_term = f"%{search}%"
            query = query.outerjoin(Payment.student).where(
                or_(
                    Payment.receipt_number.ilike(search_term),
                    Payment.payer_name.ilike(search_term),
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(Payment.student),
            joinedload(Payment.invoice),
        ).order_by(desc(Payment.payment_date))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def void_payment(
        self,
        payment_id: UUID,
        voided_by: UUID,
        reason: str,
    ) -> Optional[Payment]:
        """Void a payment."""
        payment = await self.get_payment(payment_id)
        if not payment:
            return None

        if payment.is_voided:
            raise FinanceServiceError(
                "Payment is already voided",
                code="already_voided",
            )

        payment.is_voided = True
        payment.voided_by = voided_by
        payment.voided_at = datetime.now(UTC)
        payment.void_reason = reason
        payment.status = PaymentStatus.CANCELLED

        # Update invoice if linked
        if payment.invoice_id:
            invoice_result = await self.db.execute(
                select(Invoice).where(Invoice.id == payment.invoice_id)
            )
            invoice = invoice_result.scalar_one_or_none()
            if invoice:
                invoice.amount_paid -= payment.amount
                if invoice.amount_paid < 0:
                    invoice.amount_paid = Decimal("0.00")
                InvoiceService(self.db)._update_invoice_status(invoice)

        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_student_payments(
        self,
        student_id: UUID,
        academic_year_id: Optional[UUID] = None,
    ) -> Sequence[Payment]:
        """Get all payments for a student."""
        query = select(Payment).where(
            and_(
                Payment.student_id == student_id,
                Payment.is_voided == False,
            )
        )

        if academic_year_id:
            query = query.join(Invoice).where(Invoice.academic_year_id == academic_year_id)

        query = query.order_by(desc(Payment.payment_date))
        result = await self.db.execute(query)
        return result.scalars().all()


# =========================
# Scholarship Service
# =========================


class ScholarshipService:
    """Service for managing scholarships."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_scholarship(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str,
        code: str,
        scholarship_type: str,
        coverage_type: str,
        coverage_value: Decimal,
        description: Optional[str] = None,
        applicable_fees: Optional[list[str]] = None,
        max_recipients: Optional[int] = None,
        academic_year_id: Optional[UUID] = None,
        eligibility_criteria: Optional[dict] = None,
        is_active: bool = True,
        created_by: Optional[UUID] = None,
    ) -> Scholarship:
        """Create a new scholarship."""
        # Check for duplicate code
        existing = await self.db.execute(
            select(Scholarship).where(
                and_(
                    Scholarship.tenant_id == tenant_id,
                    Scholarship.code == code,
                    Scholarship.deleted_at.is_(None),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise FinanceServiceError(
                f"Scholarship with code '{code}' already exists",
                code="duplicate_code",
            )

        scholarship = Scholarship(
            tenant_id=tenant_id,
            school_id=school_id,
            name=name,
            code=code,
            description=description,
            scholarship_type=ScholarshipType(scholarship_type),
            coverage_type=CoverageType(coverage_type),
            coverage_value=coverage_value,
            applicable_fees=applicable_fees,
            max_recipients=max_recipients,
            academic_year_id=academic_year_id,
            eligibility_criteria=eligibility_criteria,
            is_active=is_active,
            created_by=created_by,
        )
        self.db.add(scholarship)
        await self.db.commit()
        await self.db.refresh(scholarship)
        return scholarship

    async def get_scholarship(self, scholarship_id: UUID) -> Optional[Scholarship]:
        """Get scholarship by ID."""
        query = select(Scholarship).where(
            and_(
                Scholarship.id == scholarship_id,
                Scholarship.deleted_at.is_(None),
            )
        ).options(
            selectinload(Scholarship.recipients),
            joinedload(Scholarship.academic_year),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_scholarships(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        academic_year_id: Optional[UUID] = None,
        scholarship_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Scholarship], int]:
        """List scholarships with filters."""
        query = select(Scholarship).where(
            and_(
                Scholarship.tenant_id == tenant_id,
                Scholarship.deleted_at.is_(None),
            )
        )

        if school_id:
            query = query.where(Scholarship.school_id == school_id)
        if academic_year_id:
            query = query.where(Scholarship.academic_year_id == academic_year_id)
        if scholarship_type:
            query = query.where(Scholarship.scholarship_type == ScholarshipType(scholarship_type))
        if is_active is not None:
            query = query.where(Scholarship.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            selectinload(Scholarship.recipients),
            joinedload(Scholarship.academic_year),
        ).order_by(desc(Scholarship.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_scholarship(
        self, scholarship_id: UUID, **kwargs
    ) -> Optional[Scholarship]:
        """Update scholarship."""
        scholarship = await self.get_scholarship(scholarship_id)
        if not scholarship:
            return None

        # Handle enum conversion
        if "scholarship_type" in kwargs and kwargs["scholarship_type"]:
            kwargs["scholarship_type"] = ScholarshipType(kwargs["scholarship_type"])
        if "coverage_type" in kwargs and kwargs["coverage_type"]:
            kwargs["coverage_type"] = CoverageType(kwargs["coverage_type"])

        for key, value in kwargs.items():
            if value is not None and hasattr(scholarship, key):
                setattr(scholarship, key, value)

        await self.db.commit()
        await self.db.refresh(scholarship)
        return scholarship

    async def delete_scholarship(self, scholarship_id: UUID) -> bool:
        """Soft delete scholarship."""
        scholarship = await self.get_scholarship(scholarship_id)
        if not scholarship:
            return False

        scholarship.deleted_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def award_scholarship(
        self,
        tenant_id: UUID,
        scholarship_id: UUID,
        student_id: UUID,
        academic_year_id: UUID,
        effective_from: date,
        effective_to: Optional[date] = None,
        coverage_override: Optional[Decimal] = None,
        notes: Optional[str] = None,
        awarded_by: Optional[UUID] = None,
        # Enhanced award settings
        justification: Optional[str] = None,
        renewal_type: str = "one_time",
        is_provisional: bool = False,
        provisional_conditions: Optional[str] = None,
        # Reinstatement
        reinstated_from: Optional[UUID] = None,
    ) -> StudentScholarship:
        """Award scholarship to a student."""
        # Validate dates
        if effective_to and effective_from > effective_to:
            raise FinanceServiceError(
                "Effective end date must be after start date",
                code="invalid_dates",
            )

        scholarship = await self.get_scholarship(scholarship_id)
        if not scholarship:
            raise FinanceServiceError(
                "Scholarship not found",
                code="not_found",
            )

        if not scholarship.is_active:
            raise FinanceServiceError(
                "Scholarship is not active",
                code="inactive",
            )

        # Check max recipients
        if scholarship.max_recipients:
            active_count = len([
                r for r in scholarship.recipients
                if r.status == ScholarshipStatus.ACTIVE
                and r.academic_year_id == academic_year_id
            ])
            if active_count >= scholarship.max_recipients:
                raise FinanceServiceError(
                    f"Maximum recipients ({scholarship.max_recipients}) reached",
                    code="max_recipients",
                )

        # Check if student already has an ACTIVE scholarship (allow re-awarding after revocation)
        existing = await self.db.execute(
            select(StudentScholarship).where(
                and_(
                    StudentScholarship.tenant_id == tenant_id,
                    StudentScholarship.scholarship_id == scholarship_id,
                    StudentScholarship.student_id == student_id,
                    StudentScholarship.academic_year_id == academic_year_id,
                    StudentScholarship.status == ScholarshipStatus.ACTIVE,  # Only check for active
                )
            )
        )
        if existing.scalar_one_or_none():
            raise FinanceServiceError(
                "Student already has an active scholarship for this academic year",
                code="duplicate_award",
            )

        # Validate reinstated_from if provided
        if reinstated_from:
            revoked_result = await self.db.execute(
                select(StudentScholarship).where(
                    and_(
                        StudentScholarship.id == reinstated_from,
                        StudentScholarship.scholarship_id == scholarship_id,
                        StudentScholarship.student_id == student_id,
                        StudentScholarship.status == ScholarshipStatus.REVOKED,
                    )
                )
            )
            if not revoked_result.scalar_one_or_none():
                raise FinanceServiceError(
                    "Invalid reinstated_from: must reference a revoked scholarship for the same student",
                    code="invalid_reinstatement",
                )

        student_scholarship = StudentScholarship(
            tenant_id=tenant_id,
            scholarship_id=scholarship_id,
            student_id=student_id,
            academic_year_id=academic_year_id,
            awarded_by=awarded_by,
            awarded_at=datetime.now(UTC),
            status=ScholarshipStatus.ACTIVE,
            effective_from=effective_from,
            effective_to=effective_to,
            coverage_override=coverage_override,
            notes=notes,
            # Enhanced award settings
            justification=justification,
            renewal_type=renewal_type,
            is_provisional=is_provisional,
            provisional_conditions=provisional_conditions,
            # Reinstatement tracking
            reinstated_from=reinstated_from,
        )
        self.db.add(student_scholarship)
        await self.db.commit()

        # Re-fetch with relationships loaded for response building
        result = await self.db.execute(
            select(StudentScholarship)
            .where(StudentScholarship.id == student_scholarship.id)
            .options(
                joinedload(StudentScholarship.scholarship),
                joinedload(StudentScholarship.student),
                joinedload(StudentScholarship.academic_year),
                joinedload(StudentScholarship.awarded_by_user),
            )
        )
        return result.scalar_one()

    async def revoke_scholarship(
        self,
        student_scholarship_id: UUID,
        revoked_by: UUID,
        reason: str,
        create_adjustment_invoices: bool = True,
    ) -> Optional[StudentScholarship]:
        """
        Revoke a student's scholarship.

        Args:
            student_scholarship_id: The student scholarship to revoke
            revoked_by: User ID who is revoking
            reason: Reason for revocation
            create_adjustment_invoices: If True, creates adjustment invoices to
                add back the scholarship discount on affected invoices

        Returns:
            The revoked StudentScholarship
        """
        result = await self.db.execute(
            select(StudentScholarship)
            .options(joinedload(StudentScholarship.scholarship))
            .where(StudentScholarship.id == student_scholarship_id)
        )
        student_scholarship = result.scalar_one_or_none()
        if not student_scholarship:
            return None

        if student_scholarship.status == ScholarshipStatus.REVOKED:
            raise FinanceServiceError(
                "Scholarship is already revoked",
                code="already_revoked",
            )

        # Update scholarship status
        student_scholarship.status = ScholarshipStatus.REVOKED
        student_scholarship.revoked_by = revoked_by
        student_scholarship.revoked_at = datetime.now(UTC)
        student_scholarship.revoke_reason = reason

        # Create adjustment invoices if requested
        if create_adjustment_invoices:
            # Find all invoices that have scholarship items from this award
            scholarship_items_result = await self.db.execute(
                select(InvoiceScholarshipItem)
                .options(joinedload(InvoiceScholarshipItem.invoice))
                .where(
                    InvoiceScholarshipItem.student_scholarship_id == student_scholarship_id
                )
            )
            scholarship_items = scholarship_items_result.scalars().all()

            # Group by invoice and create adjustment invoices
            for item in scholarship_items:
                invoice = item.invoice
                if not invoice or invoice.deleted_at:
                    continue

                # Only create adjustments for issued/partial/paid invoices
                if invoice.status not in (
                    InvoiceStatus.ISSUED,
                    InvoiceStatus.PARTIAL,
                    InvoiceStatus.PAID,
                    InvoiceStatus.OVERDUE,
                ):
                    continue

                # Create an adjustment invoice to add back the scholarship amount
                adjustment_invoice = await self._create_scholarship_revocation_adjustment(
                    original_invoice=invoice,
                    scholarship_item=item,
                    revoked_by=revoked_by,
                    reason=reason,
                )

                if adjustment_invoice:
                    # Update original invoice's scholarship_discount
                    invoice.scholarship_discount -= item.calculated_amount
                    invoice.total_amount += item.calculated_amount
                    invoice.update_balance()

        await self.db.commit()
        await self.db.refresh(student_scholarship)
        return student_scholarship

    async def _create_scholarship_revocation_adjustment(
        self,
        original_invoice: Invoice,
        scholarship_item: InvoiceScholarshipItem,
        revoked_by: UUID,
        reason: str,
    ) -> Optional[Invoice]:
        """
        Create an adjustment invoice when a scholarship is revoked.

        The adjustment invoice adds back the scholarship discount that was
        previously applied, increasing the student's balance.
        """
        # Generate adjustment invoice number
        count_result = await self.db.execute(
            select(func.count(Invoice.id)).where(
                and_(
                    Invoice.tenant_id == original_invoice.tenant_id,
                    Invoice.adjustment_for_invoice_id == original_invoice.id,
                )
            )
        )
        adj_count = count_result.scalar() or 0

        adjustment_number = f"{original_invoice.invoice_number}-ADJ{adj_count + 1}"

        adjustment_invoice = Invoice(
            tenant_id=original_invoice.tenant_id,
            school_id=original_invoice.school_id,
            invoice_number=adjustment_number,
            student_id=original_invoice.student_id,
            fee_structure_id=None,
            academic_year_id=original_invoice.academic_year_id,
            term_id=original_invoice.term_id,
            subtotal=scholarship_item.calculated_amount,
            discount_amount=Decimal("0.00"),
            scholarship_discount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=scholarship_item.calculated_amount,
            amount_paid=Decimal("0.00"),
            balance=scholarship_item.calculated_amount,
            status=InvoiceStatus.ISSUED,
            issue_date=date.today(),
            due_date=original_invoice.due_date or date.today(),
            currency=original_invoice.currency,
            notes=f"Adjustment for scholarship revocation: {scholarship_item.scholarship_name}",
            created_by=revoked_by,
            issued_by=revoked_by,
            issued_at=datetime.now(UTC),
            # Adjustment tracking
            adjustment_for_invoice_id=original_invoice.id,
            adjustment_type="scholarship_revoked",
            adjustment_reason=reason,
        )
        self.db.add(adjustment_invoice)
        await self.db.flush()  # Get the ID

        # Create adjustment invoice item
        adjustment_item = InvoiceItem(
            tenant_id=original_invoice.tenant_id,
            invoice_id=adjustment_invoice.id,
            fee_item_id=None,
            description=f"Scholarship Revoked: {scholarship_item.scholarship_name} ({scholarship_item.scholarship_code})",
            quantity=1,
            unit_price=scholarship_item.calculated_amount,
            amount=scholarship_item.calculated_amount,
        )
        self.db.add(adjustment_item)

        return adjustment_invoice

    async def bulk_award_scholarship(
        self,
        tenant_id: UUID,
        scholarship_id: UUID,
        student_ids: list[UUID],
        academic_year_id: UUID,
        effective_from: date,
        effective_to: Optional[date] = None,
        coverage_override: Optional[Decimal] = None,
        notes: Optional[str] = None,
        awarded_by: Optional[UUID] = None,
        # Enhanced award settings
        justification: Optional[str] = None,
        renewal_type: str = "one_time",
        is_provisional: bool = False,
        provisional_conditions: Optional[str] = None,
    ) -> dict:
        """Award scholarship to multiple students."""
        result = {
            "awarded": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
            "student_scholarship_ids": [],
        }

        # Get scholarship info once
        scholarship = await self.get_scholarship(scholarship_id)
        if not scholarship:
            raise FinanceServiceError(
                "Scholarship not found",
                code="not_found",
            )

        if not scholarship.is_active:
            raise FinanceServiceError(
                "Scholarship is not active",
                code="inactive",
            )

        for student_id in student_ids:
            try:
                student_scholarship = await self.award_scholarship(
                    tenant_id=tenant_id,
                    scholarship_id=scholarship_id,
                    student_id=student_id,
                    academic_year_id=academic_year_id,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    coverage_override=coverage_override,
                    notes=notes,
                    awarded_by=awarded_by,
                    # Enhanced award settings
                    justification=justification,
                    renewal_type=renewal_type,
                    is_provisional=is_provisional,
                    provisional_conditions=provisional_conditions,
                )
                result["awarded"] += 1
                result["student_scholarship_ids"].append(student_scholarship.id)
            except FinanceServiceError as e:
                if e.code == "duplicate_award":
                    result["skipped"] += 1
                    result["errors"].append(f"Student {student_id}: {e.message}")
                elif e.code == "max_recipients":
                    result["failed"] += 1
                    result["errors"].append(f"Student {student_id}: {e.message}")
                    # Stop processing if max recipients reached
                    break
                else:
                    result["failed"] += 1
                    result["errors"].append(f"Student {student_id}: {e.message}")
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"Student {student_id}: {str(e)}")

        return result

    async def get_student_scholarships(
        self,
        student_id: UUID,
        academic_year_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Sequence[StudentScholarship]:
        """Get all scholarships for a student."""
        query = select(StudentScholarship).where(
            StudentScholarship.student_id == student_id
        ).options(
            joinedload(StudentScholarship.scholarship),
            joinedload(StudentScholarship.academic_year),
        )

        if academic_year_id:
            query = query.where(StudentScholarship.academic_year_id == academic_year_id)
        if status:
            query = query.where(StudentScholarship.status == ScholarshipStatus(status))

        query = query.order_by(desc(StudentScholarship.awarded_at))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_scholarship_recipients(
        self,
        scholarship_id: UUID,
        academic_year_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[StudentScholarship], int]:
        """Get all recipients of a scholarship."""
        query = select(StudentScholarship).where(
            StudentScholarship.scholarship_id == scholarship_id
        )

        if academic_year_id:
            query = query.where(StudentScholarship.academic_year_id == academic_year_id)
        if status:
            query = query.where(StudentScholarship.status == ScholarshipStatus(status))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results with all relationships for response building
        query = query.options(
            joinedload(StudentScholarship.student),
            joinedload(StudentScholarship.scholarship),
            joinedload(StudentScholarship.academic_year),
            joinedload(StudentScholarship.awarded_by_user),
        ).order_by(desc(StudentScholarship.awarded_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total


# =========================
# Dashboard Service
# =========================


class FinanceDashboardService:
    """Service for finance dashboard and analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_stats(
        self,
        tenant_id: UUID,
        school_id: UUID,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> dict:
        """Get finance dashboard statistics."""
        # Build base filter
        invoice_filter = [
            Invoice.tenant_id == tenant_id,
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status != InvoiceStatus.CANCELLED,
        ]
        if academic_year_id:
            invoice_filter.append(Invoice.academic_year_id == academic_year_id)
        if term_id:
            invoice_filter.append(Invoice.term_id == term_id)

        # Get invoice stats
        invoice_stats = await self.db.execute(
            select(
                func.sum(Invoice.total_amount).label("expected"),
                func.sum(Invoice.amount_paid).label("collected"),
                func.count(Invoice.id).label("total"),
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.PAID, 1),
                        else_=0,
                    )
                ).label("paid"),
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.PARTIAL, 1),
                        else_=0,
                    )
                ).label("partial"),
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.OVERDUE, 1),
                        else_=0,
                    )
                ).label("overdue"),
            ).where(and_(*invoice_filter))
        )
        stats = invoice_stats.one()

        # Get payment count
        payment_filter = [
            Payment.tenant_id == tenant_id,
            Payment.school_id == school_id,
            Payment.is_voided == False,
        ]
        payment_count = await self.db.execute(
            select(func.count(Payment.id)).where(and_(*payment_filter))
        )

        # Get scholarship stats
        scholarship_filter = [
            StudentScholarship.tenant_id == tenant_id,
            StudentScholarship.status == ScholarshipStatus.ACTIVE,
        ]
        if academic_year_id:
            scholarship_filter.append(StudentScholarship.academic_year_id == academic_year_id)

        scholarship_stats = await self.db.execute(
            select(func.count(StudentScholarship.id)).where(and_(*scholarship_filter))
        )

        # Get total scholarship discount value from invoices
        scholarship_value_result = await self.db.execute(
            select(func.sum(Invoice.scholarship_discount)).where(and_(*invoice_filter))
        )
        total_scholarships_value = scholarship_value_result.scalar() or Decimal("0.00")

        return {
            "expected_revenue": stats.expected or Decimal("0.00"),
            "collected_revenue": stats.collected or Decimal("0.00"),
            "outstanding_balance": (stats.expected or Decimal("0.00")) - (stats.collected or Decimal("0.00")),
            "total_invoices": stats.total or 0,
            "paid_invoices": stats.paid or 0,
            "partial_invoices": stats.partial or 0,
            "overdue_invoices": stats.overdue or 0,
            "total_payments": payment_count.scalar() or 0,
            "total_scholarships_value": total_scholarships_value,
            "scholarship_recipients": scholarship_stats.scalar() or 0,
        }

    async def get_recent_payments(
        self,
        tenant_id: UUID,
        school_id: UUID,
        limit: int = 5,
    ) -> Sequence[Payment]:
        """Get recent payments for dashboard."""
        query = select(Payment).where(
            and_(
                Payment.tenant_id == tenant_id,
                Payment.school_id == school_id,
                Payment.is_voided == False,
            )
        ).options(
            joinedload(Payment.student),
        ).order_by(desc(Payment.payment_date)).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_outstanding_by_class(
        self,
        tenant_id: UUID,
        school_id: UUID,
        academic_year_id: Optional[UUID] = None,
        term_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Get outstanding balance grouped by class."""
        filter_conditions = [
            Invoice.tenant_id == tenant_id,
            Invoice.school_id == school_id,
            Invoice.deleted_at.is_(None),
            Invoice.status.in_([
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIAL,
                InvoiceStatus.OVERDUE,
            ]),
        ]
        if academic_year_id:
            filter_conditions.append(Invoice.academic_year_id == academic_year_id)
        if term_id:
            filter_conditions.append(Invoice.term_id == term_id)

        query = (
            select(
                Class.id,
                Class.name,
                func.count(func.distinct(Invoice.student_id)).label("student_count"),
                func.sum(Invoice.total_amount - Invoice.amount_paid).label("total_outstanding"),
            )
            .select_from(Invoice)
            .join(Student, Invoice.student_id == Student.id)
            .join(Class, Student.class_id == Class.id)
            .where(and_(*filter_conditions))
            .group_by(Class.id, Class.name)
            .order_by(desc("total_outstanding"))
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "class_id": row.id,
                "class_name": row.name,
                "student_count": row.student_count,
                "total_outstanding": row.total_outstanding or Decimal("0.00"),
            }
            for row in rows
        ]


# =========================
# Finance Audit Service
# =========================


class FinanceAuditService:
    """
    Service for logging financial audit trail entries.

    This service records all changes to financial entities (invoices, payments,
    scholarships, etc.) for compliance and auditing purposes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        performed_by: UUID,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FinanceAuditLog:
        """
        Log an audit trail entry for a financial action.

        Args:
            tenant_id: The tenant ID
            entity_type: Type of entity (invoice, payment, scholarship, etc.)
            entity_id: ID of the entity being audited
            action: Action type (create, update, delete, void, issue, cancel, award, revoke)
            performed_by: User ID who performed the action
            field_name: Field that was changed (for updates)
            old_value: Previous value (JSON string for complex values)
            new_value: New value (JSON string for complex values)
            reason: Reason for the change
            metadata: Additional metadata about the change
            ip_address: IP address of the user
            user_agent: Browser/client user agent
        """
        audit_log = FinanceAuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            metadata_json=metadata,
            performed_by=performed_by,
            performed_at=datetime.now(UTC),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(audit_log)
        await self.db.flush()  # Don't commit - let the caller manage the transaction
        return audit_log

    async def log_create(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        performed_by: UUID,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log entity creation."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=FinanceAuditAction.CREATE.value,
            performed_by=performed_by,
            metadata=metadata,
            ip_address=ip_address,
        )

    async def log_update(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        performed_by: UUID,
        field_name: str,
        old_value: str,
        new_value: str,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log entity field update."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=FinanceAuditAction.UPDATE.value,
            performed_by=performed_by,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )

    async def log_void(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_id: UUID,
        performed_by: UUID,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log entity void action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=FinanceAuditAction.VOID.value,
            performed_by=performed_by,
            reason=reason,
            ip_address=ip_address,
        )

    async def log_scholarship_award(
        self,
        tenant_id: UUID,
        student_scholarship_id: UUID,
        performed_by: UUID,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log scholarship award."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type="student_scholarship",
            entity_id=student_scholarship_id,
            action=FinanceAuditAction.AWARD.value,
            performed_by=performed_by,
            metadata=metadata,
            ip_address=ip_address,
        )

    async def log_scholarship_revoke(
        self,
        tenant_id: UUID,
        student_scholarship_id: UUID,
        performed_by: UUID,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> FinanceAuditLog:
        """Log scholarship revocation."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type="student_scholarship",
            entity_id=student_scholarship_id,
            action=FinanceAuditAction.REVOKE.value,
            performed_by=performed_by,
            reason=reason,
            ip_address=ip_address,
        )

    async def get_entity_audit_log(
        self,
        entity_type: str,
        entity_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[FinanceAuditLog], int]:
        """Get audit log entries for a specific entity."""
        query = select(FinanceAuditLog).where(
            and_(
                FinanceAuditLog.entity_type == entity_type,
                FinanceAuditLog.entity_id == entity_id,
            )
        )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(FinanceAuditLog.performed_by_user),
        ).order_by(desc(FinanceAuditLog.performed_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def get_tenant_audit_log(
        self,
        tenant_id: UUID,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        performed_by: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[FinanceAuditLog], int]:
        """Get audit log entries for a tenant with optional filters."""
        query = select(FinanceAuditLog).where(
            FinanceAuditLog.tenant_id == tenant_id
        )

        if entity_type:
            query = query.where(FinanceAuditLog.entity_type == entity_type)
        if action:
            query = query.where(FinanceAuditLog.action == action)
        if performed_by:
            query = query.where(FinanceAuditLog.performed_by == performed_by)
        if start_date:
            query = query.where(func.date(FinanceAuditLog.performed_at) >= start_date)
        if end_date:
            query = query.where(func.date(FinanceAuditLog.performed_at) <= end_date)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(FinanceAuditLog.performed_by_user),
        ).order_by(desc(FinanceAuditLog.performed_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total


class CreditNoteService:
    """Service for credit note operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_credit_note_number(self, tenant_id: UUID) -> str:
        """Generate unique credit note number for tenant."""
        year = datetime.now().year
        # Get next sequence value
        result = await self.db.execute(text("SELECT nextval('credit_note_number_seq')"))
        seq_num = result.scalar()
        return f"CN-{year}-{seq_num:05d}"

    async def create_credit_note(
        self,
        tenant_id: UUID,
        school_id: UUID,
        data: "CreditNoteCreate",
    ) -> CreditNote:
        """Create a new credit note."""
        credit_note_number = await self._generate_credit_note_number(tenant_id)

        credit_note = CreditNote(
            tenant_id=tenant_id,
            school_id=school_id,
            credit_note_number=credit_note_number,
            credit_note_type=data.credit_note_type,
            original_invoice_id=data.original_invoice_id,
            student_id=data.student_id,
            amount=data.amount,
            currency=data.currency or "GHS",
            reason=data.reason,
            status=CreditNoteStatus.DRAFT,
            notes=data.notes,
        )
        self.db.add(credit_note)
        await self.db.commit()
        await self.db.refresh(credit_note)
        return credit_note

    async def get_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
    ) -> Optional[CreditNote]:
        """Get credit note by ID."""
        query = (
            select(CreditNote)
            .options(
                joinedload(CreditNote.student),
                joinedload(CreditNote.original_invoice),
                joinedload(CreditNote.applied_to_invoice),
                joinedload(CreditNote.issued_by_user),
            )
            .where(
                CreditNote.id == credit_note_id,
                CreditNote.tenant_id == tenant_id,
                CreditNote.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_credit_notes(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        status: Optional[CreditNoteStatus] = None,
        credit_note_type: Optional[CreditNoteType] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[CreditNote], int]:
        """List credit notes with filters."""
        query = select(CreditNote).where(
            CreditNote.tenant_id == tenant_id,
            CreditNote.deleted_at.is_(None),
        )

        if school_id:
            query = query.where(CreditNote.school_id == school_id)
        if student_id:
            query = query.where(CreditNote.student_id == student_id)
        if status:
            query = query.where(CreditNote.status == status)
        if credit_note_type:
            query = query.where(CreditNote.credit_note_type == credit_note_type)
        if search:
            from app.models.student import Student
            # Use subquery to find matching student IDs to avoid join conflicts with joinedload
            student_subq = (
                select(Student.id)
                .where(
                    or_(
                        Student.first_name.ilike(f"%{search}%"),
                        Student.last_name.ilike(f"%{search}%"),
                        Student.student_id.ilike(f"%{search}%"),
                    )
                )
            )
            query = query.where(
                or_(
                    CreditNote.credit_note_number.ilike(f"%{search}%"),
                    CreditNote.student_id.in_(student_subq),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.options(
            joinedload(CreditNote.student),
        ).order_by(desc(CreditNote.created_at))

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return result.scalars().unique().all(), total

    async def update_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteUpdate",
    ) -> Optional[CreditNote]:
        """Update a draft credit note."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Can only update draft credit notes")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(credit_note, key, value)

        credit_note.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(credit_note)
        return credit_note

    async def issue_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        issued_by: UUID,
        auto_apply: bool = False,
    ) -> tuple[Optional[CreditNote], Optional[Invoice]]:
        """
        Issue a credit note, making it active.

        Args:
            credit_note_id: The credit note ID
            tenant_id: The tenant ID
            issued_by: The user issuing the credit note
            auto_apply: If True, automatically apply to oldest unpaid invoice

        Returns:
            Tuple of (credit_note, applied_invoice) - applied_invoice is None if not auto-applied
        """
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None, None

        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Can only issue draft credit notes")

        credit_note.status = CreditNoteStatus.ISSUED
        credit_note.issued_by = issued_by
        credit_note.issued_at = datetime.now(timezone.utc)
        credit_note.updated_at = datetime.now(timezone.utc)

        # Update student's credit balance
        student_query = select(Student).where(Student.id == credit_note.student_id)
        student_result = await self.db.execute(student_query)
        student = student_result.scalars().first()
        if student:
            current_balance = student.credit_balance or Decimal("0.00")
            student.credit_balance = current_balance + credit_note.amount

        await self.db.commit()
        await self.db.refresh(credit_note)

        applied_invoice = None

        # Auto-apply to oldest unpaid invoice if requested
        if auto_apply and student:
            # Find oldest unpaid invoice for this student
            invoice_query = (
                select(Invoice)
                .where(
                    Invoice.student_id == credit_note.student_id,
                    Invoice.tenant_id == tenant_id,
                    Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE]),
                    Invoice.balance > 0,
                    Invoice.deleted_at.is_(None),
                )
                .order_by(Invoice.issue_date.asc(), Invoice.created_at.asc())
                .limit(1)
            )
            invoice_result = await self.db.execute(invoice_query)
            oldest_invoice = invoice_result.scalars().first()

            if oldest_invoice:
                # Apply the credit to this invoice
                apply_amount = min(credit_note.amount, oldest_invoice.balance)

                credit_note.status = CreditNoteStatus.APPLIED
                credit_note.applied_to_invoice_id = oldest_invoice.id
                credit_note.applied_amount = apply_amount
                credit_note.applied_by = issued_by
                credit_note.applied_at = datetime.now(timezone.utc)
                credit_note.updated_at = datetime.now(timezone.utc)

                # Update invoice
                oldest_invoice.amount_paid = oldest_invoice.amount_paid + apply_amount
                oldest_invoice.balance = oldest_invoice.total_amount - oldest_invoice.amount_paid
                if oldest_invoice.balance <= 0:
                    oldest_invoice.status = InvoiceStatus.PAID
                elif oldest_invoice.amount_paid > 0:
                    oldest_invoice.status = InvoiceStatus.PARTIAL

                # Update student credit balance (subtract what was applied)
                student.credit_balance = student.credit_balance - apply_amount

                await self.db.commit()
                await self.db.refresh(credit_note)
                await self.db.refresh(oldest_invoice)
                applied_invoice = oldest_invoice

        return credit_note, applied_invoice

    async def apply_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteApply",
        applied_by: UUID,
    ) -> Optional[CreditNote]:
        """Apply a credit note to an invoice."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status != CreditNoteStatus.ISSUED:
            raise ValueError("Can only apply issued credit notes")

        # Get the invoice to apply to
        invoice_query = select(Invoice).where(
            Invoice.id == data.invoice_id,
            Invoice.tenant_id == tenant_id,
        )
        invoice_result = await self.db.execute(invoice_query)
        invoice = invoice_result.scalars().first()
        if not invoice:
            raise ValueError("Invoice not found")

        # Validate invoice belongs to same student
        if invoice.student_id != credit_note.student_id:
            raise ValueError("Invoice belongs to a different student")

        # Calculate apply amount
        apply_amount = min(data.amount or credit_note.amount, credit_note.amount, invoice.balance)

        credit_note.status = CreditNoteStatus.APPLIED
        credit_note.applied_to_invoice_id = data.invoice_id
        credit_note.applied_amount = apply_amount
        credit_note.applied_by = applied_by
        credit_note.applied_at = datetime.now(timezone.utc)
        credit_note.updated_at = datetime.now(timezone.utc)

        # Update invoice
        invoice.amount_paid = invoice.amount_paid + apply_amount
        invoice.balance = invoice.total_amount - invoice.amount_paid
        if invoice.balance <= 0:
            invoice.status = InvoiceStatus.PAID
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIAL

        # Update student credit balance
        student_query = select(Student).where(Student.id == credit_note.student_id)
        student_result = await self.db.execute(student_query)
        student = student_result.scalars().first()
        if student:
            current_balance = student.credit_balance or Decimal("0.00")
            student.credit_balance = current_balance - apply_amount

        await self.db.commit()
        await self.db.refresh(credit_note)
        return credit_note

    async def refund_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteRefund",
        refunded_by: UUID,
    ) -> Optional[CreditNote]:
        """Refund a credit note to the student/guardian."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status != CreditNoteStatus.ISSUED:
            raise ValueError("Can only refund issued credit notes")

        credit_note.status = CreditNoteStatus.REFUNDED
        credit_note.refund_method = data.refund_method
        credit_note.refund_reference = data.refund_reference
        credit_note.refunded_by = refunded_by
        credit_note.refunded_at = datetime.now(timezone.utc)
        credit_note.updated_at = datetime.now(timezone.utc)

        # Update student credit balance
        student_query = select(Student).where(Student.id == credit_note.student_id)
        student_result = await self.db.execute(student_query)
        student = student_result.scalars().first()
        if student:
            current_balance = student.credit_balance or Decimal("0.00")
            student.credit_balance = current_balance - credit_note.amount

        await self.db.commit()
        await self.db.refresh(credit_note)
        return credit_note

    async def cancel_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
        data: "CreditNoteCancel",
        cancelled_by: UUID,
    ) -> Optional[CreditNote]:
        """Cancel a credit note."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return None

        if credit_note.status in [CreditNoteStatus.APPLIED, CreditNoteStatus.REFUNDED]:
            raise ValueError("Cannot cancel applied or refunded credit notes")

        # If issued, need to reverse the credit balance
        if credit_note.status == CreditNoteStatus.ISSUED:
            student_query = select(Student).where(Student.id == credit_note.student_id)
            student_result = await self.db.execute(student_query)
            student = student_result.scalars().first()
            if student:
                current_balance = student.credit_balance or Decimal("0.00")
                student.credit_balance = current_balance - credit_note.amount

        credit_note.status = CreditNoteStatus.CANCELLED
        credit_note.cancelled_by = cancelled_by
        credit_note.cancelled_at = datetime.now(timezone.utc)
        credit_note.cancel_reason = data.reason
        credit_note.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(credit_note)
        return credit_note

    async def delete_credit_note(
        self,
        credit_note_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        """Soft delete a draft credit note."""
        credit_note = await self.get_credit_note(credit_note_id, tenant_id)
        if not credit_note:
            return False

        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValueError("Can only delete draft credit notes")

        credit_note.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def get_student_credit_balance(
        self,
        student_id: UUID,
        tenant_id: UUID,
    ) -> Decimal:
        """Get student's available credit balance."""
        student_query = select(Student).where(
            Student.id == student_id,
            Student.tenant_id == tenant_id,
        )
        result = await self.db.execute(student_query)
        student = result.scalars().first()
        if not student:
            return Decimal("0.00")
        return student.credit_balance or Decimal("0.00")

    async def get_student_credit_notes(
        self,
        student_id: UUID,
        tenant_id: UUID,
        include_cancelled: bool = False,
    ) -> Sequence[CreditNote]:
        """Get all credit notes for a student."""
        query = select(CreditNote).where(
            CreditNote.student_id == student_id,
            CreditNote.tenant_id == tenant_id,
            CreditNote.deleted_at.is_(None),
        )

        if not include_cancelled:
            query = query.where(CreditNote.status != CreditNoteStatus.CANCELLED)

        query = query.order_by(desc(CreditNote.created_at))
        result = await self.db.execute(query)
        return result.scalars().all()

"""
SIMS Plus - Scholarship Service

Business logic for scholarship management, awarding, and revocation.
"""

from datetime import datetime, UTC, date
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.finance import (
    Invoice,
    InvoiceStatus,
    InvoiceItem,
    InvoiceScholarshipItem,
    Scholarship,
    ScholarshipType,
    CoverageType,
    StudentScholarship,
    ScholarshipStatus,
)
from app.services.finance._shared import FinanceServiceError


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
        await self.db.flush()
        await self.db.refresh(scholarship)
        return scholarship

    async def get_scholarship(self, tenant_id: UUID, scholarship_id: UUID) -> Optional[Scholarship]:
        """Get scholarship by ID."""
        query = select(Scholarship).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                Scholarship.tenant_id == tenant_id,
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
        self, tenant_id: UUID, scholarship_id: UUID, **kwargs
    ) -> Optional[Scholarship]:
        """Update scholarship."""
        scholarship = await self.get_scholarship(tenant_id, scholarship_id)
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

        await self.db.flush()
        await self.db.refresh(scholarship)
        return scholarship

    async def delete_scholarship(self, tenant_id: UUID, scholarship_id: UUID) -> bool:
        """Soft delete scholarship."""
        scholarship = await self.get_scholarship(tenant_id, scholarship_id)
        if not scholarship:
            return False

        scholarship.deleted_at = datetime.now(UTC)
        await self.db.flush()
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

        scholarship = await self.get_scholarship(tenant_id, scholarship_id)
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

        # Check max recipients using a direct count query to avoid stale
        # relationship data when multiple awards happen in the same session.
        if scholarship.max_recipients:
            active_count_result = await self.db.execute(
                select(func.count()).select_from(StudentScholarship).where(
                    and_(
                        StudentScholarship.scholarship_id == scholarship_id,
                        StudentScholarship.tenant_id == tenant_id,
                        StudentScholarship.status == ScholarshipStatus.ACTIVE,
                        StudentScholarship.academic_year_id == academic_year_id,
                    )
                )
            )
            active_count = active_count_result.scalar() or 0
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
        await self.db.flush()

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
        tenant_id: UUID,
        student_scholarship_id: UUID,
        revoked_by: UUID,
        reason: str,
        create_adjustment_invoices: bool = True,
    ) -> Optional[StudentScholarship]:
        """
        Revoke a student's scholarship.

        Args:
            tenant_id: The tenant ID (defense-in-depth)
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
            .where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    StudentScholarship.tenant_id == tenant_id,
                    StudentScholarship.id == student_scholarship_id,
                )
            )
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

        await self.db.flush()
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
                    Invoice.deleted_at.is_(None),
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
        scholarship = await self.get_scholarship(tenant_id, scholarship_id)
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
        tenant_id: UUID,
        student_id: UUID,
        academic_year_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Sequence[StudentScholarship]:
        """Get all scholarships for a student."""
        query = select(StudentScholarship).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                StudentScholarship.tenant_id == tenant_id,
                StudentScholarship.student_id == student_id,
            )
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
        tenant_id: UUID,
        scholarship_id: UUID,
        academic_year_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[StudentScholarship], int]:
        """Get all recipients of a scholarship."""
        query = select(StudentScholarship).where(
            and_(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                StudentScholarship.tenant_id == tenant_id,
                StudentScholarship.scholarship_id == scholarship_id,
            )
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

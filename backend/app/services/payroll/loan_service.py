"""
SIMS Plus - Loan Management Service

Full lifecycle management for staff loans: create, submit, approve, reject,
disburse, early repayment, restructure, write-off. Integrates with payroll
for automated installment deductions.

All queries filter by tenant_id (defense-in-depth on top of RLS).
Uses flush()/refresh() — the endpoint middleware handles commit.

CRITICAL: All balance mutations use with_for_update() to prevent
concurrent modification.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

import structlog
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payroll import (
    LOAN_VALID_TRANSITIONS,
    InterestMethod,
    LoanGuarantor,
    LoanInstallment,
    LoanPayment,
    LoanStatus,
    LoanType,
    PayrollItemDeduction,
    PayrollItem,
    StaffLoan,
)
from app.models.staff import Staff
from app.services.payroll.loan_calculation_service import (
    calculate_flat_rate_loan,
    calculate_reducing_balance_loan,
)

logger = structlog.get_logger()

TWO_DP = Decimal("0.01")
ZERO = Decimal("0.00")


class LoanService:
    """Service for managing staff loan lifecycle and payroll integration."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    # ==================================================================
    # Loan Type CRUD
    # ==================================================================

    async def list_loan_types(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
    ) -> list[LoanType]:
        """List loan types with optional filters."""
        query = (
            select(LoanType)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(LoanType.tenant_id == tenant_id)
            .where(LoanType.deleted_at.is_(None))
            .order_by(LoanType.name)
        )
        if school_id is not None:
            query = query.where(LoanType.school_id == school_id)
        if is_active is not None:
            query = query.where(LoanType.is_active == is_active)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_loan_type(
        self,
        tenant_id: UUID,
        loan_type_id: UUID,
    ) -> LoanType:
        """Get a single loan type by ID."""
        result = await self.db.execute(
            select(LoanType)
            .where(LoanType.tenant_id == tenant_id)
            .where(LoanType.id == loan_type_id)
            .where(LoanType.deleted_at.is_(None))
        )
        lt = result.scalar_one_or_none()
        if not lt:
            raise self.Error("Loan type not found", 404)
        return lt

    async def create_loan_type(
        self,
        tenant_id: UUID,
        data: dict,
    ) -> LoanType:
        """Create a new loan type."""
        # Check for duplicate code within same tenant (partial unique)
        existing = await self.db.execute(
            select(LoanType)
            .where(LoanType.tenant_id == tenant_id)
            .where(LoanType.code == data["code"])
            .where(LoanType.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise self.Error(
                f"Loan type with code '{data['code']}' already exists", 409
            )

        interest_method = data.get("default_interest_method", "flat")
        if isinstance(interest_method, str):
            interest_method = InterestMethod(interest_method)

        lt = LoanType(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            name=data["name"],
            code=data["code"],
            description=data.get("description"),
            default_interest_rate=data.get("default_interest_rate", Decimal("0.00")),
            default_interest_method=interest_method,
            max_amount=data.get("max_amount"),
            max_tenure_months=data.get("max_tenure_months"),
            max_active_loans=data.get("max_active_loans", 1),
            requires_guarantor=data.get("requires_guarantor", False),
            min_service_months=data.get("min_service_months", 0),
            max_deduction_pct=data.get("max_deduction_pct", Decimal("50.00")),
        )
        self.db.add(lt)
        await self.db.flush()
        await self.db.refresh(lt)
        return lt

    async def update_loan_type(
        self,
        tenant_id: UUID,
        loan_type_id: UUID,
        data: dict,
    ) -> LoanType:
        """Update a loan type."""
        lt = await self.get_loan_type(tenant_id, loan_type_id)

        # Check for duplicate code if code is being changed
        if "code" in data and data["code"] is not None and data["code"] != lt.code:
            existing = await self.db.execute(
                select(LoanType)
                .where(LoanType.tenant_id == tenant_id)
                .where(LoanType.code == data["code"])
                .where(LoanType.deleted_at.is_(None))
                .where(LoanType.id != loan_type_id)
            )
            if existing.scalar_one_or_none():
                raise self.Error(
                    f"Loan type with code '{data['code']}' already exists", 409
                )

        for field, value in data.items():
            if value is not None and hasattr(lt, field):
                if field == "default_interest_method" and isinstance(value, str):
                    value = InterestMethod(value)
                setattr(lt, field, value)

        await self.db.flush()
        await self.db.refresh(lt)
        return lt

    async def delete_loan_type(
        self,
        tenant_id: UUID,
        loan_type_id: UUID,
    ) -> None:
        """Soft-delete a loan type."""
        lt = await self.get_loan_type(tenant_id, loan_type_id)

        # Prevent deletion if active loans reference this type
        active_count_result = await self.db.execute(
            select(func.count(StaffLoan.id))
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.loan_type_id == loan_type_id)
            .where(StaffLoan.status.in_([
                LoanStatus.DRAFT, LoanStatus.PENDING_APPROVAL,
                LoanStatus.APPROVED, LoanStatus.ACTIVE,
            ]))
            .where(StaffLoan.deleted_at.is_(None))
        )
        if active_count_result.scalar() > 0:
            raise self.Error(
                "Cannot delete loan type with active or pending loans", 409
            )

        lt.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ==================================================================
    # Loan Number Generation
    # ==================================================================

    async def _generate_loan_number(self, tenant_id: UUID) -> str:
        """
        Generate a sequential loan number: LN-{YYYY}-{seq:04d}.

        Uses a count of existing loans in the current year for sequencing.
        The calling code should hold a lock or this should be called within
        a serializable transaction to prevent duplicates.
        """
        current_year = date.today().year
        count_result = await self.db.execute(
            select(func.count(StaffLoan.id))
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.loan_number.like(f"LN-{current_year}-%"))
        )
        seq = (count_result.scalar() or 0) + 1
        return f"LN-{current_year}-{seq:04d}"

    async def _generate_payment_number(self, tenant_id: UUID) -> str:
        """Generate a sequential payment number: LP-{YYYY}-{seq:04d}."""
        current_year = date.today().year
        count_result = await self.db.execute(
            select(func.count(LoanPayment.id))
            .where(LoanPayment.tenant_id == tenant_id)
            .where(LoanPayment.payment_number.like(f"LP-{current_year}-%"))
        )
        seq = (count_result.scalar() or 0) + 1
        return f"LP-{current_year}-{seq:04d}"

    # ==================================================================
    # Loan CRUD + Lifecycle
    # ==================================================================

    async def list_loans(
        self,
        tenant_id: UUID,
        status: Optional[str] = None,
        staff_id: Optional[UUID] = None,
        loan_type_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[StaffLoan], int]:
        """List loans with filters. Returns (loans, total_count)."""
        base = (
            select(StaffLoan)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.deleted_at.is_(None))
        )

        if status is not None:
            base = base.where(StaffLoan.status == status)
        if staff_id is not None:
            base = base.where(StaffLoan.staff_id == staff_id)
        if loan_type_id is not None:
            base = base.where(StaffLoan.loan_type_id == loan_type_id)
        if school_id is not None:
            base = base.where(StaffLoan.school_id == school_id)

        # Count query
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        # Paginated query with staff relationship loaded for name
        query = (
            base
            .options(
                selectinload(StaffLoan.staff),
                selectinload(StaffLoan.loan_type),
            )
            .order_by(StaffLoan.created_at.desc())
            .limit(min(limit, 200))
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        *,
        load_relations: bool = True,
    ) -> StaffLoan:
        """Get a loan by ID with optional eager loading."""
        query = (
            select(StaffLoan)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.id == loan_id)
            .where(StaffLoan.deleted_at.is_(None))
        )
        if load_relations:
            query = query.options(
                selectinload(StaffLoan.staff),
                selectinload(StaffLoan.loan_type),
                selectinload(StaffLoan.guarantors).selectinload(
                    LoanGuarantor.guarantor_staff
                ),
            )

        result = await self.db.execute(query)
        loan = result.scalar_one_or_none()
        if not loan:
            raise self.Error("Loan not found", 404)
        return loan

    async def create_loan(
        self,
        tenant_id: UUID,
        data: dict,
        created_by: UUID,
    ) -> StaffLoan:
        """
        Create a new loan in draft status.

        Calculates the installment schedule preview and stores computed
        fields. Optionally adds initial guarantors.
        """
        # Validate loan type exists and is active
        loan_type = await self.get_loan_type(tenant_id, data["loan_type_id"])
        if not loan_type.is_active:
            raise self.Error("Loan type is inactive", 400)

        # Resolve interest rate and method (use loan type defaults if not specified)
        interest_rate = data.get("interest_rate")
        if interest_rate is None:
            interest_rate = loan_type.default_interest_rate

        interest_method_str = data.get("interest_method")
        if interest_method_str is None:
            interest_method = loan_type.default_interest_method
        else:
            interest_method = InterestMethod(interest_method_str)

        principal = data["principal_amount"]
        tenure = data["tenure_months"]

        # Validate against loan type limits
        if loan_type.max_amount is not None and principal > loan_type.max_amount:
            raise self.Error(
                f"Principal exceeds loan type maximum of {loan_type.max_amount}", 400
            )
        if loan_type.max_tenure_months is not None and tenure > loan_type.max_tenure_months:
            raise self.Error(
                f"Tenure exceeds loan type maximum of {loan_type.max_tenure_months} months", 400
            )

        # Calculate schedule to store computed fields
        if interest_method == InterestMethod.FLAT:
            calc = calculate_flat_rate_loan(principal, interest_rate, tenure)
        else:
            calc = calculate_reducing_balance_loan(principal, interest_rate, tenure)

        # Generate loan number
        loan_number = await self._generate_loan_number(tenant_id)

        loan = StaffLoan(
            tenant_id=tenant_id,
            school_id=data.get("school_id"),
            loan_number=loan_number,
            staff_id=data["staff_id"],
            loan_type_id=data["loan_type_id"],
            status=LoanStatus.DRAFT,
            principal_amount=principal,
            interest_rate=interest_rate,
            interest_method=interest_method,
            total_interest=calc["total_interest"],
            total_repayable=calc["total_repayable"],
            tenure_months=tenure,
            monthly_installment=calc["monthly_installment"],
            total_paid=ZERO,
            outstanding_balance=calc["total_repayable"],
            installments_paid=0,
            installments_remaining=tenure,
            first_deduction_date=data["first_deduction_date"],
            purpose=data.get("purpose"),
            created_by=created_by,
            notes=data.get("notes"),
        )
        self.db.add(loan)
        await self.db.flush()
        await self.db.refresh(loan)

        # Add guarantors if provided
        for gid in data.get("guarantor_staff_ids", []):
            guarantor = LoanGuarantor(
                tenant_id=tenant_id,
                loan_id=loan.id,
                guarantor_staff_id=gid,
            )
            self.db.add(guarantor)

        if data.get("guarantor_staff_ids"):
            await self.db.flush()

        logger.info(
            "loan_created",
            loan_id=str(loan.id),
            loan_number=loan_number,
            staff_id=str(data["staff_id"]),
            principal=str(principal),
            tenant_id=str(tenant_id),
        )

        # Re-fetch with relations loaded for the response
        return await self.get_loan(tenant_id, loan.id)

    async def update_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        data: dict,
    ) -> StaffLoan:
        """Update a draft loan. Only draft loans can be updated."""
        loan = await self.get_loan(tenant_id, loan_id)

        if loan.status != LoanStatus.DRAFT:
            raise self.Error("Only draft loans can be updated", 409)

        # Apply updates
        updatable_fields = {
            "principal_amount", "interest_rate", "interest_method",
            "tenure_months", "first_deduction_date", "purpose", "notes",
        }
        changed = False
        for field, value in data.items():
            if value is not None and field in updatable_fields:
                if field == "interest_method" and isinstance(value, str):
                    value = InterestMethod(value)
                setattr(loan, field, value)
                changed = True

        if changed:
            # Recalculate schedule with potentially new terms
            if loan.interest_method == InterestMethod.FLAT:
                calc = calculate_flat_rate_loan(
                    loan.principal_amount, loan.interest_rate, loan.tenure_months
                )
            else:
                calc = calculate_reducing_balance_loan(
                    loan.principal_amount, loan.interest_rate, loan.tenure_months
                )

            loan.total_interest = calc["total_interest"]
            loan.total_repayable = calc["total_repayable"]
            loan.monthly_installment = calc["monthly_installment"]
            loan.outstanding_balance = calc["total_repayable"]
            loan.installments_remaining = loan.tenure_months

        await self.db.flush()
        await self.db.refresh(loan)
        return await self.get_loan(tenant_id, loan.id)

    async def delete_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
    ) -> None:
        """Soft-delete a draft loan."""
        loan = await self.get_loan(tenant_id, loan_id, load_relations=False)

        if loan.status != LoanStatus.DRAFT:
            raise self.Error("Only draft loans can be cancelled", 409)

        loan.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ==================================================================
    # State Transitions
    # ==================================================================

    def _validate_transition(
        self,
        current: LoanStatus,
        target: LoanStatus,
    ) -> None:
        """Validate that a state transition is allowed."""
        allowed = LOAN_VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise self.Error(
                f"Cannot transition from '{current.value}' to '{target.value}'",
                409,
            )

    async def submit_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
    ) -> StaffLoan:
        """Submit a draft loan for approval."""
        loan = await self.get_loan(tenant_id, loan_id)
        self._validate_transition(loan.status, LoanStatus.PENDING_APPROVAL)

        # Check eligibility before submission
        eligibility = await self.check_eligibility(
            tenant_id, loan.staff_id, loan.loan_type_id
        )
        if not eligibility["eligible"]:
            reasons_str = "; ".join(eligibility["reasons"])
            raise self.Error(f"Staff not eligible: {reasons_str}", 400)

        # If loan type requires guarantors, verify at least one exists
        loan_type = loan.loan_type
        if loan_type.requires_guarantor:
            guarantor_count = await self.db.execute(
                select(func.count(LoanGuarantor.id))
                .where(LoanGuarantor.loan_id == loan_id)
                .where(LoanGuarantor.tenant_id == tenant_id)
            )
            if (guarantor_count.scalar() or 0) == 0:
                raise self.Error(
                    "This loan type requires at least one guarantor", 400
                )

        loan.status = LoanStatus.PENDING_APPROVAL
        await self.db.flush()
        await self.db.refresh(loan)

        logger.info(
            "loan_submitted",
            loan_id=str(loan_id),
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, loan.id)

    async def approve_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        approver_id: UUID,
        approver_staff_id: Optional[UUID],
        comments: Optional[str] = None,
    ) -> StaffLoan:
        """
        Approve a pending loan.

        Self-approval prevention: the approver cannot be the borrower
        AND the approver cannot be the person who created the loan.
        """
        loan = await self.get_loan(tenant_id, loan_id)
        self._validate_transition(loan.status, LoanStatus.APPROVED)

        # Self-approval prevention check #1: borrower cannot approve own loan
        if approver_staff_id is not None and loan.staff_id == approver_staff_id:
            raise self.Error(
                "Borrower cannot approve their own loan", 403
            )

        # Self-approval prevention check #2: creator cannot approve
        if loan.created_by == approver_id:
            raise self.Error(
                "The person who submitted the loan cannot also approve it", 403
            )

        # Guarantor consent check: if the loan type requires a guarantor,
        # all guarantors must have given consent before approval
        if loan.loan_type and loan.loan_type.requires_guarantor:
            guarantor_result = await self.db.execute(
                select(LoanGuarantor).where(
                    LoanGuarantor.loan_id == loan.id,
                    LoanGuarantor.tenant_id == tenant_id,
                )
            )
            guarantors = guarantor_result.scalars().all()
            if not guarantors:
                raise self.Error(
                    "Loan type requires at least one guarantor", 409
                )
            unconsented = [g for g in guarantors if not g.consent_given]
            if unconsented:
                raise self.Error(
                    f"All guarantors must give consent before approval. "
                    f"{len(unconsented)} pending.",
                    409,
                )

        loan.status = LoanStatus.APPROVED
        loan.approved_by = approver_id
        loan.approval_date = date.today()
        loan.notes = (
            f"{loan.notes or ''}\n[Approved] {comments}".strip()
            if comments
            else loan.notes
        )

        await self.db.flush()
        await self.db.refresh(loan)

        logger.info(
            "loan_approved",
            loan_id=str(loan_id),
            approver_id=str(approver_id),
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, loan.id)

    async def reject_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        rejector_id: UUID,
        reason: Optional[str] = None,
    ) -> StaffLoan:
        """Reject a pending loan, returning it to rejected status."""
        loan = await self.get_loan(tenant_id, loan_id)
        self._validate_transition(loan.status, LoanStatus.REJECTED)

        loan.status = LoanStatus.REJECTED
        loan.notes = (
            f"{loan.notes or ''}\n[Rejected] {reason}".strip()
            if reason
            else loan.notes
        )

        await self.db.flush()
        await self.db.refresh(loan)

        logger.info(
            "loan_rejected",
            loan_id=str(loan_id),
            rejector_id=str(rejector_id),
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, loan.id)

    async def disburse_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        disbursed_by: UUID,
    ) -> StaffLoan:
        """
        Disburse an approved loan.

        Generates the installment schedule rows in the database with
        due dates starting from first_deduction_date.
        """
        loan = await self.get_loan(tenant_id, loan_id, load_relations=False)
        self._validate_transition(loan.status, LoanStatus.ACTIVE)

        if not loan.first_deduction_date:
            raise self.Error("First deduction date must be set before disbursement", 400)

        # Calculate installment schedule
        if loan.interest_method == InterestMethod.FLAT:
            calc = calculate_flat_rate_loan(
                loan.principal_amount, loan.interest_rate, loan.tenure_months
            )
        else:
            calc = calculate_reducing_balance_loan(
                loan.principal_amount, loan.interest_rate, loan.tenure_months
            )

        # Generate installment rows
        for inst_data in calc["installments"]:
            due_date = loan.first_deduction_date + relativedelta(
                months=inst_data["installment_number"] - 1
            )
            installment = LoanInstallment(
                tenant_id=tenant_id,
                school_id=loan.school_id,
                loan_id=loan.id,
                installment_number=inst_data["installment_number"],
                due_date=due_date,
                principal_component=inst_data["principal_component"],
                interest_component=inst_data["interest_component"],
                installment_amount=inst_data["installment_amount"],
                opening_balance=inst_data["opening_balance"],
                closing_balance=inst_data["closing_balance"],
            )
            self.db.add(installment)

        # Set expected completion date
        expected_completion = loan.first_deduction_date + relativedelta(
            months=loan.tenure_months - 1
        )

        loan.status = LoanStatus.ACTIVE
        loan.disbursement_date = date.today()
        loan.disbursed_by = disbursed_by
        loan.expected_completion_date = expected_completion

        await self.db.flush()
        await self.db.refresh(loan)

        logger.info(
            "loan_disbursed",
            loan_id=str(loan_id),
            disbursed_by=str(disbursed_by),
            installments=loan.tenure_months,
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, loan.id)

    # ==================================================================
    # Eligibility Check
    # ==================================================================

    async def check_eligibility(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        loan_type_id: Optional[UUID] = None,
    ) -> dict:
        """
        Check if a staff member is eligible for a loan.

        Returns {eligible: bool, reasons: list[str], max_eligible_amount, max_eligible_tenure}.
        """
        reasons: list[str] = []

        # Fetch staff record to check employment date
        staff_result = await self.db.execute(
            select(Staff)
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.id == staff_id)
            .where(Staff.deleted_at.is_(None))
        )
        staff = staff_result.scalar_one_or_none()
        if not staff:
            return {"eligible": False, "reasons": ["Staff member not found"],
                    "max_eligible_amount": None, "max_eligible_tenure": None}

        # Check staff is active
        if getattr(staff, "status", "active") != "active":
            reasons.append("Staff member is not in active status")

        max_amount: Optional[Decimal] = None
        max_tenure: Optional[int] = None

        if loan_type_id:
            lt_result = await self.db.execute(
                select(LoanType)
                .where(LoanType.tenant_id == tenant_id)
                .where(LoanType.id == loan_type_id)
                .where(LoanType.deleted_at.is_(None))
            )
            loan_type = lt_result.scalar_one_or_none()
            if not loan_type:
                return {"eligible": False, "reasons": ["Loan type not found"],
                        "max_eligible_amount": None, "max_eligible_tenure": None}

            # Min service months check
            if loan_type.min_service_months > 0:
                months_employed = (
                    (date.today().year - staff.employment_date.year) * 12
                    + (date.today().month - staff.employment_date.month)
                )
                if months_employed < loan_type.min_service_months:
                    reasons.append(
                        f"Staff must have at least {loan_type.min_service_months} months "
                        f"of service (currently {months_employed})"
                    )

            # Max active loans of this type
            active_count_result = await self.db.execute(
                select(func.count(StaffLoan.id))
                .where(StaffLoan.tenant_id == tenant_id)
                .where(StaffLoan.staff_id == staff_id)
                .where(StaffLoan.loan_type_id == loan_type_id)
                .where(StaffLoan.status == LoanStatus.ACTIVE)
                .where(StaffLoan.deleted_at.is_(None))
            )
            active_count = active_count_result.scalar() or 0
            if active_count >= loan_type.max_active_loans:
                reasons.append(
                    f"Maximum active loans of this type ({loan_type.max_active_loans}) reached"
                )

            max_amount = loan_type.max_amount
            max_tenure = loan_type.max_tenure_months

        eligible = len(reasons) == 0
        return {
            "eligible": eligible,
            "reasons": reasons,
            "max_eligible_amount": max_amount,
            "max_eligible_tenure": max_tenure,
        }

    # ==================================================================
    # Guarantor Management
    # ==================================================================

    async def add_guarantor(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        data: dict,
    ) -> LoanGuarantor:
        """Add a guarantor to a loan (draft or pending_approval only)."""
        loan = await self.get_loan(tenant_id, loan_id, load_relations=False)
        if loan.status not in (LoanStatus.DRAFT, LoanStatus.PENDING_APPROVAL):
            raise self.Error("Guarantors can only be added to draft or pending loans", 409)

        # Prevent self-guaranteeing
        if data["guarantor_staff_id"] == loan.staff_id:
            raise self.Error("A borrower cannot guarantee their own loan", 400)

        # Check for duplicate
        existing = await self.db.execute(
            select(LoanGuarantor)
            .where(LoanGuarantor.tenant_id == tenant_id)
            .where(LoanGuarantor.loan_id == loan_id)
            .where(LoanGuarantor.guarantor_staff_id == data["guarantor_staff_id"])
        )
        if existing.scalar_one_or_none():
            raise self.Error("This staff member is already a guarantor for this loan", 409)

        guarantor = LoanGuarantor(
            tenant_id=tenant_id,
            loan_id=loan_id,
            guarantor_staff_id=data["guarantor_staff_id"],
            relationship_desc=data.get("relationship"),
            guaranteed_amount=data.get("guaranteed_amount"),
            notes=data.get("notes"),
        )
        self.db.add(guarantor)
        await self.db.flush()
        await self.db.refresh(guarantor)
        return guarantor

    async def remove_guarantor(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        guarantor_id: UUID,
    ) -> None:
        """Remove a guarantor (draft loans only)."""
        loan = await self.get_loan(tenant_id, loan_id, load_relations=False)
        if loan.status != LoanStatus.DRAFT:
            raise self.Error("Guarantors can only be removed from draft loans", 409)

        result = await self.db.execute(
            select(LoanGuarantor)
            .where(LoanGuarantor.tenant_id == tenant_id)
            .where(LoanGuarantor.id == guarantor_id)
            # IDOR check: guarantor must belong to the specified loan
            .where(LoanGuarantor.loan_id == loan_id)
        )
        guarantor = result.scalar_one_or_none()
        if not guarantor:
            raise self.Error("Guarantor not found", 404)

        await self.db.delete(guarantor)
        await self.db.flush()

    async def update_guarantor_consent(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        guarantor_id: UUID,
        consent_given: bool,
        notes: Optional[str] = None,
    ) -> LoanGuarantor:
        """Record guarantor consent."""
        result = await self.db.execute(
            select(LoanGuarantor)
            .where(LoanGuarantor.tenant_id == tenant_id)
            .where(LoanGuarantor.id == guarantor_id)
            .where(LoanGuarantor.loan_id == loan_id)
        )
        guarantor = result.scalar_one_or_none()
        if not guarantor:
            raise self.Error("Guarantor not found", 404)

        guarantor.consent_given = consent_given
        guarantor.consent_date = date.today() if consent_given else None
        if notes:
            guarantor.notes = notes

        await self.db.flush()
        await self.db.refresh(guarantor)
        return guarantor

    # ==================================================================
    # Installments & Payments Queries
    # ==================================================================

    async def get_installments(
        self,
        tenant_id: UUID,
        loan_id: UUID,
    ) -> list[LoanInstallment]:
        """Get all installments for a loan, ordered by number."""
        # Verify loan exists and belongs to tenant (IDOR check)
        await self.get_loan(tenant_id, loan_id, load_relations=False)

        result = await self.db.execute(
            select(LoanInstallment)
            .where(LoanInstallment.tenant_id == tenant_id)
            .where(LoanInstallment.loan_id == loan_id)
            .order_by(LoanInstallment.installment_number)
        )
        return list(result.scalars().all())

    async def get_payments(
        self,
        tenant_id: UUID,
        loan_id: UUID,
    ) -> list[LoanPayment]:
        """Get all payments for a loan, ordered by date."""
        await self.get_loan(tenant_id, loan_id, load_relations=False)

        result = await self.db.execute(
            select(LoanPayment)
            .where(LoanPayment.tenant_id == tenant_id)
            .where(LoanPayment.loan_id == loan_id)
            .order_by(LoanPayment.payment_date)
        )
        return list(result.scalars().all())

    # ==================================================================
    # Payroll Integration
    # ==================================================================

    async def get_due_installments(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        year: int,
        month: int,
    ) -> list[LoanInstallment]:
        """
        Get unpaid installments for a staff member in a given month.

        Used by the payroll calculation engine to determine loan deductions.
        Loads the loan and loan_type relationships for net salary cap calculation.
        """
        result = await self.db.execute(
            select(LoanInstallment)
            .join(StaffLoan, LoanInstallment.loan_id == StaffLoan.id)
            .options(
                selectinload(LoanInstallment.loan).selectinload(StaffLoan.loan_type),
            )
            .where(StaffLoan.staff_id == staff_id)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.status == LoanStatus.ACTIVE)
            .where(LoanInstallment.is_paid.is_(False))
            .where(extract("year", LoanInstallment.due_date) == year)
            .where(extract("month", LoanInstallment.due_date) == month)
            .order_by(LoanInstallment.installment_number)
        )
        return list(result.scalars().all())

    async def get_all_due_installments_for_run(
        self,
        tenant_id: UUID,
        year: int,
        month: int,
    ) -> dict[UUID, list[LoanInstallment]]:
        """
        Batch query: all due installments for all staff in a given month.

        Returns dict keyed by staff_id for O(1) lookup during payroll
        processing. This avoids N per-staff queries.
        """
        result = await self.db.execute(
            select(LoanInstallment)
            .join(StaffLoan, LoanInstallment.loan_id == StaffLoan.id)
            .options(
                selectinload(LoanInstallment.loan).selectinload(StaffLoan.loan_type),
            )
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.status == LoanStatus.ACTIVE)
            .where(LoanInstallment.is_paid.is_(False))
            .where(extract("year", LoanInstallment.due_date) == year)
            .where(extract("month", LoanInstallment.due_date) == month)
            .order_by(LoanInstallment.installment_number)
        )
        installments = result.scalars().all()

        # Group by staff_id
        by_staff: dict[UUID, list[LoanInstallment]] = defaultdict(list)
        for inst in installments:
            by_staff[inst.loan.staff_id].append(inst)
        return dict(by_staff)

    async def process_payroll_payment(
        self,
        tenant_id: UUID,
        payroll_run_id: UUID,
        performed_by: UUID,
    ) -> list[StaffLoan]:
        """
        Post-payment hook called after a payroll run is marked as paid.

        For each payroll_item_deduction with a loan_installment_id:
        1. Mark the installment as paid
        2. Create a loan_payment record
        3. Update the loan's running totals (with_for_update for safety)
        4. Auto-complete loans where outstanding_balance <= 0

        Returns list of newly completed loans.
        """
        # Find all deduction line items in this payroll run that are loan deductions
        ded_result = await self.db.execute(
            select(PayrollItemDeduction)
            .join(PayrollItem, PayrollItemDeduction.payroll_item_id == PayrollItem.id)
            .where(PayrollItem.payroll_run_id == payroll_run_id)
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItemDeduction.loan_installment_id.isnot(None))
        )
        deduction_rows = list(ded_result.scalars().all())

        if not deduction_rows:
            return []

        completed_loans: list[StaffLoan] = []

        # Group by loan_id for efficient loan-level updates
        loan_deductions: dict[UUID, list[tuple[PayrollItemDeduction, LoanInstallment]]] = defaultdict(list)

        for ded in deduction_rows:
            # Fetch the installment row
            inst_result = await self.db.execute(
                select(LoanInstallment)
                .where(LoanInstallment.id == ded.loan_installment_id)
                .where(LoanInstallment.tenant_id == tenant_id)
            )
            inst = inst_result.scalar_one_or_none()
            if inst and not inst.is_paid:
                loan_deductions[inst.loan_id].append((ded, inst))

        for loan_id, items in loan_deductions.items():
            # Lock the loan row to prevent concurrent balance mutations
            loan_result = await self.db.execute(
                select(StaffLoan)
                .where(StaffLoan.id == loan_id)
                .where(StaffLoan.tenant_id == tenant_id)
                .with_for_update()
            )
            loan = loan_result.scalar_one_or_none()
            if not loan:
                continue

            total_paid_this_run = ZERO
            installment_ids_covered: list[str] = []

            for ded, inst in items:
                # Mark installment as paid
                inst.is_paid = True
                inst.paid_date = date.today()
                inst.paid_amount = ded.amount
                inst.payroll_run_id = payroll_run_id
                inst.payroll_item_deduction_id = ded.id

                total_paid_this_run += ded.amount
                installment_ids_covered.append(str(inst.id))

            # Create a single loan_payment record for all installments in this run
            payment_number = await self._generate_payment_number(tenant_id)
            payment = LoanPayment(
                tenant_id=tenant_id,
                school_id=loan.school_id,
                loan_id=loan_id,
                payment_number=payment_number,
                amount=total_paid_this_run,
                payment_date=date.today(),
                payment_method="payroll",
                reference=f"Payroll run {payroll_run_id}",
                installments_covered=installment_ids_covered,
                recorded_by=performed_by,
                notes=f"Auto-deducted from payroll run",
            )
            self.db.add(payment)

            # Update loan running totals
            loan.total_paid += total_paid_this_run
            loan.outstanding_balance -= total_paid_this_run
            loan.installments_paid += len(items)
            loan.installments_remaining -= len(items)

            # Prevent negative balance from rounding
            if loan.outstanding_balance < ZERO:
                loan.outstanding_balance = ZERO

            # Auto-complete if fully paid
            if loan.outstanding_balance <= ZERO:
                loan.status = LoanStatus.COMPLETED
                loan.actual_completion_date = date.today()
                completed_loans.append(loan)

                logger.info(
                    "loan_auto_completed",
                    loan_id=str(loan_id),
                    loan_number=loan.loan_number,
                    tenant_id=str(tenant_id),
                )

        await self.db.flush()
        return completed_loans

    # ==================================================================
    # Loan Operations
    # ==================================================================

    async def early_repayment(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        amount: Decimal,
        payment_date: date,
        payment_method: str,
        recorded_by: UUID,
        reference: Optional[str] = None,
        is_full_settlement: bool = False,
        notes: Optional[str] = None,
    ) -> StaffLoan:
        """
        Record an early/lump-sum payment on an active loan.

        For full settlement: marks all remaining installments as paid,
        zeroes out the balance, and completes the loan.

        Uses with_for_update() to prevent concurrent balance mutations.
        """
        # Lock the loan row
        loan_result = await self.db.execute(
            select(StaffLoan)
            .where(StaffLoan.id == loan_id)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.deleted_at.is_(None))
            .with_for_update()
        )
        loan = loan_result.scalar_one_or_none()
        if not loan:
            raise self.Error("Loan not found", 404)
        if loan.status != LoanStatus.ACTIVE:
            raise self.Error("Early repayment is only available for active loans", 409)

        if amount > loan.outstanding_balance:
            raise self.Error(
                f"Payment amount ({amount}) exceeds outstanding balance ({loan.outstanding_balance})",
                400,
            )

        if is_full_settlement:
            amount = loan.outstanding_balance

        # Mark unpaid installments as paid (up to the repayment amount)
        installments_result = await self.db.execute(
            select(LoanInstallment)
            .where(LoanInstallment.loan_id == loan_id)
            .where(LoanInstallment.tenant_id == tenant_id)
            .where(LoanInstallment.is_paid.is_(False))
            .order_by(LoanInstallment.installment_number)
        )
        unpaid_installments = list(installments_result.scalars().all())

        remaining_amount = amount
        installment_ids_covered: list[str] = []
        installments_marked = 0

        for inst in unpaid_installments:
            if remaining_amount <= ZERO:
                break
            if remaining_amount >= inst.installment_amount:
                inst.is_paid = True
                inst.paid_date = payment_date
                inst.paid_amount = inst.installment_amount
                remaining_amount -= inst.installment_amount
                installment_ids_covered.append(str(inst.id))
                installments_marked += 1
            elif is_full_settlement:
                # For full settlement, mark remaining partial installment
                inst.is_paid = True
                inst.paid_date = payment_date
                inst.paid_amount = remaining_amount
                installment_ids_covered.append(str(inst.id))
                remaining_amount = ZERO
                installments_marked += 1

        # If full settlement, mark ALL remaining as paid
        if is_full_settlement:
            for inst in unpaid_installments:
                if not inst.is_paid:
                    inst.is_paid = True
                    inst.paid_date = payment_date
                    inst.paid_amount = ZERO
                    installment_ids_covered.append(str(inst.id))
                    installments_marked += 1

        # Create payment record
        payment_number = await self._generate_payment_number(tenant_id)
        payment = LoanPayment(
            tenant_id=tenant_id,
            school_id=loan.school_id,
            loan_id=loan_id,
            payment_number=payment_number,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference=reference,
            installments_covered=installment_ids_covered,
            is_early_repayment=True,
            recorded_by=recorded_by,
            notes=notes,
        )
        self.db.add(payment)

        # Update loan totals
        loan.total_paid += amount
        loan.outstanding_balance -= amount
        loan.installments_paid += installments_marked
        loan.installments_remaining -= installments_marked

        if loan.outstanding_balance < ZERO:
            loan.outstanding_balance = ZERO

        # Complete the loan if fully paid
        if loan.outstanding_balance <= ZERO or is_full_settlement:
            loan.status = LoanStatus.COMPLETED
            loan.actual_completion_date = date.today()
            loan.outstanding_balance = ZERO

        await self.db.flush()
        await self.db.refresh(loan)

        logger.info(
            "loan_early_repayment",
            loan_id=str(loan_id),
            amount=str(amount),
            is_full_settlement=is_full_settlement,
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, loan.id)

    async def restructure_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        new_interest_rate: Decimal,
        new_interest_method: str,
        new_tenure_months: int,
        new_first_deduction_date: date,
        reason: str,
        performed_by: UUID,
    ) -> StaffLoan:
        """
        Restructure an active loan: mark the old loan as 'restructured'
        and create a new loan with the remaining balance as principal.
        """
        # Lock the old loan
        old_loan_result = await self.db.execute(
            select(StaffLoan)
            .where(StaffLoan.id == loan_id)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.deleted_at.is_(None))
            .with_for_update()
        )
        old_loan = old_loan_result.scalar_one_or_none()
        if not old_loan:
            raise self.Error("Loan not found", 404)
        if old_loan.status != LoanStatus.ACTIVE:
            raise self.Error("Only active loans can be restructured", 409)

        remaining_balance = old_loan.outstanding_balance
        if remaining_balance <= ZERO:
            raise self.Error("No outstanding balance to restructure", 400)

        # Mark old loan as restructured
        old_loan.status = LoanStatus.RESTRUCTURED
        old_loan.notes = (
            f"{old_loan.notes or ''}\n[Restructured] {reason}".strip()
        )

        # Calculate schedule for new loan
        method = InterestMethod(new_interest_method)
        if method == InterestMethod.FLAT:
            calc = calculate_flat_rate_loan(remaining_balance, new_interest_rate, new_tenure_months)
        else:
            calc = calculate_reducing_balance_loan(remaining_balance, new_interest_rate, new_tenure_months)

        # Create new loan with remaining balance
        new_loan_number = await self._generate_loan_number(tenant_id)
        new_loan = StaffLoan(
            tenant_id=tenant_id,
            school_id=old_loan.school_id,
            loan_number=new_loan_number,
            staff_id=old_loan.staff_id,
            loan_type_id=old_loan.loan_type_id,
            status=LoanStatus.ACTIVE,
            principal_amount=remaining_balance,
            interest_rate=new_interest_rate,
            interest_method=method,
            total_interest=calc["total_interest"],
            total_repayable=calc["total_repayable"],
            tenure_months=new_tenure_months,
            monthly_installment=calc["monthly_installment"],
            total_paid=ZERO,
            outstanding_balance=calc["total_repayable"],
            installments_paid=0,
            installments_remaining=new_tenure_months,
            first_deduction_date=new_first_deduction_date,
            disbursement_date=date.today(),
            disbursed_by=performed_by,
            restructured_from_id=old_loan.id,
            created_by=performed_by,
            purpose=f"Restructured from {old_loan.loan_number}: {reason}",
        )
        self.db.add(new_loan)
        await self.db.flush()
        await self.db.refresh(new_loan)

        # Generate installment rows for new loan
        for inst_data in calc["installments"]:
            due_date = new_first_deduction_date + relativedelta(
                months=inst_data["installment_number"] - 1
            )
            installment = LoanInstallment(
                tenant_id=tenant_id,
                school_id=new_loan.school_id,
                loan_id=new_loan.id,
                installment_number=inst_data["installment_number"],
                due_date=due_date,
                principal_component=inst_data["principal_component"],
                interest_component=inst_data["interest_component"],
                installment_amount=inst_data["installment_amount"],
                opening_balance=inst_data["opening_balance"],
                closing_balance=inst_data["closing_balance"],
            )
            self.db.add(installment)

        new_loan.expected_completion_date = new_first_deduction_date + relativedelta(
            months=new_tenure_months - 1
        )

        await self.db.flush()
        await self.db.refresh(new_loan)

        logger.info(
            "loan_restructured",
            old_loan_id=str(loan_id),
            new_loan_id=str(new_loan.id),
            remaining_balance=str(remaining_balance),
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, new_loan.id)

    async def write_off_loan(
        self,
        tenant_id: UUID,
        loan_id: UUID,
        reason: str,
        written_off_by: UUID,
    ) -> StaffLoan:
        """Write off the remaining balance of an active loan."""
        # Lock the loan row
        loan_result = await self.db.execute(
            select(StaffLoan)
            .where(StaffLoan.id == loan_id)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.deleted_at.is_(None))
            .with_for_update()
        )
        loan = loan_result.scalar_one_or_none()
        if not loan:
            raise self.Error("Loan not found", 404)
        if loan.status != LoanStatus.ACTIVE:
            raise self.Error("Only active loans can be written off", 409)

        loan.status = LoanStatus.WRITTEN_OFF
        loan.write_off_reason = reason
        loan.write_off_date = date.today()
        loan.written_off_by = written_off_by
        loan.outstanding_balance = ZERO

        await self.db.flush()
        await self.db.refresh(loan)

        logger.info(
            "loan_written_off",
            loan_id=str(loan_id),
            loan_number=loan.loan_number,
            written_off_by=str(written_off_by),
            tenant_id=str(tenant_id),
        )
        return await self.get_loan(tenant_id, loan.id)

    # ==================================================================
    # Analytics
    # ==================================================================

    async def get_portfolio(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Get loan portfolio summary: totals, breakdowns by type and status,
        and overdue metrics.
        """
        base_filter = and_(
            StaffLoan.tenant_id == tenant_id,
            StaffLoan.deleted_at.is_(None),
        )
        if school_id is not None:
            base_filter = and_(base_filter, StaffLoan.school_id == school_id)

        # Total counts and amounts
        summary_result = await self.db.execute(
            select(
                func.count(StaffLoan.id).label("total"),
                func.count(StaffLoan.id).filter(
                    StaffLoan.status == LoanStatus.ACTIVE
                ).label("active"),
                func.coalesce(
                    func.sum(StaffLoan.principal_amount).filter(
                        StaffLoan.status.in_([
                            LoanStatus.ACTIVE, LoanStatus.COMPLETED,
                            LoanStatus.WRITTEN_OFF, LoanStatus.RESTRUCTURED,
                        ])
                    ),
                    0,
                ).label("total_disbursed"),
                func.coalesce(
                    func.sum(StaffLoan.outstanding_balance).filter(
                        StaffLoan.status == LoanStatus.ACTIVE
                    ),
                    0,
                ).label("total_outstanding"),
                func.coalesce(
                    func.sum(StaffLoan.total_paid),
                    0,
                ).label("total_collected"),
                func.coalesce(
                    func.sum(StaffLoan.principal_amount).filter(
                        StaffLoan.status == LoanStatus.WRITTEN_OFF
                    ),
                    0,
                ).label("total_written_off"),
            )
            .where(base_filter)
        )
        row = summary_result.one()

        total_loans = row.total or 0
        avg_amount = (
            (row.total_disbursed / Decimal(total_loans)).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            if total_loans > 0
            else ZERO
        )

        # By type breakdown
        type_result = await self.db.execute(
            select(
                LoanType.id,
                LoanType.name,
                func.count(StaffLoan.id).label("count"),
                func.coalesce(func.sum(StaffLoan.principal_amount), 0).label("total_principal"),
                func.coalesce(func.sum(StaffLoan.outstanding_balance), 0).label("total_outstanding"),
            )
            .join(StaffLoan, StaffLoan.loan_type_id == LoanType.id)
            .where(base_filter)
            .group_by(LoanType.id, LoanType.name)
            .order_by(LoanType.name)
        )
        by_type = [
            {
                "loan_type_id": r.id,
                "loan_type_name": r.name,
                "count": r.count,
                "total_principal": r.total_principal,
                "total_outstanding": r.total_outstanding,
            }
            for r in type_result.all()
        ]

        # By status breakdown
        status_result = await self.db.execute(
            select(
                StaffLoan.status,
                func.count(StaffLoan.id).label("count"),
            )
            .where(base_filter)
            .group_by(StaffLoan.status)
        )
        by_status = {
            r.status.value if hasattr(r.status, "value") else r.status: r.count
            for r in status_result.all()
        }

        # Overdue metrics: installments past due date and unpaid
        overdue_result = await self.db.execute(
            select(
                func.count(func.distinct(StaffLoan.id)).label("overdue_count"),
                func.coalesce(func.sum(LoanInstallment.installment_amount), 0).label("overdue_amount"),
            )
            .join(StaffLoan, LoanInstallment.loan_id == StaffLoan.id)
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.status == LoanStatus.ACTIVE)
            .where(LoanInstallment.is_paid.is_(False))
            .where(LoanInstallment.due_date < date.today())
        )
        overdue_row = overdue_result.one()

        return {
            "total_loans": total_loans,
            "active_loans": row.active or 0,
            "total_disbursed": row.total_disbursed,
            "total_outstanding": row.total_outstanding,
            "total_collected": row.total_collected,
            "total_written_off": row.total_written_off,
            "average_loan_amount": avg_amount,
            "by_type": by_type,
            "by_status": by_status,
            "overdue_count": overdue_row.overdue_count or 0,
            "overdue_amount": overdue_row.overdue_amount or ZERO,
        }

    async def get_aging_report(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID] = None,
    ) -> dict:
        """
        Generate loan aging report with 30/60/90/120+ day overdue buckets.

        Each bucket contains count, total amount, and loan details.
        """
        today = date.today()

        # Fetch all overdue installments with loan details
        query = (
            select(LoanInstallment)
            .join(StaffLoan, LoanInstallment.loan_id == StaffLoan.id)
            .options(
                selectinload(LoanInstallment.loan).selectinload(StaffLoan.staff),
                selectinload(LoanInstallment.loan).selectinload(StaffLoan.loan_type),
            )
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.status == LoanStatus.ACTIVE)
            .where(LoanInstallment.is_paid.is_(False))
            .where(LoanInstallment.due_date < today)
        )
        if school_id is not None:
            query = query.where(StaffLoan.school_id == school_id)

        result = await self.db.execute(query)
        overdue_installments = list(result.scalars().all())

        # Categorize into buckets
        buckets: dict[str, dict] = {
            "30_days": {"bucket": "30_days", "count": 0, "total_amount": ZERO, "loans": []},
            "60_days": {"bucket": "60_days", "count": 0, "total_amount": ZERO, "loans": []},
            "90_days": {"bucket": "90_days", "count": 0, "total_amount": ZERO, "loans": []},
            "120_plus": {"bucket": "120_plus", "count": 0, "total_amount": ZERO, "loans": []},
        }

        # Group overdue amounts by loan
        loan_overdue: dict[UUID, dict] = {}
        for inst in overdue_installments:
            days_overdue = (today - inst.due_date).days
            loan = inst.loan

            if loan.id not in loan_overdue:
                staff_name = f"{loan.staff.first_name} {loan.staff.last_name}"
                loan_overdue[loan.id] = {
                    "id": loan.id,
                    "loan_number": loan.loan_number,
                    "staff_id": loan.staff_id,
                    "staff_name": staff_name,
                    "loan_type_name": loan.loan_type.name if loan.loan_type else None,
                    "status": loan.status.value,
                    "principal_amount": loan.principal_amount,
                    "total_repayable": loan.total_repayable,
                    "total_paid": loan.total_paid,
                    "outstanding_balance": loan.outstanding_balance,
                    "tenure_months": loan.tenure_months,
                    "installments_paid": loan.installments_paid,
                    "installments_remaining": loan.installments_remaining,
                    "application_date": loan.application_date,
                    "first_deduction_date": loan.first_deduction_date,
                    "max_days_overdue": days_overdue,
                    "overdue_amount": ZERO,
                }

            loan_overdue[loan.id]["overdue_amount"] += inst.installment_amount
            loan_overdue[loan.id]["max_days_overdue"] = max(
                loan_overdue[loan.id]["max_days_overdue"], days_overdue
            )

        # Assign each loan to the appropriate bucket based on max days overdue
        for loan_data in loan_overdue.values():
            days = loan_data["max_days_overdue"]
            if days <= 30:
                bucket_key = "30_days"
            elif days <= 60:
                bucket_key = "60_days"
            elif days <= 90:
                bucket_key = "90_days"
            else:
                bucket_key = "120_plus"

            buckets[bucket_key]["count"] += 1
            buckets[bucket_key]["total_amount"] += loan_data["overdue_amount"]
            buckets[bucket_key]["loans"].append(loan_data)

        total_overdue = sum(b["total_amount"] for b in buckets.values())
        total_overdue_count = sum(b["count"] for b in buckets.values())

        return {
            "total_overdue": total_overdue,
            "total_overdue_count": total_overdue_count,
            "buckets": list(buckets.values()),
        }

    # ==================================================================
    # Staff View
    # ==================================================================

    async def get_staff_loans(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> list[StaffLoan]:
        """Get all loans for a staff member."""
        result = await self.db.execute(
            select(StaffLoan)
            .options(
                selectinload(StaffLoan.loan_type),
                selectinload(StaffLoan.staff),
            )
            .where(StaffLoan.tenant_id == tenant_id)
            .where(StaffLoan.staff_id == staff_id)
            .where(StaffLoan.deleted_at.is_(None))
            .order_by(StaffLoan.created_at.desc())
        )
        return list(result.scalars().all())

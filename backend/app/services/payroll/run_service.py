"""
SIMS Plus - Payroll Run Service

Manages the payroll run lifecycle: create draft, trigger calculation,
submit for approval, approve/reject, mark paid, cancel. Enforces the
state machine (draft -> processing -> calculated -> pending_approval ->
approved -> paid) and separation-of-duties rules.

All queries filter by tenant_id (defense-in-depth on top of RLS).
Uses flush()/refresh() — the endpoint middleware handles commit.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payroll import (
    PayrollApproval,
    PayrollApprovalAction,
    PayrollItem,
    PayrollItemDeduction,
    PayrollItemEarning,
    PayrollRun,
    PayrollRunStatus,
    PayrollRunType,
    StaffSalaryConfig,
)

logger = structlog.get_logger()

# Status transitions allowed for each action
_CALCULABLE_STATUSES = {PayrollRunStatus.DRAFT, PayrollRunStatus.CALCULATED}
_CANCELLABLE_STATUSES = {PayrollRunStatus.DRAFT, PayrollRunStatus.CALCULATED}


class PayrollRunService:
    """Service for managing payroll run lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    # ==================================================================
    # Run CRUD
    # ==================================================================

    async def list_runs(
        self,
        tenant_id: UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
        status: Optional[str] = None,
        school_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PayrollRun]:
        """List payroll runs with optional filters."""
        query = (
            select(PayrollRun)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollRun.tenant_id == tenant_id)
            .where(PayrollRun.deleted_at.is_(None))
            .order_by(PayrollRun.year.desc(), PayrollRun.month.desc(), PayrollRun.run_number.desc())
        )
        if year is not None:
            query = query.where(PayrollRun.year == year)
        if month is not None:
            query = query.where(PayrollRun.month == month)
        if status is not None:
            query = query.where(PayrollRun.status == status)
        if school_id is not None:
            query = query.where(PayrollRun.school_id == school_id)

        query = query.limit(min(limit, 200)).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_run(
        self,
        tenant_id: UUID,
        run_id: UUID,
    ) -> PayrollRun:
        """Get a payroll run by ID."""
        result = await self.db.execute(
            select(PayrollRun)
            .where(PayrollRun.tenant_id == tenant_id)
            .where(PayrollRun.id == run_id)
            .where(PayrollRun.deleted_at.is_(None))
        )
        run = result.scalar_one_or_none()
        if not run:
            raise self.Error("Payroll run not found", 404)
        return run

    async def create_run(
        self,
        tenant_id: UUID,
        month: int,
        year: int,
        run_type: str,
        school_id: Optional[UUID],
        created_by: UUID,
    ) -> PayrollRun:
        """
        Create a new payroll run in draft status.

        Validates that no existing non-cancelled run exists for the same
        month/year/school combination. Auto-increments run_number for
        supplementary runs within the same period.
        """
        if month < 1 or month > 12:
            raise self.Error("Month must be between 1 and 12")
        if year < 2020 or year > 2100:
            raise self.Error("Year must be between 2020 and 2100")

        # Check for existing non-cancelled runs in the same period
        existing_query = (
            select(PayrollRun)
            .where(PayrollRun.tenant_id == tenant_id)
            .where(PayrollRun.month == month)
            .where(PayrollRun.year == year)
            .where(PayrollRun.deleted_at.is_(None))
            .where(PayrollRun.status != PayrollRunStatus.CANCELLED)
        )
        if school_id is not None:
            existing_query = existing_query.where(PayrollRun.school_id == school_id)
        else:
            existing_query = existing_query.where(PayrollRun.school_id.is_(None))

        existing_result = await self.db.execute(existing_query)
        existing_runs = list(existing_result.scalars().all())

        # For regular runs, block duplicate; for supplementary/bonus/arrears, allow
        if run_type == PayrollRunType.REGULAR.value:
            for existing in existing_runs:
                if existing.run_type == PayrollRunType.REGULAR:
                    raise self.Error(
                        f"A regular payroll run already exists for {month}/{year}. "
                        f"Cancel it first or create a supplementary run.",
                        409,
                    )

        # Auto-increment run_number within the same period
        max_run_result = await self.db.execute(
            select(func.coalesce(func.max(PayrollRun.run_number), 0))
            .where(PayrollRun.tenant_id == tenant_id)
            .where(PayrollRun.month == month)
            .where(PayrollRun.year == year)
            .where(PayrollRun.deleted_at.is_(None))
        )
        next_run_number = (max_run_result.scalar() or 0) + 1

        run = PayrollRun(
            tenant_id=tenant_id,
            school_id=school_id,
            month=month,
            year=year,
            run_number=next_run_number,
            status=PayrollRunStatus.DRAFT,
            run_type=run_type,
            processed_by=created_by,
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)

        logger.info(
            "payroll_run_created",
            run_id=str(run.id),
            month=month,
            year=year,
            run_type=run_type,
            run_number=next_run_number,
            tenant_id=str(tenant_id),
        )
        return run

    # ==================================================================
    # State Transitions
    # ==================================================================

    async def trigger_calculation(
        self,
        tenant_id: UUID,
        run_id: UUID,
        user_id: UUID,
    ) -> str:
        """
        Validate run is in a calculable state and dispatch the Celery task.

        Returns the Celery task ID so the frontend can poll for completion.
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status not in _CALCULABLE_STATUSES:
            raise self.Error(
                f"Cannot calculate: run is in '{run.status.value}' status. "
                f"Only draft or calculated runs can be (re-)calculated.",
                409,
            )

        # Import here to avoid circular imports between services and tasks
        from app.tasks.payroll import process_payroll_run

        task = process_payroll_run.delay(str(run_id), str(tenant_id))

        logger.info(
            "payroll_calculation_triggered",
            run_id=str(run_id),
            task_id=task.id,
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )
        return task.id

    async def submit_for_approval(
        self,
        tenant_id: UUID,
        run_id: UUID,
        user_id: UUID,
    ) -> PayrollRun:
        """
        Submit a calculated run for approval.

        Only 'calculated' runs can be submitted. Sets processed_by to the
        submitter so separation-of-duties can be enforced at approval time.
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status != PayrollRunStatus.CALCULATED:
            raise self.Error(
                "Only calculated runs can be submitted for approval", 409
            )

        run.status = PayrollRunStatus.PENDING_APPROVAL
        run.processed_by = user_id
        run.processed_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(run)

        logger.info(
            "payroll_run_submitted",
            run_id=str(run_id),
            submitted_by=str(user_id),
            tenant_id=str(tenant_id),
        )
        return run

    async def approve_run(
        self,
        tenant_id: UUID,
        run_id: UUID,
        approver_id: UUID,
        comments: Optional[str] = None,
    ) -> PayrollRun:
        """
        Approve a payroll run.

        Enforces separation of duties: the approver cannot be the same
        person who submitted the run (AD-10 in spec).
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status != PayrollRunStatus.PENDING_APPROVAL:
            raise self.Error(
                "Only runs pending approval can be approved", 409
            )

        # Separation of duties: approver != submitter
        if run.processed_by == approver_id:
            raise self.Error(
                "Separation of duties violation: the person who submitted "
                "the payroll run cannot also approve it",
                403,
            )

        run.status = PayrollRunStatus.APPROVED
        run.approved_by = approver_id
        run.approved_at = datetime.now(timezone.utc)

        # Record approval action
        approval = PayrollApproval(
            tenant_id=tenant_id,
            payroll_run_id=run_id,
            approver_id=approver_id,
            action=PayrollApprovalAction.APPROVE,
            comments=comments,
        )
        self.db.add(approval)

        await self.db.flush()
        await self.db.refresh(run)

        logger.info(
            "payroll_run_approved",
            run_id=str(run_id),
            approver_id=str(approver_id),
            tenant_id=str(tenant_id),
        )
        return run

    async def reject_run(
        self,
        tenant_id: UUID,
        run_id: UUID,
        approver_id: UUID,
        reason: Optional[str] = None,
    ) -> PayrollRun:
        """
        Reject a payroll run, returning it to draft for revision.

        The submitter can then make corrections and re-calculate/re-submit.
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status != PayrollRunStatus.PENDING_APPROVAL:
            raise self.Error(
                "Only runs pending approval can be rejected", 409
            )

        # Return to draft so the submitter can revise and recalculate
        run.status = PayrollRunStatus.DRAFT

        approval = PayrollApproval(
            tenant_id=tenant_id,
            payroll_run_id=run_id,
            approver_id=approver_id,
            action=PayrollApprovalAction.REJECT,
            comments=reason,
        )
        self.db.add(approval)

        await self.db.flush()
        await self.db.refresh(run)

        logger.info(
            "payroll_run_rejected",
            run_id=str(run_id),
            approver_id=str(approver_id),
            reason=reason,
            tenant_id=str(tenant_id),
        )
        return run

    async def mark_paid(
        self,
        tenant_id: UUID,
        run_id: UUID,
        user_id: UUID,
    ) -> PayrollRun:
        """
        Mark an approved payroll run as paid.

        After this transition, the run and its items are considered
        immutable — no further modifications are allowed (AD-8).

        Also processes loan payments: marks installments as paid, updates
        loan balances, and auto-completes fully paid loans.
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status != PayrollRunStatus.APPROVED:
            raise self.Error(
                "Only approved runs can be marked as paid", 409
            )

        run.status = PayrollRunStatus.PAID
        run.paid_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(run)

        # Process loan payments — mark installments paid and update balances
        from app.services.payroll.loan_service import LoanService

        loan_service = LoanService(self.db)
        completed_loans = await loan_service.process_payroll_payment(
            tenant_id=tenant_id,
            payroll_run_id=run_id,
            performed_by=user_id,
        )

        if completed_loans:
            logger.info(
                "loans_auto_completed_on_payroll_paid",
                run_id=str(run_id),
                completed_count=len(completed_loans),
                loan_numbers=[l.loan_number for l in completed_loans],
                tenant_id=str(tenant_id),
            )

        logger.info(
            "payroll_run_marked_paid",
            run_id=str(run_id),
            marked_by=str(user_id),
            tenant_id=str(tenant_id),
        )
        return run

    async def cancel_run(
        self,
        tenant_id: UUID,
        run_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Cancel a payroll run. Only draft or calculated runs can be cancelled.

        Cancelled runs remain in the database for audit purposes but are
        excluded from duplicate checks.
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status not in _CANCELLABLE_STATUSES:
            raise self.Error(
                f"Cannot cancel: run is in '{run.status.value}' status. "
                f"Only draft or calculated runs can be cancelled.",
                409,
            )

        run.status = PayrollRunStatus.CANCELLED

        await self.db.flush()

        logger.info(
            "payroll_run_cancelled",
            run_id=str(run_id),
            cancelled_by=str(user_id),
            tenant_id=str(tenant_id),
        )

    # ==================================================================
    # Payroll Items
    # ==================================================================

    async def get_run_items(
        self,
        tenant_id: UUID,
        run_id: UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PayrollItem]:
        """Get all payroll items for a run with earnings and deductions loaded."""
        # Verify run exists and belongs to tenant
        await self.get_run(tenant_id, run_id)

        result = await self.db.execute(
            select(PayrollItem)
            .options(
                selectinload(PayrollItem.earnings),
                selectinload(PayrollItem.deductions),
            )
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItem.payroll_run_id == run_id)
            .order_by(PayrollItem.staff_name)
            .limit(min(limit, 500))
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_run_item(
        self,
        tenant_id: UUID,
        run_id: UUID,
        item_id: UUID,
    ) -> PayrollItem:
        """Get a single payroll item with earnings and deductions."""
        # Verify run exists and belongs to tenant (IDOR check)
        await self.get_run(tenant_id, run_id)

        result = await self.db.execute(
            select(PayrollItem)
            .options(
                selectinload(PayrollItem.earnings),
                selectinload(PayrollItem.deductions),
            )
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItem.id == item_id)
            # IDOR check: item must belong to the specified run
            .where(PayrollItem.payroll_run_id == run_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise self.Error("Payroll item not found", 404)
        return item

    async def manual_adjustment(
        self,
        tenant_id: UUID,
        run_id: UUID,
        item_id: UUID,
        adjustments: dict,
        user_id: UUID,
    ) -> PayrollItem:
        """
        Apply manual adjustments to a payroll item.

        Only allowed on 'calculated' runs — not on approved or paid runs.
        Changes are logged to the payroll audit trail.
        """
        run = await self.get_run(tenant_id, run_id)

        if run.status != PayrollRunStatus.CALCULATED:
            raise self.Error(
                "Manual adjustments are only allowed on calculated runs. "
                "Approved and paid runs are immutable.",
                409,
            )

        item = await self.get_run_item(tenant_id, run_id, item_id)

        # Apply allowed adjustments, capturing old values for audit trail
        allowed_fields = {
            "basic_salary", "total_allowances", "gross_salary",
            "paye_tax", "ssnit_employee", "tier3_employee",
            "total_deductions", "net_salary", "notes",
        }

        old_values = {}
        new_values = {}
        for field, value in adjustments.items():
            if field in allowed_fields and hasattr(item, field):
                old_values[field] = str(getattr(item, field))
                setattr(item, field, value)
                new_values[field] = str(value)

        await self.db.flush()
        await self.db.refresh(item)

        logger.info(
            "payroll_item_adjusted",
            run_id=str(run_id),
            item_id=str(item_id),
            adjusted_by=str(user_id),
            fields=list(adjustments.keys()),
            tenant_id=str(tenant_id),
        )
        return item, old_values, new_values

    # ==================================================================
    # Run Summary
    # ==================================================================

    async def get_run_summary(
        self,
        tenant_id: UUID,
        run_id: UUID,
    ) -> dict:
        """Get aggregate summary statistics for a payroll run."""
        run = await self.get_run(tenant_id, run_id)

        # Count items and compute aggregate stats from PayrollItem
        result = await self.db.execute(
            select(
                func.count(PayrollItem.id).label("staff_count"),
                func.coalesce(func.sum(PayrollItem.basic_salary), 0).label("total_basic"),
                func.coalesce(func.sum(PayrollItem.total_allowances), 0).label("total_allowances"),
                func.coalesce(func.sum(PayrollItem.gross_salary), 0).label("total_gross"),
                func.coalesce(func.sum(PayrollItem.paye_tax), 0).label("total_paye"),
                func.coalesce(func.sum(PayrollItem.ssnit_employee), 0).label("total_ssnit_ee"),
                func.coalesce(func.sum(PayrollItem.ssnit_employer), 0).label("total_ssnit_er"),
                func.coalesce(func.sum(PayrollItem.tier2_employer), 0).label("total_tier2_er"),
                func.coalesce(func.sum(PayrollItem.tier3_employee), 0).label("total_tier3"),
                func.coalesce(func.sum(PayrollItem.total_deductions), 0).label("total_deductions"),
                func.coalesce(func.sum(PayrollItem.net_salary), 0).label("total_net"),
            )
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItem.payroll_run_id == run_id)
        )
        row = result.one()

        return {
            "run_id": run.id,
            "month": run.month,
            "year": run.year,
            "run_number": run.run_number,
            "run_type": run.run_type.value if hasattr(run.run_type, "value") else run.run_type,
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "currency": run.currency,
            "staff_count": row.staff_count,
            "total_basic": Decimal(str(row.total_basic)),
            "total_allowances": Decimal(str(row.total_allowances)),
            "total_gross": Decimal(str(row.total_gross)),
            "total_paye": Decimal(str(row.total_paye)),
            "total_ssnit_ee": Decimal(str(row.total_ssnit_ee)),
            "total_ssnit_er": Decimal(str(row.total_ssnit_er)),
            "total_tier2_er": Decimal(str(row.total_tier2_er)),
            "total_tier3": Decimal(str(row.total_tier3)),
            "total_deductions": Decimal(str(row.total_deductions)),
            "total_net": Decimal(str(row.total_net)),
            "total_employer_cost": (
                Decimal(str(row.total_gross))
                + Decimal(str(row.total_ssnit_er))
                + Decimal(str(row.total_tier2_er))
            ),
            "processed_by": run.processed_by,
            "processed_at": run.processed_at,
            "approved_by": run.approved_by,
            "approved_at": run.approved_at,
            "paid_at": run.paid_at,
        }

    # ==================================================================
    # Salary History (delegated to SalaryService, but available here
    # for the combined endpoint router)
    # ==================================================================

    async def get_salary_history(
        self,
        tenant_id: UUID,
        staff_id: UUID,
    ) -> list[StaffSalaryConfig]:
        """Get salary config history for a staff member. Delegates to SalaryService."""
        from app.services.payroll.salary_service import SalaryService

        salary_service = SalaryService(self.db)
        return await salary_service.get_salary_history(tenant_id, staff_id)

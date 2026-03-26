"""
SIMS Plus - Payroll Processing Task

Background Celery task for calculating all payroll items in a run.
Follows the established Celery pattern: synchronous task wrapper that
bridges to async DB operations via run_async().

The task is idempotent: it deletes existing payroll items before
recalculating, so re-running on the same run_id is safe. On failure,
the run status is reverted to 'draft' and the error is logged.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import redis

from app.celery_app import celery_app
from app.config import settings
from app.db.session import async_session_maker
from app.middleware.tenant import set_db_tenant_context
from app.models.payroll import (
    LoanInstallment,
    PayrollAuditLog,
    PayrollItem,
    PayrollItemDeduction,
    PayrollItemEarning,
    PayrollRun,
    PayrollRunStatus,
    StaffAllowance,
    StaffDeduction,
    StaffSalaryConfig,
    TaxBracket,
)
from app.models.staff import Staff
from app.services.payroll.calculation_service import calculate_staff_payroll
from app.services.payroll.loan_service import LoanService
from app.tasks.utils import run_async

logger = structlog.get_logger()


async def _process_payroll_run(run_id: str, tenant_id: str) -> dict:
    """
    Core async logic for payroll calculation.

    Steps:
    1. Lock the payroll_run row with FOR UPDATE (prevents concurrent runs)
    2. Set status to 'processing'
    3. Delete any existing payroll items (idempotent recalculation)
    4. Fetch all active staff with salary configs effective for the period
    5. Fetch tax brackets for the year
    6. For each staff member, calculate payroll and create item records
    7. Update run totals and set status to 'calculated'
    8. Commit atomically

    On failure: revert status to 'draft' and log the error.
    """
    run_uuid = UUID(run_id)
    tenant_uuid = UUID(tenant_id)

    async with async_session_maker() as db:
        async with db.begin():
            # Set RLS context for this tenant
            await set_db_tenant_context(db, tenant_uuid)

            try:
                # Step 1: Lock the run row to prevent concurrent calculations
                run_result = await db.execute(
                    select(PayrollRun)
                    .where(PayrollRun.id == run_uuid)
                    .where(PayrollRun.tenant_id == tenant_uuid)
                    .where(PayrollRun.deleted_at.is_(None))
                    .with_for_update()
                )
                run = run_result.scalar_one_or_none()

                if not run:
                    raise ValueError(f"Payroll run {run_id} not found")

                if run.status not in (
                    PayrollRunStatus.DRAFT,
                    PayrollRunStatus.CALCULATED,
                    PayrollRunStatus.PROCESSING,
                ):
                    raise ValueError(
                        f"Cannot calculate: run is in '{run.status.value}' status"
                    )

                # Step 2: Mark as processing
                run.status = PayrollRunStatus.PROCESSING
                await db.flush()

                # Step 2b: Recalculation guard — block if paid loan installments exist
                # This prevents orphaning balance updates that have already been committed
                paid_loan_check = await db.execute(
                    select(PayrollItemDeduction.id)
                    .join(PayrollItem, PayrollItemDeduction.payroll_item_id == PayrollItem.id)
                    .join(
                        LoanInstallment,
                        PayrollItemDeduction.loan_installment_id == LoanInstallment.id,
                    )
                    .where(PayrollItem.payroll_run_id == run_uuid)
                    .where(LoanInstallment.is_paid.is_(True))
                    .limit(1)
                )
                if paid_loan_check.scalars().first():
                    raise ValueError(
                        "Cannot recalculate: run has paid loan installments. "
                        "Cancel this run and create a new one."
                    )

                # Step 3: Delete existing items for idempotent recalculation.
                # CASCADE will also delete earnings and deductions.
                await db.execute(
                    delete(PayrollItem)
                    .where(PayrollItem.payroll_run_id == run_uuid)
                    .where(PayrollItem.tenant_id == tenant_uuid)
                )

                # Step 4: Determine the last day of the payroll month
                # to find salary configs effective on or before that date
                if run.month == 12:
                    next_month_first = date(run.year + 1, 1, 1)
                else:
                    next_month_first = date(run.year, run.month + 1, 1)
                last_day_of_month = date.fromordinal(next_month_first.toordinal() - 1)

                # Fetch all active staff with their salary configs, allowances,
                # and deductions eagerly loaded
                config_query = (
                    select(StaffSalaryConfig)
                    .options(
                        selectinload(StaffSalaryConfig.allowances).selectinload(
                            StaffAllowance.allowance_type
                        ),
                        selectinload(StaffSalaryConfig.deductions).selectinload(
                            StaffDeduction.deduction_type
                        ),
                        selectinload(StaffSalaryConfig.salary_grade),
                        selectinload(StaffSalaryConfig.staff),
                    )
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    .where(StaffSalaryConfig.tenant_id == tenant_uuid)
                    .where(StaffSalaryConfig.is_active.is_(True))
                    .where(StaffSalaryConfig.deleted_at.is_(None))
                    .where(StaffSalaryConfig.effective_date <= last_day_of_month)
                )

                # Filter by school_id if the run is school-scoped
                if run.school_id is not None:
                    config_query = config_query.where(
                        StaffSalaryConfig.school_id == run.school_id
                    )

                staff_configs_result = await db.execute(config_query)
                salary_configs = list(staff_configs_result.scalars().all())

                # Step 5: Fetch tax brackets for the year
                brackets_result = await db.execute(
                    select(TaxBracket)
                    .where(TaxBracket.tenant_id == tenant_uuid)
                    .where(TaxBracket.effective_year == run.year)
                    .where(TaxBracket.is_active.is_(True))
                    .order_by(TaxBracket.band_number)
                )
                brackets = list(brackets_result.scalars().all())

                tax_brackets = [
                    {
                        "band_number": b.band_number,
                        "lower_limit": b.lower_limit,
                        "upper_limit": b.upper_limit,
                        "rate": b.rate,
                    }
                    for b in brackets
                ]

                if not tax_brackets:
                    raise ValueError(
                        f"No tax brackets found for year {run.year}. "
                        f"Seed tax brackets before calculating payroll."
                    )

                # Step 6 & 7: Calculate payroll for each staff member
                # Aggregate totals for the run
                agg_basic = Decimal("0")
                agg_allowances = Decimal("0")
                agg_gross = Decimal("0")
                agg_paye = Decimal("0")
                agg_ssnit_ee = Decimal("0")
                agg_ssnit_er = Decimal("0")
                agg_tier2_er = Decimal("0")
                agg_tier3 = Decimal("0")
                agg_other_ded = Decimal("0")
                agg_net = Decimal("0")
                agg_employer_cost = Decimal("0")
                staff_count = 0

                for config in salary_configs:
                    staff = config.staff

                    # Skip terminated or deleted staff
                    if staff.deleted_at is not None:
                        continue
                    if getattr(staff, "status", "active") == "terminated":
                        continue

                    # Build allowance data for the calculation engine
                    allowances_data = []
                    for a in config.allowances:
                        at = a.allowance_type
                        if not at or getattr(at, "deleted_at", None) is not None:
                            continue
                        allowances_data.append({
                            "amount": a.amount,
                            "calculation_method": a.calculation_method,
                            "allowance_type_id": a.allowance_type_id,
                            "allowance_type": {
                                "id": at.id,
                                "name": at.name,
                                "code": at.code,
                                "calculation_method": (
                                    at.calculation_method.value
                                    if hasattr(at.calculation_method, "value")
                                    else at.calculation_method
                                ),
                                "is_taxable": at.is_taxable,
                            },
                        })

                    # Build deduction data for the calculation engine
                    # Skip loan-category deductions — they are handled by the loan module
                    deductions_data = []
                    for d in config.deductions:
                        dt = d.deduction_type
                        if not dt or getattr(dt, "deleted_at", None) is not None:
                            continue
                        ded_cat = (
                            dt.deduction_category.value
                            if hasattr(dt.deduction_category, "value")
                            else dt.deduction_category
                        )
                        if ded_cat == "loan":
                            continue  # Loans now handled by loan module
                        deductions_data.append({
                            "amount": d.amount,
                            "calculation_method": d.calculation_method,
                            "deduction_type_id": d.deduction_type_id,
                            "deduction_type": {
                                "id": dt.id,
                                "name": dt.name,
                                "code": dt.code,
                                "calculation_method": (
                                    dt.calculation_method.value
                                    if hasattr(dt.calculation_method, "value")
                                    else dt.calculation_method
                                ),
                                "is_statutory": dt.is_statutory,
                                "is_employer_portion": dt.is_employer_portion,
                                "deduction_category": (
                                    dt.deduction_category.value
                                    if hasattr(dt.deduction_category, "value")
                                    else dt.deduction_category
                                ),
                            },
                        })

                    # Call the pure calculation engine
                    calc = calculate_staff_payroll(
                        basic_salary=config.basic_salary,
                        staff_allowances=allowances_data,
                        staff_deductions=deductions_data,
                        tax_brackets=tax_brackets,
                    )

                    # Build snapshot fields for the payroll item
                    staff_name = f"{staff.first_name} {staff.last_name}"
                    department_name = getattr(staff, "department", None)
                    salary_grade_name = (
                        config.salary_grade.name if config.salary_grade else None
                    )

                    # Create PayrollItem (denormalized snapshot)
                    item = PayrollItem(
                        tenant_id=tenant_uuid,
                        payroll_run_id=run_uuid,
                        staff_id=staff.id,
                        staff_name=staff_name,
                        staff_code=staff.staff_id,
                        department_name=department_name,
                        salary_grade_name=salary_grade_name,
                        basic_salary=calc["basic_salary"],
                        total_allowances=calc["total_allowances"],
                        gross_salary=calc["gross_salary"],
                        taxable_income=calc["taxable_income"],
                        paye_tax=calc["paye_tax"],
                        ssnit_employee=calc["ssnit_employee"],
                        ssnit_employer=calc["ssnit_employer"],
                        tier2_employer=calc["tier2_employer"],
                        tier3_employee=calc["tier3_employee"],
                        total_deductions=calc["total_deductions"],
                        net_salary=calc["net_salary"],
                        # Payment snapshot from salary config
                        payment_method=(
                            config.payment_method.value
                            if config.payment_method
                            and hasattr(config.payment_method, "value")
                            else config.payment_method
                        ),
                        bank_name=config.bank_name,
                        bank_branch=config.bank_branch,
                        account_number=config.account_number,
                        mobile_money_number=config.mobile_money_number,
                        ssnit_number=config.ssnit_number,
                        tin_number=config.tin_number,
                    )
                    db.add(item)
                    await db.flush()
                    await db.refresh(item)

                    # Create earning line items
                    for earning in calc["earnings"]:
                        earning_record = PayrollItemEarning(
                            tenant_id=tenant_uuid,
                            payroll_item_id=item.id,
                            allowance_type_id=earning.get("allowance_type_id"),
                            name=earning["name"],
                            amount=earning["amount"],
                            is_taxable=earning["is_taxable"],
                        )
                        db.add(earning_record)

                    # Create deduction line items
                    for ded in calc["deductions"]:
                        deduction_record = PayrollItemDeduction(
                            tenant_id=tenant_uuid,
                            payroll_item_id=item.id,
                            deduction_type_id=ded.get("deduction_type_id"),
                            name=ded["name"],
                            amount=ded["amount"],
                            is_statutory=ded.get("is_statutory", False),
                            is_employer_portion=ded.get("is_employer_portion", False),
                            deduction_category=ded.get("category"),
                        )
                        db.add(deduction_record)

                    # Loan installment deductions — handled by the loan module
                    # Fetches due installments, applies net salary protection cap,
                    # and creates deduction line items linked to installments
                    loan_service = LoanService(db)
                    due_installments = await loan_service.get_due_installments(
                        tenant_id=tenant_uuid,
                        staff_id=staff.id,
                        year=run.year,
                        month=run.month,
                    )

                    if due_installments:
                        # Net salary protection: cap loan deductions at minimum
                        # max_deduction_pct across all applicable loan types
                        post_statutory_net = (
                            calc["gross_salary"]
                            - calc["paye_tax"]
                            - calc["ssnit_employee"]
                            - calc["tier3_employee"]
                        )

                        min_cap_pct = min(
                            inst.loan.loan_type.max_deduction_pct
                            for inst in due_installments
                        ) / Decimal("100")
                        max_loan_deduction = (post_statutory_net * min_cap_pct).quantize(
                            Decimal("0.01")
                        )
                        total_loan_amount = sum(
                            inst.installment_amount for inst in due_installments
                        )

                        loan_deduction_total = Decimal("0")

                        if total_loan_amount > max_loan_deduction and max_loan_deduction > 0:
                            # Cap and proportionally reduce
                            ratio = max_loan_deduction / total_loan_amount
                            for inst in due_installments:
                                capped = (inst.installment_amount * ratio).quantize(
                                    Decimal("0.01")
                                )
                                loan_ded = PayrollItemDeduction(
                                    tenant_id=tenant_uuid,
                                    payroll_item_id=item.id,
                                    name=(
                                        f"Loan {inst.loan.loan_number} "
                                        f"- #{inst.installment_number}"
                                    ),
                                    amount=capped,
                                    is_statutory=False,
                                    is_employer_portion=False,
                                    deduction_category="loan",
                                    loan_installment_id=inst.id,
                                )
                                db.add(loan_ded)
                                loan_deduction_total += capped

                            logger.info(
                                "loan_deduction_capped",
                                staff_id=str(staff.id),
                                run_id=run_id,
                                original=str(total_loan_amount),
                                capped=str(loan_deduction_total),
                                cap_pct=str(min_cap_pct * 100),
                            )
                        else:
                            for inst in due_installments:
                                loan_ded = PayrollItemDeduction(
                                    tenant_id=tenant_uuid,
                                    payroll_item_id=item.id,
                                    name=(
                                        f"Loan {inst.loan.loan_number} "
                                        f"- #{inst.installment_number}"
                                    ),
                                    amount=inst.installment_amount,
                                    is_statutory=False,
                                    is_employer_portion=False,
                                    deduction_category="loan",
                                    loan_installment_id=inst.id,
                                )
                                db.add(loan_ded)
                                loan_deduction_total += inst.installment_amount

                        # Adjust totals to include loan deductions
                        item.total_deductions += loan_deduction_total
                        item.net_salary -= loan_deduction_total
                        await db.flush()

                    # Accumulate run totals
                    agg_basic += calc["basic_salary"]
                    agg_allowances += calc["total_allowances"]
                    agg_gross += calc["gross_salary"]
                    agg_paye += calc["paye_tax"]
                    agg_ssnit_ee += calc["ssnit_employee"]
                    agg_ssnit_er += calc["ssnit_employer"]
                    agg_tier2_er += calc["tier2_employer"]
                    agg_tier3 += calc["tier3_employee"]
                    agg_other_ded += calc["total_other_deductions"]
                    agg_net += calc["net_salary"]
                    agg_employer_cost += calc["employer_cost"]
                    staff_count += 1

                # Step 8: Update run totals
                run.total_basic = agg_basic
                run.total_allowances = agg_allowances
                run.total_gross = agg_gross
                run.total_paye = agg_paye
                run.total_ssnit_ee = agg_ssnit_ee
                run.total_ssnit_er = agg_ssnit_er
                run.total_tier2_er = agg_tier2_er
                run.total_tier3 = agg_tier3
                run.total_other_deductions = agg_other_ded
                run.total_net = agg_net
                run.total_employer_cost = agg_employer_cost
                run.staff_count = staff_count

                # Step 9: Mark as calculated
                run.status = PayrollRunStatus.CALCULATED
                await db.flush()

                logger.info(
                    "payroll_run_calculated",
                    run_id=run_id,
                    staff_count=staff_count,
                    total_net=str(agg_net),
                    total_employer_cost=str(agg_employer_cost),
                    tenant_id=tenant_id,
                )

                return {
                    "run_id": run_id,
                    "staff_count": staff_count,
                    "total_net": str(agg_net),
                    "status": "calculated",
                }

            except Exception:
                logger.exception(
                    "payroll_run_calculation_failed",
                    run_id=run_id,
                    tenant_id=tenant_id,
                )
                # Revert to draft on failure so the user can retry
                # This needs a separate session since the current one
                # is being rolled back by the context manager
                raise


async def _revert_run_to_draft(run_id: str, tenant_id: str, error_msg: str) -> None:
    """Revert a payroll run back to draft after a calculation failure."""
    run_uuid = UUID(run_id)
    tenant_uuid = UUID(tenant_id)

    async with async_session_maker() as db:
        async with db.begin():
            await set_db_tenant_context(db, tenant_uuid)

            result = await db.execute(
                select(PayrollRun)
                .where(PayrollRun.id == run_uuid)
                .where(PayrollRun.tenant_id == tenant_uuid)
                .with_for_update()
            )
            run = result.scalar_one_or_none()
            if run and run.status == PayrollRunStatus.PROCESSING:
                run.status = PayrollRunStatus.DRAFT

            # Log the failure to the audit trail (only if we have a valid user)
            performed_by = run.processed_by if (run and run.processed_by) else None
            if performed_by:
                audit_entry = PayrollAuditLog(
                    tenant_id=tenant_uuid,
                    school_id=run.school_id if run else None,
                    entity_type="payroll_run",
                    entity_id=run_uuid,
                    action="calculation_failed",
                    new_value=error_msg[:500] if error_msg else None,
                    performed_by=performed_by,
                )
                db.add(audit_entry)


@celery_app.task(
    name="process_payroll_run",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def process_payroll_run(self, run_id: str, tenant_id: str) -> dict:
    """
    Celery task: calculate all payroll items for a run.

    Synchronous wrapper that bridges to the async calculation logic.
    On failure, reverts the run status to 'draft' and logs the error
    to the payroll audit trail.
    """
    try:
        return run_async(_process_payroll_run(run_id, tenant_id))
    except Exception as exc:
        logger.exception(
            "process_payroll_run_task_failed",
            run_id=run_id,
            tenant_id=tenant_id,
        )
        # Revert run status so the user can retry
        try:
            run_async(_revert_run_to_draft(run_id, tenant_id, str(exc)))
        except Exception:
            logger.exception(
                "payroll_run_revert_failed",
                run_id=run_id,
                tenant_id=tenant_id,
            )
        raise


# ======================================================================
# Bulk Payslip Generation (Phase 4C)
# ======================================================================

# Process payslips in chunks to manage memory
_PAYSLIP_CHUNK_SIZE = 50


async def _generate_bulk_payslips(run_id: str, tenant_id: str) -> dict:
    """
    Core async logic for bulk payslip generation.

    Processes all staff in a payroll run in chunks of 50 to manage memory.
    Tracks progress via Redis key: payroll:payslips:{run_id}:progress
    """
    run_uuid = UUID(run_id)
    tenant_uuid = UUID(tenant_id)
    # Tenant-prefixed key to prevent cross-tenant key collisions in shared Redis
    progress_key = f"tenant:{tenant_id}:payroll:payslips:{run_id}:progress"

    # Set up Redis for progress tracking (graceful degradation if unavailable)
    redis_client = None
    try:
        redis_client = redis.Redis.from_url(
            str(settings.REDIS_URL), decode_responses=True
        )
        redis_client.ping()
    except Exception:
        logger.warning(
            "bulk_payslips_redis_unavailable",
            run_id=run_id,
            detail="Progress tracking will not be available",
        )
        redis_client = None

    async with async_session_maker() as db:
        async with db.begin():
            # Set RLS context for this tenant
            await set_db_tenant_context(db, tenant_uuid)

            # Fetch all payroll items for this run
            items_result = await db.execute(
                select(PayrollItem)
                .where(PayrollItem.tenant_id == tenant_uuid)
                .where(PayrollItem.payroll_run_id == run_uuid)
                .order_by(PayrollItem.staff_name)
            )
            all_items = list(items_result.scalars().all())
            total_count = len(all_items)

            if total_count == 0:
                raise ValueError(
                    f"No payroll items found for run {run_id}"
                )

            # Initialize progress
            if redis_client:
                try:
                    redis_client.hset(progress_key, mapping={
                        "total": str(total_count),
                        "completed": "0",
                        "failed": "0",
                        "status": "processing",
                    })
                    # Auto-expire progress key after 24 hours
                    redis_client.expire(progress_key, 86400)
                except Exception:
                    pass

            # Import payslip service here to avoid circular imports
            from app.services.payroll.payslip_service import PayslipService

            completed = 0
            failed = 0

            # Process in chunks to manage memory
            for chunk_start in range(0, total_count, _PAYSLIP_CHUNK_SIZE):
                chunk = all_items[chunk_start:chunk_start + _PAYSLIP_CHUNK_SIZE]

                for item in chunk:
                    try:
                        # Create a fresh payslip service instance for each item
                        # to avoid stale session state
                        payslip_service = PayslipService(db)
                        await payslip_service.generate_payslip_pdf(
                            tenant_id=tenant_uuid,
                            run_id=run_uuid,
                            staff_id=item.staff_id,
                        )
                        completed += 1
                    except Exception:
                        logger.exception(
                            "bulk_payslip_item_failed",
                            run_id=run_id,
                            staff_id=str(item.staff_id),
                            staff_name=item.staff_name,
                        )
                        failed += 1

                    # Update progress in Redis
                    if redis_client:
                        try:
                            redis_client.hset(progress_key, mapping={
                                "completed": str(completed),
                                "failed": str(failed),
                            })
                        except Exception:
                            pass

            # Mark as complete
            if redis_client:
                try:
                    redis_client.hset(progress_key, "status", "complete")
                except Exception:
                    pass

            logger.info(
                "bulk_payslips_complete",
                run_id=run_id,
                total=total_count,
                completed=completed,
                failed=failed,
                tenant_id=tenant_id,
            )

            return {
                "run_id": run_id,
                "total": total_count,
                "completed": completed,
                "failed": failed,
                "status": "complete",
            }


@celery_app.task(
    name="generate_bulk_payslips",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def generate_bulk_payslips(self, run_id: str, tenant_id: str) -> dict:
    """
    Celery task: generate PDF payslips for all staff in a payroll run.

    Processes in chunks of 50 to manage memory. Each payslip is uploaded
    to S3 individually. Progress tracked via Redis key:
    payroll:payslips:{run_id}:progress
    """
    try:
        return run_async(_generate_bulk_payslips(run_id, tenant_id))
    except Exception:
        logger.exception(
            "generate_bulk_payslips_failed",
            run_id=run_id,
            tenant_id=tenant_id,
        )
        raise

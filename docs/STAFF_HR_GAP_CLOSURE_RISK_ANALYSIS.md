# Risk Analysis: Staff & HR Management Gap Closure

**Analyst:** Risk Analyst Agent (Claude Opus 4.6)
**Date:** 2026-03-25
**Spec Version:** 00-overview.md through 05-phase-5-loan-management.md
**Status:** READ-ONLY Analysis

---

## Executive Summary

The Staff & HR Gap Closure is the largest single spec in the SIMS Plus project history: 24 new tables, 101 endpoints, 194 tests, 35 frontend pages, and 3 Celery tasks across 5 phases. The spec estimate of 11-12 weeks for 2 developers is **significantly underestimated**. My revised estimate is **17-21 weeks** (2 developers), with the primary underestimation drivers being: (1) frontend effort invisible in the spec (35 pages with zero time allocated), (2) Phase 4 payroll calculation engine complexity, (3) bidirectional payroll-loan integration testing, and (4) Ghana statutory compliance verification overhead.

The spec is well-structured and demonstrates solid architectural decisions (AD-7 through AD-12 in particular). However, it contains **4 guaranteed bugs**, **2 critical design gaps**, and **3 high-risk areas** that must be addressed before or during implementation.

**Overall Risk Level: HIGH** -- primarily due to financial calculation sensitivity (payroll + loans), regulatory compliance requirements (PAYE/SSNIT), and the bidirectional payroll-loan integration creating a complex state machine.

---

## Component Complexity

| Component | Complexity | Spec Estimate | Revised Estimate | Notes |
|-----------|------------|---------------|------------------|-------|
| Phase 1: Staff Records + Docs + History | 2 | 3-4 days | 4-5 days | Straightforward; patterns exist from StudentDocument |
| Phase 2: Staff Attendance Frontend | 2 | 2-3 days | 3-4 days | Frontend-only, but Recharts reports + mobile responsive adds time |
| Phase 3A: Teaching Workload | 2 | 1-2 days | 2 days | Read-only aggregation; clean design |
| Phase 3B: Leave Management | 3 | 4-5 days | 6-8 days | 3 tables, approval workflow, holiday calculation, Celery task, 7 frontend pages |
| Phase 4A: Payroll Foundation | 5 | 2 weeks | 2.5-3 weeks | 14 models, migration, seed data, config CRUD, 22 endpoints, 6+ settings pages |
| Phase 4B: Payroll Processing | 8 | 2 weeks | 3-3.5 weeks | PAYE/SSNIT engine, Celery task, run lifecycle, approval flow, 14 endpoints, run pages |
| Phase 4C: Payslip + Bank Files + Reports | 5 | 1.5 weeks | 2-2.5 weeks | WeasyPrint PDF, 5 bank formats, 4 report types, Excel export, 4+ report pages |
| Phase 4D: Polish + Security | 3 | 0.5 weeks | 1 week | Audit log UI, security review, E2E test, perf test |
| Phase 5A: Loan Foundation | 3 | 3-4 days | 4-5 days | 5 tables, 2 enums, calc engine, loan type CRUD |
| Phase 5B: Loan Lifecycle | 5 | 4-5 days | 6-7 days | 8-state machine, guarantors, eligibility, approval, 5+ pages |
| Phase 5C: Payroll Integration | 8 | 3-4 days | 5-7 days | Bidirectional integration, net salary protection, race conditions, 3+ pages |
| Phase 5D: Reports + PDF | 3 | 2-3 days | 3-4 days | Statement PDF, portfolio dashboard, aging report, RLS tests |

**Total Estimated Effort:** 85-105 developer-days (revised) vs 55-60 developer-days (spec)
**Confidence Level:** Medium -- payroll complexity is hard to estimate without prior financial module experience in this codebase
**Recommended Buffer:** 25% -- regulatory compliance and rounding edge cases historically require extra iteration
**Realistic Total:** 106-131 developer-days
**Calendar Time (2 devs):** 17-21 weeks (vs spec's 11-12 weeks)

### Underestimation Breakdown

| Category | Spec Gap | Dev-Days Added |
|----------|----------|----------------|
| Frontend (35 pages, zero estimates) | ~40% of backend effort | +22-28 days |
| Testing overhead (194 tests at 30-40% of effort) | Implicitly assumed in task estimates | +5-8 days |
| Ghana statutory verification (PAYE bracket validation, SSNIT rate confirmation) | Not mentioned | +2-3 days |
| Integration testing (payroll + loans bidirectional) | Underscoped | +3-5 days |
| Edge cases in financial calculations | Underscoped | +3-5 days |

---

## Risk Register

| ID | Risk | Category | Severity | Probability | Impact | Mitigation Status | Recommendation |
|----|------|----------|----------|-------------|--------|-------------------|----------------|
| R-001 | **PaymentMethod enum collision**: Spec defines new `paymentmethod` enum (bank_transfer, cash, mobile_money) but `PaymentMethod` enum already exists in `models/finance/payment_models.py` with DB type `paymentmethod`. PostgreSQL will reject `CREATE TYPE paymentmethod` since it already exists. | Technical | Critical | **Certain** | Build failure at migration | **Unmitigated** | Must use a different DB type name (e.g., `payrollpaymentmethod`) or reuse existing enum with added values. The existing enum has `cash`, `bank_transfer` but also `momo_mtn`, `momo_vodafone`, `card`, `cheque`, `other` -- different granularity than what payroll needs. Recommend: create `payrollpaymentmethod` as a separate type. |
| R-002 | **PAYE brackets are 2024 rates, not 2026**: The spec seeds "2024 GRA rates" (Band 1: GHS 490 @ 0%). GRA publishes new rates annually in January. By the time this ships (mid-2026), the 2025 and possibly 2026 rates will be in effect. Seeding stale rates means first payroll will be wrong. | Compliance | High | **High** | Incorrect tax calculations for all staff; GRA audit liability | **Partially Mitigated** (AD-7: rates in DB, not hardcoded) | The DB-stored approach (AD-7) is correct and allows updates. But: (1) seed data MUST be updated to 2026 rates before Phase 4 ships, (2) add a `/payroll/tax-brackets/import` endpoint that accepts GRA's published PDF/CSV format, (3) add a dashboard warning when brackets' `effective_year` does not match current year. |
| R-003 | **SSNIT rates may change**: Spec hardcodes 5.5% employee, 13% employer, 5% Tier 2 in `calculate_ssnit()`. These are NOT in the DB -- they're in Python code. If SSNIT rates change, it requires a code deployment. | Compliance | High | **Medium** | Wrong SSNIT deductions for all staff | **Unmitigated** | Move SSNIT rates to a `statutory_rates` table or use the existing `deduction_types` table with `is_statutory=true`. The spec already has SSNIT deduction types in `deduction_types` but the calculation engine ignores them and uses hardcoded rates. This is an inconsistency. |
| R-004 | **Taxable income formula may be wrong for non-standard allowances**: The spec computes `taxable_income = basic + taxable_allowances - ssnit_employee`. GRA's actual formula is: `Taxable Income = Total Cash Emoluments - Employee Pension (SSNIT + Tier 3)`. If an employee has Tier 3 voluntary contributions, these should also be deducted from taxable income. The spec's Step 5 deducts SSNIT employee but does NOT deduct Tier 3 from taxable income -- Tier 3 is only deducted from net. | Compliance | High | **High** | Overpayment of PAYE for staff with Tier 3 | **Unmitigated** | Fix the calculation: `taxable_income = basic + taxable_allowances - ssnit_employee - tier3_employee`. The spec's Step 5 comment says "ssnit_employee (tax-deductible)" but GRA treats ALL pension contributions as tax-deductible, including Tier 3. |
| R-005 | **Rounding error accumulation in batch payroll**: Rounding each intermediate step to 2dp (correct per spec) across 300 staff could accumulate small discrepancies between individual totals and run totals. Example: if each staff's PAYE rounds up by 0.005, 300 staff = GHS 1.50 discrepancy between sum(individual PAYE) and recalculated total. | Financial | Medium | **Medium** | Small financial discrepancies in statutory returns | **Partially Mitigated** (round each step to 2dp) | Add a reconciliation check after calculation: `abs(sum(items.paye) - run.total_paye) <= Decimal("0.01") * staff_count`. If exceeded, log warning to audit. This is standard payroll practice. |
| R-006 | **Celery task failure leaves payroll in `processing` state**: If `process_payroll_run` fails after setting `status='processing'` but before the catch block runs, the run is stuck. The spec says "On failure: set status = 'draft'" but if the process crashes (OOM, worker killed), the catch block never executes. | Technical | High | **Medium** | Stuck payroll run requiring manual DB intervention | **Partially Mitigated** (max_retries=1) | Add a stale-processing detector: Celery beat task that checks for runs in `processing` state older than 10 minutes and resets to `draft`. Also add a manual "Reset to Draft" endpoint for admins. |
| R-007 | **Payroll recalculation is NOT truly idempotent**: The spec claims idempotency via "delete existing items before recalculating." But if a run is in `calculated` state and someone triggers recalculation, the previous items (which staff may have reviewed) are silently destroyed. The spec does NOT distinguish between first calculation and recalculation. | Technical | Medium | **Medium** | Loss of reviewed data without audit trail | **Unmitigated** | Only allow recalculation from `draft` or `calculated` states. Log the recalculation event to `payroll_audit_log` with the old totals before deletion. Consider adding a `calculation_count` field on `payroll_runs` to track iterations. |
| R-008 | **Concurrent payroll run creation for same month**: No unique constraint prevents creating two `regular` runs for the same month simultaneously. The spec has `UNIQUE(tenant_id, school_id, year, month, run_number, deleted_at)` but `run_number` defaults to 1 for regular runs -- if two users click "Create Run" for March 2026 at the same time, one will succeed and one will get a constraint violation (which is correct) but the error message will be confusing. | Technical | Low | **Medium** | Confusing error on duplicate run creation | **Partially Mitigated** (unique constraint catches it) | Add an explicit check before creation: "A payroll run for this month already exists" with a friendly error message. Use `SELECT ... FOR UPDATE` on the check to prevent TOCTOU. |
| R-009 | **Loan installment capping loses money silently**: When net salary protection caps loan deductions at 50%, the difference is described as "carries forward to next month." But the spec does NOT implement this carry-forward. The installment remains `is_paid=false` for the full amount, and next month it shows up again as due. This means the staff member pays partial this month plus full amount next month -- they're paying MORE than the installment amount in aggregate. | Financial | High | **High** | Staff overpayment or underpayment depending on implementation | **Unmitigated** | Two approaches: (1) Mark installment as partially paid with `paid_amount < installment_amount`, add `remaining_amount` column, and carry forward only the remainder. (2) Record the capped amount as a partial payment, and the installment remains due for the difference. Either way, the spec needs explicit carry-forward logic. |
| R-010 | **Concurrent early repayment + payroll processing**: Spec acknowledges this risk and proposes `with_for_update()` on `staff_loans`. But the payroll calculation runs in a Celery task with its own DB session, while early repayment runs via an HTTP endpoint. `FOR UPDATE` only works within a single transaction -- the Celery task's transaction and the HTTP request's transaction are separate. | Technical | High | **Medium** | Double-deduction or incorrect balance | **Partially Mitigated** | Use `pg_advisory_xact_lock(hashtext('loan:' || loan_id::text))` in BOTH the payroll task and the early repayment endpoint. This provides cross-session locking that `FOR UPDATE` alone cannot. The project already uses `pg_advisory_xact_lock` for ID generation (see memory). |
| R-011 | **Bank file format rejection by banks**: Banks in Ghana are notoriously strict about file formats -- wrong encoding, wrong date format, extra whitespace, or missing header can cause entire file rejection. The spec provides example formats but these are approximations, not verified against actual bank specifications. | Operational | High | **Medium** | Failed salary disbursement; delayed staff payments | **Unmitigated** | Before Phase 4C, obtain actual file format specifications from GCB, Ecobank, Stanbic, Fidelity, and CalBank. Test with sample files against each bank's validation tool. Consider: most Ghana banks now support GHIPSS ACH format as a standard alternative. Add GHIPSS ACH as a default format. |
| R-012 | **Staff termination with active loan**: Spec mentions this risk but says "Loans remain active; admin notified." There's no implementation for the notification. If a staff member is terminated via `StaffService.update_staff()`, there's no hook to check for active loans and alert the admin. | Operational | Medium | **Medium** | Outstanding loan balance not recovered; school loses money | **Unmitigated** | Add a check in `StaffService.update_staff()`: when `status` changes to `terminated`, query `staff_loans` for active loans. If any exist, (1) log audit event, (2) create notification for school_admin/hr_officer, (3) optionally block termination until loan disposition is decided (configurable). |
| R-013 | **Leave balance race condition**: Spec mentions `with_for_update()` on balance row but the implementation in Task 3.9 (leave request service) does not show the actual locking query. If two leave requests are submitted simultaneously for the same staff+leave_type, the balance check (`remaining >= days_requested`) could pass for both, resulting in overallocation. | Technical | Medium | **Medium** | Leave balance goes negative | **Partially Mitigated** | Ensure the service does: `balance = await db.execute(select(LeaveBalance).where(...).with_for_update())` BEFORE the remaining check. Also add a DB CHECK constraint: `used_days + pending_days <= entitled_days + carried_over`. |
| R-014 | **Leave day calculation across academic year boundaries**: If a leave request spans the end of one academic year and the start of another (e.g., Dec 28 to Jan 5), the spec does not clarify which year's balance is debited. The migration seeds balances per `academic_year_id`, so a cross-year request would need to split across two balance records. | Technical | Medium | **Low** | Incorrect leave balance deduction | **Unmitigated** | For MVP, reject leave requests that span academic year boundaries with a clear error message. Add cross-year support in a future iteration. |
| R-015 | **Model import path inconsistency**: Spec references `from app.db.base_class import Base` and `from app.models.mixins import TenantMixin, SoftDeleteMixin` in the leave models (Task 3.6). Actual project uses `from app.models.base import Base, TenantMixin, SoftDeleteMixin` (single import). | Technical | Low | **Certain** | ImportError at runtime | **Unmitigated** | Fix import paths in implementation. This is pattern #16 from memory (spec import path errors). |
| R-016 | **TENANT_SCOPED_TABLES count is wrong in spec**: Spec says 125 -> 149. Actual current count (from conftest.py): the list ends at `promotion_rules` (line 168), which is item ~125 (matching). However, the spec assumes exactly 125, and the actual count may differ if other in-progress features have added tables. | Quality | Low | **Medium** | Test failures if count doesn't match | **Partially Mitigated** | Verify exact count before each phase's implementation. Count from conftest.py at implementation time. |
| R-017 | **No `enforce_subscription_feature` dependency exists**: The spec references gating endpoints with feature flags but uses the name `enforce_subscription_feature`. The actual dependency is called `require_feature` (confirmed in `deps.py:664`). | Technical | Low | **Certain** | Incorrect dependency import | **Unmitigated** | Use `require_feature("hr_payroll")` and `require_feature("hr_leave")` following the `custom_roles.py` pattern. |
| R-018 | **Bulk payslip generation memory pressure**: Generating 300 WeasyPrint PDFs in a Celery worker. WeasyPrint is known to consume 50-100MB per PDF render for complex templates. 50 concurrent renders (spec's chunk size) = 2.5-5GB RAM. The Celery worker config `worker_max_tasks_per_child=200` won't help because this is ONE task generating 300 PDFs. | Infrastructure | High | **Medium** | Celery worker OOM kill; all payslips lost | **Partially Mitigated** (chunking at 50) | Reduce chunk size to 10-20. After each chunk, call `gc.collect()` and `weasyprint.HTML(...).write_pdf()` in a subprocess or use `del` aggressively. Monitor worker memory. Consider generating payslips on-demand rather than pre-generating all. |
| R-019 | **No rollback strategy for seed migration (20260430_0200)**: The seed migration inserts tax brackets and statutory deductions for all existing tenants. If the migration needs to be rolled back, the downgrade must DELETE these rows -- but there's no tracking of which rows were seeded vs. which were manually added by admins. | Quality | Medium | **Low** | Irreversible migration; manual data cleanup required | **Unmitigated** | Add a `is_system_seeded` boolean column to `tax_brackets` and `deduction_types`. Seed migration sets this to `true`. Downgrade deletes only `WHERE is_system_seeded = true`. |
| R-020 | **Percentage-of-gross circular reference in allowances**: The spec uses a two-pass approach where `percentage_gross` allowances use `basic + pass1_total` as a proxy. But if multiple `percentage_gross` allowances exist, their calculation order is undefined and they don't include each other. This is mathematically correct (avoids infinite recursion) but may surprise users who expect "10% of gross" to include other percentage-of-gross allowances. | Financial | Low | **Low** | User confusion about allowance calculation | **Partially Mitigated** (two-pass documented) | Document the calculation method clearly in the UI. Add a tooltip: "Percentage of gross is calculated on basic salary plus fixed and percentage-of-basic allowances." |
| R-021 | **Self-approval check is insufficient for payroll**: Spec says `processed_by != approver_id`. But what if the same person creates the run AND approves it? The `processed_by` field is set when calculation is triggered, but the run is created by a different user who clicked "Create Run." Need to check BOTH `created_by` and `processed_by` against `approver_id`. | Financial | Medium | **Medium** | Single person can create + approve payroll (audit risk) | **Unmitigated** | Add a `created_by` field to `payroll_runs`. Check `approver_id NOT IN (created_by, processed_by)`. |
| R-022 | **Loan restructure creates orphan installment schedules**: When restructuring, the spec says "marks old as restructured" and creates a new loan. But existing unpaid installments on the old loan remain in the DB with `is_paid=false`. The payroll integration queries for `is_paid=false` installments on `active` loans -- the old loan is `restructured` so they won't be picked up. But the `outstanding_balance` on the old loan is non-zero. This is technically correct but creates confusing portfolio analytics. | Financial | Low | **Medium** | Portfolio reports show inflated outstanding balances | **Unmitigated** | On restructure: set old loan's `outstanding_balance = 0`, `total_repayable = total_paid` (writedown the difference). Mark remaining installments as `is_paid=true` with `notes='Absorbed by restructure LN-XXXX-YYYY'`. |
| R-023 | **300-staff payroll performance**: The spec claims background processing handles this, which is correct. But the calculation does N queries per staff: (1) salary config, (2) allowances, (3) deductions, (4) tax brackets, (5) due loan installments. For 300 staff, that's 1500 queries minimum. | Infrastructure | Medium | **Medium** | Payroll calculation takes >5 minutes | **Partially Mitigated** (Celery background) | Batch-load: fetch ALL salary configs, ALL staff allowances, ALL staff deductions, and ALL due installments in 4 queries. Build in-memory dicts keyed by staff_id. The spec's `get_all_due_installments_for_run` method (Phase 5) does this for loans -- extend the pattern to all payroll data. |
| R-024 | **Feature flag gating inconsistency**: `hr_leave` is in PLAN_FEATURES as a boolean (Professional: true, Starter: false). But `hr_payroll` is NOT in PLAN_FEATURES -- it's only in ADDON_PRICES and AVAILABLE_ADDONS. The `require_feature` dependency checks PLAN_FEATURES. If `hr_payroll` is not in PLAN_FEATURES for Enterprise, the feature check will fail. | Technical | High | **Certain** | Payroll endpoints return 403 even for Enterprise tenants | **Unmitigated** | Add `hr_payroll` to Enterprise PLAN_FEATURES as `True`. Currently it's only referenced in ADDON_PRICES/AVAILABLE_ADDONS. Verify the `require_feature` dependency handles both plan-included features AND purchased add-ons. |
| R-025 | **No mid-month staff changes handling**: If a staff member joins mid-month (e.g., employment_date = March 15), the payroll calculation uses full monthly basic salary. No proration logic exists. Similarly, termination mid-month pays full salary. | Financial | Medium | **Medium** | Overpayment for partial-month employees | **Unmitigated** | For MVP, accept this as a known limitation and document it. Payroll admins can use a supplementary run with manual adjustments. Add proration logic in v2: `prorated_basic = basic * working_days_in_month / total_days_in_month`. |

---

## Multi-Tenancy Risk Assessment

### New Tables Requiring RLS Policies: 24

All 24 new tables have RLS policies defined in their migration scripts. The spec correctly follows the existing pattern (`get_current_tenant_id()`). Verified:
- `staff_documents`, `staff_employment_history` (Phase 1)
- `leave_types`, `leave_balances`, `leave_requests` (Phase 3)
- All 14 payroll tables (Phase 4) -- including `payroll_audit_log` with INSERT+SELECT only
- All 5 loan tables (Phase 5)

### Cross-Tenant Data Access Vectors

1. **Payroll audit log read restriction**: The spec correctly limits `payroll_audit_log` to INSERT+SELECT (no UPDATE/DELETE) for `sims_app_user`. This matches the `platform_audit_log` pattern. No cross-tenant risk.

2. **Bank file downloads via presigned S3 URL**: Presigned URLs are generated per-request with tenant-scoped paths (`tenants/{tenant_id}/payroll/...`). No cross-tenant bleed as long as the S3 key includes tenant_id (it does).

3. **Tax bracket seed migration**: The CROSS JOIN seed inserts brackets for ALL active/trial tenants. This is correct -- each row has its own `tenant_id`. No risk here.

4. **Loan guarantor cross-tenant check**: A guarantor must be a staff member in the same tenant. RLS on both `staff` and `loan_guarantors` tables ensures this. No additional check needed at the application layer (RLS handles it).

### Cache/Session Tenant Bleed Risks

1. **Payslip progress tracking via Redis**: Spec uses `payroll:payslips:{run_id}:progress` as Redis key. The `run_id` is a UUID, which is globally unique -- no tenant prefix needed. **No risk.**

2. **No salary data cached**: Salary configs, tax brackets, and payroll items are always read from DB. **No risk.**

### Background Job Tenant Context

1. **`process_payroll_run` task**: Must set tenant context before any DB queries. The spec describes "set tenant context" in Step 1. Must follow the existing pattern in `tasks/utils.py` (`run_for_all_tenants` calls `set_tenant_context`). **Risk: if tenant context is not set, RLS returns empty results, payroll calculates zero for everyone.** Add assertion: `if staff_count == 0: raise ValueError("No staff found -- check tenant context")`.

2. **`generate_bulk_payslips` task**: Same tenant context requirement. Must set before querying payroll items.

3. **`update_staff_leave_status` daily task**: This is a cross-tenant task that should use `run_for_all_tenants` to iterate all tenants and set context per-tenant. Spec does not explicitly describe this pattern. **Must follow existing pattern.**

---

## Dependencies

### Internal Dependencies

| Component | Depends On | Status |
|-----------|------------|--------|
| Phase 1 (Staff Records) | Existing staff model, StudentDocument pattern | Ready |
| Phase 2 (Attendance Frontend) | Existing staff attendance backend endpoints | Ready |
| Phase 3A (Workload) | Existing timetable models, StaffClassAssignment | Ready |
| Phase 3B (Leave Management) | Phase 1 migration chain | Sequential |
| Phase 4A (Payroll Foundation) | Phase 3 migration chain | Sequential |
| Phase 4B (Payroll Processing) | Phase 4A (models + config) | Sequential |
| Phase 4B calculation engine | Tax brackets seeded (20260430_0200) | Sequential |
| Phase 4C (Payslips/Reports) | Phase 4B (calculated runs exist) | Sequential |
| Phase 5A (Loan Foundation) | Phase 4A (payroll tables exist) | Sequential |
| Phase 5B (Loan Lifecycle) | Phase 5A | Sequential |
| Phase 5C (Payroll Integration) | Phase 4B + Phase 5B | **Critical join point** |
| Phase 5D (Reports) | Phase 5C | Sequential |
| Feature flag gating | `require_feature` in deps.py | Ready (but `hr_payroll` not in PLAN_FEATURES -- R-024) |
| Celery infrastructure | celery_app.py + docker-compose worker | Ready (bootstrapped in enrollment gap closure) |

### External Dependencies

| Dependency | Owner | Risk Level | Lead Time | Notes |
|------------|-------|------------|-----------|-------|
| GRA 2026 PAYE tax brackets | Ghana Revenue Authority | High | Unknown | Must obtain before Phase 4 ships. GRA typically publishes in January. If 2026 rates are not yet published, ship with 2025 rates and update on first payroll run. |
| SSNIT contribution rates 2026 | SSNIT | Medium | Unknown | Currently 5.5%/13%/5% -- may not change but must verify. |
| Bank file format specifications | GCB, Ecobank, Stanbic, Fidelity, CalBank | High | 2-4 weeks | Banks are slow to provide technical specs. Start requesting NOW. |
| WeasyPrint A5 landscape rendering | Open source library | Low | None | Tested in project for A4 reports; A5 landscape is straightforward. |
| Celery beat schedule additions | DevOps | Low | None | Add `update_staff_leave_status` to beat config; celery_app.py is already configured. |

---

## Recommended Approach

### Parallel Tracks

- **Track A (Dev 1):** Phase 1 (3-4d) -> Phase 3A Workload (2d) -> Phase 4A Foundation (2.5w) -> Phase 4B Processing (3w)
- **Track B (Dev 2):** Phase 2 Attendance Frontend (3-4d) -> Phase 3B Leave (6-8d) -> Phase 4A Frontend (1.5w) -> Phase 4C Output (2w)

**Note:** Phase 4 cannot be meaningfully parallelized until 4A is complete. Both devs should work on 4A together for the first week (one on models/migration/backend, one on schemas/config frontend).

### Phase 5 Dependency Bottleneck

Phase 5C (payroll-loan integration) depends on BOTH Phase 4B (payroll processing) AND Phase 5B (loan lifecycle). These are the two longest chains. If either slips, Phase 5C is blocked.

**Recommended:** Start Phase 5A (loan foundation) as soon as Phase 4A migration is complete, overlapping with Phase 4B. Dev 2 can work on Phase 5A-5B while Dev 1 finishes Phase 4B-4C.

### Sequential Dependencies (Critical Path)

1. Phase 4A migration (must be first -- all payroll tables)
2. Phase 4A config service + endpoints (allows frontend to start)
3. Phase 4B calculation engine + Celery task
4. Phase 5A loan tables + calculation engine (can overlap with 4B)
5. Phase 5C payroll-loan integration (blocked on both 4B and 5B)
6. Phase 4C payslips + bank files (needs calculated runs from 4B)
7. Phase 5D loan reports + statements

---

## Critical Path

```
Week 1-2:  Phase 1 + Phase 2 (parallel)
Week 2-3:  Phase 3A + Phase 3B
Week 3-6:  Phase 4A (both devs, 2.5-3 weeks)
Week 6-9:  Phase 4B (Dev 1) + Phase 5A-5B (Dev 2) (parallel)
Week 9-11: Phase 4C (Dev 1) + Phase 5C (Dev 2)
Week 11-12: Phase 4D + Phase 5D (parallel)
Week 12-13: Integration testing + security review + buffer
```

**Minimum Timeline:** 13 weeks (assuming 2 developers, no blockers, perfect parallelization)
**Realistic Timeline:** 17-21 weeks (with buffer, bank spec delays, PAYE rate research, integration bugs)

---

## Guaranteed Bugs in Spec

### Bug 1: PaymentMethod Enum Collision (R-001)

**Location:** Phase 4 migration (`20260430_0100`)
**Issue:** `CREATE TYPE paymentmethod AS ENUM (...)` will fail because `paymentmethod` already exists (created in finance module for Payment model).
**Fix:** Use `payrollpaymentmethod` as the DB type name, or use VARCHAR(20) with application-level validation (simpler).

### Bug 2: Tier 3 Not Deducted from Taxable Income (R-004)

**Location:** Phase 4 calculation engine, Step 5
**Issue:** `taxable_income = basic + taxable_allowances - ssnit_employee` omits Tier 3 voluntary pension. GRA rules: ALL pension contributions are tax-deductible.
**Fix:** `taxable_income = basic + taxable_allowances - ssnit_employee - tier3_employee`

### Bug 3: Model Import Paths Wrong (R-015)

**Location:** Phase 3, Task 3.6 leave models
**Issue:** `from app.db.base_class import Base` and `from app.models.mixins import TenantMixin` -- actual paths are `from app.models.base import Base, TenantMixin, SoftDeleteMixin`.
**Fix:** Use correct import path.

### Bug 4: Feature Flag Not in PLAN_FEATURES (R-024)

**Location:** Phase 4 feature gating
**Issue:** `hr_payroll` exists in `ADDON_PRICES` and `AVAILABLE_ADDONS` for Enterprise but is NOT in `PLAN_FEATURES[Enterprise]`. The `require_feature` dependency checks plan features and won't find it.
**Fix:** Add `"hr_payroll": True` to `PLAN_FEATURES[SubscriptionTier.ENTERPRISE]` (or "addon" for Professional if desired). Also ensure `require_feature` checks purchased add-ons in tenant's `features` JSONB.

---

## Testing Completeness Assessment

### 194 Tests: Sufficient or Not?

For a financial module handling real money (payroll, loans), 194 tests is on the **low side** but acceptable for MVP. The spec covers the right categories. However, there are critical gaps:

### Missing Test Scenarios

| Category | Missing Test | Risk |
|----------|-------------|------|
| **PAYE edge cases** | Staff earning exactly at bracket boundaries (e.g., GHS 490.00, GHS 600.00) | Boundary bugs cause wrong tax for many staff |
| **PAYE edge cases** | Staff with zero basic but non-zero allowances (e.g., contract workers paid only allowances) | Division by zero or wrong taxable income |
| **SSNIT** | Staff older than 60 (exempt from SSNIT in Ghana) | Over-deduction for retired staff |
| **Payroll** | Mid-run staff termination (terminated between calculate and approve) | Ghost payroll item for terminated staff |
| **Payroll** | Payroll run with zero active salary configs (all staff without configs) | Empty run should still be valid |
| **Payroll** | Supplementary run with negative adjustments (salary correction) | Net salary could go negative |
| **Loan** | Loan with 1-month tenure (edge case: single installment = total) | Rounding error on single installment |
| **Loan** | Early repayment exceeding outstanding balance | Overpayment handling unclear |
| **Loan** | Two loans for same staff, both due same month, hitting 50% cap | Proportional capping across multiple loans |
| **Loan** | Restructure of a loan that has partial payments via payroll capping | Balance calculation with mixed partial/full payments |
| **Integration** | Full E2E: create loan -> process 3 monthly payrolls -> verify loan balance decremented correctly | Most critical happy-path test |
| **Bank file** | File with special characters in staff names (e.g., "Nana Ama O'Brien-Mensah") | File parsing errors at bank |
| **Leave** | Leave request for exactly 0.5 days (half-day) | NUMERIC(5,1) precision handling |
| **Leave** | Concurrent leave requests for same dates from same staff | Double-booking prevention |

**Recommendation:** Add at least 15-20 additional tests covering the scenarios above. Total should be ~210-215 for adequate coverage of a financial module.

---

## Open Questions Impact Assessment

| # | Question | Risk if Unresolved Before Development | Recommendation |
|---|----------|---------------------------------------|----------------|
| 6 | Self-service payslips via teacher portal? | **Low** -- can be added later as a route extension. No schema impact. | Defer to post-Phase 4. |
| 7 | Multi-level payroll approval? | **Low** -- `payroll_approvals` table already supports multiple rows. Single-level is fine for MVP. | Defer. Schema is forward-compatible. |
| 9 | 13th month salary / bonus rules? | **Medium** -- `run_type=bonus` exists but no calculation logic. If a school tries to process a bonus run, the system will use the regular calculation, which may be wrong. | Either: (1) disable bonus run type in MVP, or (2) document that bonus runs use the same calculation as regular runs (admin enters manual adjustments). |
| 10 | Multi-currency payroll? | **Low** -- `currency` column defaults to GHS. No harm in leaving it. Cross-currency PAYE calculation is a much larger problem. | Defer. All statutory calculations assume GHS. |
| 11 | External payroll system integrations? | **Low** -- CSV/Excel export covers initial needs. | Defer. |

---

## Infrastructure Requirements

| Requirement | Purpose | Lead Time | Cost Impact |
|-------------|---------|-----------|-------------|
| Celery worker memory increase | Bulk payslip generation (WeasyPrint) needs 2-4GB RAM per worker | 1 day (EKS pod limit change) | +$20-40/month per worker |
| Redis key TTL for payslip progress | Progress tracking for bulk generation | None (already provisioned) | Negligible |
| S3 storage growth | Payslips (~100KB each) * 300 staff * 12 months = ~360MB/school/year; Bank files negligible | None | ~$0.01/school/year |
| Celery beat schedule additions | `update_staff_leave_status` daily task | 10 minutes | None |
| Bank format specification documents | GCB, Ecobank, Stanbic, Fidelity, CalBank CSV/ACH specs | 2-4 weeks (external) | None (but delays Phase 4C if not obtained) |

---

## Recommendations

### 1. Start Early (Before Sprint Begins)

- **Obtain GRA 2025/2026 PAYE tax brackets** -- this is a hard blocker for Phase 4 calculation testing.
- **Request bank file format specs from 5 banks** -- 2-4 week lead time; delays Phase 4C if not ready.
- **Fix R-024 (hr_payroll feature flag)** -- 5-minute fix in `subscription.py` that prevents days of debugging.
- **Fix R-001 (PaymentMethod enum)** -- decide on naming before writing the migration.

### 2. Technical Spikes (Investigate Before Committing)

- **Spike 1: PAYE calculation verification** (2 hours) -- find GRA's official worked examples and verify the spec's calculation matches. Ghana's GRA website occasionally publishes sample PAYE computations.
- **Spike 2: WeasyPrint A5 landscape** (1 hour) -- render a sample payslip template to verify layout, especially the two-column earnings/deductions format.
- **Spike 3: Celery + payroll memory profiling** (2 hours) -- run a simulated 300-staff calculation in a Celery task, monitor memory and time. Verify the 50-chunk payslip generation stays within worker memory limits.

### 3. Risk Mitigation Actions (During Development)

- **Implement reconciliation checks** after payroll calculation: `sum(items.field) == run.total_field` for all financial columns.
- **Add `pg_advisory_xact_lock`** for all loan balance mutations (R-010).
- **Move SSNIT rates to DB** alongside tax brackets (R-003).
- **Fix Tier 3 taxable income deduction** (R-004 / Bug 2).
- **Add stale-processing detector** for stuck payroll runs (R-006).
- **Implement loan installment carry-forward logic** for net salary capping (R-009).

### 4. Phased Delivery Recommendation

Given the 17-21 week timeline, consider delivering in two releases:

- **Release A (Weeks 1-8):** Phases 1-3 + Phase 4A-4B = Staff records, attendance UI, leave management, payroll configuration and calculation. Schools can configure and calculate payroll.
- **Release B (Weeks 8-14):** Phase 4C-4D + Phase 5 = Payslips, bank files, reports, loans. Full payroll output and loan management.

This de-risks delivery by providing value early (payroll calculation) while buying time for the more complex output and loan integration work.

---

## Comparison to Historical Estimation Accuracy

Based on previous analyses (from agent memory):

| Analysis | Spec Estimate | Revised Estimate | Actual Underestimation |
|----------|---------------|------------------|----------------------|
| Enrollment Gap Closure | 40 dev-days | 80 dev-days | ~100% (frontend unmeasured) |
| Preschool Gap Closure | 18.5 dev-days | 26.5 dev-days | ~43% |
| Multi-Curriculum Gap Closure | 40.5 dev-days | 54 dev-days | ~33% |
| Tenant School Setup | 11-14 dev-days | 16-21 dev-days | ~45% |
| **Staff HR Gap Closure** | **55-60 dev-days** | **85-105 dev-days** | **~55-75%** |

The underestimation pattern is consistent with previous analyses. The primary driver (as with Enrollment Gap Closure) is **unestimated frontend effort** combined with **financial module testing overhead**.

# Staff & HR Management Gap Closure — Implementation Plan

**Author:** SIMS Plus Engineering
**Date:** 2026-03-25
**Status:** Approved for Implementation
**Estimated Effort:** 5 Phases (~11-12 weeks, 2 developers)
**Branch:** `feat/staff-hr-gap-closure`

---

## Table of Contents

| Document | Covers |
|----------|--------|
| [00-overview.md](00-overview.md) | This file — gap matrix, architecture decisions, migration chain, permissions |
| [01-phase-1-staff-records-documents-history.md](01-phase-1-staff-records-documents-history.md) | Staff field gaps, document management, employment history |
| [02-phase-2-staff-attendance-frontend.md](02-phase-2-staff-attendance-frontend.md) | Staff attendance marking UI, reports UI |
| [03-phase-3-workload-leave-management.md](03-phase-3-workload-leave-management.md) | Teaching workload tracking, leave types/balances/requests/calendar |
| [04-phase-4-payroll.md](04-phase-4-payroll.md) | Salary structures, payroll processing, PAYE/SSNIT, payslips, bank files, reports |
| [05-phase-5-loan-management.md](05-phase-5-loan-management.md) | Staff loans, interest calculation, installment schedules, payroll integration, portfolio analytics |

---

## 1. Executive Summary

The existing staff module provides solid foundations — staff CRUD, departments, class assignments, staff attendance (backend), CSV import/export, and an HR Officer role. This gap closure addresses **17 identified gaps** across staff records, document management, employment history, attendance frontend, leave management, teaching workload, and payroll.

### What Already Exists

| Area | Status | Tables | Endpoints |
|------|--------|--------|-----------|
| Staff CRUD (profiles, photos, import/export) | Complete | 1 | 12 |
| Department management | Complete | 1 | 6 |
| Staff class assignments (class teacher, subjects) | Complete | 1 | 5 |
| Staff attendance (backend: mark, bulk, summary, reports) | Complete | 1 | 7 |
| Teacher portal (dashboard, grading, lessons, comments) | Complete | 2 | ~20 |
| HR Officer role + permissions | Complete | 0 | 0 |

### What This Plan Adds

| Phase | New Tables | New Columns | New Endpoints | Frontend Pages | Tests | Celery Tasks | Duration |
|-------|-----------|-------------|---------------|----------------|-------|-------------|----------|
| Phase 1: Records + Docs + History | 2 | 5 on `staff` | 6 | 2 tabs | ~25 | 0 | 3-4 days |
| Phase 2: Attendance Frontend | 0 | 0 | 0 | 3 pages | ~8 | 0 | 2-3 days |
| Phase 3: Workload + Leave | 3 | 0 | 19 | 8 pages | ~35 | 1 | 5-7 days |
| Phase 4: Payroll | 14 | 0 | 48 | 15 pages | ~55 | 2 | 6 weeks |
| Phase 5: Loan Management | 5 | 1 (FK) | 28 | 7 pages | ~71 | 0 | 2-2.5 weeks |
| **Total** | **24** | **5 + 1 FK** | **101** | **~35** | **~194** | **3** | **~11-12 weeks** |

**TENANT_SCOPED_TABLES:** 125 → **149** (+24)

---

## 2. Requirement-to-Implementation Matrix

### 11.1 Staff Records

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|------------|----------|--------|-------|----------------|
| STF-001 | Name, contact, qualifications, employment date | Must | **DONE** | — | `staff` table has all fields |
| STF-002 | Ghana Card, SSNIT, TIN numbers | Should | **PARTIAL** | 1 | Ghana Card + SSNIT exist; add `tin_number VARCHAR(50)` |
| STF-003 | Staff categories: teaching, non-teaching, admin | Must | **DONE** | — | `StaffType` enum |
| STF-004 | Staff documents (certificates, contracts) | Should | **GAP** | 1 | New `staff_documents` table with S3 presigned URLs |
| HR-003 | Employment type (Full-time, Part-time, Contract) | Must | **GAP** | 1 | New `employment_type` enum + column on `staff` |
| HR-004 | Department and designation assignment | Must | **DONE** | — | `department_id` FK + `job_title` on staff |
| HR-007 | Employment history within organisation | Should | **GAP** | 1 | New `staff_employment_history` event log table |
| HR-009 | GES staff ID tracking for public schools | Should | **GAP** | 1 | New `ges_staff_id VARCHAR(50)` column on `staff` |

### 11.2 Staff Assignment

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|------------|----------|--------|-------|----------------|
| STF-010 | Teachers assignable to classes and subjects | Must | **DONE** | — | `staff_class_assignments` table |
| STF-011 | Class teacher designation | Must | **DONE** | — | `is_class_teacher` boolean, one per section |
| STF-012 | Department/unit assignment | Should | **DONE** | — | `department_id` FK on staff |
| STF-013 | Track teaching workload | Should | **GAP** | 3 | Calculated from timetable + assignments (read-only) |
| HR-006 | Teaching subjects and class assignments tracking | Must | **DONE** | — | `subject_id` FK on `staff_class_assignments` |

### 11.3 Staff Attendance and Leave

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|------------|----------|--------|-------|----------------|
| HR-010 | Daily staff attendance marking | Must | **PARTIAL** | 2 | Backend exists; build frontend UI |
| HR-011 | Leave type configuration | Must | **GAP** | 3 | New `leave_types` table with configurable categories |
| HR-012 | Leave balance tracking | Must | **GAP** | 3 | New `leave_balances` table per staff/year |
| HR-013 | Leave application and approval workflow | Must | **GAP** | 3 | New `leave_requests` table with status machine |
| HR-014 | Leave calendar view | Should | **GAP** | 3 | Frontend calendar page reading from `leave_requests` |
| HR-015 | Attendance reports and statistics | Must | **PARTIAL** | 2 | Backend exists; build frontend reports UI |

### 11.4 Payroll

| ID | Requirement | Priority | Status | Phase | Implementation |
|----|------------|----------|--------|-------|----------------|
| HR-020 | Salary structure configuration | Could | **GAP** | 4 | `salary_grades` + `staff_salary_configs` tables |
| HR-021 | Allowances and deductions setup | Could | **GAP** | 4 | `allowance_types` + `deduction_types` tables |
| HR-022 | Monthly payroll processing | Could | **GAP** | 4 | `payroll_runs` + `payroll_items` with Celery calculation |
| HR-023 | Payslip generation | Could | **GAP** | 4 | WeasyPrint A5 PDF template stored in S3 |
| HR-024 | SSNIT and tax calculation (PAYE) | Could | **GAP** | 4 | `tax_brackets` table seeded with GRA 2024 rates |
| HR-025 | Bank file generation | Could | **GAP** | 4 | `bank_file_configs` with presets for 5 Ghana banks |
| HR-026 | Integration with existing payroll systems | Could | **GAP** | 4 | CSV/Excel export of payroll runs + statutory reports |

---

## 3. Architecture Decisions

### AD-1: Staff Documents via S3 Presigned URLs
**Decision:** Reuse the `StudentDocument` pattern — S3 storage with presigned download URLs, magic byte validation, 10MB limit.
**Rationale:** Consistent with existing document infrastructure; no public read; tenant-scoped S3 paths.
**S3 Key Pattern:** `tenants/{tenant_id}/staff/{staff_id}/documents/{uuid}-{sanitized_filename}`

### AD-2: Employment History as Event Log
**Decision:** Explicit `staff_employment_history` table with event types, not JSONB on staff.
**Rationale:** Queryable across all staff, auditable, supports reporting ("show all promotions this year").

### AD-3: Auto-Record History on Staff Update
**Decision:** Service-layer trigger in `StaffService.update_staff()` — when `job_title`, `department_id`, or `status` changes, automatically insert a history record.
**Rationale:** Keeps business logic in Python; easier to test; consistent with existing patterns.

### AD-4: Workload Derived from Timetable
**Decision:** Calculate teaching workload as a read-only aggregation from `staff_class_assignments` + `class_timetables`. No separate workload table.
**Rationale:** Timetable is the source of truth for periods; no data duplication.

### AD-5: Leave Day Calculation Server-Side
**Decision:** Server calculates `days_requested` excluding weekends and school holidays.
**Rationale:** Authoritative calculation prevents disputes; holidays vary per school.

### AD-6: Half-Day Leave Support
**Decision:** `days_requested` uses `NUMERIC(5,1)` to support 0.5-day increments.
**Rationale:** Common practice in Ghanaian schools; needed for half-day permissions.

### AD-7: Tax Brackets in DB, Not Hardcoded
**Decision:** PAYE brackets stored as tenant-scoped rows in `tax_brackets` table, seeded with current GRA rates.
**Rationale:** GRA changes rates periodically (last changed January 2024); schools update without code deployment.

### AD-8: Payroll Run as Immutable Snapshot
**Decision:** Once a payroll run is approved, its line items are frozen. Corrections require a supplementary run.
**Rationale:** Standard payroll practice; critical for audit trails and legal compliance.

### AD-9: Payroll Processing via Celery
**Decision:** Payroll calculation dispatched as a Celery background task.
**Rationale:** 200+ staff calculations with PAYE bracket walks, SSNIT computation, and DB writes would exceed HTTP request timeout.

### AD-10: Separation of Duties for Payroll Approval
**Decision:** The user who processes payroll cannot approve their own run (`processed_by != approver_id`).
**Rationale:** Financial control best practice; reduces fraud risk.

### AD-11: Separate Payroll Audit Log
**Decision:** Dedicated `payroll_audit_log` table (not reusing `finance_audit_log`).
**Rationale:** Different retention requirements (Ghana labor law: 6 years), different access control, append-only (no UPDATE/DELETE grants).

### AD-12: Configurable Bank File Formats
**Decision:** `bank_file_configs` table with JSONB `column_mapping` and presets for GCB, Ecobank, Stanbic, Fidelity, CalBank.
**Rationale:** Ghana has no single mandated format; each bank accepts different CSV/fixed-width layouts; new banks added without code changes.

### AD-13: Leave Management Feature-Gated
**Decision:** Leave endpoints gated by `hr_leave` feature flag (Professional+ tier).
**Rationale:** Starter/Trial schools don't need leave management; matches existing subscription model.

### AD-14: Payroll Feature-Gated
**Decision:** All payroll endpoints gated by `hr_payroll` feature flag (Enterprise add-on, GHS 500/term).
**Rationale:** Payroll is complex, sensitive, and requires support; only Enterprise schools opt in.
**Implementation Note:** `hr_payroll` must be added to `PLAN_FEATURES` in `backend/app/constants/subscription.py`: `False` for Starter/Professional, `"addon"` for Enterprise. The `require_feature()` dependency from `app.api.deps` is used (NOT `enforce_subscription_feature` which does not exist). Similarly, `hr_leave` must already be in `PLAN_FEATURES` — verify and add if missing.

---

## 4. Migration Chain

The migration chain extends from the current head (`20260425_0400_promotion_rules_graduation`):

```
20260425_0400 (promotion_rules_graduation)
    └── 20260426_0100 (staff_hr_fields)               — Phase 1: New columns on staff
        └── 20260426_0200 (staff_documents)            — Phase 1: staff_documents table
            └── 20260426_0300 (employment_history)     — Phase 1: staff_employment_history table
                └── 20260426_0400 (leave_management)   — Phase 3: leave_types, leave_balances, leave_requests + seed
                    └── 20260430_0100 (payroll_foundation) — Phase 4A: All 14 payroll tables + 6 enums
                        └── 20260430_0200 (seed_ghana_statutory) — Phase 4A: Seed tax brackets + statutory deductions
                            └── 20260501_0100 (staff_loans) — Phase 5: 5 loan tables + 2 enums + FK on payroll_item_deductions
```

**Note:** Phase 2 (staff attendance frontend) requires NO migrations — backend already exists.

---

## 5. Permissions Model

### New Permissions

| Permission Key | Label | Description | Module |
|---------------|-------|-------------|--------|
| `hr.leave.read` | View leave data | View leave types, balances, and requests | HR & Leave |
| `hr.leave.request` | Request leave | Submit and cancel own leave requests | HR & Leave |
| `hr.leave.approve` | Approve leave | Approve or reject leave requests | HR & Leave |
| `hr.leave.manage` | Manage leave settings | Configure leave types, adjust balances | HR & Leave |
| `payroll.read` | View payroll data | View salary configs, payroll runs, payslips | Payroll |
| `payroll.configure` | Configure payroll | Manage salary grades, allowance/deduction types, tax brackets | Payroll |
| `payroll.manage` | Manage salaries | Assign salary configs to staff | Payroll |
| `payroll.process` | Process payroll | Create and calculate payroll runs | Payroll |
| `payroll.approve` | Approve payroll | Approve/reject payroll runs (must differ from processor) | Payroll |
| `payroll.audit` | View payroll audit | View payroll audit log | Payroll |
| `payroll.loans.read` | View loan data | View loans, installments, portfolio | Loans |
| `payroll.loans.request` | Request loans | Create/submit loan applications | Loans |
| `payroll.loans.approve` | Approve loans | Approve/reject loan applications | Loans |
| `payroll.loans.disburse` | Disburse loans | Confirm loan disbursement | Loans |
| `payroll.loans.manage` | Manage loans | Early repayment, restructure | Loans |
| `payroll.loans.write_off` | Write off loans | Write off outstanding balance | Loans |

### Role Assignments

| Role | Leave Permissions | Payroll Permissions | Loan Permissions |
|------|-------------------|---------------------|-------------------|
| `school_admin` | read, request, approve, manage | read, configure, manage, process, approve, audit | all 6 loan permissions |
| `chain_admin` | read, request, approve, manage | read, configure, manage, process, approve, audit | all 6 loan permissions |
| `hr_officer` | read, request, approve, manage | read, configure, manage, process, audit | read, request, approve, manage |
| `academic_head` | read, request | — | — |
| `teacher` | read (own only), request (own leave only) | — | — |
| `finance_officer` | — | read, audit | read, disburse, manage |

**Note:** Custom roles can be assigned any combination via the existing `custom_roles` system.

**IMPORTANT Implementation Requirement:** All 16 permission keys must be explicitly added to:
1. `ROLE_PERMISSIONS` dict in `backend/app/services/auth.py` for each role listed above
2. `PERMISSIONS_CATALOG` in `backend/app/constants/permissions.py` under new "HR & Leave", "Payroll", and "Loans" modules
3. `PLAN_FEATURES` in `backend/app/constants/subscription.py` — add `hr_leave` (Professional+) and `hr_payroll` (Enterprise add-on)

Without these updates, all `require_permissions()` and `require_feature()` checks will fail at runtime.

---

## 6. TENANT_SCOPED_TABLES Updates

### Phase 1 (+2 = 127)
```python
"staff_documents",
"staff_employment_history",
```

### Phase 3 (+3 = 130)
```python
"leave_types",
"leave_balances",
"leave_requests",
```

### Phase 4 (+14 = 144)
```python
"salary_grades",
"allowance_types",
"deduction_types",
"tax_brackets",
"staff_salary_configs",
"staff_allowances",
"staff_deductions",
"payroll_runs",
"payroll_items",
"payroll_item_earnings",
"payroll_item_deductions",
"payroll_approvals",
"bank_file_configs",
"payroll_audit_log",
```

### Phase 5 (+5 = 149)
```python
"loan_types",
"staff_loans",
"loan_installments",
"loan_guarantors",
"loan_payments",
```

Update both `backend/tests/conftest.py` and `backend/scripts/verify_rls.py` at each phase.

**RLS Policy Naming Convention:** All policies MUST follow the project standard `tenant_isolation_{table_name}` (NOT just `tenant_isolation`). The `TO sims_app_user` clause MUST be included. Use `rls_helpers.py` functions (`enable_rls_for_table()`) where possible. Example:
```sql
CREATE POLICY tenant_isolation_staff_documents ON staff_documents
    FOR ALL
    TO sims_app_user
    USING (tenant_id = get_current_tenant_id())
    WITH CHECK (tenant_id = get_current_tenant_id());
```

---

## 7. Enum Reference

### Phase 1 Enums

| Enum Name | DB Type | Values |
|-----------|---------|--------|
| `EmploymentType` | `employmenttype` | `full_time`, `part_time`, `contract`, `temporary`, `intern` |
| `StaffDocumentType` | `staffdocumenttype` | `contract`, `certificate`, `cv_resume`, `id_document`, `reference_letter`, `disciplinary`, `training`, `medical`, `other` |
| `EmploymentEventType` | `employmenteventtype` | `hired`, `promoted`, `demoted`, `transferred`, `title_changed`, `department_changed`, `status_changed`, `salary_changed`, `contract_renewed` |

### Phase 3 Enums

| Enum Name | DB Type | Values |
|-----------|---------|--------|
| `LeaveRequestStatus` | `leaverequeststatus` | `pending`, `approved`, `rejected`, `cancelled` |

### Phase 4 Enums

| Enum Name | DB Type | Values |
|-----------|---------|--------|
| `PayrollRunStatus` | `payrollrunstatus` | `draft`, `processing`, `calculated`, `pending_approval`, `approved`, `paid`, `cancelled` |
| `PayrollRunType` | `payrollruntype` | `regular`, `supplementary`, `bonus`, `arrears` |
| `CalculationMethod` | `calculationmethod` | `fixed`, `percentage_basic`, `percentage_gross` |
| `PayrollPaymentMethod` | `payrollpaymentmethod` | `bank_transfer`, `cash`, `mobile_money` |

> **WARNING:** Must use `payrollpaymentmethod` (NOT `paymentmethod`) — `paymentmethod` already exists in `backend/app/models/finance/payment_models.py`. Using the same name causes a `CREATE TYPE` collision.
| `DeductionCategory` | `deductioncategory` | `statutory`, `voluntary`, `loan`, `union`, `other` |
| `PayrollApprovalAction` | `payrollapprovalaction` | `approve`, `reject`, `return_for_review` |

### Phase 5 Enums

| Enum Name | DB Type | Values |
|-----------|---------|--------|
| `LoanStatus` | `loanstatus` | `draft`, `pending_approval`, `approved`, `active`, `completed`, `written_off`, `restructured`, `rejected` |
| `InterestMethod` | `interestmethod` | `flat`, `reducing_balance` |

All enums follow the project pattern: `class EnumName(str, Enum)` with `values_callable=lambda x: [e.value for e in x]` in SQLAlchemy column definitions.

**Soft-Delete Unique Constraint Pattern:** Tables with `(code, tenant_id, deleted_at)` unique constraints must use **partial unique indexes** instead, because PostgreSQL treats NULL != NULL (so `deleted_at IS NULL` rows are not deduplicated by a standard unique constraint). The correct pattern is:
```sql
CREATE UNIQUE INDEX uq_salary_grade_code ON salary_grades(tenant_id, code) WHERE deleted_at IS NULL;
```
This applies to: `salary_grades`, `allowance_types`, `deduction_types`, `bank_file_configs`, `loan_types`, and `leave_types`.

---

## 8. Endpoint Dependency Injection Pattern

**IMPORTANT:** All endpoint signatures in this spec use simplified pseudo-code for clarity. The actual implementation MUST follow the project's established DI pattern from `backend/app/api/deps.py`:

```python
# CORRECT pattern (actual codebase):
@router.post(
    "/types",
    response_model=LeaveTypeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("hr.leave.manage"))],
)
async def create_leave_type(
    data: LeaveTypeCreate,
    db: DatabaseSession,           # Annotated alias, NOT Depends(get_db)
    current_user: ValidatedUser,   # Annotated alias, NOT Depends(require_permissions(...))
):
```

The spec shows `user=Depends(require_permissions(...))` and `db=Depends(get_db)` as shorthand. Implementers must use `DatabaseSession`, `ValidatedUser`, and `SchoolCtx` annotated aliases instead.

---

## 9. File Organization

### New Backend Files

```
backend/app/
├── models/
│   ├── staff.py                          # MODIFIED: add columns + StaffDocument + StaffEmploymentHistory
│   └── payroll.py                        # NEW: all 14 payroll models
├── schemas/
│   ├── staff.py                          # MODIFIED: add new fields to StaffCreate/Update/Response
│   ├── leave.py                          # NEW: leave types, balances, requests schemas
│   └── payroll.py                        # NEW: all payroll schemas
├── services/
│   ├── staff/
│   │   ├── staff_service.py              # MODIFIED: auto-record history on update
│   │   ├── document_service.py           # NEW: staff document upload/download/delete
│   │   ├── history_service.py            # NEW: employment history CRUD
│   │   └── workload_service.py           # NEW: workload calculation from timetable
│   ├── leave/
│   │   ├── __init__.py                   # NEW: re-exports
│   │   ├── type_service.py              # NEW: leave type CRUD
│   │   ├── balance_service.py           # NEW: balance tracking + initialization
│   │   └── request_service.py           # NEW: request lifecycle + approval
│   └── payroll/
│       ├── __init__.py                   # NEW: re-exports
│       ├── config_service.py            # NEW: salary grades, allowance/deduction types, tax brackets
│       ├── salary_service.py            # NEW: staff salary config CRUD
│       ├── calculation_service.py       # NEW: PAYE, SSNIT, net salary calculation engine
│       ├── run_service.py              # NEW: payroll run lifecycle
│       ├── payslip_service.py          # NEW: PDF generation + S3 storage
│       ├── bank_file_service.py        # NEW: bank file generation per config
│       ├── report_service.py           # NEW: SSNIT/PAYE/department/YTD reports
│       ├── audit_service.py            # NEW: payroll-specific audit logging
│       ├── loan_service.py            # NEW: loan lifecycle, eligibility, payroll integration
│       ├── loan_calculation_service.py # NEW: flat rate + reducing balance interest calculations
│       └── loan_statement_service.py  # NEW: loan statement PDF generation
├── api/v1/endpoints/
│   ├── staff/
│   │   ├── staff.py                      # MODIFIED: add document + history sub-routes
│   │   ├── documents.py                  # NEW: document upload/list/download/delete
│   │   └── history.py                    # NEW: employment history endpoints
│   ├── leave.py                          # NEW: leave types, balances, requests, calendar
│   └── payroll/
│       ├── __init__.py                   # NEW: combined router
│       ├── config.py                    # NEW: salary grades, allowances, deductions, tax brackets, bank configs
│       ├── salary.py                    # NEW: staff salary config endpoints
│       ├── runs.py                      # NEW: payroll run lifecycle endpoints
│       ├── payslips.py                  # NEW: payslip download/bulk generation
│       ├── reports.py                   # NEW: SSNIT/PAYE/department/audit reports
│       └── loans.py                    # NEW: 28 loan management endpoints
├── tasks/
│   ├── payroll.py                        # NEW: process_payroll_run, generate_bulk_payslips
│   └── leave.py                          # NEW: update_staff_leave_status (daily beat)
├── templates/reports/
│   ├── payslip.html                      # NEW: A5 landscape payslip template
│   └── loan_statement.html               # NEW: A4 loan statement template
└── constants/
    └── permissions.py                    # MODIFIED: add hr.leave.* + payroll.* permissions
```

### New Frontend Files

```
frontend/
├── actions/
│   ├── staff.action.ts                   # MODIFIED: add document + history + workload actions
│   ├── leave.action.ts                   # NEW: all leave CRUD actions
│   ├── payroll.action.ts                 # NEW: all payroll actions (~35 functions)
│   └── loans.action.ts                   # NEW: all loan actions (~25 functions)
├── types/
│   ├── index.ts                          # MODIFIED: add StaffDocument, EmploymentHistory, StaffWorkload
│   ├── leave.type.ts                     # NEW: LeaveType, LeaveBalance, LeaveRequest
│   ├── payroll.type.ts                   # NEW: all payroll TypeScript types
│   └── loan.type.ts                      # NEW: LoanType, StaffLoan, LoanInstallment, etc.
├── app/(dashboard)/
│   ├── staff/[id]/
│   │   ├── staff-documents.tsx           # NEW: document upload/list tab
│   │   └── employment-history.tsx        # NEW: timeline tab
│   ├── attendance/staff/
│   │   ├── page.tsx                      # NEW: staff attendance overview
│   │   ├── mark/page.tsx                # NEW: staff attendance marking
│   │   └── reports/page.tsx             # NEW: staff attendance reports
│   ├── staff/workload/page.tsx           # NEW: workload overview
│   ├── hr/leave/
│   │   ├── page.tsx                      # NEW: leave dashboard
│   │   ├── types/page.tsx               # NEW: leave type config
│   │   ├── requests/page.tsx            # NEW: request list + approve/reject
│   │   ├── calendar/page.tsx            # NEW: leave calendar
│   │   └── balances/page.tsx            # NEW: balance management
│   └── payroll/
│       ├── page.tsx                      # NEW: payroll dashboard
│       ├── runs/new/page.tsx            # NEW: create run
│       ├── runs/[id]/page.tsx           # NEW: run detail
│       ├── runs/[id]/review/page.tsx    # NEW: approve/reject
│       ├── runs/[id]/payslips/page.tsx  # NEW: payslip list
│       ├── staff/[staffId]/salary/      # NEW: salary config
│       ├── staff/[staffId]/payslips/    # NEW: payslip history
│       ├── settings/                     # NEW: 6 config pages
│       ├── reports/                      # NEW: 4 report pages
│       └── loans/                        # NEW: loan management
│           ├── page.tsx                  # Loan list
│           ├── new/page.tsx              # 4-step loan application wizard
│           ├── [id]/page.tsx             # Loan detail + schedule + payments
│           ├── [id]/statement/page.tsx   # Loan statement PDF
│           ├── portfolio/page.tsx        # Portfolio dashboard + charts
│           └── settings/page.tsx         # Loan type configuration
└── components/
    ├── staff/
    │   └── document-upload-dialog.tsx     # NEW
    ├── attendance/
    │   ├── staff-attendance-marking.tsx   # NEW
    │   └── staff-attendance-reports.tsx   # NEW
    ├── hr/
    │   ├── leave-request-form.tsx         # NEW
    │   ├── leave-approval-dialog.tsx      # NEW
    │   ├── leave-calendar.tsx             # NEW
    │   └── leave-balance-card.tsx         # NEW
    └── payroll/
        ├── PayrollRunList.tsx             # NEW
        ├── PayrollRunDetail.tsx           # NEW
        ├── PayrollItemsTable.tsx          # NEW
        ├── PayrollCalculationStatus.tsx   # NEW
        ├── PayrollApprovalFlow.tsx        # NEW
        ├── SalaryConfigForm.tsx           # NEW
        ├── BulkSalaryAssign.tsx           # NEW
        ├── TaxBracketsEditor.tsx          # NEW
        ├── BankFileConfigForm.tsx         # NEW
        ├── PayrollSummaryCards.tsx        # NEW
        ├── PayrollCharts.tsx              # NEW
        ├── SSNITReportTable.tsx           # NEW
        ├── PAYEReportTable.tsx            # NEW
        └── PayslipPreview.tsx             # NEW
```

---

## 9. Testing Strategy

### Test Files

| File | Phase | Tests | Focus |
|------|-------|-------|-------|
| `test_staff_hr_fields.py` | 1 | 8 | CRUD with TIN, employment_type, ges_staff_id; CSV import |
| `test_staff_documents.py` | 1 | 10 | Upload, list, download URL, delete, validation, IDOR, RLS |
| `test_staff_employment_history.py` | 1 | 7 | Create event, auto-record on update, ordering, RLS |
| `test_staff_attendance_frontend.py` | 2 | 8 | Frontend integration: marking, bulk, reports, filters |
| `test_staff_workload.py` | 3 | 5 | Workload from timetable, empty timetable, aggregation |
| `test_leave_types.py` | 3 | 6 | CRUD, unique code, soft delete, tenant isolation |
| `test_leave_balances.py` | 3 | 8 | Initialize, adjust, carryover, insufficient, bulk init |
| `test_leave_requests.py` | 3 | 12 | Submit, approve, reject, cancel, overlap, auto-approve, IDOR |
| `test_leave_rls.py` | 3 | 4 | RLS isolation for all 3 leave tables |
| `test_payroll_calculation.py` | 4 | 13 | PAYE bands, SSNIT, Tier 2, allowance methods, net salary |
| `test_payroll_config.py` | 4 | 7 | Salary grades, allowance/deduction types, tax brackets |
| `test_staff_salary.py` | 4 | 6 | Salary config CRUD, bulk assign, history |
| `test_payroll_processing.py` | 4 | 13 | Full run lifecycle, approval, separation of duties |
| `test_payslip_generation.py` | 4 | 4 | PDF output, account masking, YTD, branding |
| `test_bank_file_generation.py` | 4 | 5 | GCB/Ecobank/MoMo formats, S3 upload, custom config |
| `test_payroll_rls.py` | 4 | 6 | Tenant isolation, audit log append-only |
| `test_payroll_feature_flag.py` | 4 | 3 | Blocked without addon, accessible with addon |
| `test_loan_types.py` | 5 | 6 | CRUD, unique code, soft delete, validation |
| `test_loan_lifecycle.py` | 5 | 14 | Create, submit, approve, reject, disburse, status machine |
| `test_loan_calculation.py` | 5 | 10 | Flat rate, reducing balance, 0% interest, rounding, sum integrity |
| `test_loan_payroll_integration.py` | 5 | 8 | Due installment pickup, post-payment, auto-complete, net salary cap |
| `test_loan_early_repayment.py` | 5 | 5 | Partial, full settlement, balance update |
| `test_loan_restructure.py` | 5 | 4 | Old loan restructured, new schedule, history preserved |
| `test_loan_write_off.py` | 5 | 3 | Write-off with reason, balance zeroed |
| `test_loan_guarantors.py` | 5 | 4 | Add, consent, self-guarantor blocked, remove from draft |
| `test_loan_eligibility.py` | 5 | 5 | Service months, max active, max amount, max tenure |
| `test_loan_rls.py` | 5 | 5 | All 5 loan tables cross-tenant isolation |
| `test_loan_statement.py` | 5 | 2 | PDF generation, correct totals |
| `test_loan_portfolio.py` | 5 | 3 | Summary totals, by-type breakdown, aging buckets |
| `test_loan_feature_flag.py` | 5 | 2 | Blocked without hr_payroll, accessible with |

**Total: ~194 tests across 30 files**

### Testing Patterns

All tests follow the existing two-engine pattern from `conftest.py`:
- **admin engine** (superuser) for DDL, tenant setup, raw SQL verification
- **app_user engine** (non-superuser, RLS enforced) for service/endpoint testing
- Raw SQL enum values: **lowercase** for ALL enums
- `CAST(:param AS uuid)` for UUID bind params
- Every new RLS-enabled table gets a dedicated cross-tenant isolation test

---

## 10. Risk Summary

| Phase | Risk | Severity | Mitigation |
|-------|------|----------|-----------|
| 1 | Adding columns to busy `staff` table | Low | All nullable; no downtime migration |
| 2 | Backend API already tested | Low | Frontend-only work; stable backend |
| 3 | Leave day calculation accuracy | Medium | Unit test edge cases (year boundary, holidays) |
| 3 | Concurrent balance + request race | Medium | `with_for_update()` on balance row |
| 4 | PAYE calculation error | Critical | Unit tests against known GRA examples; manual adjustment escape |
| 4 | Rounding errors accumulate | High | `Decimal` throughout; round each step to 2dp |
| 4 | Approved payroll modified | Critical | Status machine enforced; only DRAFT/CALCULATED editable |
| 4 | Salary data leak | Critical | Account masking in API; presigned URLs; audit on reads |
| 4 | Celery task failure mid-processing | High | Idempotent task; transaction-wrapped; reverts to DRAFT |
| 5 | Rounding errors over loan term | High | Decimal throughout; last installment absorbs; sum integrity assertion |
| 5 | Double-deduction in payroll | Critical | Unique constraint; is_paid=false filter; atomic update on PAID |
| 5 | Net salary goes negative from loans | High | 50% cap on post-statutory net; configurable per loan type |
| 5 | Concurrent early repayment + payroll | Medium | with_for_update() on staff_loans for all balance mutations |

---

## 11. Sidebar Navigation Updates

### Attendance Section
Add sub-item **"Staff Attendance"** under existing Attendance menu:
- Visible to: `attendance.read` or `attendance.mark` permission
- Routes to: `/attendance/staff`

### HR Section (NEW)
Add new top-level **"HR"** section in sidebar:
- Visible to: any `hr.leave.*` permission
- Sub-items:
  - Leave Requests → `/hr/leave/requests`
  - Leave Calendar → `/hr/leave/calendar`
  - Leave Types → `/hr/leave/types` (admin only)
  - Leave Balances → `/hr/leave/balances` (admin only)

### Staff Section
Add sub-item **"Workload"** under existing Staff menu:
- Visible to: `staff.read` permission
- Routes to: `/staff/workload`

### Payroll Section (NEW)
Add new top-level **"Payroll"** section in sidebar:
- Visible to: any `payroll.*` permission
- Gated by: `hr_payroll` feature flag
- Sub-items:
  - Dashboard → `/payroll`
  - Payroll Runs → `/payroll/runs` (redirects to dashboard)
  - Loans → `/payroll/loans`
  - Loan Portfolio → `/payroll/loans/portfolio`
  - Settings → `/payroll/settings`
  - Reports → `/payroll/reports`

---

## 12. Open Questions

### Resolved

| # | Question | Decision |
|---|----------|----------|
| 1 | Half-day leave? | Yes — `NUMERIC(5,1)` for 0.5-day increments |
| 2 | Leave carryover? | Per leave type — `max_carryover_days` column on `leave_types` |
| 3 | Approval routing? | Any authorized user for MVP; add `assigned_approver_id` later |
| 4 | Auto-status on leave start? | Yes — daily Celery beat task `update_staff_leave_status` |
| 5 | Backfill employment_type? | No — leave as NULL; schools populate as needed |

### Deferred to Stakeholder Review

| # | Question | Context |
|---|----------|---------|
| 6 | Self-service payslips via teacher portal? | Needs teacher portal route extension |
| 7 | Multi-level payroll approval? | Single-level for MVP; `payroll_approvals` table supports multiple |
| 8 | Loan management sub-module? | **RESOLVED** — Phase 5 adds full loan management with balance tracking |
| 9 | 13th month salary / bonus rules? | `run_type=bonus` exists; special calculation rules TBD |
| 10 | Multi-currency payroll? | `currency` column exists; PAYE/SSNIT assume GHS |
| 11 | External payroll system integrations (HR-026)? | CSV/Excel export covers 90%; specific system APIs TBD |

# Phase 5: Staff Loan Management

**Duration:** 2-2.5 weeks
**Prerequisites:** Phase 4A (payroll tables), Phase 4B (payroll processing engine)
**Migration Chain:** `20260430_0200` → `20260501_0100`
**New Tables:** 5 (`loan_types`, `staff_loans`, `loan_installments`, `loan_guarantors`, `loan_payments`)
**Modified Tables:** 1 (`payroll_item_deductions` — add `loan_installment_id` FK)
**New Endpoints:** 28
**Tests:** ~71
**Feature Flag:** `hr_payroll` (same as payroll — Enterprise add-on)

---

## 1. Overview

The payroll module (Phase 4) treats loan deductions as simple fixed amounts — no balance tracking, no installment calculation, no lifecycle. This phase adds a **full loan sub-module** with:

- Configurable loan types (salary advance, welfare, equipment, emergency)
- Loan lifecycle: draft → pending_approval → approved → active → completed
- Interest calculation: flat rate and reducing balance methods
- Auto-generated installment schedules
- Payroll integration: auto-deduct monthly installments, post-payment balance updates
- Early repayment, loan restructuring, write-offs
- Net salary protection (cap loan deductions at 50% of post-statutory net)
- Loan statements (PDF), portfolio analytics, aging reports
- Guarantor management with consent tracking

---

## 2. Loan Lifecycle State Machine

```
                   ┌──────────┐
                   │  DRAFT   │  (created, under review)
                   └────┬─────┘
                        │ submit
                        ▼
                   ┌──────────────┐
          ┌───────│   PENDING    │──────────┐
          │       │   APPROVAL   │          │
          │       └──────────────┘          │
          │ reject                          │ approve
          ▼                                 ▼
   ┌──────────┐                     ┌──────────────┐
   │ REJECTED │                     │   APPROVED   │
   └──────────┘                     └──────┬───────┘
        │                                  │ disburse
        │ re-edit → back to DRAFT          ▼
        └──────────────►           ┌──────────────┐
                            ┌──────│    ACTIVE    │──────┐
                            │      └──────┬───────┘      │
                            │             │               │
                            │ write_off   │ all paid      │ restructure
                            ▼             ▼               ▼
                     ┌────────────┐ ┌───────────┐  ┌──────────────┐
                     │WRITTEN_OFF │ │ COMPLETED │  │ RESTRUCTURED │
                     └────────────┘ └───────────┘  └──────────────┘
```

**Valid transitions:**

| From | To | Trigger | Permission |
|------|----|---------|------------|
| `draft` | `pending_approval` | Staff/admin submits | `payroll.loans.request` |
| `pending_approval` | `approved` | Approver approves | `payroll.loans.approve` |
| `pending_approval` | `rejected` | Approver rejects | `payroll.loans.approve` |
| `rejected` | `draft` | Requester re-edits | `payroll.loans.request` |
| `approved` | `active` | Finance confirms disbursement | `payroll.loans.disburse` |

**Self-Approval Prevention:** The approval check must verify BOTH:
1. `loan.staff_id != current_user.staff_id` (borrower cannot approve own loan)
2. `loan.created_by != current_user.id` (submitter cannot approve own submission)

Add a `created_by UUID FK → users` column to `staff_loans` to enable check #2. This prevents HR officers from creating AND approving their own loans.
| `active` | `completed` | System (last installment paid) | Automatic |
| `active` | `written_off` | Admin writes off balance | `payroll.loans.write_off` |
| `active` | `restructured` | Admin restructures | `payroll.loans.manage` |

**Terminal states:** `completed`, `written_off`, `restructured`

---

## 3. Database Schema

### 3.1 New Enums

| Enum Name | DB Type | Values |
|-----------|---------|--------|
| `LoanStatus` | `loanstatus` | `draft`, `pending_approval`, `approved`, `active`, `completed`, `written_off`, `restructured`, `rejected` |
| `InterestMethod` | `interestmethod` | `flat`, `reducing_balance` |

### 3.2 Table: `loan_types`

Configuration table for school-defined loan categories.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | RLS scope |
| `school_id` | UUID | FK → schools, NULL | Chain support |
| `name` | VARCHAR(100) | NOT NULL | "Salary Advance", "Staff Welfare Loan" |
| `code` | VARCHAR(20) | NOT NULL | "SAL_ADV", "WELFARE" |
| `description` | TEXT | NULL | |
| `default_interest_rate` | NUMERIC(5,2) | NOT NULL, default 0.00 | Annual rate % (e.g. 10.00 = 10%) |
| `default_interest_method` | `interestmethod` | NOT NULL, default 'flat' | |
| `max_amount` | NUMERIC(12,2) | NULL | Max loan amount (NULL = no limit) |
| `max_tenure_months` | INTEGER | NULL | Max repayment months (NULL = no limit) |
| `max_active_loans` | INTEGER | NOT NULL, default 1 | Max concurrent active loans of this type per staff |
| `requires_guarantor` | BOOLEAN | NOT NULL, default false | |
| `min_service_months` | INTEGER | NOT NULL, default 0 | Min months of employment before eligible |
| `max_deduction_pct` | NUMERIC(5,2) | NOT NULL, default 50.00 | Max % of post-statutory net salary for deductions |
| `is_active` | BOOLEAN | NOT NULL, default true | |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(code, tenant_id, deleted_at)`

### 3.3 Table: `staff_loans`

Core loan entity tracking the full lifecycle.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | |
| `loan_number` | VARCHAR(30) | NOT NULL | Auto-generated: `LN-{YYYY}-{seq:04d}` |
| `staff_id` | UUID | FK → staff, NOT NULL | Borrower |
| `loan_type_id` | UUID | FK → loan_types, NOT NULL | |
| `status` | `loanstatus` | NOT NULL, default 'draft' | |
| `principal_amount` | NUMERIC(12,2) | NOT NULL, > 0 | Original loan amount (GHS) |
| `interest_rate` | NUMERIC(5,2) | NOT NULL, default 0.00 | Annual interest rate % |
| `interest_method` | `interestmethod` | NOT NULL, default 'flat' | |
| `total_interest` | NUMERIC(12,2) | NOT NULL, default 0.00 | Computed total interest |
| `total_repayable` | NUMERIC(12,2) | NOT NULL | principal + total_interest |
| `tenure_months` | INTEGER | NOT NULL, > 0 | Number of monthly installments |
| `monthly_installment` | NUMERIC(12,2) | NOT NULL | Computed monthly deduction |
| `total_paid` | NUMERIC(12,2) | NOT NULL, default 0.00 | Running total of payments |
| `outstanding_balance` | NUMERIC(12,2) | NOT NULL | total_repayable - total_paid |
| `installments_paid` | INTEGER | NOT NULL, default 0 | |
| `installments_remaining` | INTEGER | NOT NULL | |
| `application_date` | DATE | NOT NULL, default CURRENT_DATE | |
| `approval_date` | DATE | NULL | |
| `disbursement_date` | DATE | NULL | |
| `first_deduction_date` | DATE | NULL | Must be 1st of month |
| `expected_completion_date` | DATE | NULL | first_deduction + tenure months |
| `actual_completion_date` | DATE | NULL | Set on status = completed |
| `purpose` | TEXT | NULL | |
| `created_by` | UUID | FK → users, NULL | User who created the loan (for self-approval prevention) |
| `approved_by` | UUID | FK → users, NULL | |
| `disbursed_by` | UUID | FK → users, NULL | |
| `restructured_from_id` | UUID | FK → staff_loans, NULL | Self-reference: if replaced |
| `write_off_reason` | TEXT | NULL | |
| `write_off_date` | DATE | NULL | |
| `written_off_by` | UUID | FK → users, NULL | |
| `notes` | TEXT | NULL | |
| `deleted_at` | TIMESTAMPTZ | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(loan_number, tenant_id)`
**Indexes:** `(tenant_id, staff_id, status)`, `(tenant_id, status)`, `(tenant_id, loan_type_id)`

### 3.4 Table: `loan_installments`

One row per scheduled monthly payment. Pre-generated at disbursement.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | Chain support |
| `loan_id` | UUID | FK → staff_loans, CASCADE, NOT NULL | |
| `installment_number` | INTEGER | NOT NULL, > 0 | 1, 2, 3... |
| `due_date` | DATE | NOT NULL | 1st of the month |
| `principal_component` | NUMERIC(12,2) | NOT NULL | Principal portion |
| `interest_component` | NUMERIC(12,2) | NOT NULL | Interest portion |
| `installment_amount` | NUMERIC(12,2) | NOT NULL | principal + interest |
| `opening_balance` | NUMERIC(12,2) | NOT NULL | Balance before this installment |
| `closing_balance` | NUMERIC(12,2) | NOT NULL | Balance after (if paid) |
| `is_paid` | BOOLEAN | NOT NULL, default false | |
| `paid_date` | DATE | NULL | |
| `paid_amount` | NUMERIC(12,2) | NULL | Actual paid (may differ for partial) |
| `payroll_run_id` | UUID | FK → payroll_runs, NULL | Link to payroll run |
| `payroll_item_deduction_id` | UUID | FK → payroll_item_deductions, NULL | Specific deduction line |
| `notes` | TEXT | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(loan_id, installment_number)`
**Indexes:** `(tenant_id, due_date, is_paid)` — critical for payroll query; `(loan_id, is_paid)`
**No SoftDeleteMixin** — installments are never soft-deleted; historical records preserved.

### 3.5 Table: `loan_guarantors`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `loan_id` | UUID | FK → staff_loans, CASCADE, NOT NULL | |
| `guarantor_staff_id` | UUID | FK → staff, NOT NULL | |
| `relationship` | VARCHAR(50) | NULL | "Colleague", "HOD" |
| `guaranteed_amount` | NUMERIC(12,2) | NULL | Max liability (NULL = full) |
| `consent_given` | BOOLEAN | NOT NULL, default false | Must be true before approval |
| `consent_date` | DATE | NULL | |
| `notes` | TEXT | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(loan_id, guarantor_staff_id)`

### 3.6 Table: `loan_payments`

Records ALL payments — both payroll deductions and out-of-band payments.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | Chain support |
| `loan_id` | UUID | FK → staff_loans, NOT NULL | |
| `payment_number` | VARCHAR(30) | NOT NULL | Auto: `LP-{YYYY}-{seq:04d}` |
| `amount` | NUMERIC(12,2) | NOT NULL, > 0 | |
| `payment_date` | DATE | NOT NULL | |
| `payment_method` | VARCHAR(20) | NOT NULL | cash, bank_transfer, mobile_money, payroll |
| `reference` | VARCHAR(100) | NULL | Receipt/transaction ref |
| `installments_covered` | JSONB | NULL | Array of installment IDs |
| `is_early_repayment` | BOOLEAN | NOT NULL, default false | |
| `recorded_by` | UUID | FK → users, NOT NULL | |
| `notes` | TEXT | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(payment_number, tenant_id)`
**Index:** `(tenant_id, loan_id, payment_date)`

### 3.7 Modified Table: `payroll_item_deductions`

Add column:
```sql
ALTER TABLE payroll_item_deductions
    ADD COLUMN loan_installment_id UUID REFERENCES loan_installments(id) ON DELETE SET NULL;

CREATE INDEX ix_payroll_item_deductions_loan
    ON payroll_item_deductions(loan_installment_id)
    WHERE loan_installment_id IS NOT NULL;
```

---

## 4. Interest Calculation Engine

### 4.1 Flat Rate Method

Interest calculated on **original principal** for the full term. Common in Ghana.

```python
def calculate_flat_rate_loan(principal: Decimal, annual_rate: Decimal, tenure_months: int) -> dict:
    """
    Flat rate: interest = principal * (annual_rate / 100) * (tenure_months / 12)
    Monthly installment = (principal + total_interest) / tenure_months

    Example: GHS 5,000 at 10% flat for 12 months
      total_interest = 5000 * 0.10 * (12/12) = GHS 500.00
      total_repayable = GHS 5,500.00
      monthly = GHS 458.33 (last installment: GHS 458.37 for rounding)
    """
    rate = annual_rate / Decimal("100")
    total_interest = (principal * rate * Decimal(tenure_months) / Decimal("12")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_repayable = principal + total_interest
    monthly = (total_repayable / Decimal(tenure_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    monthly_principal = (principal / Decimal(tenure_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    monthly_interest = (total_interest / Decimal(tenure_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    installments = []
    remaining = total_repayable
    running_principal_sum = Decimal("0")
    running_interest_sum = Decimal("0")
    for i in range(1, tenure_months + 1):
        opening = remaining
        if i == tenure_months:
            inst_amount = remaining  # Last installment absorbs rounding
            # Ensure principal and interest components sum correctly across all installments
            p_comp = principal - running_principal_sum
            i_comp = inst_amount - p_comp
        else:
            inst_amount = monthly
            p_comp = monthly_principal
            i_comp = monthly_interest
        remaining = (opening - inst_amount).quantize(Decimal("0.01"))
        running_principal_sum += p_comp
        running_interest_sum += i_comp
        installments.append({
            "installment_number": i,
            "principal_component": p_comp,
            "interest_component": i_comp,
            "installment_amount": inst_amount,
            "opening_balance": opening,
            "closing_balance": max(remaining, Decimal("0.00")),
        })

    # Sum integrity assertions (must hold exactly)
    assert sum(i["principal_component"] for i in installments) == principal
    assert sum(i["installment_amount"] for i in installments) == total_repayable
    assert installments[-1]["closing_balance"] == Decimal("0.00")

    return {
        "total_interest": total_interest,
        "total_repayable": total_repayable,
        "monthly_installment": monthly,
        "installments": installments,
    }
```

### 4.2 Reducing Balance Method

Interest recalculated each month on outstanding principal. Uses EMI (Equated Monthly Installment) formula.

```python
def calculate_reducing_balance_loan(principal: Decimal, annual_rate: Decimal, tenure_months: int) -> dict:
    """
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly rate, n = tenure months

    If rate is 0%, EMI = P / n (simple division).

    Example: GHS 5,000 at 10% reducing for 12 months
      monthly_rate = 0.10 / 12 = 0.008333
      EMI ≈ GHS 439.58
      total_interest ≈ GHS 274.96
    """
    if annual_rate == Decimal("0"):
        # Zero interest — equal principal installments
        monthly = (principal / Decimal(tenure_months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        installments = []
        remaining = principal
        for i in range(1, tenure_months + 1):
            opening = remaining
            inst = remaining if i == tenure_months else monthly
            remaining = (opening - inst).quantize(Decimal("0.01"))
            installments.append({
                "installment_number": i,
                "principal_component": inst,
                "interest_component": Decimal("0.00"),
                "installment_amount": inst,
                "opening_balance": opening,
                "closing_balance": max(remaining, Decimal("0.00")),
            })
        return {"total_interest": Decimal("0.00"), "total_repayable": principal,
                "monthly_installment": monthly, "installments": installments}

    monthly_rate = annual_rate / Decimal("1200")
    n = Decimal(tenure_months)
    power = (1 + monthly_rate) ** int(n)
    emi = (principal * monthly_rate * power / (power - 1)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    installments = []
    remaining_principal = principal
    total_interest = Decimal("0.00")
    for i in range(1, tenure_months + 1):
        opening = remaining_principal
        interest_comp = (remaining_principal * monthly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if i == tenure_months:
            principal_comp = remaining_principal
            inst_amount = principal_comp + interest_comp
        else:
            inst_amount = emi
            principal_comp = (inst_amount - interest_comp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        remaining_principal = (opening - principal_comp).quantize(Decimal("0.01"))
        total_interest += interest_comp
        installments.append({
            "installment_number": i,
            "principal_component": principal_comp,
            "interest_component": interest_comp,
            "installment_amount": inst_amount,
            "opening_balance": opening,
            "closing_balance": max(remaining_principal, Decimal("0.00")),
        })

    return {"total_interest": total_interest, "total_repayable": principal + total_interest,
            "monthly_installment": emi, "installments": installments}
```

### 4.3 Validation Rule: Sum Integrity

At schedule generation time, assert:
```python
assert sum(i["installment_amount"] for i in installments) == total_repayable
assert sum(i["principal_component"] for i in installments) == principal
assert installments[-1]["closing_balance"] == Decimal("0.00")
```

---

## 5. Payroll Integration

### 5.1 Modified Payroll Calculation Flow

In `calculation_service.py`, the "other deductions" step is modified:

```python
# EXISTING Step: process staff_deductions
for d in staff_deductions:
    if d["deduction_type"]["deduction_category"] == "loan":
        continue  # SKIP — loans now handled by loan module

# NEW Step: loan installments
from app.services.payroll.loan_service import LoanService
loan_service = LoanService(db)
due_installments = await loan_service.get_due_installments(
    tenant_id=tenant_id, staff_id=staff_id,
    year=payroll_run.year, month=payroll_run.month,
)

# Net salary protection — use minimum max_deduction_pct across all loan types
post_statutory_net = gross_salary - paye_tax - ssnit_employee - tier3_employee
if due_installments:
    min_cap_pct = min(
        inst.loan.loan_type.max_deduction_pct for inst in due_installments
    ) / Decimal("100")
else:
    min_cap_pct = Decimal("0.50")
max_loan_deduction = (post_statutory_net * min_cap_pct).quantize(Decimal("0.01"))
total_loan_amount = sum(inst.installment_amount for inst in due_installments)

if total_loan_amount > max_loan_deduction and max_loan_deduction > 0:
    # Cap and proportionally reduce
    ratio = max_loan_deduction / total_loan_amount
    for inst in due_installments:
        capped = (inst.installment_amount * ratio).quantize(Decimal("0.01"))
        deduction_items.append({
            "name": f"Loan {inst.loan.loan_number} - #{inst.installment_number}",
            "amount": capped,
            "is_statutory": False, "is_employer_portion": False,
            "category": "loan", "loan_installment_id": inst.id,
        })
        total_other += capped
    # Log capping in audit
else:
    for inst in due_installments:
        deduction_items.append({
            "name": f"Loan {inst.loan.loan_number} - #{inst.installment_number}",
            "amount": inst.installment_amount,
            "is_statutory": False, "is_employer_portion": False,
            "category": "loan", "loan_installment_id": inst.id,
        })
        total_other += inst.installment_amount
```

### 5.2 Post-Payment Hook

In `run_service.py`, when `mark_paid()` is called:

```python
async def mark_paid(self, tenant_id, run_id, user_id):
    # ... existing mark-paid logic ...

    # NEW: Process loan payments
    loan_service = LoanService(self.db)
    completed_loans = await loan_service.process_payroll_payment(
        tenant_id=tenant_id, payroll_run_id=run_id, performed_by=user_id
    )
    # completed_loans = list of loans that became 'completed' this run
```

### 5.3 Recalculation Guard

When a payroll run is recalculated (items deleted and recreated), the recalculation logic must first check if any `payroll_item_deductions` rows have a `loan_installment_id` where the linked installment has `is_paid=True`. If so, the run **CANNOT be recalculated** — it must be cancelled and a new run created. This prevents orphaning paid installments whose balance updates have already been committed.

Add this check in `run_service.calculate()` before deleting existing items:
```python
# Before recalculation: check for paid loan installments
paid_loan_deductions = await db.execute(
    select(PayrollItemDeduction)
    .join(PayrollItem)
    .join(LoanInstallment, PayrollItemDeduction.loan_installment_id == LoanInstallment.id)
    .where(PayrollItem.payroll_run_id == run_id, LoanInstallment.is_paid == True)
)
if paid_loan_deductions.scalars().first():
    raise Error("Cannot recalculate: run has paid loan installments. Cancel and create a new run.", "LOAN_CONFLICT")
```

### 5.4 LoanService Integration Methods

```python
class LoanService:
    async def get_due_installments(self, tenant_id, staff_id, year, month) -> list[LoanInstallment]:
        """
        Query: unpaid installments for active loans where due_date falls in given month.
        Used by payroll calculation engine.
        """
        return await self.db.execute(
            select(LoanInstallment)
            .join(StaffLoan, LoanInstallment.loan_id == StaffLoan.id)
            .options(selectinload(LoanInstallment.loan))
            .where(
                StaffLoan.staff_id == staff_id,
                StaffLoan.tenant_id == tenant_id,
                StaffLoan.status == "active",
                LoanInstallment.is_paid == False,
                extract("year", LoanInstallment.due_date) == year,
                extract("month", LoanInstallment.due_date) == month,
            )
            .order_by(LoanInstallment.installment_number)
        )

    async def get_all_due_installments_for_run(self, tenant_id, year, month) -> dict[UUID, list]:
        """
        Batch query: all due installments for all staff in a month.
        Returns dict keyed by staff_id for O(1) lookup during payroll.
        Used instead of N per-staff queries for performance.
        """

    async def process_payroll_payment(self, tenant_id, payroll_run_id, performed_by) -> list[StaffLoan]:
        """
        Post-payment hook. For each payroll_item_deduction with loan_installment_id:
        1. Mark installment as paid (is_paid=True, paid_date=today, paid_amount)
        2. Create loan_payment record (payment_method='payroll')
        3. Update staff_loans: total_paid, outstanding_balance, installments_paid/remaining
        4. If outstanding_balance <= 0: set status='completed', actual_completion_date
        5. Audit log each update
        Returns list of newly completed loans.
        """
```

---

## 6. API Endpoints (28 total)

### 6.1 Loan Type Configuration (4)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/loan-types` | List loan types | `payroll.read` |
| POST | `/payroll/loan-types` | Create loan type | `payroll.configure` |
| PUT | `/payroll/loan-types/{id}` | Update loan type | `payroll.configure` |
| DELETE | `/payroll/loan-types/{id}` | Soft-delete | `payroll.configure` |

### 6.2 Loan Lifecycle (9)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/loans` | List loans (filterable) | `payroll.loans.read` |
| POST | `/payroll/loans` | Create loan (draft) | `payroll.loans.request` |
| GET | `/payroll/loans/{id}` | Loan detail + schedule + payments | `payroll.loans.read` |
| PUT | `/payroll/loans/{id}` | Update draft loan | `payroll.loans.request` |
| POST | `/payroll/loans/{id}/submit` | Submit for approval | `payroll.loans.request` |
| POST | `/payroll/loans/{id}/approve` | Approve (cannot self-approve) | `payroll.loans.approve` |
| POST | `/payroll/loans/{id}/reject` | Reject with reason | `payroll.loans.approve` |
| POST | `/payroll/loans/{id}/disburse` | Disburse + generate schedule | `payroll.loans.disburse` |
| DELETE | `/payroll/loans/{id}` | Cancel draft | `payroll.loans.request` |

### 6.3 Loan Operations (4)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| POST | `/payroll/loans/{id}/early-repayment` | Record early/lump-sum payment | `payroll.loans.manage` |
| POST | `/payroll/loans/{id}/restructure` | Restructure (new terms, new schedule) | `payroll.loans.manage` |
| POST | `/payroll/loans/{id}/write-off` | Write off remaining balance | `payroll.loans.write_off` |
| GET | `/payroll/loans/{id}/statement` | Generate loan statement PDF | `payroll.loans.read` |

### 6.4 Installments & Payments (2)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/loans/{id}/installments` | List installments | `payroll.loans.read` |
| GET | `/payroll/loans/{id}/payments` | List payments | `payroll.loans.read` |

### 6.5 Guarantors (3)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| POST | `/payroll/loans/{id}/guarantors` | Add guarantor | `payroll.loans.request` |
| DELETE | `/payroll/loans/{id}/guarantors/{gid}` | Remove (draft only) | `payroll.loans.request` |
| PUT | `/payroll/loans/{id}/guarantors/{gid}/consent` | Record consent | `payroll.loans.approve` |

### 6.6 Staff View (2)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/staff/{staff_id}/loans` | All loans for staff | `payroll.loans.read` |
| GET | `/payroll/staff/{staff_id}/loan-eligibility` | Check eligibility | `payroll.loans.read` |

### 6.7 Analytics & Reports (4)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/loans/portfolio` | Portfolio summary | `payroll.loans.read` |
| GET | `/payroll/loans/portfolio/export` | Export as Excel | `payroll.loans.read` |
| GET | `/payroll/reports/loan-aging` | Aging report (30/60/90/120+ days) | `payroll.loans.read` |
| GET | `/payroll/reports/loan-aging/export` | Export aging as Excel | `payroll.loans.read` |

---

## 7. Key Pydantic Schemas

```python
class LoanTypeCreate(BaseModel):
    name: str = Field(max_length=100)
    code: str = Field(max_length=20, pattern=r"^[A-Z0-9_]+$")
    description: str | None = None
    default_interest_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    default_interest_method: str = "flat"  # flat | reducing_balance
    max_amount: Decimal | None = Field(default=None, gt=0)
    max_tenure_months: int | None = Field(default=None, gt=0, le=60)
    max_active_loans: int = Field(default=1, ge=1, le=10)
    requires_guarantor: bool = False
    min_service_months: int = Field(default=0, ge=0)
    max_deduction_pct: Decimal = Field(default=Decimal("50.00"), ge=10, le=100)

class LoanCreate(BaseModel):
    staff_id: UUID
    loan_type_id: UUID
    principal_amount: Decimal = Field(gt=0, le=Decimal("999999.99"))
    interest_rate: Decimal | None = None      # NULL = use loan type default
    interest_method: str | None = None         # NULL = use loan type default
    tenure_months: int = Field(gt=0, le=60)
    first_deduction_date: date                 # Must be 1st of a future month
    purpose: str | None = Field(default=None, max_length=500)
    guarantor_staff_ids: list[UUID] = []

class LoanResponse(BaseModel):
    id: UUID
    loan_number: str
    staff_id: UUID
    staff_name: str
    loan_type: LoanTypeResponse
    status: str
    principal_amount: Decimal
    interest_rate: Decimal
    interest_method: str
    total_interest: Decimal
    total_repayable: Decimal
    tenure_months: int
    monthly_installment: Decimal
    total_paid: Decimal
    outstanding_balance: Decimal
    installments_paid: int
    installments_remaining: int
    application_date: date
    approval_date: date | None
    disbursement_date: date | None
    first_deduction_date: date | None
    expected_completion_date: date | None
    actual_completion_date: date | None
    purpose: str | None
    guarantors: list[LoanGuarantorResponse]

class EarlyRepaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_date: date
    payment_method: str       # cash, bank_transfer, mobile_money
    reference: str | None = None
    is_full_settlement: bool = False
    notes: str | None = None

class LoanRestructureRequest(BaseModel):
    new_interest_rate: Decimal = Field(ge=0, le=100)
    new_interest_method: str   # flat | reducing_balance
    new_tenure_months: int = Field(gt=0, le=60)
    new_first_deduction_date: date
    reason: str = Field(min_length=10, max_length=500)

class LoanPortfolioResponse(BaseModel):
    total_loans: int
    active_loans: int
    total_disbursed: Decimal
    total_outstanding: Decimal
    total_collected: Decimal
    total_written_off: Decimal
    average_loan_amount: Decimal
    by_type: list[LoanTypeBreakdown]
    by_status: dict[str, int]
    overdue_count: int
    overdue_amount: Decimal
```

---

## 8. Net Salary Protection

**Critical business rule:** Loan deductions must not push take-home pay below a survivable threshold.

```python
# During payroll calculation, after PAYE + SSNIT:
post_statutory_net = gross_salary - paye_tax - ssnit_employee - tier3_employee
max_loan_deduction = (post_statutory_net * loan_type.max_deduction_pct / 100).quantize(Decimal("0.01"))

if total_loan_this_month > max_loan_deduction:
    ratio = max_loan_deduction / total_loan_this_month
    for each installment:
        capped_amount = (installment_amount * ratio).quantize(Decimal("0.01"))
        # Deduct capped_amount, record as partial payment
        # Difference carries forward to next month
    # Audit log: "Loan deductions capped at {pct}%"
```

Default: 50%. Configurable per loan type via `max_deduction_pct`.

---

## 9. Loan Statement PDF

**File:** `backend/app/templates/reports/loan_statement.html`
**Format:** A4 portrait

```
┌─────────────────────────────────────────────────────────┐
│  [LOGO]  SCHOOL NAME — LOAN STATEMENT                   │
│                                                          │
│  Loan No: LN-2026-0042        Status: ACTIVE            │
│  Staff: John Doe (STF-2026-001)                         │
│  Loan Type: Staff Welfare Loan                          │
│  Applied: 15/01/2026  Disbursed: 20/01/2026             │
│─────────────────────────────────────────────────────────│
│  LOAN SUMMARY                                            │
│  Principal:     GHS 5,000.00                             │
│  Interest:      GHS 500.00 (10% flat, 12 months)        │
│  Total:         GHS 5,500.00                             │
│  Monthly:       GHS 458.33                               │
│  Paid:          GHS 2,291.65                             │
│  Outstanding:   GHS 3,208.35                             │
│─────────────────────────────────────────────────────────│
│  INSTALLMENT SCHEDULE                                    │
│  # │ Due Date   │ Amount   │ Paid    │ Balance  │ Status│
│  1 │ 01/02/2026 │ 458.33   │ 458.33  │ 5041.67  │ ✓    │
│  2 │ 01/03/2026 │ 458.33   │ 458.33  │ 4583.34  │ ✓    │
│  3 │ 01/04/2026 │ 458.33   │ 458.33  │ 4125.01  │ ✓    │
│  ...                                                     │
│─────────────────────────────────────────────────────────│
│  Generated: 25/03/2026                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Frontend Pages

```
frontend/app/(dashboard)/payroll/loans/
├── page.tsx                    # Loan list: filterable by status, type, staff
├── new/page.tsx                # 4-step wizard: Type → Amount/Terms → Guarantors → Review
├── [id]/page.tsx               # Detail: status badge, metrics, tabs (Schedule, Payments, History)
├── [id]/statement/page.tsx     # View/download loan statement PDF
├── portfolio/page.tsx          # Summary cards + charts (pie by type, bar by month)
└── settings/page.tsx           # Loan type configuration table
```

**Key components:**
- `LoanApplicationForm.tsx` — 4-step wizard with live installment preview
- `LoanInstallmentTable.tsx` — Color-coded: green=paid, white=future, red=overdue
- `LoanApprovalDialog.tsx` / `LoanDisbursementDialog.tsx`
- `EarlyRepaymentDialog.tsx` / `LoanRestructureDialog.tsx` / `LoanWriteOffDialog.tsx`
- `LoanPortfolioDashboard.tsx` — 4 summary cards + Recharts
- `LoanAgingReport.tsx` — 30/60/90/120+ day buckets
- `StaffLoanSummaryCard.tsx` — Widget for staff detail page sidebar

---

## 11. Permissions

| Permission Key | Label | Assigned To |
|---------------|-------|-------------|
| `payroll.loans.read` | View loan data | school_admin, chain_admin, hr_officer, finance_officer |
| `payroll.loans.request` | Request loans | school_admin, chain_admin, hr_officer |
| `payroll.loans.approve` | Approve loans | school_admin, chain_admin, hr_officer |
| `payroll.loans.disburse` | Disburse loans | school_admin, chain_admin, finance_officer |
| `payroll.loans.manage` | Manage loans | school_admin, chain_admin, hr_officer |
| `payroll.loans.write_off` | Write off loans | school_admin, chain_admin |

---

## 12. Sub-Sprint Breakdown

| Sprint | Duration | Scope | Dependencies |
|--------|----------|-------|-------------|
| **5A** | 3-4 days | Migration (5 tables, 2 enums, FK). Models. Loan type CRUD. Calculation engine (flat + reducing). Loan type settings page. | Phase 4A migration |
| **5B** | 4-5 days | Loan create/submit/approve/reject/disburse. Schedule generation. Guarantors. Eligibility. Loan list + detail + application form pages. | 5A |
| **5C** | 3-4 days | Payroll integration (get_due_installments, post-payment hook). Early repayment, restructure, write-off. Net salary protection. Loan operations frontend. | 5B + Phase 4B |
| **5D** | 2-3 days | Loan statement PDF. Portfolio dashboard. Aging report. Excel export. RLS + feature flag tests. Integration test. | 5C |

---

## 13. Tests (~71 across 13 files)

| File | Count | Focus |
|------|-------|-------|
| `test_loan_types.py` | 6 | CRUD, unique code, soft delete, validation |
| `test_loan_lifecycle.py` | 14 | Create → submit → approve → disburse, reject + re-edit, self-approval blocked, status machine |
| `test_loan_calculation.py` | 10 | Flat: 0%, 10%/12mo, 5%/3mo. Reducing: 0%, 10%/12mo, 8%/24mo. Rounding. 1-month edge case. Sum integrity. |
| `test_loan_payroll_integration.py` | 8 | Due installment pickup, multi-loan same staff, post-payment balance update, auto-complete, net salary cap |
| `test_loan_early_repayment.py` | 5 | Partial, full settlement, balance update, installments marked, overpayment rejected |
| `test_loan_restructure.py` | 4 | Old loan restructured, new loan created, new schedule, old installments preserved |
| `test_loan_write_off.py` | 3 | Write-off with reason, balance zeroed, audit logged |
| `test_loan_guarantors.py` | 4 | Add, consent flow, self-guarantor blocked, remove from draft only |
| `test_loan_eligibility.py` | 5 | Service months, max active, max amount, max tenure, combined |
| `test_loan_rls.py` | 5 | All 5 tables cross-tenant isolation |
| `test_loan_statement.py` | 2 | PDF generation, correct totals |
| `test_loan_portfolio.py` | 3 | Summary totals, by-type breakdown, aging buckets |
| `test_loan_feature_flag.py` | 2 | Blocked without hr_payroll, accessible with |

### Critical Calculation Test Cases

```
Flat rate: GHS 5,000 at 10% for 12 months
  → total_interest = 500.00, monthly = 458.33, last = 458.37
  → assert sum(all installments) == 5500.00

Reducing balance: GHS 5,000 at 10% for 12 months
  → EMI ≈ 439.58, total_interest ≈ 274.96
  → assert sum(principal_components) == 5000.00

0% interest (salary advance): GHS 2,000 for 3 months
  → monthly = 666.67, last = 666.66
  → assert total_interest == 0.00, sum == 2000.00
```

---

## 14. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Rounding errors over loan term | High | `Decimal` throughout; last installment absorbs; sum integrity assertion |
| Double-deduction in payroll | Critical | Unique `(loan_id, installment_number)`; `is_paid=false` filter; set `is_paid=true` atomically on PAID |
| Payroll recalculation duplicates | High | Existing idempotency: delete items + recreate; `is_paid` only set on PAID, not CALCULATED |
| Net salary goes negative | High | 50% cap on post-statutory net; proportional reduction; configurable per loan type |
| Concurrent early repayment + payroll | Medium | `with_for_update()` on `staff_loans` for all balance mutations |
| Staff termination with outstanding loan | Medium | Loans remain active; admin notified; explicit write-off or settlement required |

---

## 15. Acceptance Criteria

- [ ] Loan types configurable per school (name, interest rate, method, limits, guarantor requirement)
- [ ] Loans follow full lifecycle: draft → pending → approved → active → completed
- [ ] Self-approval blocked (approved_by != staff_id)
- [ ] Flat rate and reducing balance interest calculations are correct (verified by sum assertions)
- [ ] Installment schedule pre-generated at disbursement with correct opening/closing balances
- [ ] Payroll automatically deducts due loan installments
- [ ] Net salary protection caps loan deductions at configurable % (default 50%)
- [ ] Post-payment hook updates loan balance and auto-completes on last installment
- [ ] Early repayment records payment and marks installments as paid
- [ ] Restructure creates new loan with new terms, marks old as restructured
- [ ] Write-off zeros balance with mandatory reason
- [ ] Guarantor consent required before loan approval (when loan type requires it)
- [ ] Loan statement PDF generates with correct schedule and totals
- [ ] Portfolio dashboard shows summary metrics and charts
- [ ] Aging report shows overdue installments in 30/60/90/120+ day buckets
- [ ] All 5 tables have RLS policies and are in TENANT_SCOPED_TABLES
- [ ] All endpoints gated by `hr_payroll` feature flag
- [ ] All 71 tests pass

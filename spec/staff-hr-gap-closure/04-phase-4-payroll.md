# Phase 4: Payroll Module

**Duration:** 6 weeks (4 sub-sprints)
**Prerequisites:** Phase 1 (staff TIN column)
**Migration Chain:** `20260426_0400` → `20260430_0100` → `20260430_0200`
**New Tables:** 14
**New Endpoints:** 48
**Tests:** ~55
**Celery Tasks:** 2 (`process_payroll_run`, `generate_bulk_payslips`)
**Feature Flag:** `hr_payroll` (Enterprise add-on, GHS 500/term)

---

## 1. Overview

The Payroll module enables schools to configure salary structures, process monthly payroll with Ghana statutory deductions (PAYE, SSNIT, Tier 2/3), generate payslip PDFs, produce bank payment files, and export statutory returns (SSNIT, GRA).

Gated behind the `hr_payroll` feature flag — Enterprise add-on only.

---

## 2. Sub-Sprint Breakdown

| Sub-Sprint | Duration | Scope |
|-----------|----------|-------|
| **4A** | 2 weeks | Foundation: 14 models, migration, seed data, config service, salary service, ~22 endpoints, settings frontend |
| **4B** | 2 weeks | Processing: calculation engine (PAYE/SSNIT), Celery task, run lifecycle, ~14 endpoints, runs frontend |
| **4C** | 1.5 weeks | Output: payslip PDF, bank file generation, reports, ~12 endpoints, reports frontend |
| **4D** | 0.5 weeks | Polish: audit log UI, security review, E2E test, performance test |

---

## 3. Database Schema

### 3.1 New Tables — Complete Column Definitions

#### `salary_grades`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | RLS scope |
| `school_id` | UUID | FK → schools, NULL | Chain support |
| `name` | VARCHAR(100) | NOT NULL | "Grade A", "Senior Teacher Scale" |
| `code` | VARCHAR(20) | NULL | "GR-A", "STS" |
| `basic_salary` | NUMERIC(12,2) | NOT NULL, >= 0 | Base monthly salary |
| `min_salary` | NUMERIC(12,2) | NULL | Range minimum (informational) |
| `max_salary` | NUMERIC(12,2) | NULL | Range maximum (informational) |
| `description` | TEXT | NULL | |
| `is_active` | BOOLEAN | NOT NULL, default true | |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(code, tenant_id, deleted_at)`

#### `allowance_types`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | |
| `name` | VARCHAR(100) | NOT NULL | "Responsibility Allowance", "Housing" |
| `code` | VARCHAR(20) | NOT NULL | "RESP", "HOUS" |
| `calculation_method` | `calculationmethod` enum | NOT NULL | `fixed`, `percentage_basic`, `percentage_gross` |
| `default_amount` | NUMERIC(12,2) | NOT NULL, >= 0 | Amount (GHS) or percentage (e.g. 15.00) |
| `is_taxable` | BOOLEAN | NOT NULL, default true | Included in PAYE taxable income? |
| `is_active` | BOOLEAN | NOT NULL, default true | |
| `description` | TEXT | NULL | |
| `deleted_at` | TIMESTAMPTZ | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(code, tenant_id, deleted_at)`

#### `deduction_types`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | |
| `name` | VARCHAR(100) | NOT NULL | "SSNIT Employee", "Staff Welfare" |
| `code` | VARCHAR(20) | NOT NULL | "SSNIT_EE", "WELFARE" |
| `calculation_method` | `calculationmethod` enum | NOT NULL | |
| `default_amount` | NUMERIC(12,2) | NOT NULL, >= 0 | |
| `is_statutory` | BOOLEAN | NOT NULL, default false | true for SSNIT, PAYE |
| `is_employer_portion` | BOOLEAN | NOT NULL, default false | true = not deducted from pay |
| `deduction_category` | `deductioncategory` enum | NOT NULL | Uses DB enum: `statutory`, `voluntary`, `loan`, `union`, `other` |
| `is_active` | BOOLEAN | NOT NULL, default true | |
| `description` | TEXT | NULL | |
| `deleted_at` | TIMESTAMPTZ | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(code, tenant_id, deleted_at)`

#### `tax_brackets`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | |
| `effective_year` | INTEGER | NOT NULL | 2024, 2025, 2026... |
| `band_number` | INTEGER | NOT NULL | 1, 2, 3... (ordering) |
| `lower_limit` | NUMERIC(12,2) | NOT NULL | Monthly lower limit (GHS) |
| `upper_limit` | NUMERIC(12,2) | NULL | NULL = no upper limit (top bracket) |
| `rate` | NUMERIC(5,4) | NOT NULL | Tax rate (0.175 = 17.5%) |
| `cumulative_tax` | NUMERIC(12,2) | NOT NULL | Tax from all lower bands combined |
| `is_active` | BOOLEAN | NOT NULL, default true | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(tenant_id, effective_year, band_number)`

#### `staff_salary_configs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | |
| `staff_id` | UUID | FK → staff, NOT NULL | |
| `salary_grade_id` | UUID | FK → salary_grades, NULL | Optional (manual entry allowed) |
| `basic_salary` | NUMERIC(12,2) | NOT NULL, >= 0 | Actual monthly basic |
| `effective_date` | DATE | NOT NULL | When config takes effect |
| `end_date` | DATE | NULL | NULL = current config |
| `payment_method` | `payrollpaymentmethod` enum | default 'bank_transfer' | Uses DB enum `payrollpaymentmethod`: bank_transfer, cash, mobile_money |
| `bank_name` | VARCHAR(100) | NULL | Override staff.bank_name |
| `bank_branch` | VARCHAR(100) | NULL | |
| `account_number` | VARCHAR(50) | NULL | |
| `mobile_money_number` | VARCHAR(20) | NULL | |
| `mobile_money_provider` | VARCHAR(20) | NULL | mtn, vodafone, airteltigo |
| `tin_number` | VARCHAR(20) | NULL | Override/capture TIN |
| `ssnit_number` | VARCHAR(20) | NULL | Override/capture SSNIT |
| `notes` | TEXT | NULL | |
| `is_active` | BOOLEAN | default true | |
| `deleted_at` | TIMESTAMPTZ | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(staff_id, tenant_id, effective_date, deleted_at)`
**Partial Index:** `(staff_id, tenant_id, is_active) WHERE is_active AND deleted_at IS NULL`

#### `staff_allowances`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `staff_salary_config_id` | UUID | FK → staff_salary_configs, CASCADE, NOT NULL | |
| `allowance_type_id` | UUID | FK → allowance_types, NOT NULL | |
| `amount` | NUMERIC(12,2) | NOT NULL, >= 0 | Override amount or rate |
| `calculation_method` | VARCHAR(20) | NULL | Override type default |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(staff_salary_config_id, allowance_type_id)`

#### `staff_deductions`

Same structure as `staff_allowances` but references `deduction_type_id` instead.

#### `payroll_runs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `school_id` | UUID | FK → schools, NULL | Chain support |
| `month` | INTEGER | NOT NULL, 1-12 | |
| `year` | INTEGER | NOT NULL | |
| `run_number` | INTEGER | NOT NULL, default 1 | 1=regular, 2+=supplementary |
| `status` | `payrollrunstatus` enum | NOT NULL | draft → processing → calculated → pending_approval → approved → paid |
| `run_type` | `payrollruntype` enum | NOT NULL, default 'regular' | Uses DB enum: `regular`, `supplementary`, `bonus`, `arrears` |
| `total_basic` | NUMERIC(14,2) | NOT NULL, default 0 | |
| `total_allowances` | NUMERIC(14,2) | NOT NULL, default 0 | |
| `total_gross` | NUMERIC(14,2) | NOT NULL, default 0 | |
| `total_paye` | NUMERIC(14,2) | NOT NULL, default 0 | |
| `total_ssnit_ee` | NUMERIC(14,2) | NOT NULL, default 0 | Employee SSNIT 5.5% |
| `total_ssnit_er` | NUMERIC(14,2) | NOT NULL, default 0 | Employer SSNIT 13% |
| `total_tier2_er` | NUMERIC(14,2) | NOT NULL, default 0 | Employer Tier 2 5% |
| `total_tier3` | NUMERIC(14,2) | NOT NULL, default 0 | Voluntary Tier 3 |
| `total_other_deductions` | NUMERIC(14,2) | NOT NULL, default 0 | |
| `total_net` | NUMERIC(14,2) | NOT NULL, default 0 | |
| `total_employer_cost` | NUMERIC(14,2) | NOT NULL, default 0 | Gross + employer contributions |
| `staff_count` | INTEGER | NOT NULL, default 0 | |
| `currency` | VARCHAR(3) | NOT NULL, default 'GHS' | |
| `notes` | TEXT | NULL | |
| `processed_by` | UUID | FK → users, NULL | |
| `processed_at` | TIMESTAMPTZ | NULL | |
| `approved_by` | UUID | FK → users, NULL | |
| `approved_at` | TIMESTAMPTZ | NULL | |
| `paid_at` | TIMESTAMPTZ | NULL | |
| `bank_file_url` | VARCHAR(500) | NULL | S3 URL |
| `bank_file_generated_at` | TIMESTAMPTZ | NULL | |
| `deleted_at` | TIMESTAMPTZ | NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** Use a COALESCE partial unique index (handles NULL school_id for single-school tenants):
```sql
CREATE UNIQUE INDEX uq_payroll_run ON payroll_runs(
    tenant_id, COALESCE(school_id, '00000000-0000-0000-0000-000000000000'::uuid),
    year, month, run_number
) WHERE deleted_at IS NULL;
```
**Index:** `(tenant_id, year, month, status)`

#### `payroll_items`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | |
| `tenant_id` | UUID | FK → tenants, NOT NULL | |
| `payroll_run_id` | UUID | FK → payroll_runs, CASCADE, NOT NULL | |
| `staff_id` | UUID | FK → staff, NOT NULL | |
| `staff_name` | VARCHAR(300) | NOT NULL | Snapshot (denormalized) |
| `staff_code` | VARCHAR(50) | NOT NULL | Snapshot |
| `department_name` | VARCHAR(100) | NULL | Snapshot |
| `salary_grade_name` | VARCHAR(100) | NULL | Snapshot |
| `basic_salary` | NUMERIC(12,2) | NOT NULL | |
| `total_allowances` | NUMERIC(12,2) | NOT NULL, default 0 | |
| `gross_salary` | NUMERIC(12,2) | NOT NULL | basic + allowances |
| `taxable_income` | NUMERIC(12,2) | NOT NULL | gross - non-taxable - SSNIT EE |
| `paye_tax` | NUMERIC(12,2) | NOT NULL, default 0 | |
| `ssnit_employee` | NUMERIC(12,2) | NOT NULL, default 0 | 5.5% of basic |
| `ssnit_employer` | NUMERIC(12,2) | NOT NULL, default 0 | 13% of basic |
| `tier2_employer` | NUMERIC(12,2) | NOT NULL, default 0 | 5% of basic |
| `tier3_employee` | NUMERIC(12,2) | NOT NULL, default 0 | Voluntary |
| `total_deductions` | NUMERIC(12,2) | NOT NULL, default 0 | |
| `net_salary` | NUMERIC(12,2) | NOT NULL | |
| `payment_method` | VARCHAR(20) | NULL | Snapshot |
| `bank_name` | VARCHAR(100) | NULL | Snapshot |
| `bank_branch` | VARCHAR(100) | NULL | Snapshot |
| `account_number` | VARCHAR(50) | NULL | Snapshot (full, masked in API) |
| `mobile_money_number` | VARCHAR(20) | NULL | Snapshot |
| `ssnit_number` | VARCHAR(20) | NULL | Snapshot |
| `tin_number` | VARCHAR(20) | NULL | Snapshot |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

**Unique:** `(payroll_run_id, staff_id)`
**Index:** `(tenant_id, staff_id)`

#### `payroll_item_earnings`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants, NOT NULL |
| `payroll_item_id` | UUID | FK → payroll_items, CASCADE, NOT NULL |
| `allowance_type_id` | UUID | FK → allowance_types, NULL |
| `name` | VARCHAR(100) | NOT NULL (snapshot) |
| `amount` | NUMERIC(12,2) | NOT NULL |
| `is_taxable` | BOOLEAN | NOT NULL, default true |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

#### `payroll_item_deductions`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants, NOT NULL |
| `payroll_item_id` | UUID | FK → payroll_items, CASCADE, NOT NULL |
| `deduction_type_id` | UUID | FK → deduction_types, NULL |
| `name` | VARCHAR(100) | NOT NULL (snapshot) |
| `amount` | NUMERIC(12,2) | NOT NULL |
| `is_statutory` | BOOLEAN | NOT NULL, default false |
| `is_employer_portion` | BOOLEAN | NOT NULL, default false |
| `deduction_category` | VARCHAR(30) | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

#### `payroll_approvals`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants, NOT NULL |
| `payroll_run_id` | UUID | FK → payroll_runs, CASCADE, NOT NULL |
| `approver_id` | UUID | FK → users, NOT NULL |
| `action` | `payrollapprovalaction` enum | NOT NULL — uses DB enum: `approve`, `reject`, `return_for_review` |
| `comments` | TEXT | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

#### `bank_file_configs`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants, NOT NULL |
| `school_id` | UUID | FK → schools, NULL |
| `bank_name` | VARCHAR(100) | NOT NULL |
| `file_format` | VARCHAR(20) | NOT NULL, default 'csv' |
| `delimiter` | VARCHAR(5) | default ',' |
| `column_mapping` | JSONB | NOT NULL |
| `header_template` | TEXT | NULL |
| `footer_template` | TEXT | NULL |
| `include_header_row` | BOOLEAN | default true |
| `date_format` | VARCHAR(20) | default 'YYYY-MM-DD' |
| `amount_format` | VARCHAR(20) | default 'decimal' |
| `encoding` | VARCHAR(20) | default 'utf-8' |
| `is_default` | BOOLEAN | default false |
| `deleted_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

**Unique:** `(tenant_id, bank_name, deleted_at)`

**`column_mapping` JSONB format:**
```json
[
  {"header": "Beneficiary Name", "source": "staff_name", "width": null},
  {"header": "Account Number", "source": "account_number", "width": null},
  {"header": "Amount", "source": "net_salary", "format": "decimal_2", "width": null},
  {"header": "Narration", "source": "template", "template": "{month_name} {year} Salary", "width": null}
]
```

#### `payroll_audit_log`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → tenants, NOT NULL |
| `school_id` | UUID | FK → schools, NULL |
| `entity_type` | VARCHAR(50) | NOT NULL |
| `entity_id` | UUID | NOT NULL |
| `action` | VARCHAR(20) | NOT NULL |
| `field_name` | VARCHAR(100) | NULL |
| `old_value` | TEXT | NULL |
| `new_value` | TEXT | NULL |
| `reason` | TEXT | NULL |
| `metadata` | JSONB | NULL | **Note:** `metadata` is reserved in SQLAlchemy. The Python model attribute must use a different name: `audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)` |
| `performed_by` | UUID | FK → users, NOT NULL |
| `performed_at` | TIMESTAMPTZ | NOT NULL, default CURRENT_TIMESTAMP |
| `ip_address` | VARCHAR(45) | NULL |
| `user_agent` | TEXT | NULL |

**RLS:** Append-only. **CRITICAL:** The GRANT statement must be `GRANT SELECT, INSERT ON payroll_audit_log TO sims_app_user` — do NOT include UPDATE or DELETE. The RLS policy uses separate SELECT (USING) and INSERT (WITH CHECK) policies, not the combined FOR ALL policy used by other tables. Add a dedicated test that attempts UPDATE and DELETE via the app_user engine and asserts they fail with a permission error.
**Index:** `(entity_type, entity_id)`, `(tenant_id, performed_at)`

---

## 4. Ghana Statutory Calculation Engine

### 4.1 PAYE Calculation

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_paye(monthly_taxable_income: Decimal, tax_brackets: list[dict]) -> Decimal:
    """
    Ghana PAYE (Pay As You Earn) graduated tax calculation.

    Args:
        monthly_taxable_income: Gross - non-taxable allowances - employee SSNIT
        tax_brackets: List of dicts ordered by band_number, each with:
            - lower_limit: Decimal
            - upper_limit: Decimal | None (None = top bracket)
            - rate: Decimal (e.g., 0.175 for 17.5%)

    Default 2024 GRA monthly brackets:
        Band 1: First GHS 490.00      @ 0%      → Tax: GHS 0.00
        Band 2: Next  GHS 110.00      @ 5%      → Tax: GHS 5.50
        Band 3: Next  GHS 130.00      @ 10%     → Tax: GHS 13.00
        Band 4: Next  GHS 3,166.67    @ 17.5%   → Tax: GHS 554.17
        Band 5: Next  GHS 16,000.00   @ 25%     → Tax: GHS 4,000.00
        Band 6: Next  GHS 30,393.33   @ 30%     → Tax: GHS 9,118.00
        Band 7: Above GHS 50,290.00   @ 35%

    Returns:
        Monthly PAYE tax amount, rounded to 2 decimal places.
    """
    if monthly_taxable_income <= 0:
        return Decimal("0.00")

    remaining = monthly_taxable_income
    total_tax = Decimal("0.00")

    for bracket in sorted(tax_brackets, key=lambda b: b["band_number"]):
        if remaining <= 0:
            break

        lower = bracket["lower_limit"]
        upper = bracket["upper_limit"]
        rate = bracket["rate"]

        if upper is not None:
            band_width = upper - lower
        else:
            band_width = remaining  # Top bracket — all remaining income

        taxable_in_band = min(remaining, band_width)
        tax_in_band = (taxable_in_band * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_tax += tax_in_band
        remaining -= taxable_in_band

    return total_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

**Validation rule:** Before calculating PAYE, the config service must validate bracket contiguity:
```python
def validate_bracket_contiguity(brackets: list[dict]) -> None:
    """Assert brackets are contiguous: brackets[i].lower_limit == brackets[i-1].upper_limit."""
    sorted_brackets = sorted(brackets, key=lambda b: b["band_number"])
    for i in range(1, len(sorted_brackets)):
        prev_upper = sorted_brackets[i - 1]["upper_limit"]
        curr_lower = sorted_brackets[i]["lower_limit"]
        if prev_upper is not None and curr_lower != prev_upper:
            raise ValueError(f"Tax brackets are not contiguous: band {i} lower ({curr_lower}) != band {i-1} upper ({prev_upper})")
```
This validation runs on bracket seed and bracket update endpoints. Add a unit test with non-contiguous brackets.

### 4.2 SSNIT Calculation

```python
def calculate_ssnit(basic_salary: Decimal, ssnit_ee_rate: Decimal = Decimal("5.5"),
                    ssnit_er_rate: Decimal = Decimal("13.0"), tier2_er_rate: Decimal = Decimal("5.0")) -> dict:
    """
    Calculate SSNIT contributions based on basic salary only.

    Ghana SSNIT rates:
        Employee: 5.5% of basic salary
        Employer: 13.0% of basic salary (11% SSNIT Tier 1 + 2% Tier 2 component)
        Employer Tier 2: 5.0% of basic salary (separate contribution)

    Returns:
        {
            "ssnit_employee": Decimal,  # Deducted from pay
            "ssnit_employer": Decimal,  # NOT deducted (employer cost)
            "tier2_employer": Decimal,  # NOT deducted (employer cost)
        }
    """
    # Rates are parameters (not hardcoded) so they can be read from statutory deduction_types
    # in the DB. The default values (5.5%, 13%, 5%) reflect current Ghana SSNIT rates.
    # When SSNIT changes rates, update the deduction_types in DB — no code deploy needed.
    ssnit_employee = (basic_salary * ssnit_ee_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ssnit_employer = (basic_salary * ssnit_er_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tier2_employer = (basic_salary * tier2_er_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "ssnit_employee": ssnit_employee,
        "ssnit_employer": ssnit_employer,
        "tier2_employer": tier2_employer,
    }
```

### 4.3 Full Payroll Calculation per Staff

```python
def calculate_staff_payroll(
    basic_salary: Decimal,
    staff_allowances: list[dict],      # [{allowance_type, amount, calculation_method, is_taxable}]
    staff_deductions: list[dict],      # [{deduction_type, amount, calculation_method, is_statutory, ...}]
    tax_brackets: list[dict],
) -> dict:
    """
    Complete payroll calculation for one staff member.

    Steps:
    1. Start with basic_salary
    2. Calculate allowances (two-pass for percentage_gross circular resolution)
    3. Compute gross = basic + total_allowances
    4. Calculate SSNIT on basic only
    5. Compute taxable_income = basic + taxable_allowances - ssnit_employee - tier3_employee
       (Both employee SSNIT and Tier 3 voluntary pension are tax-deductible per GRA rules)
    6. Calculate PAYE on taxable_income
    7. Sum other (non-statutory) deductions
    8. Compute net = gross - paye - ssnit_employee - tier3 - other_deductions
    9. Compute employer_cost = gross + ssnit_employer + tier2_employer
    """
    # Pass 1: fixed + percentage_basic allowances
    pass1_total = Decimal("0")
    pass1_taxable = Decimal("0")
    pass1_earnings = []

    for a in staff_allowances:
        method = a.get("calculation_method") or a["allowance_type"]["calculation_method"]
        is_taxable = a["allowance_type"]["is_taxable"]

        if method == "fixed":
            amount = a["amount"]
        elif method == "percentage_basic":
            amount = (basic_salary * a["amount"] / Decimal("100")).quantize(Decimal("0.01"))
        elif method == "percentage_gross":
            continue  # handled in pass 2
        else:
            amount = a["amount"]

        pass1_total += amount
        if is_taxable:
            pass1_taxable += amount
        pass1_earnings.append({"name": a["allowance_type"]["name"], "amount": amount, "is_taxable": is_taxable})

    # Pass 2: percentage_gross allowances (use basic + pass1 as gross proxy)
    gross_proxy = basic_salary + pass1_total
    for a in staff_allowances:
        method = a.get("calculation_method") or a["allowance_type"]["calculation_method"]
        if method != "percentage_gross":
            continue

        is_taxable = a["allowance_type"]["is_taxable"]
        amount = (gross_proxy * a["amount"] / Decimal("100")).quantize(Decimal("0.01"))
        pass1_total += amount
        if is_taxable:
            pass1_taxable += amount
        pass1_earnings.append({"name": a["allowance_type"]["name"], "amount": amount, "is_taxable": is_taxable})

    total_allowances = pass1_total
    gross_salary = basic_salary + total_allowances

    # SSNIT (on basic only)
    ssnit = calculate_ssnit(basic_salary)
    ssnit_employee = ssnit["ssnit_employee"]
    ssnit_employer = ssnit["ssnit_employer"]
    tier2_employer = ssnit["tier2_employer"]

    # Taxable income: basic + taxable_allowances - employee_ssnit (tax-deductible)
    # Note: Tier 3 is computed BEFORE taxable income since it's also tax-deductible
    # Tier 3 amount from staff_deductions (if present)
    tier3_employee = Decimal("0")
    for d in staff_deductions:
        if d["deduction_type"].get("code") == "TIER3":
            method = d.get("calculation_method") or d["deduction_type"]["calculation_method"]
            if method == "fixed":
                tier3_employee = d["amount"]
            elif method == "percentage_basic":
                tier3_employee = (basic_salary * d["amount"] / Decimal("100")).quantize(Decimal("0.01"))

    taxable_income = basic_salary + pass1_taxable - ssnit_employee - tier3_employee
    if taxable_income < 0:
        taxable_income = Decimal("0")

    # PAYE
    paye_tax = calculate_paye(taxable_income, tax_brackets)

    # Other deductions (non-statutory, non-employer)
    total_other = Decimal("0")
    tier3_employee = Decimal("0")
    deduction_items = []

    for d in staff_deductions:
        method = d.get("calculation_method") or d["deduction_type"]["calculation_method"]
        is_statutory = d["deduction_type"]["is_statutory"]
        is_employer = d["deduction_type"]["is_employer_portion"]
        category = d["deduction_type"]["deduction_category"]

        if method == "fixed":
            amount = d["amount"]
        elif method == "percentage_basic":
            amount = (basic_salary * d["amount"] / Decimal("100")).quantize(Decimal("0.01"))
        elif method == "percentage_gross":
            amount = (gross_salary * d["amount"] / Decimal("100")).quantize(Decimal("0.01"))
        else:
            amount = d["amount"]

        # Skip employer-portion deductions (they don't reduce take-home)
        if is_employer:
            deduction_items.append({"name": d["deduction_type"]["name"], "amount": amount,
                                    "is_statutory": is_statutory, "is_employer_portion": True, "category": category})
            continue

        # Tier 3 voluntary
        if d["deduction_type"]["code"] == "TIER3":
            tier3_employee = amount

        total_other += amount
        deduction_items.append({"name": d["deduction_type"]["name"], "amount": amount,
                                "is_statutory": is_statutory, "is_employer_portion": False, "category": category})

    # Totals
    total_deductions = paye_tax + ssnit_employee + tier3_employee + total_other
    net_salary = gross_salary - total_deductions
    employer_cost = gross_salary + ssnit_employer + tier2_employer

    return {
        "basic_salary": basic_salary,
        "total_allowances": total_allowances,
        "gross_salary": gross_salary,
        "taxable_income": taxable_income,
        "paye_tax": paye_tax,
        "ssnit_employee": ssnit_employee,
        "ssnit_employer": ssnit_employer,
        "tier2_employer": tier2_employer,
        "tier3_employee": tier3_employee,
        "total_other_deductions": total_other,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "employer_cost": employer_cost,
        "earnings": pass1_earnings,
        "deductions": deduction_items,
    }
```

### 4.4 Tax Bracket Seed Data (2024 GRA Rates)

```python
GHANA_TAX_BRACKETS_2024 = [
    {"band": 1, "lower": "0.00",      "upper": "490.00",     "rate": "0.0000", "cumulative": "0.00"},
    {"band": 2, "lower": "490.00",    "upper": "600.00",     "rate": "0.0500", "cumulative": "0.00"},
    {"band": 3, "lower": "600.00",    "upper": "730.00",     "rate": "0.1000", "cumulative": "5.50"},
    {"band": 4, "lower": "730.00",    "upper": "3896.67",    "rate": "0.1750", "cumulative": "18.50"},
    {"band": 5, "lower": "3896.67",   "upper": "19896.67",   "rate": "0.2500", "cumulative": "572.67"},
    {"band": 6, "lower": "19896.67",  "upper": "50290.00",   "rate": "0.3000", "cumulative": "4572.67"},
    {"band": 7, "lower": "50290.00",  "upper": None,         "rate": "0.3500", "cumulative": "13690.67"},
]
```

---

## 5. API Endpoints

### 5.1 Configuration (Sub-Sprint 4A) — 22 endpoints

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/salary-grades` | List salary grades | `payroll.read` |
| POST | `/payroll/salary-grades` | Create salary grade | `payroll.configure` |
| PUT | `/payroll/salary-grades/{id}` | Update salary grade | `payroll.configure` |
| DELETE | `/payroll/salary-grades/{id}` | Soft-delete salary grade | `payroll.configure` |
| GET | `/payroll/allowance-types` | List allowance types | `payroll.read` |
| POST | `/payroll/allowance-types` | Create allowance type | `payroll.configure` |
| PUT | `/payroll/allowance-types/{id}` | Update allowance type | `payroll.configure` |
| DELETE | `/payroll/allowance-types/{id}` | Soft-delete | `payroll.configure` |
| GET | `/payroll/deduction-types` | List deduction types | `payroll.read` |
| POST | `/payroll/deduction-types` | Create deduction type | `payroll.configure` |
| PUT | `/payroll/deduction-types/{id}` | Update deduction type | `payroll.configure` |
| DELETE | `/payroll/deduction-types/{id}` | Soft-delete | `payroll.configure` |
| GET | `/payroll/tax-brackets` | List brackets by year | `payroll.read` |
| POST | `/payroll/tax-brackets/seed` | Seed current GRA brackets | `payroll.configure` |
| PUT | `/payroll/tax-brackets/{id}` | Update a bracket | `payroll.configure` |
| GET | `/payroll/bank-file-configs` | List bank configs | `payroll.read` |
| POST | `/payroll/bank-file-configs` | Create bank config | `payroll.configure` |
| PUT | `/payroll/bank-file-configs/{id}` | Update bank config | `payroll.configure` |
| DELETE | `/payroll/bank-file-configs/{id}` | Soft-delete | `payroll.configure` |
| GET | `/payroll/staff/{staff_id}/salary` | Get current salary config | `payroll.read` |
| POST | `/payroll/staff/{staff_id}/salary` | Create/update salary config | `payroll.manage` |
| POST | `/payroll/staff/salary/bulk` | Bulk assign salary grade | `payroll.manage` |

### 5.2 Processing (Sub-Sprint 4B) — 14 endpoints

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/runs` | List payroll runs | `payroll.read` |
| POST | `/payroll/runs` | Create run (draft) | `payroll.process` |
| GET | `/payroll/runs/{id}` | Get run detail | `payroll.read` |
| POST | `/payroll/runs/{id}/calculate` | Trigger Celery calculation | `payroll.process` |
| POST | `/payroll/runs/{id}/submit` | Submit for approval | `payroll.process` |
| POST | `/payroll/runs/{id}/approve` | Approve run | `payroll.approve` |
| POST | `/payroll/runs/{id}/reject` | Reject run | `payroll.approve` |
| POST | `/payroll/runs/{id}/mark-paid` | Mark as paid | `payroll.approve` |
| DELETE | `/payroll/runs/{id}` | Cancel draft run | `payroll.process` |
| GET | `/payroll/runs/{id}/items` | List items for a run | `payroll.read` |
| GET | `/payroll/runs/{id}/items/{item_id}` | Get single item detail | `payroll.read` |
| PUT | `/payroll/runs/{id}/items/{item_id}` | Manual adjustment | `payroll.process` |
| GET | `/payroll/runs/{id}/summary` | Run summary stats | `payroll.read` |
| GET | `/payroll/staff/{staff_id}/salary/history` | Salary config history | `payroll.read` |

### 5.3 Output (Sub-Sprint 4C) — 12 endpoints

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| GET | `/payroll/runs/{id}/payslips/{staff_id}` | Download individual payslip PDF | `payroll.read` |
| POST | `/payroll/runs/{id}/payslips/bulk` | Bulk generate (Celery) | `payroll.process` |
| GET | `/payroll/runs/{id}/bank-file` | Generate bank file (all banks) | `payroll.process` |
| GET | `/payroll/runs/{id}/bank-file/{bank_name}` | Bank file for specific bank | `payroll.process` |
| GET | `/payroll/reports/monthly-summary` | Monthly summary report | `payroll.read` |
| GET | `/payroll/reports/ssnit-returns` | SSNIT contribution report | `payroll.read` |
| POST | `/payroll/reports/ssnit-returns/export` | Export SSNIT as Excel | `payroll.read` |
| GET | `/payroll/reports/paye-returns` | PAYE tax report | `payroll.read` |
| POST | `/payroll/reports/paye-returns/export` | Export PAYE as Excel | `payroll.read` |
| GET | `/payroll/reports/department-summary` | Cost by department | `payroll.read` |
| GET | `/payroll/reports/year-to-date/{staff_id}` | Staff YTD summary | `payroll.read` |
| GET | `/payroll/audit-log` | Payroll audit trail | `payroll.audit` |

---

## 6. Payslip PDF Template

**File:** `backend/app/templates/reports/payslip.html`
**Format:** A5 landscape (two fit on A4 when printing)
**Engine:** WeasyPrint + Jinja2

```
┌───────────────────────────────────────────────────────────────┐
│  [SCHOOL LOGO]  SCHOOL NAME                                   │
│                 PAYSLIP - {month_name} {year}                  │
│───────────────────────────────────────────────────────────────│
│  Employee: {staff_name}              Staff ID: {staff_code}   │
│  Department: {department_name}       Grade: {grade_name}      │
│  TIN: {tin_number}                   SSNIT: {ssnit_number}    │
│  Bank: {bank_name} - {bank_branch}   A/C: ****{last4}        │
│───────────────────────────────────────────────────────────────│
│  EARNINGS                       │  DEDUCTIONS                  │
│  ───────────────────             │  ──────────────               │
│  Basic Salary    GHS {basic}    │  SSNIT (5.5%)   GHS {ssnit} │
│  {allowance_1}   GHS {amt_1}   │  PAYE Tax       GHS {paye}  │
│  {allowance_2}   GHS {amt_2}   │  {deduction_1}  GHS {ded_1} │
│  ...                            │  ...                          │
│  ───────────────────             │  ──────────────               │
│  TOTAL EARNINGS  GHS {gross}    │  TOTAL DEDUCT.  GHS {total} │
│───────────────────────────────────────────────────────────────│
│  NET SALARY: GHS {net_salary}                                  │
│───────────────────────────────────────────────────────────────│
│  EMPLOYER CONTRIBUTIONS (not deducted from salary):            │
│  SSNIT Employer (13%): GHS {er_ssnit}  │  Tier 2: GHS {tier2}│
│───────────────────────────────────────────────────────────────│
│  YTD Gross: GHS {ytd_gross}   YTD Tax: GHS {ytd_tax}         │
│  YTD SSNIT: GHS {ytd_ssnit}  YTD Net: GHS {ytd_net}         │
│───────────────────────────────────────────────────────────────│
│  Generated: {date} {time}  │  Computer-generated document.    │
│  Pay Period: {month} {year}│                                   │
└───────────────────────────────────────────────────────────────┘
```

**Key rules:**
- Account numbers masked: show last 4 digits only (`****5678`)
- YTD totals: sum all prior payroll_items for same staff in same calendar year
- School logo and primary color from tenant branding
- Stored in S3: `tenants/{tenant_id}/payroll/{year}/{month}/payslips/{staff_code}.pdf`

---

## 7. Bank File Generation

### Preset Formats

**GCB Bank (CSV):**
```
Beneficiary Name,Account Number,Bank Code,Branch Code,Amount,Narration
"John Doe","1234567890","040","001","4172.25","March 2026 Salary"
```

**Ecobank (CSV):**
```
Account Number,Beneficiary Name,Amount,Currency,Reference
1234567890,John Doe,4172.25,GHS,MAR2026-SAL-STF-2026-001
```

**Stanbic Bank (pipe-delimited):**
```
DR|SCHOOL_ACCOUNT|TOTAL_AMOUNT|GHS|SALARY MARCH 2026
CR|ACCT_NUMBER|AMOUNT|GHS|BENEFICIARY_NAME|SALARY
```

**Mobile Money (CSV per provider):**
```
Phone Number,Amount,Reference,Provider
0241234567,4172.25,MAR2026-SAL,MTN
```

**S3 storage:** `tenants/{tenant_id}/payroll/{year}/{month}/bank_file_{bank_name}_{timestamp}.csv`

---

## 8. Celery Tasks

### `process_payroll_run`

```python
@celery_app.task(name="process_payroll_run", bind=True, max_retries=1)
def process_payroll_run(self, run_id: str, tenant_id: str):
    """
    Background task to calculate all payroll items for a run.

    NOTE: Follow the existing Celery session pattern from backend/app/tasks/
    (e.g., tasks/notifications.py, tasks/offer_expiry.py). The project uses
    sync sessions in Celery tasks via get_sync_session() or similar utility.
    Check celery_app.py for the established pattern before implementing.

    Steps:
    1. Create sync session (using project's established Celery pattern), set tenant context
    2. Lock payroll_run row with FOR UPDATE
    3. Set status = 'processing'
    4. Delete any existing payroll_items (for recalculation)
    5. Fetch all active staff with salary configs (effective_date <= last day of month)
    6. Fetch tax brackets for the year
    7. For each staff:
       a. Skip if no active salary config
       b. Calculate allowances, gross, SSNIT, PAYE, other deductions, net
       c. Create PayrollItem + earnings + deductions
    8. Sum all items into payroll_run totals
    9. Set status = 'calculated'
    10. Commit

    On failure: set status = 'draft', log error to payroll_audit_log.
    Idempotent: deletes existing items before recalculating.
    """
```

### `generate_bulk_payslips`

```python
@celery_app.task(name="generate_bulk_payslips", bind=True)
def generate_bulk_payslips(self, run_id: str, tenant_id: str):
    """
    Generate PDF payslips for all staff in a payroll run.

    Processes in chunks of 50 to manage memory.
    Each payslip uploaded to S3 individually.
    Progress tracked via Redis key: payroll:payslips:{run_id}:progress
    """
```

---

## 9. Security Considerations

1. **Separation of duties:** `processed_by != approver_id` enforced at endpoint level
2. **Account number masking:** API responses show `****{last4}` only; full numbers in bank files only
3. **Presigned URLs:** Payslip PDFs and bank files accessed via 5-minute presigned S3 URLs
4. **Audit trail:** Every mutation logged to `payroll_audit_log` (append-only, no UPDATE/DELETE)
5. **Rate limiting:** Calculation trigger: 5/min, payslip download: 5/min, bank file: 5/min
6. **Feature gating:** Every endpoint checks `hr_payroll` via `require_feature` dependency from `app.api.deps`
7. **Sensitive data:** TIN, SSNIT, account numbers never in list responses; only in detail views
8. **RLS:** All 14 tables tenant-isolated; `payroll_audit_log` is INSERT+SELECT only for app user
9. **Bank file config validation:** `column_mapping[].source` must be validated against an allowed whitelist (`staff_name`, `staff_code`, `net_salary`, `account_number`, `bank_name`, `bank_branch`, `mobile_money_number`, `ssnit_number`, `department_name`, `template`). Reject unknown source fields to prevent data exfiltration. `header_template`/`footer_template` must use `string.Template.safe_substitute()` (NOT `str.format()`) and reject patterns containing `{%`, `{{`, `__`, or `{0`. CSV cell values starting with `=`, `+`, `-`, `@` must be escaped with a leading `'` to prevent formula injection.

---

## 10. Tests

| File | Count | Focus |
|------|-------|-------|
| `test_payroll_calculation.py` | 13 | PAYE bands (zero, single band, multi-band, top), SSNIT, Tier 2, fixed/% allowances, circular gross resolution, taxable income, full net salary |
| `test_payroll_config.py` | 7 | Salary grade CRUD, allowance/deduction type creation with validation, tax bracket seed, duplicate code rejection, soft delete |
| `test_staff_salary.py` | 6 | Salary config create, config with allowances/deductions, effective date ordering, bulk assign, salary history, bank details override |
| `test_payroll_processing.py` | 13 | Create run, calculate (E2E with 5 staff), no salary config handling, terminated staff skipped, manual adjustment, submit, approval separation of duties, approve, reject, mark paid, supplementary run, cancel draft, immutable approved run |
| `test_payslip_generation.py` | 4 | PDF generation, account masking, YTD totals, school branding |
| `test_bank_file_generation.py` | 5 | GCB format, Ecobank format, MoMo file, S3 upload, custom config |
| `test_payroll_rls.py` | 6 | Run isolation, salary config isolation, audit log append-only (no delete, no update), cross-tenant invisible |
| `test_payroll_feature_flag.py` | 3 | Blocked without addon, accessible with addon, accessible Enterprise tier |

---

## 11. Acceptance Criteria

### Sub-Sprint 4A
- [ ] Salary grades can be created/updated/deleted
- [ ] Allowance types support 3 calculation methods
- [ ] Deduction types distinguish statutory/voluntary/loan/union
- [ ] Tax brackets seeded with 2024 GRA rates per tenant
- [ ] Bank file configs seeded with 5 Ghana bank presets
- [ ] Staff salary configs can be created with allowances and deductions
- [ ] Bulk salary grade assignment works for up to 200 staff
- [ ] Settings pages render correctly with CRUD operations
- [ ] All configuration tests pass

### Sub-Sprint 4B
- [ ] Payroll runs can be created (draft) for any month/year
- [ ] Calculation correctly computes PAYE using graduated brackets
- [ ] SSNIT calculated at 5.5% (employee) and 13%/5% (employer) on basic only
- [ ] Percentage-of-gross circular dependency resolved correctly
- [ ] Staff without salary configs are skipped (reported as "unconfigured")
- [ ] Terminated staff are excluded from calculation
- [ ] Manual adjustments work on calculated (not yet approved) runs
- [ ] Status machine enforced: only valid transitions allowed
- [ ] Separation of duties: processor cannot approve own run
- [ ] All processing tests pass

### Sub-Sprint 4C
- [ ] Payslip PDFs generate with correct layout and masking
- [ ] YTD totals sum correctly across prior months
- [ ] Bank files generate in correct format per bank config
- [ ] SSNIT returns report shows all employee/employer contributions
- [ ] PAYE returns report shows taxable income and tax per staff
- [ ] Department summary shows payroll cost breakdown
- [ ] Excel export works for SSNIT and PAYE returns
- [ ] All output tests pass

### Sub-Sprint 4D
- [ ] Audit log records all payroll mutations
- [ ] Audit log is append-only (no update/delete at DB level)
- [ ] E2E test passes: config → salary → run → calculate → approve → payslip → bank file
- [ ] Performance: 300-staff payroll run completes in < 30 seconds
- [ ] All payroll feature flag tests pass
- [ ] TENANT_SCOPED_TABLES updated (+14 = 144 total)

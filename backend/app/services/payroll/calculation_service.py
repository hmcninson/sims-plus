"""
SIMS Plus - Payroll Calculation Engine

Pure-function calculation engine for Ghana payroll: PAYE graduated tax,
SSNIT contributions (Tier 1/2/3), allowance resolution, and full
staff payroll computation. All functions are stateless — they take
data as parameters and return results with no database access.

All monetary arithmetic uses Decimal with ROUND_HALF_UP to 2dp at
each step to prevent floating-point drift in tax calculations.
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_DP = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def _q(value: Decimal) -> Decimal:
    """Quantize to 2 decimal places with ROUND_HALF_UP."""
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def validate_bracket_contiguity(brackets: list[dict]) -> None:
    """
    Assert tax brackets are contiguous: brackets[i].lower_limit ==
    brackets[i-1].upper_limit.

    This prevents gaps or overlaps in the graduated tax table that would
    cause incorrect PAYE calculations. Called before PAYE calculation and
    during bracket seed/update.

    Raises:
        ValueError: If any two adjacent brackets have a gap or overlap.
    """
    sorted_brackets = sorted(brackets, key=lambda b: b["band_number"])
    for i in range(1, len(sorted_brackets)):
        prev_upper = sorted_brackets[i - 1].get("upper_limit")
        curr_lower = sorted_brackets[i].get("lower_limit")
        if prev_upper is not None and curr_lower is not None:
            if Decimal(str(curr_lower)) != Decimal(str(prev_upper)):
                raise ValueError(
                    f"Tax brackets are not contiguous: band "
                    f"{sorted_brackets[i]['band_number']} lower ({curr_lower}) "
                    f"!= band {sorted_brackets[i - 1]['band_number']} upper "
                    f"({prev_upper})"
                )


def calculate_paye(
    monthly_taxable_income: Decimal,
    tax_brackets: list[dict],
) -> Decimal:
    """
    Ghana PAYE (Pay As You Earn) graduated tax calculation.

    Walks the bracket table from lowest to highest band, taxing each
    slice of income at the corresponding marginal rate.

    GRA 2024 monthly brackets:
        Band 1: First GHS 490.00      @  0%
        Band 2: Next  GHS 110.00      @  5%
        Band 3: Next  GHS 130.00      @ 10%
        Band 4: Next  GHS 3,166.67    @ 17.5%
        Band 5: Next  GHS 16,000.00   @ 25%
        Band 6: Next  GHS 30,393.33   @ 30%
        Band 7: Above GHS 50,290.00   @ 35%

    Args:
        monthly_taxable_income: Gross - non-taxable allowances - SSNIT EE
            - Tier 3 voluntary.
        tax_brackets: List of dicts ordered by band_number, each with
            lower_limit, upper_limit (None for top band), rate.

    Returns:
        Monthly PAYE tax amount, rounded to 2dp.
    """
    if monthly_taxable_income <= ZERO:
        return ZERO

    remaining = monthly_taxable_income
    total_tax = ZERO

    for bracket in sorted(tax_brackets, key=lambda b: b["band_number"]):
        if remaining <= ZERO:
            break

        lower = Decimal(str(bracket["lower_limit"]))
        upper = (
            Decimal(str(bracket["upper_limit"]))
            if bracket["upper_limit"] is not None
            else None
        )
        rate = Decimal(str(bracket["rate"]))

        if upper is not None:
            band_width = upper - lower
        else:
            # Top bracket — all remaining income falls here
            band_width = remaining

        taxable_in_band = min(remaining, band_width)
        # Round each band's tax contribution individually to avoid
        # accumulated rounding errors across 7 brackets
        tax_in_band = _q(taxable_in_band * rate)
        total_tax += tax_in_band
        remaining -= taxable_in_band

    return _q(total_tax)


def calculate_ssnit(
    basic_salary: Decimal,
    ssnit_ee_rate: Decimal = Decimal("5.5"),
    ssnit_er_rate: Decimal = Decimal("13.0"),
    tier2_er_rate: Decimal = Decimal("5.0"),
) -> dict:
    """
    Calculate SSNIT contributions based on basic salary only.

    Ghana SSNIT rates (current defaults — configurable via DB):
        Employee:       5.5% of basic salary (deducted from pay)
        Employer:      13.0% of basic salary (employer cost, not deducted)
        Employer Tier 2: 5.0% of basic salary (employer cost, not deducted)

    Args:
        basic_salary: Monthly basic salary amount.
        ssnit_ee_rate: Employee contribution rate as percentage (e.g., 5.5).
        ssnit_er_rate: Employer Tier 1 rate as percentage (e.g., 13.0).
        tier2_er_rate: Employer Tier 2 rate as percentage (e.g., 5.0).

    Returns:
        Dict with ssnit_employee, ssnit_employer, tier2_employer — all Decimal.
    """
    ssnit_employee = _q(basic_salary * ssnit_ee_rate / HUNDRED)
    ssnit_employer = _q(basic_salary * ssnit_er_rate / HUNDRED)
    tier2_employer = _q(basic_salary * tier2_er_rate / HUNDRED)

    return {
        "ssnit_employee": ssnit_employee,
        "ssnit_employer": ssnit_employer,
        "tier2_employer": tier2_employer,
    }


def calculate_staff_payroll(
    basic_salary: Decimal,
    staff_allowances: list[dict],
    staff_deductions: list[dict],
    tax_brackets: list[dict],
) -> dict:
    """
    Complete payroll calculation for one staff member.

    Two-pass allowance resolution handles the percentage_gross circular
    dependency: pass 1 computes fixed + percentage_basic allowances, then
    pass 2 uses (basic + pass1_total) as a gross proxy for percentage_gross.

    Calculation order per GRA rules:
        1. Allowances (two-pass)
        2. Gross = basic + total_allowances
        3. SSNIT on basic salary only
        4. Tier 3 voluntary (tax-deductible per GRA)
        5. Taxable income = basic + taxable_allowances - SSNIT_EE - Tier 3
        6. PAYE on taxable income
        7. Other deductions (non-employer-portion)
        8. Net = gross - PAYE - SSNIT_EE - Tier 3 - other deductions
        9. Employer cost = gross + SSNIT_ER + Tier 2_ER

    Args:
        basic_salary: Monthly basic salary.
        staff_allowances: List of dicts, each with:
            - amount: Decimal (fixed GHS or percentage value)
            - calculation_method: Optional override
            - allowance_type: dict with name, code, calculation_method, is_taxable
        staff_deductions: List of dicts, each with:
            - amount: Decimal
            - calculation_method: Optional override
            - deduction_type: dict with name, code, calculation_method,
              is_statutory, is_employer_portion, deduction_category
        tax_brackets: List of bracket dicts for PAYE calculation.

    Returns:
        Full breakdown dict with all amounts, earnings list, and deductions list.
    """
    # ---------------------------------------------------------------
    # Pass 1: fixed + percentage_basic allowances
    # ---------------------------------------------------------------
    pass1_total = ZERO
    pass1_taxable = ZERO
    earnings: list[dict] = []

    for a in staff_allowances:
        method = (
            a.get("calculation_method")
            or a["allowance_type"]["calculation_method"]
        )
        is_taxable = a["allowance_type"]["is_taxable"]
        at_id = a.get("allowance_type_id") or a["allowance_type"].get("id")

        if method == "percentage_gross":
            continue  # Deferred to pass 2

        if method == "percentage_basic":
            amount = _q(basic_salary * a["amount"] / HUNDRED)
        else:
            # "fixed" or unknown — treat as fixed amount
            amount = _q(a["amount"])

        pass1_total += amount
        if is_taxable:
            pass1_taxable += amount
        earnings.append({
            "name": a["allowance_type"]["name"],
            "amount": amount,
            "is_taxable": is_taxable,
            "allowance_type_id": at_id,
        })

    # ---------------------------------------------------------------
    # Pass 2: percentage_gross allowances (use basic + pass1 as proxy)
    # ---------------------------------------------------------------
    gross_proxy = basic_salary + pass1_total

    for a in staff_allowances:
        method = (
            a.get("calculation_method")
            or a["allowance_type"]["calculation_method"]
        )
        if method != "percentage_gross":
            continue

        is_taxable = a["allowance_type"]["is_taxable"]
        at_id = a.get("allowance_type_id") or a["allowance_type"].get("id")
        amount = _q(gross_proxy * a["amount"] / HUNDRED)

        pass1_total += amount
        if is_taxable:
            pass1_taxable += amount
        earnings.append({
            "name": a["allowance_type"]["name"],
            "amount": amount,
            "is_taxable": is_taxable,
            "allowance_type_id": at_id,
        })

    total_allowances = pass1_total
    gross_salary = basic_salary + total_allowances

    # ---------------------------------------------------------------
    # SSNIT (calculated on basic salary only, per Ghana SSNIT Act)
    # ---------------------------------------------------------------
    ssnit = calculate_ssnit(basic_salary)
    ssnit_employee = ssnit["ssnit_employee"]
    ssnit_employer = ssnit["ssnit_employer"]
    tier2_employer = ssnit["tier2_employer"]

    # ---------------------------------------------------------------
    # Tier 3 voluntary (tax-deductible, must be computed before PAYE)
    # ---------------------------------------------------------------
    tier3_employee = ZERO
    for d in staff_deductions:
        if d["deduction_type"].get("code") == "TIER3":
            method = (
                d.get("calculation_method")
                or d["deduction_type"]["calculation_method"]
            )
            if method == "percentage_basic":
                tier3_employee = _q(basic_salary * d["amount"] / HUNDRED)
            else:
                tier3_employee = _q(d["amount"])

    # ---------------------------------------------------------------
    # Taxable income (per GRA: basic + taxable allowances
    #                  - employee SSNIT - Tier 3 voluntary)
    # ---------------------------------------------------------------
    taxable_income = basic_salary + pass1_taxable - ssnit_employee - tier3_employee
    if taxable_income < ZERO:
        taxable_income = ZERO

    # ---------------------------------------------------------------
    # PAYE
    # ---------------------------------------------------------------
    paye_tax = calculate_paye(taxable_income, tax_brackets)

    # ---------------------------------------------------------------
    # Other deductions (non-employer-portion)
    # ---------------------------------------------------------------
    total_other = ZERO
    # Reset tier3 for the deduction pass — it will be recalculated from
    # the full deduction list to produce the deduction line items
    tier3_employee = ZERO
    deduction_items: list[dict] = []

    for d in staff_deductions:
        method = (
            d.get("calculation_method")
            or d["deduction_type"]["calculation_method"]
        )
        is_statutory = d["deduction_type"]["is_statutory"]
        is_employer = d["deduction_type"]["is_employer_portion"]
        category = d["deduction_type"]["deduction_category"]
        dt_id = d.get("deduction_type_id") or d["deduction_type"].get("id")

        if method == "percentage_basic":
            amount = _q(basic_salary * d["amount"] / HUNDRED)
        elif method == "percentage_gross":
            amount = _q(gross_salary * d["amount"] / HUNDRED)
        else:
            amount = _q(d["amount"])

        # Employer-portion deductions do not reduce take-home pay
        if is_employer:
            deduction_items.append({
                "name": d["deduction_type"]["name"],
                "amount": amount,
                "is_statutory": is_statutory,
                "is_employer_portion": True,
                "category": category,
                "deduction_type_id": dt_id,
            })
            continue

        # Track Tier 3 voluntary separately
        if d["deduction_type"].get("code") == "TIER3":
            tier3_employee = amount

        total_other += amount
        deduction_items.append({
            "name": d["deduction_type"]["name"],
            "amount": amount,
            "is_statutory": is_statutory,
            "is_employer_portion": False,
            "category": category,
            "deduction_type_id": dt_id,
        })

    # ---------------------------------------------------------------
    # Final totals
    # ---------------------------------------------------------------
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
        "earnings": earnings,
        "deductions": deduction_items,
    }

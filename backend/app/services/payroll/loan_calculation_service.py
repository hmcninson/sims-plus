"""
SIMS Plus - Loan Calculation Engine

Pure-function calculation engine for staff loan installment schedules.
Supports flat rate and reducing balance (EMI) interest methods.

All monetary arithmetic uses Decimal with ROUND_HALF_UP to 2dp at each
step to prevent floating-point drift. The last installment absorbs any
rounding difference to ensure sum integrity.

These functions have NO database access — they take parameters and return
results, making them easily testable.
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_DP = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
TWELVE = Decimal("12")


def _q(value: Decimal) -> Decimal:
    """Quantize to 2 decimal places with ROUND_HALF_UP."""
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def calculate_flat_rate_loan(
    principal: Decimal,
    annual_rate: Decimal,
    tenure_months: int,
) -> dict:
    """
    Flat rate interest calculation.

    Interest is calculated on the ORIGINAL principal for the full term,
    regardless of how much principal has been repaid. This is the common
    method used in Ghana for staff salary advances and welfare loans.

    Formula:
        total_interest = principal * (annual_rate / 100) * (tenure_months / 12)
        monthly_installment = (principal + total_interest) / tenure_months

    The last installment absorbs any rounding difference so that:
        - sum(installment_amounts) == total_repayable (exact)
        - sum(principal_components) == principal (exact)
        - last closing_balance == 0.00

    Args:
        principal: Loan amount in GHS (must be > 0).
        annual_rate: Annual interest rate as percentage (e.g. 10.00 = 10%).
        tenure_months: Number of monthly installments (must be > 0).

    Returns:
        Dict with total_interest, total_repayable, monthly_installment,
        and installments list.
    """
    rate = annual_rate / HUNDRED
    total_interest = _q(principal * rate * Decimal(tenure_months) / TWELVE)
    total_repayable = principal + total_interest

    monthly = _q(total_repayable / Decimal(tenure_months))
    monthly_principal = _q(principal / Decimal(tenure_months))
    monthly_interest = _q(total_interest / Decimal(tenure_months))

    installments: list[dict] = []
    remaining = total_repayable
    running_principal_sum = ZERO
    running_interest_sum = ZERO

    for i in range(1, tenure_months + 1):
        opening = remaining

        if i == tenure_months:
            # Last installment absorbs rounding to ensure exact totals
            inst_amount = remaining
            p_comp = principal - running_principal_sum
            i_comp = inst_amount - p_comp
        else:
            inst_amount = monthly
            p_comp = monthly_principal
            i_comp = monthly_interest

        remaining = _q(opening - inst_amount)
        running_principal_sum += p_comp
        running_interest_sum += i_comp

        installments.append({
            "installment_number": i,
            "principal_component": p_comp,
            "interest_component": i_comp,
            "installment_amount": inst_amount,
            "opening_balance": opening,
            "closing_balance": max(remaining, ZERO),
        })

    # Sum integrity assertions — must hold exactly
    assert sum(i["principal_component"] for i in installments) == principal, (
        f"Principal sum mismatch: "
        f"{sum(i['principal_component'] for i in installments)} != {principal}"
    )
    assert sum(i["installment_amount"] for i in installments) == total_repayable, (
        f"Repayable sum mismatch: "
        f"{sum(i['installment_amount'] for i in installments)} != {total_repayable}"
    )
    assert installments[-1]["closing_balance"] == ZERO, (
        f"Final balance not zero: {installments[-1]['closing_balance']}"
    )

    return {
        "total_interest": total_interest,
        "total_repayable": total_repayable,
        "monthly_installment": monthly,
        "installments": installments,
    }


def calculate_reducing_balance_loan(
    principal: Decimal,
    annual_rate: Decimal,
    tenure_months: int,
) -> dict:
    """
    Reducing balance (EMI) interest calculation.

    Interest is recalculated each month on the outstanding principal.
    Uses the EMI (Equated Monthly Installment) formula:

        EMI = P * r * (1+r)^n / ((1+r)^n - 1)

    where r = monthly rate, n = tenure months. If the annual rate is 0%,
    falls back to simple equal principal division.

    The last installment absorbs rounding to ensure exact totals.

    Args:
        principal: Loan amount in GHS (must be > 0).
        annual_rate: Annual interest rate as percentage (e.g. 10.00 = 10%).
        tenure_months: Number of monthly installments (must be > 0).

    Returns:
        Dict with total_interest, total_repayable, monthly_installment,
        and installments list.
    """
    if annual_rate == ZERO:
        # Zero interest — equal principal installments (salary advance)
        monthly = _q(principal / Decimal(tenure_months))
        installments: list[dict] = []
        remaining = principal

        for i in range(1, tenure_months + 1):
            opening = remaining
            inst = remaining if i == tenure_months else monthly
            remaining = _q(opening - inst)

            installments.append({
                "installment_number": i,
                "principal_component": inst,
                "interest_component": ZERO,
                "installment_amount": inst,
                "opening_balance": opening,
                "closing_balance": max(remaining, ZERO),
            })

        return {
            "total_interest": ZERO,
            "total_repayable": principal,
            "monthly_installment": monthly,
            "installments": installments,
        }

    # Standard EMI calculation with non-zero interest
    monthly_rate = annual_rate / Decimal("1200")
    n = int(tenure_months)
    power = (1 + monthly_rate) ** n
    emi = _q(principal * monthly_rate * power / (power - 1))

    installments = []
    remaining_principal = principal
    total_interest = ZERO

    for i in range(1, tenure_months + 1):
        opening = remaining_principal
        # Interest on remaining principal for this month
        interest_comp = _q(remaining_principal * monthly_rate)

        if i == tenure_months:
            # Last installment: pay off all remaining principal
            principal_comp = remaining_principal
            inst_amount = principal_comp + interest_comp
        else:
            inst_amount = emi
            principal_comp = _q(inst_amount - interest_comp)

        remaining_principal = _q(opening - principal_comp)
        total_interest += interest_comp

        installments.append({
            "installment_number": i,
            "principal_component": principal_comp,
            "interest_component": interest_comp,
            "installment_amount": inst_amount,
            "opening_balance": opening,
            "closing_balance": max(remaining_principal, ZERO),
        })

    total_repayable = principal + total_interest

    # Sum integrity assertions — must hold exactly after last-installment adjustment
    total_principal = sum(i["principal_component"] for i in installments)
    assert total_principal == principal, (
        f"Principal sum mismatch: {total_principal} != {principal}"
    )
    assert installments[-1]["closing_balance"] == ZERO, (
        f"Final balance not zero: {installments[-1]['closing_balance']}"
    )

    return {
        "total_interest": total_interest,
        "total_repayable": total_repayable,
        "monthly_installment": emi,
        "installments": installments,
    }

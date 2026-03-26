"""
Tests for loan calculation engine (Phase 5 — pure functions).

Flat rate and reducing balance interest calculations. No database needed.
Uses Decimal inputs; verifies Decimal outputs with 2dp precision.
"""

import pytest
from decimal import Decimal

from app.services.payroll.loan_calculation_service import (
    calculate_flat_rate_loan,
    calculate_reducing_balance_loan,
)

ZERO = Decimal("0.00")


# --- Flat Rate Tests ---


def test_flat_rate_basic():
    """GHS 5000 at 10% flat for 12 months.

    total_interest = 5000 * 0.10 * (12/12) = 500.00
    total_repayable = 5500.00
    monthly = 458.33 (last absorbs rounding)
    """
    result = calculate_flat_rate_loan(Decimal("5000.00"), Decimal("10.00"), 12)

    assert result["total_interest"] == Decimal("500.00")
    assert result["total_repayable"] == Decimal("5500.00")
    assert result["monthly_installment"] == Decimal("458.33")
    assert len(result["installments"]) == 12


def test_flat_rate_zero_interest():
    """0% interest produces zero interest and equal installments."""
    result = calculate_flat_rate_loan(Decimal("3000.00"), Decimal("0.00"), 6)

    assert result["total_interest"] == ZERO
    assert result["total_repayable"] == Decimal("3000.00")
    assert result["monthly_installment"] == Decimal("500.00")


def test_flat_rate_short_term():
    """3-month loan produces exactly 3 installments."""
    result = calculate_flat_rate_loan(Decimal("1000.00"), Decimal("12.00"), 3)

    assert len(result["installments"]) == 3
    # Interest = 1000 * 0.12 * 3/12 = 30.00
    assert result["total_interest"] == Decimal("30.00")


def test_flat_rate_sum_integrity():
    """Sum of all installment_amounts equals total_repayable exactly."""
    result = calculate_flat_rate_loan(Decimal("5000.00"), Decimal("10.00"), 12)

    total = sum(i["installment_amount"] for i in result["installments"])
    assert total == result["total_repayable"]


def test_flat_rate_principal_sum():
    """Sum of principal_components equals original principal exactly."""
    result = calculate_flat_rate_loan(Decimal("5000.00"), Decimal("10.00"), 12)

    principal_sum = sum(i["principal_component"] for i in result["installments"])
    assert principal_sum == Decimal("5000.00")


def test_flat_rate_last_closes_zero():
    """Last installment closing_balance is exactly 0.00."""
    result = calculate_flat_rate_loan(Decimal("7777.77"), Decimal("8.50"), 11)

    assert result["installments"][-1]["closing_balance"] == ZERO


# --- Reducing Balance Tests ---


def test_reducing_balance_basic():
    """GHS 5000 at 10% reducing for 12 months.

    EMI ~ 439.58, total_interest ~ 274.96.
    We check the EMI is in the expected ballpark and verify sum integrity.
    """
    result = calculate_reducing_balance_loan(Decimal("5000.00"), Decimal("10.00"), 12)

    assert result["monthly_installment"] == Decimal("439.58")
    # Total interest should be less than flat rate (500)
    assert result["total_interest"] < Decimal("500.00")
    assert result["total_interest"] > Decimal("200.00")


def test_reducing_balance_zero_interest():
    """0% reducing balance is simple division."""
    result = calculate_reducing_balance_loan(Decimal("6000.00"), Decimal("0.00"), 6)

    assert result["total_interest"] == ZERO
    assert result["total_repayable"] == Decimal("6000.00")
    assert result["monthly_installment"] == Decimal("1000.00")


def test_reducing_balance_sum_integrity():
    """Principal components sum to original principal."""
    result = calculate_reducing_balance_loan(Decimal("5000.00"), Decimal("10.00"), 12)

    principal_sum = sum(i["principal_component"] for i in result["installments"])
    assert principal_sum == Decimal("5000.00")

    # Last closing balance should be zero
    assert result["installments"][-1]["closing_balance"] == ZERO


def test_reducing_balance_one_month():
    """Single installment edge case: 1 month tenure."""
    result = calculate_reducing_balance_loan(Decimal("1000.00"), Decimal("12.00"), 1)

    assert len(result["installments"]) == 1
    # Interest for 1 month = 1000 * 0.12 / 12 = 10.00
    assert result["total_interest"] == Decimal("10.00")
    assert result["installments"][0]["closing_balance"] == ZERO

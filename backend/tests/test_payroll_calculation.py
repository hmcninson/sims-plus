"""
Tests for the payroll calculation engine (Phase 4 — pure functions).

PAYE graduated tax, SSNIT contributions, allowance resolution, and full
staff payroll calculation. All functions are stateless — no database needed.

Uses Decimal inputs; verifies Decimal outputs with 2dp precision.
"""

import pytest
from decimal import Decimal

from app.services.payroll.calculation_service import (
    calculate_paye,
    calculate_ssnit,
    calculate_staff_payroll,
    validate_bracket_contiguity,
)

# GRA 2024 monthly tax brackets (same as config_service.GHANA_TAX_BRACKETS_2024)
GRA_2024_BRACKETS = [
    {"band_number": 1, "lower_limit": Decimal("0.00"), "upper_limit": Decimal("490.00"), "rate": Decimal("0.0000")},
    {"band_number": 2, "lower_limit": Decimal("490.00"), "upper_limit": Decimal("600.00"), "rate": Decimal("0.0500")},
    {"band_number": 3, "lower_limit": Decimal("600.00"), "upper_limit": Decimal("730.00"), "rate": Decimal("0.1000")},
    {"band_number": 4, "lower_limit": Decimal("730.00"), "upper_limit": Decimal("3896.67"), "rate": Decimal("0.1750")},
    {"band_number": 5, "lower_limit": Decimal("3896.67"), "upper_limit": Decimal("19896.67"), "rate": Decimal("0.2500")},
    {"band_number": 6, "lower_limit": Decimal("19896.67"), "upper_limit": Decimal("50290.00"), "rate": Decimal("0.3000")},
    {"band_number": 7, "lower_limit": Decimal("50290.00"), "upper_limit": None, "rate": Decimal("0.3500")},
]


# --- PAYE Tests ---


def test_paye_zero_income():
    """Income 0 produces zero tax."""
    tax = calculate_paye(Decimal("0.00"), GRA_2024_BRACKETS)
    assert tax == Decimal("0.00")


def test_paye_below_threshold():
    """Income 400 (below first band upper of 490) is tax-free."""
    tax = calculate_paye(Decimal("400.00"), GRA_2024_BRACKETS)
    assert tax == Decimal("0.00")


def test_paye_single_band():
    """Income 550 falls in bands 1 and 2 only.

    Band 1: first 490 @ 0%   = 0.00
    Band 2: next 60 @ 5%     = 3.00
    Total = 3.00
    """
    tax = calculate_paye(Decimal("550.00"), GRA_2024_BRACKETS)
    assert tax == Decimal("3.00")


def test_paye_multi_band():
    """Income 2000 falls across bands 1-4.

    Band 1: 490 @ 0%          = 0.00
    Band 2: 110 @ 5%          = 5.50
    Band 3: 130 @ 10%         = 13.00
    Band 4: 1270 @ 17.5%      = 222.25
    Total = 240.75
    """
    tax = calculate_paye(Decimal("2000.00"), GRA_2024_BRACKETS)
    assert tax == Decimal("240.75")


def test_paye_top_bracket():
    """Income 60000 hits all 7 bands including the top bracket.

    Band 1: 490.00 @ 0%           = 0.00
    Band 2: 110.00 @ 5%           = 5.50
    Band 3: 130.00 @ 10%          = 13.00
    Band 4: 3166.67 @ 17.5%       = 554.17
    Band 5: 16000.00 @ 25%        = 4000.00
    Band 6: 30393.33 @ 30%        = 9118.00
    Band 7: 9710.00 @ 35%         = 3398.50
    Total = 17089.17
    """
    tax = calculate_paye(Decimal("60000.00"), GRA_2024_BRACKETS)
    assert tax == Decimal("17089.17")


# --- SSNIT Tests ---


def test_ssnit_calculation():
    """Basic 5000 produces correct employee and employer contributions."""
    result = calculate_ssnit(Decimal("5000.00"))

    assert result["ssnit_employee"] == Decimal("275.00")   # 5.5%
    assert result["ssnit_employer"] == Decimal("650.00")   # 13%
    assert result["tier2_employer"] == Decimal("250.00")   # 5%


def test_ssnit_zero_salary():
    """Basic 0 produces all-zero contributions."""
    result = calculate_ssnit(Decimal("0.00"))

    assert result["ssnit_employee"] == Decimal("0.00")
    assert result["ssnit_employer"] == Decimal("0.00")
    assert result["tier2_employer"] == Decimal("0.00")


# --- Allowance Tests ---


def test_fixed_allowance():
    """Fixed allowance passes through as-is."""
    result = calculate_staff_payroll(
        basic_salary=Decimal("3000.00"),
        staff_allowances=[
            {
                "amount": Decimal("500.00"),
                "calculation_method": None,
                "allowance_type": {
                    "name": "Responsibility",
                    "code": "RESP",
                    "calculation_method": "fixed",
                    "is_taxable": True,
                    "id": None,
                },
            }
        ],
        staff_deductions=[],
        tax_brackets=GRA_2024_BRACKETS,
    )

    assert result["total_allowances"] == Decimal("500.00")
    assert result["gross_salary"] == Decimal("3500.00")


def test_percentage_basic_allowance():
    """10% of basic 3000 = 300."""
    result = calculate_staff_payroll(
        basic_salary=Decimal("3000.00"),
        staff_allowances=[
            {
                "amount": Decimal("10.00"),  # 10%
                "calculation_method": None,
                "allowance_type": {
                    "name": "Housing",
                    "code": "HOUS",
                    "calculation_method": "percentage_basic",
                    "is_taxable": True,
                    "id": None,
                },
            }
        ],
        staff_deductions=[],
        tax_brackets=GRA_2024_BRACKETS,
    )

    assert result["total_allowances"] == Decimal("300.00")
    assert result["gross_salary"] == Decimal("3300.00")


def test_percentage_gross_allowance():
    """5% of gross (circular resolution via two-pass).

    Basic = 3000, no other allowances in pass 1.
    Gross proxy = 3000 + 0 = 3000.
    5% of 3000 = 150.
    """
    result = calculate_staff_payroll(
        basic_salary=Decimal("3000.00"),
        staff_allowances=[
            {
                "amount": Decimal("5.00"),  # 5%
                "calculation_method": None,
                "allowance_type": {
                    "name": "Transport",
                    "code": "TRNS",
                    "calculation_method": "percentage_gross",
                    "is_taxable": True,
                    "id": None,
                },
            }
        ],
        staff_deductions=[],
        tax_brackets=GRA_2024_BRACKETS,
    )

    assert result["total_allowances"] == Decimal("150.00")
    assert result["gross_salary"] == Decimal("3150.00")


# --- Taxable Income Tests ---


def test_taxable_income_excludes_ssnit():
    """Taxable income = basic + taxable_allowances - SSNIT employee.

    Basic = 3000, no allowances.
    SSNIT EE = 3000 * 5.5% = 165.
    Taxable = 3000 - 165 = 2835.
    """
    result = calculate_staff_payroll(
        basic_salary=Decimal("3000.00"),
        staff_allowances=[],
        staff_deductions=[],
        tax_brackets=GRA_2024_BRACKETS,
    )

    expected_ssnit_ee = Decimal("165.00")
    expected_taxable = Decimal("3000.00") - expected_ssnit_ee

    assert result["ssnit_employee"] == expected_ssnit_ee
    assert result["taxable_income"] == expected_taxable


def test_tier3_reduces_taxable():
    """Tier 3 voluntary pension is tax-deductible.

    Basic = 5000, Tier 3 = 250 (fixed).
    SSNIT EE = 5000 * 5.5% = 275.
    Taxable = 5000 - 275 - 250 = 4475.
    """
    result = calculate_staff_payroll(
        basic_salary=Decimal("5000.00"),
        staff_allowances=[],
        staff_deductions=[
            {
                "amount": Decimal("250.00"),
                "calculation_method": None,
                "deduction_type": {
                    "name": "Tier 3 Voluntary",
                    "code": "TIER3",
                    "calculation_method": "fixed",
                    "is_statutory": False,
                    "is_employer_portion": False,
                    "deduction_category": "voluntary",
                    "id": None,
                },
            }
        ],
        tax_brackets=GRA_2024_BRACKETS,
    )

    assert result["taxable_income"] == Decimal("4475.00")
    assert result["tier3_employee"] == Decimal("250.00")


# --- Full Calculation Test ---


def test_full_net_salary_calculation():
    """Complete calculation with known expected values.

    Basic = 4000
    Allowance: 500 fixed taxable
    Gross = 4500
    SSNIT EE = 4000 * 5.5% = 220.00
    Taxable = 4000 + 500 - 220 = 4280
    PAYE on 4280:
        Band 1: 490.00 @ 0%     = 0.00
        Band 2: 110.00 @ 5%     = 5.50
        Band 3: 130.00 @ 10%    = 13.00
        Band 4: 3166.67 @ 17.5% = 554.17
        Band 5: 383.33 @ 25%    = 95.83
        Total = 668.50
    Net = 4500 - 668.50 - 220 = 3611.50
    Employer cost = 4500 + 520 + 200 = 5220
    """
    result = calculate_staff_payroll(
        basic_salary=Decimal("4000.00"),
        staff_allowances=[
            {
                "amount": Decimal("500.00"),
                "calculation_method": None,
                "allowance_type": {
                    "name": "Responsibility",
                    "code": "RESP",
                    "calculation_method": "fixed",
                    "is_taxable": True,
                    "id": None,
                },
            }
        ],
        staff_deductions=[],
        tax_brackets=GRA_2024_BRACKETS,
    )

    assert result["basic_salary"] == Decimal("4000.00")
    assert result["total_allowances"] == Decimal("500.00")
    assert result["gross_salary"] == Decimal("4500.00")
    assert result["ssnit_employee"] == Decimal("220.00")
    assert result["ssnit_employer"] == Decimal("520.00")
    assert result["tier2_employer"] == Decimal("200.00")
    assert result["taxable_income"] == Decimal("4280.00")
    assert result["paye_tax"] == Decimal("668.50")
    assert result["net_salary"] == Decimal("3611.50")
    assert result["employer_cost"] == Decimal("5220.00")


# --- Contiguity Validation ---


def test_bracket_contiguity_valid():
    """Valid contiguous brackets do not raise."""
    validate_bracket_contiguity(
        [
            {"band_number": 1, "lower_limit": Decimal("0"), "upper_limit": Decimal("490")},
            {"band_number": 2, "lower_limit": Decimal("490"), "upper_limit": Decimal("600")},
        ]
    )


def test_bracket_contiguity_invalid():
    """Non-contiguous brackets (gap between 400 and 500) raise ValueError."""
    with pytest.raises(ValueError, match="not contiguous"):
        validate_bracket_contiguity(
            [
                {"band_number": 1, "lower_limit": Decimal("0"), "upper_limit": Decimal("400")},
                {"band_number": 2, "lower_limit": Decimal("500"), "upper_limit": Decimal("600")},
            ]
        )

"""
SIMS Plus Utilities package.

Common utility functions and helpers.
"""

import re
from datetime import date


def format_ghana_phone(phone: str) -> str:
    """
    Format phone number to Ghana standard format.

    Args:
        phone: Phone number in various formats

    Returns:
        Formatted phone number (e.g., +233241234567)
    """
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)

    # Handle different formats
    if digits.startswith("233"):
        return f"+{digits}"
    elif digits.startswith("0") and len(digits) == 10:
        return f"+233{digits[1:]}"
    elif len(digits) == 9:
        return f"+233{digits}"

    return phone  # Return original if format unknown


def format_ghana_date(d: date) -> str:
    """
    Format date to Ghana standard (DD/MM/YYYY).

    Args:
        d: Date object

    Returns:
        Formatted date string
    """
    return d.strftime("%d/%m/%Y")


def parse_ghana_date(date_str: str) -> date:
    """
    Parse Ghana format date (DD/MM/YYYY) to date object.

    Args:
        date_str: Date string in DD/MM/YYYY format

    Returns:
        Date object
    """
    from datetime import datetime
    return datetime.strptime(date_str, "%d/%m/%Y").date()


def format_currency_ghs(amount: float) -> str:
    """
    Format amount to Ghana Cedis.

    Args:
        amount: Monetary amount

    Returns:
        Formatted currency string (e.g., GHS 1,500.00)
    """
    return f"GHS {amount:,.2f}"

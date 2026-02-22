"""
SIMS Plus - Staff Service Shared

Shared error class used across staff service modules.
"""


class StaffServiceError(Exception):
    """Base exception for staff service errors."""

    def __init__(self, message: str, code: str = "staff_error"):
        self.message = message
        self.code = code
        super().__init__(message)

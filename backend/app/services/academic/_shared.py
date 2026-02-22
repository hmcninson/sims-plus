"""
SIMS Plus - Academic Service Shared

Shared error class used across academic service modules.
"""


class AcademicServiceError(Exception):
    """Base exception for academic service errors."""

    def __init__(self, message: str, code: str = "academic_error"):
        self.message = message
        self.code = code
        super().__init__(message)

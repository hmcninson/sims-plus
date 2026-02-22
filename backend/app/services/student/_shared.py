"""
SIMS Plus - Student Service Shared

Shared error class used across student service modules.
"""


class StudentServiceError(Exception):
    """Base exception for student service errors."""

    def __init__(self, message: str, code: str = "student_error"):
        self.message = message
        self.code = code
        super().__init__(message)

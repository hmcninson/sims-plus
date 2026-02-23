"""
SIMS Plus - Teacher Portal Shared Classes

Shared error class used across multiple teacher service modules.
"""


class TeacherServiceError(Exception):
    """Base exception for teacher portal service errors."""

    def __init__(self, message: str, code: str = "teacher_error"):
        self.message = message
        self.code = code
        super().__init__(message)

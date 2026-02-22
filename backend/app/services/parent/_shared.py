"""
SIMS Plus - Parent Portal Shared Classes

Shared error class used across multiple parent service modules.
"""


class ParentServiceError(Exception):
    """Base exception for parent portal service errors."""

    def __init__(self, message: str, code: str = "parent_error"):
        self.message = message
        self.code = code
        super().__init__(message)

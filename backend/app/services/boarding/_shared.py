"""
SIMS Plus - Boarding Service Shared Classes

Shared error class used across all boarding service modules.
"""


class BoardingServiceError(Exception):
    """Base exception for boarding service errors."""

    def __init__(self, message: str, code: str = "boarding_error"):
        self.message = message
        self.code = code
        super().__init__(message)

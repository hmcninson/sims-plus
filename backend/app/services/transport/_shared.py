"""
SIMS Plus - Transport Service Shared

Shared error class used across transport service modules.
"""


class TransportServiceError(Exception):
    """Base exception for transport service errors."""

    def __init__(self, message: str, code: str = "transport_error"):
        self.message = message
        self.code = code
        super().__init__(message)

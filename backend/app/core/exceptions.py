"""
SIMS Plus - Custom Exceptions

Application-specific exceptions for consistent error handling.
"""

from typing import Any


class SIMSException(Exception):
    """Base exception for SIMS Plus application."""

    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# =========================
# Authentication Errors
# =========================
class AuthenticationError(SIMSException):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=401, details=details)


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__(message="Invalid email or password")


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    def __init__(self) -> None:
        super().__init__(message="Token has expired")


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""

    def __init__(self) -> None:
        super().__init__(message="Invalid token")


# =========================
# Authorization Errors
# =========================
class AuthorizationError(SIMSException):
    """Raised when user lacks permission."""

    def __init__(
        self,
        message: str = "Permission denied",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=403, details=details)


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user doesn't have required permission."""

    def __init__(self, permission: str) -> None:
        super().__init__(
            message=f"Missing required permission: {permission}",
            details={"required_permission": permission},
        )


# =========================
# Resource Errors
# =========================
class NotFoundError(SIMSException):
    """Raised when a resource is not found."""

    def __init__(
        self,
        resource: str = "Resource",
        resource_id: str | None = None,
    ) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with ID '{resource_id}' not found"
        super().__init__(message, status_code=404, details={"resource": resource})


class DuplicateError(SIMSException):
    """Raised when attempting to create a duplicate resource."""

    def __init__(
        self,
        resource: str = "Resource",
        field: str | None = None,
    ) -> None:
        message = f"{resource} already exists"
        if field:
            message = f"{resource} with this {field} already exists"
        super().__init__(message, status_code=409, details={"resource": resource})


# =========================
# Validation Errors
# =========================
class ValidationError(SIMSException):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=422,
            details={"errors": errors or []},
        )


# =========================
# Tenant Errors
# =========================
class TenantError(SIMSException):
    """Base exception for tenant-related errors."""

    pass


class TenantNotFoundError(TenantError):
    """Raised when tenant is not found."""

    def __init__(self, tenant_id: str | None = None) -> None:
        message = "Tenant not found"
        if tenant_id:
            message = f"Tenant with ID '{tenant_id}' not found"
        super().__init__(message, status_code=404)


class CrossTenantAccessError(TenantError):
    """Raised when attempting to access another tenant's data."""

    def __init__(self) -> None:
        super().__init__(
            message="Cannot access data from another tenant",
            status_code=403,
        )


# =========================
# Business Logic Errors
# =========================
class BusinessRuleError(SIMSException):
    """Raised when a business rule is violated."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=400, details=details)

"""
SIMS Plus Schemas package.

Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, ConfigDict

from app.schemas.tenant import (
    SubdomainCheckRequest,
    SubdomainCheckResponse,
    TenantBranding,
    TenantPublic,
    TenantResponse,
    TenantValidationResponse,
)

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
    TokenResponse,
    ChangePasswordRequest,
    UserResponse,
    UserMeResponse,
)

from app.schemas.onboarding import (
    SchoolRegistrationRequest,
    SchoolRegistrationResponse,
)


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class MessageResponse(BaseSchema):
    """Standard message response."""

    message: str
    success: bool = True


class PaginationParams(BaseSchema):
    """Pagination parameters."""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseSchema):
    """Paginated response wrapper."""

    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

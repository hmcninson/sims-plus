"""
SIMS Plus - User Schemas

Pydantic schemas for user management endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole, UserStatus


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# User Schemas
# =========================


class UserCreate(BaseSchema):
    """Create user request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: UserRole = UserRole.TEACHER
    school_id: Optional[UUID] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserUpdate(BaseSchema):
    """Update user request."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    school_id: Optional[UUID] = None


class UserResponse(BaseSchema):
    """User response."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole
    status: UserStatus
    school_id: Optional[UUID] = None
    custom_role_id: Optional[UUID] = None
    email_verified: bool
    mfa_enabled: bool
    last_login: Optional[datetime] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseSchema):
    """Paginated user list response."""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserRoleUpdate(BaseSchema):
    """Update user role request."""

    role: UserRole


class UserStatusUpdate(BaseSchema):
    """Update user status request."""

    status: UserStatus


class ResetUserPasswordRequest(BaseSchema):
    """Admin reset user password request."""

    new_password: str = Field(..., min_length=8)
    send_email: bool = True

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserInviteRequest(BaseSchema):
    """Invite a new user by email."""

    email: EmailStr
    role: UserRole
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class UserInviteResponse(BaseSchema):
    """Response after inviting a user."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    created_at: datetime


# =========================
# Bulk Import Schemas
# =========================


class MySchoolRoleResponse(BaseSchema):
    """A school and the current user's role at that school."""

    school_id: UUID
    school_name: str
    role_at_school: str | None
    is_primary: bool
    is_active: bool


class UserImportRowError(BaseSchema):
    """A single validation error from CSV import."""

    row: int
    field: str
    error: str


class UserImportRow(BaseSchema):
    """Single row preview from CSV import."""

    row_number: int
    email: str
    first_name: str
    last_name: str
    role: str
    phone: Optional[str] = None
    valid: bool
    errors: list[str] = []


class UserImportCredential(BaseSchema):
    """One-time credential for a newly imported user."""

    email: str
    temporary_password: str


class UserImportResult(BaseSchema):
    """Result of a bulk user import operation."""

    total: int
    valid: int
    created: int
    errors: list[UserImportRowError]
    preview: list[UserImportRow]
    credentials: Optional[list[UserImportCredential]] = None

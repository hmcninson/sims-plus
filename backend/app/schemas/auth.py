"""
SIMS Plus - Authentication Schemas

Pydantic schemas for authentication endpoints.
"""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


# =========================
# Password Validation
# =========================

def validate_password_strength(password: str) -> str:
    """
    Validate password meets strength requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain at least one special character")

    return password


# =========================
# Login Schemas
# =========================

class LoginRequest(BaseSchema):
    """Login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")
    remember_me: bool = Field(default=False, description="Extended session")


class LoginResponse(BaseSchema):
    """Login response with tokens and user info."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")
    user: "UserResponse"


# =========================
# Registration Schemas
# =========================

class RegisterRequest(BaseSchema):
    """User registration request (within existing tenant)."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Remove spaces and validate Ghana phone format
        phone = re.sub(r"\s+", "", v)
        if not re.match(r"^(\+233|0)[0-9]{9}$", phone):
            raise ValueError("Invalid Ghana phone number format")
        return phone


class RegisterResponse(BaseSchema):
    """Registration response."""

    message: str
    user_id: UUID
    email: str
    requires_verification: bool = True


# =========================
# Token Schemas
# =========================

class RefreshTokenRequest(BaseSchema):
    """Refresh token request."""

    refresh_token: str


class TokenResponse(BaseSchema):
    """Token refresh response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# =========================
# Password Reset Schemas
# =========================

class PasswordResetRequest(BaseSchema):
    """Request password reset."""

    email: EmailStr


class PasswordResetConfirm(BaseSchema):
    """Confirm password reset with new password."""

    token: str
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class ChangePasswordRequest(BaseSchema):
    """Change password (authenticated user)."""

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


# =========================
# User Response Schemas
# =========================

class UserResponse(BaseSchema):
    """User information response."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: str
    status: str
    tenant_id: UUID
    school_id: Optional[UUID] = None
    avatar_url: Optional[str] = None
    email_verified: bool
    mfa_enabled: bool
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class UserMeResponse(BaseSchema):
    """Current user response with tenant info."""

    user: UserResponse
    tenant: "TenantInfo"
    permissions: list[str] = []


class TenantInfo(BaseSchema):
    """Tenant info for user response."""

    id: UUID
    name: str
    subdomain: str
    subscription_tier: str
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


# =========================
# Profile Update
# =========================

class ProfileUpdateRequest(BaseSchema):
    """Update user profile request."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    avatar_url: Optional[str] = Field(None, max_length=500)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Remove spaces and validate phone format
        phone = re.sub(r"\s+", "", v)
        # Allow Ghana format or international
        if not re.match(r"^(\+233|0)[0-9]{9}$|^\+[0-9]{10,15}$", phone):
            raise ValueError("Invalid phone number format")
        return phone


# =========================
# Email Verification
# =========================

class VerifyEmailRequest(BaseSchema):
    """Email verification request."""

    token: str


class ResendVerificationRequest(BaseSchema):
    """Resend verification email request."""

    email: EmailStr


# Update forward references
LoginResponse.model_rebuild()
UserMeResponse.model_rebuild()

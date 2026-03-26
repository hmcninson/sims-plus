"""Pydantic schemas for OTP-based flows (phone verification, SMS password reset)."""

from pydantic import BaseModel, Field, field_validator


class SendPhoneOTPResponse(BaseModel):
    """Response after sending a phone verification OTP."""

    message: str = "Verification code sent"


class VerifyPhoneRequest(BaseModel):
    """Request to verify phone number with OTP."""

    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit verification code",
    )

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v


class ForgotPasswordSMSRequest(BaseModel):
    """Request to initiate SMS-based password reset."""

    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number in international format (e.g., +233241234567)",
    )


class ResetPasswordSMSRequest(BaseModel):
    """Request to reset password using SMS OTP."""

    phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number that received the OTP",
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit verification code",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (must meet complexity requirements)",
    )

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Reuse the shared password validator from schemas/auth.py."""
        from app.schemas.auth import validate_password_strength

        return validate_password_strength(v)

"""
SIMS Plus - MFA Schemas

Pydantic schemas for Multi-Factor Authentication endpoints.
"""

from pydantic import BaseModel, Field, field_validator


class MFASetupResponse(BaseModel):
    """Response from MFA setup initiation."""

    secret: str = Field(description="Base32 secret for manual entry")
    provisioning_uri: str = Field(description="otpauth:// URI for QR code")
    qr_code_base64: str = Field(description="data:image/png;base64,... for display")
    backup_codes: list[str] = Field(
        description="10 one-time backup codes (XXXX-XXXX format)"
    )


class MFAVerifySetupRequest(BaseModel):
    """Request to verify MFA setup with a TOTP code from authenticator app."""

    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit code from authenticator app",
    )

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v


class MFAVerifyLoginRequest(BaseModel):
    """Request to verify MFA during login flow."""

    mfa_pending_token: str = Field(
        ...,
        description="Token received from initial login attempt",
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=9,  # 6 digits for TOTP or 8-9 chars for backup code (with dash)
        description="TOTP code or backup code",
    )


class MFADisableRequest(BaseModel):
    """Request to disable MFA. Requires password confirmation."""

    password: str = Field(
        ...,
        min_length=1,
        description="Current password for confirmation",
    )


class MFABackupCodesResponse(BaseModel):
    """Response containing newly generated backup codes."""

    backup_codes: list[str]


class MFAStatusResponse(BaseModel):
    """MFA status for the current user."""

    mfa_enabled: bool
    backup_codes_remaining: int | None = None  # None if MFA not enabled


class MFARequiredResponse(BaseModel):
    """Returned when login succeeds but MFA verification is needed."""

    mfa_required: bool = True
    mfa_pending_token: str

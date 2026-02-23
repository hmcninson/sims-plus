"""
SIMS Plus - Communication Settings Schemas

Pydantic schemas for school-level communication preferences:
SMS sender configuration, email defaults, and notification toggles.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SMSSettings(BaseModel):
    """SMS gateway and notification settings for a school."""

    sender_id: str = Field(
        default="SIMSPLUS",
        max_length=11,
        description="Alphanumeric sender ID shown on SMS (max 11 characters per GSM spec)",
    )
    attendance_alerts_enabled: bool = True
    fee_reminders_enabled: bool = True

    @field_validator("sender_id")
    @classmethod
    def validate_sender_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Sender ID cannot be empty")
        if len(v) > 11:
            raise ValueError("Sender ID must be 11 characters or fewer")
        return v


class EmailSettings(BaseModel):
    """Email sending defaults for a school."""

    from_email: str | None = Field(
        default=None,
        max_length=255,
        description="Custom from-email address (falls back to system default)",
    )
    from_name: str | None = Field(
        default=None,
        max_length=255,
        description="Custom from-name (falls back to school name)",
    )
    reply_to: str | None = Field(
        default=None,
        max_length=255,
        description="Reply-to address for outbound emails",
    )
    signature: str | None = Field(
        default=None,
        max_length=2000,
        description="HTML email signature appended to composed messages",
    )


class NotificationDefaults(BaseModel):
    """Default notification preferences for a school."""

    report_card_notifications: bool = True
    event_announcements: bool = True
    weekly_digest: bool = False


class CommunicationSettings(BaseModel):
    """Full communication settings object stored in schools.communication_settings."""

    sms: SMSSettings = Field(default_factory=SMSSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    notifications: NotificationDefaults = Field(default_factory=NotificationDefaults)


class CommunicationSettingsUpdate(BaseModel):
    """Partial update for communication settings (only provided sections are merged)."""

    sms: SMSSettings | None = None
    email: EmailSettings | None = None
    notifications: NotificationDefaults | None = None


class CommunicationSettingsResponse(BaseModel):
    """Response schema for communication settings."""

    model_config = ConfigDict(from_attributes=True)

    sms: SMSSettings
    email: EmailSettings
    notifications: NotificationDefaults

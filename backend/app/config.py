"""
SIMS Plus - Application Configuration

Uses Pydantic Settings for environment variable management.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================
    # Application
    # =========================
    APP_NAME: str = "SIMS Plus"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = "development"
    DEBUG: bool = False  # SECURITY: Default to False, explicitly enable in development

    # =========================
    # Server
    # =========================
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # =========================
    # Database
    # =========================
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Alembic uses superuser for DDL operations
    ALEMBIC_DATABASE_URL: str | None = None

    # =========================
    # Redis
    # =========================
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"  # type: ignore

    # =========================
    # Security
    # =========================
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # =========================
    # CORS
    # =========================
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_SUBDOMAIN_PATTERN: str = r"https?://[\w-]+\.simsplus\.io"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or JSON array."""
        if isinstance(v, str):
            # Try JSON array first
            if v.startswith("["):
                import json
                return json.loads(v)
            # Fall back to comma-separated
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key_length(cls, v: str, info: ValidationInfo) -> str:
        """
        Validate SECRET_KEY minimum length.

        Enforces 64 characters in production for stronger security,
        32 characters in development/staging for convenience.
        """
        env = info.data.get("ENVIRONMENT", "development")
        min_length = 64 if env == "production" else 32
        if len(v) < min_length:
            raise ValueError(
                f"SECRET_KEY must be at least {min_length} characters in {env} mode. "
                "Generate with: openssl rand -base64 64"
            )
        return v

    # =========================
    # Rate Limiting
    # =========================
    RATE_LIMIT_ENABLED: bool = True
    # Production-safe defaults per security spec; override via env vars for development
    RATE_LIMIT_DEFAULT_REQUESTS: int = 100
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # seconds
    RATE_LIMIT_AUTH_REQUESTS: int = 5
    RATE_LIMIT_AUTH_WINDOW: int = 60  # seconds
    RATE_LIMIT_SUBDOMAIN_CHECK_REQUESTS: int = 20
    RATE_LIMIT_SUBDOMAIN_CHECK_WINDOW: int = 60  # seconds

    # =========================
    # Email (SMTP)
    # =========================
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = False
    SMTP_START_TLS: bool = True
    SMTP_FROM_EMAIL: str = "noreply@simsplus.io"
    SMTP_FROM_NAME: str = "SIMS Plus"

    # =========================
    # SMS (Hubtel)
    # =========================
    HUBTEL_CLIENT_ID: str | None = None
    HUBTEL_CLIENT_SECRET: str | None = None
    HUBTEL_SENDER_ID: str = "SIMSPlus"
    HUBTEL_MERCHANT_ACCOUNT: str | None = None

    # =========================
    # Mobile Money (MTN MoMo)
    # =========================
    MTN_MOMO_SUBSCRIPTION_KEY: str | None = None
    MTN_MOMO_API_USER: str | None = None
    MTN_MOMO_API_KEY: str | None = None
    MTN_MOMO_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"

    # =========================
    # AWS S3
    # =========================
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "sims-plus-files"
    S3_ENDPOINT_URL: str | None = None  # Set to MinIO URL for local dev
    USE_MINIO: bool = False  # True when using MinIO instead of S3

    # =========================
    # Web Push (VAPID)
    # =========================
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CONTACT_EMAIL: str = "support@simsplus.io"

    # =========================
    # Paystack (Online Payments)
    # =========================
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_WEBHOOK_SECRET: str = ""  # Falls back to PAYSTACK_SECRET_KEY if empty
    PAYMENT_CALLBACK_URL: str = ""  # URL to redirect parent after Paystack payment

    # =========================
    # Cloudflare Turnstile (CAPTCHA for public forms)
    # =========================
    TURNSTILE_SECRET_KEY: str = ""  # Server-side secret key
    TURNSTILE_SITE_KEY: str = ""  # Client-side site key (exposed to frontend)

    # =========================
    # Admissions
    # =========================
    ADMISSIONS_DAILY_CAP_PER_TENANT: int = 500  # Max applications per tenant per day
    RATE_LIMIT_ADMISSIONS_SUBMIT_REQUESTS: int = 3
    RATE_LIMIT_ADMISSIONS_SUBMIT_WINDOW: int = 60  # 3 submissions per minute per IP

    # Applicant account rate limits
    RATE_LIMIT_APPLICANT_REGISTER_REQUESTS: int = 3
    RATE_LIMIT_APPLICANT_REGISTER_WINDOW: int = 60  # 3 per minute per IP
    RATE_LIMIT_APPLICANT_RESEND_REQUESTS: int = 2
    RATE_LIMIT_APPLICANT_RESEND_WINDOW: int = 60  # 2 per minute per IP
    RATE_LIMIT_SUBSCRIPTION_REQUESTS: int = 5
    RATE_LIMIT_SUBSCRIPTION_WINDOW: int = 3600  # 5 per hour per IP (M3)

    # =========================
    # Subscription / Trial
    # =========================
    TRIAL_DAYS: int = 90
    TRIAL_GRACE_PERIOD_DAYS: int = 7  # Read-only grace period after trial/subscription expires

    # =========================
    # Sentry
    # =========================
    SENTRY_DSN: str | None = None

    # =========================
    # Logging
    # =========================
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore


settings = get_settings()

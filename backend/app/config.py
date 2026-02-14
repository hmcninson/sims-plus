"""
SIMS Plus - Application Configuration

Uses Pydantic Settings for environment variable management.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, field_validator
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
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
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

    # =========================
    # Rate Limiting
    # =========================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_REQUESTS: int = 500  # Increased for development
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # seconds
    RATE_LIMIT_AUTH_REQUESTS: int = 30  # Increased for development
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
    AWS_REGION: str = "eu-west-1"
    AWS_S3_BUCKET: str = "sims-plus-files"

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

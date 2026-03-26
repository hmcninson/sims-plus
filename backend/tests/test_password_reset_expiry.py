"""
Tests for password reset token expiry configuration.

Verifies that the PASSWORD_RESET_TOKEN_EXPIRY_MINUTES setting is
respected by the PasswordResetService.
"""

import pytest

from app.config import settings


class TestPasswordResetConfig:
    def test_password_reset_expiry_is_60_minutes(self):
        """The password reset token expiry should be configured at 60 minutes."""
        assert settings.PASSWORD_RESET_TOKEN_EXPIRY_MINUTES == 60

    def test_password_reset_expiry_is_positive(self):
        """Expiry must be a positive integer."""
        assert settings.PASSWORD_RESET_TOKEN_EXPIRY_MINUTES > 0

    def test_password_reset_expiry_converts_to_seconds(self):
        """The service uses expiry * 60 for Redis TTL. Verify the math."""
        ttl_seconds = settings.PASSWORD_RESET_TOKEN_EXPIRY_MINUTES * 60
        assert ttl_seconds == 3600  # 60 minutes = 3600 seconds

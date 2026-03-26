"""
SIMS Plus - Password Reset Service

Handles password reset token generation, validation, and email sending.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models.user import User, UserStatus
from app.services.audit import AuditService, AuditEventType


class PasswordResetError(Exception):
    """Password reset operation failed."""

    def __init__(self, message: str, code: str = "reset_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class PasswordResetService:
    """
    Service for password reset operations.

    Uses Redis for token storage with automatic expiration.
    """

    TOKEN_PREFIX = "password_reset:"
    MAX_RESET_ATTEMPTS = 5  # Per email per hour

    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis] = None):
        self.db = db
        self._redis_client = redis_client
        self.audit = AuditService(db)

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection."""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    str(settings.REDIS_URL),
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis_client.ping()
            except Exception:
                return None
        return self._redis_client

    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    async def request_password_reset(
        self,
        email: str,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Request a password reset.

        Args:
            email: User's email address
            tenant_id: Tenant UUID
            ip_address: Client IP for rate limiting and audit

        Returns:
            Reset token if user exists, None otherwise.
            Always returns success message to prevent email enumeration.

        Raises:
            PasswordResetError: If rate limited
        """
        redis_client = await self._get_redis()

        # Rate limiting check
        if redis_client:
            rate_key = f"reset_rate:{tenant_id}:{email}"
            attempts = await redis_client.get(rate_key)
            if attempts and int(attempts) >= self.MAX_RESET_ATTEMPTS:
                raise PasswordResetError(
                    "Too many password reset attempts. Please try again later.",
                    code="rate_limited",
                )

        # Find user
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            # Log attempt but don't reveal user doesn't exist
            await self.audit.log(
                event_type=AuditEventType.PASSWORD_RESET_REQUEST,
                tenant_id=tenant_id,
                ip_address=ip_address,
                details={"email": email, "result": "user_not_found"},
                success=False,
            )
            return None

        # Check user status
        if user.status not in (UserStatus.ACTIVE, UserStatus.PENDING):
            await self.audit.log(
                event_type=AuditEventType.PASSWORD_RESET_REQUEST,
                tenant_id=tenant_id,
                user_id=user.id,
                ip_address=ip_address,
                details={"status": user.status.value, "result": "invalid_status"},
                success=False,
            )
            return None

        # Generate token
        token = self._generate_token()

        if redis_client:
            # Store token in Redis
            token_key = f"{self.TOKEN_PREFIX}{token}"
            token_data = f"{user.id}:{tenant_id}"
            expiry = settings.PASSWORD_RESET_TOKEN_EXPIRY_MINUTES * 60

            await redis_client.setex(token_key, expiry, token_data)

            # Increment rate limit counter
            rate_key = f"reset_rate:{tenant_id}:{email}"
            pipe = redis_client.pipeline()
            pipe.incr(rate_key)
            pipe.expire(rate_key, 3600)  # 1 hour window
            await pipe.execute()

        # Log successful request
        await self.audit.log(
            event_type=AuditEventType.PASSWORD_RESET_REQUEST,
            tenant_id=tenant_id,
            user_id=user.id,
            ip_address=ip_address,
            details={"result": "token_generated"},
            success=True,
        )

        return token

    async def validate_reset_token(self, token: str) -> Optional[tuple[UUID, UUID]]:
        """
        Validate a password reset token.

        Args:
            token: The reset token to validate

        Returns:
            Tuple of (user_id, tenant_id) if valid, None otherwise
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return None

        try:
            token_key = f"{self.TOKEN_PREFIX}{token}"
            token_data = await redis_client.get(token_key)

            if not token_data:
                return None

            user_id_str, tenant_id_str = token_data.split(":")
            return UUID(user_id_str), UUID(tenant_id_str)

        except Exception:
            return None

    async def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Reset user password using token.

        Args:
            token: Password reset token
            new_password: New password (already validated by schema)
            ip_address: Client IP for audit

        Returns:
            True if successful

        Raises:
            PasswordResetError: If token is invalid or expired
        """
        redis_client = await self._get_redis()
        if not redis_client:
            raise PasswordResetError(
                "Password reset service unavailable",
                code="service_unavailable",
            )

        # Validate token
        token_data = await self.validate_reset_token(token)
        if not token_data:
            raise PasswordResetError(
                "Invalid or expired reset token",
                code="invalid_token",
            )

        user_id, tenant_id = token_data

        # Get user
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise PasswordResetError(
                "User not found",
                code="user_not_found",
            )

        # Update password
        user.password_hash = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None

        # If user was pending (email not verified), activate them
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE
            user.email_verified = True
            user.email_verified_at = datetime.now(UTC)

        await self.db.flush()

        # Delete used token
        token_key = f"{self.TOKEN_PREFIX}{token}"
        await redis_client.delete(token_key)

        # Invalidate all existing tokens for this user
        from app.services.token_blacklist import get_token_blacklist_service
        blacklist_service = await get_token_blacklist_service()
        await blacklist_service.blacklist_user_tokens(str(user_id))

        # Log successful reset
        await self.audit.log(
            event_type=AuditEventType.PASSWORD_RESET_COMPLETE,
            tenant_id=tenant_id,
            user_id=user_id,
            target_type="user",
            target_id=user_id,
            ip_address=ip_address,
            details={"result": "password_reset"},
            success=True,
        )

        return True

    async def send_reset_email(
        self,
        email: str,
        token: str,
        subdomain: str,
    ) -> bool:
        """
        Send password reset email.

        Args:
            email: User's email address
            token: Password reset token
            subdomain: Tenant subdomain for reset link

        Returns:
            True if email sent successfully
        """
        # Build reset URL
        if settings.is_production:
            reset_url = f"https://{subdomain}.simsplus.io/reset-password?token={token}"
        else:
            reset_url = f"http://localhost:3000/reset-password?token={token}"

        # TODO: Integrate with SendGrid
        # For now, log the reset URL in development
        if settings.is_development:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Password reset link for {email}: {reset_url}")
            return True

        # In production, use SendGrid
        if settings.SENDGRID_API_KEY:
            try:
                # TODO: Implement SendGrid integration
                # from sendgrid import SendGridAPIClient
                # from sendgrid.helpers.mail import Mail
                pass
            except Exception:
                return False

        return True

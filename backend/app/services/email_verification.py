"""
SIMS Plus - Email Verification Service

Handles email verification token generation, validation, and email sending.
"""

import secrets
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserStatus
from app.services.audit import AuditService, AuditEventType


class EmailVerificationError(Exception):
    """Email verification operation failed."""

    def __init__(self, message: str, code: str = "verification_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class EmailVerificationService:
    """
    Service for email verification operations.

    Uses Redis for token storage with automatic expiration.
    """

    TOKEN_PREFIX = "email_verify:"
    TOKEN_EXPIRY_HOURS = 24
    MAX_RESEND_ATTEMPTS = 5  # Per email per hour

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

    async def create_verification_token(
        self,
        user_id: UUID,
        tenant_id: UUID,
        email: str,
    ) -> Optional[str]:
        """
        Create an email verification token.

        Args:
            user_id: User's UUID
            tenant_id: Tenant's UUID
            email: User's email address

        Returns:
            Verification token if successful, None otherwise
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return None

        token = self._generate_token()
        token_key = f"{self.TOKEN_PREFIX}{token}"
        token_data = f"{user_id}:{tenant_id}:{email}"
        expiry = self.TOKEN_EXPIRY_HOURS * 3600

        await redis_client.setex(token_key, expiry, token_data)

        return token

    async def validate_verification_token(
        self,
        token: str,
    ) -> Optional[tuple[UUID, UUID, str]]:
        """
        Validate an email verification token.

        Args:
            token: The verification token

        Returns:
            Tuple of (user_id, tenant_id, email) if valid, None otherwise
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return None

        try:
            token_key = f"{self.TOKEN_PREFIX}{token}"
            token_data = await redis_client.get(token_key)

            if not token_data:
                return None

            parts = token_data.split(":")
            if len(parts) != 3:
                return None

            user_id_str, tenant_id_str, email = parts
            return UUID(user_id_str), UUID(tenant_id_str), email

        except Exception:
            return None

    async def verify_email(
        self,
        token: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Verify user email using token.

        Args:
            token: Email verification token
            ip_address: Client IP for audit

        Returns:
            True if successful

        Raises:
            EmailVerificationError: If token is invalid or expired
        """
        redis_client = await self._get_redis()
        if not redis_client:
            raise EmailVerificationError(
                "Email verification service unavailable",
                code="service_unavailable",
            )

        # Validate token
        token_data = await self.validate_verification_token(token)
        if not token_data:
            raise EmailVerificationError(
                "Invalid or expired verification token",
                code="invalid_token",
            )

        user_id, tenant_id, email = token_data

        # Get user
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise EmailVerificationError(
                "User not found",
                code="user_not_found",
            )

        if user.email_verified:
            # Already verified - still return success
            return True

        # Mark email as verified
        user.email_verified = True
        user.email_verified_at = datetime.now(UTC)

        # Activate user if pending
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE

        await self.db.flush()

        # Delete used token
        token_key = f"{self.TOKEN_PREFIX}{token}"
        await redis_client.delete(token_key)

        # Log successful verification
        await self.audit.log(
            event_type=AuditEventType.ACCOUNT_ACTIVATED,
            tenant_id=tenant_id,
            user_id=user_id,
            target_type="user",
            target_id=user_id,
            ip_address=ip_address,
            details={"email": email, "result": "email_verified"},
            success=True,
        )

        return True

    async def resend_verification(
        self,
        email: str,
        tenant_id: UUID,
        ip_address: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resend verification email.

        Args:
            email: User's email address
            tenant_id: Tenant UUID
            ip_address: Client IP for rate limiting

        Returns:
            Verification token if successful, None otherwise

        Raises:
            EmailVerificationError: If rate limited or user not found
        """
        redis_client = await self._get_redis()

        # Rate limiting check
        if redis_client:
            rate_key = f"verify_rate:{tenant_id}:{email}"
            attempts = await redis_client.get(rate_key)
            if attempts and int(attempts) >= self.MAX_RESEND_ATTEMPTS:
                raise EmailVerificationError(
                    "Too many verification email requests. Please try again later.",
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
            return None

        if user.email_verified:
            raise EmailVerificationError(
                "Email is already verified",
                code="already_verified",
            )

        # Generate new token
        token = await self.create_verification_token(
            user_id=user.id,
            tenant_id=tenant_id,
            email=email,
        )

        if redis_client:
            # Increment rate limit counter
            rate_key = f"verify_rate:{tenant_id}:{email}"
            pipe = redis_client.pipeline()
            pipe.incr(rate_key)
            pipe.expire(rate_key, 3600)  # 1 hour window
            await pipe.execute()

        return token

    async def send_verification_email(
        self,
        email: str,
        token: str,
        subdomain: str,
        first_name: str = "",
    ) -> bool:
        """
        Send verification email.

        Args:
            email: User's email address
            token: Verification token
            subdomain: Tenant subdomain
            first_name: User's first name for personalization

        Returns:
            True if email sent successfully
        """
        # Build verification URL
        if settings.is_production:
            verify_url = f"https://{subdomain}.simsplus.io/verify-email?token={token}"
        else:
            verify_url = f"http://localhost:3000/verify-email?token={token}"

        # TODO: Integrate with SendGrid
        # For now, log the verification URL in development
        if settings.is_development:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Email verification link for {email}: {verify_url}")
            return True

        # In production, use SendGrid
        if settings.SENDGRID_API_KEY:
            try:
                # TODO: Implement SendGrid integration
                pass
            except Exception:
                return False

        return True

"""
SIMS Plus - Token Blacklist Service

Redis-based token blacklisting for secure logout.
"""

import hashlib
import logging
from datetime import UTC, datetime
from typing import Optional

import redis.asyncio as redis
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """
    Service for managing token blacklist using Redis.

    Tokens are blacklisted by storing a hash of the token with TTL
    matching the token's remaining validity period.
    """

    BLACKLIST_PREFIX = "token_blacklist:"

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis_client = redis_client
        self._connected = False

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection."""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    str(settings.REDIS_URL),
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Test connection
                await self._redis_client.ping()
                self._connected = True
            except Exception:
                self._connected = False
                return None
        return self._redis_client

    def _get_token_hash(self, token: str) -> str:
        """Generate a hash of the token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _get_token_expiry_seconds(self, token: str) -> int:
        """
        Get remaining seconds until token expires.

        Returns 0 if token is already expired or invalid.
        """
        try:
            # Decode without verification to get expiry
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
            exp = payload.get("exp")
            if not exp:
                return 0

            # Calculate remaining seconds
            exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
            now = datetime.now(UTC)

            if exp_datetime <= now:
                return 0

            remaining = (exp_datetime - now).total_seconds()
            return int(remaining) + 60  # Add 60s buffer

        except JWTError:
            return 0

    async def blacklist_token(self, token: str) -> bool:
        """
        Add a token to the blacklist.

        Args:
            token: JWT token to blacklist

        Returns:
            True if successfully blacklisted, False if Redis unavailable
        """
        redis_client = await self._get_redis()
        if redis_client is None:
            return False

        try:
            token_hash = self._get_token_hash(token)
            ttl = self._get_token_expiry_seconds(token)

            if ttl <= 0:
                # Token already expired, no need to blacklist
                return True

            key = f"{self.BLACKLIST_PREFIX}{token_hash}"
            await redis_client.setex(key, ttl, "1")
            return True

        except Exception:
            return False

    async def is_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token: JWT token to check

        Returns:
            True if blacklisted or Redis unavailable in production, False otherwise
        """
        redis_client = await self._get_redis()
        if redis_client is None:
            # Fail closed in production: treat as blacklisted when Redis is down,
            # so logged-out tokens cannot be reused during outages
            if settings.ENVIRONMENT == "production":
                return True
            # Fail open in development/staging for developer convenience
            return False

        try:
            token_hash = self._get_token_hash(token)
            key = f"{self.BLACKLIST_PREFIX}{token_hash}"
            result = await redis_client.exists(key)
            return result > 0

        except Exception:
            # Fail closed in production if Redis command fails
            if settings.ENVIRONMENT == "production":
                return True
            return False

    async def blacklist_jti(self, jti: str) -> bool:
        """
        Blacklist a refresh token by its JTI (JWT ID).

        Used when terminating sessions -- we know the JTI but not the
        full token string. The JTI is stored for the full refresh token
        lifetime so any attempt to use a token with this JTI is rejected.

        Args:
            jti: JWT ID to blacklist

        Returns:
            True if successfully blacklisted, False if Redis unavailable
        """
        redis_client = await self._get_redis()
        if redis_client is None:
            return False

        try:
            key = f"jti_blacklist:{jti}"
            # Keep for full refresh token duration
            ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            await redis_client.setex(key, ttl, "1")
            return True
        except Exception:
            return False

    async def is_jti_blacklisted(
        self,
        jti: str,
        db: Optional[AsyncSession] = None,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a JTI has been blacklisted.

        Fail-closed: when Redis is unavailable, falls back to checking the
        user_sessions table. If the session is inactive or missing, the JTI
        is treated as blacklisted. If both Redis and DB are unavailable,
        returns True (blocked) for security.

        Args:
            jti: JWT ID to check
            db: Optional database session for fallback when Redis is down
            tenant_id: Optional tenant ID for defense-in-depth filtering on DB fallback

        Returns:
            True if blacklisted, False otherwise
        """
        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                key = f"jti_blacklist:{jti}"
                result = await redis_client.exists(key)
                return result > 0
            except Exception:
                # Redis command failed -- fall through to DB fallback
                logger.warning(
                    "Redis command failed for JTI blacklist check, "
                    "falling back to database",
                    extra={"jti": jti[:8]},
                )

        # Redis unavailable or command failed -- use DB fallback
        return await self._check_jti_via_db(jti, db, tenant_id=tenant_id)

    async def _check_jti_via_db(
        self,
        jti: str,
        db: Optional[AsyncSession],
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Database fallback for JTI blacklist check.

        Queries user_sessions to determine if the session is still active.
        If the session is inactive or not found, returns True (blocked).
        If DB is unavailable, returns True (fail closed for security).
        """
        if db is None:
            # No DB session available -- fail closed
            logger.warning(
                "No DB session for JTI blacklist fallback, failing closed",
                extra={"jti": jti[:8]},
            )
            return True

        try:
            from app.models.user_session import UserSession
            from sqlalchemy import select

            query = (
                select(UserSession.is_active)
                .where(UserSession.jti == jti)
            )
            # Defense-in-depth: scope to tenant even though RLS enforces isolation
            if tenant_id is not None:
                query = query.where(UserSession.tenant_id == tenant_id)

            result = await db.execute(query)
            session_active = result.scalar_one_or_none()

            if session_active is None:
                # Session not found -- treat as revoked
                return True

            # Session found -- blocked if inactive
            return not session_active

        except Exception:
            # DB query failed -- fail closed for security
            logger.error(
                "DB fallback for JTI blacklist check failed, failing closed",
                extra={"jti": jti[:8]},
            )
            return True

    async def blacklist_user_tokens(self, user_id: str) -> bool:
        """
        Blacklist all tokens for a user (for password change, account suspension).

        This stores a user-level blacklist marker with a timestamp.
        Tokens issued before this timestamp should be rejected.

        Args:
            user_id: User ID to blacklist all tokens for

        Returns:
            True if successful, False otherwise
        """
        redis_client = await self._get_redis()
        if redis_client is None:
            return False

        try:
            key = f"user_token_blacklist:{user_id}"
            # Store current timestamp - all tokens issued before this are invalid
            timestamp = int(datetime.now(UTC).timestamp())
            # Keep for refresh token duration
            ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            await redis_client.setex(key, ttl, str(timestamp))
            return True

        except Exception:
            return False

    async def is_user_token_revoked(self, user_id: str, token_issued_at: int) -> bool:
        """
        Check if a user's token was revoked (issued before mass revocation).

        Args:
            user_id: User ID to check
            token_issued_at: Token's iat (issued at) timestamp

        Returns:
            True if token should be rejected, False otherwise
        """
        redis_client = await self._get_redis()
        if redis_client is None:
            return False

        try:
            key = f"user_token_blacklist:{user_id}"
            revoked_at = await redis_client.get(key)

            if revoked_at is None:
                return False

            # Token is revoked if issued before the revocation timestamp
            return token_issued_at < int(revoked_at)

        except Exception:
            # Fail closed in production if Redis command fails
            if settings.ENVIRONMENT == "production":
                return True
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()


# Global instance for dependency injection
_token_blacklist_service: Optional[TokenBlacklistService] = None


async def get_token_blacklist_service() -> TokenBlacklistService:
    """Get the global token blacklist service instance."""
    global _token_blacklist_service
    if _token_blacklist_service is None:
        _token_blacklist_service = TokenBlacklistService()
    return _token_blacklist_service

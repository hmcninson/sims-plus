"""
OTP (One-Time Password) service for phone-based verification flows.

Used by:
- Phone number verification (UM-001)
- SMS password reset (UM-003)

OTPs are:
- 6 digits, randomly generated
- Hashed (SHA-256) before Redis storage
- Scoped by tenant_id to prevent cross-tenant reuse
- Rate-limited: 1 OTP per phone per minute
- Max 5 verification attempts per OTP
- 10-minute expiry
"""

import hashlib
import secrets
import structlog
from enum import Enum
from uuid import UUID

from app.services.messaging.arkesel_client import ArkeselClient

logger = structlog.get_logger()

# Module-level singleton — avoids creating a new client per OTP send
_sms_client = ArkeselClient()


class OTPPurpose(str, Enum):
    PHONE_VERIFICATION = "phone_verify"
    PASSWORD_RESET = "password_reset"


class OTPError(Exception):
    """OTP operation error with machine-readable code."""

    def __init__(self, message: str, code: str = "otp_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class OTPService:
    """OTP generation, storage (Redis), and verification."""

    OTP_LENGTH = 6
    OTP_EXPIRY_SECONDS = 600        # 10 minutes
    MAX_ATTEMPTS = 5
    RATE_LIMIT_SECONDS = 60         # 1 OTP per phone per minute

    def __init__(self, redis_client):
        """
        Args:
            redis_client: Redis client from request.app.state.redis
                          (must have decode_responses=True)
        """
        self.redis = redis_client

    def _key(self, purpose: OTPPurpose, tenant_id: UUID, phone: str, suffix: str) -> str:
        """
        Generate tenant-scoped Redis key.

        Format: otp:{purpose}:{tenant_id}:{phone}:{suffix}
        Suffixes: code, attempts, rate
        """
        return f"otp:{purpose.value}:{tenant_id}:{phone}:{suffix}"

    def _hash_otp(self, otp: str) -> str:
        """Hash OTP with SHA-256 for storage. NOT for passwords — just for OTP defense-in-depth."""
        return hashlib.sha256(otp.encode()).hexdigest()

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone number: strip spaces/dashes and convert local
        Ghana format (0XX) to international (+233XX).
        """
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("0") and len(phone) == 10:
            phone = "+233" + phone[1:]
        return phone

    async def generate_and_send(
        self,
        phone: str,
        purpose: OTPPurpose,
        tenant_id: UUID,
        school_name: str = "SIMS Plus",
    ) -> bool:
        """
        Generate a 6-digit OTP, store hashed in Redis, send via Arkesel SMS.

        Args:
            phone: Recipient phone number (will be normalized, e.g., +233241234567)
            purpose: What the OTP is for (phone_verify or password_reset)
            tenant_id: Current tenant UUID (for key scoping)
            school_name: School name for SMS message personalization

        Returns:
            True if OTP was sent successfully.

        Raises:
            OTPError("rate_limited"): If OTP was requested within the last 60 seconds
            OTPError("send_failed"): If SMS sending failed
        """
        phone = self._normalize_phone(phone)

        # 1. Check rate limit
        rate_key = self._key(purpose, tenant_id, phone, "rate")
        if await self.redis.exists(rate_key):
            raise OTPError(
                "Please wait before requesting another code",
                "rate_limited",
            )

        # 2. Generate OTP (cryptographically random)
        otp = "".join([str(secrets.randbelow(10)) for _ in range(self.OTP_LENGTH)])

        # 3. Store hashed OTP + attempts counter in Redis
        code_key = self._key(purpose, tenant_id, phone, "code")
        attempts_key = self._key(purpose, tenant_id, phone, "attempts")

        pipe = self.redis.pipeline()
        pipe.setex(code_key, self.OTP_EXPIRY_SECONDS, self._hash_otp(otp))
        pipe.setex(attempts_key, self.OTP_EXPIRY_SECONDS, "0")
        pipe.setex(rate_key, self.RATE_LIMIT_SECONDS, "1")
        await pipe.execute()

        # 4. Send SMS via Arkesel
        if purpose == OTPPurpose.PHONE_VERIFICATION:
            message = (
                f"Your {school_name} phone verification code is: {otp}. "
                f"Valid for 10 minutes."
            )
        else:
            message = (
                f"Your {school_name} password reset code is: {otp}. "
                f"Valid for 10 minutes. If you did not request this, ignore this message."
            )

        try:
            result = await _sms_client.send_sms(phone, message)

            # ArkeselClient.send_sms returns a dict, not raising on failure
            if not result["success"]:
                raise RuntimeError(result.get("error", "SMS sending failed"))

            logger.info(
                "otp_sent",
                purpose=purpose.value,
                tenant_id=str(tenant_id),
                phone_last4=phone[-4:],
            )
            return True

        except Exception as e:
            # Clean up Redis keys on send failure (don't lock user out)
            await self.redis.delete(code_key, attempts_key, rate_key)
            logger.error(
                "otp_send_failed",
                purpose=purpose.value,
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise OTPError("Failed to send verification code", "send_failed")

    async def verify(
        self,
        phone: str,
        code: str,
        purpose: OTPPurpose,
        tenant_id: UUID,
    ) -> bool:
        """
        Verify an OTP code.

        Increments attempt counter on failure. Deletes all keys on success.

        Args:
            phone: Phone number the OTP was sent to
            code: 6-digit code entered by user
            purpose: Must match the purpose used during generation
            tenant_id: Must match the tenant used during generation

        Returns:
            True if code is valid.

        Raises:
            OTPError("expired"): If no OTP exists for this phone/purpose
            OTPError("max_attempts"): If 5 failed attempts have been made
            OTPError("invalid"): If the code is wrong
        """
        phone = self._normalize_phone(phone)

        code_key = self._key(purpose, tenant_id, phone, "code")
        attempts_key = self._key(purpose, tenant_id, phone, "attempts")

        # 1. Check if OTP exists
        stored_hash = await self.redis.get(code_key)
        if not stored_hash:
            raise OTPError(
                "Verification code expired or not found",
                "expired",
            )

        # 2. Check attempt count
        attempts = int(await self.redis.get(attempts_key) or "0")
        if attempts >= self.MAX_ATTEMPTS:
            # Clean up — force user to request a new OTP
            await self.redis.delete(code_key, attempts_key)
            raise OTPError(
                "Too many failed attempts. Please request a new code.",
                "max_attempts",
            )

        # 3. Verify hash
        if self._hash_otp(code) != stored_hash:
            await self.redis.incr(attempts_key)
            remaining = self.MAX_ATTEMPTS - attempts - 1
            logger.info(
                "otp_verify_failed",
                purpose=purpose.value,
                tenant_id=str(tenant_id),
                phone_last4=phone[-4:],
                attempts_remaining=remaining,
            )
            raise OTPError("Invalid verification code", "invalid")

        # 4. Success — clean up all keys
        rate_key = self._key(purpose, tenant_id, phone, "rate")
        await self.redis.delete(code_key, attempts_key, rate_key)

        logger.info(
            "otp_verified",
            purpose=purpose.value,
            tenant_id=str(tenant_id),
            phone_last4=phone[-4:],
        )
        return True

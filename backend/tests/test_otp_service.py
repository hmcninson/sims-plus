"""
Tests for the shared OTP service.

Phase 1B: OTP generation, storage, verification, rate limiting,
cross-tenant isolation, and phone normalization.

Uses fakeredis for Redis operations and patches ArkeselClient.send_sms.
"""

import hashlib
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis

from app.services.otp import OTPService, OTPPurpose, OTPError


@pytest_asyncio.fixture
async def redis():
    """Fresh fakeredis instance per test."""
    r = FakeRedis(decode_responses=True)
    yield r
    await r.flushall()
    await r.aclose()


@pytest.fixture
def otp_service(redis):
    """OTP service wired to fakeredis."""
    return OTPService(redis)


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def phone():
    return "+233241234567"


def _mock_sms_success():
    """Patch ArkeselClient.send_sms to return success without sending."""
    return patch(
        "app.services.otp._sms_client.send_sms",
        new_callable=AsyncMock,
        return_value={"success": True, "message_id": "test-123"},
    )


def _mock_sms_failure():
    """Patch ArkeselClient.send_sms to simulate failure."""
    return patch(
        "app.services.otp._sms_client.send_sms",
        new_callable=AsyncMock,
        return_value={"success": False, "error": "Gateway unavailable"},
    )


class TestOTPGeneration:
    @pytest.mark.asyncio
    async def test_generate_otp_returns_true(self, otp_service, phone, tenant_id):
        """OTP generation should succeed with valid phone and tenant."""
        with _mock_sms_success():
            result = await otp_service.generate_and_send(
                phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_otp_stored_hashed_in_redis(self, otp_service, redis, phone, tenant_id):
        """OTP should be hashed (SHA-256) before Redis storage, not plaintext."""
        with _mock_sms_success():
            await otp_service.generate_and_send(
                phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )

        code_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "code"
        )
        stored = await redis.get(code_key)
        # SHA-256 produces 64 hex chars, not 6 digits
        assert stored is not None
        assert len(stored) == 64
        assert not stored.isdigit()

    @pytest.mark.asyncio
    async def test_otp_redis_keys_tenant_scoped(self, otp_service, redis, phone, tenant_id):
        """Redis keys should include tenant_id."""
        with _mock_sms_success():
            await otp_service.generate_and_send(
                phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )

        expected_prefix = f"otp:phone_verify:{tenant_id}:{phone}"
        code_key = f"{expected_prefix}:code"
        assert await redis.exists(code_key)

    @pytest.mark.asyncio
    async def test_otp_is_6_digits(self, otp_service, redis, phone, tenant_id):
        """Generated OTP should be exactly 6 digits (verified via hash match)."""
        # We can't directly read the OTP from Redis (it's hashed).
        # Instead, verify that a 6-digit code can match the stored hash.
        captured_otp = None

        original_send = AsyncMock(return_value={"success": True, "message_id": "x"})
        with patch("app.services.otp._sms_client.send_sms", original_send):
            await otp_service.generate_and_send(
                phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )
            # Extract OTP from the SMS message arg
            call_args = original_send.call_args
            message = call_args[0][1]  # second positional arg is message
            # Message format: "Your ... code is: 123456. Valid..."
            otp_str = message.split("code is: ")[1].split(".")[0]
            captured_otp = otp_str

        assert len(captured_otp) == 6
        assert captured_otp.isdigit()

    @pytest.mark.asyncio
    async def test_otp_expires_after_10_minutes(self, otp_service, redis, phone, tenant_id):
        """Redis TTL should be 600 seconds (10 minutes)."""
        with _mock_sms_success():
            await otp_service.generate_and_send(
                phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )

        code_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "code"
        )
        ttl = await redis.ttl(code_key)
        assert 590 <= ttl <= 600


class TestOTPRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_1_per_minute(self, otp_service, phone, tenant_id):
        """Second OTP request within 60 seconds should raise rate_limited."""
        with _mock_sms_success():
            await otp_service.generate_and_send(
                phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )

        with _mock_sms_success():
            with pytest.raises(OTPError) as exc_info:
                await otp_service.generate_and_send(
                    phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                    tenant_id=tenant_id,
                )
            assert exc_info.value.code == "rate_limited"


class TestOTPVerification:
    async def _generate_and_capture_otp(self, otp_service, phone, tenant_id, purpose=OTPPurpose.PHONE_VERIFICATION):
        """Helper: generate OTP and capture the 6-digit code from the SMS message."""
        mock_send = AsyncMock(return_value={"success": True, "message_id": "x"})
        with patch("app.services.otp._sms_client.send_sms", mock_send):
            await otp_service.generate_and_send(
                phone=phone, purpose=purpose, tenant_id=tenant_id,
            )
            message = mock_send.call_args[0][1]
            return message.split("code is: ")[1].split(".")[0]

    @pytest.mark.asyncio
    async def test_verify_correct_code(self, otp_service, phone, tenant_id):
        """Correct OTP should verify successfully."""
        otp = await self._generate_and_capture_otp(otp_service, phone, tenant_id)
        result = await otp_service.verify(phone, otp, OTPPurpose.PHONE_VERIFICATION, tenant_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_incorrect_code(self, otp_service, phone, tenant_id):
        """Incorrect OTP should raise invalid error."""
        await self._generate_and_capture_otp(otp_service, phone, tenant_id)
        with pytest.raises(OTPError) as exc_info:
            await otp_service.verify(phone, "000000", OTPPurpose.PHONE_VERIFICATION, tenant_id)
        assert exc_info.value.code == "invalid"

    @pytest.mark.asyncio
    async def test_verify_increments_attempts(self, otp_service, redis, phone, tenant_id):
        """Each failed verification should increment attempt counter."""
        await self._generate_and_capture_otp(otp_service, phone, tenant_id)
        attempts_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "attempts"
        )

        # First failed attempt
        with pytest.raises(OTPError):
            await otp_service.verify(phone, "000000", OTPPurpose.PHONE_VERIFICATION, tenant_id)
        assert await redis.get(attempts_key) == "1"

        # Second failed attempt
        with pytest.raises(OTPError):
            await otp_service.verify(phone, "111111", OTPPurpose.PHONE_VERIFICATION, tenant_id)
        assert await redis.get(attempts_key) == "2"

    @pytest.mark.asyncio
    async def test_max_5_attempts(self, otp_service, redis, phone, tenant_id):
        """After 5 failed attempts, should raise max_attempts and delete OTP."""
        await self._generate_and_capture_otp(otp_service, phone, tenant_id)

        # Make 5 failed attempts
        for i in range(5):
            with pytest.raises(OTPError) as exc_info:
                await otp_service.verify(phone, "000000", OTPPurpose.PHONE_VERIFICATION, tenant_id)
            if i < 4:
                assert exc_info.value.code == "invalid"

        # 6th attempt should get max_attempts
        with pytest.raises(OTPError) as exc_info:
            await otp_service.verify(phone, "000000", OTPPurpose.PHONE_VERIFICATION, tenant_id)
        # After 5 failed, keys are deleted, so next verify gets "expired"
        assert exc_info.value.code in ("max_attempts", "expired")

    @pytest.mark.asyncio
    async def test_verify_expired_otp(self, otp_service, redis, phone, tenant_id):
        """Expired OTP should raise expired error."""
        await self._generate_and_capture_otp(otp_service, phone, tenant_id)
        # Delete Redis keys to simulate expiry
        code_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "code"
        )
        await redis.delete(code_key)

        with pytest.raises(OTPError) as exc_info:
            await otp_service.verify(phone, "123456", OTPPurpose.PHONE_VERIFICATION, tenant_id)
        assert exc_info.value.code == "expired"

    @pytest.mark.asyncio
    async def test_verify_deletes_keys_on_success(self, otp_service, redis, phone, tenant_id):
        """Successful verification should delete all Redis keys for this OTP."""
        otp = await self._generate_and_capture_otp(otp_service, phone, tenant_id)
        await otp_service.verify(phone, otp, OTPPurpose.PHONE_VERIFICATION, tenant_id)

        code_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "code"
        )
        attempts_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "attempts"
        )
        rate_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "rate"
        )
        assert not await redis.exists(code_key)
        assert not await redis.exists(attempts_key)
        assert not await redis.exists(rate_key)

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self, otp_service, phone):
        """OTP from tenant A should not verify in tenant B."""
        tenant_a = uuid4()
        tenant_b = uuid4()

        otp = await self._generate_and_capture_otp(otp_service, phone, tenant_a)

        # Should fail when verifying with tenant B
        with pytest.raises(OTPError) as exc_info:
            await otp_service.verify(phone, otp, OTPPurpose.PHONE_VERIFICATION, tenant_b)
        assert exc_info.value.code == "expired"  # No OTP exists for tenant_b


class TestOTPPhoneNormalization:
    def test_normalize_local_ghana_format(self):
        """Phone '0241234567' should be normalized to '+233241234567'."""
        assert OTPService._normalize_phone("0241234567") == "+233241234567"

    def test_normalize_strips_spaces_and_dashes(self):
        """Phone '+233 24-123-4567' should be normalized to '+233241234567'."""
        assert OTPService._normalize_phone("+233 24-123-4567") == "+233241234567"

    @pytest.mark.asyncio
    async def test_otp_matches_after_normalization(self, otp_service, tenant_id):
        """OTP sent to '0241234567' should verify with '+233241234567'."""
        local_phone = "0241234567"
        intl_phone = "+233241234567"

        mock_send = AsyncMock(return_value={"success": True, "message_id": "x"})
        with patch("app.services.otp._sms_client.send_sms", mock_send):
            await otp_service.generate_and_send(
                phone=local_phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                tenant_id=tenant_id,
            )
            message = mock_send.call_args[0][1]
            otp = message.split("code is: ")[1].split(".")[0]

        # Verify with international format
        result = await otp_service.verify(
            intl_phone, otp, OTPPurpose.PHONE_VERIFICATION, tenant_id
        )
        assert result is True


class TestOTPSendFailure:
    @pytest.mark.asyncio
    async def test_sms_failure_cleans_up_redis(self, otp_service, redis, phone, tenant_id):
        """If SMS sending fails, Redis keys should be cleaned up."""
        with _mock_sms_failure():
            with pytest.raises(OTPError) as exc_info:
                await otp_service.generate_and_send(
                    phone=phone, purpose=OTPPurpose.PHONE_VERIFICATION,
                    tenant_id=tenant_id,
                )
            assert exc_info.value.code == "send_failed"

        # Verify no orphaned Redis keys
        code_key = otp_service._key(
            OTPPurpose.PHONE_VERIFICATION, tenant_id, phone, "code"
        )
        assert not await redis.exists(code_key)

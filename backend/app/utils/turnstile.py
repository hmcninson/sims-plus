"""
SIMS Plus - Cloudflare Turnstile CAPTCHA Verification

Verifies Turnstile tokens to prevent bot submissions on public forms.
In development (TURNSTILE_SECRET_KEY not set), verification is skipped.

FAIL CLOSED: any network or parsing error returns False. The applicant
can simply retry — this is a deliberate trade-off to prevent automated
abuse of the public application form.
"""

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str, remote_ip: str | None = None) -> bool:
    """
    Verify a Cloudflare Turnstile token.

    Args:
        token: The turnstile response token from the frontend widget.
        remote_ip: Optional client IP for additional validation.

    Returns:
        True if the token is valid, False otherwise.
        Returns True in development when TURNSTILE_SECRET_KEY is not configured.
    """
    if not settings.TURNSTILE_SECRET_KEY:
        logger.warning("turnstile_skipped", reason="TURNSTILE_SECRET_KEY not configured")
        return True

    try:
        payload: dict[str, str] = {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
        }
        if remote_ip:
            payload["remoteip"] = remote_ip

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data=payload,
            )
            result = response.json()
            success = result.get("success", False)

            if not success:
                logger.warning(
                    "turnstile_verification_failed",
                    error_codes=result.get("error-codes", []),
                )

            return success

    except httpx.TimeoutException:
        logger.error("turnstile_timeout")
        # Fail CLOSED — reject submission, applicant can retry
        return False
    except Exception:
        logger.exception("turnstile_error")
        # Fail CLOSED in production — reject submission, applicant can retry.
        # Rate limiting alone is not sufficient against distributed attacks.
        return False

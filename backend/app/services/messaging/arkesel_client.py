"""
SIMS Plus - Arkesel SMS Client

HTTP client for the Arkesel SMS gateway (sms.arkesel.com).
Uses httpx for async HTTP requests with API key authentication.

Arkesel API V2 docs: https://developers.arkesel.com/

Replaces HubtelClient as the primary SMS provider.
Maintains the same return interface: {success, message_id, error}
"""

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class ArkeselClient:
    """Async HTTP client for Arkesel SMS gateway (V2 API)."""

    BASE_URL = "https://sms.arkesel.com"

    def __init__(self) -> None:
        self.api_key = settings.ARKESEL_API_KEY
        self.sender_id = settings.ARKESEL_SENDER_ID
        self.sandbox = settings.ARKESEL_SANDBOX
        self.callback_url = settings.ARKESEL_CALLBACK_URL

    @property
    def is_configured(self) -> bool:
        """True when Arkesel API key is present."""
        return bool(self.api_key)

    async def send_sms(
        self,
        to: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        """
        Send a single SMS via Arkesel V2 API.

        Args:
            to: Destination phone number (e.g., "+233241234567" or "0241234567").
            message: SMS body text.
            sender_id: Override the default sender ID for this message.

        Returns:
            Dict with keys: success (bool), message_id (str|None), error (str|None).
            Same interface as the previous HubtelClient for drop-in replacement.
        """
        if not self.is_configured:
            logger.warning("arkesel_not_configured")
            return {
                "success": False,
                "message_id": None,
                "error": "Arkesel API key not configured",
            }

        effective_sender = sender_id or self.sender_id

        # Build request payload
        payload: dict = {
            "sender": effective_sender,
            "message": message,
            "recipients": [to],
        }

        # Add optional parameters
        if self.sandbox:
            payload["sandbox"] = True
        if self.callback_url:
            payload["callback_url"] = self.callback_url

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/api/v2/sms/send",
                    json=payload,
                    headers={
                        "api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    # Extract message ID from first recipient
                    recipients_data = data.get("data", [])
                    message_id = (
                        recipients_data[0].get("id")
                        if recipients_data
                        else None
                    )
                    logger.info(
                        "arkesel_sms_sent",
                        to_last4=to[-4:],
                        message_id=message_id,
                        sender=effective_sender,
                    )
                    return {
                        "success": True,
                        "message_id": message_id,
                        "error": None,
                    }
                else:
                    # API returned 200 but status is not "success"
                    error_msg = data.get("message", "Unknown error")
                    logger.error(
                        "arkesel_send_failed",
                        to_last4=to[-4:],
                        status="api_error",
                        error=error_msg,
                    )
                    return {
                        "success": False,
                        "message_id": None,
                        "error": "SMS sending failed",
                    }

            elif response.status_code == 402:
                logger.error("arkesel_insufficient_balance", to_last4=to[-4:])
                return {
                    "success": False,
                    "message_id": None,
                    "error": "SMS service temporarily unavailable",
                }

            elif response.status_code == 403:
                logger.error("arkesel_auth_failed", status=response.status_code)
                return {
                    "success": False,
                    "message_id": None,
                    "error": "SMS service configuration error",
                }

            elif response.status_code == 422:
                logger.error(
                    "arkesel_validation_error",
                    status=response.status_code,
                    to_last4=to[-4:],
                )
                return {
                    "success": False,
                    "message_id": None,
                    "error": "SMS validation error",
                }

            else:
                # Sanitize error: never leak raw provider response to callers
                logger.error(
                    "arkesel_send_failed",
                    status=response.status_code,
                    to_last4=to[-4:],
                )
                return {
                    "success": False,
                    "message_id": None,
                    "error": f"SMS gateway returned status {response.status_code}",
                }

        except httpx.TimeoutException:
            logger.error("arkesel_timeout", to_last4=to[-4:])
            return {
                "success": False,
                "message_id": None,
                "error": "SMS gateway request timed out",
            }
        except Exception:
            # Sanitize: log the full exception but return a generic message
            logger.exception("arkesel_unexpected_error", to_last4=to[-4:])
            return {
                "success": False,
                "message_id": None,
                "error": "SMS sending failed unexpectedly",
            }

    async def send_bulk(
        self,
        recipients: list[str],
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        """
        Send SMS to multiple recipients in a single API call.

        Arkesel V2 natively supports multiple recipients in one request.

        Args:
            recipients: List of phone numbers.
            message: SMS body text (same message to all).
            sender_id: Override the default sender ID.

        Returns:
            Dict with keys: success (bool), results (list), error (str|None).
        """
        if not self.is_configured:
            logger.warning("arkesel_not_configured")
            return {
                "success": False,
                "results": [],
                "error": "Arkesel API key not configured",
            }

        effective_sender = sender_id or self.sender_id

        payload: dict = {
            "sender": effective_sender,
            "message": message,
            "recipients": recipients,
        }

        if self.sandbox:
            payload["sandbox"] = True
        if self.callback_url:
            payload["callback_url"] = self.callback_url

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/api/v2/sms/send",
                    json=payload,
                    headers={
                        "api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=60.0,  # Longer timeout for bulk
                )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    logger.info(
                        "arkesel_bulk_sms_sent",
                        recipient_count=len(recipients),
                        sender=effective_sender,
                    )
                    return {
                        "success": True,
                        "results": data.get("data", []),
                        "error": None,
                    }

            logger.error(
                "arkesel_bulk_send_failed",
                status=response.status_code,
                recipient_count=len(recipients),
            )
            return {
                "success": False,
                "results": [],
                "error": "Bulk SMS sending failed",
            }

        except httpx.TimeoutException:
            logger.error("arkesel_bulk_timeout", recipient_count=len(recipients))
            return {
                "success": False,
                "results": [],
                "error": "SMS gateway request timed out",
            }
        except Exception:
            logger.exception("arkesel_bulk_unexpected_error")
            return {
                "success": False,
                "results": [],
                "error": "Bulk SMS sending failed unexpectedly",
            }

    async def check_balance(self) -> dict:
        """
        Check Arkesel SMS balance.

        Returns:
            Dict with keys: success (bool), sms_balance (str|None),
            main_balance (str|None), error (str|None).
        """
        if not self.is_configured:
            return {
                "success": False,
                "sms_balance": None,
                "main_balance": None,
                "error": "Arkesel API key not configured",
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/api/v2/clients/balance-details",
                    headers={"api-key": self.api_key},
                    timeout=15.0,
                )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    balance_data = data.get("data", {})
                    return {
                        "success": True,
                        "sms_balance": balance_data.get("sms_balance"),
                        "main_balance": balance_data.get("main_balance"),
                        "error": None,
                    }

            return {
                "success": False,
                "sms_balance": None,
                "main_balance": None,
                "error": "Failed to check balance",
            }

        except Exception:
            logger.exception("arkesel_balance_check_failed")
            return {
                "success": False,
                "sms_balance": None,
                "main_balance": None,
                "error": "Balance check failed",
            }

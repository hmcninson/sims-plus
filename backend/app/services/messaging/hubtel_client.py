"""
SIMS Plus - Hubtel SMS Client

HTTP client for the Hubtel SMS gateway (smsc.hubtel.com).
Uses httpx for async HTTP requests with timeout and error handling.
Uses HTTP Basic Auth to avoid leaking credentials in URL query parameters.

Hubtel API docs: https://developers.hubtel.com/docs/sms-sending
"""

import base64

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class HubtelClient:
    """Async HTTP client for Hubtel SMS gateway."""

    BASE_URL = "https://smsc.hubtel.com/v1/messages/send"

    def __init__(self) -> None:
        self.client_id = settings.HUBTEL_CLIENT_ID
        self.client_secret = settings.HUBTEL_CLIENT_SECRET
        self.sender_id = settings.HUBTEL_SENDER_ID

    @property
    def is_configured(self) -> bool:
        """True when Hubtel credentials are present."""
        return bool(self.client_id and self.client_secret)

    async def send_sms(
        self,
        to: str,
        message: str,
        sender_id: str | None = None,
    ) -> dict:
        """
        Send a single SMS via Hubtel.

        Args:
            to: Destination phone number (e.g., "+233241234567" or "0241234567").
            message: SMS body text.
            sender_id: Override the default sender ID for this message.

        Returns:
            Dict with keys: success (bool), message_id (str|None), error (str|None).
        """
        if not self.is_configured:
            logger.warning("hubtel_not_configured")
            return {
                "success": False,
                "message_id": None,
                "error": "Hubtel credentials not configured",
            }

        effective_sender = sender_id or self.sender_id

        try:
            # Use HTTP Basic Auth instead of query params to avoid
            # credentials appearing in URL logs, proxies, and monitoring tools.
            auth_str = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.BASE_URL,
                    params={
                        "from": effective_sender,
                        "to": to,
                        "content": message,
                    },
                    headers={"Authorization": f"Basic {auth_str}"},
                    timeout=30.0,
                )

            if response.status_code == 200:
                data = response.json()
                message_id = data.get("MessageId") or data.get("messageid")
                logger.info(
                    "hubtel_sms_sent",
                    to=to,
                    message_id=message_id,
                    sender=effective_sender,
                )
                return {
                    "success": True,
                    "message_id": message_id,
                    "error": None,
                }
            elif response.status_code == 401:
                logger.error("hubtel_auth_failed", status=response.status_code)
                return {
                    "success": False,
                    "message_id": None,
                    "error": "Hubtel authentication failed",
                }
            else:
                # Sanitize error: never leak raw provider response to callers
                logger.error(
                    "hubtel_send_failed",
                    status=response.status_code,
                    to=to,
                )
                return {
                    "success": False,
                    "message_id": None,
                    "error": f"SMS gateway returned status {response.status_code}",
                }

        except httpx.TimeoutException:
            logger.error("hubtel_timeout", to=to)
            return {
                "success": False,
                "message_id": None,
                "error": "SMS gateway request timed out",
            }
        except Exception:
            # Sanitize: log the full exception but return a generic message
            logger.exception("hubtel_unexpected_error", to=to)
            return {
                "success": False,
                "message_id": None,
                "error": "SMS sending failed unexpectedly",
            }

# Pre-requisite: Arkesel SMS Migration (Hubtel → Arkesel)

**Complexity:** Small-Medium
**Dependencies:** None (must be done before Phase 1B OTP)
**Estimated effort:** 1 day

---

## Summary

Replace Hubtel as the primary SMS gateway with Arkesel. The existing `HubtelClient` will be replaced by an `ArkeselClient` that implements the same interface. All callers (SMS service, notification dispatcher, admissions notifications, OTP service) will use Arkesel.

This is a clean break — all Hubtel code, config, and enum values are removed entirely. We are pre-MVP so there are no historical logs to preserve.

---

## Arkesel API Reference

**Base URL:** `https://sms.arkesel.com`
**API Version:** V2 (recommended)
**Authentication:** `api-key` header
**Docs:** https://developers.arkesel.com/

### Send SMS (V2)

```
POST https://sms.arkesel.com/api/v2/sms/send

Headers:
  api-key: YOUR_API_KEY

Body (JSON):
{
    "sender": "SIMSPlus",
    "message": "Your verification code is: 123456",
    "recipients": ["+233241234567"]
}

Success Response (200):
{
    "status": "success",
    "data": [
        {"recipient": "233241234567", "id": "uuid-message-id"}
    ]
}

Error Responses:
  402: Insufficient balance
  403: Invalid API key
  422: Validation error
  500: Server error

{
    "status": "error",
    "message": "Error description"
}
```

### Optional Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `scheduled_date` | string | Schedule delivery: `"YYYY-MM-DD HH:MM AM/PM"` |
| `callback_url` | string | Webhook URL for delivery reports |
| `sandbox` | boolean | Test mode (no billing) |

### Check Balance

```
GET https://sms.arkesel.com/api/v2/clients/balance-details

Headers:
  api-key: YOUR_API_KEY

Response:
{
    "status": "success",
    "data": {
        "sms_balance": "2003",
        "main_balance": "GHS 20.99"
    }
}
```

### Get Message Status

```
GET https://sms.arkesel.com/api/v2/sms/{message_id}

Headers:
  api-key: YOUR_API_KEY
```

---

## Task 1: Update Configuration

### File: `backend/app/config.py`

**Replace Hubtel settings with Arkesel:**

```python
# BEFORE (lines 123-129):
# =========================
# SMS (Hubtel)
# =========================
HUBTEL_CLIENT_ID: str | None = None
HUBTEL_CLIENT_SECRET: str | None = None
HUBTEL_SENDER_ID: str = "SIMSPlus"
HUBTEL_MERCHANT_ACCOUNT: str | None = None

# AFTER:
# =========================
# SMS (Arkesel)
# =========================
ARKESEL_API_KEY: str | None = None
ARKESEL_SENDER_ID: str = "SIMSPlus"
ARKESEL_SANDBOX: bool = False        # True for development/testing
ARKESEL_CALLBACK_URL: str | None = None  # Optional delivery report webhook
```

**Delete the Hubtel settings entirely** — no legacy/backwards-compat needed (pre-MVP).

### File: `.env.example`

Add:
```
# SMS (Arkesel)
ARKESEL_API_KEY=
ARKESEL_SENDER_ID=SIMSPlus
ARKESEL_SANDBOX=false
```

---

## Task 2: Create Arkesel Client

### New File: `backend/app/services/messaging/arkesel_client.py`

```python
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
        payload = {
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
                    "error": "SMS balance insufficient",
                }

            elif response.status_code == 403:
                logger.error("arkesel_auth_failed", status=response.status_code)
                return {
                    "success": False,
                    "message_id": None,
                    "error": "Arkesel authentication failed",
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

        payload = {
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
                "error": f"Bulk SMS failed with status {response.status_code}",
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
```

---

## Task 3: Update Messaging Package Exports

### File: `backend/app/services/messaging/__init__.py`

```python
"""
SIMS Plus - Messaging Service Package

Provides recipient resolution, Arkesel SMS integration, and email
composition with logging for the communication module.
"""

from app.services.messaging.recipient_resolver import RecipientResolver
from app.services.messaging.arkesel_client import ArkeselClient
from app.services.messaging.email_compose import EmailComposeService

__all__ = [
    "RecipientResolver",
    "ArkeselClient",
    "EmailComposeService",
]
```

---

## Task 4: Update SMS Service

### File: `backend/app/services/sms.py`

**Changes:**

```python
# BEFORE (line 21-26):
from app.services.messaging.hubtel_client import HubtelClient
# ...
_hubtel_client = HubtelClient()

# AFTER:
from app.services.messaging.arkesel_client import ArkeselClient
# ...
_sms_client = ArkeselClient()
```

**Update `send_sms()` method (around line 84-85):**

```python
# BEFORE:
if provider == SMSProvider.HUBTEL and _hubtel_client.is_configured:
    result = await _hubtel_client.send_sms(

# AFTER:
if _sms_client.is_configured:
    result = await _sms_client.send_sms(
```

**Update the provider default:**

```python
# BEFORE (line 49):
provider: SMSProvider = SMSProvider.HUBTEL,

# AFTER:
provider: SMSProvider = SMSProvider.ARKESEL,
```

**Same for bulk (line 116):**

```python
# BEFORE:
provider: SMSProvider = SMSProvider.HUBTEL,

# AFTER:
provider: SMSProvider = SMSProvider.ARKESEL,
```

**Update the log entry provider:**

When creating `SMSLog` entries, set `provider=SMSProvider.ARKESEL` instead of `SMSProvider.HUBTEL`.

---

## Task 5: Update Admissions Notification Service

### File: `backend/app/services/admissions/notification_service.py`

**Change the SMS import (around line 293-295):**

```python
# BEFORE:
from app.services.messaging.hubtel_client import HubtelClient
# ...
client = HubtelClient()

# AFTER:
from app.services.messaging.arkesel_client import ArkeselClient
# ...
client = ArkeselClient()
```

The `send_sms(to, message, sender_id)` interface is identical, so no other changes needed.

---

## Task 6: Update Notification Dispatcher

### File: `backend/app/services/notification_dispatcher.py`

Check if this file imports `HubtelClient` directly or uses `SMSService`. If it uses `SMSService`, no changes needed (the service handles the client internally). If it imports `HubtelClient` directly, update the import.

---

## Task 7: Update SMS Model Default

### File: `backend/app/models/sms.py`

**Change the default provider (around line 50):**

```python
# BEFORE:
default=SMSProvider.HUBTEL,

# AFTER:
default=SMSProvider.ARKESEL,
```

**Update the Python enum** to add `arkesel` and keep the old values (harmless dead values are safer than destructive ALTER TYPE):

```python
class SMSProvider(str, Enum):
    ARKESEL = "arkesel"
    HUBTEL = "hubtel"    # Dead value — kept to avoid destructive enum migration
    TWILIO = "twilio"    # Dead value — kept to avoid destructive enum migration
```

**Database enum migration:** Create a **separate** migration file `20260324_0100_arkesel_migration.py` (revises: `20260322_0300`). This uses the COMMIT/BEGIN pattern for ALTER TYPE ADD VALUE:

```python
"""Add arkesel to smsprovider enum and update default.

Revision ID: 20260324_0100
Revises: 20260322_0300
"""
from alembic import op
import sqlalchemy as sa

revision = "20260324_0100"
down_revision = "20260322_0300"

def upgrade() -> None:
    # Add 'arkesel' to the smsprovider enum (COMMIT/BEGIN required for ALTER TYPE ADD VALUE)
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE smsprovider ADD VALUE IF NOT EXISTS 'arkesel'"))
    connection.execute(sa.text("BEGIN"))

    # Update the default to arkesel
    op.execute("ALTER TABLE sms_log ALTER COLUMN provider SET DEFAULT 'arkesel'")

def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL — just revert the default
    op.execute("ALTER TABLE sms_log ALTER COLUMN provider SET DEFAULT 'hubtel'")
```

**NOTE:** We intentionally keep the old `hubtel` and `twilio` enum values in the database. Keeping dead enum values is safer than destructive ALTER TYPE (per Risk Analyst recommendation). The old values are harmless — no application code references them, and removing them requires a destructive enum recreation that risks data loss if any rows still reference the old values.

---

## Task 8: Update Tests

### File: `backend/tests/test_sms_messaging.py`

**Update mocks (around line 468):**

```python
# BEFORE:
with patch("app.services.sms._hubtel_client") as mock_hubtel:

# AFTER:
with patch("app.services.sms._sms_client") as mock_arkesel:
```

Update all test assertions that reference "hubtel" to reference "arkesel".

---

## Task 9: Delete Hubtel Client File

**Delete** `backend/app/services/messaging/hubtel_client.py` entirely. We are pre-MVP — no need to keep dead code.

---

## Impact on Phase 1B (OTP Service)

The OTP service (`02-phase-1b-otp-phone-verification.md`) already references `ArkeselClient`. The interface is identical (`send_sms(to, message, sender_id)` → `{success, message_id, error}`), so no additional changes needed.

---

## Environment Variables Summary

### Remove from all environments:
```
HUBTEL_CLIENT_ID
HUBTEL_CLIENT_SECRET
HUBTEL_SENDER_ID
HUBTEL_MERCHANT_ACCOUNT
```

### Add to all environments:
```
ARKESEL_API_KEY=your_arkesel_api_key_here
ARKESEL_SENDER_ID=SIMSPlus
ARKESEL_SANDBOX=false
```

---

## Verification Checklist

- [ ] ArkeselClient sends SMS successfully (test with sandbox=true)
- [ ] ArkeselClient returns `{success, message_id, error}` interface
- [ ] SMS service uses ArkeselClient
- [ ] Admissions notification service uses ArkeselClient
- [ ] SMS log entries have `provider=arkesel`
- [ ] `hubtel_client.py` deleted
- [ ] No Hubtel references remain in codebase (config, imports, env vars)
- [ ] `SMSProvider` enum only has `arkesel`
- [ ] Balance check endpoint works
- [ ] Bulk send works via Arkesel native multi-recipient
- [ ] Sandbox mode works for development
- [ ] Graceful degradation when ARKESEL_API_KEY is not set
- [ ] Error responses sanitized (no raw Arkesel errors leaked to callers)
- [ ] All existing SMS tests pass with updated mocks
- [ ] OTP service (Phase 1B) uses ArkeselClient

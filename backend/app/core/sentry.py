"""
SIMS Plus - Sentry Integration

Configures Sentry error tracking with tenant data scrubbing to prevent
sensitive multi-tenant information from leaking into external services.
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import settings


def init_sentry():
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,
            environment=settings.ENVIRONMENT,  # "development", "staging", "production"
            # CRITICAL: Never auto-collect PII (emails, IPs, usernames)
            send_default_pii=False,
            # Scrub any remaining sensitive data from events
            before_send=scrub_tenant_data,
        )


# Body keys that contain credentials or tokens and must never reach Sentry
_SENSITIVE_BODY_KEYS = frozenset({
    "password",
    "current_password",
    "new_password",
    "confirm_password",
    "token",
    "refresh_token",
    "access_token",
})


def scrub_tenant_data(event, hint):
    """Remove sensitive tenant and authentication data from Sentry events.

    This is defense-in-depth on top of send_default_pii=False. We explicitly
    strip anything that could leak credentials, session tokens, or PII that
    could identify students across tenants.
    """
    # Remove user context entirely -- tenant user IDs are internal
    event.pop("user", None)

    if "request" in event:
        request = event["request"]

        # Strip headers that carry auth tokens
        headers = request.get("headers", {})
        headers.pop("authorization", None)
        headers.pop("Authorization", None)
        # Cookies may contain refresh tokens (HttpOnly)
        headers.pop("cookie", None)
        headers.pop("Cookie", None)

        # Query strings may contain student names or search terms
        request.pop("query_string", None)

        # Scrub sensitive keys from request body (JSON data dict)
        data = request.get("data")
        if isinstance(data, dict):
            for key in _SENSITIVE_BODY_KEYS:
                if key in data:
                    data[key] = "[Filtered]"

    return event

"""
Tests for Paystack subscription webhook handling.

Covers: signature verification, idempotency, intent validation,
addon purchase (no subscription date reset), and edge cases.
Uses two-engine pattern (admin seeds, app queries).
"""

import hashlib
import hmac
import json

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


def _make_webhook_payload(
    *, tenant_id, reference, target_tier="starter", billing_period="term",
    payment_type="subscription_upgrade", addons=None,
):
    """Build a Paystack charge.success webhook payload."""
    return {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 50000,
            "currency": "GHS",
            "metadata": {
                "tenant_id": str(tenant_id),
                "target_tier": target_tier,
                "billing_period": billing_period,
                "duration_days": 120,
                "student_count": 10,
                "addons": addons or [],
                "type": payment_type,
            },
        },
    }


def _sign_payload(payload_bytes, secret="test_webhook_secret"):
    """Compute HMAC-SHA512 signature."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha512).hexdigest()


async def _create_intent(
    admin_session, *, tenant_id, reference, target_tier="starter",
    amount=50000, billing_period="term", intent_type="upgrade", status="pending",
    addon_name=None,
):
    """Create a SubscriptionIntent directly via SQL."""
    intent_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO subscription_intents (
                id, tenant_id, reference, target_tier, amount,
                billing_period, intent_type, status, addon_name,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :ref, :tier, :amount,
                :period, :itype, :status, :addon,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(intent_id),
            "tid": str(tenant_id),
            "ref": reference,
            "tier": target_tier,
            "amount": amount,
            "period": billing_period,
            "itype": intent_type,
            "status": status,
            "addon": addon_name,
        },
    )
    await admin_session.commit()
    return intent_id


async def _table_exists(admin_session, table_name):
    """Check if a table exists in the database."""
    result = await admin_session.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_name = :name AND table_schema = 'public'
        """),
        {"name": table_name},
    )
    return result.fetchone() is not None


# --- Tests ---


class TestWebhookSignature:
    """Webhook HMAC-SHA512 signature verification."""

    async def test_valid_signature_accepted(self, app_session, admin_session):
        """Valid signature should not raise."""
        if not await _table_exists(admin_session, "subscription_intents"):
            pytest.skip("subscription_intents table not yet created")

        tenant = await create_test_tenant(admin_session)
        reference = f"sub_{uuid4().hex[:8]}"

        await _create_intent(
            admin_session, tenant_id=tenant["id"], reference=reference,
        )
        await set_app_tenant_context(app_session, tenant["id"])

        payload = _make_webhook_payload(
            tenant_id=tenant["id"], reference=reference,
        )
        body = json.dumps(payload).encode()
        sig = _sign_payload(body)

        from app.services.subscription import SubscriptionService
        from unittest.mock import patch

        service = SubscriptionService(app_session)
        with patch.object(
            type(service), "PAYSTACK_BASE_URL", "https://mock.test"
        ), patch("app.config.settings.PAYSTACK_WEBHOOK_SECRET", "test_webhook_secret"):
            await service.handle_webhook(body, sig)

    async def test_invalid_signature_rejected(self, app_session, admin_session):
        """Invalid signature should raise SubscriptionError."""
        if not await _table_exists(admin_session, "subscription_intents"):
            pytest.skip("subscription_intents table not yet created")

        payload = _make_webhook_payload(
            tenant_id=uuid4(), reference="fake_ref",
        )
        body = json.dumps(payload).encode()

        from app.services.subscription import SubscriptionService, SubscriptionError
        from unittest.mock import patch

        service = SubscriptionService(app_session)
        with patch("app.config.settings.PAYSTACK_WEBHOOK_SECRET", "test_webhook_secret"):
            with pytest.raises(SubscriptionError) as exc_info:
                await service.handle_webhook(body, "bad_signature")
            assert exc_info.value.code == "INVALID_SIGNATURE"


class TestWebhookIdempotency:
    """Webhook idempotency -- duplicate webhooks must not double-process."""

    async def test_duplicate_webhook_no_double_upgrade(self, app_session, admin_session):
        """Processing the same reference twice should skip the second time."""
        if not await _table_exists(admin_session, "subscription_intents"):
            pytest.skip("subscription_intents table not yet created")

        tenant = await create_test_tenant(admin_session)
        reference = f"sub_{uuid4().hex[:8]}"

        # Create intent that is already completed
        await _create_intent(
            admin_session, tenant_id=tenant["id"], reference=reference,
            status="completed",
        )
        await set_app_tenant_context(app_session, tenant["id"])

        payload = _make_webhook_payload(
            tenant_id=tenant["id"], reference=reference,
        )
        body = json.dumps(payload).encode()
        sig = _sign_payload(body)

        from app.services.subscription import SubscriptionService
        from unittest.mock import patch

        service = SubscriptionService(app_session)
        with patch("app.config.settings.PAYSTACK_WEBHOOK_SECRET", "test_webhook_secret"):
            # Should return silently without processing
            await service.handle_webhook(body, sig)

        # Verify intent is still completed (not re-processed)
        result = await admin_session.execute(
            text("SELECT status FROM subscription_intents WHERE reference = :ref"),
            {"ref": reference},
        )
        assert result.fetchone()[0] == "completed"


class TestWebhookIntentValidation:
    """Webhook must validate against stored SubscriptionIntent."""

    async def test_missing_intent_raises(self, app_session, admin_session):
        """Webhook with no matching intent should raise."""
        if not await _table_exists(admin_session, "subscription_intents"):
            pytest.skip("subscription_intents table not yet created")

        payload = _make_webhook_payload(
            tenant_id=uuid4(), reference="nonexistent_ref",
        )
        body = json.dumps(payload).encode()
        sig = _sign_payload(body)

        from app.services.subscription import SubscriptionService, SubscriptionError
        from unittest.mock import patch

        service = SubscriptionService(app_session)
        with patch("app.config.settings.PAYSTACK_WEBHOOK_SECRET", "test_webhook_secret"):
            with pytest.raises(SubscriptionError) as exc_info:
                await service.handle_webhook(body, sig)
            assert exc_info.value.code == "NO_INTENT"


class TestAddonPurchaseWebhook:
    """Add-on purchase must NOT reset subscription dates."""

    async def test_addon_purchase_preserves_subscription_dates(
        self, app_session, admin_session
    ):
        """Add-on purchase should not change subscription_start or subscription_end."""
        if not await _table_exists(admin_session, "subscription_intents"):
            pytest.skip("subscription_intents table not yet created")

        tenant = await create_test_tenant(admin_session)
        reference = f"addon_{uuid4().hex[:8]}"

        # Set tenant to active professional with existing dates
        await admin_session.execute(
            text("""
                UPDATE tenants
                SET subscription_tier = 'professional',
                    status = 'active',
                    subscription_start = '2026-01-01',
                    subscription_end = '2026-12-31'
                WHERE id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant["id"])},
        )
        await admin_session.commit()

        await _create_intent(
            admin_session,
            tenant_id=tenant["id"],
            reference=reference,
            target_tier="addon",
            intent_type="addon_purchase",
            addon_name="boarding",
        )
        await set_app_tenant_context(app_session, tenant["id"])

        payload = _make_webhook_payload(
            tenant_id=tenant["id"],
            reference=reference,
            payment_type="addon_purchase",
            addons=["boarding"],
        )
        body = json.dumps(payload).encode()
        sig = _sign_payload(body)

        from app.services.subscription import SubscriptionService
        from unittest.mock import patch

        service = SubscriptionService(app_session)
        with patch("app.config.settings.PAYSTACK_WEBHOOK_SECRET", "test_webhook_secret"):
            await service.handle_webhook(body, sig)

        # Commit so the admin_session (separate connection) can see the changes
        await app_session.commit()

        # Verify subscription dates were NOT changed
        result = await admin_session.execute(
            text("""
                SELECT subscription_start, subscription_end, features
                FROM tenants WHERE id = CAST(:tid AS uuid)
            """),
            {"tid": str(tenant["id"])},
        )
        row = result.fetchone()
        assert str(row[0]) == "2026-01-01"
        assert str(row[1]) == "2026-12-31"

        # Verify boarding feature was enabled
        features = row[2] or {}
        assert features.get("boarding", {}).get("enabled") is True

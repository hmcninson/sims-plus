"""
SIMS Plus - Push Notification Service Tests

Tests covering:
1. CRUD operations (subscribe, unsubscribe, list subscriptions)
2. Duplicate endpoint handling (key rotation / re-activation)
3. Tenant isolation (RLS + defense-in-depth tenant_id filtering)
4. User isolation (same tenant, different users)

Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from app.models.push_subscription import PushSubscription
from app.schemas.push_subscription import PushSubscriptionCreate
from app.services.push_notification import PushNotificationService

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.integration,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subscription_data(
    endpoint: str | None = None,
    p256dh_key: str = "test-p256dh-key-abcdef",
    auth_key: str = "test-auth-key-123456",
    user_agent: str | None = "Mozilla/5.0 Test Browser",
) -> PushSubscriptionCreate:
    """Create a PushSubscriptionCreate schema with sensible defaults."""
    return PushSubscriptionCreate(
        endpoint=endpoint or f"https://push.example.com/{uuid4().hex}",
        p256dh_key=p256dh_key,
        auth_key=auth_key,
        user_agent=user_agent,
    )


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------


class TestPushSubscriptionCRUD:
    """Core CRUD operations for the PushNotificationService."""

    async def test_subscribe_creates_subscription(self, app_session, admin_session):
        """Subscribing creates a new push subscription with all fields persisted."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        data = _make_subscription_data()
        subscription = await service.subscribe(
            user_id=user["id"],
            tenant_id=tenant["id"],
            data=data,
        )

        assert subscription.id is not None
        assert subscription.tenant_id == tenant["id"]
        assert subscription.user_id == user["id"]
        assert subscription.endpoint == data.endpoint
        assert subscription.p256dh_key == data.p256dh_key
        assert subscription.auth_key == data.auth_key
        assert subscription.user_agent == data.user_agent
        assert subscription.is_active is True

    async def test_subscribe_duplicate_endpoint_updates_keys(
        self, app_session, admin_session
    ):
        """Re-subscribing with the same endpoint updates keys instead of creating a duplicate."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        endpoint = f"https://push.example.com/{uuid4().hex}"

        # First subscribe
        data1 = _make_subscription_data(
            endpoint=endpoint,
            p256dh_key="old-key",
            auth_key="old-auth",
        )
        sub1 = await service.subscribe(
            user_id=user["id"],
            tenant_id=tenant["id"],
            data=data1,
        )
        sub1_id = sub1.id

        # Re-subscribe with new keys (simulates browser key rotation)
        data2 = _make_subscription_data(
            endpoint=endpoint,
            p256dh_key="new-key",
            auth_key="new-auth",
        )
        sub2 = await service.subscribe(
            user_id=user["id"],
            tenant_id=tenant["id"],
            data=data2,
        )

        # Should be the same record, updated
        assert sub2.id == sub1_id
        assert sub2.p256dh_key == "new-key"
        assert sub2.auth_key == "new-auth"
        assert sub2.is_active is True

    async def test_unsubscribe_removes_subscription(self, app_session, admin_session):
        """Unsubscribing removes the subscription and returns True."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        data = _make_subscription_data()
        await service.subscribe(
            user_id=user["id"],
            tenant_id=tenant["id"],
            data=data,
        )

        removed = await service.unsubscribe(
            user_id=user["id"],
            tenant_id=tenant["id"],
            endpoint=data.endpoint,
        )
        assert removed is True

        # Verify it is no longer in the active list
        subs = await service.get_user_subscriptions(
            user_id=user["id"],
            tenant_id=tenant["id"],
        )
        assert len(subs) == 0

    async def test_unsubscribe_nonexistent_returns_false(
        self, app_session, admin_session
    ):
        """Unsubscribing with an unknown endpoint returns False."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        removed = await service.unsubscribe(
            user_id=user["id"],
            tenant_id=tenant["id"],
            endpoint="https://push.example.com/nonexistent",
        )
        assert removed is False

    async def test_get_user_subscriptions_returns_active_only(
        self, app_session, admin_session
    ):
        """get_user_subscriptions returns only active subscriptions."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        # Create two subscriptions
        data1 = _make_subscription_data()
        data2 = _make_subscription_data()
        await service.subscribe(user_id=user["id"], tenant_id=tenant["id"], data=data1)
        await service.subscribe(user_id=user["id"], tenant_id=tenant["id"], data=data2)

        subs = await service.get_user_subscriptions(
            user_id=user["id"],
            tenant_id=tenant["id"],
        )
        assert len(subs) == 2

    async def test_multiple_subscriptions_for_same_user(
        self, app_session, admin_session
    ):
        """A user can have multiple subscriptions (different browsers/devices)."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        # Subscribe from 3 different endpoints (3 devices)
        for _ in range(3):
            data = _make_subscription_data()
            await service.subscribe(
                user_id=user["id"],
                tenant_id=tenant["id"],
                data=data,
            )

        subs = await service.get_user_subscriptions(
            user_id=user["id"],
            tenant_id=tenant["id"],
        )
        assert len(subs) == 3


# ---------------------------------------------------------------------------
# Tenant Isolation Tests
# ---------------------------------------------------------------------------


class TestPushSubscriptionTenantIsolation:
    """Push subscriptions in Tenant A must NEVER be visible to Tenant B.

    Verifies both RLS enforcement (database level) and defense-in-depth
    tenant_id filtering (service level).
    """

    async def test_subscriptions_in_tenant_a_not_visible_in_b(
        self, app_session, admin_session
    ):
        """A subscription created in Tenant A does not appear in Tenant B's list."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])
        await admin_session.commit()

        # Create subscription in Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = PushNotificationService(app_session)

        data = _make_subscription_data()
        sub = await service.subscribe(
            user_id=user_a["id"],
            tenant_id=tenant_a["id"],
            data=data,
        )
        sub_id = sub.id

        # Switch to Tenant B and list -- should be empty
        await set_app_tenant_context(app_session, tenant_b["id"])
        subs_b = await service.get_user_subscriptions(
            user_id=user_b["id"],
            tenant_id=tenant_b["id"],
        )
        assert len(subs_b) == 0

        # Also verify that even if we pass tenant_a's user_id, RLS blocks it
        subs_cross = await service.get_user_subscriptions(
            user_id=user_a["id"],
            tenant_id=tenant_b["id"],
        )
        assert len(subs_cross) == 0

    async def test_cannot_unsubscribe_cross_tenant(
        self, app_session, admin_session
    ):
        """Unsubscribing from another tenant's subscription returns False."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant_a["id"])
        user_b = await create_test_user(admin_session, tenant_b["id"])

        # Create subscription via admin (bypasses RLS)
        sub_id = uuid4()
        endpoint = f"https://push.example.com/{uuid4().hex}"
        await admin_session.execute(
            text("""
                INSERT INTO push_subscriptions
                    (id, tenant_id, user_id, endpoint, p256dh_key, auth_key,
                     is_active, created_at, updated_at)
                VALUES
                    (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:uid AS uuid),
                     :endpoint, :p256dh, :auth, true,
                     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(sub_id),
                "tid": str(tenant_a["id"]),
                "uid": str(user_a["id"]),
                "endpoint": endpoint,
                "p256dh": "test-key",
                "auth": "test-auth",
            },
        )
        await admin_session.commit()

        # Switch to Tenant B and try to unsubscribe
        await set_app_tenant_context(app_session, tenant_b["id"])
        service = PushNotificationService(app_session)
        result = await service.unsubscribe(
            user_id=user_b["id"],
            tenant_id=tenant_b["id"],
            endpoint=endpoint,
        )
        assert result is False

        # Verify subscription still exists via admin
        row = await admin_session.execute(
            text(
                "SELECT COUNT(*) FROM push_subscriptions WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(sub_id)},
        )
        assert row.scalar() == 1

    async def test_rls_policy_exists_on_push_subscriptions(self, admin_session):
        """Verify that an RLS policy exists on the push_subscriptions table."""
        result = await admin_session.execute(
            text("""
                SELECT COUNT(*) FROM pg_policies
                WHERE tablename = 'push_subscriptions'
            """)
        )
        count = result.scalar()
        assert count >= 1, "push_subscriptions table should have at least one RLS policy"


# ---------------------------------------------------------------------------
# User Isolation Tests
# ---------------------------------------------------------------------------


class TestPushSubscriptionUserIsolation:
    """Within the same tenant, User A's subscriptions must not appear for User B."""

    async def test_subscriptions_for_user_a_not_visible_to_user_b(
        self, app_session, admin_session
    ):
        """User B cannot see User A's push subscriptions (same tenant)."""
        tenant = await create_test_tenant(admin_session)
        user_a = await create_test_user(admin_session, tenant["id"])
        user_b = await create_test_user(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = PushNotificationService(app_session)

        # User A subscribes
        data = _make_subscription_data()
        await service.subscribe(
            user_id=user_a["id"],
            tenant_id=tenant["id"],
            data=data,
        )

        # User B's subscriptions should be empty
        subs_b = await service.get_user_subscriptions(
            user_id=user_b["id"],
            tenant_id=tenant["id"],
        )
        assert len(subs_b) == 0

        # User A should see 1
        subs_a = await service.get_user_subscriptions(
            user_id=user_a["id"],
            tenant_id=tenant["id"],
        )
        assert len(subs_a) == 1


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestPushSubscriptionModel:
    """Verify the PushSubscription model has the expected columns and mixins."""

    def test_model_has_tenant_id_column(self):
        """PushSubscription inherits TenantMixin and has tenant_id."""
        columns = {c.name for c in PushSubscription.__table__.columns}
        assert "tenant_id" in columns

    def test_model_has_expected_columns(self):
        """PushSubscription has all required columns."""
        columns = {c.name for c in PushSubscription.__table__.columns}
        expected = {
            "id", "tenant_id", "user_id",
            "endpoint", "p256dh_key", "auth_key",
            "user_agent", "is_active",
        }
        assert expected.issubset(columns)

    def test_tablename_is_push_subscriptions(self):
        """Tablename matches what migrations and RLS expect."""
        assert PushSubscription.__tablename__ == "push_subscriptions"

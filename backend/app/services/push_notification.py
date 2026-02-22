"""
SIMS Plus - Push Notification Service

Manages Web Push subscriptions and sends push notifications to users.
Uses the pywebpush library for VAPID-authenticated Web Push protocol.
"""

import json
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_subscription import PushSubscription
from app.schemas.push_subscription import PushSubscriptionCreate

logger = structlog.get_logger()


class PushNotificationService:
    """Service for managing push subscriptions and sending notifications."""

    class Error(Exception):
        """Push notification service error."""

        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def subscribe(
        self,
        user_id: UUID,
        tenant_id: UUID,
        data: PushSubscriptionCreate,
    ) -> PushSubscription:
        """
        Register or update a push subscription for a user.

        If the same endpoint already exists for this user/tenant, the keys
        are updated (browsers may rotate them) and the subscription is
        re-activated.
        """
        # Defense-in-depth: always filter by tenant_id alongside user_id
        stmt = select(PushSubscription).where(
            PushSubscription.tenant_id == tenant_id,
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == data.endpoint,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Keys may have rotated -- update them
            existing.p256dh_key = data.p256dh_key
            existing.auth_key = data.auth_key
            existing.user_agent = data.user_agent
            existing.is_active = True
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        subscription = PushSubscription(
            user_id=user_id,
            tenant_id=tenant_id,
            endpoint=data.endpoint,
            p256dh_key=data.p256dh_key,
            auth_key=data.auth_key,
            user_agent=data.user_agent,
        )
        self.db.add(subscription)
        await self.db.flush()
        await self.db.refresh(subscription)
        return subscription

    async def unsubscribe(
        self,
        user_id: UUID,
        tenant_id: UUID,
        endpoint: str,
    ) -> bool:
        """
        Remove a push subscription by endpoint.

        Returns True if a row was deleted, False if no matching subscription found.
        """
        # Defense-in-depth: tenant_id filter ensures cross-tenant isolation
        stmt = delete(PushSubscription).where(
            PushSubscription.tenant_id == tenant_id,
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def get_user_subscriptions(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> list[PushSubscription]:
        """Get all active push subscriptions for a user within their tenant."""
        stmt = select(PushSubscription).where(
            PushSubscription.tenant_id == tenant_id,
            PushSubscription.user_id == user_id,
            PushSubscription.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def send_to_user(
        self,
        user_id: UUID,
        tenant_id: UUID,
        title: str,
        body: str,
        url: str = "/dashboard",
        tag: str = "default",
    ) -> None:
        """
        Send a push notification to all active subscriptions for a user.

        SECURITY: No PII in payloads -- only titles and generic messages.
        Deactivates subscriptions that return 404/410 (expired/unsubscribed).
        """
        from app.config import settings

        subscriptions = await self.get_user_subscriptions(user_id, tenant_id)
        if not subscriptions:
            return

        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            logger.warning("pywebpush_not_installed", msg="Skipping push notification")
            return

        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url,
            "tag": tag,
        })

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {
                            "p256dh": sub.p256dh_key,
                            "auth": sub.auth_key,
                        },
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{settings.VAPID_CONTACT_EMAIL}"},
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    # Subscription expired or user unsubscribed via browser
                    sub.is_active = False
                    await self.db.flush()
                    logger.info(
                        "push_subscription_expired",
                        user_id=str(user_id),
                        # Truncate endpoint to avoid logging full URL
                        endpoint_prefix=sub.endpoint[:50],
                    )
                else:
                    logger.error(
                        "push_notification_failed",
                        user_id=str(user_id),
                        status_code=getattr(e.response, "status_code", None),
                    )
            except Exception:
                # Never let a push failure propagate and break the calling operation
                logger.exception("push_notification_unexpected_error", user_id=str(user_id))

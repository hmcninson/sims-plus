"""
SIMS Plus - Push Notification Endpoints

Endpoints for managing Web Push subscriptions and retrieving the VAPID
public key needed by the browser to subscribe.

IMPORTANT: Do NOT use `from __future__ import annotations` in this file.
It breaks FastAPI's 204 No Content response handling.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DatabaseSession,
    ValidatedUser,
    require_permissions,
)
from app.config import settings
from app.schemas.push_subscription import (
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    VapidKeyResponse,
)
from app.services.push_notification import PushNotificationService

router = APIRouter()


@router.get(
    "/vapid-key",
    response_model=VapidKeyResponse,
    summary="Get VAPID public key",
    dependencies=[Depends(require_permissions())],
)
async def get_vapid_public_key(
    user: ValidatedUser,
) -> VapidKeyResponse:
    """
    Return the VAPID public key for the browser to use when subscribing
    to push notifications via the Push API.
    """
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured",
        )
    return VapidKeyResponse(public_key=settings.VAPID_PUBLIC_KEY)


@router.post(
    "/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register push subscription",
    dependencies=[Depends(require_permissions())],
)
async def subscribe_push(
    data: PushSubscriptionCreate,
    user: ValidatedUser,
    db: DatabaseSession,
) -> PushSubscriptionResponse:
    """
    Register a Web Push subscription for the current user.

    If the same endpoint already exists, its keys are updated (browsers
    may rotate them) and the subscription is re-activated.
    """
    service = PushNotificationService(db)
    try:
        subscription = await service.subscribe(
            user_id=UUID(user["user_id"]),
            tenant_id=UUID(user["tenant_id"]),
            data=data,
        )
        return PushSubscriptionResponse.model_validate(subscription)
    except PushNotificationService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove push subscription",
    dependencies=[Depends(require_permissions())],
)
async def unsubscribe_push(
    endpoint: str,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """
    Remove a push subscription by its endpoint URL.

    Called when the user disables notifications or the service worker
    is unregistered.
    """
    service = PushNotificationService(db)
    removed = await service.unsubscribe(
        user_id=UUID(user["user_id"]),
        tenant_id=UUID(user["tenant_id"]),
        endpoint=endpoint,
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

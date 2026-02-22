"""
SIMS Plus - Push Subscription Schemas

Pydantic v2 schemas for Web Push subscription management.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PushSubscriptionCreate(BaseModel):
    """Request schema for registering a push subscription."""

    endpoint: str = Field(..., max_length=2000)
    p256dh_key: str = Field(..., max_length=255)
    auth_key: str = Field(..., max_length=255)
    user_agent: str | None = Field(None, max_length=500)


class PushSubscriptionResponse(BaseModel):
    """Response schema for a push subscription."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    endpoint: str
    is_active: bool
    created_at: datetime


class VapidKeyResponse(BaseModel):
    """Response schema for the VAPID public key."""

    public_key: str

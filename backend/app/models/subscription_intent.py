"""
SIMS Plus - Subscription Intent Model

Stores pending subscription upgrade/addon payment intents for
server-side webhook validation (H1). Prevents a crafted webhook
from upgrading a different tenant or to an unauthorized tier.

NOT tenant-scoped (no TenantMixin/RLS): accessed via unscoped DB
in webhook handlers where tenant context is derived from metadata.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SubscriptionIntent(Base):
    """
    Payment intent for subscription upgrades and add-on purchases.

    Created when a user initiates a payment via Paystack.
    Validated in the webhook handler to ensure the payment matches
    the intended action.

    No TenantMixin — accessed via UnscopedDatabaseSession since
    webhook handlers don't have subdomain context.
    """

    __tablename__ = "subscription_intents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Paystack payment reference (unique per transaction)",
    )
    target_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Target subscription tier or 'addon' for add-on purchases",
    )
    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Expected payment amount in pesewas",
    )
    billing_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'term' or 'year'",
    )
    intent_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="'upgrade' or 'addon_purchase'",
    )
    addon_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Comma-separated add-on names (for addon_purchase type)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending, completed, failed, expired",
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionIntent(reference='{self.reference}', "
            f"type='{self.intent_type}', status='{self.status}')>"
        )

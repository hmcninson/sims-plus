"""Add trial/subscription indexes to tenants and subscription_intents table

Phase 1A: Trial & Subscription Enforcement

1. Check if trial_ends_at, subscription_start, subscription_end columns
   exist on tenants (they should — added in 20260221_0200). Add if missing.
2. Create partial index idx_tenants_trial_expires for efficient trial
   expiration queries (Celery daily task, subscription middleware).
3. Create partial index idx_tenants_subscription_expires for subscription
   expiration queries.
4. Create subscription_intents table for Paystack webhook validation (H1).
   - NOT tenant-scoped (accessed via UnscopedDatabaseSession in webhook)
   - Has tenant_id FK but NO RLS (webhook runs without tenant context)

Clean slate: no existing tenant data to migrate.

Revision ID: 20260322_0100
Revises: 20260320_0100
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260322_0100"
down_revision: Union[str, None] = "20260320_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. Ensure trial/subscription columns exist on tenants
    # ============================================================
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "trial_ends_at" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column(
                "trial_ends_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="When the trial period expires",
            ),
        )

    if "subscription_start" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column(
                "subscription_start",
                sa.Date(),
                nullable=True,
                comment="When the paid subscription started",
            ),
        )

    if "subscription_end" not in existing_columns:
        op.add_column(
            "tenants",
            sa.Column(
                "subscription_end",
                sa.Date(),
                nullable=True,
                comment="When the paid subscription expires",
            ),
        )

    # ============================================================
    # 2. Partial indexes for expiration queries
    # ============================================================
    # Used by: Celery check_trial_expirations task (daily scan),
    #          SubscriptionMiddleware / enforce_subscription dependency
    op.create_index(
        "idx_tenants_trial_expires",
        "tenants",
        ["status", "trial_ends_at"],
        postgresql_where=sa.text("status = 'trial'"),
    )

    op.create_index(
        "idx_tenants_subscription_expires",
        "tenants",
        ["status", "subscription_end"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # ============================================================
    # 3. Create subscription_intents table (webhook validation)
    # ============================================================
    # This table validates that Paystack webhook metadata matches a
    # server-side record created at payment initiation time (H1 fix).
    # Accessed via UnscopedDatabaseSession — NO RLS needed.
    op.create_table(
        "subscription_intents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reference",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="Paystack payment reference (unique across all intents)",
        ),
        sa.Column(
            "target_tier",
            sa.String(50),
            nullable=False,
            comment="Tier being upgraded to: starter, professional, enterprise",
        ),
        sa.Column(
            "amount",
            sa.Integer(),
            nullable=False,
            comment="Amount in pesewas (GHS * 100)",
        ),
        sa.Column(
            "billing_period",
            sa.String(20),
            nullable=False,
            comment="Billing cycle: term or annual",
        ),
        sa.Column(
            "intent_type",
            sa.String(20),
            nullable=False,
            comment="Intent type: upgrade or addon_purchase",
        ),
        sa.Column(
            "addon_name",
            sa.String(100),
            nullable=True,
            comment="Add-on being purchased (NULL for tier upgrades)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Intent status: pending, completed, failed, expired",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Index for webhook lookup by reference (most common query path)
    op.create_index(
        "idx_subscription_intents_reference",
        "subscription_intents",
        ["reference"],
    )

    # Index for listing intents by tenant (admin dashboard)
    op.create_index(
        "idx_subscription_intents_tenant",
        "subscription_intents",
        ["tenant_id", "status"],
    )

    # Grant permissions to app user for webhook access
    op.execute("GRANT SELECT, INSERT, UPDATE ON subscription_intents TO sims_app_user")


def downgrade() -> None:
    # ============================================================
    # 1. Drop subscription_intents table
    # ============================================================
    op.execute("REVOKE ALL ON subscription_intents FROM sims_app_user")
    op.drop_index("idx_subscription_intents_tenant", table_name="subscription_intents")
    op.drop_index("idx_subscription_intents_reference", table_name="subscription_intents")
    op.drop_table("subscription_intents")

    # ============================================================
    # 2. Drop partial indexes on tenants
    # ============================================================
    op.drop_index("idx_tenants_subscription_expires", table_name="tenants")
    op.drop_index("idx_tenants_trial_expires", table_name="tenants")

    # ============================================================
    # 3. Do NOT drop trial_ends_at, subscription_start, subscription_end
    #    — they were added by earlier migrations (20260221_0200),
    #    not by this migration. Only drop what we added.
    # ============================================================

"""Fix tenant enum values: UPPERCASE -> lowercase to match model values_callable

The initial migration created tenanttype and subscriptiontier enums using
Python enum member NAMES (UPPERCASE) instead of VALUES (lowercase).
The model uses values_callable=lambda x: [e.value for e in x] which sends
lowercase values. This migration renames the enum values to match.

Revision ID: 20260221_0300
Revises: 20260221_0200
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260221_0300"
down_revision: Union[str, None] = "20260221_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix tenanttype: SINGLE_SCHOOL -> single_school, SCHOOL_CHAIN -> school_chain
    op.execute("ALTER TYPE tenanttype RENAME VALUE 'SINGLE_SCHOOL' TO 'single_school'")
    op.execute("ALTER TYPE tenanttype RENAME VALUE 'SCHOOL_CHAIN' TO 'school_chain'")

    # Fix subscriptiontier: TRIAL -> trial, STARTER -> starter, etc.
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'TRIAL' TO 'trial'")
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'STARTER' TO 'starter'")
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'PROFESSIONAL' TO 'professional'")
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'ENTERPRISE' TO 'enterprise'")


def downgrade() -> None:
    # Revert to UPPERCASE
    op.execute("ALTER TYPE tenanttype RENAME VALUE 'single_school' TO 'SINGLE_SCHOOL'")
    op.execute("ALTER TYPE tenanttype RENAME VALUE 'school_chain' TO 'SCHOOL_CHAIN'")

    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'trial' TO 'TRIAL'")
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'starter' TO 'STARTER'")
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'professional' TO 'PROFESSIONAL'")
    op.execute("ALTER TYPE subscriptiontier RENAME VALUE 'enterprise' TO 'ENTERPRISE'")

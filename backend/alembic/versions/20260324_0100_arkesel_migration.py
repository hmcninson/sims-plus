"""Update sms_log default provider from hubtel to arkesel.

The 'arkesel' value already exists in the smsprovider enum (added in
the original 20260220_0100 migration). This migration only changes the
column default so new rows use 'arkesel' instead of 'hubtel'.

Revision ID: 20260324_0100
Revises: 20260322_0300
Create Date: 2026-03-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260324_0100"
down_revision: Union[str, None] = "20260322_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update the default provider to arkesel
    op.execute("ALTER TABLE sms_log ALTER COLUMN provider SET DEFAULT 'arkesel'")


def downgrade() -> None:
    # Revert the default to hubtel
    op.execute("ALTER TABLE sms_log ALTER COLUMN provider SET DEFAULT 'hubtel'")

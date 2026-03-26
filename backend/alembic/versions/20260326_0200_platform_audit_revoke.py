"""Revoke excess privileges on platform_audit_log for sims_app_user.

Ensures INSERT-only access even in dev environments where broader
default grants may exist.

Revision ID: 20260326_0200
Revises: 20260326_0100
"""
from alembic import op

revision = "20260326_0200"
down_revision = "20260326_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Strip any inherited/default privileges, then re-grant INSERT only.
    op.execute("REVOKE ALL ON platform_audit_log FROM sims_app_user")
    op.execute("GRANT INSERT ON platform_audit_log TO sims_app_user")


def downgrade() -> None:
    # On downgrade, restore the broader grants that may have existed.
    # The base GRANT INSERT from 20260326_0100 will still be in effect.
    pass

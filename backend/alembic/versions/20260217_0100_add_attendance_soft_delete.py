"""Add deleted_at column to attendance tables for soft delete support.

Both student_attendance and staff_attendance tables now use SoftDeleteMixin,
which requires a nullable deleted_at TIMESTAMPTZ column. This enables soft
deletes instead of physical row removal, preserving audit history and
allowing recovery of accidentally deleted records.

Revision ID: add_attendance_soft_delete
Revises: transaction_scoped_tenant_ctx
Create Date: 2026-02-17 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_attendance_soft_delete"
down_revision = "transaction_scoped_tenant_ctx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add deleted_at column to student_attendance and staff_attendance."""
    op.add_column(
        "student_attendance",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "staff_attendance",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove deleted_at column from attendance tables."""
    op.drop_column("staff_attendance", "deleted_at")
    op.drop_column("student_attendance", "deleted_at")

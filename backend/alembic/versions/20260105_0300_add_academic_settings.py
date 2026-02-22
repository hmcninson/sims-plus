"""Add academic settings table

Revision ID: 20260105_0300
Revises: 20260105_0200
Create Date: 2026-01-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260105_0300"
down_revision: Union[str, None] = "20260105_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auto_promote_students", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_grade_amendments", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("show_position_on_report_cards", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("require_attendance_for_exams", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable_continuous_assessment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_academic_settings_tenant"),
    )

    # Create index for tenant lookup
    op.create_index("ix_academic_settings_tenant_id", "academic_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_academic_settings_tenant_id", table_name="academic_settings")
    op.drop_table("academic_settings")

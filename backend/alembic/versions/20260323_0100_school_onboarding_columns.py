"""Add onboarding columns to schools table

Revision ID: 20260323_0100
Revises: user_sessions
Create Date: 2026-03-23 01:00:00.000000+00:00

Adds four columns to the schools table to support the setup wizard:
- ges_registration_number: dedicated GES registration number field
- setup_completed: boolean flag for wizard completion
- setup_wizard_step: tracks last completed wizard step for resumability
- calendar_type: configures academic calendar (term/semester/quarter)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260323_0100"
down_revision: Union[str, None] = "user_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding-related columns to schools table."""
    op.add_column(
        "schools",
        sa.Column(
            "ges_registration_number",
            sa.String(100),
            nullable=True,
            comment="Ghana Education Service registration number",
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "setup_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether the school has completed the setup wizard",
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "setup_wizard_step",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Last completed wizard step (0 = not started)",
        ),
    )
    # Create the enum type explicitly before using it in add_column.
    # sa.Enum with create_type=True inside add_column does NOT auto-create
    # the type — it only works inside create_table's before_create event.
    calendar_type_enum = sa.Enum('term', 'semester', 'quarter', name='calendartype')
    calendar_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "schools",
        sa.Column(
            "calendar_type",
            sa.Enum('term', 'semester', 'quarter', name='calendartype', create_type=False),
            nullable=False,
            server_default="term",
            comment="Academic calendar type: term, semester, or quarter",
        ),
    )


def downgrade() -> None:
    """Remove onboarding-related columns from schools table."""
    op.drop_column("schools", "calendar_type")
    # Drop the enum type after the column that uses it is gone
    calendar_type_enum = sa.Enum(name='calendartype')
    calendar_type_enum.drop(op.get_bind())
    op.drop_column("schools", "setup_wizard_step")
    op.drop_column("schools", "setup_completed")
    op.drop_column("schools", "ges_registration_number")

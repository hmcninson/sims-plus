"""Enrollment Gap Closure Phase 2: Letters, Offers & Waitlist

Column additions to 3 existing admissions tables:
  - admission_decisions: rejection_reason, rejection_letter_url, waitlist_rank, waitlist_notes
  - applications: offer_responded_at, offer_response, offer_response_notes
  - admission_periods: reminder_enabled, reminder_days_before_close

No new tables, no new RLS policies (existing table policies still apply).

Indexes:
  - ix_decisions_waitlist: partial index on waitlisted decisions with rank
  - ix_applications_offer_pending: partial index on offered applications awaiting response

Revision ID: 20260408_0100
Revises: 20260401_0200
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408_0100"
down_revision: Union[str, None] = "20260401_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =================================================================
    # admission_decisions — waitlist + rejection letter columns
    # =================================================================
    op.add_column(
        "admission_decisions",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("rejection_letter_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("waitlist_rank", sa.Integer(), nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("waitlist_notes", sa.Text(), nullable=True),
    )

    # Partial index: efficiently query waitlisted decisions ordered by rank
    op.execute("""
        CREATE INDEX ix_decisions_waitlist
            ON admission_decisions(tenant_id, waitlist_rank)
            WHERE decision_type = 'waitlisted'
              AND waitlist_rank IS NOT NULL
              AND deleted_at IS NULL;
    """)

    # =================================================================
    # applications — offer response tracking columns
    # =================================================================
    op.add_column(
        "applications",
        sa.Column("offer_responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("offer_response", sa.String(20), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("offer_response_notes", sa.Text(), nullable=True),
    )

    # Partial index: find applications with pending offer responses
    op.execute("""
        CREATE INDEX ix_applications_offer_pending
            ON applications(tenant_id, status)
            WHERE status = 'offered'
              AND offer_responded_at IS NULL
              AND deleted_at IS NULL;
    """)

    # =================================================================
    # admission_periods — reminder configuration columns
    # =================================================================
    op.add_column(
        "admission_periods",
        sa.Column(
            "reminder_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "admission_periods",
        sa.Column("reminder_days_before_close", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # =================================================================
    # Drop indexes first
    # =================================================================
    op.execute("DROP INDEX IF EXISTS ix_applications_offer_pending;")
    op.execute("DROP INDEX IF EXISTS ix_decisions_waitlist;")

    # =================================================================
    # admission_periods — drop reminder columns
    # =================================================================
    op.drop_column("admission_periods", "reminder_days_before_close")
    op.drop_column("admission_periods", "reminder_enabled")

    # =================================================================
    # applications — drop offer response columns
    # =================================================================
    op.drop_column("applications", "offer_response_notes")
    op.drop_column("applications", "offer_response")
    op.drop_column("applications", "offer_responded_at")

    # =================================================================
    # admission_decisions — drop waitlist + rejection columns
    # =================================================================
    op.drop_column("admission_decisions", "waitlist_notes")
    op.drop_column("admission_decisions", "waitlist_rank")
    op.drop_column("admission_decisions", "rejection_letter_url")
    op.drop_column("admission_decisions", "rejection_reason")

"""Enrollment Gap Closure Phase 4: Capacity Planning, School Events & Event Registrations

New tables:
  - enrollment_targets: Per-class enrollment targets for capacity planning
  - school_events: Tours, open days, orientations for prospective families
  - event_registrations: Registrations for school events (hard delete, no soft delete)

Column additions to existing tables:
  - return_intents: re_enrollment_confirmed, re_enrollment_confirmed_at,
    outstanding_fees_checked, outstanding_fee_amount

RLS policies on all 3 new tables.

Revision ID: 20260422_0100
Revises: 20260415_0100
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260422_0100"
down_revision: Union[str, None] = "20260415_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All 3 tenant-scoped tables that need RLS
NEW_TABLES = [
    "enrollment_targets",
    "school_events",
    "event_registrations",
]


def upgrade() -> None:
    # =================================================================
    # PHASE 1: Create new tables
    # =================================================================

    # --- Table 1: enrollment_targets ---
    op.create_table(
        "enrollment_targets",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("boarding_target", sa.Integer(), nullable=True),
        sa.Column("day_target", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("target_count >= 0", name="ck_enrollment_targets_target_count"),
        sa.CheckConstraint("boarding_target >= 0", name="ck_enrollment_targets_boarding_target"),
        sa.CheckConstraint("day_target >= 0", name="ck_enrollment_targets_day_target"),
    )

    # --- Table 2: school_events ---
    op.create_table(
        "school_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("venue", sa.String(255), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("registered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("guide_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("capacity >= 1", name="ck_school_events_capacity"),
        sa.CheckConstraint("registered_count >= 0", name="ck_school_events_registered_count"),
    )

    # --- Table 3: event_registrations (NO deleted_at — hard delete) ---
    op.create_table(
        "event_registrations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("school_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registrant_name", sa.String(200), nullable=False),
        sa.Column("registrant_phone", sa.String(20), nullable=False),
        sa.Column("registrant_email", sa.String(255), nullable=True),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("attended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("tenant_id", "event_id", "registrant_phone", name="uq_event_registrations_phone"),
    )

    # =================================================================
    # PHASE 2: Enable RLS on new tables
    # =================================================================
    for table_name in NEW_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table_name}
            FOR ALL
            TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
        """)

    # =================================================================
    # PHASE 3: Grant permissions to application role
    # =================================================================
    for table_name in NEW_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")

    # =================================================================
    # PHASE 4: Create indexes on new tables
    # =================================================================

    # --- enrollment_targets ---
    # Partial unique: one active target per class per academic year
    op.execute("""
        CREATE UNIQUE INDEX uq_enrollment_targets_class_year
        ON enrollment_targets(tenant_id, academic_year_id, class_id)
        WHERE deleted_at IS NULL
    """)
    # School + year lookup for dashboard queries
    op.execute("""
        CREATE INDEX ix_enrollment_targets_school_year
        ON enrollment_targets(tenant_id, school_id, academic_year_id)
        WHERE deleted_at IS NULL
    """)

    # --- school_events ---
    # Date-based listing
    op.execute("""
        CREATE INDEX ix_school_events_tenant_date
        ON school_events(tenant_id, school_id, event_date)
        WHERE deleted_at IS NULL
    """)
    # Type-based filtering
    op.execute("""
        CREATE INDEX ix_school_events_tenant_type
        ON school_events(tenant_id, school_id, event_type)
        WHERE deleted_at IS NULL
    """)
    # Guide lookup
    op.execute("""
        CREATE INDEX ix_school_events_guide
        ON school_events(tenant_id, guide_id)
        WHERE deleted_at IS NULL AND guide_id IS NOT NULL
    """)

    # --- event_registrations ---
    # Event lookup
    op.execute("""
        CREATE INDEX ix_event_registrations_event
        ON event_registrations(tenant_id, event_id)
    """)
    # Phone lookup (for searching registrations by phone)
    op.execute("""
        CREATE INDEX ix_event_registrations_phone
        ON event_registrations(tenant_id, registrant_phone)
    """)

    # =================================================================
    # PHASE 5: Add columns to return_intents
    # =================================================================
    op.add_column("return_intents", sa.Column(
        "re_enrollment_confirmed", sa.Boolean(), nullable=False, server_default="false",
    ))
    op.add_column("return_intents", sa.Column(
        "re_enrollment_confirmed_at", sa.DateTime(timezone=True), nullable=True,
    ))
    op.add_column("return_intents", sa.Column(
        "outstanding_fees_checked", sa.Boolean(), nullable=False, server_default="false",
    ))
    op.add_column("return_intents", sa.Column(
        "outstanding_fee_amount", sa.Numeric(10, 2), nullable=True,
    ))


def downgrade() -> None:
    # --- Drop columns from return_intents ---
    op.drop_column("return_intents", "outstanding_fee_amount")
    op.drop_column("return_intents", "outstanding_fees_checked")
    op.drop_column("return_intents", "re_enrollment_confirmed_at")
    op.drop_column("return_intents", "re_enrollment_confirmed")

    # --- Drop indexes (partial indexes need explicit DROP) ---
    op.execute("DROP INDEX IF EXISTS ix_event_registrations_phone")
    op.execute("DROP INDEX IF EXISTS ix_event_registrations_event")
    op.execute("DROP INDEX IF EXISTS ix_school_events_guide")
    op.execute("DROP INDEX IF EXISTS ix_school_events_tenant_type")
    op.execute("DROP INDEX IF EXISTS ix_school_events_tenant_date")
    op.execute("DROP INDEX IF EXISTS ix_enrollment_targets_school_year")
    op.execute("DROP INDEX IF EXISTS uq_enrollment_targets_class_year")

    # --- Drop RLS policies and grants ---
    for table_name in reversed(NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
        op.execute(f"REVOKE ALL ON {table_name} FROM sims_app_user")

    # --- Drop tables (child first: event_registrations before school_events) ---
    op.drop_table("event_registrations")
    op.drop_table("school_events")
    op.drop_table("enrollment_targets")

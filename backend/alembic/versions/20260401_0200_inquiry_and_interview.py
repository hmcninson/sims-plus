"""Enrollment Gap Closure Phase 1: Inquiry & Interview tables

Creates 5 new tenant-scoped tables:
  1. inquiries -- Pre-application lead tracking
  2. inquiry_communications -- Append-only communication log (no soft delete)
  3. inquiry_follow_ups -- Scheduled follow-up tasks
  4. interviews -- Interview scheduling and scoring
  5. screening_checklists -- Per-application verification items

Adds columns to existing tables:
  - applications.inquiry_id (FK to inquiries)
  - admission_decisions.interview_score, screening_score
  - entrance_exam_results.subject_name, weight

Enables RLS + FORCE RLS on all 5 new tables.
Grants permissions to sims_app_user.
Creates composite indexes for common query patterns.

Revision ID: 20260401_0200
Revises: 20260330_0200
Create Date: 2026-04-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "20260401_0200"
down_revision: Union[str, None] = "20260330_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All 5 new tenant-scoped tables that need RLS
NEW_TABLES = [
    "inquiries",
    "inquiry_communications",
    "inquiry_follow_ups",
    "interviews",
    "screening_checklists",
]


def upgrade() -> None:
    # =================================================================
    # PHASE 1: Create tables
    # =================================================================

    # --- Table 1: inquiries ---
    op.create_table(
        "inquiries",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, comment="InquirySource enum value"),
        sa.Column("status", sa.String(20), nullable=False, server_default="new", comment="InquiryStatus enum value"),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("target_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guardian_name", sa.String(200), nullable=False),
        sa.Column("guardian_phone", sa.String(20), nullable=False),
        sa.Column("guardian_email", sa.String(255), nullable=True),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("referred_by", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("converted_application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 2: inquiry_communications (NO soft delete, append-only) ---
    op.create_table(
        "inquiry_communications",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("inquiry_id", UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, comment="sms, email, phone, in_person"),
        sa.Column("direction", sa.String(10), nullable=False, comment="inbound or outbound"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sent_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # NOTE: No deleted_at -- this is append-only audit data
    )

    # --- Table 3: inquiry_follow_ups ---
    op.create_table(
        "inquiry_follow_ups",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("inquiry_id", UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium", comment="low, medium, high"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 4: interviews ---
    op.create_table(
        "interviews",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("venue", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("scoring_criteria", JSONB(), nullable=False, server_default="{}"),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 5: screening_checklists ---
    op.create_table(
        "screening_checklists",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("item_category", sa.String(100), nullable=False, comment="documents, academic, medical, other"),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("completed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # =================================================================
    # PHASE 2: Enable RLS on all 5 new tables
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
    # PHASE 4: Add columns to existing tables
    # =================================================================

    # applications.inquiry_id
    op.add_column(
        "applications",
        sa.Column(
            "inquiry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("inquiries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # admission_decisions.interview_score, screening_score
    op.add_column(
        "admission_decisions",
        sa.Column("interview_score", sa.Numeric(6, 2), nullable=True),
    )
    op.add_column(
        "admission_decisions",
        sa.Column("screening_score", sa.Numeric(6, 2), nullable=True),
    )

    # entrance_exam_results.subject_name, weight
    op.add_column(
        "entrance_exam_results",
        sa.Column("subject_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "entrance_exam_results",
        sa.Column("weight", sa.Numeric(4, 2), nullable=True, server_default="1.0"),
    )

    # =================================================================
    # PHASE 5: Create indexes
    # =================================================================

    # --- inquiries indexes ---
    op.create_index(
        "ix_inquiries_tenant_status",
        "inquiries",
        ["tenant_id", "school_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_inquiries_tenant_source",
        "inquiries",
        ["tenant_id", "school_id", "source"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_inquiries_guardian_phone",
        "inquiries",
        ["tenant_id", "guardian_phone"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_inquiries_guardian_email",
        "inquiries",
        ["tenant_id", "guardian_email"],
        postgresql_where=sa.text("deleted_at IS NULL AND guardian_email IS NOT NULL"),
    )
    op.create_index(
        "ix_inquiries_assigned",
        "inquiries",
        ["tenant_id", "assigned_to"],
        postgresql_where=sa.text("deleted_at IS NULL AND assigned_to IS NOT NULL"),
    )

    # --- inquiry_communications indexes ---
    op.create_index(
        "ix_inquiry_comms_inquiry",
        "inquiry_communications",
        ["tenant_id", "inquiry_id"],
    )

    # --- inquiry_follow_ups indexes ---
    op.create_index(
        "ix_followups_pending",
        "inquiry_follow_ups",
        ["tenant_id", "assigned_to", "due_date"],
        postgresql_where=sa.text("completed_at IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_followups_inquiry",
        "inquiry_follow_ups",
        ["tenant_id", "inquiry_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- interviews indexes ---
    op.create_index(
        "uq_interviews_application",
        "interviews",
        ["tenant_id", "application_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_interviews_scheduled",
        "interviews",
        ["tenant_id", "school_id", "scheduled_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_interviews_interviewer",
        "interviews",
        ["tenant_id", "interviewer_id", "scheduled_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- screening_checklists indexes ---
    op.create_index(
        "ix_screening_application",
        "screening_checklists",
        ["tenant_id", "application_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_screening_tenant_app_item",
        "screening_checklists",
        ["tenant_id", "application_id", "item_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- applications.inquiry_id index ---
    op.create_index(
        "ix_applications_inquiry",
        "applications",
        ["tenant_id", "inquiry_id"],
        postgresql_where=sa.text("inquiry_id IS NOT NULL AND deleted_at IS NULL"),
    )

    # --- CHECK constraint on interviews.duration_minutes ---
    op.execute("""
        ALTER TABLE interviews
        ADD CONSTRAINT ck_interviews_duration
        CHECK (duration_minutes >= 10 AND duration_minutes <= 180)
    """)


def downgrade() -> None:
    # =================================================================
    # Drop CHECK constraints
    # =================================================================
    op.execute("ALTER TABLE interviews DROP CONSTRAINT IF EXISTS ck_interviews_duration")

    # =================================================================
    # Drop indexes on existing tables
    # =================================================================
    op.drop_index("ix_applications_inquiry", table_name="applications")

    # =================================================================
    # Drop columns from existing tables
    # =================================================================
    op.drop_column("entrance_exam_results", "weight")
    op.drop_column("entrance_exam_results", "subject_name")
    op.drop_column("admission_decisions", "screening_score")
    op.drop_column("admission_decisions", "interview_score")

    # Drop FK constraint before column (applications.inquiry_id)
    op.execute("""
        ALTER TABLE applications
        DROP CONSTRAINT IF EXISTS applications_inquiry_id_fkey
    """)
    op.drop_column("applications", "inquiry_id")

    # =================================================================
    # Drop indexes on new tables
    # =================================================================
    op.drop_index("uq_screening_tenant_app_item", table_name="screening_checklists")
    op.drop_index("ix_screening_application", table_name="screening_checklists")
    op.drop_index("ix_interviews_interviewer", table_name="interviews")
    op.drop_index("ix_interviews_scheduled", table_name="interviews")
    op.drop_index("uq_interviews_application", table_name="interviews")
    op.drop_index("ix_followups_inquiry", table_name="inquiry_follow_ups")
    op.drop_index("ix_followups_pending", table_name="inquiry_follow_ups")
    op.drop_index("ix_inquiry_comms_inquiry", table_name="inquiry_communications")
    op.drop_index("ix_inquiries_assigned", table_name="inquiries")
    op.drop_index("ix_inquiries_guardian_email", table_name="inquiries")
    op.drop_index("ix_inquiries_guardian_phone", table_name="inquiries")
    op.drop_index("ix_inquiries_tenant_source", table_name="inquiries")
    op.drop_index("ix_inquiries_tenant_status", table_name="inquiries")

    # =================================================================
    # Drop RLS policies and revoke permissions
    # =================================================================
    for table_name in reversed(NEW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table_name} FROM sims_app_user")

    # =================================================================
    # Drop tables in reverse dependency order
    # =================================================================
    op.drop_table("screening_checklists")
    op.drop_table("interviews")
    op.drop_table("inquiry_follow_ups")
    op.drop_table("inquiry_communications")
    op.drop_table("inquiries")

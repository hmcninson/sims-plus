"""Preschool Phase 2: Learning Stories, Extended Care, Caregiver Ratios, Report Enhancements

Creates:
- learning_stories table with RLS
- extended_care_sessions table with RLS
- class_caregiver_ratios table with RLS
- report_type, photo_urls, chart_data columns on preschool_reports
- Updated unique constraint on preschool_reports

Revision ID: 20260330_0100
Revises: 20260328_0100
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260330_0100"
down_revision = "20260328_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. Create learning_stories table
    # ---------------------------------------------------------------
    op.create_table(
        "learning_stories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", UUID(as_uuid=True), sa.ForeignKey("terms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("learning_area_ids", JSONB(), nullable=True),
        sa.Column("skill_ids", JSONB(), nullable=True),
        sa.Column("observation_ids", JSONB(), nullable=True),
        sa.Column("attachments", JSONB(), nullable=True),
        sa.Column("is_shared_with_parents", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # 2. Create extended_care_sessions table
    # ---------------------------------------------------------------
    op.create_table(
        "extended_care_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(20), nullable=False),
        sa.Column("check_in_time", sa.Time(), nullable=False),
        sa.Column("check_out_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("checked_in_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("checked_out_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ---------------------------------------------------------------
    # 3. Create class_caregiver_ratios table
    # ---------------------------------------------------------------
    op.create_table(
        "class_caregiver_ratios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("max_children_per_caregiver", sa.Integer(), nullable=False),
        sa.Column("current_caregiver_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_class_caregiver_ratio", "class_caregiver_ratios",
        ["tenant_id", "class_id", "academic_year_id"],
    )

    # ---------------------------------------------------------------
    # 4. Add columns to preschool_reports
    # ---------------------------------------------------------------
    op.add_column("preschool_reports", sa.Column(
        "report_type", sa.String(20), nullable=False, server_default="term",
    ))
    op.add_column("preschool_reports", sa.Column(
        "photo_urls", JSONB(), nullable=True,
    ))
    op.add_column("preschool_reports", sa.Column(
        "chart_data", JSONB(), nullable=True,
    ))

    # Update unique constraint to include report_type
    op.drop_constraint("uq_preschool_report", "preschool_reports", type_="unique")
    op.create_unique_constraint(
        "uq_preschool_report_v2", "preschool_reports",
        ["tenant_id", "student_id", "term_id", "report_type"],
    )

    # ---------------------------------------------------------------
    # 5. Create indexes
    # ---------------------------------------------------------------
    for table in ["learning_stories", "extended_care_sessions", "class_caregiver_ratios"]:
        op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])
        op.create_index(f"ix_{table}_school", table, ["school_id"])

    op.create_index("ix_learning_stories_student", "learning_stories", ["tenant_id", "student_id"])
    op.create_index("ix_extended_care_sessions_student_date", "extended_care_sessions", ["tenant_id", "student_id", "session_date"])
    op.create_index("ix_class_caregiver_ratios_class", "class_caregiver_ratios", ["tenant_id", "class_id"])

    # ---------------------------------------------------------------
    # 6. CHECK constraints
    # ---------------------------------------------------------------
    op.execute("""
        ALTER TABLE extended_care_sessions
        ADD CONSTRAINT ck_session_type CHECK (session_type IN ('before_care', 'after_care')),
        ADD CONSTRAINT ck_duration_positive CHECK (duration_minutes >= 0),
        ADD CONSTRAINT ck_checkout_after_checkin CHECK (check_out_time > check_in_time)
    """)

    # ---------------------------------------------------------------
    # 7. RLS policies (using project-standard rls_helpers)
    # ---------------------------------------------------------------
    from app.db.rls_helpers import enable_rls_for_table
    conn = op.get_bind()
    for table in ["learning_stories", "extended_care_sessions", "class_caregiver_ratios"]:
        enable_rls_for_table(conn, table)


def downgrade() -> None:
    from app.db.rls_helpers import disable_rls_for_table
    conn = op.get_bind()

    # Disable RLS before dropping tables
    for table in ["class_caregiver_ratios", "extended_care_sessions", "learning_stories"]:
        disable_rls_for_table(conn, table)

    # Restore original unique constraint
    op.drop_constraint("uq_preschool_report_v2", "preschool_reports", type_="unique")
    op.create_unique_constraint(
        "uq_preschool_report", "preschool_reports",
        ["tenant_id", "student_id", "term_id"],
    )

    # Drop added columns
    op.drop_column("preschool_reports", "chart_data")
    op.drop_column("preschool_reports", "photo_urls")
    op.drop_column("preschool_reports", "report_type")

    # Drop indexes (created in upgrade step 5)
    op.drop_index("ix_class_caregiver_ratios_class", "class_caregiver_ratios")
    op.drop_index("ix_extended_care_sessions_student_date", "extended_care_sessions")
    op.drop_index("ix_learning_stories_student", "learning_stories")
    for table in ["class_caregiver_ratios", "extended_care_sessions", "learning_stories"]:
        op.drop_index(f"ix_{table}_school", table)
        op.drop_index(f"ix_{table}_tenant", table)

    # Drop tables
    op.drop_table("class_caregiver_ratios")
    op.drop_table("extended_care_sessions")
    op.drop_table("learning_stories")

"""Add admissions portal tables, enums, RLS policies, and indexes

Sprint 19-20: Admissions Portal

1. Create 16 tables with FK constraints
2. Enable RLS + FORCE RLS on all 16 tables
3. Create tenant_isolation policies using get_current_tenant_id()
4. Grant permissions to sims_app_user
5. Create composite indexes for common query patterns

Note: All status/type columns use VARCHAR (not PG enum types) for
flexibility -- the 14-value applicationstatus would be unwieldy as
a PG enum, and VARCHAR keeps all admissions tables consistent.

Revision ID: 20260303_0100
Revises: 20260302_0100
Create Date: 2026-03-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "20260303_0100"
down_revision: Union[str, None] = "20260302_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All 16 tenant-scoped tables that need RLS
ADMISSIONS_TABLES = [
    "admission_periods",
    "admission_form_configs",
    "applications",
    "application_guardians",
    "application_documents",
    "application_payments",
    "application_status_history",
    "application_notes",
    "entrance_exams",
    "entrance_exam_registrations",
    "entrance_exam_results",
    "admission_decisions",
    "class_promotions",
    "class_promotion_entries",
    "return_intent_campaigns",
    "return_intents",
]


def upgrade() -> None:
    # =================================================================
    # PHASE 1: Create tables
    # =================================================================

    # --- Table 1: admission_periods ---
    op.create_table(
        "admission_periods",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("application_fee_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("application_fee_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entrance_exam_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("max_applications", sa.Integer(), nullable=True),
        sa.Column("target_classes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 2: admission_form_configs ---
    op.create_table(
        "admission_form_configs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_period_id", UUID(as_uuid=True), sa.ForeignKey("admission_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_schema", JSONB(), nullable=False, server_default="{}"),
        sa.Column("required_documents", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "admission_period_id", name="uq_form_configs_tenant_period"),
    )

    # --- Table 3: applications ---
    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_period_id", UUID(as_uuid=True), sa.ForeignKey("admission_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tracking_code", sa.String(100), nullable=False),
        sa.Column("applicant_first_name", sa.String(100), nullable=False),
        sa.Column("applicant_last_name", sa.String(100), nullable=False),
        sa.Column("applicant_other_names", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("target_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("custom_fields", JSONB(), nullable=False, server_default="{}"),
        sa.Column("fee_waived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("exam_waived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("converted_student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applicant_photo_url", sa.String(500), nullable=True),
        sa.Column("previous_school", sa.String(255), nullable=True),
        sa.Column("medical_info", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "tracking_code", name="uq_applications_tenant_tracking"),
    )

    # --- Table 4: application_guardians ---
    op.create_table(
        "application_guardians",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 5: application_documents ---
    op.create_table(
        "application_documents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 6: application_payments ---
    op.create_table(
        "application_payments",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GHS"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "provider_reference", name="uq_payments_tenant_reference"),
    )

    # --- Table 7: application_status_history (NO soft delete, append-only) ---
    op.create_table(
        "application_status_history",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        # NOTE: No deleted_at -- this is append-only audit data (no soft deletes)
    )

    # --- Table 8: application_notes ---
    op.create_table(
        "application_notes",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 9: entrance_exams ---
    op.create_table(
        "entrance_exams",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admission_period_id", UUID(as_uuid=True), sa.ForeignKey("admission_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("venue", sa.String(255), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 10: entrance_exam_registrations ---
    op.create_table(
        "entrance_exam_registrations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entrance_exam_id", UUID(as_uuid=True), sa.ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat_number", sa.String(20), nullable=True),
        sa.Column("attended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 11: entrance_exam_results ---
    op.create_table(
        "entrance_exam_results",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entrance_exam_id", UUID(as_uuid=True), sa.ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("grade", sa.String(10), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("scored_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 12: admission_decisions ---
    op.create_table(
        "admission_decisions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_type", sa.String(20), nullable=False),
        sa.Column("decided_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("offered_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("decision_letter_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "application_id", name="uq_decisions_tenant_application"),
    )

    # --- Table 13: class_promotions ---
    op.create_table(
        "class_promotions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_students", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promoted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("graduated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("withdrawn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 14: class_promotion_entries ---
    op.create_table(
        "class_promotion_entries",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("promotion_id", UUID(as_uuid=True), sa.ForeignKey("class_promotions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_section_id", UUID(as_uuid=True), sa.ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_section_id", UUID(as_uuid=True), sa.ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(20), nullable=False, server_default="promote"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 15: return_intent_campaigns ---
    op.create_table(
        "return_intent_campaigns",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_classes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Table 16: return_intents ---
    op.create_table(
        "return_intents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("return_intent_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # =================================================================
    # PHASE 2: Enable RLS on all 16 tables
    # =================================================================
    for table_name in ADMISSIONS_TABLES:
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
    for table_name in ADMISSIONS_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")

    # =================================================================
    # PHASE 4: Create composite indexes for common query patterns
    # =================================================================

    # admission_periods
    op.create_index("ix_admission_periods_tenant_school", "admission_periods", ["tenant_id", "school_id"])
    op.create_index("ix_admission_periods_tenant_year", "admission_periods", ["tenant_id", "academic_year_id"])
    op.create_index("ix_admission_periods_tenant_status", "admission_periods", ["tenant_id", "status"])

    # admission_form_configs
    op.create_index("ix_admission_form_configs_tenant_period", "admission_form_configs", ["tenant_id", "admission_period_id"])

    # applications (most queried table)
    op.create_index("ix_applications_tenant_school", "applications", ["tenant_id", "school_id"])
    op.create_index("ix_applications_tenant_period", "applications", ["tenant_id", "admission_period_id"])
    op.create_index("ix_applications_tenant_status", "applications", ["tenant_id", "status"])
    op.create_index("ix_applications_tenant_class", "applications", ["tenant_id", "target_class_id"])

    # application_guardians
    op.create_index("ix_application_guardians_tenant_app", "application_guardians", ["tenant_id", "application_id"])

    # application_documents
    op.create_index("ix_application_documents_tenant_app", "application_documents", ["tenant_id", "application_id"])

    # application_payments
    op.create_index("ix_application_payments_tenant_app", "application_payments", ["tenant_id", "application_id"])

    # application_status_history
    op.create_index("ix_app_status_history_tenant_app", "application_status_history", ["tenant_id", "application_id"])
    op.create_index("ix_app_status_history_tenant_created", "application_status_history", ["tenant_id", "created_at"])

    # application_notes
    op.create_index("ix_application_notes_tenant_app", "application_notes", ["tenant_id", "application_id"])

    # entrance_exams
    op.create_index("ix_entrance_exams_tenant_period", "entrance_exams", ["tenant_id", "admission_period_id"])
    op.create_index("ix_entrance_exams_tenant_date", "entrance_exams", ["tenant_id", "exam_date"])

    # entrance_exam_registrations
    op.create_index("ix_exam_regs_tenant_exam", "entrance_exam_registrations", ["tenant_id", "entrance_exam_id"])
    op.create_index("ix_exam_regs_tenant_app", "entrance_exam_registrations", ["tenant_id", "application_id"], unique=True)

    # entrance_exam_results
    op.create_index("ix_exam_results_tenant_exam", "entrance_exam_results", ["tenant_id", "entrance_exam_id"])
    op.create_index("ix_exam_results_tenant_app", "entrance_exam_results", ["tenant_id", "application_id"], unique=True)

    # admission_decisions
    op.create_index("ix_admission_decisions_tenant_type", "admission_decisions", ["tenant_id", "decision_type"])

    # class_promotions
    op.create_index("ix_class_promotions_tenant_school", "class_promotions", ["tenant_id", "school_id"])
    op.create_index("ix_class_promotions_tenant_source_year", "class_promotions", ["tenant_id", "source_academic_year_id"])
    op.create_index("ix_class_promotions_tenant_target_year", "class_promotions", ["tenant_id", "target_academic_year_id"])

    # class_promotion_entries
    op.create_index("ix_promotion_entries_tenant_promotion", "class_promotion_entries", ["tenant_id", "promotion_id"])
    op.create_index("ix_promotion_entries_tenant_student", "class_promotion_entries", ["tenant_id", "student_id", "promotion_id"], unique=True)

    # return_intent_campaigns
    op.create_index("ix_return_intent_campaigns_tenant_school", "return_intent_campaigns", ["tenant_id", "school_id"])
    op.create_index("ix_return_intent_campaigns_tenant_year", "return_intent_campaigns", ["tenant_id", "academic_year_id"])

    # return_intents
    op.create_index("ix_return_intents_tenant_campaign", "return_intents", ["tenant_id", "campaign_id"])
    op.create_index("ix_return_intents_tenant_student_year", "return_intents", ["tenant_id", "student_id", "academic_year_id"], unique=True)


def downgrade() -> None:
    # Drop RLS policies and grants first
    for table_name in reversed(ADMISSIONS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
        op.execute(f"REVOKE ALL ON {table_name} FROM sims_app_user")

    # Drop tables in reverse order (child tables first to respect FK constraints)
    op.drop_table("return_intents")
    op.drop_table("return_intent_campaigns")
    op.drop_table("class_promotion_entries")
    op.drop_table("class_promotions")
    op.drop_table("admission_decisions")
    op.drop_table("entrance_exam_results")
    op.drop_table("entrance_exam_registrations")
    op.drop_table("entrance_exams")
    op.drop_table("application_notes")
    op.drop_table("application_status_history")
    op.drop_table("application_payments")
    op.drop_table("application_documents")
    op.drop_table("application_guardians")
    op.drop_table("applications")
    op.drop_table("admission_form_configs")
    op.drop_table("admission_periods")

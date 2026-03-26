"""Add external exam registrations, student credit accumulations, and predicted grades

Phase 3 migration for Multi-Curriculum support:

1. Create externalexamboard enum type
2. Create external_exam_registrations table (exam board registration tracking)
3. Create student_credit_accumulations table (credit/GPA tracking)
4. Create predicted_grades table (teacher predicted grades)
5. Enable RLS on all 3 tables
6. Add indexes for common query patterns

Revision ID: 20260320_0100
Revises: 20260315_0100
Create Date: 2026-03-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.db.rls_helpers import disable_rls_for_table, enable_rls_for_table


revision: str = "20260320_0100"
down_revision: Union[str, None] = "20260315_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. Define externalexamboard enum (created by create_table)
    # ============================================================
    externalexamboard = sa.Enum(
        "waec", "cambridge_international", "edexcel",
        "college_board", "ibo", "other",
        name="externalexamboard",
    )

    # ============================================================
    # 2. Create external_exam_registrations table
    # ============================================================
    op.create_table(
        "external_exam_registrations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), nullable=False),
        sa.Column("exam_board", externalexamboard, nullable=False),
        sa.Column("exam_session", sa.String(20), nullable=False),
        sa.Column("candidate_number", sa.String(50), nullable=True),
        sa.Column("center_number", sa.String(20), nullable=True),
        sa.Column("registration_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("subjects", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("results", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("registration_date", sa.Date(), nullable=True),
        sa.Column("results_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "registration_status IN ('pending', 'registered', 'confirmed')",
            name="chk_registration_status",
        ),
    )

    # Partial unique index (accounts for soft delete)
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_external_exam_registration
        ON external_exam_registrations (tenant_id, student_id, exam_board, exam_session)
        WHERE deleted_at IS NULL
    """))

    # ============================================================
    # 3. Create student_credit_accumulations table
    # ============================================================
    op.create_table(
        "student_credit_accumulations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_profile_id", UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), nullable=False),
        sa.Column("term_id", UUID(as_uuid=True), nullable=True),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("credits_attempted", sa.Numeric(4, 1), nullable=False),
        sa.Column("credits_earned", sa.Numeric(4, 1), nullable=False),
        sa.Column("grade_points", sa.Numeric(5, 2), nullable=True),
        sa.Column("weighted_grade_points", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_ap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_honors", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["curriculum_profile_id"], ["curriculum_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
    )

    # COALESCE-based unique index (NULL term_id = whole-year accumulation)
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_student_credit
        ON student_credit_accumulations (
            tenant_id, student_id, subject_id, academic_year_id,
            COALESCE(term_id, '00000000-0000-0000-0000-000000000000'::UUID)
        )
    """))

    # ============================================================
    # 4. Create predicted_grades table
    # ============================================================
    op.create_table(
        "predicted_grades",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), nullable=False),
        sa.Column("term_id", UUID(as_uuid=True), nullable=True),
        sa.Column("predicted_grade", sa.String(10), nullable=True),
        sa.Column("target_grade", sa.String(10), nullable=True),
        sa.Column("predicted_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("predicted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["predicted_by"], ["users.id"], ondelete="SET NULL"),
    )

    # Partial unique index (accounts for soft delete)
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_predicted_grade
        ON predicted_grades (
            tenant_id, student_id, subject_id, academic_year_id,
            COALESCE(term_id, '00000000-0000-0000-0000-000000000000'::UUID)
        )
        WHERE deleted_at IS NULL
    """))

    # ============================================================
    # 5. Enable RLS on all 3 tables
    # ============================================================
    conn = op.get_bind()
    for table_name in [
        "external_exam_registrations",
        "student_credit_accumulations",
        "predicted_grades",
    ]:
        enable_rls_for_table(conn, table_name)

    # ============================================================
    # 6. Create indexes
    # ============================================================
    # external_exam_registrations
    op.create_index("ix_external_exam_registrations_tenant_id", "external_exam_registrations", ["tenant_id"])
    op.create_index("ix_external_exam_registrations_school_id", "external_exam_registrations", ["school_id"])
    op.create_index("ix_external_exam_registrations_student_id", "external_exam_registrations", ["student_id"])
    op.create_index(
        "ix_external_exam_registrations_tenant_student",
        "external_exam_registrations",
        ["tenant_id", "student_id"],
    )

    # student_credit_accumulations
    op.create_index("ix_student_credit_accumulations_tenant_id", "student_credit_accumulations", ["tenant_id"])
    op.create_index("ix_student_credit_accumulations_school_id", "student_credit_accumulations", ["school_id"])
    op.create_index("ix_student_credit_accumulations_student_id", "student_credit_accumulations", ["student_id"])
    op.create_index(
        "ix_student_credit_accumulations_tenant_student_profile",
        "student_credit_accumulations",
        ["tenant_id", "student_id", "curriculum_profile_id"],
    )

    # predicted_grades
    op.create_index("ix_predicted_grades_tenant_id", "predicted_grades", ["tenant_id"])
    op.create_index("ix_predicted_grades_school_id", "predicted_grades", ["school_id"])
    op.create_index("ix_predicted_grades_student_id", "predicted_grades", ["student_id"])
    op.execute(sa.text("""
        CREATE INDEX ix_predicted_grades_tenant_student_year
        ON predicted_grades (tenant_id, student_id, academic_year_id)
        WHERE deleted_at IS NULL
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Disable RLS
    for table_name in ["predicted_grades", "student_credit_accumulations", "external_exam_registrations"]:
        disable_rls_for_table(conn, table_name)

    # Drop partial/unique indexes
    op.execute(sa.text("DROP INDEX IF EXISTS uq_predicted_grade"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_student_credit"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_external_exam_registration"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_predicted_grades_tenant_student_year"))

    # Drop tables (reverse order)
    op.drop_table("predicted_grades")
    op.drop_table("student_credit_accumulations")
    op.drop_table("external_exam_registrations")

    # Drop enum
    op.execute(sa.text("DROP TYPE IF EXISTS externalexamboard"))

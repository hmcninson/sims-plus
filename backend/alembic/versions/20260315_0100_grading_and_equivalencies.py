"""Add grade equivalencies, subject curriculum mappings, and curriculum columns

Phase 2 migration for Multi-Curriculum support:

1. Create grade_equivalencies table (cross-curriculum grade mapping)
2. Create subject_curriculum_mappings table (subject-to-curriculum metadata)
3. Add curriculum columns to term_reports (GPA, credits, honor roll, etc.)
4. Add effort_grade column to exam_scores
5. Add credit_value/coefficient columns to subjects
6. Enable RLS on new tables
7. Add indexes for common query patterns

Revision ID: 20260315_0100
Revises: 20260310_0200
Create Date: 2026-03-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.db.rls_helpers import disable_rls_for_table, enable_rls_for_table


revision: str = "20260315_0100"
down_revision: Union[str, None] = "20260310_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. Create grade_equivalencies table
    # ============================================================
    op.create_table(
        "grade_equivalencies",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_grading_scale_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_grading_scale_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_grade_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_grade_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_grading_scale_id"], ["grading_scales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_grading_scale_id"], ["grading_scales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_grade_id"], ["grades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_grade_id"], ["grades.id"], ondelete="CASCADE"),
        # Unique constraint
        sa.UniqueConstraint("tenant_id", "source_grade_id", "target_grading_scale_id", name="uq_grade_equivalency"),
    )

    # ============================================================
    # 2. Create subject_curriculum_mappings table
    # ============================================================
    op.create_table(
        "subject_curriculum_mappings",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), nullable=True),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_profile_id", UUID(as_uuid=True), nullable=False),
        sa.Column("external_code", sa.String(20), nullable=True),
        sa.Column("external_name", sa.String(200), nullable=True),
        sa.Column("level", sa.String(50), nullable=True),
        sa.Column("credits", sa.Numeric(4, 1), nullable=True),
        sa.Column("coefficient", sa.Numeric(4, 1), nullable=True),
        sa.Column("is_hl", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("grading_scale_id", UUID(as_uuid=True), nullable=True),
        sa.Column("config", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["curriculum_profile_id"], ["curriculum_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grading_scale_id"], ["grading_scales.id"], ondelete="SET NULL"),
        # Unique constraint
        sa.UniqueConstraint("tenant_id", "subject_id", "curriculum_profile_id", name="uq_subject_curriculum_mapping"),
    )

    # ============================================================
    # 3. Add columns to exam_scores
    # ============================================================
    op.add_column("exam_scores", sa.Column("effort_grade", sa.String(5), nullable=True))

    # ============================================================
    # 4. Add columns to term_reports
    # ============================================================
    op.add_column("term_reports", sa.Column(
        "curriculum_profile_id", UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        "fk_term_reports_curriculum_profile_id",
        "term_reports", "curriculum_profiles",
        ["curriculum_profile_id"], ["id"],
        ondelete="SET NULL",
    )
    op.add_column("term_reports", sa.Column("gpa", sa.Numeric(4, 2), nullable=True))
    op.add_column("term_reports", sa.Column("weighted_gpa", sa.Numeric(4, 2), nullable=True))
    op.add_column("term_reports", sa.Column("cumulative_gpa", sa.Numeric(4, 2), nullable=True))
    op.add_column("term_reports", sa.Column("total_credits_earned", sa.Numeric(5, 1), nullable=True))
    op.add_column("term_reports", sa.Column("cumulative_credits", sa.Numeric(5, 1), nullable=True))
    op.add_column("term_reports", sa.Column("honor_roll", sa.Boolean(), nullable=True))
    op.add_column("term_reports", sa.Column("ib_total_points", sa.Integer(), nullable=True))
    op.add_column("term_reports", sa.Column("french_mention", sa.String(20), nullable=True))
    op.add_column("term_reports", sa.Column("extra_data", sa.dialects.postgresql.JSONB(), nullable=True))

    # ============================================================
    # 5. Add columns to subjects
    # ============================================================
    op.add_column("subjects", sa.Column("credit_value", sa.Numeric(4, 1), nullable=True))
    op.add_column("subjects", sa.Column("coefficient", sa.Numeric(4, 1), nullable=True))

    # ============================================================
    # 6. Enable RLS on new tables
    # ============================================================
    conn = op.get_bind()
    for table_name in ["grade_equivalencies", "subject_curriculum_mappings"]:
        enable_rls_for_table(conn, table_name)

    # ============================================================
    # 7. Create indexes
    # ============================================================
    # grade_equivalencies indexes
    op.create_index("ix_grade_equivalencies_tenant_id", "grade_equivalencies", ["tenant_id"])
    op.create_index("ix_grade_equivalencies_school_id", "grade_equivalencies", ["school_id"])
    op.create_index("ix_grade_equivalencies_source_scale", "grade_equivalencies", ["source_grading_scale_id"])
    op.create_index("ix_grade_equivalencies_target_scale", "grade_equivalencies", ["target_grading_scale_id"])
    op.create_index(
        "ix_grade_equivalencies_tenant_source_target",
        "grade_equivalencies",
        ["tenant_id", "source_grading_scale_id", "target_grading_scale_id"],
    )

    # subject_curriculum_mappings indexes
    op.create_index("ix_subject_curriculum_mappings_tenant_id", "subject_curriculum_mappings", ["tenant_id"])
    op.create_index("ix_subject_curriculum_mappings_school_id", "subject_curriculum_mappings", ["school_id"])
    op.create_index("ix_subject_curriculum_mappings_subject", "subject_curriculum_mappings", ["subject_id"])
    op.create_index("ix_subject_curriculum_mappings_profile", "subject_curriculum_mappings", ["curriculum_profile_id"])
    op.create_index(
        "ix_subject_curriculum_mappings_tenant_profile",
        "subject_curriculum_mappings",
        ["tenant_id", "curriculum_profile_id"],
    )

    # Indexes on new FK columns in existing tables
    op.create_index("ix_term_reports_curriculum_profile_id", "term_reports", ["curriculum_profile_id"])


def downgrade() -> None:
    # Disable RLS before dropping
    conn = op.get_bind()
    for table_name in ["subject_curriculum_mappings", "grade_equivalencies"]:
        disable_rls_for_table(conn, table_name)

    # Drop indexes on existing tables
    op.drop_index("ix_term_reports_curriculum_profile_id", table_name="term_reports")

    # Drop new tables (reverse order of creation)
    op.drop_table("subject_curriculum_mappings")
    op.drop_table("grade_equivalencies")

    # Remove columns added to subjects
    op.drop_column("subjects", "coefficient")
    op.drop_column("subjects", "credit_value")

    # Remove columns added to term_reports
    op.drop_column("term_reports", "extra_data")
    op.drop_column("term_reports", "french_mention")
    op.drop_column("term_reports", "ib_total_points")
    op.drop_column("term_reports", "honor_roll")
    op.drop_column("term_reports", "cumulative_credits")
    op.drop_column("term_reports", "total_credits_earned")
    op.drop_column("term_reports", "cumulative_gpa")
    op.drop_column("term_reports", "weighted_gpa")
    op.drop_column("term_reports", "gpa")
    op.drop_column("term_reports", "curriculum_profile_id")

    # Remove columns added to exam_scores
    op.drop_column("exam_scores", "effort_grade")

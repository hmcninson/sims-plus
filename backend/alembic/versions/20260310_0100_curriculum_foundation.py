"""Add multi-curriculum foundation tables, enums, RLS policies, and indexes

Phase 1 of Multi-Curriculum Support:

1. Create 4 new enum types (curriculumtype, assessmentcomponenttype, scoredisplaymode, academiccalendartype)
2. Extend existing gradingscaletype enum with 6 new values
3. Create 4 new tables (curriculum_profiles, assessment_structures, assessment_components, report_card_configs)
4. Enable RLS + FORCE RLS on all 4 tables via rls_helpers
5. Add curriculum_profile_id FK column to schools, classes, students, grading_scales
6. Create composite indexes for common query patterns

Revision ID: 20260310_0100
Revises: 20260303_0200
Create Date: 2026-03-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.rls_helpers import enable_rls_for_table, disable_rls_for_table


revision: str = "20260310_0100"
down_revision: Union[str, None] = "20260303_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All 4 new tenant-scoped tables that need RLS
CURRICULUM_TABLES = [
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
]


def upgrade() -> None:
    connection = op.get_bind()

    # =================================================================
    # STEP 1: Extend existing gradingscaletype enum
    #
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    # We commit the Alembic-managed transaction, execute outside a tx,
    # then start a new transaction for the remaining DDL.
    # =================================================================
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text(
        "ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'cambridge'"
    ))
    connection.execute(sa.text(
        "ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'edexcel'"
    ))
    connection.execute(sa.text(
        "ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'ib'"
    ))
    connection.execute(sa.text(
        "ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'french'"
    ))
    connection.execute(sa.text(
        "ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'narrative'"
    ))
    connection.execute(sa.text(
        "ALTER TYPE gradingscaletype ADD VALUE IF NOT EXISTS 'american'"
    ))
    # Start a new transaction for the remaining DDL
    connection.execute(sa.text("BEGIN"))

    # =================================================================
    # STEP 3: Create tables (in FK dependency order)
    # =================================================================

    # --- Table 1: curriculum_profiles ---
    op.create_table(
        "curriculum_profiles",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False, comment="Profile name, e.g., 'Cambridge IGCSE', 'GES Standard'"),
        sa.Column("curriculum_type", sa.Enum(
            "ges", "cambridge", "edexcel", "american", "ib", "french", "montessori", "custom",
            name="curriculumtype", create_type=True,
        ), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("grading_scale_id", UUID(as_uuid=True), sa.ForeignKey("grading_scales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("academic_calendar_type", sa.Enum(
            "terms", "semesters", "quarters",
            name="academiccalendartype", create_type=True,
        ), nullable=False, server_default="terms"),
        sa.Column("periods_per_year", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("score_display_mode", sa.Enum(
            "percentage", "grade_only", "grade_and_score", "level", "gpa", "narrative", "mention",
            name="scoredisplaymode", create_type=True,
        ), nullable=False, server_default="grade_and_score"),
        sa.Column("show_position", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_class_average", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("use_gpa", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("use_credits", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("use_criterion_grading", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("config", JSONB(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial unique index (allows re-use of name after soft delete)
    op.create_index(
        "uq_curriculum_profile_name",
        "curriculum_profiles",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- Table 2: assessment_structures ---
    op.create_table(
        "assessment_structures",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("curriculum_profile_id", UUID(as_uuid=True), sa.ForeignKey("curriculum_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, comment="e.g., 'IGCSE Assessment Structure'"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # COALESCE-based unique index: one structure per profile per year
    op.create_index(
        "uq_assessment_structure",
        "assessment_structures",
        ["tenant_id", "curriculum_profile_id", sa.text("COALESCE(academic_year_id, '00000000-0000-0000-0000-000000000000')")],
        unique=True,
    )

    # --- Table 3: assessment_components ---
    op.create_table(
        "assessment_components",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("assessment_structure_id", UUID(as_uuid=True), sa.ForeignKey("assessment_structures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_type", sa.Enum(
            "continuous_assessment", "exam", "class_work", "homework", "midterm", "end_term",
            "coursework", "controlled_assessment", "external_exam", "practical", "oral",
            "internal_assessment", "external_assessment", "extended_essay", "tok", "cas",
            "quiz", "test", "project", "participation", "final",
            "controle_continu", "epreuve",
            "observation", "narrative", "portfolio",
            name="assessmentcomponenttype", create_type=True,
        ), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, comment="Display name, e.g., 'Coursework'"),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False, comment="Percentage weight (must sum to 100)"),
        sa.Column("max_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_external", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("maps_to_ca", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("maps_to_exam", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("config", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # --- Table 4: report_card_configs ---
    op.create_table(
        "report_card_configs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("curriculum_profile_id", UUID(as_uuid=True), sa.ForeignKey("curriculum_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_key", sa.String(50), nullable=False, server_default="default"),
        sa.Column("show_position", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_class_average", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_subject_position", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_effort_grade", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("show_predicted_grades", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("show_gpa", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("show_credits", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("show_honor_roll", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("show_learner_profile", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("show_atl_skills", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("custom_columns", JSONB(), nullable=True),
        sa.Column("header_text", sa.Text(), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial unique index: allows re-creating a config after soft delete
    op.create_index(
        "uq_report_card_config",
        "report_card_configs",
        ["tenant_id", "curriculum_profile_id", "template_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # =================================================================
    # STEP 4: Enable RLS on all 4 new tables
    # =================================================================
    for table_name in CURRICULUM_TABLES:
        enable_rls_for_table(connection, table_name)

    # =================================================================
    # STEP 5: Add curriculum_profile_id to existing tables
    # =================================================================

    # schools
    op.add_column(
        "schools",
        sa.Column(
            "curriculum_profile_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="School's default curriculum profile",
        ),
    )
    op.create_foreign_key(
        "fk_schools_curriculum_profile_id",
        "schools",
        "curriculum_profiles",
        ["curriculum_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "schools",
        sa.Column(
            "curriculum_settings",
            JSONB(),
            nullable=True,
            comment="School-level curriculum overrides",
        ),
    )

    # classes
    op.add_column(
        "classes",
        sa.Column(
            "curriculum_profile_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Class-level curriculum override (for dual-track schools)",
        ),
    )
    op.create_foreign_key(
        "fk_classes_curriculum_profile_id",
        "classes",
        "curriculum_profiles",
        ["curriculum_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # students
    op.add_column(
        "students",
        sa.Column(
            "curriculum_profile_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Student's current curriculum (inherited from class if NULL)",
        ),
    )
    op.create_foreign_key(
        "fk_students_curriculum_profile_id",
        "students",
        "curriculum_profiles",
        ["curriculum_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "students",
        sa.Column(
            "previous_curriculum_type",
            sa.String(20),
            nullable=True,
            comment="For transfer students -- records origin curriculum type",
        ),
    )

    # grading_scales
    op.add_column(
        "grading_scales",
        sa.Column(
            "curriculum_profile_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Links scale to a curriculum (NULL = usable by all)",
        ),
    )
    op.create_foreign_key(
        "fk_grading_scales_curriculum_profile_id",
        "grading_scales",
        "curriculum_profiles",
        ["curriculum_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # =================================================================
    # STEP 6: Create indexes
    # =================================================================

    # FK indexes on new tables
    op.create_index(
        "ix_assessment_structures_profile_id",
        "assessment_structures",
        ["curriculum_profile_id"],
    )
    op.create_index(
        "ix_assessment_components_structure_id",
        "assessment_components",
        ["assessment_structure_id"],
    )
    op.create_index(
        "ix_report_card_configs_profile_id",
        "report_card_configs",
        ["curriculum_profile_id"],
    )

    # FK indexes on existing tables
    op.create_index(
        "ix_schools_curriculum_profile_id",
        "schools",
        ["curriculum_profile_id"],
    )
    op.create_index(
        "ix_classes_curriculum_profile_id",
        "classes",
        ["curriculum_profile_id"],
    )
    op.create_index(
        "ix_students_curriculum_profile_id",
        "students",
        ["curriculum_profile_id"],
    )
    op.create_index(
        "ix_grading_scales_curriculum_profile_id",
        "grading_scales",
        ["curriculum_profile_id"],
    )

    # Composite indexes for common multi-tenant query patterns
    op.create_index(
        "ix_curriculum_profiles_tenant_school_active",
        "curriculum_profiles",
        ["tenant_id", "school_id", "is_active"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_curriculum_profiles_default",
        "curriculum_profiles",
        ["tenant_id", "school_id"],
        postgresql_where=sa.text("is_default = true AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_assessment_structures_tenant_profile_year",
        "assessment_structures",
        ["tenant_id", "curriculum_profile_id", "academic_year_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()

    # =================================================================
    # Drop indexes on existing tables
    # =================================================================
    op.drop_index("ix_assessment_structures_tenant_profile_year", table_name="assessment_structures")
    op.drop_index("ix_curriculum_profiles_default", table_name="curriculum_profiles")
    op.drop_index("ix_curriculum_profiles_tenant_school_active", table_name="curriculum_profiles")
    op.drop_index("ix_grading_scales_curriculum_profile_id", table_name="grading_scales")
    op.drop_index("ix_students_curriculum_profile_id", table_name="students")
    op.drop_index("ix_classes_curriculum_profile_id", table_name="classes")
    op.drop_index("ix_schools_curriculum_profile_id", table_name="schools")
    op.drop_index("ix_report_card_configs_profile_id", table_name="report_card_configs")
    op.drop_index("ix_assessment_components_structure_id", table_name="assessment_components")
    op.drop_index("ix_assessment_structures_profile_id", table_name="assessment_structures")

    # =================================================================
    # Drop FK constraints and columns from existing tables
    # =================================================================

    # grading_scales
    op.drop_constraint("fk_grading_scales_curriculum_profile_id", "grading_scales", type_="foreignkey")
    op.drop_column("grading_scales", "curriculum_profile_id")

    # students
    op.drop_column("students", "previous_curriculum_type")
    op.drop_constraint("fk_students_curriculum_profile_id", "students", type_="foreignkey")
    op.drop_column("students", "curriculum_profile_id")

    # classes
    op.drop_constraint("fk_classes_curriculum_profile_id", "classes", type_="foreignkey")
    op.drop_column("classes", "curriculum_profile_id")

    # schools
    op.drop_column("schools", "curriculum_settings")
    op.drop_constraint("fk_schools_curriculum_profile_id", "schools", type_="foreignkey")
    op.drop_column("schools", "curriculum_profile_id")

    # =================================================================
    # Disable RLS on new tables
    # =================================================================
    for table_name in reversed(CURRICULUM_TABLES):
        disable_rls_for_table(connection, table_name)

    # =================================================================
    # Drop new tables (reverse order of creation)
    # =================================================================
    op.drop_index("uq_curriculum_profile_name", table_name="curriculum_profiles")
    op.drop_index("uq_assessment_structure", table_name="assessment_structures")
    op.drop_table("report_card_configs")
    op.drop_table("assessment_components")
    op.drop_table("assessment_structures")
    op.drop_table("curriculum_profiles")

    # =================================================================
    # Drop new enum types
    # =================================================================
    op.execute(sa.text("DROP TYPE IF EXISTS academiccalendartype"))
    op.execute(sa.text("DROP TYPE IF EXISTS scoredisplaymode"))
    op.execute(sa.text("DROP TYPE IF EXISTS assessmentcomponenttype"))
    op.execute(sa.text("DROP TYPE IF EXISTS curriculumtype"))

    # NOTE: Cannot remove values from gradingscaletype enum.
    # The 6 new values (cambridge, edexcel, ib, french, narrative, american)
    # will remain. This is acceptable and backward-compatible.

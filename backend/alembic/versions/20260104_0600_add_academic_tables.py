"""Add academic tables (Sprint 6)

Revision ID: 20260104_0600
Revises: 549287f1f9df
Create Date: 2026-01-04

Creates tables for:
- academic_years
- terms
- classes
- class_sections
- subjects
- class_subjects
- grading_scales
- grades
- assessment_weights

All tenant-scoped tables have RLS policies applied.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260104_0600"
down_revision = "549287f1f9df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE academicyearstatus AS ENUM ('planning', 'active', 'completed');
    """)
    op.execute("""
        CREATE TYPE termstatus AS ENUM ('upcoming', 'active', 'completed');
    """)
    op.execute("""
        CREATE TYPE classlevel AS ENUM (
            'nursery_1', 'nursery_2', 'kg_1', 'kg_2',
            'primary_1', 'primary_2', 'primary_3', 'primary_4', 'primary_5', 'primary_6',
            'jhs_1', 'jhs_2', 'jhs_3',
            'shs_1', 'shs_2', 'shs_3'
        );
    """)
    op.execute("""
        CREATE TYPE subjectcategory AS ENUM ('core', 'elective', 'vocational', 'extra');
    """)
    op.execute("""
        CREATE TYPE gradingscaletype AS ENUM ('waec', 'gpa', 'percentage', 'custom');
    """)

    # =========================
    # Academic Years Table
    # =========================
    op.create_table(
        "academic_years",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False, comment="Year name, e.g., 2025/2026"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False, comment="Academic year start date"),
        sa.Column("end_date", sa.Date(), nullable=False, comment="Academic year end date"),
        sa.Column("status", postgresql.ENUM("planning", "active", "completed", name="academicyearstatus", create_type=False), server_default="planning", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", comment="Is this the current academic year?"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_academic_year_name"),
    )
    op.create_index("ix_academic_years_tenant_id", "academic_years", ["tenant_id"])

    # =========================
    # Terms Table
    # =========================
    op.create_table(
        "terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False, comment="Term name, e.g., First Term"),
        sa.Column("short_name", sa.String(20), nullable=True, comment="Short name, e.g., Term 1"),
        sa.Column("sequence", sa.Integer(), server_default="1", comment="Order of term within year"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM("upcoming", "active", "completed", name="termstatus", create_type=False), server_default="upcoming", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", comment="Is this the current term?"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "academic_year_id", "name", name="uq_term_name"),
    )
    op.create_index("ix_terms_tenant_id", "terms", ["tenant_id"])
    op.create_index("ix_terms_academic_year_id", "terms", ["academic_year_id"])

    # =========================
    # Classes Table
    # =========================
    op.create_table(
        "classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False, comment="Class name, e.g., JHS 1"),
        sa.Column("short_name", sa.String(20), nullable=True, comment="Short name, e.g., J1"),
        sa.Column("level", postgresql.ENUM(
            'nursery_1', 'nursery_2', 'kg_1', 'kg_2',
            'primary_1', 'primary_2', 'primary_3', 'primary_4', 'primary_5', 'primary_6',
            'jhs_1', 'jhs_2', 'jhs_3', 'shs_1', 'shs_2', 'shs_3',
            name="classlevel", create_type=False
        ), nullable=True, comment="Standard level mapping"),
        sa.Column("sequence", sa.Integer(), server_default="1", comment="Order for display"),
        sa.Column("capacity", sa.Integer(), nullable=True, comment="Maximum students"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_class_name"),
    )
    op.create_index("ix_classes_tenant_id", "classes", ["tenant_id"])
    op.create_index("ix_classes_school_id", "classes", ["school_id"])

    # =========================
    # Class Sections Table
    # =========================
    op.create_table(
        "class_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False, comment="Section name, e.g., A, B"),
        sa.Column("capacity", sa.Integer(), nullable=True, comment="Maximum students in section"),
        sa.Column("class_teacher_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Assigned class teacher"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "class_id", "name", name="uq_section_name"),
    )
    op.create_index("ix_class_sections_tenant_id", "class_sections", ["tenant_id"])
    op.create_index("ix_class_sections_class_id", "class_sections", ["class_id"])

    # =========================
    # Subjects Table
    # =========================
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, comment="Subject name"),
        sa.Column("code", sa.String(20), nullable=False, comment="Subject code, e.g., MATH"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", postgresql.ENUM("core", "elective", "vocational", "extra", name="subjectcategory", create_type=False), server_default="core", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_subject_code"),
    )
    op.create_index("ix_subjects_tenant_id", "subjects", ["tenant_id"])

    # =========================
    # Class Subjects (M2M) Table
    # =========================
    op.create_table(
        "class_subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("periods_per_week", sa.Integer(), nullable=True, comment="Number of periods per week"),
        sa.Column("is_compulsory", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "class_id", "subject_id", name="uq_class_subject"),
    )
    op.create_index("ix_class_subjects_tenant_id", "class_subjects", ["tenant_id"])

    # =========================
    # Grading Scales Table
    # =========================
    op.create_table(
        "grading_scales",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, comment="Scale name, e.g., WAEC Standard"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("scale_type", postgresql.ENUM("waec", "gpa", "percentage", "custom", name="gradingscaletype", create_type=False), server_default="waec", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_grading_scale_name"),
    )
    op.create_index("ix_grading_scales_tenant_id", "grading_scales", ["tenant_id"])

    # =========================
    # Grades Table
    # =========================
    op.create_table(
        "grades",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grading_scale_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade", sa.String(10), nullable=False, comment="Grade symbol, e.g., A1, B2"),
        sa.Column("min_score", sa.Numeric(5, 2), nullable=False, comment="Minimum score for this grade"),
        sa.Column("max_score", sa.Numeric(5, 2), nullable=False, comment="Maximum score for this grade"),
        sa.Column("grade_point", sa.Numeric(3, 2), nullable=True, comment="Grade point value (for GPA)"),
        sa.Column("remark", sa.String(50), nullable=True, comment="Grade remark, e.g., Excellent"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["grading_scale_id"], ["grading_scales.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "grading_scale_id", "grade", name="uq_grade"),
    )
    op.create_index("ix_grades_tenant_id", "grades", ["tenant_id"])
    op.create_index("ix_grades_grading_scale_id", "grades", ["grading_scale_id"])

    # =========================
    # Assessment Weights Table
    # =========================
    op.create_table(
        "assessment_weights",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Specific to an academic year, or null for default"),
        sa.Column("class_work_weight", sa.Numeric(5, 2), server_default="20", comment="Class work percentage"),
        sa.Column("homework_weight", sa.Numeric(5, 2), server_default="10", comment="Homework percentage"),
        sa.Column("midterm_weight", sa.Numeric(5, 2), server_default="20", comment="Mid-term exam percentage"),
        sa.Column("end_term_weight", sa.Numeric(5, 2), server_default="50", comment="End of term exam percentage"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "academic_year_id", name="uq_assessment_weight"),
    )
    op.create_index("ix_assessment_weights_tenant_id", "assessment_weights", ["tenant_id"])

    # =========================
    # Enable RLS on all tables
    # =========================
    tables = [
        "academic_years",
        "terms",
        "classes",
        "class_sections",
        "subjects",
        "class_subjects",
        "grading_scales",
        "grades",
        "assessment_weights",
    ]

    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

        # Create RLS policy
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR current_setting('app.is_platform_admin', true) = 'true'
                OR current_setting('app.current_tenant_id', true) IS NULL
                OR current_setting('app.current_tenant_id', true) = ''
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
                OR current_setting('app.is_platform_admin', true) = 'true'
            );
        """)


def downgrade() -> None:
    # Drop RLS policies and tables
    tables = [
        "assessment_weights",
        "grades",
        "grading_scales",
        "class_subjects",
        "subjects",
        "class_sections",
        "classes",
        "terms",
        "academic_years",
    ]

    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.drop_table(table)

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS gradingscaletype;")
    op.execute("DROP TYPE IF EXISTS subjectcategory;")
    op.execute("DROP TYPE IF EXISTS classlevel;")
    op.execute("DROP TYPE IF EXISTS termstatus;")
    op.execute("DROP TYPE IF EXISTS academicyearstatus;")

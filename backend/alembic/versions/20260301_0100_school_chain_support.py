"""Add school chain support: user_schools table, school_id columns, backfill

Sprint 17-18: School Chain Support

1. Create user_schools junction table with RLS
2. Add nullable school_id column to 32 tables that don't have it yet
3. Backfill school_id from each tenant's single school
4. Backfill user_schools from existing users
5. Add composite (tenant_id, school_id) indexes
6. Update unique constraints with COALESCE pattern for school_id

Revision ID: 20260301_0100
Revises: 20260224_0100
Create Date: 2026-03-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "20260301_0100"
down_revision: Union[str, None] = "20260224_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -----------------------------------------------------------------------
# Tables that need school_id added (32 tables)
# Grouped by category for clarity
# -----------------------------------------------------------------------
TABLES_NEEDING_SCHOOL_ID = [
    # Academic
    "academic_years",
    "terms",
    "class_sections",
    "class_subjects",
    "subjects",
    "grading_scales",
    "grades",
    "assessment_weights",
    "academic_settings",
    "school_holidays",
    "school_periods",
    "class_timetables",
    # Staff
    "departments",
    "staff_class_assignments",
    # Students
    "guardians",
    "student_guardians",
    # Attendance
    "student_attendance",
    "staff_attendance",
    # Exams
    "exams",
    "exam_subjects",
    "exam_scores",
    "score_change_logs",
    "continuous_assessments",
    "term_reports",
    # Preschool
    "learning_areas",
    "developmental_skills",
    "preschool_rating_scales",
    "preschool_ratings",
    "student_skill_assessments",
    "progress_observations",
    "daily_activity_logs",
    "preschool_reports",
    # Finance
    "fee_items",
    "invoice_items",
    "invoice_scholarship_items",
    "student_scholarships",
    "scholarship_applications",
    "finance_audit_log",
    # Teacher Portal
    "report_comments",
    "lesson_plans",
]

# Sentinel UUID for COALESCE in unique constraints (NULL-safe)
NULL_SCHOOL_SENTINEL = "00000000-0000-0000-0000-000000000000"


def _enable_rls(table_name: str) -> None:
    """Enable and force RLS with hardened tenant isolation policy."""
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user"
    )


def upgrade() -> None:
    # =================================================================
    # 1. Create user_schools junction table
    # =================================================================
    op.create_table(
        "user_schools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("role_at_school", sa.String(50), nullable=False,
                  comment="User's role at this specific school"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false"),
                  comment="Primary school shown on login"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"),
                  comment="Whether the user currently has access"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "user_id", "school_id",
                            name="uq_user_school_tenant"),
    )

    # Create tenant_id index for RLS performance
    op.create_index("ix_user_schools_tenant_id", "user_schools", ["tenant_id"])

    # Enable RLS on user_schools
    _enable_rls("user_schools")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user")

    # =================================================================
    # 2. Add nullable school_id column to 32 tables + FK + index
    # =================================================================
    for table_name in TABLES_NEEDING_SCHOOL_ID:
        # Check if column already exists (idempotent)
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    AND column_name = 'school_id'
                ) THEN
                    ALTER TABLE {table_name}
                    ADD COLUMN school_id UUID REFERENCES schools(id) ON DELETE SET NULL;

                    CREATE INDEX IF NOT EXISTS ix_{table_name}_school_id
                    ON {table_name} (school_id);
                END IF;
            END $$;
        """)

        # Add composite (tenant_id, school_id) index for chain queries
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant_school
            ON {table_name} (tenant_id, school_id)
            WHERE school_id IS NOT NULL;
        """)

    # =================================================================
    # 3. Backfill school_id from each tenant's single school
    # =================================================================
    # For each tenant, find their school(s). Single-school tenants have
    # exactly one school. Chain tenants (if any exist) are skipped because
    # their rows can't be auto-assigned to a single school.
    op.execute("""
        DO $$
        DECLARE
            t RECORD;
            school_uuid UUID;
            school_count INT;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                -- Count schools for this tenant
                SELECT COUNT(*) INTO school_count
                FROM schools WHERE tenant_id = t.id AND deleted_at IS NULL;

                -- Only backfill for single-school tenants
                IF school_count = 1 THEN
                    SELECT id INTO school_uuid
                    FROM schools WHERE tenant_id = t.id AND deleted_at IS NULL LIMIT 1;

                    -- Update each table's null school_id rows
                    UPDATE academic_years SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE terms SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE class_sections SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE class_subjects SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE subjects SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE grading_scales SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE grades SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE assessment_weights SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE academic_settings SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE school_holidays SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE school_periods SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE class_timetables SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE departments SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE staff_class_assignments SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE guardians SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE student_guardians SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE student_attendance SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE staff_attendance SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE exams SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE exam_subjects SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE exam_scores SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE score_change_logs SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE continuous_assessments SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE term_reports SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE learning_areas SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE developmental_skills SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE preschool_rating_scales SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE preschool_ratings SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE student_skill_assessments SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE progress_observations SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE daily_activity_logs SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE preschool_reports SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE fee_items SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE invoice_items SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE invoice_scholarship_items SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE student_scholarships SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE scholarship_applications SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE finance_audit_log SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE report_comments SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                    UPDATE lesson_plans SET school_id = school_uuid WHERE tenant_id = t.id AND school_id IS NULL;
                END IF;
            END LOOP;
        END $$;
    """)

    # =================================================================
    # 4. Backfill user_schools from existing users
    # =================================================================
    # For each user with a school_id, create a user_schools row.
    # For users without school_id in single-school tenants, derive
    # the school from the tenant.
    op.execute("""
        INSERT INTO user_schools (tenant_id, user_id, school_id, role_at_school, is_primary, is_active)
        SELECT
            u.tenant_id,
            u.id,
            COALESCE(u.school_id, s.id),
            u.role,
            true,
            true
        FROM users u
        JOIN LATERAL (
            SELECT id FROM schools
            WHERE schools.tenant_id = u.tenant_id
            AND schools.deleted_at IS NULL
            LIMIT 1
        ) s ON true
        WHERE u.deleted_at IS NULL
        AND COALESCE(u.school_id, s.id) IS NOT NULL
        ON CONFLICT (tenant_id, user_id, school_id) DO NOTHING;
    """)

    # =================================================================
    # 5. Update unique constraints with COALESCE for school_id
    # =================================================================

    # academic_years: (tenant_id, name) -> (tenant_id, COALESCE(school_id, sentinel), name)
    op.execute("""
        DO $$
        BEGIN
            -- Drop old constraint if it exists
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_academic_year_name'
            ) THEN
                ALTER TABLE academic_years DROP CONSTRAINT uq_academic_year_name;
            END IF;
        END $$;
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_academic_year_name_school
        ON academic_years (
            tenant_id,
            COALESCE(school_id, '{NULL_SCHOOL_SENTINEL}'::uuid),
            name
        )
        WHERE deleted_at IS NULL;
    """)

    # terms: (tenant_id, academic_year_id, name) -> add school_id
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_term_name'
            ) THEN
                ALTER TABLE terms DROP CONSTRAINT uq_term_name;
            END IF;
        END $$;
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_term_name_school
        ON terms (
            tenant_id,
            COALESCE(school_id, '{NULL_SCHOOL_SENTINEL}'::uuid),
            academic_year_id,
            name
        )
        WHERE deleted_at IS NULL;
    """)

    # exams: (tenant_id, academic_year_id, term_id, name) -> add school_id
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_exam_name'
            ) THEN
                ALTER TABLE exams DROP CONSTRAINT uq_exam_name;
            END IF;
        END $$;
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_exam_name_school
        ON exams (
            tenant_id,
            COALESCE(school_id, '{NULL_SCHOOL_SENTINEL}'::uuid),
            academic_year_id,
            term_id,
            name
        )
        WHERE deleted_at IS NULL;
    """)


def downgrade() -> None:
    # =================================================================
    # Reverse: restore unique constraints
    # =================================================================
    op.execute("DROP INDEX IF EXISTS uq_exam_name_school;")
    op.execute("DROP INDEX IF EXISTS uq_term_name_school;")
    op.execute("DROP INDEX IF EXISTS uq_academic_year_name_school;")

    # Restore original constraints (best effort -- may fail if data changed)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_academic_year_name'
            ) THEN
                ALTER TABLE academic_years
                ADD CONSTRAINT uq_academic_year_name UNIQUE (tenant_id, name);
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_term_name'
            ) THEN
                ALTER TABLE terms
                ADD CONSTRAINT uq_term_name UNIQUE (tenant_id, academic_year_id, name);
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_exam_name'
            ) THEN
                ALTER TABLE exams
                ADD CONSTRAINT uq_exam_name UNIQUE (tenant_id, academic_year_id, term_id, name);
            END IF;
        END $$;
    """)

    # =================================================================
    # Reverse: clear user_schools
    # =================================================================
    op.execute("TRUNCATE TABLE user_schools;")

    # =================================================================
    # Reverse: remove school_id columns from 32 tables
    # =================================================================
    for table_name in reversed(TABLES_NEEDING_SCHOOL_ID):
        # Drop indexes first
        op.execute(f"DROP INDEX IF EXISTS ix_{table_name}_tenant_school;")
        op.execute(f"DROP INDEX IF EXISTS ix_{table_name}_school_id;")

        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    AND column_name = 'school_id'
                ) THEN
                    ALTER TABLE {table_name} DROP COLUMN school_id;
                END IF;
            END $$;
        """)

    # =================================================================
    # Reverse: drop user_schools table
    # =================================================================
    op.execute("DROP POLICY IF EXISTS tenant_isolation_user_schools ON user_schools;")
    op.execute("DROP INDEX IF EXISTS ix_user_schools_tenant_id;")
    op.drop_table("user_schools")

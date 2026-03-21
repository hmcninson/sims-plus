"""
SIMS Plus - Test Configuration

Two-engine test pattern:
- admin_engine: Connects as postgres (superuser). Used for DDL (create/drop tables),
  seeding test data, and verifying data across tenants.
- app_engine: Connects as sims_app_user (non-superuser). RLS is enforced.
  All application-level test queries run through this engine.

IMPORTANT:
- After switching tenant context, always call session.expire_all() to clear
  the ORM identity map. Without this, SQLAlchemy may return cached objects
  from the previous context.
- UUID bind params in raw SQL must use CAST(:param AS uuid) because asyncpg
  sends str params as VARCHAR, which doesn't match uuid columns.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.base import Base
from app.main import app
from app.api.deps import get_db, get_unscoped_db


# Database URLs
# Admin engine: superuser for DDL and seed data (bypasses RLS)
# Start from the app DATABASE_URL, point to test database, use superuser.
_base_url = str(settings.DATABASE_URL).replace("/sims_plus", "/sims_plus_test")

# Build admin URL: MUST use postgres superuser to bypass FORCE ROW LEVEL SECURITY.
# sims_admin is NOT a superuser and cannot bypass FORCE RLS.
# Reconstruct from _base_url by replacing everything before @ with postgres:postgres.
_url_parts = str(_base_url).split("@")
ADMIN_DATABASE_URL = f"postgresql+asyncpg://postgres:postgres@{_url_parts[-1]}"

# App engine: non-superuser for application queries (RLS enforced)
# Ensure the URL uses sims_app_user regardless of what DATABASE_URL has.
APP_DATABASE_URL = _base_url.replace(
    "postgres:", "sims_app_user:"
)

# Disable rate limiting during tests to prevent 429 errors from rapid requests.
settings.RATE_LIMIT_ENABLED = False


# ALL tenant-scoped tables (every table with a tenant_id column, except tenants itself).
# MUST be kept in sync with the rls_policy_rework migration. When adding a new
# tenant-scoped model, add its __tablename__ here AND in the migration
# TENANT_SCOPED_TABLES list.
TENANT_SCOPED_TABLES = [
    # Core
    "schools", "users",
    # Students
    "students", "guardians", "student_guardians",
    # Staff
    "departments", "staff", "staff_class_assignments",
    # Academic
    "academic_years", "terms", "classes", "class_sections",
    "subjects", "class_subjects", "grading_scales", "grades",
    "assessment_weights", "academic_settings", "school_holidays",
    "school_periods", "class_timetables",
    # Attendance
    "student_attendance", "staff_attendance",
    # Exams
    "exams", "exam_subjects", "exam_scores",
    "score_change_logs", "continuous_assessments", "term_reports",
    # Preschool
    "learning_areas", "developmental_skills", "preschool_rating_scales",
    "preschool_ratings", "student_skill_assessments", "progress_observations",
    "daily_activity_logs", "preschool_reports",
    # Finance
    "fee_types", "fee_structures", "fee_items",
    "invoices", "invoice_items", "invoice_scholarship_items",
    "payments", "scholarships", "student_scholarships",
    "scholarship_applications", "credit_notes", "finance_audit_log",
    # Notifications & SMS
    "notifications", "sms_log",
    # Boarding
    "houses", "dormitories", "beds", "student_boarding",
    "boarding_roll_call", "boarding_roll_call_entries",
    "exeats", "boarding_incidents", "dining_meals",
    # Transport
    "vehicles", "drivers", "routes", "route_stops",
    "student_transport", "trip_logs", "vehicle_maintenance",
    # Push Notifications
    "push_subscriptions",
    # Parent Portal
    "announcements", "teacher_notes", "parent_notification_preferences",
    # Teacher Portal
    "report_comments", "lesson_plans",
    # User-School junction (chain support)
    "user_schools",
    # Email log (messaging module)
    "email_log",
    # Admissions (Sprint 19-20)
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
    # Multi-Curriculum (Phase 1)
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
    # Multi-Curriculum (Phase 2)
    "grade_equivalencies",
    "subject_curriculum_mappings",
    # Multi-Curriculum (Phase 3)
    "external_exam_registrations",
    "student_credit_accumulations",
    "predicted_grades",
]

# Tables with tenant_id that intentionally do NOT use RLS.
# audit_logs: platform admins need cross-tenant access for security monitoring.
# subscription_intents: accessed via UnscopedDatabaseSession for Paystack webhook validation.
RLS_EXEMPT_TABLES = {"audit_logs", "subscription_intents"}


# --- Engine fixtures ---

admin_engine = create_async_engine(
    ADMIN_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

app_engine = create_async_engine(
    APP_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

admin_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)

app_session_maker = async_sessionmaker(
    app_engine, class_=AsyncSession, expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _fix_schema_mismatches():
    """Fix schema mismatches between migrations and current ORM models.

    The test database was created from an earlier set of migrations. The ORM
    models have since gained new columns (e.g. tenants.status, tenants.max_staff)
    and enum labels were UPPERCASE in migrations but lowercase in models.

    This fixture runs once per session as superuser and:
    1. Renames UPPERCASE enum labels to lowercase for userrole/userstatus/tenanttype.
    2. Creates the tenantstatus enum type if missing.
    3. Adds missing columns to the tenants table (status, max_staff, features, trial_ends_at).

    This is a test-only shim. In production, these changes would be proper Alembic migrations.
    """
    async with admin_engine.connect() as conn:
        # ---- Fix userrole / userstatus enum casing ----
        result = await conn.execute(
            text("""
                SELECT enumlabel FROM pg_enum
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                WHERE pg_type.typname = 'userrole'
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row and row[0] == row[0].upper() and row[0] != row[0].lower():
            role_renames = [
                ("PLATFORM_ADMIN", "platform_admin"),
                ("CHAIN_ADMIN", "chain_admin"),
                ("SCHOOL_ADMIN", "school_admin"),
                ("ACADEMIC_HEAD", "academic_head"),
                ("FINANCE_OFFICER", "finance_officer"),
                ("TEACHER", "teacher"),
                ("HOUSE_PARENT", "house_parent"),
                ("PARENT", "parent"),
                ("STUDENT", "student"),
            ]
            status_renames = [
                ("PENDING", "pending"),
                ("ACTIVE", "active"),
                ("SUSPENDED", "suspended"),
                ("DEACTIVATED", "deactivated"),
            ]
            for old, new in role_renames:
                await conn.execute(
                    text(f"ALTER TYPE userrole RENAME VALUE '{old}' TO '{new}'")
                )
            for old, new in status_renames:
                await conn.execute(
                    text(f"ALTER TYPE userstatus RENAME VALUE '{old}' TO '{new}'")
                )

        # ---- Add 'applicant' value to userrole enum if missing (Sprint 19-20) ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM pg_enum
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                WHERE pg_type.typname = 'userrole'
                AND pg_enum.enumlabel = 'applicant'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(
                text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'applicant'")
            )
            await conn.commit()
            # Must re-enter transaction after ALTER TYPE ADD VALUE outside txn
            # asyncpg requires the new enum value to be committed before use

        # ---- Add 'archived' value to academicyearstatus enum if missing (Sprint tenant-setup Phase 3B) ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM pg_enum
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                WHERE pg_type.typname = 'academicyearstatus'
                AND pg_enum.enumlabel = 'archived'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(
                text("ALTER TYPE academicyearstatus ADD VALUE IF NOT EXISTS 'archived'")
            )
            await conn.commit()

        # ---- Add applicant_user_id column to applications if missing ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'applications'
                AND column_name = 'applicant_user_id'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                ALTER TABLE applications
                ADD COLUMN applicant_user_id UUID REFERENCES users(id) ON DELETE SET NULL
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_applications_applicant_user
                ON applications (tenant_id, applicant_user_id)
                WHERE applicant_user_id IS NOT NULL
            """))

        # ---- Make date_of_birth, gender, target_class_id nullable on applications ----
        for col in ["date_of_birth", "gender", "target_class_id"]:
            await conn.execute(text(f"""
                ALTER TABLE applications ALTER COLUMN {col} DROP NOT NULL
            """))

        # ---- Add require_applicant_account to admission_periods if missing ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'admission_periods'
                AND column_name = 'require_applicant_account'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                ALTER TABLE admission_periods
                ADD COLUMN require_applicant_account BOOLEAN NOT NULL DEFAULT false
            """))

        # ---- Add locked_until column to users if missing ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'locked_until'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN locked_until TIMESTAMPTZ
            """))

        # ---- Add last_login column to users if missing ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'last_login'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN last_login TIMESTAMPTZ
            """))

        # ---- Convert users.email unique constraint to tenant-scoped ----
        # Drop global unique if it exists, create tenant-scoped composite unique
        await conn.execute(text("DROP INDEX IF EXISTS ix_users_email"))
        await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key"))
        # Create tenant-scoped unique if not exists
        result = await conn.execute(text("""
            SELECT 1 FROM pg_indexes
            WHERE indexname = 'uq_users_tenant_email'
        """))
        if result.fetchone() is None:
            await conn.execute(text("""
                CREATE UNIQUE INDEX uq_users_tenant_email
                ON users(tenant_id, email) WHERE deleted_at IS NULL
            """))

        # ---- Fix tenanttype enum casing (SINGLE_SCHOOL → single_school) ----
        result = await conn.execute(
            text("""
                SELECT enumlabel FROM pg_enum
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                WHERE pg_type.typname = 'tenanttype'
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row and row[0] == row[0].upper() and row[0] != row[0].lower():
            for old, new in [
                ("SINGLE_SCHOOL", "single_school"),
                ("SCHOOL_CHAIN", "school_chain"),
            ]:
                await conn.execute(
                    text(f"ALTER TYPE tenanttype RENAME VALUE '{old}' TO '{new}'")
                )

        # ---- Fix subscriptiontier enum casing (TRIAL → trial) ----
        result = await conn.execute(
            text("""
                SELECT enumlabel FROM pg_enum
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
                WHERE pg_type.typname = 'subscriptiontier'
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row and row[0] == row[0].upper() and row[0] != row[0].lower():
            for old, new in [
                ("TRIAL", "trial"),
                ("STARTER", "starter"),
                ("PROFESSIONAL", "professional"),
                ("ENTERPRISE", "enterprise"),
            ]:
                await conn.execute(
                    text(f"ALTER TYPE subscriptiontier RENAME VALUE '{old}' TO '{new}'")
                )

        # ---- Create tenantstatus enum if it doesn't exist ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM pg_type WHERE typname = 'tenantstatus'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(
                text("""
                    CREATE TYPE tenantstatus AS ENUM (
                        'trial', 'active', 'suspended', 'cancelled'
                    )
                """)
            )

        # ---- Add missing columns to tenants table ----
        # Check which columns exist
        result = await conn.execute(
            text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tenants'
            """)
        )
        existing_cols = {r[0] for r in result.fetchall()}

        if "status" not in existing_cols:
            await conn.execute(
                text("""
                    ALTER TABLE tenants
                    ADD COLUMN status tenantstatus NOT NULL DEFAULT 'trial'
                """)
            )
        if "max_staff" not in existing_cols:
            await conn.execute(
                text("""
                    ALTER TABLE tenants
                    ADD COLUMN max_staff integer NOT NULL DEFAULT 10
                """)
            )
        if "features" not in existing_cols:
            await conn.execute(
                text("""
                    ALTER TABLE tenants
                    ADD COLUMN features jsonb DEFAULT '{}'::jsonb
                """)
            )
        if "trial_ends_at" not in existing_cols:
            await conn.execute(
                text("""
                    ALTER TABLE tenants
                    ADD COLUMN trial_ends_at timestamptz
                """)
            )

        # ---- Fix score_change_logs.changed_at timezone type ----
        # The model uses DateTime (without timezone) but service code passes
        # timezone-aware datetime. Convert column to timestamptz.
        result = await conn.execute(
            text("""
                SELECT data_type FROM information_schema.columns
                WHERE table_name = 'score_change_logs'
                AND column_name = 'changed_at'
            """)
        )
        row = result.fetchone()
        if row and row[0] == 'timestamp without time zone':
            await conn.execute(
                text("""
                    ALTER TABLE score_change_logs
                    ALTER COLUMN changed_at TYPE timestamptz
                    USING changed_at AT TIME ZONE 'UTC'
                """)
            )

        # ---- Add missing columns to finance_audit_log ----
        # The ORM model inherits created_at/updated_at from Base but the
        # migration omitted them.
        result = await conn.execute(
            text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'finance_audit_log'
            """)
        )
        fal_cols = {r[0] for r in result.fetchall()}

        if "created_at" not in fal_cols:
            await conn.execute(
                text("""
                    ALTER TABLE finance_audit_log
                    ADD COLUMN created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                """)
            )
        if "updated_at" not in fal_cols:
            await conn.execute(
                text("""
                    ALTER TABLE finance_audit_log
                    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                """)
            )

        # ---- Create parent portal tables if missing (Sprint 13-14) ----
        # Three new enum types and tables: announcements, teacher_notes,
        # parent_notification_preferences. These may be missing if the
        # test database hasn't had `alembic upgrade head` run recently.
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'announcements'
                AND table_schema = 'public'
            """)
        )
        if result.fetchone() is None:
            # Create enum types
            for enum_sql in [
                "CREATE TYPE announcementtarget AS ENUM ('all_parents', 'specific_class', 'specific_house', 'boarding_parents', 'transport_parents')",
                "CREATE TYPE announcementpriority AS ENUM ('normal', 'important', 'urgent')",
                "CREATE TYPE notetype AS ENUM ('positive', 'concern', 'information', 'action_required')",
            ]:
                # Check if enum already exists before creating
                enum_name = enum_sql.split("TYPE ")[1].split(" AS")[0]
                check = await conn.execute(
                    text("SELECT 1 FROM pg_type WHERE typname = :name"),
                    {"name": enum_name},
                )
                if check.fetchone() is None:
                    await conn.execute(text(enum_sql))

            # Create announcements table
            await conn.execute(text("""
                CREATE TABLE announcements (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    target_audience announcementtarget NOT NULL DEFAULT 'all_parents',
                    target_class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
                    target_house_id UUID,
                    priority announcementpriority NOT NULL DEFAULT 'normal',
                    published_at TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ,
                    attachment_url VARCHAR(500),
                    is_pinned BOOLEAN NOT NULL DEFAULT false,
                    deleted_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Create teacher_notes table
            await conn.execute(text("""
                CREATE TABLE teacher_notes (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
                    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
                    note_type notetype NOT NULL,
                    content TEXT NOT NULL,
                    is_visible_to_parent BOOLEAN NOT NULL DEFAULT true,
                    parent_acknowledged BOOLEAN NOT NULL DEFAULT false,
                    parent_acknowledged_at TIMESTAMPTZ,
                    deleted_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Create parent_notification_preferences table
            await conn.execute(text("""
                CREATE TABLE parent_notification_preferences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    email_enabled BOOLEAN NOT NULL DEFAULT true,
                    sms_enabled BOOLEAN NOT NULL DEFAULT false,
                    push_enabled BOOLEAN NOT NULL DEFAULT false,
                    notify_attendance BOOLEAN NOT NULL DEFAULT true,
                    notify_grades BOOLEAN NOT NULL DEFAULT true,
                    notify_finance BOOLEAN NOT NULL DEFAULT true,
                    notify_announcements BOOLEAN NOT NULL DEFAULT true,
                    notify_transport BOOLEAN NOT NULL DEFAULT false,
                    notify_boarding BOOLEAN NOT NULL DEFAULT true,
                    quiet_hours_start TIME,
                    quiet_hours_end TIME,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (tenant_id, user_id)
                )
            """))

            # Enable RLS on all 3 tables
            for tbl in ["announcements", "teacher_notes", "parent_notification_preferences"]:
                await conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
                await conn.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))
                await conn.execute(text(f"""
                    CREATE POLICY tenant_isolation_{tbl} ON {tbl}
                        FOR ALL TO sims_app_user
                        USING (tenant_id = get_current_tenant_id())
                        WITH CHECK (tenant_id = get_current_tenant_id())
                """))
                await conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO sims_app_user"))

            await conn.execute(text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user"))

        # ---- Create push_subscriptions table if missing (Sprint 11-12) ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'push_subscriptions'
                AND table_schema = 'public'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                CREATE TABLE push_subscriptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    endpoint TEXT NOT NULL,
                    p256dh_key VARCHAR(255) NOT NULL,
                    auth_key VARCHAR(255) NOT NULL,
                    user_agent VARCHAR(500),
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))

            # Create indexes
            await conn.execute(text("CREATE INDEX idx_push_subscriptions_endpoint ON push_subscriptions (endpoint)"))
            await conn.execute(text("CREATE INDEX idx_push_subscriptions_tenant_id ON push_subscriptions (tenant_id)"))
            await conn.execute(text("CREATE INDEX idx_push_subscriptions_tenant_user ON push_subscriptions (tenant_id, user_id)"))

            # Enable RLS
            await conn.execute(text("ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text("ALTER TABLE push_subscriptions FORCE ROW LEVEL SECURITY"))
            await conn.execute(text("""
                CREATE POLICY tenant_isolation_push_subscriptions ON push_subscriptions
                    FOR ALL TO sims_app_user
                    USING (tenant_id = get_current_tenant_id())
                    WITH CHECK (tenant_id = get_current_tenant_id())
            """))
            await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON push_subscriptions TO sims_app_user"))

        # ---- Create teacher portal tables if missing (Sprint 15-16) ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'report_comments'
                AND table_schema = 'public'
            """)
        )
        if result.fetchone() is None:
            # Create lessonplanstatus enum
            check = await conn.execute(
                text("SELECT 1 FROM pg_type WHERE typname = 'lessonplanstatus'"),
            )
            if check.fetchone() is None:
                await conn.execute(text(
                    "CREATE TYPE lessonplanstatus AS ENUM ('planned', 'taught', 'cancelled')"
                ))

            # Add teacher_id to class_subjects if missing
            cs_cols = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'class_subjects'
            """))
            cs_col_names = {r[0] for r in cs_cols.fetchall()}
            if "teacher_id" not in cs_col_names:
                await conn.execute(text("""
                    ALTER TABLE class_subjects
                    ADD COLUMN teacher_id UUID REFERENCES staff(id) ON DELETE SET NULL
                """))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_class_subjects_teacher_id ON class_subjects (teacher_id)"
                ))

            # Create report_comments table
            await conn.execute(text("""
                CREATE TABLE report_comments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    term_id UUID NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
                    academic_year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
                    class_teacher_comment TEXT,
                    head_teacher_comment TEXT,
                    class_teacher_id UUID REFERENCES staff(id) ON DELETE SET NULL,
                    head_teacher_id UUID REFERENCES staff(id) ON DELETE SET NULL,
                    class_teacher_signed BOOLEAN NOT NULL DEFAULT false,
                    head_teacher_signed BOOLEAN NOT NULL DEFAULT false,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                )
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX uq_report_comment_student_term
                ON report_comments (tenant_id, student_id, term_id)
                WHERE deleted_at IS NULL
            """))

            # Create lesson_plans table
            await conn.execute(text("""
                CREATE TABLE lesson_plans (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    teacher_id UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
                    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    period INTEGER,
                    topic VARCHAR(200) NOT NULL,
                    objectives TEXT,
                    resources TEXT,
                    activities TEXT,
                    notes TEXT,
                    status lessonplanstatus NOT NULL DEFAULT 'planned',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                )
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX uq_lesson_plan_with_period
                ON lesson_plans (tenant_id, teacher_id, class_id, subject_id, date, period)
                WHERE period IS NOT NULL AND deleted_at IS NULL
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX uq_lesson_plan_without_period
                ON lesson_plans (tenant_id, teacher_id, class_id, subject_id, date)
                WHERE period IS NULL AND deleted_at IS NULL
            """))

            # Enable RLS on both tables
            for tbl in ["report_comments", "lesson_plans"]:
                await conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
                await conn.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))
                await conn.execute(text(f"""
                    CREATE POLICY tenant_isolation_{tbl} ON {tbl}
                        FOR ALL TO sims_app_user
                        USING (tenant_id = get_current_tenant_id())
                        WITH CHECK (tenant_id = get_current_tenant_id())
                """))
                await conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO sims_app_user"))

        # ---- Create user_schools table if missing (Sprint 17-18 chain support) ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'user_schools'
                AND table_schema = 'public'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                CREATE TABLE user_schools (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
                    role_at_school VARCHAR(50) NOT NULL,
                    is_primary BOOLEAN NOT NULL DEFAULT false,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (tenant_id, user_id, school_id)
                )
            """))

            # Create indexes
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_user_schools_user_id ON user_schools (user_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_user_schools_school_id ON user_schools (school_id)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_user_schools_tenant_id ON user_schools (tenant_id)"
            ))

            # Enable RLS
            await conn.execute(text("ALTER TABLE user_schools ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text("ALTER TABLE user_schools FORCE ROW LEVEL SECURITY"))
            await conn.execute(text("""
                CREATE POLICY tenant_isolation_user_schools ON user_schools
                    FOR ALL TO sims_app_user
                    USING (tenant_id = get_current_tenant_id())
                    WITH CHECK (tenant_id = get_current_tenant_id())
            """))
            await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON user_schools TO sims_app_user"))

        # ---- Create email_log table if missing (Sprint 18.5 messaging) ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'email_log'
                AND table_schema = 'public'
            """)
        )
        if result.fetchone() is None:
            # Create emailstatus enum if missing
            check = await conn.execute(
                text("SELECT 1 FROM pg_type WHERE typname = 'emailstatus'"),
            )
            if check.fetchone() is None:
                await conn.execute(text(
                    "CREATE TYPE emailstatus AS ENUM ('pending', 'sent', 'delivered', 'failed', 'bounced')"
                ))

            await conn.execute(text("""
                CREATE TABLE email_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    school_id UUID REFERENCES schools(id) ON DELETE SET NULL,
                    recipient_email VARCHAR(255) NOT NULL,
                    recipient_name VARCHAR(255),
                    subject VARCHAR(500) NOT NULL,
                    body TEXT NOT NULL,
                    status emailstatus NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    sent_at TIMESTAMPTZ,
                    sent_by UUID,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Indexes
            await conn.execute(text("CREATE INDEX ix_email_log_tenant_id ON email_log (tenant_id)"))
            await conn.execute(text("CREATE INDEX ix_email_log_school_id ON email_log (school_id)"))
            await conn.execute(text("CREATE INDEX ix_email_log_recipient_email ON email_log (recipient_email)"))
            await conn.execute(text("CREATE INDEX ix_email_log_tenant_status ON email_log (tenant_id, status)"))
            await conn.execute(text("CREATE INDEX ix_email_log_tenant_created_at ON email_log (tenant_id, created_at)"))

            # Enable RLS
            await conn.execute(text("ALTER TABLE email_log ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text("ALTER TABLE email_log FORCE ROW LEVEL SECURITY"))
            await conn.execute(text("""
                CREATE POLICY tenant_isolation_email_log ON email_log
                    FOR ALL TO sims_app_user
                    USING (tenant_id = get_current_tenant_id())
                    WITH CHECK (tenant_id = get_current_tenant_id())
            """))
            await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON email_log TO sims_app_user"))

        # ---- Add communication_settings column to schools if missing ----
        result = await conn.execute(
            text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'schools'
                AND column_name = 'communication_settings'
            """)
        )
        if result.fetchone() is None:
            await conn.execute(text("""
                ALTER TABLE schools
                ADD COLUMN communication_settings JSONB
            """))

        # ---- Add school_id to tables that don't have it yet (chain support) ----
        chain_tables = [
            "academic_years", "terms", "class_sections", "class_subjects",
            "subjects", "grading_scales", "grades", "assessment_weights",
            "academic_settings", "school_holidays", "school_periods",
            "class_timetables", "departments", "staff_class_assignments",
            "guardians", "student_guardians", "student_attendance",
            "staff_attendance", "exams", "exam_subjects", "exam_scores",
            "score_change_logs", "continuous_assessments", "term_reports",
            "learning_areas", "developmental_skills", "preschool_rating_scales",
            "preschool_ratings", "student_skill_assessments",
            "progress_observations", "daily_activity_logs", "preschool_reports",
            "fee_items", "invoice_items", "invoice_scholarship_items",
            "student_scholarships", "scholarship_applications",
            "finance_audit_log", "report_comments", "lesson_plans",
        ]
        for tbl in chain_tables:
            # Check if table exists and school_id column is missing
            check = await conn.execute(text(f"""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{tbl}'
                AND column_name = 'school_id'
            """))
            if check.fetchone() is None:
                # Check if table exists at all before altering
                tbl_check = await conn.execute(text(f"""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = '{tbl}' AND table_schema = 'public'
                """))
                if tbl_check.fetchone() is not None:
                    await conn.execute(text(f"""
                        ALTER TABLE {tbl}
                        ADD COLUMN school_id UUID REFERENCES schools(id) ON DELETE SET NULL
                    """))

        await conn.commit()


@pytest_asyncio.fixture(scope="function")
async def admin_session() -> AsyncGenerator[AsyncSession, None]:
    """Admin database session (superuser, bypasses RLS).

    Use for:
    - Seeding test data across multiple tenants
    - Verifying data across tenants (cross-tenant assertions)
    - DDL operations (create/drop tables)
    """
    async with admin_session_maker() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass  # Connection may have been closed during long test runs


@pytest_asyncio.fixture(scope="function")
async def app_session() -> AsyncGenerator[AsyncSession, None]:
    """App database session (sims_app_user, RLS enforced).

    Use for:
    - All application-level queries (simulates the real app)
    - Testing that RLS policies filter correctly
    - Verifying cross-tenant access is blocked
    """
    async with app_session_maker() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass  # Connection may have been closed during long test runs


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Legacy fixture -- uses admin engine. Prefer admin_session or app_session."""
    async with admin_session_maker() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass  # Connection may have been closed during long test runs


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with overridden database dependency.

    Patches app.db.session.async_session_maker so that the TenantMiddleware,
    get_unscoped_db(), and the /health endpoint all query sims_plus_test
    instead of the application's sims_plus database.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_unscoped_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db

    # The TenantMiddleware and /health endpoint import async_session_maker from
    # app.db.session and create their own sessions. Patch the module-level
    # session maker to point at the test database so tenant lookups succeed.
    test_session_maker = async_sessionmaker(
        admin_engine, class_=AsyncSession, expire_on_commit=False,
    )

    with patch("app.middleware.tenant.async_session_maker", test_session_maker), \
         patch("app.main.async_session_maker", test_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


# --- Helper functions ---

async def create_test_tenant(
    admin_session: AsyncSession,
    subdomain: str | None = None,
) -> dict[str, Any]:
    """Create a test tenant via admin session (bypasses RLS).

    Includes all NOT NULL columns that lack server defaults:
    tenant_type, subscription_tier, status, max_students, max_staff.

    Returns dict with tenant info including id.
    """
    tenant_id = uuid4()
    sub = subdomain or f"test{uuid4().hex[:8]}"
    slug = sub

    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students,
                created_at, updated_at)
            VALUES (
                CAST(:id AS uuid), :subdomain, :slug, :name,
                true, 'single_school', 'trial', 50,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(tenant_id), "subdomain": sub, "slug": slug, "name": f"School {sub}"},
    )
    await admin_session.flush()

    return {"id": tenant_id, "subdomain": sub, "slug": slug, "name": f"School {sub}"}


async def create_test_user(
    admin_session: AsyncSession,
    tenant_id,
    email: str | None = None,
) -> dict[str, Any]:
    """Create a test user via admin session (bypasses RLS).

    Includes all NOT NULL columns that lack server defaults:
    email_verified, mfa_enabled, failed_login_attempts, timezone.
    Uses UPPERCASE enum values to match PostgreSQL enum type definitions.

    Returns dict with user info including id.
    """
    user_id = uuid4()
    user_email = email or f"user-{uuid4().hex[:8]}@test.com"

    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                :fn, :ln, :role, :status,
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": user_email,
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash_for_testing",
            "fn": "Test",
            "ln": "User",
            "role": "teacher",
            "status": "active",
        },
    )
    await admin_session.flush()

    return {"id": user_id, "email": user_email, "tenant_id": tenant_id}


async def set_app_tenant_context(app_session: AsyncSession, tenant_id) -> None:
    """Set tenant context on an app session."""
    await app_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_id)},
    )
    app_session.expire_all()  # CRITICAL: clear ORM identity map after context switch


async def clear_app_tenant_context(app_session: AsyncSession) -> None:
    """Clear tenant context on an app session."""
    await app_session.execute(text("SELECT clear_tenant_context()"))
    app_session.expire_all()


@pytest.fixture
def sample_tenant_data() -> dict[str, Any]:
    """Sample tenant data for testing."""
    return {
        "name": "Test School",
        "slug": "test-school",
        "email": "admin@testschool.edu.gh",
        "tenant_type": "single_school",
        "subscription_tier": "professional",
    }


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Sample user data for testing."""
    return {
        "email": "user@testschool.edu.gh",
        "password": "SecurePassword123!",
        "first_name": "Kwame",
        "last_name": "Asante",
        "phone": "0241234567",
        "role": "teacher",
    }

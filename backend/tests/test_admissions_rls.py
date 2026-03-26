"""
RLS Isolation Tests for Admissions Portal (16 tables).

Verifies that tenant B cannot see, modify, or delete tenant A's data.
Uses the two-engine test pattern (admin_session for seeding, app_session for RLS queries).

This is the most critical test file for admissions. If any test here fails,
tenant data is leaking across tenants.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
    TENANT_SCOPED_TABLES,
)

pytestmark = [
    pytest.mark.rls,
    pytest.mark.asyncio,
    pytest.mark.xdist_group("rls_serial"),
]

# The 16 admissions tables that must have RLS
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


async def _seed_prerequisite_data(admin_session, tenant_id):
    """Seed the prerequisite chain: school, academic_year, class, student.

    Returns dict with all IDs needed to populate admissions tables.
    """
    school_id = uuid4()
    academic_year_id = uuid4()
    class_id = uuid4()
    student_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School {uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31',
                'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(academic_year_id),
            "tid": str(tenant_id),
            "name": f"AY-{uuid4().hex[:6]}",
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(class_id),
            "tid": str(tenant_id),
            "name": f"Class-{uuid4().hex[:6]}",
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, student_id, first_name, last_name,
                date_of_birth, gender, status, class_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :student_id, 'Test', 'Student',
                '2012-05-15', 'male', 'active', CAST(:cid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "student_id": f"STU-{uuid4().hex[:6]}",
            "cid": str(class_id),
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (
                id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": f"admin-{uuid4().hex[:6]}@test.com",
            "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash",
        },
    )

    return {
        "school_id": school_id,
        "academic_year_id": academic_year_id,
        "class_id": class_id,
        "student_id": student_id,
        "user_id": user_id,
    }


async def _seed_admission_period(admin_session, tenant_id, school_id, academic_year_id):
    """Seed an admission period. Returns period_id."""
    period_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2026-06-01', '2026-08-31', 'open',
                50.00, true, true, '[]',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "ayid": str(academic_year_id),
            "name": f"Period-{uuid4().hex[:6]}",
        },
    )
    return period_id


async def _seed_application(admin_session, tenant_id, school_id, period_id, class_id):
    """Seed an application. Returns app_id."""
    app_id = uuid4()
    import secrets
    tracking_code = secrets.token_urlsafe(48)

    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tracking_code, 'Test', 'Applicant',
                '2012-05-15', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "pid": str(period_id),
            "tracking_code": tracking_code,
            "cid": str(class_id),
        },
    )
    return app_id


class TestAdmissionPeriodsIsolation:
    """Admission periods must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_periods(self, app_session, admin_session):
        """Tenant B must not see any admission periods from Tenant A."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_prerequisite_data(admin_session, tenant_a["id"])

        await _seed_admission_period(
            admin_session, tenant_a["id"],
            prereqs["school_id"], prereqs["academic_year_id"],
        )
        await admin_session.commit()

        # Tenant A sees the period
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT count(*) FROM admission_periods"))
        assert result.scalar() >= 1, "Tenant A should see its own period"

        # Tenant B sees nothing
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM admission_periods"))
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's periods"


class TestApplicationsIsolation:
    """Applications must be invisible and unmodifiable across tenants."""

    async def test_tenant_b_cannot_select_tenant_a_applications(self, app_session, admin_session):
        """Tenant B cannot SELECT tenant A's applications."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_prerequisite_data(admin_session, tenant_a["id"])

        period_id = await _seed_admission_period(
            admin_session, tenant_a["id"],
            prereqs["school_id"], prereqs["academic_year_id"],
        )
        app_id = await _seed_application(
            admin_session, tenant_a["id"],
            prereqs["school_id"], period_id, prereqs["class_id"],
        )
        await admin_session.commit()

        # Tenant B sees 0 applications
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM applications"))
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's applications"

    async def test_tenant_b_cannot_update_tenant_a_applications(self, app_session, admin_session):
        """Tenant B's UPDATE affects 0 rows for Tenant A's data."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_prerequisite_data(admin_session, tenant_a["id"])

        period_id = await _seed_admission_period(
            admin_session, tenant_a["id"],
            prereqs["school_id"], prereqs["academic_year_id"],
        )
        app_id = await _seed_application(
            admin_session, tenant_a["id"],
            prereqs["school_id"], period_id, prereqs["class_id"],
        )
        await admin_session.commit()

        # Tenant B tries to update Tenant A's application by known PK
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("UPDATE applications SET status = 'rejected' WHERE id = CAST(:id AS uuid)"),
            {"id": str(app_id)},
        )
        assert result.rowcount == 0, "Tenant B must NOT be able to update Tenant A's applications"

    async def test_tenant_b_cannot_delete_tenant_a_applications(self, app_session, admin_session):
        """Tenant B's DELETE affects 0 rows for Tenant A's data."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_prerequisite_data(admin_session, tenant_a["id"])

        period_id = await _seed_admission_period(
            admin_session, tenant_a["id"],
            prereqs["school_id"], prereqs["academic_year_id"],
        )
        app_id = await _seed_application(
            admin_session, tenant_a["id"],
            prereqs["school_id"], period_id, prereqs["class_id"],
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("DELETE FROM applications WHERE id = CAST(:id AS uuid)"),
            {"id": str(app_id)},
        )
        assert result.rowcount == 0, "Tenant B must NOT be able to delete Tenant A's applications"


class TestApplicationGuardiansIsolation:
    """Application guardians must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_guardians(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_prerequisite_data(admin_session, tenant_a["id"])

        period_id = await _seed_admission_period(
            admin_session, tenant_a["id"],
            prereqs["school_id"], prereqs["academic_year_id"],
        )
        app_id = await _seed_application(
            admin_session, tenant_a["id"],
            prereqs["school_id"], period_id, prereqs["class_id"],
        )

        # Seed a guardian for the application
        await admin_session.execute(
            text("""
                INSERT INTO application_guardians (
                    id, tenant_id, application_id,
                    first_name, last_name, phone, relationship, is_primary,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                    'Jane', 'Doe', '0241234567', 'mother', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "aid": str(app_id),
            },
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM application_guardians")
        )
        assert result.scalar() == 0


class TestEntranceExamsIsolation:
    """Entrance exams must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_exams(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_prerequisite_data(admin_session, tenant_a["id"])

        period_id = await _seed_admission_period(
            admin_session, tenant_a["id"],
            prereqs["school_id"], prereqs["academic_year_id"],
        )

        # Seed an entrance exam
        await admin_session.execute(
            text("""
                INSERT INTO entrance_exams (
                    id, tenant_id, school_id, admission_period_id,
                    name, exam_date, venue, capacity, status,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid),
                    'Batch 1 Exam', '2026-07-15', 'Main Hall', 50, 'scheduled',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "sid": str(prereqs["school_id"]),
                "pid": str(period_id),
            },
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM entrance_exams")
        )
        assert result.scalar() == 0


class TestAllAdmissionsTablesRLS:
    """Dynamic test that verifies RLS configuration on all 16 admissions tables."""

    async def test_all_16_admissions_tables_in_tenant_scoped_list(self):
        """All 16 admissions tables must be in TENANT_SCOPED_TABLES."""
        for table in ADMISSIONS_TABLES:
            assert table in TENANT_SCOPED_TABLES, (
                f"Admissions table '{table}' is missing from "
                f"TENANT_SCOPED_TABLES in conftest.py"
            )

    async def test_rls_enabled_on_all_admissions_tables(self, app_session):
        """Verify RLS is enabled on every admissions table."""
        result = await app_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = ANY(:tables)
            """),
            {"tables": ADMISSIONS_TABLES},
        )
        rows = result.fetchall()

        # Check we actually found all tables (they exist in the DB)
        found_tables = {row.tablename for row in rows}
        missing = set(ADMISSIONS_TABLES) - found_tables
        assert not missing, (
            f"Admissions tables not found in database: {missing}. "
            f"Run 'alembic upgrade head' on the test database."
        )

        for row in rows:
            assert row.rowsecurity is True, (
                f"RLS not enabled on admissions table '{row.tablename}'"
            )

    async def test_force_rls_on_all_admissions_tables(self, app_session):
        """Verify FORCE RLS is set on every admissions table."""
        result = await app_session.execute(
            text("""
                SELECT relname, relforcerowsecurity
                FROM pg_class
                WHERE relname = ANY(:tables)
            """),
            {"tables": ADMISSIONS_TABLES},
        )
        for row in result.fetchall():
            assert row.relforcerowsecurity is True, (
                f"FORCE RLS not set on '{row.relname}'"
            )

    async def test_tenant_isolation_policy_on_all_admissions_tables(self, app_session):
        """Every admissions table must have a policy using get_current_tenant_id()."""
        for table_name in ADMISSIONS_TABLES:
            result = await app_session.execute(
                text("""
                    SELECT policyname, qual, with_check
                    FROM pg_policies
                    WHERE schemaname = 'public'
                    AND tablename = :table_name
                """),
                {"table_name": table_name},
            )
            policies = result.fetchall()
            assert len(policies) > 0, (
                f"No RLS policies on '{table_name}'"
            )

            has_tenant_policy = any(
                "get_current_tenant_id" in (row.qual or "")
                and "get_current_tenant_id" in (row.with_check or "")
                for row in policies
            )
            assert has_tenant_policy, (
                f"'{table_name}' has no policy using get_current_tenant_id() "
                f"in both USING and WITH CHECK"
            )

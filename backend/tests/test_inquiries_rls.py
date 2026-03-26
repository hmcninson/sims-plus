"""
RLS Isolation Tests for Enrollment Gap Closure Phase 1 (5 tables).

Verifies that tenant B cannot see, modify, or delete tenant A's data
for: inquiries, inquiry_communications, inquiry_follow_ups, interviews,
screening_checklists.

Uses the two-engine test pattern (admin_session for seeding, app_session for RLS queries).

This is the most critical test file for Phase 1. If any test here fails,
tenant data is leaking across tenants.
"""

import pytest
import secrets
from datetime import date, time
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

# The 5 Phase 1 tables that must have RLS
PHASE1_TABLES = [
    "inquiries",
    "inquiry_communications",
    "inquiry_follow_ups",
    "interviews",
    "screening_checklists",
]


# --- Helpers ---


async def _seed_prereqs(admin_session, tenant_id):
    """Seed school, academic year, class, admission period, user. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake_hash"},
    )
    return {
        "school_id": school_id, "year_id": year_id,
        "class_id": class_id, "period_id": period_id,
        "user_id": user_id,
    }


async def _seed_inquiry(admin_session, tenant_id, school_id):
    """Seed an inquiry. Returns inquiry_id."""
    inquiry_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO inquiries (
                id, tenant_id, school_id, source, status,
                first_name, last_name, guardian_name, guardian_phone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'website', 'new',
                'Test', 'Student', 'Test Guardian', '0241234567',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(inquiry_id), "tid": str(tenant_id), "sid": str(school_id)},
    )
    return inquiry_id


async def _seed_application(admin_session, tenant_id, school_id, period_id, class_id):
    """Seed an application. Returns app_id."""
    app_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Test', 'Applicant',
                '2012-05-15', 'male', CAST(:cid AS uuid), 'submitted',
                '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
        },
    )
    return app_id


# --- RLS Configuration Tests ---


class TestPhase1TablesRLSConfig:
    """Verify RLS is properly configured on all 5 Phase 1 tables."""

    async def test_all_phase1_tables_in_tenant_scoped_list(self):
        """All 5 Phase 1 tables must be in TENANT_SCOPED_TABLES."""
        for table in PHASE1_TABLES:
            assert table in TENANT_SCOPED_TABLES, (
                f"Phase 1 table '{table}' is missing from "
                f"TENANT_SCOPED_TABLES in conftest.py"
            )

    async def test_rls_enabled_on_all_phase1_tables(self, app_session):
        """Verify RLS is enabled on every Phase 1 table."""
        result = await app_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = ANY(:tables)
            """),
            {"tables": PHASE1_TABLES},
        )
        rows = result.fetchall()

        found_tables = {row.tablename for row in rows}
        missing = set(PHASE1_TABLES) - found_tables
        assert not missing, (
            f"Phase 1 tables not found in database: {missing}. "
            f"Run 'alembic upgrade head' on the test database."
        )

        for row in rows:
            assert row.rowsecurity is True, (
                f"RLS not enabled on Phase 1 table '{row.tablename}'"
            )

    async def test_force_rls_on_all_phase1_tables(self, app_session):
        """Verify FORCE RLS is set on every Phase 1 table."""
        result = await app_session.execute(
            text("""
                SELECT relname, relforcerowsecurity
                FROM pg_class
                WHERE relname = ANY(:tables)
            """),
            {"tables": PHASE1_TABLES},
        )
        for row in result.fetchall():
            assert row.relforcerowsecurity is True, (
                f"FORCE RLS not set on '{row.relname}'"
            )

    async def test_tenant_isolation_policy_on_all_phase1_tables(self, app_session):
        """Every Phase 1 table must have a policy using get_current_tenant_id()."""
        for table_name in PHASE1_TABLES:
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


# --- Data Isolation Tests ---


class TestInquiryIsolation:
    """Inquiry data must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_inquiries(self, app_session, admin_session):
        """Tenant B must not see any inquiries from Tenant A."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        await _seed_inquiry(admin_session, tenant_a["id"], prereqs_a["school_id"])
        await admin_session.commit()

        # Tenant A sees the inquiry
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT count(*) FROM inquiries"))
        assert result.scalar() >= 1, "Tenant A should see its own inquiry"

        # Tenant B sees nothing
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM inquiries"))
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's inquiries"

    async def test_tenant_b_cannot_update_tenant_a_inquiries(self, app_session, admin_session):
        """Tenant B's UPDATE affects 0 rows for Tenant A's data."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        inquiry_id = await _seed_inquiry(admin_session, tenant_a["id"], prereqs_a["school_id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("UPDATE inquiries SET status = 'lost' WHERE id = CAST(:id AS uuid)"),
            {"id": str(inquiry_id)},
        )
        assert result.rowcount == 0, "Tenant B must NOT update Tenant A's inquiries"


class TestInquiryCommunicationIsolation:
    """Inquiry communications must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_communications(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        inquiry_id = await _seed_inquiry(admin_session, tenant_a["id"], prereqs_a["school_id"])

        # Seed a communication
        await admin_session.execute(
            text("""
                INSERT INTO inquiry_communications (
                    id, tenant_id, inquiry_id, channel, direction, content,
                    sent_at, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:iid AS uuid),
                    'phone', 'outbound', 'Called guardian',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "iid": str(inquiry_id),
            },
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM inquiry_communications")
        )
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's communications"


class TestInquiryFollowUpIsolation:
    """Inquiry follow-ups must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_follow_ups(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        inquiry_id = await _seed_inquiry(admin_session, tenant_a["id"], prereqs_a["school_id"])

        # Seed a follow-up
        await admin_session.execute(
            text("""
                INSERT INTO inquiry_follow_ups (
                    id, tenant_id, inquiry_id, assigned_to,
                    due_date, priority,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:iid AS uuid),
                    CAST(:uid AS uuid),
                    '2026-08-01', 'medium',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "iid": str(inquiry_id),
                "uid": str(prereqs_a["user_id"]),
            },
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM inquiry_follow_ups")
        )
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's follow-ups"


class TestInterviewIsolation:
    """Interviews must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_interviews(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        app_id = await _seed_application(
            admin_session, tenant_a["id"],
            prereqs_a["school_id"], prereqs_a["period_id"], prereqs_a["class_id"],
        )

        # Seed an interview
        await admin_session.execute(
            text("""
                INSERT INTO interviews (
                    id, tenant_id, school_id, application_id,
                    interviewer_id, scheduled_date, venue, status,
                    duration_minutes, scoring_criteria,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:aid AS uuid), CAST(:uid AS uuid),
                    '2026-07-15', 'Main Hall', 'scheduled',
                    30, '{}',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(uuid4()),
                "tid": str(tenant_a["id"]),
                "sid": str(prereqs_a["school_id"]),
                "aid": str(app_id),
                "uid": str(prereqs_a["user_id"]),
            },
        )
        await admin_session.commit()

        # Tenant A sees it
        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT count(*) FROM interviews"))
        assert result.scalar() >= 1, "Tenant A should see its own interview"

        # Tenant B sees nothing
        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM interviews"))
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's interviews"


class TestScreeningChecklistIsolation:
    """Screening checklists must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_screening(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        app_id = await _seed_application(
            admin_session, tenant_a["id"],
            prereqs_a["school_id"], prereqs_a["period_id"], prereqs_a["class_id"],
        )

        # Seed a screening item
        await admin_session.execute(
            text("""
                INSERT INTO screening_checklists (
                    id, tenant_id, application_id,
                    item_name, item_category, is_completed,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                    'Birth certificate', 'documents', false,
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
            text("SELECT count(*) FROM screening_checklists")
        )
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's screening items"


class TestCrossTenantInquiryService:
    """Cross-tenant inquiry access through the service layer should fail."""

    async def test_cross_tenant_inquiry_api(self, app_session, admin_session):
        """Service.get() with wrong tenant returns NOT_FOUND (not data leak)."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

        inquiry_id = await _seed_inquiry(admin_session, tenant_a["id"], prereqs_a["school_id"])
        await admin_session.commit()

        # Set context to tenant B and try to get tenant A's inquiry
        await set_app_tenant_context(app_session, tenant_b["id"])

        from app.services.admissions import InquiryService, InquiryServiceError

        svc = InquiryService(app_session)
        with pytest.raises(InquiryServiceError) as exc_info:
            await svc.get(inquiry_id=inquiry_id, tenant_id=tenant_b["id"])
        assert exc_info.value.code == "NOT_FOUND"

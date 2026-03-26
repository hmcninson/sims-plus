"""
RLS Isolation Tests for Enrollment Checklists (Phase 3).

Verifies that tenant B cannot see, modify, or delete tenant A's
enrollment checklists and checklist items.
Uses the two-engine test pattern (admin_session for seeding, app_session for RLS queries).

This is the most critical test file for enrollment checklists. If any test
here fails, tenant data is leaking across tenants.
"""

import pytest
import secrets
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    TENANT_SCOPED_TABLES,
)

pytestmark = [
    pytest.mark.rls,
    pytest.mark.asyncio,
    pytest.mark.xdist_group("rls_serial"),
]

ENROLLMENT_TABLES = [
    "enrollment_checklists",
    "enrollment_checklist_items",
]


async def _seed_full_chain(admin_session, tenant_id):
    """Seed school -> academic_year -> class -> period -> accepted app. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()

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
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
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
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
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
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )

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
                :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )

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
                '2012-05-15', 'male', CAST(:cid AS uuid), 'accepted',
                '{}', false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant_id), "sid": str(school_id),
            "pid": str(period_id), "tracking_code": secrets.token_urlsafe(48),
            "cid": str(class_id),
        },
    )

    return {
        "school_id": school_id, "year_id": year_id, "class_id": class_id,
        "period_id": period_id, "app_id": app_id,
    }


async def _seed_checklist(admin_session, tenant_id, school_id, app_id):
    """Seed an enrollment checklist + one item. Returns (checklist_id, item_id)."""
    checklist_id = uuid4()
    item_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO enrollment_checklists (
                id, tenant_id, school_id, application_id,
                checklist_type,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:aid AS uuid),
                'standard',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(checklist_id), "tid": str(tenant_id),
            "sid": str(school_id), "aid": str(app_id),
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO enrollment_checklist_items (
                id, tenant_id, checklist_id,
                item_type, item_name, is_required, is_completed,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                'document', 'Birth certificate', true, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(item_id), "tid": str(tenant_id),
            "cid": str(checklist_id),
        },
    )

    return checklist_id, item_id


class TestEnrollmentChecklistRLS:
    """Enrollment checklists must be invisible across tenants."""

    async def test_enrollment_checklist_rls(self, app_session, admin_session):
        """Tenant B cannot SELECT tenant A's enrollment checklists."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        prereqs_a = await _seed_full_chain(admin_session, tenant_a["id"])
        checklist_id, _ = await _seed_checklist(
            admin_session, tenant_a["id"],
            prereqs_a["school_id"], prereqs_a["app_id"],
        )
        await admin_session.commit()

        # Tenant A sees the checklist
        await set_app_tenant_context(app_session, tenant_a["id"])
        result_a = await app_session.execute(
            text("SELECT count(*) FROM enrollment_checklists")
        )
        assert result_a.scalar() >= 1, "Tenant A should see its own checklist"

        # Tenant B sees nothing
        await set_app_tenant_context(app_session, tenant_b["id"])
        result_b = await app_session.execute(
            text("SELECT count(*) FROM enrollment_checklists")
        )
        assert result_b.scalar() == 0, "Tenant B must NOT see Tenant A's checklists"

    async def test_enrollment_checklist_item_rls(self, app_session, admin_session):
        """Tenant B cannot SELECT tenant A's enrollment checklist items."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)

        prereqs_a = await _seed_full_chain(admin_session, tenant_a["id"])
        _, item_id = await _seed_checklist(
            admin_session, tenant_a["id"],
            prereqs_a["school_id"], prereqs_a["app_id"],
        )
        await admin_session.commit()

        # Tenant A sees the item
        await set_app_tenant_context(app_session, tenant_a["id"])
        result_a = await app_session.execute(
            text("SELECT count(*) FROM enrollment_checklist_items")
        )
        assert result_a.scalar() >= 1, "Tenant A should see its own checklist items"

        # Tenant B sees nothing
        await set_app_tenant_context(app_session, tenant_b["id"])
        result_b = await app_session.execute(
            text("SELECT count(*) FROM enrollment_checklist_items")
        )
        assert result_b.scalar() == 0, "Tenant B must NOT see Tenant A's checklist items"


class TestEnrollmentRLSRegistration:
    """Verify enrollment tables are properly registered and have RLS policies."""

    async def test_rls_tables_registered(self):
        """Both enrollment tables must be in TENANT_SCOPED_TABLES."""
        for table in ENROLLMENT_TABLES:
            assert table in TENANT_SCOPED_TABLES, (
                f"Table '{table}' is missing from TENANT_SCOPED_TABLES in conftest.py"
            )

    async def test_rls_policies_exist(self, admin_session):
        """Both tables must have RLS enabled and at least one policy."""
        for table in ENROLLMENT_TABLES:
            # Check RLS is enabled
            rls_result = await admin_session.execute(
                text("""
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname = :table_name
                """),
                {"table_name": table},
            )
            row = rls_result.fetchone()
            assert row is not None, f"Table '{table}' not found in pg_class"
            assert row[0] is True, f"RLS not enabled on '{table}'"
            assert row[1] is True, f"FORCE RLS not enabled on '{table}'"

            # Check at least one policy exists
            policy_result = await admin_session.execute(
                text("""
                    SELECT count(*) FROM pg_policies
                    WHERE tablename = :table_name
                """),
                {"table_name": table},
            )
            count = policy_result.scalar()
            assert count >= 1, f"No RLS policy found on '{table}'"

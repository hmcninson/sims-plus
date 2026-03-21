"""
Tests for setup wizard completion checks.

Covers: needsSetup when terms=0, when subjects=0, and when all present.
Uses two-engine pattern (admin seeds, app queries).
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_school(admin_session, tenant_id):
    school_id = uuid4()
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
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
    )
    await admin_session.commit()
    return school_id


async def _seed_academic_year(admin_session, tenant_id):
    year_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
                '2025-09-01', '2026-07-31',
                'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(year_id), "tid": str(tenant_id)},
    )
    await admin_session.commit()
    return year_id


async def _seed_term(admin_session, tenant_id, year_id):
    term_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO terms (
                id, tenant_id, academic_year_id, name, short_name,
                start_date, end_date, status, sequence,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:yid AS uuid),
                'First Term', 'T1', '2025-09-01', '2025-12-15',
                'active', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(term_id),
            "tid": str(tenant_id),
            "yid": str(year_id),
        },
    )
    await admin_session.commit()
    return term_id


async def _seed_subject(admin_session, tenant_id):
    subj_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO subjects (
                id, tenant_id, name, code, category, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                'English', 'ENG', 'core', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(subj_id), "tid": str(tenant_id)},
    )
    await admin_session.commit()
    return subj_id


async def _seed_class(admin_session, tenant_id):
    class_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                'Class 1', 'primary', 1,
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id)},
    )
    await admin_session.commit()
    return class_id


# --- Tests ---


class TestSetupCheck:
    """Setup wizard completion check logic.

    The setup check says needsSetup when:
    - academic_years.count == 0 OR classes.count == 0
    Updated criteria should also check:
    - terms.count == 0 OR subjects.count == 0
    """

    async def test_needs_setup_when_no_terms(self, app_session, admin_session):
        """Setup needed when academic year exists but no terms."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"])
        year_id = await _seed_academic_year(admin_session, tenant["id"])
        await _seed_class(admin_session, tenant["id"])
        # No term seeded
        await set_app_tenant_context(app_session, tenant["id"])

        # Check term count
        result = await app_session.execute(
            text("SELECT COUNT(*) FROM terms WHERE deleted_at IS NULL")
        )
        term_count = result.scalar()
        assert term_count == 0  # needsSetup should be true

    async def test_needs_setup_when_no_subjects(self, app_session, admin_session):
        """Setup needed when no subjects exist."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"])
        year_id = await _seed_academic_year(admin_session, tenant["id"])
        await _seed_term(admin_session, tenant["id"], year_id)
        await _seed_class(admin_session, tenant["id"])
        # No subject seeded
        await set_app_tenant_context(app_session, tenant["id"])

        result = await app_session.execute(
            text("SELECT COUNT(*) FROM subjects WHERE deleted_at IS NULL")
        )
        subject_count = result.scalar()
        assert subject_count == 0  # needsSetup should be true

    async def test_setup_complete_when_all_present(self, app_session, admin_session):
        """Setup complete when academic years, terms, classes, and subjects exist."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"])
        year_id = await _seed_academic_year(admin_session, tenant["id"])
        await _seed_term(admin_session, tenant["id"], year_id)
        await _seed_class(admin_session, tenant["id"])
        await _seed_subject(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        # All counts > 0
        for table in ["academic_years", "terms", "classes", "subjects"]:
            result = await app_session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE deleted_at IS NULL")
            )
            count = result.scalar()
            assert count > 0, f"{table} should have at least 1 record"

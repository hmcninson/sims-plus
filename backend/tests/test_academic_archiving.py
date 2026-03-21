"""
Tests for academic year archiving and read-only enforcement (Phase 3B).

Covers: archive transitions, guard checks, and preventing modifications
to archived/completed years.
Uses two-engine pattern (admin seeds, app queries via AcademicService).
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


async def _seed_year(admin_session, tenant_id, *, status="completed", is_current=False):
    """Create an academic year with given status.

    Uses SQL literals for enum status to avoid asyncpg type issues.
    """
    year_id = uuid4()
    name = f"AY-{uuid4().hex[:6]}"
    current_str = "true" if is_current else "false"

    await admin_session.execute(
        text(f"""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2024-09-01'::date, '2025-07-31'::date,
                '{status}', {current_str}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(year_id),
            "tid": str(tenant_id),
            "name": name,
        },
    )
    await admin_session.commit()
    return year_id


async def _seed_term(admin_session, tenant_id, year_id, *, status="completed"):
    """Create a term with given status.

    Uses SQL literals for dates and enum status.
    """
    term_id = uuid4()
    name = f"Term-{uuid4().hex[:6]}"

    await admin_session.execute(
        text(f"""
            INSERT INTO terms (
                id, tenant_id, academic_year_id, name, short_name,
                start_date, end_date, status, sequence,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:yid AS uuid),
                :name, 'T1', '2024-09-01'::date, '2024-12-15'::date,
                '{status}', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(term_id),
            "tid": str(tenant_id),
            "yid": str(year_id),
            "name": name,
        },
    )
    await admin_session.commit()
    return term_id


# --- Archive Transition Tests ---


class TestArchiveTransition:
    """Tests for archiving academic years."""

    async def test_archive_completed_year_succeeds(self, app_session, admin_session):
        """Completed year with all terms completed -> archive succeeds."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="completed")
        await _seed_term(admin_session, tenant["id"], year_id, status="completed")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService

        service = AcademicService(app_session)
        result = await service.archive_academic_year(tenant["id"], year_id)

        assert result.status.value == "archived"

    async def test_archive_active_year_fails(self, app_session, admin_session):
        """Active year should NOT be archivable."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="active")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService
        from app.services.academic._shared import AcademicServiceError

        service = AcademicService(app_session)
        with pytest.raises(AcademicServiceError) as exc_info:
            await service.archive_academic_year(tenant["id"], year_id)
        assert exc_info.value.code == "INVALID_STATUS"

    async def test_archive_planning_year_fails(self, app_session, admin_session):
        """Planning year should NOT be archivable."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="planning")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService
        from app.services.academic._shared import AcademicServiceError

        service = AcademicService(app_session)
        with pytest.raises(AcademicServiceError) as exc_info:
            await service.archive_academic_year(tenant["id"], year_id)
        assert exc_info.value.code == "INVALID_STATUS"

    async def test_archive_current_year_fails(self, app_session, admin_session):
        """Current year (is_current=True) should NOT be archivable."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(
            admin_session, tenant["id"], status="completed", is_current=True
        )
        await _seed_term(admin_session, tenant["id"], year_id, status="completed")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService
        from app.services.academic._shared import AcademicServiceError

        service = AcademicService(app_session)
        with pytest.raises(AcademicServiceError) as exc_info:
            await service.archive_academic_year(tenant["id"], year_id)
        assert exc_info.value.code == "IS_CURRENT"

    async def test_archive_with_incomplete_term_fails(self, app_session, admin_session):
        """Year with non-completed terms should NOT be archivable."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="completed")
        await _seed_term(admin_session, tenant["id"], year_id, status="active")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService
        from app.services.academic._shared import AcademicServiceError

        service = AcademicService(app_session)
        with pytest.raises(AcademicServiceError) as exc_info:
            await service.archive_academic_year(tenant["id"], year_id)
        assert exc_info.value.code == "INCOMPLETE_TERMS"


# --- Read-Only Enforcement Tests ---


class TestReadOnlyEnforcement:
    """Tests that archived/completed years cannot be modified."""

    async def test_update_archived_year_name_fails(self, app_session, admin_session):
        """Updating an archived year's name should raise READ_ONLY_YEAR."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="archived")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService
        from app.services.academic._shared import AcademicServiceError

        service = AcademicService(app_session)
        with pytest.raises(AcademicServiceError) as exc_info:
            await service.update_academic_year(
                academic_year_id=year_id,
                tenant_id=tenant["id"],
                name="New Name",
            )
        assert exc_info.value.code == "READ_ONLY_YEAR"

    async def test_create_term_in_archived_year_fails(self, app_session, admin_session):
        """Creating a term in an archived year should fail."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="archived")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic import AcademicService
        from app.services.academic._shared import AcademicServiceError
        from app.services.academic.guards import ReadOnlyYearError

        service = AcademicService(app_session)
        with pytest.raises((AcademicServiceError, ReadOnlyYearError)):
            await service.create_term(
                tenant_id=tenant["id"],
                academic_year_id=year_id,
                name="New Term",
                start_date="2025-01-01",
                end_date="2025-04-15",
                short_name="NT",
                sequence=1,
            )

    async def test_guard_allows_planning_year(self, app_session, admin_session):
        """Guard should allow modifications to planning years."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="planning")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.guards import assert_year_editable

        # Should NOT raise
        await assert_year_editable(app_session, tenant["id"], year_id)

    async def test_guard_allows_active_year(self, app_session, admin_session):
        """Guard should allow modifications to active years."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="active")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.guards import assert_year_editable

        # Should NOT raise
        await assert_year_editable(app_session, tenant["id"], year_id)

    async def test_guard_blocks_completed_year(self, app_session, admin_session):
        """Guard should block modifications to completed years."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="completed")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.guards import assert_year_editable, ReadOnlyYearError

        with pytest.raises(ReadOnlyYearError):
            await assert_year_editable(app_session, tenant["id"], year_id)

    async def test_guard_blocks_archived_year(self, app_session, admin_session):
        """Guard should block modifications to archived years."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="archived")
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.guards import assert_year_editable, ReadOnlyYearError

        with pytest.raises(ReadOnlyYearError):
            await assert_year_editable(app_session, tenant["id"], year_id)

    async def test_term_year_guard_resolves_parent(self, app_session, admin_session):
        """assert_term_year_editable should resolve the parent year and check."""
        tenant = await create_test_tenant(admin_session)
        year_id = await _seed_year(admin_session, tenant["id"], status="archived")
        term_id = await _seed_term(
            admin_session, tenant["id"], year_id, status="completed"
        )
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.academic.guards import (
            assert_term_year_editable,
            ReadOnlyYearError,
        )

        with pytest.raises(ReadOnlyYearError):
            await assert_term_year_editable(app_session, tenant["id"], term_id)

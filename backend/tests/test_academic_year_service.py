"""
Academic Year & Term Service Tests

Tests for academic year and term CRUD operations via AcademicService.
Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require a running sims_plus_test database with
RLS policies applied (alembic upgrade head).
"""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models.academic import AcademicYearStatus, TermStatus
from app.services.academic import AcademicService, AcademicServiceError

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("academic_year_serial"),
]


# =========================
# Academic Year Tests
# =========================


class TestCreateAcademicYear:
    """Tests for creating academic years."""

    async def test_create_academic_year_returns_planning_status(
        self, app_session, admin_session
    ):
        """New academic year starts with status=planning."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        assert year is not None
        assert year.name == "2025/2026"
        assert year.status == AcademicYearStatus.PLANNING
        assert year.is_current is False
        assert year.tenant_id == tenant["id"]

    async def test_create_academic_year_with_is_current(
        self, app_session, admin_session
    ):
        """Creating a year with is_current=True works."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
            is_current=True,
        )

        assert year.is_current is True

    async def test_create_duplicate_name_raises_error(
        self, app_session, admin_session
    ):
        """Duplicate academic year name within same tenant raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_academic_year(
                tenant_id=tenant["id"],
                name="2025/2026",
                start_date=date(2025, 9, 1),
                end_date=date(2026, 7, 31),
            )

        assert exc_info.value.code == "duplicate_academic_year"

    async def test_set_is_current_clears_other_current_years(
        self, app_session, admin_session
    ):
        """Setting is_current on a new year clears it from all others."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        # Create first year as current
        year_1 = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2024/2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 7, 31),
            is_current=True,
        )
        year_1_id = year_1.id
        assert year_1.is_current is True

        # Create second year as current -- should unset first
        year_2 = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
            is_current=True,
        )
        assert year_2.is_current is True

        # Re-fetch year_1 to verify is_current was cleared
        year_1_refreshed = await service.get_academic_year(tenant["id"], year_1_id)
        assert year_1_refreshed.is_current is False


class TestAcademicYearStatusTransitions:
    """Tests for academic year status changes."""

    async def test_activate_year_changes_status(
        self, app_session, admin_session
    ):
        """Updating status from planning to active works."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )
        assert year.status == AcademicYearStatus.PLANNING

        updated = await service.update_academic_year(
            year.id, tenant["id"], status="active"
        )
        assert updated.status == AcademicYearStatus.ACTIVE

    async def test_complete_year_changes_status(
        self, app_session, admin_session
    ):
        """Updating status from active to completed works."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        # Activate
        await service.update_academic_year(year.id, tenant["id"], status="active")

        # Complete
        updated = await service.update_academic_year(
            year.id, tenant["id"], status="completed"
        )
        assert updated.status == AcademicYearStatus.COMPLETED


class TestListAcademicYears:
    """Tests for listing academic years."""

    async def test_list_academic_years_returns_tenant_data(
        self, app_session, admin_session
    ):
        """List returns only the current tenant's academic years."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2024/2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 7, 31),
        )
        await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        years = await service.list_academic_years(tenant["id"])
        assert len(years) == 2

    async def test_get_academic_year_with_terms(
        self, app_session, admin_session
    ):
        """Get academic year with include_terms loads terms."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )

        loaded = await service.get_academic_year(
            tenant["id"], year.id, include_terms=True
        )
        assert loaded is not None
        assert len(loaded.terms) == 1
        assert loaded.terms[0].name == "First Term"


class TestDeleteAcademicYear:
    """Tests for soft-deleting academic years."""

    async def test_soft_delete_academic_year(
        self, app_session, admin_session
    ):
        """Deleted academic year does not appear in list."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        deleted = await service.delete_academic_year(tenant["id"], year.id)
        assert deleted is True

        # Should no longer be findable
        result = await service.get_academic_year(tenant["id"], year.id)
        assert result is None

    async def test_delete_nonexistent_year_returns_false(
        self, app_session, admin_session
    ):
        """Deleting a nonexistent academic year returns False."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        result = await service.delete_academic_year(tenant["id"], uuid4())
        assert result is False


# =========================
# Term Tests
# =========================


class TestCreateTerm:
    """Tests for creating terms within academic years."""

    async def test_create_term_returns_upcoming_status(
        self, app_session, admin_session
    ):
        """New term starts with status=upcoming."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        term = await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )

        assert term is not None
        assert term.name == "First Term"
        assert term.status == TermStatus.UPCOMING
        assert term.sequence == 1
        assert term.academic_year_id == year.id
        assert term.tenant_id == tenant["id"]

    async def test_create_duplicate_term_name_raises_error(
        self, app_session, admin_session
    ):
        """Duplicate term name within same academic year raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_term(
                tenant_id=tenant["id"],
                academic_year_id=year.id,
                name="First Term",
                start_date=date(2025, 9, 1),
                end_date=date(2025, 12, 20),
                sequence=1,
            )

        assert exc_info.value.code == "duplicate_term"

    async def test_create_term_with_nonexistent_year_raises_error(
        self, app_session, admin_session
    ):
        """Creating a term for a nonexistent academic year raises error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        with pytest.raises(AcademicServiceError) as exc_info:
            await service.create_term(
                tenant_id=tenant["id"],
                academic_year_id=uuid4(),
                name="First Term",
                start_date=date(2025, 9, 1),
                end_date=date(2025, 12, 20),
            )

        assert exc_info.value.code == "academic_year_not_found"


class TestListTerms:
    """Tests for listing terms."""

    async def test_list_terms_filtered_by_academic_year(
        self, app_session, admin_session
    ):
        """List terms returns only terms for specified academic year."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year_1 = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2024/2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 7, 31),
        )
        year_2 = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        # 2 terms for year_1, 1 term for year_2
        await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year_1.id,
            name="First Term",
            start_date=date(2024, 9, 1),
            end_date=date(2024, 12, 20),
            sequence=1,
        )
        await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year_1.id,
            name="Second Term",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 4, 15),
            sequence=2,
        )
        await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year_2.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )

        terms_y1 = await service.list_terms(tenant["id"], academic_year_id=year_1.id)
        terms_y2 = await service.list_terms(tenant["id"], academic_year_id=year_2.id)

        assert len(terms_y1) == 2
        assert len(terms_y2) == 1


class TestUpdateTerm:
    """Tests for updating terms."""

    async def test_set_term_is_current_clears_others(
        self, app_session, admin_session
    ):
        """Setting is_current on a term clears it from all other terms."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        term_1 = await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )
        term_1_id = term_1.id

        term_2 = await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="Second Term",
            start_date=date(2026, 1, 6),
            end_date=date(2026, 4, 15),
            sequence=2,
        )

        # Make term_1 current
        await service.update_term(term_1_id, tenant["id"], is_current=True)

        # Make term_2 current -- should clear term_1
        await service.update_term(term_2.id, tenant["id"], is_current=True)

        term_1_refreshed = await service.get_term(tenant["id"], term_1_id)
        assert term_1_refreshed.is_current is False

    async def test_update_term_status(self, app_session, admin_session):
        """Term status can be updated."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        term = await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )
        assert term.status == TermStatus.UPCOMING

        updated = await service.update_term(term.id, tenant["id"], status="active")
        assert updated.status == TermStatus.ACTIVE


class TestDeleteTerm:
    """Tests for soft-deleting terms."""

    async def test_soft_delete_term(self, app_session, admin_session):
        """Deleted term no longer returned by get."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = AcademicService(app_session)

        year = await service.create_academic_year(
            tenant_id=tenant["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        term = await service.create_term(
            tenant_id=tenant["id"],
            academic_year_id=year.id,
            name="First Term",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 20),
            sequence=1,
        )

        deleted = await service.delete_term(tenant["id"], term.id)
        assert deleted is True

        result = await service.get_term(tenant["id"], term.id)
        assert result is None


# =========================
# Tenant Isolation
# =========================


class TestAcademicYearTenantIsolation:
    """Academic years and terms must be isolated between tenants."""

    async def test_tenant_a_cannot_see_tenant_b_academic_years(
        self, app_session, admin_session
    ):
        """Tenant A's academic years are invisible to Tenant B."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create year as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)

        await service.create_academic_year(
            tenant_id=tenant_a["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        # Flush and capture the year id before switching context
        await app_session.flush()

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        years = await service.list_academic_years(tenant_b["id"])
        assert len(years) == 0, "Tenant B must not see Tenant A's academic years"

    async def test_tenant_a_cannot_get_tenant_b_academic_year(
        self, app_session, admin_session
    ):
        """Tenant A cannot fetch Tenant B's academic year by ID."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create year as Tenant A via admin (to get the ID)
        year_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO academic_years (
                    id, tenant_id, name, start_date, end_date,
                    status, is_current, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    '2025-09-01', '2026-07-31',
                    'planning', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {
                "id": str(year_id),
                "tid": str(tenant_a["id"]),
                "name": "2025/2026",
            },
        )
        await admin_session.commit()

        # Try to fetch as Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])
        service = AcademicService(app_session)

        result = await service.get_academic_year(tenant_b["id"], year_id)
        assert result is None, "Tenant B must not access Tenant A's academic year"

    async def test_same_year_name_allowed_in_different_tenants(
        self, app_session, admin_session
    ):
        """Two tenants can have academic years with the same name."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        await admin_session.commit()

        # Create as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = AcademicService(app_session)
        year_a = await service.create_academic_year(
            tenant_id=tenant_a["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )
        await app_session.flush()
        # Capture scalar values before switching context to avoid
        # MissingGreenlet when SQLAlchemy tries to lazy-refresh expired attrs
        year_a_id = year_a.id
        year_a_name = year_a.name

        # Switch to Tenant B -- same name should work
        await set_app_tenant_context(app_session, tenant_b["id"])
        year_b = await service.create_academic_year(
            tenant_id=tenant_b["id"],
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 7, 31),
        )

        assert year_a_id != year_b.id
        assert year_a_name == year_b.name == "2025/2026"

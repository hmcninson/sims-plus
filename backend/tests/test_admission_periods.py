"""
Tests for AdmissionPeriodService.

Covers: CRUD, status transitions, overlap validation, form config,
tenant isolation. Uses two-engine pattern (admin seeds, app queries).
"""

import pytest
from datetime import date
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_school_and_year(admin_session, tenant_id):
    """Create school + academic year, return (school_id, year_id)."""
    school_id = uuid4()
    year_id = uuid4()

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
            "id": str(year_id),
            "tid": str(tenant_id),
            "name": f"AY-{uuid4().hex[:6]}",
        },
    )

    await admin_session.commit()
    return school_id, year_id


async def _seed_class(admin_session, tenant_id, name="Class 1", sequence=1):
    """Create a class, return class_id."""
    class_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', :seq, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(class_id),
            "tid": str(tenant_id),
            "name": name,
            "seq": sequence,
        },
    )
    await admin_session.commit()
    return class_id


class TestAdmissionPeriodCRUD:
    """Basic create/read/update/list operations."""

    async def test_create_admission_period(self, app_session, admin_session):
        """Create period with valid data, assert defaults and fields."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService

        service = AdmissionPeriodService(app_session)
        period = await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="2026/2027 Admissions",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            application_fee_amount=50.00,
            application_fee_required=True,
            entrance_exam_required=True,
            max_applications=200,
        )

        assert period.name == "2026/2027 Admissions"
        assert period.status == "draft"
        assert period.application_fee_required is True
        assert period.entrance_exam_required is True
        assert period.max_applications == 200

    async def test_create_period_validates_date_range(self, app_session, admin_session):
        """end_date <= start_date raises INVALID_DATES error."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService, AdmissionPeriodError

        service = AdmissionPeriodService(app_session)
        with pytest.raises(AdmissionPeriodError) as exc_info:
            await service.create(
                tenant_id=tenant["id"],
                school_id=school_id,
                name="Bad Period",
                academic_year_id=year_id,
                start_date=date(2026, 9, 1),
                end_date=date(2026, 6, 1),  # Before start
            )
        assert exc_info.value.code == "INVALID_DATES"

    async def test_create_period_rejects_overlap(self, app_session, admin_session):
        """Two periods with overlapping dates AND classes -> PERIOD_OVERLAP error."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        class_1 = await _seed_class(admin_session, tenant["id"], "Class 1", 1)
        class_2 = await _seed_class(admin_session, tenant["id"], "Class 2", 2)
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService, AdmissionPeriodError

        service = AdmissionPeriodService(app_session)

        # Period A for Class 1 in June-August
        await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Period A",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            target_classes=[class_1],
        )

        # Period B for Class 1 in July-September -> OVERLAP
        with pytest.raises(AdmissionPeriodError) as exc_info:
            await service.create(
                tenant_id=tenant["id"],
                school_id=school_id,
                name="Period B (overlap)",
                academic_year_id=year_id,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 9, 30),
                target_classes=[class_1],
            )
        assert exc_info.value.code == "PERIOD_OVERLAP"

        # Period C for Class 2 in July-September -> OK (different class)
        period_c = await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Period C (no overlap)",
            academic_year_id=year_id,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
            target_classes=[class_2],
        )
        assert period_c.name == "Period C (no overlap)"

    async def test_list_periods_with_filters(self, app_session, admin_session):
        """List periods with status filter and pagination."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService

        service = AdmissionPeriodService(app_session)

        # Create 3 periods (all start as draft)
        for i in range(3):
            await service.create(
                tenant_id=tenant["id"],
                school_id=school_id,
                name=f"Period {i}",
                academic_year_id=year_id,
                start_date=date(2026, 6 + i, 1),
                end_date=date(2026, 7 + i, 28),
            )

        # List all
        periods, total = await service.list_periods(tenant["id"])
        assert total == 3

        # Filter by status
        periods, total = await service.list_periods(tenant["id"], status="draft")
        assert total == 3  # All are draft

        # Pagination
        periods, total = await service.list_periods(tenant["id"], page=1, page_size=2)
        assert len(periods) == 2
        assert total == 3


class TestAdmissionPeriodStatusTransitions:
    """Valid and invalid status transitions."""

    async def test_valid_transitions(self, app_session, admin_session):
        """draft -> open -> closed -> archived: all succeed."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService

        service = AdmissionPeriodService(app_session)
        period = await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Transition Test",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
        )
        period_id = period.id

        # draft -> open
        period = await service.update_status(tenant["id"], period_id, "open")
        assert period.status == "open"

        # open -> closed
        period = await service.update_status(tenant["id"], period_id, "closed")
        assert period.status == "closed"

        # closed -> archived
        period = await service.update_status(tenant["id"], period_id, "archived")
        assert period.status == "archived"

    async def test_invalid_transitions(self, app_session, admin_session):
        """draft -> closed, open -> draft, archived -> open: all fail."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService, AdmissionPeriodError

        service = AdmissionPeriodService(app_session)
        period = await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Invalid Transition",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
        )

        # draft -> closed (skip open)
        with pytest.raises(AdmissionPeriodError) as exc_info:
            await service.update_status(tenant["id"], period.id, "closed")
        assert exc_info.value.code == "INVALID_TRANSITION"

    async def test_archived_period_cannot_be_updated(self, app_session, admin_session):
        """Archived period rejects field updates."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService, AdmissionPeriodError

        service = AdmissionPeriodService(app_session)
        period = await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="To Archive",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
        )

        # Move to archived
        await service.update_status(tenant["id"], period.id, "open")
        await service.update_status(tenant["id"], period.id, "closed")
        await service.update_status(tenant["id"], period.id, "archived")

        # Try to update name -- should fail
        with pytest.raises(AdmissionPeriodError) as exc_info:
            await service.update(tenant["id"], period.id, name="Updated Name")
        assert exc_info.value.code == "PERIOD_LOCKED"


class TestAdmissionPeriodFormConfig:
    """Form configuration upsert behavior."""

    async def test_update_form_config_upsert(self, app_session, admin_session):
        """Create form config, then update it (upsert)."""
        tenant = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        from app.services.admissions import AdmissionPeriodService

        service = AdmissionPeriodService(app_session)
        period = await service.create(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Config Test",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
        )

        schema = {
            "type": "object",
            "properties": {
                "religion": {"type": "string"},
            },
            "required": ["religion"],
        }

        # First call: creates
        config = await service.update_form_config(
            tenant["id"], period.id, schema, ["birth_certificate"],
        )
        assert config.form_schema == schema
        assert config.required_documents == ["birth_certificate"]
        config_id = config.id

        # Second call: updates (same record)
        updated_schema = {
            "type": "object",
            "properties": {
                "religion": {"type": "string"},
                "hobby": {"type": "string"},
            },
        }
        config = await service.update_form_config(
            tenant["id"], period.id, updated_schema, ["birth_certificate", "transcript"],
        )
        assert config.id == config_id  # Same record (upsert)
        assert "hobby" in config.form_schema["properties"]
        assert len(config.required_documents) == 2


class TestAdmissionPeriodTenantIsolation:
    """Tenant isolation at the service level."""

    async def test_period_tenant_isolation(self, app_session, admin_session):
        """Period created for tenant A is invisible from tenant B context."""
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        school_id, year_id = await _seed_school_and_year(admin_session, tenant_a["id"])
        await set_app_tenant_context(app_session, tenant_a["id"])

        from app.services.admissions import AdmissionPeriodService, AdmissionPeriodError

        service = AdmissionPeriodService(app_session)
        period = await service.create(
            tenant_id=tenant_a["id"],
            school_id=school_id,
            name="Tenant A Only",
            academic_year_id=year_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
        )
        period_id = period.id

        # Switch to tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        # List returns empty
        periods, total = await service.list_periods(tenant_b["id"])
        assert total == 0

        # Direct get raises NOT_FOUND
        with pytest.raises(AdmissionPeriodError) as exc_info:
            await service.get_period(tenant_b["id"], period_id)
        assert exc_info.value.code == "NOT_FOUND"

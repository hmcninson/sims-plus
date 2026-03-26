"""
Tests for InquiryService bulk import, duplicate checking, and statistics.

Covers: bulk import with dedup, max row enforcement, invalid data handling,
duplicate phone/email check, stats endpoint. Uses two-engine pattern.
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
    """Seed a school. Returns school_id."""
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
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.commit()
    return school_id


def _make_import_row(**overrides):
    """Create a single bulk import row dict."""
    defaults = {
        "first_name": f"Student-{uuid4().hex[:6]}",
        "last_name": f"Last-{uuid4().hex[:6]}",
        "guardian_name": f"Guardian-{uuid4().hex[:6]}",
        "guardian_phone": f"024{uuid4().hex[:7]}",
    }
    defaults.update(overrides)
    return defaults


# --- Bulk Import Tests ---


async def test_bulk_import_success(app_session, admin_session):
    """Bulk import with valid rows creates inquiries."""
    tenant = await create_test_tenant(admin_session)
    school_id = await _seed_school(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService
    from app.schemas.inquiry import BulkInquiryImportRow

    rows = [BulkInquiryImportRow(**_make_import_row()) for _ in range(5)]

    svc = InquiryService(app_session)
    result = await svc.bulk_import(
        tenant_id=tenant["id"], school_id=school_id, rows=rows,
    )

    assert result["imported"] == 5
    assert result["skipped"] == 0
    assert result["errors"] == []


async def test_bulk_import_dedup(app_session, admin_session):
    """Duplicate guardian_phone in same tenant is skipped."""
    tenant = await create_test_tenant(admin_session)
    school_id = await _seed_school(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService
    from app.schemas.inquiry import BulkInquiryImportRow, InquiryCreate

    # Create an existing inquiry with a known phone
    known_phone = "0241111111"
    svc = InquiryService(app_session)
    await svc.create(
        tenant_id=tenant["id"],
        school_id=school_id,
        data=InquiryCreate(
            source="website",
            first_name="Existing",
            last_name="Lead",
            guardian_name="Existing Guardian",
            guardian_phone=known_phone,
        ),
    )

    # Import: one with duplicate phone, one with new phone
    rows = [
        BulkInquiryImportRow(**_make_import_row(guardian_phone=known_phone)),
        BulkInquiryImportRow(**_make_import_row(guardian_phone="0242222222")),
    ]

    result = await svc.bulk_import(
        tenant_id=tenant["id"], school_id=school_id, rows=rows,
    )

    assert result["imported"] == 1
    assert result["skipped"] == 1


async def test_bulk_import_max_rows(app_session, admin_session):
    """Schema rejects > 200 rows at validation time."""
    from app.schemas.inquiry import BulkImportRequest
    from pydantic import ValidationError

    rows = [_make_import_row() for _ in range(201)]

    with pytest.raises(ValidationError):
        BulkImportRequest(rows=rows)


async def test_bulk_import_invalid_data(app_session, admin_session):
    """Missing required fields in a row cause validation error at schema level."""
    from app.schemas.inquiry import BulkInquiryImportRow
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BulkInquiryImportRow(
            first_name="Good",
            # last_name missing
            guardian_name="Guardian",
            guardian_phone="0241234567",
        )


# --- Duplicate Check Tests ---


async def test_check_duplicate_by_phone(app_session, admin_session):
    """Check duplicate finds matching guardian_phone."""
    tenant = await create_test_tenant(admin_session)
    school_id = await _seed_school(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService
    from app.schemas.inquiry import InquiryCreate

    known_phone = "0249999999"
    svc = InquiryService(app_session)
    await svc.create(
        tenant_id=tenant["id"],
        school_id=school_id,
        data=InquiryCreate(
            source="phone",
            first_name="Ama",
            last_name="Darko",
            guardian_name="Grace Darko",
            guardian_phone=known_phone,
        ),
    )

    matches = await svc.check_duplicate(
        tenant_id=tenant["id"], phone=known_phone,
    )
    assert len(matches) >= 1
    assert any(m.guardian_phone == known_phone for m in matches)


async def test_check_duplicate_by_email(app_session, admin_session):
    """Check duplicate finds matching guardian_email."""
    tenant = await create_test_tenant(admin_session)
    school_id = await _seed_school(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService
    from app.schemas.inquiry import InquiryCreate

    known_email = f"parent-{uuid4().hex[:6]}@example.com"
    svc = InquiryService(app_session)
    await svc.create(
        tenant_id=tenant["id"],
        school_id=school_id,
        data=InquiryCreate(
            source="website",
            first_name="Kofi",
            last_name="Adu",
            guardian_name="Nana Adu",
            guardian_phone="0243334444",
            guardian_email=known_email,
        ),
    )

    matches = await svc.check_duplicate(
        tenant_id=tenant["id"], email=known_email,
    )
    assert len(matches) >= 1
    assert any(m.guardian_email == known_email for m in matches)


async def test_check_duplicate_no_match(app_session, admin_session):
    """No duplicates returns empty list."""
    tenant = await create_test_tenant(admin_session)
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService

    svc = InquiryService(app_session)
    matches = await svc.check_duplicate(
        tenant_id=tenant["id"], phone="0240000000",
    )
    assert matches == []


# --- Statistics Tests ---


async def test_get_stats(app_session, admin_session):
    """Stats returns by_status, by_source, and conversion_rate."""
    tenant = await create_test_tenant(admin_session)
    school_id = await _seed_school(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import InquiryService
    from app.schemas.inquiry import InquiryCreate

    svc = InquiryService(app_session)

    # Create a few inquiries with different sources
    await svc.create(
        tenant_id=tenant["id"], school_id=school_id,
        data=InquiryCreate(
            source="website", first_name="A", last_name="B",
            guardian_name="G", guardian_phone="0241111111",
        ),
    )
    await svc.create(
        tenant_id=tenant["id"], school_id=school_id,
        data=InquiryCreate(
            source="walk_in", first_name="C", last_name="D",
            guardian_name="H", guardian_phone="0242222222",
        ),
    )

    stats = await svc.get_stats(
        tenant_id=tenant["id"], school_id=school_id,
    )

    assert stats["total"] == 2
    assert "new" in stats["by_status"]
    assert stats["by_status"]["new"] == 2
    assert "website" in stats["by_source"]
    assert "walk_in" in stats["by_source"]
    assert stats["conversion_rate"] == 0.0  # No conversions yet

"""
Tests for CSSPS Import Service (Phase 3).

Covers: CSV parsing, file size limits, row caps, preview with validation,
import with dedup, guardian creation, boarding status mapping, formula
injection prevention, and tenant isolation.
Uses the two-engine pattern (admin_session for seeding, app_session for RLS queries).
"""

import pytest
import secrets
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


def _make_csv(rows: list[dict], headers: list[str] | None = None) -> bytes:
    """Build a CSV file as bytes from a list of dicts."""
    import io, csv

    output = io.StringIO()
    if headers is None:
        headers = list(rows[0].keys()) if rows else []
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def _default_mapping() -> dict[str, str | None]:
    """Standard column mapping that matches our CSV headers."""
    return {
        "index_number": "index_number",
        "first_name": "first_name",
        "last_name": "last_name",
        "other_names": "other_names",
        "gender": "gender",
        "date_of_birth": "date_of_birth",
        "programme": "programme",
        "aggregate": "aggregate",
        "jhs_school": "jhs_school",
        "parent_name": "parent_name",
        "parent_phone": "parent_phone",
        "residential_status": "residential_status",
        "house": "house",
    }


def _valid_row(**overrides) -> dict:
    """A valid CSSPS placement row with sensible defaults."""
    defaults = {
        "index_number": f"IDX-{uuid4().hex[:8]}",
        "first_name": "Kwame",
        "last_name": "Asante",
        "other_names": "",
        "gender": "M",
        "date_of_birth": "15/03/2010",
        "programme": "General Science",
        "aggregate": "12",
        "jhs_school": "Achimota JHS",
        "parent_name": "Akosua Mensah",
        "parent_phone": "0241234567",
        "residential_status": "Boarding",
        "house": "Aggrey",
    }
    defaults.update(overrides)
    return defaults


async def _seed_prereqs(admin_session, tenant_id):
    """Seed school, academic year, class, admission period. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'shs', 'active', 'STU', 'STF',
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
                'shs', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"SHS1-{uuid4().hex[:6]}"},
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

    await admin_session.commit()
    return {
        "school_id": school_id, "year_id": year_id,
        "class_id": class_id, "period_id": period_id,
    }


# --- Parsing Tests ---


async def test_parse_csv():
    """Valid CSV file parsed into list of dicts with standard field names."""
    from app.services.admissions.cssps_service import CSSPSImportService

    rows = [_valid_row(), _valid_row()]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService.__new__(CSSPSImportService)  # No DB needed for parse
    records = svc.parse_file(csv_bytes, ".csv", _default_mapping())

    assert len(records) == 2
    assert records[0]["index_number"] == rows[0]["index_number"]
    assert records[0]["first_name"] == "Kwame"
    assert records[0]["gender"] == "M"
    assert records[0]["_row_number"] == 1


async def test_file_too_large():
    """File exceeding 5MB -> FILE_TOO_LARGE error."""
    from app.services.admissions.cssps_service import CSSPSImportService, CSSPSImportError

    svc = CSSPSImportService.__new__(CSSPSImportService)
    large_bytes = b"x" * (5 * 1024 * 1024 + 1)  # Just over 5MB

    with pytest.raises(CSSPSImportError) as exc_info:
        svc.parse_file(large_bytes, ".csv", _default_mapping())
    assert exc_info.value.code == "FILE_TOO_LARGE"


async def test_too_many_rows(app_session, admin_session):
    """File with >1000 rows -> TOO_MANY_ROWS error on import."""
    from app.services.admissions.cssps_service import CSSPSImportService, CSSPSImportError

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    # Build CSV with 1001 rows
    rows = [_valid_row(index_number=f"IDX-{i:05d}") for i in range(1001)]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)

    with pytest.raises(CSSPSImportError) as exc_info:
        await svc.import_placements(
            tenant_id=tenant["id"],
            school_id=prereqs["school_id"],
            period_id=prereqs["period_id"],
            file_bytes=csv_bytes,
            file_type=".csv",
            column_mapping=_default_mapping(),
            programme_to_class_mapping={"General Science": prereqs["class_id"]},
        )
    assert exc_info.value.code == "TOO_MANY_ROWS"


# --- Preview Tests ---


async def test_preview_valid(app_session, admin_session):
    """Preview shows correct valid/error counts for a clean file."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    await set_app_tenant_context(app_session, tenant["id"])

    rows = [_valid_row(), _valid_row()]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.preview_import(
        tenant_id=tenant["id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
    )

    assert result["total_rows"] == 2
    assert result["valid_rows"] == 2
    assert result["error_rows"] == 0
    assert len(result["rows"]) == 2
    assert result["rows"][0]["errors"] == []


async def test_preview_invalid_rows(app_session, admin_session):
    """Rows missing required fields -> marked invalid in preview."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    await set_app_tenant_context(app_session, tenant["id"])

    rows = [
        _valid_row(),  # valid
        _valid_row(index_number="", first_name=""),  # missing index_number + first_name
    ]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.preview_import(
        tenant_id=tenant["id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
    )

    assert result["valid_rows"] == 1
    assert result["error_rows"] == 1
    assert "Missing index_number" in result["rows"][1]["errors"]
    assert "Missing first_name" in result["rows"][1]["errors"]


# --- Import Tests ---


async def test_import_creates_applications(app_session, admin_session):
    """Valid rows imported as Application records with SUBMITTED status."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    rows = [_valid_row(), _valid_row()]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )

    assert result["imported"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == 0
    assert len(result["results"]) == 2
    assert all(r["status"] == "imported" for r in result["results"])
    assert all(r["application_id"] is not None for r in result["results"])


async def test_import_creates_guardians(app_session, admin_session):
    """Parent info in CSV -> ApplicationGuardian created."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    rows = [_valid_row(parent_name="Akosua Mensah", parent_phone="0241234567")]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )

    assert result["imported"] == 1
    app_id = result["results"][0]["application_id"]

    # Verify guardian was created
    guardian_result = await app_session.execute(
        text("""
            SELECT first_name, last_name, phone, is_primary
            FROM application_guardians
            WHERE application_id = CAST(:app_id AS uuid)
        """),
        {"app_id": app_id},
    )
    guardian = guardian_result.fetchone()
    assert guardian is not None
    assert guardian[0] == "Akosua"  # first_name from "Akosua Mensah"
    assert guardian[1] == "Mensah"  # last_name
    assert guardian[2] == "0241234567"
    assert guardian[3] is True  # is_primary


async def test_import_dedup(app_session, admin_session):
    """Existing index_number in same period -> skipped."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    shared_index = f"IDX-{uuid4().hex[:8]}"

    # First import
    rows_1 = [_valid_row(index_number=shared_index)]
    csv_1 = _make_csv(rows_1)

    svc = CSSPSImportService(app_session)
    result_1 = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_1,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )
    assert result_1["imported"] == 1

    # Second import with same index_number -> skipped
    rows_2 = [_valid_row(index_number=shared_index)]
    csv_2 = _make_csv(rows_2)

    result_2 = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_2,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )
    assert result_2["skipped"] == 1
    assert result_2["imported"] == 0
    assert result_2["results"][0]["status"] == "skipped"


async def test_import_dedup_within_batch(app_session, admin_session):
    """Duplicate index_numbers within the same file -> second is skipped."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    shared_index = f"IDX-{uuid4().hex[:8]}"
    rows = [
        _valid_row(index_number=shared_index),
        _valid_row(index_number=shared_index),  # duplicate within same file
    ]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )

    assert result["imported"] == 1
    assert result["skipped"] == 1


async def test_import_boarding_status(app_session, admin_session):
    """Residential status 'Boarding' -> boarding_status='boarding' on application."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    rows = [_valid_row(residential_status="Boarding")]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )

    assert result["imported"] == 1
    app_id = result["results"][0]["application_id"]

    row = await app_session.execute(
        text("SELECT boarding_status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": app_id},
    )
    assert row.scalar() == "boarding"


async def test_import_custom_fields(app_session, admin_session):
    """Imported app has cssps=true and index_number in custom_fields."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    idx = f"IDX-{uuid4().hex[:8]}"
    rows = [_valid_row(index_number=idx, programme="General Science")]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )

    app_id = result["results"][0]["application_id"]
    row = await app_session.execute(
        text("SELECT custom_fields FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": app_id},
    )
    custom_fields = row.scalar()
    assert custom_fields["cssps"] is True
    assert custom_fields["index_number"] == idx


async def test_import_programme_mapping(app_session, admin_session):
    """Programme maps to target_class_id. Unmapped programme -> error."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    rows = [
        _valid_row(programme="General Science"),  # mapped
        _valid_row(programme="Visual Arts"),       # NOT mapped
    ]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant["id"],
        school_id=prereqs["school_id"],
        period_id=prereqs["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        # Only map "General Science" -- "Visual Arts" has no mapping
        programme_to_class_mapping={"General Science": prereqs["class_id"]},
    )

    assert result["imported"] == 1
    assert result["errors"] == 1
    assert "No class mapping" in result["results"][1]["error"]


async def test_import_formula_injection():
    """Leading =, +, -, @ stripped from cell values (formula injection prevention)."""
    from app.services.admissions.cssps_service import CSSPSImportService

    svc = CSSPSImportService.__new__(CSSPSImportService)

    # Build CSV with formula injection attempt
    rows = [_valid_row(first_name="=CMD('calc')", last_name="+HYPERLINK")]
    csv_bytes = _make_csv(rows)

    records = svc.parse_file(csv_bytes, ".csv", _default_mapping())

    assert records[0]["first_name"].startswith("'")  # Prefixed with '
    assert records[0]["last_name"].startswith("'")


async def test_import_tenant_isolation(app_session, admin_session):
    """Tenant B cannot see applications imported by Tenant A."""
    from app.services.admissions.cssps_service import CSSPSImportService

    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)

    prereqs_a = await _seed_prereqs(admin_session, tenant_a["id"])

    # Import as Tenant A
    await set_app_tenant_context(app_session, tenant_a["id"])

    rows = [_valid_row()]
    csv_bytes = _make_csv(rows)

    svc = CSSPSImportService(app_session)
    result = await svc.import_placements(
        tenant_id=tenant_a["id"],
        school_id=prereqs_a["school_id"],
        period_id=prereqs_a["period_id"],
        file_bytes=csv_bytes,
        file_type=".csv",
        column_mapping=_default_mapping(),
        programme_to_class_mapping={"General Science": prereqs_a["class_id"]},
    )
    assert result["imported"] == 1
    imported_app_id = result["results"][0]["application_id"]

    # Capture tenant A's app count
    count_a = await app_session.execute(text("SELECT count(*) FROM applications"))
    assert count_a.scalar() >= 1

    # Switch to Tenant B -- should see 0 applications
    await set_app_tenant_context(app_session, tenant_b["id"])
    count_b = await app_session.execute(text("SELECT count(*) FROM applications"))
    assert count_b.scalar() == 0, "Tenant B must NOT see Tenant A's CSSPS imports"

    # Verify specific app is invisible
    specific = await app_session.execute(
        text("SELECT id FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": imported_app_id},
    )
    assert specific.fetchone() is None, "Tenant B must NOT see Tenant A's application by ID"

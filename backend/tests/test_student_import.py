"""
SIMS Plus - Student Import Service Tests

Tests for CSV/Excel file import functionality. These cover:
- CSV parsing and column auto-mapping
- Date/gender/boolean parsing helpers
- Import with valid data (creates students)
- Import with missing required fields (returns validation errors)
- Import with duplicate student IDs (handles gracefully)
- Preview mode (returns parsed preview without creating)

Import tests use the two-engine pattern where the service needs a DB
session (for generate_student_id and create_student), but the parsing
and mapping methods are tested as static methods where possible.
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.services.student import StudentService, StudentServiceError
from app.services.student.import_service import StudentImportMixin

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
]


# --- Helpers ---

def _make_csv(rows: list[list[str]]) -> bytes:
    """Build CSV bytes from a list of rows (first row is headers)."""
    lines = [",".join(row) for row in rows]
    return "\n".join(lines).encode("utf-8")


async def _seed_school(admin_session, tenant_id, prefix="STU"):
    """Create a minimal school for the tenant. Returns school_id."""
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', :prefix, 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"Import School",
            "slug": f"import-{uuid4().hex[:8]}",
            "prefix": prefix,
        },
    )
    await admin_session.flush()
    return school_id


# --- Static Method Tests (No DB required) ---


class TestCsvParsing:
    """Tests for static CSV parsing and column mapping methods."""

    async def test_parse_csv_file_returns_headers_and_rows(self):
        """parse_csv_file returns (headers, rows) from valid CSV bytes."""
        csv_data = _make_csv([
            ["first_name", "last_name", "date_of_birth", "gender"],
            ["Kwame", "Asante", "2010-05-15", "male"],
            ["Ama", "Boateng", "2011-03-20", "female"],
        ])

        headers, rows = StudentImportMixin.parse_csv_file(csv_data)

        assert headers == ["first_name", "last_name", "date_of_birth", "gender"]
        assert len(rows) == 2
        assert rows[0]["first_name"] == "Kwame"
        assert rows[1]["first_name"] == "Ama"

    async def test_parse_csv_file_empty_returns_empty_rows(self):
        """parse_csv_file with headers only returns empty rows."""
        csv_data = _make_csv([
            ["first_name", "last_name"],
        ])

        headers, rows = StudentImportMixin.parse_csv_file(csv_data)
        assert len(headers) == 2
        assert len(rows) == 0

    async def test_auto_map_columns_standard_headers(self):
        """_auto_map_columns correctly maps standard header names."""
        headers = ["First Name", "Last Name", "Date of Birth", "Gender", "Phone"]

        mapping = StudentImportMixin._auto_map_columns(headers)

        assert "first_name" in mapping
        assert "last_name" in mapping
        assert "date_of_birth" in mapping
        assert "gender" in mapping
        assert "phone" in mapping

    async def test_auto_map_columns_alternate_names(self):
        """_auto_map_columns maps alternate header names (surname, dob, sex)."""
        headers = ["firstname", "surname", "dob", "sex"]

        mapping = StudentImportMixin._auto_map_columns(headers)

        assert "first_name" in mapping
        assert "last_name" in mapping
        assert "date_of_birth" in mapping
        assert "gender" in mapping

    async def test_auto_map_columns_student_id_maps_to_previous(self):
        """student_id from file maps to previous_student_id (system auto-generates)."""
        headers = ["student_id", "first_name", "last_name"]

        mapping = StudentImportMixin._auto_map_columns(headers)

        assert "previous_student_id" in mapping
        assert mapping["previous_student_id"] == "student_id"


class TestDateParsing:
    """Tests for the _parse_date static method."""

    async def test_parse_date_iso_format(self):
        """Parses YYYY-MM-DD format."""
        result = StudentImportMixin._parse_date("2010-05-15")
        assert result == date(2010, 5, 15)

    async def test_parse_date_slash_format(self):
        """Parses DD/MM/YYYY format."""
        result = StudentImportMixin._parse_date("15/01/2010")
        assert result == date(2010, 1, 15)

    async def test_parse_date_none_returns_none(self):
        """None input returns None."""
        result = StudentImportMixin._parse_date(None)
        assert result is None

    async def test_parse_date_empty_string_returns_none(self):
        """Empty string returns None."""
        result = StudentImportMixin._parse_date("")
        assert result is None

    async def test_parse_date_date_object_passthrough(self):
        """A date object is returned as-is."""
        d = date(2010, 5, 15)
        result = StudentImportMixin._parse_date(d)
        assert result == d

    async def test_parse_date_invalid_raises_error(self):
        """Unparseable date string raises ValueError."""
        with pytest.raises(ValueError):
            StudentImportMixin._parse_date("not-a-date")


class TestGenderParsing:
    """Tests for the _parse_gender static method."""

    async def test_parse_gender_male_variants(self):
        """Various male representations map to 'male'."""
        for value in ["male", "Male", "M", "m", "boy", "Boy"]:
            assert StudentImportMixin._parse_gender(value) == "male"

    async def test_parse_gender_female_variants(self):
        """Various female representations map to 'female'."""
        for value in ["female", "Female", "F", "f", "girl", "Girl"]:
            assert StudentImportMixin._parse_gender(value) == "female"

    async def test_parse_gender_none_defaults_to_male(self):
        """None defaults to 'male'."""
        assert StudentImportMixin._parse_gender(None) == "male"


class TestBooleanParsing:
    """Tests for the _parse_boolean static method."""

    async def test_parse_boolean_truthy_values(self):
        """Truthy strings return True."""
        for value in ["true", "True", "yes", "Yes", "1", "y", "Y", "boarder"]:
            assert StudentImportMixin._parse_boolean(value) is True

    async def test_parse_boolean_falsy_values(self):
        """Falsy strings return False."""
        for value in ["false", "False", "no", "No", "0", "n"]:
            assert StudentImportMixin._parse_boolean(value) is False

    async def test_parse_boolean_none_returns_false(self):
        """None returns False."""
        assert StudentImportMixin._parse_boolean(None) is False


# --- Import Integration Tests (Require DB) ---


class TestStudentImportFromFile:
    """Tests for import_students_from_file (requires database)."""

    async def test_import_valid_csv_creates_students(
        self, app_session, admin_session
    ):
        """Importing a valid CSV with required fields creates students."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"], prefix="IMP")
        await admin_session.commit()

        csv_data = _make_csv([
            ["first_name", "last_name", "date_of_birth", "gender"],
            ["Kwame", "Asante", "2010-05-15", "male"],
            ["Ama", "Boateng", "2011-03-20", "female"],
        ])

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.import_students_from_file(
            tenant_id=tenant["id"],
            file_content=csv_data,
            file_type="csv",
        )

        assert result["total_rows"] == 2
        assert result["created"] == 2
        assert result["failed"] == 0
        assert result["errors"] == []

    async def test_import_csv_missing_required_fields_returns_errors(
        self, app_session, admin_session
    ):
        """Importing CSV with missing required fields reports per-row errors."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        # Missing date_of_birth and gender columns entirely
        csv_data = _make_csv([
            ["first_name", "last_name"],
            ["Kofi", "Mensah"],
        ])

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.import_students_from_file(
            tenant_id=tenant["id"],
            file_content=csv_data,
            file_type="csv",
        )

        assert result["created"] == 0
        assert result["failed"] == 1
        assert len(result["errors"]) > 0
        # Errors should mention the missing fields
        error_fields = [e.get("field") for e in result["errors"]]
        assert "date_of_birth" in error_fields or "gender" in error_fields

    async def test_import_empty_csv_returns_zero(
        self, app_session, admin_session
    ):
        """Importing an empty CSV (headers only) returns total_rows=0."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        csv_data = _make_csv([
            ["first_name", "last_name", "date_of_birth", "gender"],
        ])

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.import_students_from_file(
            tenant_id=tenant["id"],
            file_content=csv_data,
            file_type="csv",
        )

        assert result["total_rows"] == 0
        assert result["created"] == 0

    async def test_import_preview_mode_does_not_create(
        self, app_session, admin_session
    ):
        """Preview mode returns parsed data without creating students."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"])
        await admin_session.commit()

        csv_data = _make_csv([
            ["first_name", "last_name", "date_of_birth", "gender"],
            ["Preview", "Student", "2010-01-01", "male"],
        ])

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.import_students_from_file(
            tenant_id=tenant["id"],
            file_content=csv_data,
            file_type="csv",
            preview_only=True,
        )

        assert result["total_rows"] == 1
        assert result["created"] == 0  # preview does not create
        assert len(result["preview"]) == 1
        assert result["preview"][0]["parsed"]["first_name"] == "Preview"

        # Verify no students actually created
        students, total = await service.list_students(tenant["id"])
        assert total == 0

    async def test_import_csv_with_student_id_column_stores_as_previous(
        self, app_session, admin_session
    ):
        """The file's student_id column is stored as previous_student_id.
        The system auto-generates the actual student_id."""
        tenant = await create_test_tenant(admin_session)
        await _seed_school(admin_session, tenant["id"], prefix="IMP")
        await admin_session.commit()

        csv_data = _make_csv([
            ["student_id", "first_name", "last_name", "date_of_birth", "gender"],
            ["OLD-001", "Transfer", "Student", "2010-06-15", "male"],
        ])

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        result = await service.import_students_from_file(
            tenant_id=tenant["id"],
            file_content=csv_data,
            file_type="csv",
        )

        assert result["created"] == 1

        # The created student should have system-generated ID, not the file's
        students, _ = await service.list_students(tenant["id"])
        assert len(students) == 1
        assert students[0].student_id.startswith("IMP")
        assert students[0].previous_student_id == "OLD-001"

    async def test_import_unsupported_file_type_raises_error(
        self, app_session, admin_session
    ):
        """Importing with an unsupported file type raises an error."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = StudentService(app_session)

        with pytest.raises(StudentServiceError):
            await service.import_students_from_file(
                tenant_id=tenant["id"],
                file_content=b"some data",
                file_type="pdf",
            )

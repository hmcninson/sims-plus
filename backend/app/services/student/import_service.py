"""
SIMS Plus - Student Import Service

File import methods (CSV, Excel) for bulk student creation.
"""

import csv
import io
from datetime import datetime, date
from typing import Optional, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.student._shared import StudentServiceError

# Try to import openpyxl for Excel support
try:
    from openpyxl import load_workbook
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False


class StudentImportMixin:
    """Mixin providing file import methods for StudentService."""

    # Type hints for self.db -- set by StudentService.__init__
    db: AsyncSession

    # =========================
    # File Import Methods
    # =========================

    @staticmethod
    def parse_csv_file(file_content: bytes) -> tuple[list[str], list[dict]]:
        """
        Parse a CSV file and return headers and rows.

        Args:
            file_content: Raw bytes of the CSV file

        Returns:
            Tuple of (headers, rows as list of dicts)
        """
        # Try different encodings
        content = None
        for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                content = file_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise StudentServiceError("Unable to decode file. Please use UTF-8 encoding.")

        reader = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames or []
        rows = list(reader)

        return headers, rows

    @staticmethod
    def parse_excel_file(file_content: bytes) -> tuple[list[str], list[dict]]:
        """
        Parse an Excel file and return headers and rows.

        Args:
            file_content: Raw bytes of the Excel file

        Returns:
            Tuple of (headers, rows as list of dicts)
        """
        if not EXCEL_SUPPORT:
            raise StudentServiceError("Excel support not available. Install openpyxl.")

        workbook = load_workbook(filename=io.BytesIO(file_content), read_only=True)
        sheet = workbook.active

        rows = []
        headers = []

        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                # First row is headers
                headers = [str(cell).strip() if cell else f"Column_{j}" for j, cell in enumerate(row)]
            else:
                # Convert row to dict
                row_dict = {}
                for j, cell in enumerate(row):
                    if j < len(headers):
                        row_dict[headers[j]] = cell
                # Skip empty rows
                if any(v is not None and v != "" for v in row_dict.values()):
                    rows.append(row_dict)

        workbook.close()
        return headers, rows

    @staticmethod
    def _normalize_column_name(name: str) -> str:
        """Normalize column name for matching."""
        return name.lower().strip().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _auto_map_columns(headers: list[str]) -> dict[str, str]:
        """
        Auto-map CSV/Excel headers to student fields.

        Returns:
            Dict mapping student field names to CSV column names
        """
        # Map file columns to our fields
        # Note: student_id from file is mapped to previous_student_id
        # The system always auto-generates the actual student_id
        field_aliases = {
            "previous_student_id": ["student_id", "studentid", "student_no", "student_number", "id", "admission_no", "previous_student_id", "old_id", "external_id"],
            "first_name": ["first_name", "firstname", "first", "given_name"],
            "middle_name": ["middle_name", "middlename", "middle", "other_names"],
            "last_name": ["last_name", "lastname", "last", "surname", "family_name"],
            "date_of_birth": ["date_of_birth", "dob", "dateofbirth", "birth_date", "birthdate"],
            "gender": ["gender", "sex"],
            "email": ["email", "email_address", "e_mail"],
            "phone": ["phone", "phone_number", "telephone", "mobile", "contact"],
            "address": ["address", "home_address", "residential_address"],
            "city": ["city", "town"],
            "region": ["region", "state", "province"],
            "class_name": ["class", "class_name", "grade", "level", "form"],
            "is_boarder": ["is_boarder", "boarder", "boarding", "resident"],
        }

        mapping = {}
        normalized_headers = {StudentImportMixin._normalize_column_name(h): h for h in headers}

        for field, aliases in field_aliases.items():
            for alias in aliases:
                if alias in normalized_headers:
                    mapping[field] = normalized_headers[alias]
                    break

        return mapping

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        """Parse various date formats."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()

        value_str = str(value).strip()
        if not value_str:
            return None

        # Try various date formats
        formats = [
            "%Y-%m-%d",      # 2026-01-15
            "%d/%m/%Y",      # 15/01/2026
            "%m/%d/%Y",      # 01/15/2026
            "%d-%m-%Y",      # 15-01-2026
            "%Y/%m/%d",      # 2026/01/15
            "%d %b %Y",      # 15 Jan 2026
            "%d %B %Y",      # 15 January 2026
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date: {value_str}")

    @staticmethod
    def _parse_gender(value: Any) -> str:
        """Parse gender value to standard format."""
        if value is None:
            return "male"  # Default

        value_str = str(value).lower().strip()
        if value_str in ["m", "male", "boy", "man"]:
            return "male"
        elif value_str in ["f", "female", "girl", "woman"]:
            return "female"
        else:
            return "male"  # Default

    @staticmethod
    def _parse_boolean(value: Any) -> bool:
        """Parse boolean value."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value

        value_str = str(value).lower().strip()
        return value_str in ["true", "yes", "1", "y", "t", "boarder"]

    async def import_students_from_file(
        self,
        tenant_id: UUID,
        file_content: bytes,
        file_type: str,
        column_mapping: Optional[dict[str, str]] = None,
        preview_only: bool = False,
        auto_generate_ids: bool = True,  # Kept for backward compatibility, but always generates
    ) -> dict:
        """
        Import students from a CSV or Excel file.

        Args:
            tenant_id: Tenant UUID
            file_content: Raw file bytes
            file_type: 'csv' or 'xlsx'
            column_mapping: Optional manual column mapping
            preview_only: If True, only return preview without creating
            auto_generate_ids: Deprecated - student_id is always auto-generated.
                               File's student_id column is stored as previous_student_id.

        Returns:
            Dict with import results
        """
        # Parse file based on type
        if file_type == "csv":
            headers, rows = self.parse_csv_file(file_content)
        elif file_type in ["xlsx", "xls"]:
            headers, rows = self.parse_excel_file(file_content)
        else:
            raise StudentServiceError(f"Unsupported file type: {file_type}")

        if not rows:
            return {
                "total_rows": 0,
                "created": 0,
                "failed": 0,
                "errors": [{"row": 0, "error": "File is empty or has no data rows"}],
                "preview": [],
            }

        # Auto-map columns if not provided
        if not column_mapping:
            column_mapping = self._auto_map_columns(headers)

        # Preview mode - return first 5 rows with parsed values
        if preview_only:
            preview = []
            for i, row in enumerate(rows[:5]):
                parsed = self._parse_row(row, column_mapping, i + 2)
                preview.append({
                    "row_number": i + 2,
                    "raw": row,
                    "parsed": parsed.get("data", {}),
                    "errors": parsed.get("errors", []),
                })
            return {
                "total_rows": len(rows),
                "created": 0,
                "failed": 0,
                "errors": [],
                "preview": preview,
                "headers": headers,
                "auto_mapping": column_mapping,
            }

        # Check plan limit for the entire batch before starting import
        from app.services.subscription import SubscriptionService
        sub_service = SubscriptionService(self.db)
        await sub_service.check_student_limit(tenant_id, additional=len(rows))

        # Import mode - create students
        # Note: student_id is ALWAYS auto-generated by the system
        # The file's student_id column is mapped to previous_student_id
        created = 0
        failed = 0
        errors = []
        max_id_retries = 5  # Max retries for ID conflicts

        # Get the school's student_id_prefix for consistent ID generation
        from app.models.school import School
        school_result = await self.db.execute(
            select(School.student_id_prefix).where(
                School.tenant_id == tenant_id,
                School.deleted_at.is_(None),
            ).limit(1)
        )
        school_prefix = school_result.scalar_one_or_none() or "STU"

        for i, row in enumerate(rows):
            row_number = i + 2  # Account for header row
            parsed = self._parse_row(row, column_mapping, row_number)

            if parsed.get("errors"):
                failed += 1
                errors.extend(parsed["errors"])
                continue

            student_data = parsed["data"]

            # Create the student with retry logic for auto-generated IDs
            student_created = False
            for attempt in range(max_id_retries):
                try:
                    # Always auto-generate student ID using school's prefix
                    student_data["student_id"] = await self.generate_student_id(
                        tenant_id, prefix=school_prefix
                    )

                    await self.create_student(
                        tenant_id=tenant_id,
                        **student_data,
                    )
                    created += 1
                    student_created = True
                    break
                except StudentServiceError as e:
                    # Retry on duplicate ID (race condition on auto-generation)
                    if e.code == "duplicate_student_id" and attempt < max_id_retries - 1:
                        import asyncio
                        await asyncio.sleep(0.01 * (attempt + 1))
                        continue
                    failed += 1
                    errors.append({
                        "row": row_number,
                        "previous_student_id": student_data.get("previous_student_id"),
                        "error": e.message,
                    })
                    break
                except Exception as e:
                    failed += 1
                    errors.append({
                        "row": row_number,
                        "previous_student_id": student_data.get("previous_student_id"),
                        "error": str(e),
                    })
                    break

            if not student_created and not any(
                err.get("row") == row_number for err in errors
            ):
                # All retries exhausted without recording an error
                failed += 1
                errors.append({
                    "row": row_number,
                    "error": f"Failed to generate unique student ID after {max_id_retries} attempts",
                })

        return {
            "total_rows": len(rows),
            "created": created,
            "failed": failed,
            "errors": errors,
            "preview": [],
        }

    def _parse_row(
        self,
        row: dict,
        column_mapping: dict[str, str],
        row_number: int,
    ) -> dict:
        """
        Parse a single row using the column mapping.

        Returns:
            Dict with 'data' and 'errors' keys
        """
        data = {}
        errors = []

        # Required fields
        required_fields = ["first_name", "last_name", "date_of_birth", "gender"]

        for field, column in column_mapping.items():
            if column not in row:
                continue

            value = row[column]

            try:
                if field == "date_of_birth":
                    parsed_value = self._parse_date(value)
                    if parsed_value:
                        data[field] = parsed_value
                elif field == "gender":
                    data[field] = self._parse_gender(value)
                elif field == "is_boarder":
                    data[field] = self._parse_boolean(value)
                elif field == "class_name":
                    # Store for later lookup, don't add to data directly
                    pass
                elif value is not None and str(value).strip():
                    data[field] = str(value).strip()
            except Exception as e:
                errors.append({
                    "row": row_number,
                    "field": field,
                    "value": str(value),
                    "error": str(e),
                })

        # Check required fields
        for field in required_fields:
            if field not in data:
                mapped_column = column_mapping.get(field, field)
                errors.append({
                    "row": row_number,
                    "field": field,
                    "error": f"Required field '{mapped_column}' is missing or empty",
                })

        return {"data": data, "errors": errors}

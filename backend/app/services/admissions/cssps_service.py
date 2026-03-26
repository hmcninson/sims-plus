"""
SIMS Plus - CSSPS Import Service

Parses CSSPS (Computerised School Selection and Placement System) placement
files and imports them as applications. CSSPS places JHS graduates into SHS.

The parser supports:
- CSV files with configurable column mapping
- Excel (.xlsx) files with configurable column mapping
- Deduplication by BECE index_number within the same admission period
- Programme-to-class mapping (admin maps programme names to class UUIDs)
- Preview mode (parse without DB writes)

See 00-overview.md Section 5 for the CSSPS file format definition.

Security controls (REVIEW FIX H3):
- 5MB file size limit (enforced at both endpoint and service layer)
- 1000 row cap (prevents resource exhaustion on large files)
- Formula injection prevention (strips leading =, +, -, @ from cell values)
"""

import csv
import io
import secrets
import uuid
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admissions import (
    AdmissionApplicationStatus,
    Application,
    ApplicationGuardian,
    ApplicationStatusHistory,
)

logger = structlog.get_logger(__name__)

# Characters that can trigger formula execution in spreadsheet applications
_FORMULA_CHARS = frozenset({"=", "+", "-", "@"})


class CSSPSImportError(Exception):
    def __init__(self, message: str, code: str = "CSSPS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class CSSPSImportService:
    MAX_CSSPS_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_IMPORT_ROWS = 1000

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- File Parsing ---

    def parse_file(
        self,
        file_bytes: bytes,
        file_type: str,
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """
        Parse a CSV or Excel file into a list of standardized record dicts.

        column_mapping maps our standard field names to the actual file column headers.
        Only mapped columns are extracted; unmapped fields default to None.

        Returns a list of dicts with standardized field names.
        """
        # Defense-in-depth: enforce file size limit at the service layer
        if len(file_bytes) > self.MAX_CSSPS_FILE_SIZE:
            raise CSSPSImportError("File too large. Maximum 5MB.", "FILE_TOO_LARGE")

        if file_type in ("text/csv", "application/csv", ".csv"):
            return self._parse_csv(file_bytes, column_mapping)
        elif file_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        ):
            return self._parse_excel(file_bytes, column_mapping)
        else:
            raise CSSPSImportError(
                f"Unsupported file type: {file_type}. Use CSV or Excel (.xlsx)",
                code="UNSUPPORTED_FILE_TYPE",
            )

    def _parse_csv(
        self,
        file_bytes: bytes,
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """Parse CSV with configurable column mapping."""
        # Try UTF-8 first (with BOM stripping), fall back to latin-1 for legacy files
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        return self._map_rows(list(reader), column_mapping)

    def _parse_excel(
        self,
        file_bytes: bytes,
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """Parse Excel (.xlsx) with configurable column mapping."""
        try:
            import openpyxl
        except ImportError:
            raise CSSPSImportError(
                "openpyxl is required for Excel import",
                code="MISSING_DEPENDENCY",
            )

        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes), read_only=True, data_only=True
        )
        ws = wb.active
        if ws is None:
            raise CSSPSImportError(
                "Excel file has no active worksheet", code="EMPTY_FILE"
            )

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            raise CSSPSImportError("File has no data rows", code="EMPTY_FILE")

        # First row is headers
        headers = [str(h).strip() if h else "" for h in rows[0]]
        data_rows = []
        for row in rows[1:]:
            if all(cell is None for cell in row):
                continue  # Skip completely empty rows
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = (
                        str(row[i]).strip() if row[i] is not None else None
                    )
            data_rows.append(row_dict)

        wb.close()
        return self._map_rows(data_rows, column_mapping)

    def _map_rows(
        self,
        rows: list[dict],
        column_mapping: dict[str, str | None],
    ) -> list[dict]:
        """
        Map file columns to standard field names using the provided mapping.

        Also sanitizes values to prevent formula injection in downstream
        spreadsheet re-exports.
        """
        mapped = []
        for row_num, row in enumerate(rows, start=1):
            record: dict = {"_row_number": row_num}
            for standard_field, file_column in column_mapping.items():
                if file_column is None:
                    record[standard_field] = None
                else:
                    # Case-insensitive column lookup
                    value = None
                    for key, val in row.items():
                        if key and key.strip().lower() == file_column.strip().lower():
                            value = val
                            break
                    value = value.strip() if value else None
                    # Formula injection prevention: prefix dangerous characters
                    # Skip numeric fields that can legitimately start with -
                    if (
                        value
                        and value[0] in _FORMULA_CHARS
                        and standard_field not in ("aggregate",)
                    ):
                        value = "'" + value
                    record[standard_field] = value
            mapped.append(record)
        return mapped

    # --- Preview (no DB writes) ---

    async def preview_import(
        self,
        tenant_id: uuid.UUID,
        file_bytes: bytes,
        file_type: str,
        column_mapping: dict[str, str | None],
    ) -> dict:
        """
        Parse file and return preview data without writing to the database.

        Used by the frontend to show a preview of the import with validation
        errors before the admin commits to importing.
        """
        records = self.parse_file(file_bytes, file_type, column_mapping)

        preview_rows = []
        valid_count = 0
        error_count = 0

        for record in records:
            errors = self._validate_record(record)
            row_data = {
                "row_number": record.get("_row_number", 0),
                "index_number": record.get("index_number"),
                "first_name": record.get("first_name"),
                "last_name": record.get("last_name"),
                "other_names": record.get("other_names"),
                "gender": record.get("gender"),
                "date_of_birth": record.get("date_of_birth"),
                "programme": record.get("programme"),
                "aggregate": self._safe_int(record.get("aggregate")),
                "jhs_school": record.get("jhs_school"),
                "parent_name": record.get("parent_name"),
                "parent_phone": record.get("parent_phone"),
                "residential_status": record.get("residential_status"),
                "house": record.get("house"),
                "errors": errors,
            }
            preview_rows.append(row_data)
            if errors:
                error_count += 1
            else:
                valid_count += 1

        # Detect raw file columns for the column mapping UI so the admin
        # can see what headers are in the file and map them to our fields
        detected_columns = self._detect_columns(file_bytes, file_type)

        return {
            "total_rows": len(records),
            "valid_rows": valid_count,
            "error_rows": error_count,
            "detected_columns": detected_columns,
            "rows": preview_rows,
        }

    def _detect_columns(self, file_bytes: bytes, file_type: str) -> list[str]:
        """
        Extract the raw column headers from the file for the mapping UI.

        Returns the first row's keys without any mapping applied.
        """
        if file_type in ("text/csv", "application/csv", ".csv"):
            try:
                text = file_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1")
            reader = csv.DictReader(io.StringIO(text))
            return list(reader.fieldnames or [])
        elif file_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        ):
            try:
                import openpyxl

                wb = openpyxl.load_workbook(
                    io.BytesIO(file_bytes), read_only=True, data_only=True
                )
                ws = wb.active
                if ws is None:
                    return []
                rows = list(ws.iter_rows(max_row=1, values_only=True))
                wb.close()
                if rows:
                    return [str(h).strip() for h in rows[0] if h]
            except Exception:
                pass
        return []

    # --- Import (creates Application records) ---

    async def import_placements(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        period_id: uuid.UUID,
        *,
        file_bytes: bytes,
        file_type: str,
        column_mapping: dict[str, str | None],
        programme_to_class_mapping: dict[str, uuid.UUID],
    ) -> dict:
        """
        Import CSSPS placement data as application records.

        For each valid row:
        1. Check dedup by index_number within the same admission period
        2. Map programme to target_class_id via programme_to_class_mapping
        3. Create Application (status=submitted, custom_fields.cssps=true)
        4. Create ApplicationGuardian if parent_name/phone present
        5. Create ApplicationStatusHistory for audit trail
        6. Set boarding_status from residential_status
        """
        records = self.parse_file(file_bytes, file_type, column_mapping)

        # Enforce row cap to prevent resource exhaustion
        if len(records) > self.MAX_IMPORT_ROWS:
            raise CSSPSImportError(
                f"File contains {len(records)} rows. Maximum {self.MAX_IMPORT_ROWS}. "
                "Split the file into smaller batches.",
                "TOO_MANY_ROWS",
            )

        # Pre-load existing index_numbers for this period to check duplicates
        # in a single query rather than N+1 per row
        existing_result = await self.db.execute(
            select(Application.custom_fields).filter(
                Application.tenant_id == tenant_id,
                Application.admission_period_id == period_id,
                Application.deleted_at.is_(None),
            )
        )
        existing_index_numbers: set[str] = set()
        for (custom_fields,) in existing_result.all():
            if isinstance(custom_fields, dict) and custom_fields.get("index_number"):
                existing_index_numbers.add(str(custom_fields["index_number"]))

        results: list[dict] = []
        imported = 0
        skipped = 0
        errors = 0

        for record in records:
            row_num = record.get("_row_number", 0)
            index_number = record.get("index_number", "")

            # Validate required fields
            validation_errors = self._validate_record(record)
            if validation_errors:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number or "",
                    "status": "error",
                    "application_id": None,
                    "error": "; ".join(validation_errors),
                })
                errors += 1
                continue

            # Dedup check by index_number within same period
            if index_number in existing_index_numbers:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "skipped",
                    "application_id": None,
                    "error": "Duplicate index number in this period",
                })
                skipped += 1
                continue

            # Map programme to class — unmapped programmes are an error
            programme = record.get("programme", "")
            target_class_id = programme_to_class_mapping.get(programme)
            if not target_class_id:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "error",
                    "application_id": None,
                    "error": f"No class mapping for programme: {programme}",
                })
                errors += 1
                continue

            # Parse and normalize fields
            dob = self._parse_date(record.get("date_of_birth"))
            gender = self._normalize_gender(record.get("gender"))
            aggregate = self._safe_int(record.get("aggregate"))

            # Determine boarding status from residential_status field
            residential = record.get("residential_status", "")
            boarding_status = None
            if residential:
                boarding_status = (
                    "boarding"
                    if residential.lower() in ("boarding", "boarder", "b")
                    else "day"
                )

            # Build custom_fields with CSSPS metadata for later querying
            custom_fields = {
                "cssps": True,
                "index_number": index_number,
                "aggregate": aggregate,
                "jhs_school": record.get("jhs_school"),
                "jhs_district": record.get("jhs_district"),
                "region": record.get("region"),
                "programme": programme,
                "house": record.get("house"),
            }

            try:
                # Create application with SUBMITTED status (CSSPS placements
                # skip the draft/payment stage — they are pre-approved)
                application = Application(
                    tenant_id=tenant_id,
                    school_id=school_id,
                    admission_period_id=period_id,
                    tracking_code=secrets.token_urlsafe(48),
                    applicant_first_name=record["first_name"],
                    applicant_last_name=record["last_name"],
                    applicant_other_names=record.get("other_names"),
                    date_of_birth=dob,
                    gender=gender,
                    target_class_id=target_class_id,
                    status=AdmissionApplicationStatus.SUBMITTED.value,
                    custom_fields=custom_fields,
                    boarding_status=boarding_status,
                )
                self.db.add(application)
                await self.db.flush()

                # Create guardian if parent info is present
                parent_name = record.get("parent_name")
                parent_phone = record.get("parent_phone")
                if parent_name:
                    # Best-effort name splitting: "Ama Mensah" -> first="Ama" last="Mensah"
                    parts = parent_name.strip().split(" ", 1)
                    guardian = ApplicationGuardian(
                        tenant_id=tenant_id,
                        application_id=application.id,
                        first_name=parts[0],
                        last_name=parts[-1] if len(parts) > 1 else parts[0],
                        phone=parent_phone or "",
                        relationship="parent",
                        is_primary=True,
                    )
                    self.db.add(guardian)

                # Append-only status history for audit trail
                history = ApplicationStatusHistory(
                    tenant_id=tenant_id,
                    application_id=application.id,
                    from_status=None,
                    to_status=AdmissionApplicationStatus.SUBMITTED.value,
                    reason="Imported from CSSPS placement data",
                )
                self.db.add(history)

                await self.db.flush()

                # Track for dedup within this batch so later rows with the
                # same index_number are caught without another DB query
                existing_index_numbers.add(index_number)

                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "imported",
                    "application_id": str(application.id),
                    "error": None,
                })
                imported += 1

            except Exception as e:
                results.append({
                    "row_number": row_num,
                    "index_number": index_number,
                    "status": "error",
                    "application_id": None,
                    # Never expose internal error details to the client
                    "error": "Import failed for this row",
                })
                errors += 1
                logger.error(
                    "cssps_row_import_failed",
                    row_number=row_num,
                    index_number=index_number,
                    error=str(e),
                )

        logger.info(
            "cssps_import_completed",
            total=len(records),
            imported=imported,
            skipped=skipped,
            errors=errors,
        )

        return {
            "total_rows": len(records),
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "results": results,
        }

    # --- Validation Helpers ---

    def _validate_record(self, record: dict) -> list[str]:
        """
        Validate a parsed record. Returns a list of error messages (empty = valid).

        Required fields: index_number, first_name, last_name, gender, programme.
        """
        errors = []
        if not record.get("index_number"):
            errors.append("Missing index_number")
        if not record.get("first_name"):
            errors.append("Missing first_name")
        if not record.get("last_name"):
            errors.append("Missing last_name")
        if not record.get("gender"):
            errors.append("Missing gender")
        if not record.get("programme"):
            errors.append("Missing programme")
        return errors

    def _normalize_gender(self, value: str | None) -> str | None:
        """Normalize gender values: M/m/Male -> male, F/f/Female -> female."""
        if not value:
            return None
        v = value.strip().lower()
        if v in ("m", "male"):
            return "male"
        if v in ("f", "female"):
            return "female"
        return value.lower()

    def _parse_date(self, value: str | None) -> date | None:
        """
        Parse date in DD/MM/YYYY format (Ghana standard).

        Falls back to ISO format (YYYY-MM-DD) for flexibility.
        """
        if not value:
            return None
        try:
            # Try DD/MM/YYYY first (Ghana format)
            parts = value.strip().split("/")
            if len(parts) == 3:
                return date(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            pass
        try:
            # Fall back to ISO format YYYY-MM-DD
            return date.fromisoformat(value.strip())
        except ValueError:
            return None

    def _safe_int(self, value: str | None) -> int | None:
        """Safely convert to int, returning None on failure."""
        if not value:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

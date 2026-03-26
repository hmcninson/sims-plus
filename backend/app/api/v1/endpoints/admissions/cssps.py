"""
SIMS Plus - CSSPS Placement Import Endpoints

Import CSSPS (Computerised School Selection and Placement System) data
for SHS student placement. Supports CSV and Excel files with configurable
column mapping.

Two-step workflow:
1. POST /preview — parse file, show validation results to admin
2. POST /import  — commit valid rows as Application records

Both endpoints accept multipart form data (file + JSON config string)
because file uploads cannot use JSON request bodies.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.cssps import (
    CSSPSColumnMapping,
    CSSPSImportRequest,
    CSSPSImportResponse,
    CSSPSPreviewRequest,
    CSSPSPreviewResponse,
)
from app.services.admissions.cssps_service import CSSPSImportError, CSSPSImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/cssps")

# Defense-in-depth: enforce at endpoint layer too (service also checks)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _handle_error(e: CSSPSImportError) -> HTTPException:
    """Map CSSPS service errors to HTTP responses."""
    status_map = {
        "UNSUPPORTED_FILE_TYPE": 422,
        "EMPTY_FILE": 422,
        "FILE_TOO_LARGE": 413,
        "TOO_MANY_ROWS": 422,
        "MISSING_DEPENDENCY": 500,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


def _resolve_file_type(file: UploadFile) -> str:
    """
    Determine file type from filename extension, falling back to content_type.

    Extension-based detection is more reliable than content_type which
    browsers often set incorrectly for CSV files.
    """
    if file.filename and file.filename.endswith(".csv"):
        return ".csv"
    if file.filename and file.filename.endswith(".xlsx"):
        return ".xlsx"
    return file.content_type or ""


@router.post(
    "/preview",
    response_model=CSSPSPreviewResponse,
    summary="Preview CSSPS file",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def preview_cssps(
    user: ValidatedUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    column_mapping: str = Form("{}"),
) -> CSSPSPreviewResponse:
    """
    Parse and preview a CSSPS placement file without creating any records.

    Upload a CSV or Excel file. Optionally provide column_mapping as a JSON
    string to map file columns to standard CSSPS fields. Returns parsed rows
    with validation errors so the admin can review before committing.
    """
    import json

    # Enforce file size limit at the endpoint layer
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5MB limit",
        )

    # Parse column mapping from form data (JSON string)
    try:
        mapping_dict = json.loads(column_mapping) if column_mapping != "{}" else {}
        if mapping_dict:
            preview_req = CSSPSPreviewRequest(
                column_mapping=CSSPSColumnMapping(**mapping_dict),
            )
        else:
            preview_req = CSSPSPreviewRequest()
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid column_mapping JSON: {e}",
        )

    try:
        svc = CSSPSImportService(db)
        file_type = _resolve_file_type(file)

        result = await svc.preview_import(
            tenant_id=UUID(user["tenant_id"]),
            file_bytes=file_bytes,
            file_type=file_type,
            column_mapping=preview_req.column_mapping.model_dump(exclude_none=True),
        )
        return CSSPSPreviewResponse(**result)
    except CSSPSImportError as e:
        raise _handle_error(e)


@router.post(
    "/import",
    response_model=CSSPSImportResponse,
    summary="Import CSSPS placements",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def import_cssps(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    import_config: str = Form(...),
) -> CSSPSImportResponse:
    """
    Import CSSPS placement data as application records.

    Upload a CSV or Excel file with import_config as a JSON string containing:
    - admission_period_id: UUID of the target admission period
    - column_mapping: maps file column headers to standard fields
    - programme_to_class_mapping: maps programme names to class UUIDs

    Deduplication: rows with index_numbers already present in the same
    admission period are skipped automatically.
    """
    import json

    # Enforce file size limit at the endpoint layer
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5MB limit",
        )

    # Parse import config from form data (JSON string)
    try:
        config = json.loads(import_config)
        import_req = CSSPSImportRequest(**config)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid import_config JSON: {e}",
        )

    try:
        svc = CSSPSImportService(db)
        file_type = _resolve_file_type(file)

        result = await svc.import_placements(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=import_req.admission_period_id,
            file_bytes=file_bytes,
            file_type=file_type,
            column_mapping=import_req.column_mapping.model_dump(exclude_none=True),
            programme_to_class_mapping={
                k: v for k, v in import_req.programme_to_class_mapping.items()
            },
        )
        return CSSPSImportResponse(**result)
    except CSSPSImportError as e:
        raise _handle_error(e)

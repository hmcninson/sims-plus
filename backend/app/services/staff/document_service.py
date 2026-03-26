"""
SIMS Plus - Staff Document Service

Manages staff document uploads, downloads, and soft-deletions via S3.
Cloned from the student document service pattern.
"""

import re
import uuid
from datetime import datetime, UTC
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import Staff, StaffDocument, StaffDocumentType
from app.services.s3 import get_s3_service
from app.services.staff._shared import StaffServiceError

logger = structlog.get_logger()

# Magic byte signatures for document types (prevents Content-Type spoofing)
_DOCUMENT_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG"],
    "application/msword": [b"\xd0\xcf\x11\xe0"],  # OLE2 compound document
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04",  # ZIP-based OOXML
    ],
}


def _validate_document_magic(content: bytes, claimed_type: str) -> bool:
    """Verify file content matches claimed MIME type via magic byte inspection.

    Prevents Content-Type spoofing where an attacker declares a legitimate MIME
    type but uploads a malicious file (e.g., executable, HTML).
    """
    sigs = _DOCUMENT_MAGIC_SIGNATURES.get(claimed_type)
    if not sigs:
        return False
    for sig in sigs:
        if content[: len(sig)] == sig:
            return True
    return False


def _sanitize_filename(filename: str) -> str:
    """Remove path traversal sequences and special characters from filename.

    Strips directory separators and null bytes to prevent path traversal.
    Replaces non-alphanumeric characters (except dot, hyphen, underscore) with
    underscores. Returns 'document' if the result is empty.
    """
    # Strip any directory components (path traversal prevention)
    filename = filename.replace("\\", "/")
    filename = filename.split("/")[-1]
    # Remove null bytes
    filename = filename.replace("\x00", "")
    # Replace non-safe characters with underscore
    filename = re.sub(r"[^\w.\-]", "_", filename)
    # Collapse consecutive underscores
    filename = re.sub(r"_+", "_", filename)
    # Remove leading dots (prevents hidden files)
    filename = filename.lstrip(".")
    return filename or "document"


class StaffDocumentService:
    """Manages staff document uploads, downloads, and deletions via S3."""

    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_document(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_type: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        file_size: int,
        uploaded_by: UUID,
        school_id: Optional[UUID] = None,
        description: Optional[str] = None,
    ) -> StaffDocument:
        """Upload a document to S3 and create a DB record.

        Validates magic bytes to prevent Content-Type spoofing.
        Sanitizes filename to prevent path traversal.
        """
        # Defense-in-depth: verify staff exists and belongs to tenant
        staff = await self._get_staff_or_raise(tenant_id, staff_id)

        # Validate MIME type
        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise StaffServiceError(
                f"Unsupported file type: {mime_type}. Allowed: PDF, JPEG, PNG, DOC, DOCX",
                code="invalid_file_type",
            )

        # Validate file size
        if file_size > self.MAX_FILE_SIZE:
            raise StaffServiceError(
                f"File too large. Maximum size is 10MB, got {file_size / 1024 / 1024:.1f}MB",
                code="file_too_large",
            )

        if file_size == 0:
            raise StaffServiceError("File is empty", code="empty_file")

        # Verify actual content matches claimed MIME type
        if not _validate_document_magic(file_content, mime_type):
            raise StaffServiceError(
                "File content does not match declared type",
                code="magic_byte_mismatch",
            )

        # Validate document_type enum value
        try:
            doc_type_enum = StaffDocumentType(document_type)
        except ValueError:
            valid = ", ".join(e.value for e in StaffDocumentType)
            raise StaffServiceError(
                f"Invalid document type: {document_type}. Valid: {valid}",
                code="invalid_document_type",
            )

        # Sanitize filename before using in S3 key
        safe_filename = _sanitize_filename(filename)

        # Build S3 key: tenants/{tenant_id}/staff/{staff_id}/documents/{uuid}-{sanitized_filename}
        unique_id = uuid.uuid4().hex
        s3_key = (
            f"tenants/{tenant_id}/staff/{staff_id}/documents/{unique_id}-{safe_filename}"
        )

        # Upload to S3
        try:
            s3 = get_s3_service()
            s3.upload_file(
                file_content=file_content,
                key=s3_key,
                content_type=mime_type,
            )
        except Exception:
            logger.exception(
                "staff_document_upload.s3_failed",
                tenant_id=str(tenant_id),
                staff_id=str(staff_id),
            )
            raise StaffServiceError(
                "Failed to upload document. Please try again.",
                code="upload_failed",
            )

        # Create DB record
        document = StaffDocument(
            tenant_id=tenant_id,
            staff_id=staff_id,
            school_id=school_id,
            document_type=doc_type_enum,
            file_name=safe_filename,
            file_key=s3_key,
            file_size=file_size,
            mime_type=mime_type,
            description=description,
            uploaded_by=uploaded_by,
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def list_documents(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_type: Optional[str] = None,
    ) -> list[StaffDocument]:
        """List documents for a staff member (excluding soft-deleted)."""
        # Defense-in-depth: verify staff exists and belongs to tenant
        await self._get_staff_or_raise(tenant_id, staff_id)

        query = (
            select(StaffDocument)
            .where(StaffDocument.tenant_id == tenant_id)
            .where(StaffDocument.staff_id == staff_id)
            .where(StaffDocument.deleted_at.is_(None))
            .order_by(StaffDocument.created_at.desc())
        )

        if document_type is not None:
            try:
                doc_type_enum = StaffDocumentType(document_type)
            except ValueError:
                raise StaffServiceError(
                    f"Invalid document type filter: {document_type}",
                    code="invalid_document_type",
                )
            query = query.where(StaffDocument.document_type == doc_type_enum)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_download_url(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_id: UUID,
    ) -> str:
        """Generate presigned S3 URL for downloading a document (15-min expiry).

        IDOR check: verify document belongs to the staff member.
        """
        document = await self._get_document_or_raise(tenant_id, staff_id, document_id)

        try:
            s3 = get_s3_service()
            # 15-minute expiry for presigned download URLs
            url = s3.generate_presigned_url(document.file_key, expires_in=900)
        except Exception:
            logger.exception(
                "staff_document_download.presigned_url_failed",
                tenant_id=str(tenant_id),
                document_id=str(document_id),
            )
            raise StaffServiceError(
                "Failed to generate download URL. Please try again.",
                code="download_url_failed",
            )

        return url

    async def delete_document(
        self,
        tenant_id: UUID,
        staff_id: UUID,
        document_id: UUID,
    ) -> None:
        """Soft-delete a document. IDOR check: verify document belongs to staff."""
        document = await self._get_document_or_raise(tenant_id, staff_id, document_id)

        document.deleted_at = datetime.now(UTC)
        await self.db.flush()

    # =========================
    # Private Helpers
    # =========================

    async def _get_staff_or_raise(self, tenant_id: UUID, staff_id: UUID) -> Staff:
        """Fetch staff by ID with tenant scoping, raise if not found."""
        result = await self.db.execute(
            select(Staff)
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.id == staff_id)
            .where(Staff.deleted_at.is_(None))
        )
        staff = result.scalar_one_or_none()
        if not staff:
            raise StaffServiceError("Staff member not found", code="staff_not_found")
        return staff

    async def _get_document_or_raise(
        self, tenant_id: UUID, staff_id: UUID, document_id: UUID
    ) -> StaffDocument:
        """Fetch document with tenant + staff IDOR check."""
        result = await self.db.execute(
            select(StaffDocument)
            .where(StaffDocument.tenant_id == tenant_id)
            .where(StaffDocument.staff_id == staff_id)  # IDOR: belongs to staff
            .where(StaffDocument.id == document_id)
            .where(StaffDocument.deleted_at.is_(None))
        )
        document = result.scalar_one_or_none()
        if not document:
            raise StaffServiceError(
                "Document not found", code="document_not_found"
            )
        return document

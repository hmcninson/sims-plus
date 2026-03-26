"""
SIMS Plus - Student Document & Previous School Service

Mixin for document upload/download and previous school history management.
"""

import re
import uuid
from typing import Optional
from uuid import UUID

import nh3
import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import (
    Student,
    StudentDocument,
    StudentDocumentType,
    PreviousSchool,
)
from app.services.s3 import get_s3_service
from app.services.student._shared import StudentServiceError

logger = structlog.get_logger()

# F-11: Magic byte signatures for document types (extends image-only signatures
# in sanitize.py to cover PDFs and Word documents)
_DOCUMENT_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG"],
    "application/msword": [b"\xd0\xcf\x11\xe0"],  # OLE2 compound document
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04",  # ZIP-based OOXML
    ],
}

# Allowed MIME types for student document uploads
ALLOWED_DOCUMENT_TYPES = set(_DOCUMENT_MAGIC_SIGNATURES.keys())

# 10 MB maximum file size
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


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
    """F-27: Remove path traversal sequences and special characters from filename.

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


class StudentDocumentMixin:
    """Mixin for document upload/download and previous school history."""

    # Type hint for self.db -- set by StudentService.__init__
    db: AsyncSession

    # =========================
    # Document Methods
    # =========================

    async def upload_document(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        document_type: StudentDocumentType,
        title: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        file_size: int,
        uploaded_by: UUID,
        notes: Optional[str] = None,
    ) -> StudentDocument:
        """Upload a document to S3 and create a DB record.

        F-11: Validates magic bytes to prevent Content-Type spoofing.
        F-27: Sanitizes filename to prevent path traversal.
        """
        # Verify the student exists and belongs to this tenant (defense-in-depth)
        student = await self._get_student_or_raise(tenant_id, student_id)

        # Validate MIME type
        if mime_type not in ALLOWED_DOCUMENT_TYPES:
            raise StudentServiceError(
                f"Unsupported file type: {mime_type}. Allowed: PDF, JPEG, PNG, DOC, DOCX",
                code="invalid_file_type",
            )

        # Validate file size
        if file_size > MAX_DOCUMENT_SIZE:
            raise StudentServiceError(
                f"File too large. Maximum size is 10MB, got {file_size / 1024 / 1024:.1f}MB",
                code="file_too_large",
            )

        if file_size == 0:
            raise StudentServiceError("File is empty", code="empty_file")

        # F-11: Verify actual content matches claimed MIME type
        if not _validate_document_magic(file_content, mime_type):
            raise StudentServiceError(
                "File content does not match declared type",
                code="magic_byte_mismatch",
            )

        # F-27: Sanitize filename before using in S3 key
        safe_filename = _sanitize_filename(filename)

        # Build S3 key: {tenant_id}/students/{student_id}/documents/{uuid}_{sanitized_filename}
        unique_id = uuid.uuid4().hex
        s3_key = (
            f"{tenant_id}/students/{student_id}/documents/{unique_id}_{safe_filename}"
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
                "document_upload.s3_failed",
                tenant_id=str(tenant_id),
                student_id=str(student_id),
            )
            raise StudentServiceError(
                "Failed to upload document. Please try again.",
                code="upload_failed",
            )

        # Create DB record
        document = StudentDocument(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            document_type=document_type,
            title=title,
            file_url=s3_key,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=uploaded_by,
            notes=notes,
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def list_documents(
        self,
        tenant_id: UUID,
        student_id: UUID,
        document_type: Optional[StudentDocumentType] = None,
    ) -> dict:
        """List documents for a student (excluding soft-deleted).

        Returns dict with documents list, total count, and total size in bytes.
        """
        # Verify the student exists (defense-in-depth)
        await self._get_student_or_raise(tenant_id, student_id)

        query = (
            select(StudentDocument)
            .where(StudentDocument.tenant_id == tenant_id)
            .where(StudentDocument.student_id == student_id)
            .where(StudentDocument.deleted_at.is_(None))
            .order_by(StudentDocument.created_at.desc())
        )

        if document_type is not None:
            query = query.where(StudentDocument.document_type == document_type)

        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        total_size = sum(doc.file_size for doc in documents)

        return {
            "documents": documents,
            "total": len(documents),
            "total_size_bytes": total_size,
        }

    async def delete_document(
        self,
        tenant_id: UUID,
        student_id: UUID,
        document_id: UUID,
        deleted_by: UUID,
    ) -> bool:
        """Soft-delete a document. IDOR check: verify document belongs to student."""
        document = await self._get_document_or_raise(
            tenant_id, student_id, document_id
        )

        from datetime import datetime, UTC

        document.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def get_document_download_url(
        self,
        tenant_id: UUID,
        student_id: UUID,
        document_id: UUID,
    ) -> dict:
        """Generate presigned S3 URL for downloading a document.

        IDOR check: verify document belongs to student.
        Presigned URL expires in 15 minutes (900 seconds).
        """
        document = await self._get_document_or_raise(
            tenant_id, student_id, document_id
        )

        try:
            s3 = get_s3_service()
            url = s3.generate_presigned_url(document.file_url, expires_in=900)
        except Exception:
            logger.exception(
                "document_download.presigned_url_failed",
                tenant_id=str(tenant_id),
                document_id=str(document_id),
            )
            raise StudentServiceError(
                "Failed to generate download URL. Please try again.",
                code="download_url_failed",
            )

        return {"download_url": url, "expires_in": 900}

    async def _get_student_or_raise(
        self, tenant_id: UUID, student_id: UUID
    ) -> Student:
        """Fetch student by ID with tenant scoping, raise if not found."""
        result = await self.db.execute(
            select(Student)
            .where(Student.tenant_id == tenant_id)
            .where(Student.id == student_id)
            .where(Student.deleted_at.is_(None))
        )
        student = result.scalar_one_or_none()
        if not student:
            raise StudentServiceError("Student not found", code="student_not_found")
        return student

    async def _get_document_or_raise(
        self, tenant_id: UUID, student_id: UUID, document_id: UUID
    ) -> StudentDocument:
        """Fetch document with tenant + student IDOR check."""
        result = await self.db.execute(
            select(StudentDocument)
            .where(StudentDocument.tenant_id == tenant_id)
            .where(StudentDocument.student_id == student_id)  # IDOR: belongs to student
            .where(StudentDocument.id == document_id)
            .where(StudentDocument.deleted_at.is_(None))
        )
        document = result.scalar_one_or_none()
        if not document:
            raise StudentServiceError(
                "Document not found", code="document_not_found"
            )
        return document

    # =========================
    # Previous School Methods
    # =========================

    async def add_previous_school(
        self,
        tenant_id: UUID,
        student_id: UUID,
        school_id: UUID,
        school_name: str,
        school_address: Optional[str] = None,
        last_class: Optional[str] = None,
        years_attended: Optional[str] = None,
        transfer_reason: Optional[str] = None,
        leaving_certificate_ref: Optional[str] = None,
    ) -> PreviousSchool:
        """Create a previous school record for a student."""
        # Verify the student exists and belongs to this tenant
        await self._get_student_or_raise(tenant_id, student_id)

        record = PreviousSchool(
            tenant_id=tenant_id,
            student_id=student_id,
            school_id=school_id,
            school_name=school_name,
            school_address=school_address,
            last_class=last_class,
            years_attended=years_attended,
            transfer_reason=transfer_reason,
            leaving_certificate_ref=leaving_certificate_ref,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def list_previous_schools(
        self, tenant_id: UUID, student_id: UUID
    ) -> list[PreviousSchool]:
        """List previous schools for a student, ordered by created_at DESC."""
        # Verify the student exists
        await self._get_student_or_raise(tenant_id, student_id)

        result = await self.db.execute(
            select(PreviousSchool)
            .where(PreviousSchool.tenant_id == tenant_id)
            .where(PreviousSchool.student_id == student_id)
            .order_by(PreviousSchool.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_previous_school(
        self,
        tenant_id: UUID,
        student_id: UUID,
        record_id: UUID,
        **fields,
    ) -> PreviousSchool:
        """Update a previous school record. IDOR check: verify record belongs to student."""
        record = await self._get_previous_school_or_raise(
            tenant_id, student_id, record_id
        )

        for key, value in fields.items():
            if hasattr(record, key) and value is not None:
                setattr(record, key, value)

        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def delete_previous_school(
        self,
        tenant_id: UUID,
        student_id: UUID,
        record_id: UUID,
    ) -> bool:
        """Hard-delete a previous school record. IDOR check: verify belongs to student."""
        record = await self._get_previous_school_or_raise(
            tenant_id, student_id, record_id
        )

        await self.db.delete(record)
        await self.db.flush()
        return True

    async def _get_previous_school_or_raise(
        self, tenant_id: UUID, student_id: UUID, record_id: UUID
    ) -> PreviousSchool:
        """Fetch previous school record with tenant + student IDOR check."""
        result = await self.db.execute(
            select(PreviousSchool)
            .where(PreviousSchool.tenant_id == tenant_id)
            .where(PreviousSchool.student_id == student_id)  # IDOR: belongs to student
            .where(PreviousSchool.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise StudentServiceError(
                "Previous school record not found",
                code="previous_school_not_found",
            )
        return record

    # =========================
    # Structured Medical
    # =========================

    async def update_structured_medical(
        self,
        tenant_id: UUID,
        student_id: UUID,
        medical_data: dict,
    ) -> Student:
        """Update the structured_medical JSONB field on a student.

        F-13: Input is pre-validated by Pydantic schema (max_length, max_items).
        emergency_protocol is sanitized with nh3.clean() in the schema validator.
        Also syncs key fields to legacy text columns for backward compatibility.
        """
        student = await self._get_student_or_raise(tenant_id, student_id)

        student.structured_medical = medical_data

        # Sync to legacy text columns for backward compatibility
        conditions = medical_data.get("conditions", [])
        allergies = medical_data.get("allergies", [])
        blood_group = medical_data.get("blood_group")

        if conditions:
            student.medical_conditions = "; ".join(
                c["name"] for c in conditions if c.get("name")
            )
        if allergies:
            student.allergies = "; ".join(
                a["name"] for a in allergies if a.get("name")
            )
        if blood_group:
            student.blood_group = blood_group

        await self.db.flush()
        await self.db.refresh(student)
        return student

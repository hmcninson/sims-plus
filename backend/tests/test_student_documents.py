"""
Tests for student document management (Phase 3).

Covers: upload, MIME type validation, size limit, list, filter,
soft delete, IDOR prevention, presigned download URL.
Uses two-engine pattern (admin for seeding, app for RLS queries).
S3 is mocked for all tests.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import patch, MagicMock
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

# Valid PDF content (magic bytes match application/pdf)
PDF_MAGIC = b"%PDF-1.4 fake content here for testing"

# Valid PNG content (magic bytes match image/png)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n fake png content"


async def _seed_doc_prereqs(admin_session, tenant_id):
    """Seed school and student. Returns dict with IDs."""
    school_id = uuid4()
    student_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :stuid, 'Esi', 'Boateng', '2013-06-10', 'female', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
            "stuid": f"STU-{uuid4().hex[:8]}",
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "student_id": student_id,
        "user_id": user_id,
    }


def _mock_s3():
    """Create a mock S3 service."""
    mock = MagicMock()
    mock.upload_file.return_value = None
    mock.generate_presigned_url.return_value = "https://s3.example.com/presigned-url?token=abc"
    return mock


# --- Tests ---


@patch("app.services.student.document_service.get_s3_service")
async def test_upload_document(mock_get_s3, app_session, admin_session):
    """Upload a document creates a DB record with correct fields."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)
    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        document_type=StudentDocumentType.BIRTH_CERTIFICATE,
        title="Birth Certificate",
        file_content=PDF_MAGIC,
        filename="birth_cert.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
        notes="Original copy",
    )

    assert doc.id is not None
    assert doc.student_id == prereqs["student_id"]
    assert doc.title == "Birth Certificate"
    assert doc.document_type.value == "birth_certificate"
    assert doc.mime_type == "application/pdf"
    assert doc.file_size == len(PDF_MAGIC)
    assert doc.notes == "Original copy"
    assert doc.file_url is not None


@patch("app.services.student.document_service.get_s3_service")
async def test_upload_invalid_mime_type(mock_get_s3, app_session, admin_session):
    """Rejects disallowed MIME type."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            document_type=StudentDocumentType.OTHER,
            title="Evil file",
            file_content=b"#!/bin/bash rm -rf /",
            filename="malware.sh",
            mime_type="application/x-shellscript",
            file_size=20,
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "invalid_file_type"


@patch("app.services.student.document_service.get_s3_service")
async def test_upload_exceeds_size_limit(mock_get_s3, app_session, admin_session):
    """Rejects files exceeding 10MB limit."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)
    too_large = 11 * 1024 * 1024  # 11MB

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            document_type=StudentDocumentType.REPORT_CARD,
            title="Huge file",
            file_content=PDF_MAGIC,  # content doesn't matter, size is checked separately
            filename="huge.pdf",
            mime_type="application/pdf",
            file_size=too_large,
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "file_too_large"


@patch("app.services.student.document_service.get_s3_service")
async def test_upload_magic_byte_mismatch(mock_get_s3, app_session, admin_session):
    """Rejects file whose content doesn't match declared MIME type."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    # Claims PDF but content is PNG
    with pytest.raises(StudentServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            document_type=StudentDocumentType.OTHER,
            title="Mismatch",
            file_content=PNG_MAGIC,
            filename="fake.pdf",
            mime_type="application/pdf",
            file_size=len(PNG_MAGIC),
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "magic_byte_mismatch"


@patch("app.services.student.document_service.get_s3_service")
async def test_list_documents(mock_get_s3, app_session, admin_session):
    """List documents returns correct count and total_size_bytes."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    # Upload two documents
    for i, doc_type in enumerate([StudentDocumentType.BIRTH_CERTIFICATE, StudentDocumentType.PHOTO]):
        content = PDF_MAGIC if doc_type == StudentDocumentType.BIRTH_CERTIFICATE else PNG_MAGIC
        mime = "application/pdf" if doc_type == StudentDocumentType.BIRTH_CERTIFICATE else "image/png"
        await svc.upload_document(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            document_type=doc_type,
            title=f"Doc {i}",
            file_content=content,
            filename=f"doc_{i}.pdf",
            mime_type=mime,
            file_size=len(content),
            uploaded_by=prereqs["user_id"],
        )

    result = await svc.list_documents(tenant["id"], prereqs["student_id"])
    assert result["total"] == 2
    assert result["total_size_bytes"] == len(PDF_MAGIC) + len(PNG_MAGIC)
    assert len(result["documents"]) == 2


@patch("app.services.student.document_service.get_s3_service")
async def test_list_documents_by_type(mock_get_s3, app_session, admin_session):
    """Filter documents by document_type returns only matching records."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    # Upload one PDF and one PNG
    await svc.upload_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        document_type=StudentDocumentType.BIRTH_CERTIFICATE,
        title="BC",
        file_content=PDF_MAGIC,
        filename="bc.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )
    await svc.upload_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        document_type=StudentDocumentType.PHOTO,
        title="Photo",
        file_content=PNG_MAGIC,
        filename="photo.png",
        mime_type="image/png",
        file_size=len(PNG_MAGIC),
        uploaded_by=prereqs["user_id"],
    )

    # Filter for birth certificates only
    result = await svc.list_documents(
        tenant["id"], prereqs["student_id"],
        document_type=StudentDocumentType.BIRTH_CERTIFICATE,
    )
    assert result["total"] == 1
    assert result["documents"][0].document_type.value == "birth_certificate"


@patch("app.services.student.document_service.get_s3_service")
async def test_delete_document(mock_get_s3, app_session, admin_session):
    """Delete sets deleted_at (soft delete)."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        document_type=StudentDocumentType.OTHER,
        title="To delete",
        file_content=PDF_MAGIC,
        filename="delete_me.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )
    doc_id = doc.id

    result = await svc.delete_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        document_id=doc_id,
        deleted_by=prereqs["user_id"],
    )
    assert result is True

    # List should now return 0 documents
    listing = await svc.list_documents(tenant["id"], prereqs["student_id"])
    assert listing["total"] == 0


@patch("app.services.student.document_service.get_s3_service")
async def test_delete_document_idor(mock_get_s3, app_session, admin_session):
    """Delete rejects if document belongs to a different student."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])

    # Create a second student in the same tenant
    student2_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :stuid, 'Kofi', 'Adu', '2013-01-01', 'male', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student2_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "stuid": f"STU-{uuid4().hex[:8]}",
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    # Upload document for student 1
    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        document_type=StudentDocumentType.REPORT_CARD,
        title="Student 1 Report",
        file_content=PDF_MAGIC,
        filename="report.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )

    # Try to delete using student 2's ID -- should fail
    with pytest.raises(StudentServiceError) as exc_info:
        await svc.delete_document(
            tenant_id=tenant["id"],
            student_id=student2_id,
            document_id=doc.id,
            deleted_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "document_not_found"


@patch("app.services.student.document_service.get_s3_service")
async def test_download_url(mock_get_s3, app_session, admin_session):
    """Download URL returns presigned URL with expiry."""
    mock_s3 = _mock_s3()
    mock_get_s3.return_value = mock_s3

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        document_type=StudentDocumentType.ID_CARD,
        title="Student ID",
        file_content=PNG_MAGIC,
        filename="id_card.png",
        mime_type="image/png",
        file_size=len(PNG_MAGIC),
        uploaded_by=prereqs["user_id"],
    )

    result = await svc.get_document_download_url(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        document_id=doc.id,
    )

    assert "download_url" in result
    assert result["expires_in"] == 900
    assert "presigned-url" in result["download_url"]


@patch("app.services.student.document_service.get_s3_service")
async def test_upload_empty_file_rejected(mock_get_s3, app_session, admin_session):
    """Empty file (size 0) is rejected."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError
    from app.models.student import StudentDocumentType

    svc = StudentService(app_session)

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            document_type=StudentDocumentType.OTHER,
            title="Empty",
            file_content=b"",
            filename="empty.pdf",
            mime_type="application/pdf",
            file_size=0,
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "empty_file"

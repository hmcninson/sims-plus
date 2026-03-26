"""
Tests for staff document management (Phase 1).

Covers: upload, MIME type validation, size limit, magic bytes,
list, filter by type, download URL, soft delete, IDOR, tenant isolation.
Uses two-engine pattern (admin for seeding, app for RLS queries).
S3 is mocked for all tests.
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    clear_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Constants ---

# Valid PDF content (magic bytes match application/pdf)
PDF_MAGIC = b"%PDF-1.4 fake content here for testing"

# Valid JPEG content (magic bytes match image/jpeg)
JPEG_MAGIC = b"\xff\xd8\xff\xe0 fake jpeg content here"

# Valid PNG content (magic bytes match image/png)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n fake png content"


# --- Helpers ---


async def _seed_staff_doc_prereqs(admin_session, tenant_id):
    """Seed school, staff, and user. Returns dict with IDs."""
    school_id = uuid4()
    staff_db_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title,
                employment_date,
                created_at, updated_at)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, 'Kofi', 'Mensah',
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher',
                '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(staff_db_id), "tid": str(tenant_id), "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:8]}",
            "email": f"staff-{uuid4().hex[:8]}@test.com",
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
        "staff_id": staff_db_id,
        "user_id": user_id,
    }


def _mock_s3():
    """Create a mock S3 service."""
    mock = MagicMock()
    mock.upload_file.return_value = None
    mock.generate_presigned_url.return_value = "https://s3.example.com/presigned-url?token=abc"
    return mock


# --- Tests ---


@patch("app.services.staff.document_service.get_s3_service")
async def test_upload_staff_document_pdf(mock_get_s3, app_session, admin_session):
    """Upload a valid PDF creates a DB record with correct fields."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService

    svc = StaffDocumentService(app_session)
    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        document_type="contract",
        file_content=PDF_MAGIC,
        filename="employment_contract.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
        school_id=prereqs["school_id"],
        description="2024 employment contract",
    )

    assert doc.id is not None
    assert doc.staff_id == prereqs["staff_id"]
    assert doc.document_type.value == "contract"
    assert doc.mime_type == "application/pdf"
    assert doc.file_size == len(PDF_MAGIC)
    assert doc.description == "2024 employment contract"
    assert doc.file_key is not None
    assert "staff" in doc.file_key


@patch("app.services.staff.document_service.get_s3_service")
async def test_upload_staff_document_image(mock_get_s3, app_session, admin_session):
    """Upload a valid JPEG succeeds."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService

    svc = StaffDocumentService(app_session)
    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        document_type="id_document",
        file_content=JPEG_MAGIC,
        filename="ghana_card.jpg",
        mime_type="image/jpeg",
        file_size=len(JPEG_MAGIC),
        uploaded_by=prereqs["user_id"],
    )

    assert doc.id is not None
    assert doc.mime_type == "image/jpeg"


@patch("app.services.staff.document_service.get_s3_service")
async def test_upload_rejects_invalid_mime_type(mock_get_s3, app_session, admin_session):
    """Upload with disallowed MIME type raises invalid_file_type."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService, StaffServiceError

    svc = StaffDocumentService(app_session)

    with pytest.raises(StaffServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_id"],
            document_type="other",
            file_content=b"MZ\x90\x00",  # .exe header
            filename="malware.exe",
            mime_type="application/x-msdownload",
            file_size=4,
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "invalid_file_type"


@patch("app.services.staff.document_service.get_s3_service")
async def test_upload_rejects_oversized_file(mock_get_s3, app_session, admin_session):
    """Upload exceeding 10MB limit raises file_too_large."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService, StaffServiceError

    svc = StaffDocumentService(app_session)

    with pytest.raises(StaffServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_id"],
            document_type="certificate",
            file_content=PDF_MAGIC,
            filename="huge.pdf",
            mime_type="application/pdf",
            file_size=11 * 1024 * 1024,  # 11MB
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "file_too_large"


@patch("app.services.staff.document_service.get_s3_service")
async def test_upload_validates_magic_bytes(mock_get_s3, app_session, admin_session):
    """Upload where content doesn't match declared MIME type raises magic_byte_mismatch."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService, StaffServiceError

    svc = StaffDocumentService(app_session)

    # Claims PDF but content is actually PNG
    with pytest.raises(StaffServiceError) as exc_info:
        await svc.upload_document(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_id"],
            document_type="certificate",
            file_content=PNG_MAGIC,
            filename="fake_cert.pdf",
            mime_type="application/pdf",
            file_size=len(PNG_MAGIC),
            uploaded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "magic_byte_mismatch"


@patch("app.services.staff.document_service.get_s3_service")
async def test_list_staff_documents(mock_get_s3, app_session, admin_session):
    """Uploading 3 documents then listing returns all 3."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService

    svc = StaffDocumentService(app_session)

    for i, doc_type in enumerate(["contract", "certificate", "cv_resume"]):
        await svc.upload_document(
            tenant_id=tenant["id"],
            staff_id=prereqs["staff_id"],
            document_type=doc_type,
            file_content=PDF_MAGIC,
            filename=f"doc_{i}.pdf",
            mime_type="application/pdf",
            file_size=len(PDF_MAGIC),
            uploaded_by=prereqs["user_id"],
        )

    docs = await svc.list_documents(tenant["id"], prereqs["staff_id"])
    assert len(docs) == 3


@patch("app.services.staff.document_service.get_s3_service")
async def test_list_staff_documents_filter_by_type(mock_get_s3, app_session, admin_session):
    """Filtering by document_type returns only matching records."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService

    svc = StaffDocumentService(app_session)

    await svc.upload_document(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        document_type="contract",
        file_content=PDF_MAGIC,
        filename="contract.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )
    await svc.upload_document(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        document_type="certificate",
        file_content=PDF_MAGIC,
        filename="cert.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )

    docs = await svc.list_documents(tenant["id"], prereqs["staff_id"], document_type="contract")
    assert len(docs) == 1
    assert docs[0].document_type.value == "contract"


@patch("app.services.staff.document_service.get_s3_service")
async def test_get_document_download_url(mock_get_s3, app_session, admin_session):
    """Get download URL returns a presigned URL string."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService

    svc = StaffDocumentService(app_session)
    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        document_type="training",
        file_content=PDF_MAGIC,
        filename="training_cert.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )

    url = await svc.get_download_url(tenant["id"], prereqs["staff_id"], doc.id)
    assert "presigned-url" in url


@patch("app.services.staff.document_service.get_s3_service")
async def test_delete_staff_document(mock_get_s3, app_session, admin_session):
    """Soft-deleting a document removes it from list results."""
    mock_get_s3.return_value = _mock_s3()

    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_staff_doc_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.staff import StaffDocumentService

    svc = StaffDocumentService(app_session)
    doc = await svc.upload_document(
        tenant_id=tenant["id"],
        staff_id=prereqs["staff_id"],
        document_type="other",
        file_content=PDF_MAGIC,
        filename="to_delete.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs["user_id"],
    )
    doc_id = doc.id

    await svc.delete_document(tenant["id"], prereqs["staff_id"], doc_id)

    docs = await svc.list_documents(tenant["id"], prereqs["staff_id"])
    assert len(docs) == 0


@patch("app.services.staff.document_service.get_s3_service")
async def test_staff_documents_tenant_isolation(mock_get_s3, app_session, admin_session):
    """Tenant A's staff documents are invisible from Tenant B (RLS)."""
    mock_get_s3.return_value = _mock_s3()

    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs_a = await _seed_staff_doc_prereqs(admin_session, tenant_a["id"])
    prereqs_b = await _seed_staff_doc_prereqs(admin_session, tenant_b["id"])

    # Upload document as Tenant A
    await set_app_tenant_context(app_session, tenant_a["id"])
    from app.services.staff import StaffDocumentService

    svc_a = StaffDocumentService(app_session)
    doc = await svc_a.upload_document(
        tenant_id=tenant_a["id"],
        staff_id=prereqs_a["staff_id"],
        document_type="contract",
        file_content=PDF_MAGIC,
        filename="contract_a.pdf",
        mime_type="application/pdf",
        file_size=len(PDF_MAGIC),
        uploaded_by=prereqs_a["user_id"],
    )
    doc_id = doc.id

    # Switch to Tenant B and try to access
    await set_app_tenant_context(app_session, tenant_b["id"])
    svc_b = StaffDocumentService(app_session)

    # Tenant B should NOT be able to get the download URL for Tenant A's document
    from app.services.staff import StaffServiceError

    with pytest.raises(StaffServiceError) as exc_info:
        await svc_b.get_download_url(
            tenant_b["id"], prereqs_a["staff_id"], doc_id,
        )
    # Under Tenant B's RLS context, the document is invisible,
    # so either staff_not_found or document_not_found is acceptable
    assert exc_info.value.code in ("staff_not_found", "document_not_found")

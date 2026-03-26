"""
SIMS Plus - Staff Document Endpoints

Upload, list, download, and delete staff documents (contracts, certificates, etc.).
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.staff import StaffDocumentResponse
from app.services.staff import StaffDocumentService, StaffServiceError

router = APIRouter()


@router.post(
    "/{staff_id}/documents",
    response_model=StaffDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload staff document",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def upload_document(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    file: UploadFile = File(..., description="Document file (PDF, JPEG, PNG, DOC, DOCX)"),
    document_type: str = Form(..., description="Document type (contract, certificate, cv_resume, id_document, reference_letter, disciplinary, training, medical, other)"),
    description: Optional[str] = Form(None, description="Optional document description"),
) -> StaffDocumentResponse:
    """Upload a document for a staff member.

    Validates file type via magic bytes and MIME type. Maximum file size is 10MB.
    """
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    filename = file.filename or "document"
    mime_type = file.content_type or "application/octet-stream"

    service = StaffDocumentService(db)
    try:
        document = await service.upload_document(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            document_type=document_type,
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            uploaded_by=UUID(current_user["user_id"]),
            school_id=UUID(current_user["school_id"]) if current_user.get("school_id") else None,
            description=description,
        )
    except StaffServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    # Generate a presigned download URL for the response
    try:
        download_url = await service.get_download_url(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            document_id=document.id,
        )
    except StaffServiceError:
        download_url = ""

    return StaffDocumentResponse(
        id=document.id,
        staff_id=document.staff_id,
        document_type=document.document_type.value if hasattr(document.document_type, "value") else document.document_type,
        file_name=document.file_name,
        file_size=document.file_size,
        mime_type=document.mime_type,
        description=document.description,
        download_url=download_url,
        uploaded_by=document.uploaded_by,
        created_at=document.created_at,
    )


@router.get(
    "/{staff_id}/documents",
    response_model=list[StaffDocumentResponse],
    summary="List staff documents",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def list_documents(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    document_type: Optional[str] = Query(None, description="Filter by document type"),
) -> list[StaffDocumentResponse]:
    """List all documents for a staff member."""
    service = StaffDocumentService(db)
    try:
        documents = await service.list_documents(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            document_type=document_type,
        )
    except StaffServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
            if e.code != "staff_not_found"
            else status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )

    result = []
    for doc in documents:
        # Generate presigned download URL for each document
        try:
            download_url = await service.get_download_url(
                tenant_id=tenant.tenant_id,
                staff_id=staff_id,
                document_id=doc.id,
            )
        except StaffServiceError:
            download_url = ""

        result.append(
            StaffDocumentResponse(
                id=doc.id,
                staff_id=doc.staff_id,
                document_type=doc.document_type.value if hasattr(doc.document_type, "value") else doc.document_type,
                file_name=doc.file_name,
                file_size=doc.file_size,
                mime_type=doc.mime_type,
                description=doc.description,
                download_url=download_url,
                uploaded_by=doc.uploaded_by,
                created_at=doc.created_at,
            )
        )

    return result


@router.get(
    "/{staff_id}/documents/{document_id}",
    response_model=dict,
    summary="Get document download URL",
    dependencies=[Depends(require_permissions("staff.read"))],
)
async def get_document_download_url(
    staff_id: UUID,
    document_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> dict:
    """Get a presigned download URL for a staff document (15-minute expiry)."""
    service = StaffDocumentService(db)
    try:
        url = await service.get_download_url(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            document_id=document_id,
        )
    except StaffServiceError as e:
        code = status.HTTP_404_NOT_FOUND if e.code in ("staff_not_found", "document_not_found") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.message)

    return {"download_url": url, "expires_in": 900}


@router.delete(
    "/{staff_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete staff document",
    dependencies=[Depends(require_permissions("staff.delete"))],
)
async def delete_document(
    staff_id: UUID,
    document_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft-delete a staff document."""
    service = StaffDocumentService(db)
    try:
        await service.delete_document(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            document_id=document_id,
        )
    except StaffServiceError as e:
        code = status.HTTP_404_NOT_FOUND if e.code in ("staff_not_found", "document_not_found") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=e.message)

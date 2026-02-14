"""
SIMS Plus - Media Upload API Endpoints

API endpoints for file uploads (logos, avatars, documents, etc.)
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUserId, RequestTenant, require_permissions
from app.schemas.media import FileUploadResponse
from app.services.s3 import S3Service, get_s3_service

router = APIRouter()

# Allowed MIME types for image uploads
ALLOWED_IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}

# Allowed types for logos (no GIF)
ALLOWED_LOGO_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

# Max file size: 2MB
MAX_IMAGE_SIZE = 2 * 1024 * 1024


@router.post(
    "/upload/logo",
    response_model=FileUploadResponse,
    summary="Upload school logo",
    description="Upload a logo image for the school. Supports PNG, JPEG, and WEBP formats. Max 2MB.",
    dependencies=[Depends(require_permissions("school.update"))],
)
async def upload_logo(
    tenant: RequestTenant,
    file: UploadFile = File(..., description="Logo image file (PNG, JPEG, or WEBP)"),
    s3: S3Service = Depends(get_s3_service),
) -> FileUploadResponse:
    """Upload a school logo to S3."""

    # Validate file type
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPEG, WEBP. Got: {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 2MB. Got: {len(content) / 1024 / 1024:.2f}MB",
        )

    # Validate file is not empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Generate unique key
    key = s3.generate_unique_key(
        folder="logos",
        tenant_id=str(tenant.tenant_id),
        original_filename=file.filename or "logo.png",
    )

    # Upload to S3
    try:
        url = s3.upload_file(
            file_content=content,
            key=key,
            content_type=file.content_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    return FileUploadResponse(
        url=url,
        key=key,
        filename=file.filename or "logo",
        content_type=file.content_type,
        size=len(content),
    )


@router.post(
    "/upload/student-photo/{student_id}",
    response_model=FileUploadResponse,
    summary="Upload student photo",
    description="Upload a photo for a student. Supports PNG, JPEG, WEBP formats. Max 2MB.",
    dependencies=[Depends(require_permissions("students.update"))],
)
async def upload_student_photo(
    student_id: str,
    tenant: RequestTenant,
    file: UploadFile = File(..., description="Student photo (PNG, JPEG, or WEBP)"),
    s3: S3Service = Depends(get_s3_service),
) -> FileUploadResponse:
    """Upload a student photo to S3."""

    # Validate file type
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPEG, WEBP. Got: {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 2MB. Got: {len(content) / 1024 / 1024:.2f}MB",
        )

    # Validate file is not empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Generate unique key using student_id for organization
    key = s3.generate_unique_key(
        folder="students",
        tenant_id=str(tenant.tenant_id),
        original_filename=f"{student_id}.{file.filename or 'photo.png'}",
    )

    # Upload to S3
    try:
        url = s3.upload_file(
            file_content=content,
            key=key,
            content_type=file.content_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    return FileUploadResponse(
        url=url,
        key=key,
        filename=file.filename or "photo",
        content_type=file.content_type,
        size=len(content),
    )


@router.post(
    "/upload/staff-photo/{staff_id}",
    response_model=FileUploadResponse,
    summary="Upload staff photo",
    description="Upload a photo for a staff member. Supports PNG, JPEG, WEBP formats. Max 2MB.",
    dependencies=[Depends(require_permissions("staff.update"))],
)
async def upload_staff_photo(
    staff_id: str,
    tenant: RequestTenant,
    file: UploadFile = File(..., description="Staff photo (PNG, JPEG, or WEBP)"),
    s3: S3Service = Depends(get_s3_service),
) -> FileUploadResponse:
    """Upload a staff photo to S3."""

    # Validate file type
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPEG, WEBP. Got: {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 2MB. Got: {len(content) / 1024 / 1024:.2f}MB",
        )

    # Validate file is not empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Generate unique key using staff_id for organization
    key = s3.generate_unique_key(
        folder="staff",
        tenant_id=str(tenant.tenant_id),
        original_filename=f"{staff_id}.{file.filename or 'photo.png'}",
    )

    # Upload to S3
    try:
        url = s3.upload_file(
            file_content=content,
            key=key,
            content_type=file.content_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    return FileUploadResponse(
        url=url,
        key=key,
        filename=file.filename or "photo",
        content_type=file.content_type,
        size=len(content),
    )


@router.post(
    "/upload/avatar",
    response_model=FileUploadResponse,
    summary="Upload user avatar",
    description="Upload an avatar/profile image for the current user. Supports PNG, JPEG, WEBP, and GIF formats. Max 2MB.",
)
async def upload_avatar(
    tenant: RequestTenant,
    current_user_id: CurrentUserId,
    file: UploadFile = File(..., description="Avatar image file (PNG, JPEG, WEBP, or GIF)"),
    s3: S3Service = Depends(get_s3_service),
) -> FileUploadResponse:
    """Upload a user avatar to S3."""

    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPEG, WEBP, GIF. Got: {file.content_type}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 2MB. Got: {len(content) / 1024 / 1024:.2f}MB",
        )

    # Validate file is not empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Generate unique key using user_id for organization
    key = s3.generate_unique_key(
        folder="avatars",
        tenant_id=str(current_user_id),
        original_filename=file.filename or "avatar.png",
    )

    # Upload to S3
    try:
        url = s3.upload_file(
            file_content=content,
            key=key,
            content_type=file.content_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    return FileUploadResponse(
        url=url,
        key=key,
        filename=file.filename or "avatar",
        content_type=file.content_type,
        size=len(content),
    )

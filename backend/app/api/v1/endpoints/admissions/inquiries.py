"""
SIMS Plus - Inquiry Management Endpoints (Enrollment Gap Closure Phase 1)

Admin endpoints for managing inquiries/leads in the admissions pipeline.
All endpoints require JWT authentication and admissions permissions.
"""

import math
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.inquiry import (
    BulkImportRequest,
    BulkImportResponse,
    CommunicationCreate,
    CommunicationResponse,
    DuplicateCheckResponse,
    FollowUpCreate,
    FollowUpResponse,
    InquiryAssign,
    InquiryConvert,
    InquiryCreate,
    InquiryListResponse,
    InquiryResponse,
    InquiryStatsResponse,
    InquiryStatusUpdate,
    InquiryUpdate,
)
from app.services.admissions import InquiryService, InquiryServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/inquiries")


def _handle_error(e: InquiryServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_TRANSITION": 422,
        "INVALID_STATUS": 422,
        "ALREADY_CONVERTED": 409,
        "ALREADY_COMPLETED": 409,
        "USER_NOT_FOUND": 404,
        "PERIOD_NOT_FOUND": 404,
        "PERIOD_NOT_OPEN": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


# ------------------------------------------------------------------
# List-level endpoints (must be declared before /{id} to avoid conflicts)
# ------------------------------------------------------------------


@router.get(
    "",
    response_model=InquiryListResponse,
    summary="List inquiries",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_inquiries(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    source: str | None = Query(None),
    assigned_to: UUID | None = Query(None),
    search: str | None = Query(None, max_length=100),
) -> InquiryListResponse:
    """
    List inquiries with filtering, search, and pagination.

    Search matches against first_name, last_name, guardian_name,
    and guardian_phone.
    """
    service = InquiryService(db)
    items, total = await service.list_inquiries(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        status=status_filter,
        source=source,
        assigned_to=assigned_to,
        search=search,
        page=page,
        page_size=page_size,
    )
    return InquiryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/stats",
    response_model=InquiryStatsResponse,
    summary="Get inquiry statistics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_inquiry_stats(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryStatsResponse:
    """Get inquiry pipeline statistics for the current school."""
    service = InquiryService(db)
    stats = await service.get_stats(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
    )
    return InquiryStatsResponse(**stats)


@router.get(
    "/check-duplicate",
    response_model=DuplicateCheckResponse,
    summary="Check for duplicate inquiries",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def check_duplicate(
    user: ValidatedUser,
    db: DatabaseSession,
    phone: str | None = Query(None, max_length=20),
    email: str | None = Query(None, max_length=255),
) -> DuplicateCheckResponse:
    """
    Check if an inquiry with the same guardian phone or email already exists.

    Advisory only -- does not block creation. Returns matching inquiries
    for the user to review before creating a potential duplicate.
    """
    if not phone and not email:
        return DuplicateCheckResponse(has_duplicates=False, matches=[])

    service = InquiryService(db)
    matches = await service.check_duplicate(
        tenant_id=UUID(user["tenant_id"]),
        phone=phone,
        email=email,
    )
    return DuplicateCheckResponse(
        has_duplicates=len(matches) > 0,
        matches=matches,
    )


@router.get(
    "/follow-ups/pending",
    response_model=list[FollowUpResponse],
    summary="List my pending follow-ups",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_pending_follow_ups(
    user: ValidatedUser,
    db: DatabaseSession,
    mine_only: bool = Query(True, description="If true, only show follow-ups assigned to current user"),
) -> list[FollowUpResponse]:
    """
    List pending (incomplete) follow-up tasks.

    By default returns only follow-ups assigned to the current user.
    Set mine_only=false to see all pending follow-ups in the tenant.
    """
    service = InquiryService(db)
    user_id = UUID(user["user_id"]) if mine_only else None
    follow_ups = await service.list_pending_follow_ups(
        tenant_id=UUID(user["tenant_id"]),
        user_id=user_id,
    )
    return follow_ups


# ------------------------------------------------------------------
# Single inquiry CRUD
# ------------------------------------------------------------------


@router.post(
    "",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create inquiry",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def create_inquiry(
    data: InquiryCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryResponse:
    """Create a new inquiry/lead for a prospective student."""
    service = InquiryService(db)
    inquiry = await service.create(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        data=data,
    )
    return inquiry


@router.get(
    "/{inquiry_id}",
    response_model=InquiryResponse,
    summary="Get inquiry detail",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_inquiry(
    inquiry_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryResponse:
    """Get full inquiry detail including communications and follow-ups."""
    service = InquiryService(db)
    try:
        return await service.get(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{inquiry_id}",
    response_model=InquiryResponse,
    summary="Update inquiry",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def update_inquiry(
    inquiry_id: UUID,
    data: InquiryUpdate,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryResponse:
    """Update inquiry details (non-status fields)."""
    service = InquiryService(db)
    try:
        return await service.update(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
            data=data,
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{inquiry_id}/status",
    response_model=InquiryResponse,
    summary="Update inquiry status",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def update_inquiry_status(
    inquiry_id: UUID,
    data: InquiryStatusUpdate,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryResponse:
    """
    Transition inquiry status through the lead pipeline.

    Valid transitions are enforced by the state machine:
    new -> contacted, interested, lost
    contacted -> interested, lost
    interested -> applied, lost
    applied -> enrolled (terminal)
    lost -> new, contacted (re-engagement)
    """
    service = InquiryService(db)
    try:
        return await service.update_status(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
            new_status=data.status.value,
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{inquiry_id}/assign",
    response_model=InquiryResponse,
    summary="Assign inquiry to staff",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def assign_inquiry(
    inquiry_id: UUID,
    data: InquiryAssign,
    user: ValidatedUser,
    db: DatabaseSession,
) -> InquiryResponse:
    """Assign an inquiry to a staff member for follow-up."""
    service = InquiryService(db)
    try:
        return await service.assign(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
            assigned_to=data.assigned_to,
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{inquiry_id}/convert",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Convert inquiry to application",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def convert_to_application(
    inquiry_id: UUID,
    data: InquiryConvert,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> dict:
    """
    Convert an inquiry into a formal application.

    Creates a new Application record with the inquiry's student and
    guardian data, linking the inquiry to the resulting application.
    The inquiry status is automatically set to 'applied'.
    """
    service = InquiryService(db)
    try:
        application = await service.convert_to_application(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=data.period_id,
        )
        return {
            "application_id": str(application.id),
            "tracking_code": application.tracking_code,
            "message": "Inquiry successfully converted to application",
        }
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.delete(
    "/{inquiry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete inquiry",
    dependencies=[Depends(require_permissions("admissions.delete"))],
)
async def delete_inquiry(
    inquiry_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> None:
    """Soft-delete an inquiry."""
    service = InquiryService(db)
    try:
        await service.delete(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


# ------------------------------------------------------------------
# Communications sub-resource
# ------------------------------------------------------------------


@router.post(
    "/{inquiry_id}/communications",
    response_model=CommunicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log communication",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def add_communication(
    inquiry_id: UUID,
    data: CommunicationCreate,
    user: ValidatedUser,
    db: DatabaseSession,
) -> CommunicationResponse:
    """
    Log a communication (SMS, email, phone call, or in-person visit)
    related to this inquiry.

    If the communication is outbound and the inquiry status is 'new',
    the status is automatically transitioned to 'contacted'.
    """
    service = InquiryService(db)
    try:
        return await service.add_communication(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
            user_id=UUID(user["user_id"]),
            data=data,
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.get(
    "/{inquiry_id}/communications",
    response_model=list[CommunicationResponse],
    summary="List communications",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_communications(
    inquiry_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[CommunicationResponse]:
    """List all communication log entries for an inquiry."""
    service = InquiryService(db)
    try:
        return await service.list_communications(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


# ------------------------------------------------------------------
# Follow-ups sub-resource
# ------------------------------------------------------------------


@router.post(
    "/{inquiry_id}/follow-ups",
    response_model=FollowUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create follow-up task",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def create_follow_up(
    inquiry_id: UUID,
    data: FollowUpCreate,
    user: ValidatedUser,
    db: DatabaseSession,
) -> FollowUpResponse:
    """Create a follow-up task assigned to a staff member."""
    service = InquiryService(db)
    try:
        return await service.create_follow_up(
            inquiry_id=inquiry_id,
            tenant_id=UUID(user["tenant_id"]),
            data=data,
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/follow-ups/{follow_up_id}/complete",
    response_model=FollowUpResponse,
    summary="Complete follow-up task",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def complete_follow_up(
    follow_up_id: UUID,
    user: ValidatedUser,
    db: DatabaseSession,
) -> FollowUpResponse:
    """Mark a follow-up task as completed."""
    service = InquiryService(db)
    try:
        return await service.complete_follow_up(
            follow_up_id=follow_up_id,
            tenant_id=UUID(user["tenant_id"]),
        )
    except InquiryServiceError as e:
        raise _handle_error(e)


# ------------------------------------------------------------------
# Bulk import
# ------------------------------------------------------------------


@router.post(
    "/bulk-import",
    response_model=BulkImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import inquiries",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def bulk_import(
    data: BulkImportRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkImportResponse:
    """
    Bulk import inquiries from a list of rows (max 200).

    Deduplicates by guardian_phone within the tenant.
    Returns counts of imported, skipped, and errored rows.
    """
    service = InquiryService(db)
    result = await service.bulk_import(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        rows=data.rows,
    )
    return BulkImportResponse(**result)

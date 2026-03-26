"""
SIMS Plus - Return Intent Survey Endpoints

Optional intent-to-return survey for boarding/private schools.
Results are advisory only -- does NOT block promotion or enrollment.
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
from app.schemas.admissions import (
    ReturnIntentCampaignCreate,
    ReturnIntentCampaignListResponse,
    ReturnIntentCampaignResponse,
    ReturnIntentRespondRequest,
    ReturnIntentResponse,
)
from app.schemas.enrollment_analytics import ReEnrollmentSummaryResponse
from app.services.admissions import ReturnIntentError, ReturnIntentService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/return-intents")


def _handle_error(e: ReturnIntentError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INTENT_NOT_FOUND": 404,
        "YEAR_NOT_FOUND": 404,
        "SCHOOL_NOT_FOUND": 404,
        "CAMPAIGN_NOT_DRAFT": 409,
        "CAMPAIGN_ALREADY_SENT": 409,
        "CAMPAIGN_NOT_SENT": 409,
        "ALREADY_CONFIRMED": 409,
        "NO_TARGET_CLASSES": 422,
        "NO_STUDENTS": 422,
        "INVALID_INTENT": 422,
        "INVALID_INTENT_STATE": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "/campaigns",
    response_model=ReturnIntentCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create return intent campaign",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def create_campaign(
    data: ReturnIntentCampaignCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentCampaignResponse:
    """Create a return intent survey campaign for existing students."""
    service = ReturnIntentService(db)
    try:
        # Unpack Pydantic model fields into individual kwargs
        # target_classes needs to be list[str] for the service
        target_classes = [str(c) for c in data.target_classes]
        return await service.create_campaign(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            academic_year_id=data.academic_year_id,
            name=data.name,
            target_classes=target_classes,
            message_template=data.message_template,
            deadline=data.deadline,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.get(
    "/campaigns",
    response_model=ReturnIntentCampaignListResponse,
    summary="List return intent campaigns",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_campaigns(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReturnIntentCampaignListResponse:
    """List return intent campaigns with stats."""
    service = ReturnIntentService(db)
    # list_campaigns returns (items, total) tuple
    items, total = await service.list_campaigns(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        page=page,
        page_size=page_size,
    )
    return ReturnIntentCampaignListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/campaigns/{campaign_id}",
    response_model=ReturnIntentCampaignResponse,
    summary="Get campaign details",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_campaign(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentCampaignResponse:
    """Get campaign details with response breakdown."""
    service = ReturnIntentService(db)
    try:
        return await service.get_campaign(
            tenant_id=UUID(user["tenant_id"]),
            campaign_id=campaign_id,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.get(
    "/campaigns/{campaign_id}/intents",
    response_model=list[ReturnIntentResponse],
    summary="Get campaign intent list",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_campaign_intents(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    intent_filter: str | None = Query(None, alias="intent"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> list[ReturnIntentResponse]:
    """Get list of students with their intent status."""
    service = ReturnIntentService(db)
    try:
        # list_intents returns (items, total) tuple
        items, total = await service.list_intents(
            tenant_id=UUID(user["tenant_id"]),
            campaign_id=campaign_id,
            intent_filter=intent_filter,
            page=page,
            page_size=page_size,
        )
        return items
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.put(
    "/{intent_id}/respond",
    response_model=ReturnIntentResponse,
    summary="Respond to return intent survey",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def respond_to_intent(
    intent_id: UUID,
    data: ReturnIntentRespondRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentResponse:
    """
    Record a parent's response to the return intent survey.

    Allows re-response (parent can change their mind before deadline).
    intent must be one of: returning, not_returning, undecided.
    """
    service = ReturnIntentService(db)
    try:
        return await service.respond(
            tenant_id=UUID(user["tenant_id"]),
            intent_id=intent_id,
            intent=data.intent,
            responded_by=UUID(user["user_id"]),
            reason=data.reason,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.post(
    "/campaigns/{campaign_id}/send",
    response_model=ReturnIntentCampaignResponse,
    summary="Send return intent survey",
    dependencies=[Depends(require_permissions("admissions.manage"))],
)
async def send_campaign(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentCampaignResponse:
    """
    Send SMS/email survey to parents of students in the campaign.
    Creates ReturnIntent records for all active students in target classes.
    Campaign status changes from 'draft' to 'sent'.
    """
    service = ReturnIntentService(db)
    try:
        # send_campaign returns int (count), but we need the campaign object
        await service.send_campaign(
            tenant_id=UUID(user["tenant_id"]),
            campaign_id=campaign_id,
        )
        # Fetch the updated campaign to return its current state
        return await service.get_campaign(
            tenant_id=UUID(user["tenant_id"]),
            campaign_id=campaign_id,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.post(
    "/{intent_id}/confirm",
    response_model=ReturnIntentResponse,
    summary="Confirm re-enrollment",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def confirm_re_enrollment(
    intent_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReturnIntentResponse:
    """
    Confirm re-enrollment for a returning student.
    Checks outstanding fees and records confirmation timestamp.
    """
    service = ReturnIntentService(db)
    try:
        return await service.confirm_re_enrollment(
            tenant_id=UUID(user["tenant_id"]),
            intent_id=intent_id,
            user_id=UUID(user["user_id"]),
        )
    except ReturnIntentError as e:
        raise _handle_error(e)


@router.get(
    "/campaigns/{campaign_id}/summary",
    response_model=ReEnrollmentSummaryResponse,
    summary="Re-enrollment summary",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_re_enrollment_summary(
    campaign_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> ReEnrollmentSummaryResponse:
    """
    Get re-enrollment confirmation summary for a campaign.
    Shows confirmed/pending/not-returning counts, outstanding fees, and class breakdown.
    """
    service = ReturnIntentService(db)
    try:
        return await service.get_re_enrollment_summary(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            campaign_id=campaign_id,
        )
    except ReturnIntentError as e:
        raise _handle_error(e)

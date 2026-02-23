"""
SIMS Plus - SMS Messaging Endpoints

Send single/bulk SMS, view history, and get delivery statistics.

Permissions:
  - communications.send  for POST endpoints
  - communications.read  for GET endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.models.sms import SMSStatus
from app.schemas.messaging import (
    RecipientType,
    SMSBulkRequest,
    SMSHistoryResponse,
    SMSLogResponse,
    SMSSendRequest,
    SMSStatsResponse,
)
from app.services.messaging.recipient_resolver import (
    RecipientResolver,
    RecipientResolverError,
)
from app.services.sms import SMSService, SMSError

router = APIRouter(prefix="/sms", tags=["SMS"])


@router.post(
    "/send",
    response_model=list[SMSLogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Send SMS to specific phone numbers",
    dependencies=[Depends(require_permissions("communications.send"))],
)
async def send_sms(
    data: SMSSendRequest,
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> list[SMSLogResponse]:
    """
    Send an SMS to one or more phone numbers.

    Limited to 100 recipients per request. For larger audiences use
    the /bulk endpoint with an audience segment.
    """
    service = SMSService(db)
    logs = []

    for phone in data.recipient_phones:
        log = await service.send_sms(
            tenant_id=school.tenant_id,
            recipient_phone=phone,
            message=data.message,
        )
        logs.append(log)

    return [SMSLogResponse.model_validate(log) for log in logs]


@router.post(
    "/bulk",
    response_model=list[SMSLogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Send SMS to an audience segment",
    dependencies=[Depends(require_permissions("communications.send"))],
)
async def send_bulk_sms(
    data: SMSBulkRequest,
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> list[SMSLogResponse]:
    """
    Resolve an audience (all_parents, all_staff, class_parents) and
    send the message to every resolved recipient that has a phone number.
    """
    if data.audience == RecipientType.CLASS_PARENTS and not data.class_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="class_id is required when audience is class_parents",
        )

    if data.audience == RecipientType.SPECIFIC:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use /sms/send for specific recipients",
        )

    resolver = RecipientResolver(db)
    try:
        recipients = await resolver.resolve(
            tenant_id=school.tenant_id,
            audience=data.audience.value,
            school_id=school.school_id,
            class_id=data.class_id,
        )
    except RecipientResolverError as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    # Filter to recipients that have a phone number
    phone_recipients = [r for r in recipients if r.get("phone")]
    if not phone_recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No recipients with phone numbers found for this audience",
        )

    # Limit bulk sends to prevent request timeouts (async Celery for larger batches later)
    MAX_BULK_RECIPIENTS = 200
    if len(phone_recipients) > MAX_BULK_RECIPIENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Too many recipients ({len(phone_recipients)}). Maximum is {MAX_BULK_RECIPIENTS}.",
        )

    sms_service = SMSService(db)
    logs = await sms_service.send_bulk(
        tenant_id=school.tenant_id,
        recipients=phone_recipients,
        message=data.message,
    )

    return [SMSLogResponse.model_validate(log) for log in logs]


@router.get(
    "/history",
    response_model=SMSHistoryResponse,
    summary="SMS sending history",
    dependencies=[Depends(require_permissions("communications.read"))],
)
async def get_sms_history(
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sms_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
) -> SMSHistoryResponse:
    """Return paginated SMS log for the current tenant."""
    status_filter = None
    if sms_status:
        try:
            status_filter = SMSStatus(sms_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status value: {sms_status}",
            )

    service = SMSService(db)
    result = await service.get_sms_log(
        tenant_id=school.tenant_id,
        page=page,
        page_size=page_size,
        status=status_filter,
    )

    return SMSHistoryResponse(
        items=[SMSLogResponse.model_validate(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get(
    "/stats",
    response_model=SMSStatsResponse,
    summary="SMS delivery statistics",
    dependencies=[Depends(require_permissions("communications.read"))],
)
async def get_sms_stats(
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> SMSStatsResponse:
    """Return aggregate SMS delivery statistics for the tenant."""
    service = SMSService(db)
    stats = await service.get_stats(tenant_id=school.tenant_id)
    return SMSStatsResponse(**stats)

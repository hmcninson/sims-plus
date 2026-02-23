"""
SIMS Plus - Email Messaging Endpoints

Send single/bulk email, view history, and get delivery statistics.

Permissions:
  - communications.send  for POST endpoints
  - communications.read  for GET endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.models.email_log import EmailLog, EmailStatus
from app.schemas.messaging import (
    EmailBulkRequest,
    EmailHistoryResponse,
    EmailLogResponse,
    EmailSendRequest,
    EmailStatsResponse,
    RecipientType,
)
from app.services.messaging.email_compose import EmailComposeService
from app.services.messaging.recipient_resolver import (
    RecipientResolver,
    RecipientResolverError,
)

router = APIRouter(prefix="/email", tags=["Email"])


@router.post(
    "/send",
    response_model=list[EmailLogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Send email to specific addresses",
    dependencies=[Depends(require_permissions("communications.send"))],
)
async def send_email(
    data: EmailSendRequest,
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> list[EmailLogResponse]:
    """
    Send an email to one or more addresses.

    Limited to 100 recipients per request. For larger audiences use
    the /bulk endpoint with an audience segment.
    """
    service = EmailComposeService(db)
    logs = []

    names = data.recipient_names or [None] * len(data.recipient_emails)
    # Pad names list if shorter than emails
    while len(names) < len(data.recipient_emails):
        names.append(None)

    for email_addr, name in zip(data.recipient_emails, names):
        log = await service.send_email(
            tenant_id=school.tenant_id,
            school_id=school.school_id,
            recipient_email=email_addr,
            recipient_name=name,
            subject=data.subject,
            body=data.body,
            sent_by=UUID(user["user_id"]),
        )
        logs.append(log)

    return [EmailLogResponse.model_validate(log) for log in logs]


@router.post(
    "/bulk",
    response_model=list[EmailLogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Send email to an audience segment",
    dependencies=[Depends(require_permissions("communications.send"))],
)
async def send_bulk_email(
    data: EmailBulkRequest,
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> list[EmailLogResponse]:
    """
    Resolve an audience (all_parents, all_staff, class_parents) and
    send the email to every resolved recipient that has an email address.
    """
    if data.audience == RecipientType.CLASS_PARENTS and not data.class_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="class_id is required when audience is class_parents",
        )

    if data.audience == RecipientType.SPECIFIC:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use /email/send for specific recipients",
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

    # Filter to recipients that have an email address
    email_recipients = [r for r in recipients if r.get("email")]
    if not email_recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No recipients with email addresses found for this audience",
        )

    # Limit bulk sends to prevent request timeouts (async Celery for larger batches later)
    MAX_BULK_RECIPIENTS = 200
    if len(email_recipients) > MAX_BULK_RECIPIENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Too many recipients ({len(email_recipients)}). Maximum is {MAX_BULK_RECIPIENTS}.",
        )

    compose_service = EmailComposeService(db)
    logs = await compose_service.send_bulk(
        tenant_id=school.tenant_id,
        school_id=school.school_id,
        recipients=email_recipients,
        subject=data.subject,
        body=data.body,
        sent_by=UUID(user["user_id"]),
    )

    return [EmailLogResponse.model_validate(log) for log in logs]


@router.get(
    "/history",
    response_model=EmailHistoryResponse,
    summary="Email sending history",
    dependencies=[Depends(require_permissions("communications.read"))],
)
async def get_email_history(
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    email_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
) -> EmailHistoryResponse:
    """Return paginated email log for the current tenant."""
    # Defense-in-depth: always scope by tenant_id
    conditions = [EmailLog.tenant_id == school.tenant_id]

    if email_status:
        try:
            status_enum = EmailStatus(email_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status value: {email_status}",
            )
        conditions.append(EmailLog.status == status_enum)

    count_stmt = select(func.count()).select_from(EmailLog).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    offset = (page - 1) * page_size
    stmt = (
        select(EmailLog)
        .where(*conditions)
        .order_by(EmailLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return EmailHistoryResponse(
        items=[EmailLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/stats",
    response_model=EmailStatsResponse,
    summary="Email delivery statistics",
    dependencies=[Depends(require_permissions("communications.read"))],
)
async def get_email_stats(
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
) -> EmailStatsResponse:
    """Return aggregate email delivery statistics for the tenant."""
    # Defense-in-depth: always scope by tenant_id
    stmt = (
        select(EmailLog.status, func.count().label("cnt"))
        .where(EmailLog.tenant_id == school.tenant_id)
        .group_by(EmailLog.status)
    )
    result = await db.execute(stmt)
    rows = result.all()

    counts: dict[str, int] = {row.status.value: row.cnt for row in rows}

    return EmailStatsResponse(
        total_sent=counts.get("sent", 0),
        total_failed=counts.get("failed", 0),
        total_pending=counts.get("pending", 0),
        total_delivered=counts.get("delivered", 0),
        total_bounced=counts.get("bounced", 0),
    )

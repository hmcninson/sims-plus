"""
SIMS Plus - Recipient Resolution Endpoint

Resolves an audience segment into a concrete list of recipients
with their contact details. Used by the frontend to preview who
will receive a message before actually sending it.

Permission: communications.read (any user who can view messaging data)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    DatabaseSession,
    SchoolCtx,
    ValidatedUser,
    require_permissions,
)
from app.schemas.messaging import RecipientInfo, RecipientListResponse, RecipientType
from app.services.messaging.recipient_resolver import (
    RecipientResolver,
    RecipientResolverError,
)

router = APIRouter(prefix="/recipients", tags=["Recipients"])


@router.get(
    "/resolve",
    response_model=RecipientListResponse,
    summary="Resolve audience to recipient list",
    dependencies=[Depends(require_permissions("communications.read"))],
)
async def resolve_recipients(
    school: SchoolCtx,
    db: DatabaseSession,
    user: ValidatedUser,
    audience: RecipientType = Query(..., description="Audience segment to resolve"),
    class_id: UUID | None = Query(None, description="Class ID (required for class_parents)"),
) -> RecipientListResponse:
    """
    Preview the list of recipients for a given audience segment.

    This endpoint does NOT send any messages -- it only resolves names
    and contact details so the admin can review before sending.
    """
    if audience == RecipientType.CLASS_PARENTS and not class_id:
        raise HTTPException(
            status_code=422,
            detail="class_id query parameter is required when audience is class_parents",
        )

    if audience == RecipientType.SPECIFIC:
        # Nothing to resolve; the caller already knows the recipients
        return RecipientListResponse(recipients=[], total=0)

    resolver = RecipientResolver(db)
    try:
        raw_recipients = await resolver.resolve(
            tenant_id=school.tenant_id,
            audience=audience.value,
            school_id=school.school_id,
            class_id=class_id,
        )
    except RecipientResolverError as e:
        raise HTTPException(status_code=e.code, detail=e.message)

    recipients = [RecipientInfo(**r) for r in raw_recipients]

    return RecipientListResponse(
        recipients=recipients,
        total=len(recipients),
    )

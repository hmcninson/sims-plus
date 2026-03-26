"""
SIMS Plus - Admission Decision Endpoints

Admin endpoints for making single and bulk admission decisions,
generating admission/rejection letters (PDF), and managing the waitlist.

IMPORTANT: Do NOT use 'from __future__ import annotations' in this file.
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
    AdmissionDecisionCreate,
    AdmissionDecisionResponse,
    BulkDecisionRequest,
    BulkDecisionResponse,
    GenerateLetterResponse,
    WaitlistEntryResponse,
    WaitlistListResponse,
    WaitlistPromoteRequest,
    WaitlistRankUpdate,
    WaitlistReorderRequest,
)
from app.services.admissions import DecisionService, DecisionServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/decisions")


def _handle_error(e: DecisionServiceError) -> HTTPException:
    """Map service errors to HTTP responses."""
    status_map = {
        "NOT_FOUND": 404,
        "INVALID_TRANSITION": 422,
        "INVALID_DECISION_TYPE": 422,
        "MISSING_CLASS": 422,
        "DECISION_EXISTS": 409,
        # Phase 2 additions
        "INVALID_STATUS": 422,
        "INVALID_RESPONSE": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=AdmissionDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Make admission decision",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def make_decision(
    data: AdmissionDecisionCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionDecisionResponse:
    """
    Make an admission decision for a single application.

    Creates admission_decisions record and updates application status:
    - accepted -> status=OFFERED (not ACCEPTED -- applicant must accept offer)
    - rejected -> status=REJECTED
    - waitlisted -> status=WAITLISTED
    - deferred -> status=DEFERRED

    Sends notification to primary guardian on acceptance/rejection.
    """
    service = DecisionService(db)
    try:
        # Unpack Pydantic model fields into individual kwargs
        return await service.decide(
            tenant_id=UUID(user["tenant_id"]),
            application_id=data.application_id,
            decision_type=data.decision_type.value,
            decided_by=UUID(user["user_id"]),
            offered_class_id=data.offered_class_id,
            conditions=data.conditions,
            response_deadline=data.response_deadline,
        )
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/bulk",
    response_model=BulkDecisionResponse,
    summary="Bulk admission decision",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def bulk_decision(
    data: BulkDecisionRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BulkDecisionResponse:
    """
    Make bulk admission decisions.

    Each decision is processed in its own savepoint:
    - If one fails, others still succeed
    - Returns partial success: {succeeded: [...], failed: [...]}
    - If ALL fail -> HTTP 422; if some succeed -> HTTP 200

    Max 100 applications per request.
    """
    service = DecisionService(db)
    # bulk_decide returns dict with "succeeded" and "failed" lists
    result = await service.bulk_decide(
        tenant_id=UUID(user["tenant_id"]),
        application_ids=data.application_ids,
        decision_type=data.decision_type.value,
        decided_by=UUID(user["user_id"]),
        offered_class_id=data.offered_class_id,
        conditions=data.conditions,
        response_deadline=data.response_deadline,
    )

    succeeded = result["succeeded"]
    failed = result["failed"]

    # If every decision failed, return 422 to signal complete failure
    if len(succeeded) == 0 and len(failed) > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "All decisions failed",
                "failed": failed,
            },
        )

    return BulkDecisionResponse(
        succeeded=succeeded,
        failed=failed,
        total_succeeded=len(succeeded),
        total_failed=len(failed),
    )


# ================================================================
# Letter Generation (Enrollment Gap Closure Phase 2)
# ================================================================


@router.post(
    "/{decision_id}/generate-letter",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate admission letter PDF",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def generate_admission_letter(
    decision_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> GenerateLetterResponse:
    """Generate admission letter PDF and upload to S3. Returns presigned URL."""
    service = DecisionService(db)
    try:
        letter_url = await service.generate_admission_letter(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
        )
        return GenerateLetterResponse(
            decision_id=decision_id,
            letter_url=letter_url,
            letter_type="admission",
        )
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{decision_id}/generate-rejection-letter",
    response_model=GenerateLetterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate rejection letter PDF",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def generate_rejection_letter(
    decision_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    rejection_reason: str | None = None,
) -> GenerateLetterResponse:
    """Generate rejection letter PDF and upload to S3. Returns presigned URL."""
    service = DecisionService(db)
    try:
        letter_url = await service.generate_rejection_letter(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
            rejection_reason=rejection_reason,
        )
        return GenerateLetterResponse(
            decision_id=decision_id,
            letter_url=letter_url,
            letter_type="rejection",
        )
    except DecisionServiceError as e:
        raise _handle_error(e)


# ================================================================
# Waitlist Management (Enrollment Gap Closure Phase 2)
# ================================================================


@router.patch(
    "/{decision_id}/waitlist-rank",
    response_model=AdmissionDecisionResponse,
    summary="Update waitlist rank",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def update_waitlist_rank(
    decision_id: UUID,
    data: WaitlistRankUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionDecisionResponse:
    """Set or update the waitlist rank for a waitlisted decision."""
    service = DecisionService(db)
    try:
        decision = await service.update_waitlist_rank(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
            rank=data.rank,
        )
        return AdmissionDecisionResponse.model_validate(decision)
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/reorder-waitlist",
    response_model=list[AdmissionDecisionResponse],
    summary="Bulk reorder waitlist",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def reorder_waitlist(
    data: WaitlistReorderRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> list[AdmissionDecisionResponse]:
    """Bulk reorder waitlist by specifying decision IDs in desired rank order."""
    service = DecisionService(db)
    try:
        decisions = await service.reorder_waitlist(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=data.period_id,
            ordered_decision_ids=data.ordered_decision_ids,
        )
        return [AdmissionDecisionResponse.model_validate(d) for d in decisions]
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{decision_id}/promote-waitlist",
    response_model=AdmissionDecisionResponse,
    summary="Promote waitlisted applicant to offered",
    dependencies=[Depends(require_permissions("admissions.decide"))],
)
async def promote_from_waitlist(
    decision_id: UUID,
    data: WaitlistPromoteRequest,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> AdmissionDecisionResponse:
    """Promote a waitlisted applicant to offered status."""
    service = DecisionService(db)
    try:
        decision = await service.promote_from_waitlist(
            tenant_id=UUID(user["tenant_id"]),
            decision_id=decision_id,
            offered_class_id=data.offered_class_id,
            response_deadline=data.response_deadline,
            conditions=data.conditions,
            promoted_by=UUID(user["user_id"]),
        )
        return AdmissionDecisionResponse.model_validate(decision)
    except DecisionServiceError as e:
        raise _handle_error(e)


@router.get(
    "/waitlist",
    response_model=WaitlistListResponse,
    summary="List waitlisted decisions",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_waitlist(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    period_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> WaitlistListResponse:
    """List waitlisted decisions ordered by rank. Nulls appear last."""
    service = DecisionService(db)
    try:
        items, total = await service.list_waitlisted(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            period_id=period_id,
            page=page,
            page_size=page_size,
        )
        return WaitlistListResponse(
            items=[WaitlistEntryResponse(**item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    except DecisionServiceError as e:
        raise _handle_error(e)

"""
SIMS Plus - Boarding Roll Call Endpoints

Endpoints for conducting boarding house roll calls, viewing roll call history,
and generating attendance reports over date ranges.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_permissions,
)
from app.schemas.boarding import (
    BoardingRollCallDetailResponse,
    BoardingRollCallResponse,
    BoardingRollCallSubmit,
    RollCallEntryResponse,
)
from app.services.boarding import BoardingServiceError, RollCallService

from ._helpers import _get_school_id, _handle_service_error

router = APIRouter()


@router.post(
    "/roll-calls",
    response_model=BoardingRollCallDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create roll call",
    dependencies=[Depends(require_permissions("boarding.write"))],
)
async def create_roll_call(
    data: BoardingRollCallSubmit,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingRollCallDetailResponse:
    """
    Submit a roll call for a house with all student entries.

    The conducting user is automatically set from the authenticated user's JWT.
    """
    service = RollCallService(db)

    try:
        roll_call = await service.create_roll_call(
            tenant_id=tenant.tenant_id,
            school_id=UUID(user["school_id"]),
            house_id=data.house_id,
            roll_call_date=data.date,
            roll_call_type=data.roll_call_type,
            conducted_by_id=UUID(user["user_id"]),
            entries=[e.model_dump() for e in data.entries],
            notes=data.notes,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    return _build_roll_call_detail(roll_call)


@router.get(
    "/roll-calls",
    response_model=list[BoardingRollCallResponse],
    summary="List roll calls",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def list_roll_calls(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    house_id: UUID | None = Query(None, description="Filter by house"),
    date_from: date | None = Query(None, description="Start date filter"),
    date_to: date | None = Query(None, description="End date filter"),
    roll_call_type: str | None = Query(
        None,
        description="Filter by type (morning, evening, lights_out, emergency)",
    ),
) -> list[BoardingRollCallResponse]:
    """List roll calls with optional filters."""
    school_id = _get_school_id(user)
    service = RollCallService(db)

    roll_calls = await service.get_roll_calls(
        tenant_id=tenant.tenant_id,
        school_id=school_id,
        house_id=house_id,
        date_from=date_from,
        date_to=date_to,
        roll_call_type=roll_call_type,
    )

    results = []
    for rc in roll_calls:
        results.append(
            BoardingRollCallResponse(
                id=rc.id,
                tenant_id=rc.tenant_id,
                school_id=rc.school_id,
                house_id=rc.house_id,
                date=rc.date,
                roll_call_type=rc.roll_call_type.value
                if hasattr(rc.roll_call_type, "value")
                else rc.roll_call_type,
                conducted_by_id=rc.conducted_by_id,
                notes=rc.notes,
                created_at=rc.created_at,
                updated_at=rc.updated_at,
            )
        )
    return results


@router.get(
    "/roll-calls/report",
    summary="Roll call report",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_roll_call_report(
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
    house_id: UUID = Query(..., description="House to report on"),
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
) -> list[dict]:
    """
    Generate a roll call attendance report for a house over a date range.

    Returns per-student aggregated counts and attendance percentages.
    """
    service = RollCallService(db)

    try:
        return await service.get_roll_call_report(
            tenant_id=tenant.tenant_id,
            house_id=house_id,
            start_date=start_date,
            end_date=end_date,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)


@router.get(
    "/roll-calls/{roll_call_id}",
    response_model=BoardingRollCallDetailResponse,
    summary="Get roll call detail",
    dependencies=[Depends(require_permissions("boarding.read"))],
)
async def get_roll_call(
    roll_call_id: UUID,
    tenant: RequestTenant,
    user: ValidatedUser,
    db: DatabaseSession,
) -> BoardingRollCallDetailResponse:
    """Get a roll call by ID with all entries and student names."""
    service = RollCallService(db)

    try:
        roll_call = await service.get_roll_call(
            tenant_id=tenant.tenant_id,
            roll_call_id=roll_call_id,
        )
    except BoardingServiceError as e:
        raise _handle_service_error(e)

    return _build_roll_call_detail(roll_call)


def _build_roll_call_detail(rc) -> BoardingRollCallDetailResponse:
    """Build a detailed roll call response with entries and counts."""
    entries = []
    present_count = 0
    absent_count = 0

    if hasattr(rc, "entries") and rc.entries:
        for entry in rc.entries:
            entry_status = (
                entry.status.value
                if hasattr(entry.status, "value")
                else entry.status
            )
            if entry_status == "present":
                present_count += 1
            elif entry_status in ("absent", "awol"):
                absent_count += 1

            # Build student name from loaded relationship
            student_name = None
            if hasattr(entry, "student") and entry.student:
                student_name = (
                    f"{entry.student.first_name} {entry.student.last_name}"
                )

            entries.append(
                RollCallEntryResponse(
                    id=entry.id,
                    roll_call_id=entry.roll_call_id,
                    student_id=entry.student_id,
                    status=entry_status,
                    notes=entry.notes,
                    student_name=student_name,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                )
            )

    # House and conductor names from loaded relationships
    house_name = rc.house.name if hasattr(rc, "house") and rc.house else None
    conducted_by_name = None
    if hasattr(rc, "conducted_by") and rc.conducted_by:
        conducted_by_name = (
            f"{rc.conducted_by.first_name} {rc.conducted_by.last_name}"
        )

    return BoardingRollCallDetailResponse(
        id=rc.id,
        tenant_id=rc.tenant_id,
        school_id=rc.school_id,
        house_id=rc.house_id,
        date=rc.date,
        roll_call_type=rc.roll_call_type.value
        if hasattr(rc.roll_call_type, "value")
        else rc.roll_call_type,
        conducted_by_id=rc.conducted_by_id,
        notes=rc.notes,
        created_at=rc.created_at,
        updated_at=rc.updated_at,
        house_name=house_name,
        conducted_by_name=conducted_by_name,
        entries=entries,
        present_count=present_count,
        absent_count=absent_count,
        total_count=len(entries),
    )

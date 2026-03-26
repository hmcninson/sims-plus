"""
SIMS Plus - School Event Endpoints

Tours, open days, and orientation event management.
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
from app.schemas.event import (
    AttendanceUpdate,
    EventCreate,
    EventListResponse,
    EventResponse,
    EventStatsResponse,
    EventUpdate,
    RegistrationCreate,
    RegistrationResponse,
)
from app.services.admissions import EventService, EventServiceError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events")


def _handle_error(e: EventServiceError) -> HTTPException:
    status_map = {
        "NOT_FOUND": 404,
        "REG_NOT_FOUND": 404,
        "NOT_UPCOMING": 409,
        "EVENT_FULL": 409,
        "DUPLICATE_REGISTRATION": 409,
        "INVALID_TYPE": 422,
    }
    return HTTPException(
        status_code=status_map.get(e.code, 400),
        detail=e.message,
    )


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create school event",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def create_event(
    data: EventCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        event = await svc.create_event(
            tenant_id=UUID(user["tenant_id"]),
            school_id=school.school_id,
            **data.model_dump(),
        )
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.get(
    "",
    response_model=EventListResponse,
    summary="List school events",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_events(
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    event_type: str | None = Query(None),
    event_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EventListResponse:
    svc = EventService(db)
    items, total = await svc.list_events(
        tenant_id=UUID(user["tenant_id"]),
        school_id=school.school_id,
        event_type=event_type,
        status=event_status,
        page=page,
        page_size=page_size,
    )
    return EventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event detail",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_event(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        event = await svc._get_event(UUID(user["tenant_id"]), event_id)
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update event",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        # Only pass non-None values to the service
        update_data = data.model_dump(exclude_unset=True)
        event = await svc.update_event(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            **update_data,
        )
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.delete(
    "/{event_id}",
    response_model=EventResponse,
    summary="Cancel event",
    dependencies=[Depends(require_permissions("admissions.delete"))],
)
async def cancel_event(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventResponse:
    try:
        svc = EventService(db)
        event = await svc.cancel_event(UUID(user["tenant_id"]), event_id)
        return EventResponse.model_validate(event)
    except EventServiceError as e:
        raise _handle_error(e)


@router.post(
    "/{event_id}/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register for event",
    dependencies=[Depends(require_permissions("admissions.create"))],
)
async def register_for_event(
    event_id: UUID,
    data: RegistrationCreate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RegistrationResponse:
    try:
        svc = EventService(db)
        reg = await svc.register(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            **data.model_dump(),
        )
        return RegistrationResponse.model_validate(reg)
    except EventServiceError as e:
        raise _handle_error(e)


@router.delete(
    "/{event_id}/registrations/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel registration",
    dependencies=[Depends(require_permissions("admissions.delete"))],
)
async def cancel_registration(
    event_id: UUID,
    registration_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
):
    try:
        svc = EventService(db)
        await svc.delete_registration(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            registration_id=registration_id,
        )
    except EventServiceError as e:
        raise _handle_error(e)


@router.patch(
    "/{event_id}/registrations/{registration_id}/attendance",
    response_model=RegistrationResponse,
    summary="Mark attendance",
    dependencies=[Depends(require_permissions("admissions.update"))],
)
async def mark_attendance(
    event_id: UUID,
    registration_id: UUID,
    data: AttendanceUpdate,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> RegistrationResponse:
    try:
        svc = EventService(db)
        reg = await svc.mark_attendance(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            registration_id=registration_id,
            attended=data.attended,
        )
        return RegistrationResponse.model_validate(reg)
    except EventServiceError as e:
        raise _handle_error(e)


@router.get(
    "/{event_id}/registrations",
    response_model=list[RegistrationResponse],
    summary="List event registrations",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def list_registrations(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> list[RegistrationResponse]:
    try:
        svc = EventService(db)
        items, total = await svc.list_registrations(
            tenant_id=UUID(user["tenant_id"]),
            event_id=event_id,
            page=page,
            page_size=page_size,
        )
        return [RegistrationResponse.model_validate(r) for r in items]
    except EventServiceError as e:
        raise _handle_error(e)


@router.get(
    "/{event_id}/stats",
    response_model=EventStatsResponse,
    summary="Event statistics",
    dependencies=[Depends(require_permissions("admissions.read"))],
)
async def get_event_stats(
    event_id: UUID,
    school: SchoolCtx,
    user: ValidatedUser,
    db: DatabaseSession,
) -> EventStatsResponse:
    try:
        svc = EventService(db)
        return await svc.get_event_stats(UUID(user["tenant_id"]), event_id)
    except EventServiceError as e:
        raise _handle_error(e)
